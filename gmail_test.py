
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone

gmail = os.getenv("GMAIL_ADDRESS")
password = os.getenv("GMAIL_APP_PASSWORD")
receiver = os.getenv("SIGNAL_RECEIVER_EMAIL")

print("Checking Gmail secrets...")

if not all([gmail, password, receiver]):
    raise ValueError("Gmail secrets missing!")

email = EmailMessage()
email["Subject"] = "Binance Bot Gmail Test"
email["From"] = gmail
email["To"] = receiver
email.set_content(
    "SUCCESS! Gmail is connected.\n"
    + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
)

with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
    server.login(gmail, password)
    server.send_message(email)

print("SUCCESS: Test email sent!")
