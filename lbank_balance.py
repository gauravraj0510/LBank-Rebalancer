import requests
import hashlib
import base64
import json
from typing import Dict, Any
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

def trim_print(text: str, max_length: int = 500) -> str:
    """Trim text to max_length and add ellipsis if truncated"""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

class LBankAPI:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://api.lbank.info"
        
    def _get_server_timestamp(self) -> str:
        """Get server timestamp from LBANK API"""
        response = requests.get(f"{self.base_url}/v2/timestamp.do")
        return response.json()["data"]
        
    def _get_private_key(self, key: str) -> RSA.RsaKey:
        """Convert base64 encoded private key to RSA key"""
        try:
            # Decode base64 key
            key_bytes = base64.b64decode(key)
            # Import as RSA key
            return RSA.import_key(key_bytes)
        except Exception as e:
            # print(trim_print(f"Error loading private key: {str(e)}"))
            raise
        
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        # Sort parameters alphabetically
        sorted_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        # print(trim_print(f"\nDebug - Sorted parameters: {sorted_params}"))
        
        # Create MD5 hash of parameters and convert to uppercase
        md5_hash = hashlib.md5(sorted_params.encode()).hexdigest().upper()
        # print(trim_print(f"Debug - MD5 hash: {md5_hash}"))
        
        try:
            # Get private key
            private_key = self._get_private_key(self.secret_key)
            
            # Create SHA256 hash of the MD5 hash
            hash_obj = SHA256.new(md5_hash.encode())
            
            # Sign using SHA256WithRSA
            signature = pkcs1_15.new(private_key).sign(hash_obj)
            
            # Base64 encode the signature
            final_signature = base64.b64encode(signature).decode()
            # print(trim_print(f"Debug - Final signature: {final_signature}"))
            return final_signature
            
        except Exception as e:
            # print(trim_print(f"Error generating signature: {str(e)}"))
            raise

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
        
        # print(trim_print(f"\nDebug - Request URL: {self.base_url}/v2/supplement/user_info_account.do"))
        # print(trim_print(f"Debug - Request Headers: {headers}"))
        # print(trim_print(f"Debug - Request Parameters: {params}"))
        
        response = requests.post(
            f"{self.base_url}/v2/supplement/user_info_account.do",
            data=params,
            headers=headers
        )
        
        # print(trim_print(f"\nDebug - Response Status Code: {response.status_code}"))
        # print(trim_print(f"Debug - Response Headers: {response.headers}"))
        # print(trim_print(f"Debug - Response Content: {response.text}"))
        
        return response.json()

def main():
    # Get API credentials from user
    api_key = input("Please enter your LBANK API key: ")
    secret_key = input("Please enter your LBANK Secret key: ")
    
    # Initialize API client
    client = LBankAPI(api_key, secret_key)
    
    try:
        # Get account balance
        response = client.get_account_balance()
        
        # Print root variables
        # print("\nResponse Root Variables:")
        # print("-" * 40)
        # for key, value in response.items():
        #     if isinstance(value, (list, tuple)):
        #         print(trim_print(f"{key}: Array with {len(value)} items"))
        #     else:
        #         print(trim_print(f"{key}: {value}"))
        
        # Extract mntl and usdt balances from the nested structure
        mntl_balance = None
        usdt_balance = None
        
        if response.get("result") == "true" and "data" in response:
            balances = response["data"].get("balances", [])
            for balance in balances:
                if balance["asset"].lower() == "mntl":
                    mntl_balance = balance
                elif balance["asset"].lower() == "usdt":
                    usdt_balance = balance
        
        # Display results
        print("\nToken Balances:")
        print("-" * 40)
        
        if mntl_balance:
            print(f"mntl Balance:")
            print(f"  Free: {mntl_balance['free']}")
            print(f"  Locked: {mntl_balance['locked']}")
        else:
            print("No mntl balance found")
            
        print()
        
        if usdt_balance:
            print(f"usdt Balance:")
            print(f"  Free: {usdt_balance['free']}")
            print(f"  Locked: {usdt_balance['locked']}")
        else:
            print("No usdt balance found")
            
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    main() 