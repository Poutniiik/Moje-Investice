import streamlit as st
import yfinance as yf

st.title("Test Yahoo Spojení")

tickers = ["AAPL", "CEZ.PR", "ADS.DE"]

for t in tickers:
    st.write(f"Zkouším stáhnout: {t}...")
    try:
        stock = yf.Ticker(t)
        price = stock.fast_info.last_price
        currency = stock.fast_info.currency
        st.success(f"✅ {t}: {price} {currency}")
    except Exception as e:
        st.error(f"❌ {t} selhalo: {e}")
