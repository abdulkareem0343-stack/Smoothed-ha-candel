import streamlit as st
import pandas as pd
import requests
import ta

# Page Configuration
st.set_page_config(page_title="KuCoin SHA Green Scanner", page_icon="📈", layout="wide")

st.title("📈 KuCoin Smoothed HA Green Candle Scanner")
st.write("Ye app KuCoin ke Spot pairs scan karke sirf wo coins dikhaye gi jin par Smoothed Heikin-Ashi indicator **Green (Bullish)** hai.")

# Sidebar Settings
st.sidebar.header("Scanner Settings")
timeframe = st.sidebar.selectbox("Timeframe Select Karein", ["15m", "1h", "4h", "1d"], index=1)
timeframe_map = {"15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
scan_limit = st.sidebar.slider("Kitne Coins Scan Karne Hain?", min_value=10, max_value=100, value=30, step=10)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

# EMA Helper Function
def calculate_ema(series, period):
    return ta.trend.ema_indicator(series, window=period)

# Smoothed Heikin-Ashi Calculation Logic
def check_smoothed_ha(df, len1=10, len2=10):
    e_open = calculate_ema(df['open'], len1)
    e_high = calculate_ema(df['high'], len1)
    e_low = calculate_ema(df['low'], len1)
    e_close = calculate_ema(df['close'], len1)

    ha_close = (e_open + e_high + e_low + e_close) / 4
    ha_open = [(e_open.iloc[0] + e_close.iloc[0]) / 2]

    for i in range(1, len(df)):
        ha_open.append((ha_open[i - 1] + ha_close.iloc[i - 1]) / 2)

    ha_open = pd.Series(ha_open, index=df.index)

    sha_open = calculate_ema(ha_open, len2)
    sha_close = calculate_ema(ha_close, len2)

    curr_open = sha_open.iloc[-1]
    curr_close = sha_close.iloc[-1]
    prev_open = sha_open.iloc[-2]
    prev_close = sha_close.iloc[-2]

    is_green = curr_close > curr_open
    was_red = prev_close <= prev_open

    return {
        "is_green": is_green,
        "is_new_green": is_green and was_red,
        "sha_open": curr_open,
        "sha_close": curr_close
    }

# Safe KuCoin K-Line Fetcher
def fetch_kucoin_klines(symbol, type_tf):
    # KuCoin API Endpoint for Klines
    url = f"https://api.kucoin.com/api/v1/market/candles?symbol={symbol}&type={type_tf}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data_json = res.json()
            if data_json.get('code') == '200000':
                data = data_json['data']
                # KuCoin Structure: [time, open, close, high, low, volume, turnover]
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

# Scan Action Button
if st.button("🚀 Start Scanning KuCoin Market"):
    st.info("KuCoin market scan ho rahi hai, baraye meharbani intazar karein...")
    
    # Get KuCoin USDT Spot Pairs
    ticker_url = "https://api.kucoin.com/api/v1/symbols"
    
    try:
        ticker_res = requests.get(ticker_url, headers=HEADERS, timeout=10)
        if ticker_res.status_code != 200:
            st.error("KuCoin API Response Error! Phir se try karein.")
            st.stop()
            
        ticker_data = ticker_res.json()
        if ticker_data.get('code') != '200000':
            st.error("KuCoin Symbol Fetching Error!")
            st.stop()
            
        # Filter active USDT pairs
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
            
            if df is not None and len(df) > 20:
                signal = check_smoothed_ha(df)
                
                if signal['is_green']:
                    status = "🟢 NEW GREEN (Fresh Buy)" if signal['is_new_green'] else "🟢 GREEN (Bullish)"
                    tv_symbol = symbol.replace("-", "")
                    tv_link = f"https://www.tradingview.com/chart/?symbol=KUCOIN:{tv_symbol}"
                    
                    results.append({
                        "Coin Symbol": symbol,
                        "Current Price": f"${df['close'].iloc[-1]}",
                        "SHA Status": status,
                        "TradingView": tv_link
                    })

        st.success(f"Scan complete! Total **{len(results)}** Green coins mile hain.")

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
            st.warning("Filhal koi coin Green condition meet nahi kar raha.")

    except Exception as e:
        st.error(f"Error occurred: {e}")
