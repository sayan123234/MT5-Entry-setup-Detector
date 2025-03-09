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
│   │   ├── two_candle_rejection.py # 2CR pattern detection
│   │   ├── candle_classifier.py # Candle type classification
│   │   ├── pd_rays.py    # Premium/Discount Arrays handling
│   │   └── trading_strategy.py # Complete trading framework
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

### Candle Classification
- **Disrespect Candles**: Large body with small wicks, indicating strong trend continuation.
- **Respect Candles**: Long wicks with small body, indicating price respecting a key level.
- Pattern detection between consecutive candles for trend analysis.

### PD Rays (Premium/Discount Arrays)
- Identifies critical price levels where markets reverse or accelerate:
  - Fair Value Gaps (FVGs)
  - Swing Highs/Lows
  - Previous Candle Highs/Lows
- Determines market direction based on PD Ray analysis.
- Establishes trading narrative based on price movement relative to PD Rays.

### Complete Trading Strategy Framework
- **Step 1**: Identify PD Rays across multiple timeframes.
- **Step 2**: Determine market direction with confidence scoring.
- **Step 3**: Establish narrative (where price is coming from and where it's going).
- **Step 4**: Two Candle Rejection Strategy for entry timing.
- **Step 5**: Entries and Risk Management with specific stop loss and target levels.

### Risk Management
- Calculates risk-reward ratios for potential trades.
- Implements breakeven rules (move stops to breakeven once a new FVG forms).
- Sets targets based on the next PD Ray in the direction of the trade.
- Provides comprehensive trade plans with entry, stop loss, and target levels.

### Time Synchronization
- The `TimeSync` class handles broker time synchronization.
- Automatically calculates the broker time offset.
- Falls back to direct server time queries when needed.

### Alerting System
- Multiple alert types:
  - **2CR Alerts** (Two Candle Rejection) - Main trading setup alerts
  - **Potential 2CR Alerts** - Watch alerts for possible setups
  - **Directional Bias Alerts** - Strong market bias alerts
  - **Trade Plan Alerts** - Comprehensive trade plans with entry, stop loss, and target
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

### Detailed Analysis Configuration
In `config.yaml`, you can enable detailed analysis for specific symbols:
```yaml
detailed_analysis:
  enabled: true  # Set to false to disable detailed analysis
  symbols:
    - "EURUSD.sml"
    - "GBPUSD.sml"
    - "XAUUSD.sml"
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

### Directional Bias Alert
```
📈 Strong Bullish Bias: {symbol}
📊 Timeframe: {timeframe}
🔍 Confidence: {confidence}%
🎯 Target: {target}
🛑 Stop Loss: {stop_loss}
📝 Analysis: {description}
```

### Trade Plan Alert
```
📈 Trade Plan: {symbol}
📊 Bias: Bullish (75.5%)
⏱️ Entry Timeframe: H4
✅ Entry: Enter now at 1.10500
🎯 Target: 1.11200
🛑 Stop Loss: 1.10200
⚖️ Risk-Reward: 1:2.33
🔒 Breakeven: 1.10733
📝 Breakeven Rule: Move stop to breakeven once a new FVG forms in the direction of the trade
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
- Risk-reward calculation for trade evaluation.

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
The detector implements a comprehensive trading strategy framework:

### Core Concepts
1. **Candle Types**:
   - **Disrespect Candle**: Large body with small wicks, indicating strong trend continuation.
   - **Respect Candle**: Long wicks with small body, indicating price respecting a key level.

2. **PD Rays (Premium/Discount Arrays)**:
   - Critical price levels where markets reverse or accelerate.
   - Includes FVGs, Swing Highs/Lows, and Previous Candle Highs/Lows.

### Step-by-Step Framework
1. **Identify PD Rays**: Mark FVGs, swing points, and previous candle extremes on higher timeframes.
2. **Determine Direction**: Analyze if the next candle is likely to be bullish or bearish based on trend context and respect/disrespect of PD Rays.
3. **Establish Narrative**: Determine where price is coming from and where it's going.
4. **Two Candle Rejection Strategy**: Look for first candle rejection or second candle sweep and rejection at PD Rays.
5. **Entries and Risk Management**: Use lower timeframes to refine entries after higher timeframe confirmation, with clear stop loss and target levels.

### Practical Application
- Multi-timeframe alignment: Higher timeframes guide direction; lower timeframes refine entries.
- Probability over certainty: Focus on high-probability setups.
- Synergy of candle patterns and key levels creates a robust predictive framework.

This approach provides high-quality trading setups with clear entry points and defined risk parameters, offering more trading opportunities while maintaining signal quality.

## Credits
Inspired by Arjoio's trading methodology. Check out his YouTube channel for more insights: [Arjoio's YouTube Channel](https://www.youtube.com/@Arjoio)

⚠️ **Always test in a demo environment before live trading!**
