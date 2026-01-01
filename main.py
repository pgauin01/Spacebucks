from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
from solcx import compile_source, install_solc

from fastapi.staticfiles import StaticFiles # Add this import

# Add this line AFTER creating 'app = FastAPI(...)'

# --- CONFIGURATION ---
RPC_URL = "HTTP://172.19.224.1:8545"
CONTRACT_ADDRESS = "0x15ea89927a369997c4b4c8bD46A4a51Ed014e27d"  # <--- PASTE YOUR ADDRESS HERE
SENDER_PRIVATE_KEY = "0xb61560436aa204805b5c51c6dbfcf39d64522ec104c0f69399451e4c8eeca605"             # <--- PASTE YOUR PRIVATE KEY HERE

app = FastAPI(title="SpaceBucks API")
app.mount("/dapp", StaticFiles(directory="static", html=True), name="static")

# Connect to Ganache
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(SENDER_PRIVATE_KEY)

# Store ABI globally so we compile only once
TOKEN_ABI = None

# --- SOLIDITY SOURCE (Same as before) ---
SOLIDITY_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;
contract SpaceBucks {
    string public name;
    string public symbol;
    uint8 public decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    event Transfer(address indexed from, address indexed to, uint256 value);
    constructor(string memory _name, string memory _symbol, uint256 _supply) {
        name = _name;
        symbol = _symbol;
        _mint(msg.sender, _supply * 10**decimals);
    }
    function transfer(address recipient, uint256 amount) external returns (bool) {
        return _transfer(msg.sender, recipient, amount);
    }
    function _transfer(address sender, address recipient, uint256 amount) internal returns (bool) {
        require(balanceOf[sender] >= amount, "ERC20: transfer amount exceeds balance");
        balanceOf[sender] -= amount;
        balanceOf[recipient] += amount;
        emit Transfer(sender, recipient, amount);
        return true;
    }
    function _mint(address to, uint256 amount) internal {
        totalSupply += amount;
        balanceOf[to] += amount;
    }
}
"""

@app.on_event("startup")
def load_contract():
    """Compiles the code once when server starts to get the ABI."""
    global TOKEN_ABI
    print("Compiling contract to get ABI...")
    install_solc('0.8.19')
    compiled = compile_source(SOLIDITY_SOURCE, solc_version='0.8.19')
    contract_id, contract_interface = next(iter(compiled.items()))
    TOKEN_ABI = contract_interface['abi']
    print("API Ready!")

# --- DATA MODELS ---
class TransferRequest(BaseModel):
    to_address: str
    amount: float

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "online", "token": "SpaceBucks"}

@app.get("/balance/{address}")
def get_balance(address: str):
    """Checks the SPX balance of any address."""
    if not w3.is_address(address):
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=TOKEN_ABI)
    balance_wei = contract.functions.balanceOf(address).call()
    
    return {
        "address": address,
        "balance_spx": balance_wei / 10**18
    }

@app.post("/transfer")
def transfer_tokens(req: TransferRequest):
    """Transfers SPX from the Server Wallet to a User."""
    if not w3.is_address(req.to_address):
        raise HTTPException(status_code=400, detail="Invalid receiver address")

    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=TOKEN_ABI)
    
    # 1. Build Transaction
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.transfer(
        req.to_address,
        int(req.amount * 10**18) # Convert to Wei
    ).build_transaction({
        "chainId": w3.eth.chain_id,
        "gasPrice": w3.eth.gas_price,
        "from": account.address,
        "nonce": nonce
    })

    # 2. Sign & Send
    try:
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=SENDER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        return {
            "status": "success",
            "tx_hash": tx_hash.hex(),
            "amount_sent": req.amount,
            "recipient": req.to_address
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# --- ADD THIS TO main.py ---

# --- UPDATE THIS FUNCTION IN main.py ---

@app.get("/history")
def get_history():
    """Fetches all past Transfer events from the blockchain."""
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=TOKEN_ABI)
    
    # FIX: Use get_logs() instead of create_filter()
    # This fetches historical logs in one request without creating a stateful filter ID.
    try:
        # Try the standard argument first
        events = contract.events.Transfer.get_logs(fromBlock=0)
    except TypeError:
        # Fallback for strict Web3.py v6+ (uses snake_case)
        events = contract.events.Transfer.get_logs(from_block=0)
    
    formatted_history = []
    
    for event in events:
        args = event['args']
        formatted_history.append({
            "tx_hash": event['transactionHash'].hex(),
            "from": args['from'],
            "to": args['to'],
            "amount": args['value'] / 10**18, # Convert Wei to SPX
            "block_number": event['blockNumber']
        })
        
    # Return newest first
    return formatted_history[::-1]  