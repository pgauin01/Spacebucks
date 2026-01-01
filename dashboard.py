import streamlit as st
import requests

# --- CONFIGURATION ---
# This points to your running FastAPI server
API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="SpaceBucks Wallet", page_icon="🚀", layout="centered")

# --- HEADER ---
st.title("🚀 SpaceBucks (SPX) Dashboard")
st.markdown("Manage your tokens on the local Ganache Blockchain.")

# Check API Connection
try:
    response = requests.get(f"{API_URL}/")
    if response.status_code == 200:
        st.success(f"✅ Connected to API: {API_URL}")
    else:
        st.error("⚠️ API connected but returned an error.")
except requests.exceptions.ConnectionError:
    st.error(f"❌ Could not connect to {API_URL}. Is uvicorn running?")
    st.stop()

st.divider()

# --- TABS FOR ACTIONS ---
tab1, tab2, tab3 = st.tabs(["💰 Check Balance", "💸 Send Tokens", "📜 History"])


# --- TAB 1: CHECK BALANCE ---
with tab1:
    st.subheader("Wallet Viewer")
    
    # Input address (defaulting to the one you used before for convenience)
    address_input = st.text_input(
        "Enter Wallet Address", 
        value="0x476Beb6bf1540f4dC41d04a64d12f5403119590b",
        placeholder="0x..."
    )

    if st.button("Check Balance"):
        if len(address_input) != 42:
            st.warning("Please enter a valid 42-character Ethereum address.")
        else:
            with st.spinner("Querying blockchain..."):
                try:
                    res = requests.get(f"{API_URL}/balance/{address_input}")
                    if res.status_code == 200:
                        data = res.json()
                        balance = data['balance_spx']
                        st.metric(label="Current Balance", value=f"{balance:,.2f} SPX")
                    else:
                        st.error(f"Error: {res.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

# --- TAB 2: SEND TOKENS ---
with tab2:
    st.subheader("Transfer Fund")
    
    col1, col2 = st.columns(2)
    with col1:
        recipient = st.text_input("Recipient Address", placeholder="0x...")
    with col2:
        amount = st.number_input("Amount (SPX)", min_value=0.01, value=10.0, step=1.0)

    if st.button("Send Transaction 🚀"):
        if not recipient or len(recipient) != 42:
            st.error("Invalid Recipient Address")
        else:
            payload = {
                "to_address": recipient,
                "amount": amount
            }
            
            with st.spinner("Signing and sending transaction..."):
                try:
                    res = requests.post(f"{API_URL}/transfer", json=payload)
                    
                    if res.status_code == 200:
                        data = res.json()
                        st.balloons() # Fun visual effect
                        st.success("Transaction Successful!")
                        
                        # Show Receipt details
                        st.json({
                            "Status": "Confirmed",
                            "Amount Sent": f"{data['amount_sent']} SPX",
                            "Recipient": data['recipient'],
                            "Transaction Hash": data['tx_hash']
                        })
                        st.info("Check your Ganache 'Transactions' tab to see this block!")
                    else:
                        st.error(f"Transaction Failed: {res.text}")
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# Change the tab definition line to include "📜 History"

# ... (Keep Tab 1 and Tab 2 code exactly as it is) ...

# --- TAB 3: TRANSACTION HISTORY ---
with tab3:
    st.subheader("Blockchain Activity Log")
    
    if st.button("Refresh History 🔄"):
        with st.spinner("Scanning blockchain events..."):
            try:
                res = requests.get(f"{API_URL}/history")
                if res.status_code == 200:
                    transactions = res.json()
                    
                    if not transactions:
                        st.info("No transactions found on the blockchain yet.")
                    else:
                        # Display as a clean data table
                        st.dataframe(
                            transactions, 
                            column_config={
                                "tx_hash": "Transaction Hash",
                                "from": "Sender",
                                "to": "Receiver",
                                "amount": st.column_config.NumberColumn(
                                    "Amount (SPX)",
                                    format="%.2f ⭐" 
                                ),
                                "block_number": "Block #"
                            },
                            use_container_width=True,
                            hide_index=True
                        )
                else:
                    st.error("Failed to fetch history.")
            except Exception as e:
                st.error(f"Connection Error: {e}")

# --- FOOTER ---
st.markdown("---")
st.caption("Powered by FastAPI, Web3.py, and Ganache")