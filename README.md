# MMT-Inspired Trading Entry Setup Detector

A Python-based entry alert system for MetaTrader 5, inspired by Arjoio's trading concepts. This project automatically scans multiple financial instruments across hierarchical timeframes to identify and alert about FVG formations with entry setups.

## Project Structure

The project has been reorganized into a more modular structure with clear separation of concerns:

```
fvg_detector/
├── config/
│   └── config.yaml        # Configuration settings
├── cache/                 # Cache directory for alerts
├── logs/                  # Log files directory
├── src/
│   ├── core/              # Core business logic
│   │   ├── fvg_finder.py  # FVG detection logic
│   │   ├── market_analyzer.py # Analysis orchestration
│   │   └── two_candle_rejection.py # 2CR pattern detection
│   ├── config/            # Configuration handling
│   │   └── config_handler.py # Configuration management
│   ├── utils/             # Utility functions
│   │   ├── alert_cache.py # Alert deduplication
│   │   ├── helpers.py     # General utility functions
│   │   └── time_sync.py   # Broker time synchronization
│   ├── services/          # External services
│   │   ├── mt5_service.py # MT5 specific operations
│   │   └── telegram_service.py # Telegram notifications
│   ├── tools/             # Standalone tools
│   │   └── check_symbols.py # Symbol verification tool
│   └── main.py            # Entry point
├── requirements.txt       # Dependencies
└── .env                   # Environment variables
```

## Features

### Timeframe Analysis
- Focuses on H1 and higher timeframes for robust signal detection.
- Timeframe hierarchy: **MONTHLY → WEEKLY → DAILY → H4 → H1**.
- Lower timeframes (M15, M5, M1) are filtered out for reliability.

### Advanced Pattern Detection
- Identifies Fair Value Gaps (FVGs) and looks for Two Candle Rejection (2CR) patterns in:
  - The same timeframe as the FVG (primary detection)
  - Lower timeframes (secondary detection)
- Candle closure validation ensures accurate signals.
- Tracks mitigation events to avoid false signals.
- Detects follow-through confirmation for stronger setups.

### Time Synchronization
- The `TimeSync` class handles broker time synchronization.
- Automatically calculates the broker time offset.
- Falls back to direct server time queries when needed.

### Alerting System
- Two alert types:
  - **2CR Alerts** (Two Candle Rejection) - Main trading setup alerts
  - **Potential 2CR Alerts** - Watch alerts for possible setups
- Minute-precision deduplication prevents redundant alerts.
- Telegram messaging with rate-limiting to avoid spam.

### Resource & Performance Management
- Daily cache file rotation with a 100MB size limit.
- Automated garbage collection after each analysis cycle.
- LRU caching for efficient rate data handling.

### Robust Error Handling
- Retry mechanism for MT5 initialization (3 attempts, 30-second delay).
- Graceful shutdown procedures.
- Cross-platform timeout handling.

## Symbol Verification  

Before running the detector, ensure that your broker's symbols match the ones defined in `config.yaml`. Brokers may use different symbol naming conventions, which can cause mismatches.  

To fetch and save all available MT5 symbols, run:  

```sh
python -m src.tools.check_symbols
```

## Configuration

### Environment Variables
Create a `.env` file with the following details:
```ini
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_account_password
MT5_SERVER=your_broker_server
MT5_PATH=path_to_mt5_terminal
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Alert Examples

### Same Timeframe 2CR Alert
```
🔄 SAME TF 2CR Setup: {symbol}
📈 Timeframe: {timeframe}
📊 Pattern: {type} FVG with 2CR ({rejection_type})
🔍 FVG Range: {bottom} - {top}
📏 FVG Size: {size} pips
🕒 First Candle: {first_candle_time}
🕒 Second Candle: {second_candle_time}
📊 Follow-through: ✅ Expected/Confirmed
```

### Lower Timeframe 2CR Alert
```
🔄 2CR Setup: {symbol}
📈 HTF: {htf_timeframe} {type} FVG (Mitigated)
📉 LTF: {ltf_timeframe} 2CR Pattern ({rejection_type})
🔍 FVG Range: {bottom} - {top}
📏 FVG Size: {size} pips
🕒 First Candle: {first_candle_time}
🕒 Second Candle: {second_candle_time}
📊 Follow-through: ✅ Expected/Confirmed
```

### Potential 2CR Alert
```
⏳ Potential 2CR Setup: {symbol}
📈 HTF: {timeframe} {type} FVG (Mitigated)
👀 Watch for 2CR pattern on: {timeframes}
🔍 FVG Range: {bottom} - {top}
📏 FVG Size: {size} pips
```

## Key Operational Features

### Performance Optimizations
- Cached rate data with automatic invalidation.
- Smart timeframe filtering for efficiency.
- Memory-efficient analysis cycles.

### Risk Management
- Candle validation to ensure confirmed setups.
- Mitigation checks before sending alerts.
- Rate-limited alerts to prevent spam.
- Duplicate prevention using timestamp-based deduplication.

### Error Recovery
- Automatic MT5 reconnection for stability.
- Cache cleanup on shutdown to maintain performance.
- Graceful error handling to prevent crashes.

## Installation

### Requirements

Install dependencies using:
```
pip install -r requirements.txt
```

**Dependencies:**
```
MetaTrader5==5.0.45
pandas
pyyaml
python-dotenv
requests
```

## Running the Application

To start the FVG detector:

```sh
python -m src.main
```

## Important Notes
- The system prioritizes H1 and higher timeframes for accuracy.
- 2CR patterns are detected in both the same timeframe as the FVG and lower timeframes, providing more trading opportunities.
- Same timeframe 2CR patterns are prioritized over lower timeframe patterns.
- Time synchronization ensures correct candle closure validation.
- Alerts are deduplicated with minute-level precision.
- Cache management is automated with size limits.

## Trading Strategy
The detector implements a trading strategy based on Fair Value Gaps (FVGs) and Two Candle Rejection (2CR) patterns:

1. **FVG Detection**: Identifies price gaps created when price moves rapidly in one direction.
2. **FVG Mitigation**: Waits for price to return to the FVG area.
3. **2CR Pattern Detection**: After FVG mitigation, looks for a two-candle rejection pattern in:
   - The same timeframe as the FVG (primary detection)
   - Lower timeframes if no pattern is found in the same timeframe (secondary detection)
4. **Entry Signal**: Generates an alert when a complete setup is found.

This dual-timeframe approach provides high-quality trading setups with clear entry points and defined risk parameters, offering more trading opportunities while maintaining signal quality.

## Credits
Inspired by Arjoio's trading methodology. Check out his YouTube channel for more insights: [Arjoio's YouTube Channel](https://www.youtube.com/@Arjoio)

⚠️ **Always test in a demo environment before live trading!**
