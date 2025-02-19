FVG Detector
A Python-based Fair Value Gap (FVG) detection system for MetaTrader 5. This project automatically scans multiple financial instruments across hierarchical timeframes to identify and alert about FVG formations with entry setups.

Features
Multi-Timeframe Analysis (Monthly → Weekly → Daily → H4 → H1 → M15 → M5 → M1)

Smart Pattern Detection:

Confirmed FVGs (closed candles)

Mitigation checks

Swing point identification

Broker-Agnostic Implementation:

Dynamic symbol suffix handling

Server time synchronization

Alert System:

Entry alerts with HTF/LTF confluence

24-hour deduplication

Telegram integration

Efficient Resource Management:

LRU caching for rate data

Automatic cache cleanup

Memory optimization

Robust Configuration:

YAML-based settings

Customizable lookback periods

Multiple asset classes support

Project Structure
Copy
fvg_detector/
├── config/
│   └── config.yaml        # Configuration settings
├── alert_cache_handler.py # Alert deduplication
├── config_handler.py      # Configuration management
├── fvg_finder.py          # Core detection logic
├── main.py                # Entry point
├── market_analyzer.py     # Analysis orchestration
├── requirements.txt       # Dependencies
└── .env                   # Environment variables
Key Improvements from Codebase
Hierarchical Analysis:

python
Copy
# config_handler.py
timeframe_hierarchy = {
    TimeFrame.MONTHLY: [W1, D1, H4, H1, M15, M5, M1],
    TimeFrame.WEEKLY: [D1, H4, H1, M15, M5, M1],
    # ... full hierarchy down to M1
}
Smart Caching:

python
Copy
# alert_cache_handler.py
self.cache_file = f"fvg_alerts_{datetime.now().strftime('%Y%m%d')}.json"
self.manage_cache_size()  # Automatic 100MB limit
Configuration Updates
Expanded Timeframe Settings
yaml
Copy
timeframes:
  MN1:
    max_lookback: 12    # Monthly
  W1:
    max_lookback: 24    # Weekly
  D1:
    max_lookback: 50    # Daily
  H4:
    max_lookback: 100   # 4-Hour
  H1:
    max_lookback: 200   # 1-Hour
  M15:
    max_lookback: 400   # 15-Minute
  M5:
    max_lookback: 600   # 5-Minute
  M1:
    max_lookback: 1000  # 1-Minute
Enhanced Alert Configuration
yaml
Copy
fvg_settings:
  min_size: 0.0001  # Minimum gap size (0.1 pip for FX)

telegram:
  enabled: true      # Enable/disable alerts
Alert Examples
Entry Alert (HTF/LTF Confluence):

Copy
🚨 ENTRY SETUP: EURUSDm
📈 HTF: H4 bullish FVG (Mitigated)
📉 LTF: M15 bullish FVG detected
🔝 LTF Top: 1.12345
⬇ LTF Bottom: 1.12222
🕒 LTF Time: 2024-02-20 14:45:00
Installation Updates
Telegram Requirements:

bash
Copy
# requirements.txt
python-telegram-bot==13.7
Enhanced Environment:

.env
Copy
TELEGRAM_TOKEN=your_bot_token       # Required for alerts
TELEGRAM_CHAT_ID=your_chat_id       # Group/user ID
MT5_LOGIN=your_account_number       # Must be numeric
MT5_SERVER=your_broker_server       # e.g., 'ICMarkets-Demo'
Operational Notes
Analysis Workflow:

Scans from highest to lowest timeframe

Stops at first valid FVG with LTF confirmation

Checks first 3 lower timeframes for confluence

Performance Features:

python
Copy
# fvg_finder.py
@lru_cache(maxsize=100)  # Efficient rate data caching
def get_cached_rates(self, symbol: str, timeframe: TimeFrame):
Risk Management:

Requires confirmed + mitigated FVG

5-minute analysis intervals

Automatic retry on failures

Backtesting Recommendation
python
Copy
# market_analyzer.py
# Uncomment to enable market hours check
# def is_market_open(self, symbol: str) -> bool:
Warning: Always test in demo account first. Historical FVG performance may vary significantly from real-time detection.

