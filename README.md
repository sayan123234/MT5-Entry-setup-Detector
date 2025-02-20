# MMT inspired Trading Entry Setup Detector

A Python-based entry alert system for MetaTrader 5 based on Arjoio's trading concepts. This project automatically scans multiple financial instruments across hierarchical timeframes to identify and alert about FVG formations with entry setups.

## Key Updates from Code Analysis

### Refined Timeframe Analysis
- Actually limited to H1 and above timeframes in production
- Hierarchy: MONTHLY → WEEKLY → DAILY → H4 → H1
- Lower timeframes (M15, M5, M1) are filtered out in `market_analyzer.py`

### Enhanced Pattern Detection
- Reentry FVG detection for additional trading opportunities
- Comprehensive candle closure validation
- Detailed mitigation tracking
- Three-candle pattern confirmation

### Time Synchronization
- New `TimeSync` class for broker time synchronization
- Automatic time offset calculation
- Fallback to direct server time queries

### Advanced Alert System
- Three types of alerts:
  - Standard entry alerts
  - Reentry setup alerts
  - "Watch out" alerts for potential setups
- Minute-precision deduplication
- Rate-limited Telegram messaging

### Resource Management
- Daily cache file rotation
- 100MB cache size limit with automatic cleanup
- Garbage collection after analysis cycles
- LRU caching for rate data

### Error Handling
- Retry mechanism for MT5 initialization (3 attempts, 30-second delay)
- Graceful shutdown handling
- Cross-platform timeout handling for operations

## Project Structure Updates

```
fvg_detector/
├── config/
│   └── config.yaml        # Configuration settings
├── alert_cache_handler.py # Alert deduplication
├── config_handler.py      # Configuration management
├── fvg_finder.py         # Core detection logic
├── main.py               # Entry point
├── market_analyzer.py    # Analysis orchestration
├── time_sync.py         # Broker time synchronization
├── timeframe_utils.py    # Timeframe calculations
├── utils.py             # Helper functions
├── requirements.txt      # Dependencies
└── .env                 # Environment variables
```

## Configuration Requirements

### Environment Variables
```ini
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_account_password
MT5_SERVER=your_broker_server
MT5_PATH=path_to_mt5_terminal
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Updated Alert Examples

#### ST Entry Alert
```
🚨 ST Setup: {symbol}
📈 HTF: {timeframe} {type} FVG (Mitigated)
📉 LTF: {ltf} {type} FVG detected
🔝 LTF Top: {top}
⬇ LTF Bottom: {bottom}
🕒 LTF Time: {time}
```

#### ST+RE Setup Alert
```
🎯 ST+RE Setup: {symbol}
📈 HTF: {timeframe} {type} FVG (Mitigated)
📊 LTF: {ltf} Reentry FVG
🔝 Top: {top}
⬇ Bottom: {bottom}
🕒 Time: {time}
📍 Original FVG Time: {original_time}
```

#### Watch Alert
```
⏳ Watch out for potential entry setups!: {symbol}
📊 {timeframe} {type} FVG was mitigated
🔍 No matching LTF FVGs found in: {timeframes}
```

## Operational Features

### Performance Optimizations
- Cached rate data with automatic invalidation
- Smart timeframe filtering
- Memory-efficient analysis cycles

### Risk Management
- Confirmed candle validation
- Mitigation checks before alerts
- Rate limiting for alerts
- Duplicate prevention

### Error Recovery
- Automatic MT5 reconnection
- Cache cleanup on shutdown
- Graceful error handling

## Installation Requirements

```
MetaTrader5==5.0.45
pandas
pyyaml
python-dotenv
requests
```

⚠️ **Important Notes:**
- System now focuses on H1 and higher timeframes for more reliable signals
- Reentry detection provides additional trading opportunities
- Time synchronization is critical for accurate candle closure detection
- Alert deduplication uses minute-precision timestamps
- Cache management is automated with size limits

The system is designed for production use but should always be tested in a demo environment first.