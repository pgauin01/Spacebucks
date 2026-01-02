import json
from web3 import Web3
import re
from solcx import compile_source, install_solc

# --- CONFIGURATION ---
RPC_URL = "HTTP://172.19.224.1:8545"
# PASTE YOUR KEY HERE
PRIVATE_KEY = "0xb61560436aa204805b5c51c6dbfcf39d64522ec104c0f69399451e4c8eeca605"



# Token Settings
TOKEN_NAME = "SpaceBucks"
TOKEN_SYMBOL = "SPX"
TOKEN_SUPPLY = 1000

# 1. UPDATED V3 SOLIDITY CODE (Marketplace Logic)
SOLIDITY_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;

contract SpaceBucks {
    string public name;
    string public symbol;
    uint8 public decimals = 18;
    uint256 public totalSupply;
    
    // 1 ETH = 1000 SPX (Simple Exchange Rate)
    uint256 public constant RATE = 1000; 

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    // --- STRUCTS & MAPPINGS ---
    struct Question {
        address author;
        string content;
        uint256 bounty;
        bool solved;
    }
    mapping(uint256 => Question) public questions;
    uint256 public nextQuestionId;

    // --- EVENTS ---
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event TokensPurchased(address indexed buyer, uint256 amountETH, uint256 amountSPX);
    event QuestionPosted(uint256 indexed questionId, address indexed author, string content, uint256 bounty);
    event AnswerPosted(uint256 indexed questionId, address indexed answerer, string content);
    event BountyAwarded(uint256 indexed questionId, address indexed winner, uint256 amount);

    constructor(string memory _name, string memory _symbol, uint256 _supply) {
        name = _name;
        symbol = _symbol;
        _mint(msg.sender, _supply * 10**decimals);
    }

    // --- 1. BUY TOKENS (Crowdsale) ---
    function buyTokens() external payable {
        require(msg.value > 0, "Send ETH to buy tokens");
        uint256 tokensToBuy = msg.value * RATE; // Calculate SPX amount
        _mint(msg.sender, tokensToBuy);
        emit TokensPurchased(msg.sender, msg.value, tokensToBuy);
    }

    // --- 2. POST QUESTION (With Bounty) ---
    function postQuestion(string memory content, uint256 bounty) external {
        // Transfer bounty from User -> Contract (Escrow)
        require(balanceOf[msg.sender] >= bounty, "Insufficient SPX for bounty");
        _transfer(msg.sender, address(this), bounty);

        questions[nextQuestionId] = Question(msg.sender, content, bounty, false);
        emit QuestionPosted(nextQuestionId, msg.sender, content, bounty);
        nextQuestionId++;
    }

    // --- 3. ANSWER (Just an event for cheap storage) ---
    function postAnswer(uint256 questionId, string memory content) external {
        emit AnswerPosted(questionId, msg.sender, content);
    }

    // --- 4. SELECT WINNER ---
    function awardBounty(uint256 questionId, address winner) external {
        Question storage q = questions[questionId];
        require(msg.sender == q.author, "Only author can pick winner");
        require(!q.solved, "Bounty already awarded");
        
        q.solved = true;
        _transfer(address(this), winner, q.bounty); // Contract pays the winner
        emit BountyAwarded(questionId, winner, q.bounty);
    }

    // --- STANDARD ERC20 LOGIC ---
    function transfer(address recipient, uint256 amount) external returns (bool) {
        return _transfer(msg.sender, recipient, amount);
    }
    
    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool) {
        uint256 currentAllowance = allowance[sender][msg.sender];
        require(currentAllowance >= amount, "ERC20: transfer amount exceeds allowance");
        allowance[sender][msg.sender] = currentAllowance - amount;
        return _transfer(sender, recipient, amount);
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

# 2. SETUP & COMPILE
print("Connecting to Ganache...")
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)
print(f"Deploying from: {account.address}")

print("Installing Compiler (0.8.19)...")
install_solc('0.8.19')

print("Compiling Contract...")
compiled_sol = compile_source(
    SOLIDITY_SOURCE,
    output_values=['abi', 'bin'],
    solc_version='0.8.19'
)

# Get the compiled object
contract_id, contract_interface = next(iter(compiled_sol.items()))
bytecode = contract_interface['bin']
abi = contract_interface['abi']

# 3. DEPLOY
SpaceBucks = w3.eth.contract(abi=abi, bytecode=bytecode)

# We pass the arguments defined at the top of the script
print(f"Deploying {TOKEN_NAME} ({TOKEN_SYMBOL})...")
tx = SpaceBucks.constructor(TOKEN_NAME, TOKEN_SYMBOL, TOKEN_SUPPLY).build_transaction({
    "chainId": w3.eth.chain_id,
    "gasPrice": w3.eth.gas_price,
    "from": account.address,
    "nonce": w3.eth.get_transaction_count(account.address)
})

print("Signing and sending...")
signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

print(f"Tx Hash: {tx_hash.hex()}")
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

print("---")
print(f"SUCCESS! {TOKEN_NAME} deployed at: {tx_receipt.contractAddress}")

# 4. VERIFY BALANCE
contract_instance = w3.eth.contract(address=tx_receipt.contractAddress, abi=abi)
balance = contract_instance.functions.balanceOf(account.address).call()
print(f"Your Balance: {balance / 10**18} {TOKEN_SYMBOL}")