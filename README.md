# CoinPilot AI

CoinPilot AI is an MVP crypto trading assistant for safe decision support. It does not connect to an exchange, does not use leverage, and does not place real buy or sell orders.

## What It Does

- Accepts account size and max risk per trade.
- Lets the user choose BTC, ETH, SOL, or another CoinGecko coin id.
- Fetches public market data from CoinGecko.
- Calculates 20-period moving average, 50-period moving average, RSI, volume change, and simple support/resistance.
- Produces a structured `Trade` or `No Trade` analysis.
- Enforces hard safety rules before showing any trade plan.
- Uses OpenAI only to explain the analysis in plain English when an API key is available.
- Saves every analysis to a local SQLite journal.

## Setup

```bash
cd ~/Desktop/coinpilot_ai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and add `OPENAI_API_KEY` if you want AI explanations. The app still works without it.

## Run the FastAPI Backend

```bash
uvicorn backend.main:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

## Run the Streamlit Dashboard

Open a second terminal:

```bash
cd ~/Desktop/coinpilot_ai
source venv/bin/activate
streamlit run app.py
```

## Safety Notes

CoinPilot AI is not financial advice. It is a paper-analysis tool only. There is no exchange login, no order routing, no leverage, and no automatic trading.

## Scheduled Notifications

CoinPilot can scan automatically and notify you when a buy candidate or exit/avoid risk appears.
The scanner is decision-support only. It does not auto-buy, auto-sell, connect to an exchange, or use leverage.

### Local Test

```bash
cd ~/Desktop/coinpilot_ai
source venv/bin/activate
python scripts/auto_scan_alerts.py --once
```

### GitHub Actions Setup

The workflow `.github/workflows/coinpilot-alerts.yml` runs every 30 minutes.

Add these GitHub repository secrets for Telegram alerts:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Optional email secrets:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
ALERT_EMAIL_TO
ALERT_EMAIL_FROM
```

Optional repository variables:

```text
COINPILOT_ACCOUNT_SIZE=1000
COINPILOT_RISK_PERCENT=1
COINPILOT_UNIVERSE_LIMIT=100
COINPILOT_DEEP_SCAN_LIMIT=20
COINPILOT_RANK_START=1
COINPILOT_MIN_VOLUME_USD=300000
COINPILOT_SEND_EMPTY=false
```\n

## Alert Quality Controls

CoinPilot scheduled alerts use cooldown filtering so Telegram does not repeat
the same signal every 30 minutes.

Optional GitHub repository variables:

```text
COINPILOT_ALERT_COOLDOWN_HOURS=6
COINPILOT_MIN_BUY_CONFIDENCE=55
COINPILOT_MIN_EXIT_CONFIDENCE=65
COINPILOT_ALERT_WATCH=false
COINPILOT_SEND_EMPTY=false
```

Set `COINPILOT_SEND_EMPTY=true` only when testing delivery. Set it back to
`false` for normal use.\n

## Paper Trade Tracking

CoinPilot can save a valid `Trade` decision as a simulated paper position.
Use the Paper Trades page to refresh positions, review stop/target progress,
and close positions manually. This is learning and journaling only; no real
orders are placed.
