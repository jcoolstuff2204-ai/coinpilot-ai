# Agent Operating Rules

This deployed app is a financial decision-support assistant. Keep all future
work aligned with these rules:

- Deterministic code calculates all numbers.
- OpenAI may explain structured evidence, but must not invent market data.
- No live trading, order submission, leverage, or exchange account connection.
- Risk gates override opportunity scores.
- Missing or stale data must be shown clearly.
- Prefer conservative signals and explicit uncertainty.
