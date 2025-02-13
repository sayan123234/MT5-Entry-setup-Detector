# FVG Detector

A Python-based Fair Value Gap (FVG) detection system for MetaTrader 5. This project automatically scans multiple currency pairs across different timeframes to identify and alert about FVG formations.

## Features

- Hierarchical timeframe analysis (Monthly → Weekly → Daily → H4)
- Automated FVG detection with swing point validation
- Support for multiple currency pairs, metals, and crypto
- Real-time Telegram alerts
- Configurable settings via YAML
- Comprehensive logging system

## Project Structure

```
fvg_detector/
├── config/
│   └── config.yaml     # Configuration settings
├── src/
│   ├── __init__.py
│   ├── main.py         # Entry point
│   ├── config_handler.py
│   ├── market_analyzer.py
│   ├── fvg_finder.py
│   └── utils.py
├── logs/               # Log files directory
├── .env               # Environment variables
└── requirements.txt   # Dependencies
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
MT5_ACCOUNT=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=your_server
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

4. Configure your settings in `config/config.yaml`

## Configuration

### Supported Symbols

The system supports the following symbols by default:

- Major Pairs: EURUSDm, USDJPYm, GBPUSDm, USDCHFm, USDCADm, AUDUSDm, NZDUSDm
- Crosses: EURGBPm, EURJPYm, EURCHFm, EURAUDm, EURCADm, GBPJPYm, GBPCHFm, GBPAUDm, GBPCADm
- Metals: XAUUSDm, XAGUSDm
- Crypto: BTCUSDm, ETHUSDm

### Timeframe Settings

You can configure lookback periods for each timeframe in `config.yaml`:

```yaml
timeframes:
  monthly:
    value: 16408  # MT5.TIMEFRAME_MN1
    max_lookback: 12
  weekly:
    value: 16386  # MT5.TIMEFRAME_W1
    max_lookback: 24
  daily:
    value: 16385  # MT5.TIMEFRAME_D1
    max_lookback: 50
  h4:
    value: 16388  # MT5.TIMEFRAME_H4
    max_lookback: 100
```

### FVG Settings

Customize FVG detection parameters:

```yaml
fvg_settings:
  min_size: 0.0001    # Minimum FVG size
  swing_window: 5     # Candles to check for swing points
```

## Usage

Run the FVG detector:

```bash
python src/main.py
```

The system will:
1. Connect to your MT5 terminal
2. Start scanning configured symbols
3. Check for FVGs in order of timeframes (Monthly → Weekly → Daily → H4)
4. Send alerts when FVGs are found
5. Log all activities

## Alerts

When an FVG is detected, you'll receive a Telegram alert with:
- Symbol name
- Timeframe
- FVG type (bullish/bearish)
- Price range
- Size of the gap
- Timestamp

## Logging

Logs are stored in the `logs/` directory with the filename format `fvg_detector_YYYYMMDD.log`. Each log entry includes:
- Timestamp
- Log level
- Detailed message about the operation or error

## Error Handling

The system includes comprehensive error handling for:
- MT5 connection issues
- Data retrieval problems
- Configuration errors
- Alert sending failures

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.


## Disclaimer

This software is for educational purposes only. Trading involves risk of loss. Make sure to understand the risks before using this system for live trading.