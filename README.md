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
