import requests
import hashlib
import base64
import json
from typing import Dict, Any
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import MD5

class LBankAPI:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.lbank.info"
        
    def _get_server_timestamp(self) -> str:
        """Get server timestamp from LBANK API"""
        response = requests.get(f"{self.base_url}/v2/timestamp.do")
        return response.json()["data"]
        
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        # Sort parameters alphabetically
        sorted_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        print(f"\nDebug - Sorted parameters: {sorted_params}")
        
        # Create MD5 hash of parameters and convert to uppercase
        md5_hash = hashlib.md5(sorted_params.encode()).hexdigest().upper()
        print(f"Debug - MD5 hash: {md5_hash}")
        
        # Base64 encode the preparedStr (md5_hash) before signing
        prepared_str = base64.b64encode(md5_hash.encode()).decode()
        print(f"Debug - Prepared string (Base64): {prepared_str}")
        
        # Convert secret key to RSA key
        # Format the secret key as a proper PEM format
        pem_key = f"-----BEGIN RSA PRIVATE KEY-----\n{self.secret_key}\n-----END RSA PRIVATE KEY-----"
        rsa_key = RSA.import_key(pem_key)
        
        # Create signature using RSA
        hash_obj = MD5.new(prepared_str.encode())
        signature = pkcs1_15.new(rsa_key).sign(hash_obj)
        
        # Base64 encode the signature
        final_signature = base64.b64encode(signature).decode()
        print(f"Debug - Final signature: {final_signature}")
        return final_signature

    def get_account_balance(self) -> Dict[str, Any]:
        # Get server timestamp
        timestamp = self._get_server_timestamp()
        echostr = "P3LHfw6tUIYWc8R2VQNy0ilKmdg5pjhbxC7"  # Example echostr
        
        params = {
            "api_key": self.api_key,
            "timestamp": timestamp,
            "echostr": echostr,
            "signature_method": "RSA"
        }
        
        # Generate signature
        params["sign"] = self._generate_signature(params)
        
        # Make API request
        headers = {
            "contentType": "application/x-www-form-urlencoded"
        }
        
        print(f"\nDebug - Request URL: {self.base_url}/v2/supplement/user_info_account.do")
        print(f"Debug - Request Headers: {headers}")
        print(f"Debug - Request Parameters: {params}")
        
        response = requests.post(
            f"{self.base_url}/v2/supplement/user_info_account.do",
            data=params,
            headers=headers
        )
        
        print(f"\nDebug - Response Status Code: {response.status_code}")
        print(f"Debug - Response Headers: {response.headers}")
        print(f"Debug - Response Content: {response.text}")
        
        return response.json()

def main():
    # Get API credentials from user
    api_key = input("Please enter your LBANK API key: ")
    secret_key = input("Please enter your LBANK Secret key: ")
    
    # Initialize API client
    client = LBankAPI(api_key, secret_key)
    
    try:
        # Get account balance
        balance_data = client.get_account_balance()
        
        # Extract MNTL and USDT balances
        mntl_balance = None
        usdt_balance = None
        
        print(f"\nDebug - Full balance data: {json.dumps(balance_data, indent=2)}")
        
        for balance in balance_data.get("balances", []):
            if balance["asset"] == "MNTL":
                mntl_balance = balance
            elif balance["asset"] == "USDT":
                usdt_balance = balance
        
        # Display results
        print("\nAccount Balances:")
        print("-" * 40)
        
        if mntl_balance:
            print(f"MNTL Balance:")
            print(f"  Free: {mntl_balance['free']}")
            print(f"  Locked: {mntl_balance['locked']}")
        else:
            print("No MNTL balance found")
            
        print()
        
        if usdt_balance:
            print(f"USDT Balance:")
            print(f"  Free: {usdt_balance['free']}")
            print(f"  Locked: {usdt_balance['locked']}")
        else:
            print("No USDT balance found")
            
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    main() 