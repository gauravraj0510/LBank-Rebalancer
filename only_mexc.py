import time
import logging
import getpass
import requests
import hmac
import hashlib
import math
from urllib.parse import urlencode, quote
from typing import Dict, List, Tuple
import threading

DELTA = 120  # Time between rebalancing checks in seconds
VOLUME_TIME = 10  # Time between order manager executions in seconds
TARGET_USDT = 1900  # Target USDT balance to maintain
MNTL_QUANTITY = 44000 # MNTL quantity to buy/sell
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
        """Get current price for a symbol (signed request for assetment zone compatibility)"""
        return self.private_request('GET', '/api/v3/ticker/price', {'symbol': symbol}).json()

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

MNTL_WARNING_BALANCE = 100000  # Warning threshold for MNTL balance

# Telegram configuration
TELEGRAM_BOT_TOKEN = "<YOUR_TELEGRAM_BOT_TOKEN>"  # Replace with your bot token
TELEGRAM_CHAT_ID = "<YOUR_TELEGRAM_CHAT_ID>"      # Replace with your chat ID

def send_telegram_message(message: str):
    """
    Send a message to a Telegram channel using a bot.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            logging.error(f"Failed to send Telegram message: {response.text}")
    except Exception as e:
        logging.error(f"Exception while sending Telegram message: {e}")

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
            logging.info(f"Account info response: {account_info}")  # Log the full response
            balances = {}
            if 'balances' not in account_info:
                logging.error(f"'balances' key not found in account info: {account_info}")
                return {}
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
            price = float(ticker.get('price', 0.0))
            logging.info(f"Fetched price for {self.symbol}: {price}")
            if price == 0.0:
                logging.error(f"Fetched price is zero for {self.symbol}, skipping this cycle.")
            return price
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
        
        # Handle zero price error
        if mntl_price == 0.0:
            logging.error(f"Cannot calculate rebalance trade: MNTL price is zero.")
            return None
        
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

    def check_mntl_warning_balance(self, current_balances: Dict[str, float]):
        """
        Check if MNTL balance is below warning threshold and send Telegram alert if needed.
        """
        mntl_balance = current_balances.get('MNTL', 0.0)
        if mntl_balance < MNTL_WARNING_BALANCE:
            message = (f"⚠️ MNTL balance is low: {mntl_balance} MNTL (below warning threshold of {MNTL_WARNING_BALANCE})")
            logging.warning(message)
            send_telegram_message(message)

    def rebalance(self):
        """Main rebalancing function"""
        try:
            current_balances = self.get_current_balances()
            # Check MNTL warning balance before rebalancing
            self.check_mntl_warning_balance(current_balances)
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

class OrderManager:
    def __init__(self, client: MEXCClient, symbol: str):
        self.client = client
        self.symbol = symbol
        self.saved_orders = []  # List of orderIds

    def manage_orders(self):
        """
        Cancel all orders in saved_orders one by one and remove them from the list after cancellation.
        If saved_orders is empty, do nothing.
        """
        if not self.saved_orders:
            logging.info("No saved orders to cancel.")
            return
        for order_id in self.saved_orders[:]:  # Copy to avoid modification during iteration
            try:
                params = {
                    'symbol': self.symbol,
                    'orderId': order_id
                }
                response = self.client.private_request('DELETE', '/api/v3/order', params)
                logging.info(f"Cancelled order {order_id}: {response.text}")
                self.saved_orders.remove(order_id)
            except Exception as e:
                logging.error(f"Error cancelling order {order_id}: {e}")

    def get_midpoint_price(self):
        """
        Fetch the order book and calculate the midpoint price from the topmost buy and sell orders.
        Uses private_request for assetment zone compatibility.
        """
        params = {
            'symbol': self.symbol,
            'limit': 5
        }
        response = self.client.private_request('GET', '/api/v3/depth', params)
        try:
            data = response.json()
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            if not bids or not asks:
                logging.error("Orderbook missing bids or asks.")
                return None
            top_bid = float(bids[0][0])
            top_ask = float(asks[0][0])
            midpoint = (top_bid + top_ask) / 2
            logging.info(f"Top bid: {top_bid}, Top ask: {top_ask}, Midpoint: {midpoint}")
            return midpoint
        except Exception as e:
            logging.error(f"Error parsing orderbook: {e}\nRaw response: {response.text}")
            return None

    def place_buy_and_sell(self, quantity=MNTL_QUANTITY):
        """
        Place a BUY and a SELL limit order at the midpoint price, store their orderIds in saved_orders.
        """
        price = self.get_midpoint_price()
        if price is None:
            logging.error("Cannot place orders: midpoint price not available.")
            return
        # Place BUY order
        buy_params = {
            'symbol': self.symbol,
            'side': 'BUY',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'price': f'{price:.8f}',
            'quantity': str(quantity)
        }
        buy_response = self.client.private_request('POST', '/api/v3/order', buy_params)
        try:
            buy_result = buy_response.json()
            buy_order_id = buy_result.get('orderId')
            if buy_order_id:
                self.saved_orders.append(buy_order_id)
                logging.info(f"Placed BUY order, orderId: {buy_order_id}")
            else:
                logging.error(f"BUY order response missing orderId: {buy_result}")
        except Exception as e:
            logging.error(f"Error parsing BUY order response: {e}\nRaw response: {buy_response.text}")
        # Place SELL order
        sell_params = {
            'symbol': self.symbol,
            'side': 'SELL',
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'price': f'{price:.8f}',
            'quantity': str(quantity)
        }
        sell_response = self.client.private_request('POST', '/api/v3/order', sell_params)
        try:
            sell_result = sell_response.json()
            sell_order_id = sell_result.get('orderId')
            if sell_order_id:
                self.saved_orders.append(sell_order_id)
                logging.info(f"Placed SELL order, orderId: {sell_order_id}")
            else:
                logging.error(f"SELL order response missing orderId: {sell_result}")
        except Exception as e:
            logging.error(f"Error parsing SELL order response: {e}\nRaw response: {sell_response.text}")

def main():
    print("=== MEXC MNTL-USDT Rebalancer ===")
    print(f"Target USDT Balance: {TARGET_USDT}")
    print(f"Rebalancing Threshold: {THRESHOLD*100}%")
    print(f"Trading Pair: {TRADING_PAIR}")
    print(f"Check Interval: {DELTA} seconds")
    print(f"Order Manager Interval: {VOLUME_TIME} seconds")

    # Get API credentials
    api_key, secret_key = get_api_credentials()

    # Initialize rebalancer and order manager
    rebalancer = BalanceRebalancer(TARGET_USDT, api_key, secret_key)
    client = MEXCClient(api_key, secret_key)
    order_manager = OrderManager(client, TRADING_PAIR)

    print("\nStarting rebalancing and order management process...")
    print("Press Ctrl+C to stop at any time")

    last_rebalance = 0
    last_volume = 0

    while True:
        now = time.time()
        try:
            # Run rebalance every DELTA seconds
            if now - last_rebalance >= DELTA:
                rebalancer.rebalance()
                last_rebalance = now
            # Run order manager every VOLUME_TIME seconds
            if now - last_volume >= VOLUME_TIME:
                order_manager.manage_orders()
                order_manager.place_buy_and_sell()
                last_volume = now
            time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Rebalancing and order management stopped by user")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(5)  # Wait a bit before retrying

if __name__ == "__main__":
    main() 