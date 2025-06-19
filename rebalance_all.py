import time
import getpass
import lbank_rebalance
import mexc_rebalance

CYCLE_SECONDS = 120  # 2 minutes

def prompt_credentials(exchange_name):
    print(f"\n=== {exchange_name} API Credentials Setup ===")
    api_key = input("API Key: ").strip()
    while not api_key:
        print("API Key cannot be empty!")
        api_key = input("API Key: ").strip()
    secret_key = getpass.getpass("Secret Key: ").strip()
    while not secret_key:
        print("Secret Key cannot be empty!")
        secret_key = getpass.getpass("Secret Key: ").strip()
    return api_key, secret_key

if __name__ == "__main__":
    print("Combined LBANK + MEXC Rebalancer")
    lbank_api_key, lbank_secret_key = prompt_credentials("LBANK")
    mexc_api_key, mexc_secret_key = prompt_credentials("MEXC")

    print(f"\nStarting combined rebalancing every {CYCLE_SECONDS} seconds. Press Ctrl+C to stop.")
    while True:
        print("\n=== Running LBANK rebalance ===")
        lbank_rebalance.main(lbank_api_key, lbank_secret_key)
        print("\n=== Running MEXC rebalance ===")
        mexc_rebalance.main(mexc_api_key, mexc_secret_key)
        print(f"\nWaiting {CYCLE_SECONDS} seconds before next cycle...\n")
        time.sleep(CYCLE_SECONDS) 