import requests
import json

# We make the prompt very explicit about the version
user_prompt = "Create an ERC20 token named SpaceBucks with symbol SPX and 1000 supply."
strict_prompt = f"{user_prompt} IMPORTANT: You MUST use Solidity version 0.8.19 exactly. Do not use 0.8.20 or newer."

payload = {
    "prompt": strict_prompt
}

try:
    print("Requesting contract generation (Strict 0.8.19)...")
    response = requests.post("http://localhost:3000/generate", json=payload)
    response.raise_for_status()

    data = response.json()
    
    # --- SANITY CHECK ---
    # Let's check the source code before saving to see if the API listened
    source = data.get("sourceCode", "")
    if "pragma solidity ^0.8.20" in source or "pragma solidity 0.8.20" in source:
        print("WARNING: The API ignored the version constraint and used 0.8.20.")
        print("Try Option 1 (Update Ganache) instead.")
    else:
        print("Success: API generated compatible code (likely 0.8.19).")

    with open("contract_data.json", "w") as f:
        json.dump(data, f, indent=4)
    
    print("Saved to 'contract_data.json'")

except Exception as e:
    print(f"Error: {e}")