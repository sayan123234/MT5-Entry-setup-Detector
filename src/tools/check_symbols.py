import os
import csv
import logging
import argparse
from pathlib import Path
from typing import List, Optional
from src.services.mt5_service import mt5_service

logger = logging.getLogger(__name__)

def setup_logging(log_level: int = logging.INFO) -> None:
    """
    Setup logging configuration.
    
    Args:
        log_level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def save_symbols_to_csv(symbols: List[str], csv_filename: str = "mt5_symbols.csv") -> bool:
    """
    Save symbols to a CSV file.
    
    Args:
        symbols: List of MT5 symbol names
        csv_filename: Output CSV filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        output_path = Path(csv_filename)
        output_path.parent.mkdir(exist_ok=True)
        
        # Get detailed info for each symbol
        symbol_details = []
        for symbol_name in symbols:
            info = mt5_service.get_symbol_info(symbol_name)
            if info:
                symbol_details.append({
                    'name': symbol_name,
                    'description': info.get('description', 'N/A'),
                    'path': info.get('path', 'N/A'),
                    'spread': info.get('spread', 'N/A'),
                    'point': info.get('point', 'N/A'),
                    'digits': info.get('digits', 'N/A')
                })
        
        # Write to CSV
        with open(output_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Symbol", "Description", "Path", "Spread", "Point", "Digits"])
            
            for symbol in symbol_details:
                writer.writerow([
                    symbol['name'], 
                    symbol['description'], 
                    symbol['path'],
                    symbol['spread'],
                    symbol['point'],
                    symbol['digits']
                ])
        
        logger.info(f"Saved {len(symbols)} symbols to {csv_filename}")
        return True
    except Exception as e:
        logger.error(f"Error saving symbols to CSV: {e}")
        return False

def fetch_mt5_symbols_to_csv(csv_filename: str = "mt5_symbols.csv") -> bool:
    """
    Fetch all available symbols from MetaTrader 5 and save them to a CSV file.
    
    Args:
        csv_filename: Output CSV filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize MT5
        success, error_msg = mt5_service.initialize()
        if not success:
            logger.error(error_msg)
            return False
        
        # Fetch symbols
        symbols = mt5_service.get_symbols()
        if not symbols:
            logger.error("Failed to get symbols from MT5")
            mt5_service.shutdown()
            return False
        
        # Save to CSV
        result = save_symbols_to_csv(symbols, csv_filename)
        
        # Shutdown MT5
        mt5_service.shutdown()
        return result
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        mt5_service.shutdown()
        return False

def main():
    """Command-line entry point"""
    parser = argparse.ArgumentParser(description='Fetch and save MT5 symbols to CSV')
    parser.add_argument('--output', '-o', default='mt5_symbols.csv', help='Output CSV filename')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)
    
    # Fetch and save symbols
    success = fetch_mt5_symbols_to_csv(args.output)
    
    if success:
        print(f"Successfully saved MT5 symbols to {args.output}")
    else:
        print("Failed to save MT5 symbols. Check the logs for details.")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
