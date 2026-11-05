import os
import time
import requests
import pandas as pd
import pandas_ta as ta

def send_whatsapp_alert(message):
    """Sends signal alert to WhatsApp Business API"""
    WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL")
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    RECIPIENT = os.getenv("WHATSAPP_RECIPIENT_PHONE")
    
    if not WHATSAPP_API_URL or not WHATSAPP_TOKEN:
        print("WhatsApp credentials not set. Alert message:\n", message)
        return
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": RECIPIENT,
        "type": "text",
        "text": {"body": message}
    }
    try:
        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        print("WhatsApp alert sent successfully!")
    except Exception as e:
        print(f"Failed to send WhatsApp alert: {e}")

def fetch_futures_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    response = requests.get(url)
    data = response.json()
    symbols = []
    for s in data['symbols']:
        if s['contractType'] == 'PERPETUAL' and s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING':
            symbols.append(s['symbol'])
    return symbols

def fetch_ohlcv(symbol, interval='1h', limit=50):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_supertrend(df, period=10, multiplier=3):
    st = ta.supertrend(df['high'], df['low'], df['close'], length=period, multiplier=multiplier)
    if st is None or st.empty:
        return df
    df = pd.concat([df, st], axis=1)
    return df

def scan_markets():
    symbols = fetch_futures_symbols()
    print(f"Scanning {len(symbols)} USDT-M perpetual pairs...")
    
    for symbol in symbols:
        df = fetch_ohlcv(symbol, interval='1h', limit=50)
        if df is None or len(df) < 30:
            continue
            
        df = calculate_supertrend(df, period=10, multiplier=3)
        
        trend_col = [col for col in df.columns if col.startswith('SUPERTd_')]
        if not trend_col:
            continue
        t_col = trend_col[0]
        
        recent_24 = df[t_col].iloc[-25:-1]
        curr_close = df['close'].iloc[-2]
        prev_low = df['low'].iloc[-3]
        prev_high = df['high'].iloc[-3]
        
        # SHORT CONDITION
        if (recent_24 == -1).all():
            if curr_close < prev_low:
                msg = (
                    f"BINANCE FUTURES SIGNAL\n"
                    f"SHORT\n"
                    f"Coin: {symbol}\n"
                    f"Timeframe: 1 Hour\n"
                    f"Strategy: Supertrend 10,3\n"
                    f"Trend: Bearish (24h Confirmed)\n"
                    f"Confirmation: Candle closed below previous candle low.\n"
                    f"Entry: {curr_close}\n"
                    f"Signal Time: {df['timestamp'].iloc[-2]} UTC"
                )
                print(f"Signal Found: SHORT on {symbol}")
                send_whatsapp_alert(msg)

        # LONG CONDITION
        elif (recent_24 == 1).all():
            if curr_close > prev_high:
                msg = (
                    f"BINANCE FUTURES SIGNAL\n"
                    f"LONG\n"
                    f"Coin: {symbol}\n"
                    f"Timeframe: 1 Hour\n"
                    f"Strategy: Supertrend 10,3\n"
                    f"Trend: Bullish (24h Confirmed)\n"
                    f"Confirmation: Candle closed above previous candle high.\n"
                    f"Entry: {curr_close}\n"
                    f"Signal Time: {df['timestamp'].iloc[-2]} UTC"
                )
                print(f"Signal Found: LONG on {symbol}")
                send_whatsapp_alert(msg)

        time.sleep(0.1)

if __name__ == "__main__":
    scan_markets()
