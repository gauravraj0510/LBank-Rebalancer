# MEXC Rebalancing Script Guidelines

## Overview
This script automatically maintains a target USDT balance by trading MNTL tokens on the MEXC exchange. It continuously monitors your balance and executes trades when the USDT balance deviates from the target by more than the specified threshold.

## Prerequisites
- Python 3.6 or higher
- MEXC API credentials with trading permissions
- Sufficient MNTL and USDT balances in your MEXC account

## Configuration
The script has several configurable parameters at the top of the file:

```python
DELTA = 120  # Time between rebalancing checks in seconds
TARGET_USDT = 40  # Target USDT balance to maintain
TRADING_PAIR = "MNTLUSDT"  # Trading pair
THRESHOLD = 0.05  # 5% deviation threshold for rebalancing
```

- `DELTA`: How often the script checks balances (in seconds)
- `TARGET_USDT`: The desired USDT balance to maintain
- `TRADING_PAIR`: The trading pair to use (currently set to MNTLUSDT)
- `THRESHOLD`: Maximum allowed deviation from target (5% by default)

## Trading Rules
The script follows these trading rules for MNTL-USDT:

- MNTL quantities must be whole numbers (no decimals)
- USDT amounts are rounded to 2 decimal places
- Minimum trade quantity: 1 MNTL
- Market orders are used for both buying and selling

## How It Works

### Balance Monitoring
1. The script checks your MNTL and USDT balances every `DELTA` seconds
2. It calculates the deviation from your target USDT balance
3. If the deviation exceeds the threshold, it calculates the required trade

### Trading Logic
- When USDT balance is too high:
  - Executes a market buy order using the excess USDT
  - Uses `quoteOrderQty` to specify the USDT amount to spend

- When USDT balance is too low:
  - Calculates how much MNTL to sell to reach the target
  - Executes a market sell order using the calculated MNTL amount
  - Uses `quantity` to specify the MNTL amount to sell

### Safety Features
- Rounds down quantities to prevent exceeding available balances
- Checks for minimum trade quantities
- Includes comprehensive error handling and logging
- Logs all trades and balance changes

## Running the Script

1. Ensure you have the required Python packages:
   ```bash
   pip install requests
   ```

2. Run the script:
   ```bash
   python mexc_rebalance.py
   ```

3. When prompted, enter your MEXC API credentials:
   - API Key
   - Secret Key

4. The script will start monitoring and rebalancing automatically

## Logging
The script creates a log file `mexc-rebalance.log` with detailed information about:
- Current balances
- Calculated trades
- Executed orders
- Any errors or issues

## Important Notes

### API Credentials
- Keep your API credentials secure
- Only grant trading permissions to the API key
- Never share your API credentials

### Trading Risks
- Market orders may execute at different prices than expected
- High volatility can affect the accuracy of rebalancing
- Consider the trading fees in your calculations

### Best Practices
1. Start with a small `TARGET_USDT` amount for testing
2. Monitor the script's behavior initially
3. Adjust the `THRESHOLD` based on your risk tolerance
4. Consider market conditions when setting parameters

## Error Handling
The script handles various error conditions:
- API connection issues
- Invalid quantities
- Insufficient balances
- Rate limiting

If an error occurs, the script will:
1. Log the error
2. Wait for 60 seconds
3. Continue monitoring

## Stopping the Script
- Press Ctrl+C to stop the script gracefully
- The script will complete any pending operations before stopping

## Support
For issues or questions:
1. Check the log file for detailed error messages
2. Verify your API credentials and permissions
3. Ensure you have sufficient balances
4. Check MEXC's API status and trading rules 