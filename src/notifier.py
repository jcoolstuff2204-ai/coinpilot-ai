"""Notification helpers for CoinPilot alerts.

CoinPilot sends decision-support alerts only. It never places trades.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

import requests
from dotenv import load_dotenv

from src.config import PROJECT_ROOT


load_dotenv(PROJECT_ROOT / ".env")


def send_notification(subject: str, body: str) -> list[str]:
    channels: list[str] = []

    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        send_telegram(body)
        channels.append("telegram")

    if all(os.getenv(key) for key in ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "ALERT_EMAIL_TO"]):
        send_email(subject, body)
        channels.append("email")

    if not channels:
        print(f"\n{subject}\n{body}")
        channels.append("console")

    return channels


def send_telegram(message: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message[:3900]},
        timeout=20,
    )
    response.raise_for_status()


def send_email(subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.getenv("ALERT_EMAIL_FROM", os.environ["SMTP_USERNAME"])
    message["To"] = os.environ["ALERT_EMAIL_TO"]
    message.set_content(body)

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), timeout=25) as server:
        server.starttls()
        server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        server.send_message(message)
