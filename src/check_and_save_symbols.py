import os
import csv
import MetaTrader5 as mt5
from dotenv import load_dotenv

load_dotenv(override=True)

def fetch_mt5_symbols_to_csv(csv_filename="mt5_symbols.csv"):
    """Fetch all available symbols from MetaTrader 5 and save them to a CSV file."""
    
    # Get credentials and path from environment variables
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    mt5_path = os.getenv("MT5_PATH")

    # Initialize MetaTrader 5
    if not mt5.initialize(path=mt5_path, login=int(login), password=password, server=server):
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return

    # Fetch all symbols
    symbols = mt5.symbols_get()
    if symbols is None or len(symbols) == 0:
        print("No symbols found")
        mt5.shutdown()
        return

    # Save symbols to CSV
    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Symbol", "Description", "Path"])
        
        for symbol in symbols:
            writer.writerow([symbol.name, symbol.description, symbol.path])

    print(f"Saved {len(symbols)} symbols to {csv_filename}")

    # Shutdown MT5 connection
    mt5.shutdown()

if __name__ == "__main__":
    fetch_mt5_symbols_to_csv()
