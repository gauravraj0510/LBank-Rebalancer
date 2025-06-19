import time
import logging
import getpass
import requests
import hmac
import hashlib
import math
from urllib.parse import urlencode, quote
from typing import Dict, List, Tuple

DELTA = 120  # Time between rebalancing checks in seconds
TARGET_USDT = 40  # Target USDT balance to maintain
TRADING_PAIR = "MNTLUSDT"  # Trading pair
THRESHOLD = 0.05  # 5% deviation threshold for rebalancing
MEXC_HOST = "https://api.mexc.com"

# Trading rules for MNTL-USDT
QUANTITY_PRECISION = 0  # MNTL quantity should be rounded to whole numbers
PRICE_PRECISION = 8    # Price precision for MNTL-USDT
MIN_QUANTITY = 1       # Minimum quantity for MNTL-USDT

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
        }
        
        if side == 'BUY' and type == 'MARKET':
            # For market buy, use quoteOrderQty (USDT amount)
            # Round USDT amount to 2 decimal places
            params['quoteOrderQty'] = round(quantity, 2)
        else:
            # For market sell, use quantity (MNTL amount)
            # Round MNTL quantity to whole numbers
            params['quantity'] = math.floor(quantity)  # Round down to ensure we don't exceed available balance
            
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
            Tuple of (symbol, amount, side) where amount is:
            - For BUY: USDT amount to spend
            - For SELL: MNTL amount to sell
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
            # For market buy, we specify the USDT amount to spend
            usdt_amount = round(usdt_deviation, 2)  # Round USDT amount to 2 decimal places
            logging.info(f"USDT above target, will BUY MNTL worth {usdt_amount:.2f} USDT")
            return (self.symbol, usdt_amount, 'BUY')
        else:
            # Too little USDT, need to sell MNTL
            # For market sell, we specify the MNTL amount to sell
            mntl_amount = abs(usdt_deviation) / mntl_price
            # Round down to whole number for MNTL quantity
            mntl_amount = math.floor(mntl_amount)
            
            # Check if we have enough MNTL
            if mntl_amount > current_mntl:
                mntl_amount = math.floor(current_mntl)  # Round down available MNTL
                logging.info(f"Not enough MNTL, will sell all available: {mntl_amount} MNTL")
            else:
                logging.info(f"USDT below target, will SELL {mntl_amount} MNTL worth {abs(usdt_deviation):.2f} USDT")
            
            # Ensure minimum quantity
            if mntl_amount < MIN_QUANTITY:
                logging.info(f"Calculated quantity {mntl_amount} is below minimum {MIN_QUANTITY}, skipping trade")
                return None
                
            return (self.symbol, mntl_amount, 'SELL')

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

def main(api_key=None, secret_key=None):
    print("=== MEXC MNTL-USDT Rebalancer ===")
    print(f"Target USDT Balance: {TARGET_USDT}")
    print(f"Rebalancing Threshold: {THRESHOLD*100}%")
    print(f"Trading Pair: {TRADING_PAIR}")
    print(f"Check Interval: {DELTA} seconds")
    
    # Get API credentials
    if api_key is None or secret_key is None:
        api_key, secret_key = get_api_credentials()
    
    # Initialize rebalancer
    rebalancer = BalanceRebalancer(TARGET_USDT, api_key, secret_key)
    
    print("\nRunning one rebalancing cycle...")
    try:
        rebalancer.rebalance()
    except KeyboardInterrupt:
        logging.info("Rebalancing stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main() 