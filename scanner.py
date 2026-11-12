
import os
import time
import smtplib
import requests
import pandas as pd
import pandas_ta as ta

from email.message import EmailMessage
from datetime import datetime, timezone

BINANCE_URL = "https://fapi.binance.com"
TIMEFRAME = "1h"
CANDLE_LIMIT = 50
SUPERTREND_LENGTH = 10
SUPERTREND_MULTIPLIER = 3
REQUEST_TIMEOUT = 20


def send_email_alert(message, subject="Binance Supertrend Signals"):

    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    receiver_email = os.getenv("SIGNAL_RECEIVER_EMAIL")

    if not all([gmail_address, gmail_password, receiver_email]):
        print("ERROR: Gmail secrets missing!")
        return False

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = gmail_address
    email["To"] = receiver_email
    email.set_content(message)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(gmail_address, gmail_password)
            server.send_message(email)

        print("EMAIL SENT SUCCESSFULLY!")
        return True

    except Exception as e:
        print("EMAIL ERROR:", str(e))
        return False


def get_symbols():

    url = f"{BINANCE_URL}/fapi/v1/exchangeInfo"

    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()

    return [
        item["symbol"]
        for item in data["symbols"]
        if item["quoteAsset"] == "USDT"
        and item["contractType"] == "PERPETUAL"
        and item["status"] == "TRADING"
    ]


def get_klines(symbol):

    url = f"{BINANCE_URL}/fapi/v1/klines"

    params = {
        "symbol": symbol,
        "interval": TIMEFRAME,
        "limit": CANDLE_LIMIT
    }

    response = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    columns = [
        "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ]

    df = pd.DataFrame(response.json(), columns=columns)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def check_signal(symbol):

    try:
        df = get_klines(symbol)

        if len(df) < 30:
            return None

        supertrend = ta.supertrend(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            length=SUPERTREND_LENGTH,
            multiplier=SUPERTREND_MULTIPLIER
        )

        if supertrend is None:
            return None

        direction_columns = [
            col for col in supertrend.columns
            if col.startswith("SUPERTd_")
        ]

        if not direction_columns:
            return None

        direction = pd.to_numeric(
            supertrend[direction_columns[0]],
            errors="coerce"
        )

        recent_24 = direction.iloc[-25:-1]

        if len(recent_24) != 24 or recent_24.isna().any():
            return None

        latest_close = df["close"].iloc[-2]
        previous_low = df["low"].iloc[-3]
        previous_high = df["high"].iloc[-3]

        if (recent_24 == 1).all() and latest_close > previous_high:
            return {
                "symbol": symbol,
                "signal": "LONG",
                "price": latest_close
            }

        if (recent_24 == -1).all() and latest_close < previous_low:
            return {
                "symbol": symbol,
                "signal": "SHORT",
                "price": latest_close
            }

        return None

    except Exception as e:
        print(f"{symbol} ERROR: {e}")
        return None


def main():

    print("=" * 45)
    print("BINANCE SUPERTREND SCANNER STARTED")
    print("Time:", datetime.now(timezone.utc))
    print("=" * 45)

    # Manual GitHub run par email connection test
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":

        test_message = (
            "GMAIL CONNECTION TEST SUCCESSFUL!\n\n"
            "Your Binance Supertrend scanner is connected "
            "to Gmail successfully.\n\n"
            "Time: "
            + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        )

        test_sent = send_email_alert(
            test_message,
            "TEST EMAIL - Binance Scanner"
        )

        if not test_sent:
            print("WARNING: Test email could not be sent.")

    try:
        symbols = get_symbols()
    except Exception as e:
        print("BINANCE SYMBOL ERROR:", e)
        return

    print("Total USDT perpetual symbols:", len(symbols))

    signals = []

    for index, symbol in enumerate(symbols, start=1):

        print(f"Scanning {index}/{len(symbols)}: {symbol}")

        result = check_signal(symbol)

        if result:
            signals.append(result)
            print("SIGNAL FOUND:", result)

        time.sleep(0.05)

    if signals:

        message = (
            "BINANCE SUPERTREND SIGNALS\n"
            "Time: "
            + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            + "\n\n"
        )

        for signal in signals:
            message += (
                f"Symbol: {signal['symbol']}\n"
                f"Signal: {signal['signal']}\n"
                f"Price: {signal['price']}\n"
                "--------------------------\n"
            )

        send_email_alert(message)

    else:
        print("No trading signals found.")

    print("SCANNING COMPLETED")


if __name__ == "__main__":
    main()
