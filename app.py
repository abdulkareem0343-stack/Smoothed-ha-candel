import streamlit as st
import pandas as pd
import requests
import numpy as np
import ta

st.set_page_config(page_title="KuCoin SHA & RSI Scanner", page_icon="📈", layout="wide")

st.title("📈 KuCoin Smoothed HA + RSI Green Scanner")
st.write("Ye app KuCoin pairs scan karegi aur sirf wahi coins dikhaye gi jin par **Smoothed Heikin-Ashi Green** ho aur **RSI aapki set ki hui range** me ho.")

# Sidebar Controls
st.sidebar.header("1. Timeframe & Limit")
timeframe = st.sidebar.selectbox("Timeframe Select Karein", ["15m", "1h", "4h", "1d"], index=0)
timeframe_map = {"15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
scan_limit = st.sidebar.slider("Kitne Coins Scan Karne Hain?", min_value=10, max_value=150, value=50, step=10)

st.sidebar.header("2. RSI Filter")
rsi_period = st.sidebar.number_input("RSI Period", min_value=2, max_value=50, value=14)
rsi_range = st.sidebar.slider("RSI Range Select Karein (Min & Max)", 0.0, 100.0, (50.0, 70.0), step=1.0)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Weighted Moving Average (WMA)
def calculate_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda np_slice: np.dot(np_slice, weights) / weights.sum(), raw=True)

# TradingView Smoothed Heikin-Ashi + RSI Logic
def analyze_indicators(df, len1=10, len2=10, rsi_p=14):
    # --- Smoothed Heikin-Ashi ---
    e_open = calculate_wma(df['open'], len1)
    e_high = calculate_wma(df['high'], len1)
    e_low = calculate_wma(df['low'], len1)
    e_close = calculate_wma(df['close'], len1)

    ha_close = (e_open + e_high + e_low + e_close) / 4
    
    ha_open = [0.0] * len(df)
    ha_open[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
    
    for i in range(1, len(df)):
        if pd.isna(e_open.iloc[i-1]):
            ha_open[i] = (df['open'].iloc[i] + df['close'].iloc[i]) / 2
        else:
            ha_open[i] = (ha_open[i - 1] + ha_close.iloc[i - 1]) / 2

    ha_open_series = pd.Series(ha_open, index=df.index)

    sha_open = calculate_wma(ha_open_series, len2)
    sha_close = calculate_wma(ha_close, len2)

    curr_open = sha_open.iloc[-1]
    curr_close = sha_close.iloc[-1]
    prev_open = sha_open.iloc[-2]
    prev_close = sha_close.iloc[-2]

    is_green = curr_close > curr_open
    was_red = prev_close <= prev_open

    # --- RSI Calculation ---
    rsi_series = ta.momentum.rsi(df['close'], window=rsi_p)
    current_rsi = rsi_series.iloc[-1]

    return {
        "is_green": is_green,
        "is_new_green": is_green and was_red,
        "rsi": round(current_rsi, 2) if not pd.isna(current_rsi) else 0.0
    }

# KuCoin Kline Fetcher
def fetch_kucoin_klines(symbol, type_tf):
    url = f"https://api.kucoin.com/api/v1/market/candles?symbol={symbol}&type={type_tf}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data_json = res.json()
            if data_json.get('code') == '200000':
                data = data_json['data']
                df = pd.DataFrame(data, columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
                df = df.iloc[::-1].reset_index(drop=True)
                
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['close'] = df['close'].astype(float)
                return df
    except Exception:
        return None
    return None

if st.button("🚀 Start Scanning Market"):
    min_rsi, max_rsi = rsi_range
    st.info(f"Scanning KuCoin pairs on **{timeframe}** timeframe | RSI Range: **{min_rsi} to {max_rsi}**...")
    
    ticker_url = "https://api.kucoin.com/api/v1/symbols"
    
    try:
        ticker_res = requests.get(ticker_url, headers=HEADERS, timeout=10)
        ticker_data = ticker_res.json()
        
        if ticker_data.get('code') == '200000':
            symbols = [
                item['symbol'] for item in ticker_data['data'] 
                if item['symbol'].endswith('-USDT') and item['enableTrading']
            ]
            
            if "FIL-USDT" in symbols:
                symbols.remove("FIL-USDT")
                symbols.insert(0, "FIL-USDT")

            selected_symbols = symbols[:scan_limit]

            results = []
            progress_bar = st.progress(0)

            for idx, symbol in enumerate(selected_symbols):
                progress_bar.progress((idx + 1) / len(selected_symbols))
                df = fetch_kucoin_klines(symbol, timeframe_map[timeframe])
                
                if df is not None and len(df) >= 35:
                    analysis = analyze_indicators(df, rsi_p=rsi_period)
                    
                    # Conditions: 1. Green HA Candle AND 2. RSI in Selected Range
                    if analysis['is_green'] and (min_rsi <= analysis['rsi'] <= max_rsi):
                        status = "🟢 NEW GREEN (Fresh Buy)" if analysis['is_new_green'] else "🟢 GREEN (Bullish)"
                        tv_symbol = symbol.replace("-", "")
                        tv_link = f"https://www.tradingview.com/chart/?symbol=KUCOIN:{tv_symbol}"
                        
                        results.append({
                            "Coin Symbol": symbol,
                            "Current Price": f"${df['close'].iloc[-1]}",
                            "RSI Value": analysis['rsi'],
                            "SHA Status": status,
                            "TradingView": tv_link
                        })

            st.success(f"Scan Complete! **{len(results)}** Matching coins mile hain.")

            if results:
                res_df = pd.DataFrame(results)
                st.dataframe(
                    res_df,
                    column_config={
                        "TradingView": st.column_config.LinkColumn("Chart Link", display_text="Open Chart")
                    },
                    use_container_width=True
                )
            else:
                st.warning("Selected RSI Range aur Green Candle match karne wala koi coin nahi mila.")

    except Exception as e:
        st.error(f"Scan error: {e}")
