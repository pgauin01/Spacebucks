from web3 import Web3
from solcx import compile_source

# --- CONFIGURATION ---
RPC_URL = "HTTP://172.19.224.1:8545"
# 1. Your Account (The Sender)
SENDER_PRIVATE_KEY = "0xb61560436aa204805b5c51c6dbfcf39d64522ec104c0f69399451e4c8eeca605"
# 2. The Contract Address (From your success output)
CONTRACT_ADDRESS = "0x15ea89927a369997c4b4c8bD46A4a51Ed014e27d" 

# 3. Receiver Account (Pick any other address from Ganache)
RECEIVER_ADDRESS = "0x476Beb6bf1540f4dC41d04a64d12f5403119590b" 

# Re-using the source to get the ABI exactly as before
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
    event Approval(address indexed owner, address indexed spender, uint256 value);
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
        emit Transfer(address(0), to, amount);
    }
}
"""


# Connect
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(SENDER_PRIVATE_KEY)
print(f"Sender: {account.address}")

# Compile to get ABI (fast way to get interface)
compiled = compile_source(SOLIDITY_SOURCE, solc_version='0.8.19')
contract_id, contract_interface = next(iter(compiled.items()))
abi = contract_interface['abi']

# Load Contract
token_contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)

# Check Initial Balance
balance_wei = token_contract.functions.balanceOf(account.address).call()
print(f"Initial Balance: {balance_wei / 10**18} SPX")

# --- EXECUTE TRANSFER ---
AMOUNT_TO_SEND = 50 # SPX
print(f"Sending {AMOUNT_TO_SEND} SPX to {RECEIVER_ADDRESS}...")

# 1. Build Transaction
nonce = w3.eth.get_transaction_count(account.address)
tx = token_contract.functions.transfer(
    RECEIVER_ADDRESS, 
    AMOUNT_TO_SEND * 10**18  # Convert to Wei
).build_transaction({
    "chainId": w3.eth.chain_id,
    "gasPrice": w3.eth.gas_price,
    "from": account.address,
    "nonce": nonce
})

# 2. Sign & Send
signed_tx = w3.eth.account.sign_transaction(tx, private_key=SENDER_PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
print(f"Tx Hash: {tx_hash.hex()}")

# 3. Wait & Verify
w3.eth.wait_for_transaction_receipt(tx_hash)

new_balance = token_contract.functions.balanceOf(account.address).call()
receiver_balance = token_contract.functions.balanceOf(RECEIVER_ADDRESS).call()

print("---")
print(f"Transfer Successful!")
print(f"Your New Balance: {new_balance / 10**18} SPX")
print(f"Friend's Balance: {receiver_balance / 10**18} SPX")