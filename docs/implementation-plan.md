# CoinPilot to QuanTrade AI Agent Implementation Plan

## Scope Decision

The deployed production app is currently the Streamlit-based `coinpilot_ai`
application at `/Users/quanbaoho/Desktop/coinpilot_ai`.

The master QuanTrade brief recommends a React/FastAPI/PostgreSQL/Redis
monorepo. For this deployed app, the first milestone keeps the current
Streamlit/FastAPI/SQLite structure so the existing Streamlit Cloud deployment,
GitHub Actions alerts, Telegram notifications, OpenAI configuration, and public
market-data scanner continue to work.

This is a deliberate migration path, not a rejection of the target architecture.
The app will be upgraded one milestone at a time while preserving deployment.

## Non-Negotiable Safety Boundary

- No live order execution.
- No exchange account connection.
- No leverage or margin.
- No hidden endpoint that can buy or sell.
- AI explains structured evidence only.
- Deterministic code calculates prices, indicators, scores, risk, stops,
  targets, and paper position sizes.

## Current Architecture

- `app.py`: Streamlit dashboard.
- `backend/main.py`: FastAPI wrapper around local services.
- `src/market_data.py`: public market-data ingestion from KuCoin, Binance, and
  CoinGecko fallback.
- `src/indicators.py`: MA20, MA50, RSI, volume, support, resistance.
- `src/strategy.py`: deterministic rule-based safety and setup logic.
- `src/ai_agent.py`: AI/fallback explanation layer.
- `src/journal.py`: SQLite trade journal.
- `scripts/auto_scan_alerts.py`: scheduled scanner and Telegram/email alerts.

## Milestone Checklist

- [x] Milestone 0: Inspect deployed app and document migration plan.
- [x] Milestone 1: Add deterministic agent-enrichment fields.
- [x] Milestone 2: Improve UI explainability with Agent Evidence tab.
- [x] Milestone 3: Improve alert messages with opportunity/risk context.
- [ ] Milestone 4: Add fixture/demo mode with persistent DEMO DATA label.
- [x] Milestone 5: Add paper-trade lifecycle tracking.
- [ ] Milestone 6: Add data-health dashboard and provider status.
- [ ] Milestone 7: Add more formal tests and CI checks.
- [ ] Milestone 8: Plan migration to React/FastAPI/PostgreSQL if still desired.

## Implemented in This Upgrade

- Opportunity score.
- Risk score.
- Manipulation-risk score.
- Behavioral state classification.
- Counter-thesis.
- Exit-warning text.
- Signal component breakdown.
- Manual action checklist.
- Journal columns for agent evidence.
- AI prompt restrictions that prevent invented numeric values.
- Alert messages with opportunity/risk context.

## Remaining Gaps Against Master Prompt

- No Level 2 order-book maintenance yet.
- No real-time trade stream storage yet.
- No PostgreSQL/TimescaleDB migration yet.
- No Redis pub/sub yet.
- No full fixture replay mode yet.
- No paper-trade position lifecycle yet.
- Limited automated tests in the deployed app.

## Acceptance Criteria for This Milestone

- Existing Streamlit app still starts.
- Existing scanner still returns `Buy Setup`, `Watch for Entry`, `Hold`, or
  `Sell / Avoid`.
- Every result includes deterministic opportunity/risk/manipulation scores.
- Every result includes counter-thesis and action checklist.
- AI explanations consume structured result objects and do not invent prices.
- No live trading code is added.


## Paper Trading Upgrade

Implemented:

- Save a valid `Trade` decision as a paper position.
- Track entry price, latest price, quantity, stop, target, invalidation, and PnL.
- Refresh open paper positions from public market data.
- Automatically mark paper positions as Target Hit, Stopped, or Invalidated.
- Allow manual paper close with a reason.

Safety:

- This is simulated tracking only.
- No exchange connection exists.
- No orders are submitted.
