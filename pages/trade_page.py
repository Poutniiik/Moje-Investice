# =========================================================================
# SOUBOR: pages/trade_page.py (VERZE: STABILNÍ FORMULÁŘ)
# =========================================================================
import streamlit as st
import pandas as pd
import time
import utils

def trade_page(USER, df, df_cash, zustatky, LIVE_DATA, kurzy, 
               proved_nakup_fn, proved_prodej_fn, proved_smenu_fn, 
               pohyb_penez_fn, invalidate_data_core_fn):
    
    st.title("💸 OBCHODNÍ PULT")

    # 1. Čítač transakcí (Pro kompletní reset formuláře po odeslání)
    if 'tx_counter' not in st.session_state:
        st.session_state['tx_counter'] = 0
    
    # Tento klíč se změní po každé úspěšné transakci -> vyčistí formulář
    form_key = f"trade_form_{st.session_state['tx_counter']}"

    # --- HORNÍ ČÁST (Výběr Tickeru - MUSÍ BÝT MIMO FORMULÁŘ PRO LIVE UPDATE) ---
    with st.container(border=True):
        mode = st.radio("Režim:", ["🟢 NÁKUP", "🔴 PRODEJ"], horizontal=True, key="main_mode")
        st.divider()
        
        # Ticker a Cena jsou mimo formulář, aby se cena aktualizovala hned, jak napíšeš ticker
        c1, c2 = st.columns([1, 1])
        with c1:
            if mode == "🔴 PRODEJ" and not df.empty:
                ticker_input = st.selectbox("Ticker", df['Ticker'].unique(), key="global_ticker_select")
            else:
                ticker_input = st.text_input("Ticker", placeholder="např. AAPL", key="global_ticker_input").upper()
        
        # Live Cena Logic
        price, curr = 0, "USD"
        if ticker_input:
            info = LIVE_DATA.get(ticker_input, {})
            price = info.get('price', 0)
            curr = info.get('curr', 'USD')
            if price == 0:
                with st.spinner(f"Hledám cenu pro {ticker_input}..."):
                    p, m, _ = utils.ziskej_info(ticker_input)
                    if p: price, curr = p, m
        
        if price > 0:
            with c2: 
                st.markdown(f"### {price:,.2f} {curr}")
                st.caption("Aktuální tržní cena")
        
        st.divider()

        # --- FORMULÁŘ PRO ZADÁNÍ MNOŽSTVÍ A POTVRZENÍ ---
        # Tady začíná "bezpečná zóna". Nic se neodešle samo.
        with st.form(key=form_key, clear_on_submit=True):
            st.write(f"Zadání objednávky ({mode}):")
            
            c_q, c_p = st.columns(2)
            with c_q: 
                qty = st.number_input("Počet kusů", min_value=0.0, step=1.0)
            with c_p: 
                limit = st.number_input("Cena za kus", value=float(price) if price > 0 else 0.0)
            
            # Info o celkové ceně (v rámci formu se neaktualizuje dynamicky, 
            # ale uživatel to vidí odhadem, přesná kalkulace proběhne po stisku)
            st.caption("Poznámka: Celková cena se vypočte při odeslání.")

            # Tlačítko uvnitř formuláře
            submit_label = f"POTVRDIT {mode.split()[1]}"
            submitted = st.form_submit_button(submit_label, type="primary", use_container_width=True)
            
            if submitted:
                # --- TADY SE DĚJE AKCE PO KLIKNUTÍ ---
                if qty <= 0:
                    st.error("Musíš zadat počet kusů větší než 0.")
                elif limit <= 0:
                    st.error("Cena musí být větší než 0.")
                else:
                    # Rozcestník Nákup/Prodej
                    success = False
                    msg = ""
                    
                    if mode == "🟢 NÁKUP":
                        success, msg = proved_nakup_fn(ticker_input, qty, limit, USER)
                    else:
                        success, msg = proved_prodej_fn(ticker_input, qty, limit, USER, curr)
                    
                    # Vyhodnocení
                    if success:
                        st.success(msg)
                        # DŮLEŽITÉ: Zvýšíme counter -> Při příštím načtení bude mít formulář 
                        # nový klíč a bude PRÁZDNÝ.
                        st.session_state['tx_counter'] += 1
                        
                        # Invalidace cache dat
                        if invalidate_data_core_fn: 
                            invalidate_data_core_fn()
                        
                        time.sleep(1) # Krátká pauza pro přečtení zprávy
                        st.rerun()    # Restart stránky
                    else:
                        st.error(msg)

    # --- SMĚNÁRNA (Taky do formuláře pro jistotu) ---
    with st.expander("💱 SMĚNÁRNA"):
        with st.form(key=f"exchange_form_{st.session_state['tx_counter']}"):
            c_ex1, c_ex2, c_ex3 = st.columns(3)
            with c_ex1: am = st.number_input("Částka", 0.0, step=100.0)
            with c_ex2: fr = st.selectbox("Z měny", ["CZK", "USD", "EUR"])
            with c_ex3: to = st.selectbox("Do měny", ["USD", "CZK", "EUR"])
            
            ex_submit = st.form_submit_button("Směnit", use_container_width=True)
            
            if ex_submit:
                res = proved_smenu_fn(am, fr, to, USER)
                if isinstance(res, tuple): ok, msg = res
                else: ok, msg = res, "Info"
                
                if ok:
                    st.success(msg)
                    st.session_state['tx_counter'] += 1
                    if invalidate_data_core_fn: invalidate_data_core_fn()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)

    # --- MANUÁLNÍ VKLAD (Formulář) ---
    with st.expander("💰 PENĚŽENKA (Vklad/Výběr)"):
        with st.form(key=f"wallet_form_{st.session_state['tx_counter']}"):
            m_op = st.radio("Typ operace", ["Vklad", "Výběr"], horizontal=True)
            c_w1, c_w2 = st.columns(2)
            with c_w1: m_amt = st.number_input("Částka", 0.0, step=500.0)
            with c_w2: m_cur = st.selectbox("Měna", ["CZK", "USD", "EUR"])
            
            w_submit = st.form_submit_button("Provést operaci")
            
            if w_submit:
                sign = 1 if m_op == "Vklad" else -1
                df_new = pohyb_penez_fn(m_amt * sign, m_cur, m_op, "Manual", USER, df_cash)
                
                # Manuální uložení (protože nemáme wrapper funkci ve web_investice pro vklad)
                # Tohle je bezpečné, protože se děje jen po submitu
                st.session_state['df_cash'] = df_new
                from data_manager import SOUBOR_CASH, uloz_data_uzivatele
                uloz_data_uzivatele(df_new, USER, SOUBOR_CASH)
                
                st.success("Hotovo")
                st.session_state['tx_counter'] += 1
                if invalidate_data_core_fn: invalidate_data_core_fn()
                time.sleep(1)
                st.rerun()
