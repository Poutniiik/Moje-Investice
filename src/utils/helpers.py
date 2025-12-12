# Helpers
import numpy as np
import smtplib
from email.mime.text import MIMEText
import streamlit as st
from src.config import RISK_FREE_RATE

# --- FINANČNÍ FUNKCE ---
def calculate_sharpe_ratio(returns, risk_free_rate=RISK_FREE_RATE, periods_per_year=252):
    if returns.empty or returns.std() == 0:
        return 0.0
    daily_risk_free_rate = risk_free_rate / periods_per_year
    excess_returns = returns - daily_risk_free_rate
    sharpe_ratio = np.sqrt(periods_per_year) * (excess_returns.mean() / returns.std())
    return sharpe_ratio

def odeslat_email(prijemce, predmet, telo):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
        msg = MIMEText(telo, 'html')
        msg['Subject'] = predmet
        msg['From'] = sender_email
        msg['To'] = prijemce
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, prijemce, msg.as_string())
        return True
    except Exception as e: return f"Chyba: {e}"
