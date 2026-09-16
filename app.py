import streamlit as st
import pandas as pd
import requests
import numpy as np
import ta

# Page Configuration & Custom Theme
st.set_page_config(
    page_title="By Abdul Kareem - SHA & RSI Scanner",
    page_icon="⚡",
    layout="wide"
)

# Custom Styling for Unique Look
st.markdown("""
    <style>
    .developer-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
    }
    .stMetric {
        background-color: #1e293b;
        padding: 10px;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# App Header with Developer Branding
st.markdown("""
    <div class="developer-header">
        <h1>⚡ Crypto Scanner Dashboard</h1>
        <h3>Developed by: <b>ABDUL KAREEM</b></h3>
        <p>KuCoin Smoothed Heikin-Ashi + RSI Low-to-High Priority Scanner</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar Controls
st.sidebar.header("⚙️ Scanner Settings")
timeframe = st.sidebar.selectbox("Select Timeframe", ["15m", "1h", "4h", "1d"], index=0)
timeframe_map = {"15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
scan_limit = st.sidebar.slider("Scan Limit (Coins)", min_value=10, max_value=150, value=50, step=10)

st.sidebar.header("🎯 RSI Filter")
rsi_period = st.sidebar.number_input("RSI Period", min_value=2, max_value=50, value=14)
rsi_range = st.sidebar.slider("RSI Range Filter (Min & Max)", 0.0, 100.0, (20.0, 70.0), step=1.0)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Weighted Moving Average (WMA)
def calculate_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda np_slice: np.dot(np_slice, weights) / weights.sum(), raw=True)

# Technical Analysis Function
def analyze_indicators(df, len1=10, len2=10, rsi_p=14):
    # Smoothed Heikin-Ashi Calculation
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

    # RSI Calculation
    rsi_series = ta.momentum.rsi(df['close'], window=rsi_p)
    current_rsi = rsi_series.iloc[-1]

    return {
        "is_green": is_green,
        "is_new_green": is_green and was_red,
        "rsi": round(current_rsi, 2) if not pd.isna(current_rsi) else 0.0
    }

# KuCoin Data Fetcher
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

if st.button("🚀 Run Live Market Scan"):
    min_rsi, max_rsi = rsi_range
    st.info(f"Scanning KuCoin pairs on **{timeframe}** timeframe...")
    
    ticker_url = "https://api.kucoin.com/api/v1/symbols"
    
    try:
        ticker_res = requests.get(ticker_url, headers=HEADERS, timeout=10)
        ticker_data = ticker_res.json()
        
        if ticker_data.get('code') == '200000':
            symbols = [
                item['symbol'] for item in ticker_data['data'] 
                if item['symbol'].endswith('-USDT') and item['enableTrading']
            ]
            
            selected_symbols = symbols[:scan_limit]
            results = []
            progress_bar = st.progress(0)

            for idx, symbol in enumerate(selected_symbols):
                progress_bar.progress((idx + 1) / len(selected_symbols))
                df = fetch_kucoin_klines(symbol, timeframe_map[timeframe])
                
                if df is not None and len(df) >= 35:
                    analysis = analyze_indicators(df, rsi_p=rsi_period)
                    
                    if analysis['is_green'] and (min_rsi <= analysis['rsi'] <= max_rsi):
                        status = "🟢 NEW GREEN (Fresh Buy)" if analysis['is_new_green'] else "🟢 GREEN (Bullish)"
                        tv_symbol = symbol.replace("-", "")
                        tv_link = f"https://www.tradingview.com/chart/?symbol=KUCOIN:{tv_symbol}"
                        
                        results.append({
                            "Coin Symbol": symbol,
                            "RSI Value": analysis['rsi'],
                            "Current Price": f"${df['close'].iloc[-1]}",
                            "SHA Signal": status,
                            "TradingView": tv_link
                        })

            st.success("Scan Complete!")

            if results:
                # 1. Sort Results by RSI (Ascending Order: Low to High)
                res_df = pd.DataFrame(results)
                res_df = res_df.sort_values(by="RSI Value", ascending=True).reset_index(drop=True)

                # 2. Key Metrics Summary Display
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Coins Found", len(res_df))
                col2.metric("Lowest RSI Coin", f"{res_df.iloc[0]['Coin Symbol']} ({res_df.iloc[0]['RSI Value']})")
                col3.metric("Average RSI", round(res_df['RSI Value'].mean(), 2))

                st.subheader("📊 Sorted Results (Lowest RSI First)")

                # 3. Interactive Data Table Display
                st.dataframe(
                    res_df,
                    column_config={
                        "RSI Value": st.column_config.NumberColumn("RSI Value", format="%.2f 📉"),
                        "TradingView": st.column_config.LinkColumn("Chart Link", display_text="Open Chart 🔗")
                    },
                    use_container_width=True
                )
            else:
                st.warning("Selected RSI Range aur Green Candle match karne wala koi coin nahi mila.")

    except Exception as e:
        st.error(f"Scan error: {e}")
