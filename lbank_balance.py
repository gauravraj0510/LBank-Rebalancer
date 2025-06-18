import requests
import hashlib
import base64
import json
import time
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

    def place_market_order(self, symbol: str, order_type: str, amount: str) -> Dict[str, Any]:
        """Place a market order on LBANK"""
        timestamp = self._get_server_timestamp()
        echostr = "P3LHfw6tUIYWc8R2VQNy0ilKmdg5pjhbxC7"
        
        # Convert amount to float for comparison
        amount_float = float(amount)
        
        # Minimum order quantities
        MIN_MNTL_QUANTITY = 11000  # Minimum MNTL amount for sell orders
        MIN_USDT_QUANTITY = 5     # Minimum USDT amount for buy orders
        
        # Check minimum quantity based on order type
        if order_type.startswith("buy"):
            min_quantity = MIN_USDT_QUANTITY
        else:
            min_quantity = MIN_MNTL_QUANTITY
            
        if amount_float < min_quantity:
            print(f"\nWarning: Order amount {amount_float} is below minimum quantity {min_quantity}")
            return {"result": False, "msg": "Order amount below minimum quantity"}
        
        params = {
            "api_key": self.api_key,
            "symbol": symbol,
            "type": order_type,
            "amount": amount,
            "price": "1",  # For market orders, price should be 0
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
        
        print(f"\nPlacing {order_type} order with parameters:")
        print(f"Symbol: {symbol}")
        print(f"Amount: {amount}")
        print(f"Price: 1")
        
        response = requests.post(
            f"{self.base_url}/v2/supplement/create_order.do",
            data=params,
            headers=headers
        )
        
        return response.json()

    def get_current_price(self, symbol: str) -> float:
        """Get current price for a trading pair"""
        try:
            response = requests.get(f"{self.base_url}/v2/ticker.do?symbol={symbol}")
            data = response.json()
            if data.get("result") == "true" and "data" in data:
                return float(data["data"][0]["ticker"]["latest"])
            return None
        except Exception as e:
            print(f"Error getting current price: {str(e)}")
            return None

def check_and_rebalance(client: LBankAPI):
    """Check balance and rebalance if needed"""
    try:
        # Get account balance
        response = client.get_account_balance()
        
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
            
        # Check balance difference and place orders if needed
        target_balance = 60000
        min_difference = 11500
        
        if mntl_balance:
            current_balance = float(mntl_balance['free']) + float(mntl_balance['locked'])
            difference = current_balance - target_balance
            abs_difference = abs(difference)
            
            print("\nBalance Difference Check:")
            print("-" * 40)
            print(f"Current Balance: {current_balance}")
            print(f"Target Balance: {target_balance}")
            print(f"Difference: {abs_difference}")
            
            if abs_difference > min_difference:
                print("\nStatus: Action Required")
                
                # Place market order based on difference
                if difference < 0:  # Need to buy
                    # Get current MNTL price
                    current_price = client.get_current_price("mntl_usdt")
                    if current_price is None:
                        print("Could not fetch current MNTL price, using default estimate")
                        current_price = 0.025
                    
                    # Calculate maximum possible buy amount based on USDT balance
                    if usdt_balance:
                        available_usdt = float(usdt_balance['free'])
                        # For market buy, we specify the USDT amount to spend
                        usdt_to_spend = min(available_usdt, abs_difference * current_price)
                        
                        print(f"\nAvailable USDT: {available_usdt}")
                        print(f"Current MNTL price: {current_price} USDT")
                        print(f"USDT to spend: {usdt_to_spend}")
                        print(f"Expected MNTL to receive: {usdt_to_spend / current_price}")
                        
                        if usdt_to_spend >= 10:  # Minimum USDT order value
                            print(f"\nPlacing buy_market order for {usdt_to_spend} USDT")
                            order_response = client.place_market_order(
                                symbol="mntl_usdt",
                                order_type="buy_market",
                                amount=str(usdt_to_spend)
                            )
                            print(f"Order Response: {order_response}")
                        else:
                            print("\nInsufficient USDT balance to place minimum order")
                    else:
                        print("\nNo USDT balance available for buying MNTL")
                    
                else:  # Need to sell
                    print(f"\nPlacing sell_market order for {abs_difference} MNTL")
                    order_response = client.place_market_order(
                        symbol="mntl_usdt",
                        order_type="sell_market",
                        amount=str(abs_difference)
                    )
                    print(f"Order Response: {order_response}")
            else:
                print("\nStatus: No Action Required")
            
    except Exception as e:
        print(f"Error occurred: {str(e)}")

def main():
    # Get API credentials from user (only once at startup)
    print("Please enter your LBANK API credentials (will be reused for all checks):")
    api_key = input("API key: ")
    secret_key = input("Secret key: ")
    
    # Initialize API client
    client = LBankAPI(api_key, secret_key)
    
    # Set the interval in seconds
    DELTA = 300
    
    print(f"\nStarting continuous rebalancing with {DELTA}-second intervals...")
    print("Press Ctrl+C to stop the script")
    
    try:
        while True:
            print(f"\n{'='*50}")
            print(f"Running check at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}")
            
            check_and_rebalance(client)
            
            print(f"\nWaiting {DELTA} seconds until next check...")
            time.sleep(DELTA)
            
    except KeyboardInterrupt:
        print("\nScript stopped by user")
    except Exception as e:
        print(f"\nUnexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main() 