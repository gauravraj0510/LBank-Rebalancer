import time
import logging
import getpass
import requests
import hmac
import hashlib
from urllib.parse import urlencode, quote
from typing import Dict, List, Tuple

DELTA = 120  # Time between rebalancing checks in seconds
TARGET_USDT = 1000  # Target USDT balance to maintain
TRADING_PAIR = "MNTLUSDT"  # Trading pair
THRESHOLD = 0.05  # 5% deviation threshold for rebalancing
MEXC_HOST = "https://api.mexc.com"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mexc-rebalance.log'),
        logging.StreamHandler()
    ]
)

class MEXCClient:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.host = MEXC_HOST

    def _get_server_time(self):
        return requests.get(f'{self.host}/api/v3/time').json()['serverTime']

    def _sign_v3(self, req_time, sign_params=None):
        if sign_params:
            sign_params = urlencode(sign_params, quote_via=quote)
            to_sign = "{}&timestamp={}".format(sign_params, req_time)
        else:
            to_sign = "timestamp={}".format(req_time)
        sign = hmac.new(self.secret_key.encode('utf-8'), to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        return sign

    def public_request(self, method: str, endpoint: str, params=None):
        url = f'{self.host}{endpoint}'
        return requests.request(method, url, params=params)

    def private_request(self, method: str, endpoint: str, params=None):
        url = f'{self.host}{endpoint}'
        req_time = self._get_server_time()
        
        if params:
            params['signature'] = self._sign_v3(req_time=req_time, sign_params=params)
        else:
            params = {}
            params['signature'] = self._sign_v3(req_time=req_time)
            
        params['timestamp'] = req_time
        headers = {
            'x-mexc-apikey': self.api_key,
            'Content-Type': 'application/json',
        }
        return requests.request(method, url, params=params, headers=headers)

    def get_account_info(self):
        """Get account information including balances"""
        return self.private_request('GET', '/api/v3/account').json()

    def get_price(self, symbol: str):
        """Get current price for a symbol"""
        return self.public_request('GET', '/api/v3/ticker/price', {'symbol': symbol}).json()

    def place_order(self, symbol: str, side: str, type: str, quantity: float):
        """Place a new order"""
        params = {
            'symbol': symbol,
            'side': side,
            'type': type,
            'quantity': quantity
        }
        return self.private_request('POST', '/api/v3/order', params).json()

def get_api_credentials() -> Tuple[str, str]:
    """
    Prompt user for API credentials securely
    Returns:
        Tuple of (api_key, secret_key)
    """
    print("\n=== MEXC API Credentials Setup ===")
    print("Please enter your MEXC API credentials:")
    
    api_key = input("API Key: ").strip()
    while not api_key:
        print("API Key cannot be empty!")
        api_key = input("API Key: ").strip()
    
    secret_key = getpass.getpass("Secret Key: ").strip()
    while not secret_key:
        print("Secret Key cannot be empty!")
        secret_key = getpass.getpass("Secret Key: ").strip()
    
    return api_key, secret_key

class BalanceRebalancer:
    def __init__(self, target_usdt: float, api_key: str, secret_key: str, threshold: float = THRESHOLD):
        """
        Initialize the rebalancer with target USDT balance
        
        Args:
            target_usdt: Target USDT balance to maintain
            api_key: MEXC API key
            secret_key: MEXC Secret key
            threshold: Maximum allowed deviation from target (default 5%)
        """
        self.target_usdt = target_usdt
        self.threshold = threshold
        self.symbol = TRADING_PAIR
        self.client = MEXCClient(api_key, secret_key)
        
    def get_current_balances(self) -> Dict[str, float]:
        """Get current balances for MNTL and USDT"""
        try:
            account_info = self.client.get_account_info()
            balances = {}
            for asset in account_info['balances']:
                if asset['asset'] in ['MNTL', 'USDT']:
                    balances[asset['asset']] = float(asset['free']) + float(asset['locked'])
            return balances
        except Exception as e:
            logging.error(f"Error getting balances: {e}")
            return {}

    def get_market_price(self) -> float:
        """Get current market price for MNTL-USDT"""
        try:
            ticker = self.client.get_price(self.symbol)
            return float(ticker['price'])
        except Exception as e:
            logging.error(f"Error getting price for {self.symbol}: {e}")
            return 0.0

    def calculate_rebalance_trade(self, current_balances: Dict[str, float]) -> Tuple[str, float, str]:
        """
        Calculate required trade to rebalance USDT balance
        
        Returns:
            Tuple of (symbol, quantity, side) or None if no trade needed
        """
        current_usdt = current_balances.get('USDT', 0.0)
        current_mntl = current_balances.get('MNTL', 0.0)
        mntl_price = self.get_market_price()
        
        # Calculate USDT deviation
        usdt_deviation = current_usdt - self.target_usdt
        deviation_percentage = abs(usdt_deviation) / self.target_usdt
        
        logging.info(f"Current USDT: {current_usdt:.2f}, Target: {self.target_usdt:.2f}, "
                    f"Deviation: {usdt_deviation:.2f} ({deviation_percentage*100:.1f}%)")
        
        # If deviation is within threshold, no trade needed
        if deviation_percentage <= self.threshold:
            logging.info(f"Deviation within threshold ({self.threshold*100}%), no trade needed")
            return None
            
        if usdt_deviation > 0:
            # Too much USDT, need to buy MNTL
            quantity = usdt_deviation / mntl_price
            logging.info(f"USDT above target, will BUY {quantity:.4f} MNTL worth {usdt_deviation:.2f} USDT")
            return (self.symbol, quantity, 'BUY')
        else:
            # Too little USDT, need to sell MNTL
            quantity = abs(usdt_deviation) / mntl_price
            # Check if we have enough MNTL
            if quantity > current_mntl:
                quantity = current_mntl
                logging.info(f"Not enough MNTL, will sell all available: {quantity:.4f} MNTL")
            else:
                logging.info(f"USDT below target, will SELL {quantity:.4f} MNTL worth {abs(usdt_deviation):.2f} USDT")
            return (self.symbol, quantity, 'SELL')

    def execute_trade(self, symbol: str, quantity: float, side: str) -> bool:
        """Execute a single trade"""
        try:
            response = self.client.place_order(symbol, side, 'MARKET', quantity)
            logging.info(f"Trade executed: {response}")
            return True
        except Exception as e:
            logging.error(f"Error executing trade: {e}")
            return False

    def rebalance(self):
        """Main rebalancing function"""
        try:
            current_balances = self.get_current_balances()
            trade = self.calculate_rebalance_trade(current_balances)
            
            if not trade:
                return
            
            symbol, quantity, side = trade
            logging.info(f"Executing {side} trade for {quantity} {symbol}")
            
            success = self.execute_trade(symbol, quantity, side)
            if not success:
                logging.error(f"Failed to execute trade for {symbol}")
                return
                
            logging.info("Rebalancing completed successfully")
            
        except Exception as e:
            logging.error(f"Error during rebalancing: {e}")

def main():
    print("=== MEXC MNTL-USDT Rebalancer ===")
    print(f"Target USDT Balance: {TARGET_USDT}")
    print(f"Rebalancing Threshold: {THRESHOLD*100}%")
    print(f"Trading Pair: {TRADING_PAIR}")
    print(f"Check Interval: {DELTA} seconds")
    
    # Get API credentials
    api_key, secret_key = get_api_credentials()
    
    # Initialize rebalancer
    rebalancer = BalanceRebalancer(TARGET_USDT, api_key, secret_key)
    
    print("\nStarting rebalancing process...")
    print("Press Ctrl+C to stop at any time")
    
    while True:
        try:
            rebalancer.rebalance()
            # Wait for DELTA before next check
            time.sleep(DELTA)
        except KeyboardInterrupt:
            logging.info("Rebalancing stopped by user")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main() 