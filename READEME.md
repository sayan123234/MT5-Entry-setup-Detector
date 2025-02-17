# FVG Detector

A Python-based Fair Value Gap (FVG) detection system for MetaTrader 5. This project automatically scans multiple currency pairs across different timeframes to identify and alert about FVG formations.

## Features

- Hierarchical timeframe analysis (Monthly → Weekly → Daily → H4)
- Detection of both confirmed and potential FVGs
- Smart candle closure detection based on broker time
- Dynamic symbol suffix handling for different brokers
- 24-hour alert deduplication system
- Support for multiple currency pairs, metals, and crypto
- Real-time Telegram alerts with detailed status
- Configurable settings via YAML
- Comprehensive logging system
- Automatic cache cleanup on program exit

## Project Structure

```
fvg_detector/
├── config/
│   └── config.yaml        # Configuration settings
├── src/
│   ├── __init__.py
│   ├── main.py           # Entry point
│   ├── config_handler.py  # Configuration management
│   ├── market_analyzer.py # Market analysis logic
│   ├── fvg_finder.py     # FVG detection logic
│   ├── timeframe_utils.py # Timeframe handling
│   ├── alert_cache_handler.py # Alert deduplication
│   └── utils.py          # Utility functions
├── logs/                 # Log files directory
├── cache/               # Alert cache directory
├── .env                # Environment variables
└── requirements.txt    # Dependencies
```

## Prerequisites

- Python 3.8 or higher
- MetaTrader 5 terminal installed
- Active MT5 account
- Telegram bot for alerts (optional)

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd fvg_detector
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your credentials:
```
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=your_server
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

4. Configure your settings in `config/config.yaml`

## Configuration

### Symbol Configuration

The system supports dynamic symbol suffixes for different brokers and various symbol categories:

```yaml
# Broker-specific symbol suffix
# Examples:
# - For suffix 'm': "EURUSDm" (e.g., "symbol_suffix: m")
# - For suffix '.r': "EURUSD.r" (e.g., "symbol_suffix: .r")
# - For no suffix: EURUSD (leave empty)
symbol_suffix: "m"

symbols:
  major_pairs:
    - "EURUSD"    # Will become EURUSDm with suffix
    - "USDJPY"    # Will become USDJPYm with suffix
    # ... more pairs
  crosses:
    - "EURGBP"
    - "EURJPY"
    # ... more crosses
  metals:
    - "XAUUSD"
    - "XAGUSD"
  crypto:
    - "BTCUSD"
    - "ETHUSD"
```

### Timeframe Settings

Configure lookback periods for each timeframe:

```yaml
timeframes:
  MN1:
    max_lookback: 12
  W1:
    max_lookback: 24
  D1:
    max_lookback: 50
  H4:
    max_lookback: 100
```

### FVG Settings

Configure FVG detection parameters:

```yaml
fvg_settings:
  min_size: 0.0001  # Minimum FVG size
```

## Alert System

The system features two types of alerts:
1. Confirmed FVGs: All candles in the pattern have closed
2. Potential FVGs: Pattern detected but some candles are still forming

Alert features:
- Detailed candle status information
- 24-hour deduplication (no repeat alerts for same pattern)
- Automatic cache cleanup at midnight and program exit
- Separate tracking for potential and confirmed patterns

Sample alert message:
```
🔍 Confirmed FVG Detected on EURUSD
⏱ Timeframe: D1
📊 Type: bullish
💹 Size: 0.00123
🔝 Top: 1.12345
⬇ Bottom: 1.12222
🕒 Time: 2024-02-17 10:00:00
```

## Time Synchronization

The system ensures accurate candle closure detection by:
- Using broker server time instead of local time
- Proper handling of timeframe-specific closures
- Accurate detection of forming vs closed candles

## Cache Management

The system includes automatic cache management:
- 24-hour alert deduplication
- Automatic cleanup at midnight
- Cache removal on program exit (Ctrl+C)
- Separate caching for potential and confirmed alerts

## Error Handling

Enhanced error handling for:
- MT5 connection and data retrieval
- Time synchronization issues
- Alert deduplication and caching
- Configuration validation
- Symbol suffix validation

## Logging

Comprehensive logging system with:
- Daily log rotation
- Detailed timeframe analysis logs
- Alert and cache operation tracking
- Error and warning notifications

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## Disclaimer

This software is for educational purposes only. Trading involves risk of loss. Make sure to understand the risks before using this system for live trading.