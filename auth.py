import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# Import funkcí pro práci s daty a šifrování
# (Streamlit vidí root složku, takže import z data_manager funguje i odtud)
from data_manager import nacti_uzivatele, uloz_csv, zasifruj, SOUBOR_UZIVATELE

def render_login_screen(cookie_manager):
    """
    Vykreslí přihlašovací obrazovku.
    Vrací True, pokud se uživatel úspěšně přihlásil (nebo byl přihlášen).
    """
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔐 INVESTIČNÍ TERMINÁL")
        t1, t2, t3 = st.tabs(["PŘIHLÁŠENÍ", "REGISTRACE", "OBNOVA HESLA"])
        
        # --- TAB 1: PŘIHLÁŠENÍ ---
        with t1:
            with st.form("l"):
                u = st.text_input("Uživatelské jméno")
                p = st.text_input("Heslo", type="password")
                if st.form_submit_button("VSTOUPIT", use_container_width=True):
                    df_u = nacti_uzivatele()
                    # Ošetření prázdné databáze
                    if df_u.empty:
                        st.error("Databáze uživatelů je prázdná.")
                    else:
                        row = df_u[df_u['username'] == u]
                        if not row.empty and row.iloc[0]['password'] == zasifruj(p):
                            # Nastavení cookies a session state
                            cookie_manager.set("invest_user", u, expires_at=datetime.now() + timedelta(days=30))
                            st.session_state.update({'prihlasen': True, 'user': u})
                            st.toast("Přihlašování...", icon="⏳")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.toast("Chyba přihlášení (špatné jméno nebo heslo)", icon="❌")

        # --- TAB 2: REGISTRACE ---
        with t2:
            with st.form("r"):
                nu = st.text_input("Nové jméno")
                new_pass = st.text_input("Nové heslo", type="password")
                nr = st.text_input("Záchranný kód", help="Slouží pro obnovu zapomenutého hesla.")
                if st.form_submit_button("VYTVOŘIT ÚČET", use_container_width=True):
                    df_u = nacti_uzivatele()
                    if not df_u.empty and nu in df_u['username'].values:
                        st.toast("Jméno již existuje.", icon="⚠️")
                    else:
                        if len(nu) < 3 or len(new_pass) < 3:
                            st.error("Jméno i heslo musí mít alespoň 3 znaky.")
                        else:
                            new = pd.DataFrame([{"username": nu, "password": zasifruj(new_pass), "recovery_key": zasifruj(nr)}])
                            uloz_csv(pd.concat([df_u, new], ignore_index=True), SOUBOR_UZIVATELE, "New user")
                            st.toast("Účet vytvořen!", icon="✅")

        # --- TAB 3: OBNOVA HESLA ---
        with t3:
            st.caption("Zapomněl jsi heslo?")
            with st.form("recovery"):
                ru = st.text_input("Jméno")
                rk = st.text_input("Záchranný kód")
                rnp = st.text_input("Nové heslo", type="password")
                if st.form_submit_button("OBNOVIT"):
                    df_u = nacti_uzivatele()
                    if df_u.empty:
                        st.error("Databáze je prázdná.")
                    else:
                        row = df_u[df_u['username'] == ru]
                        if not row.empty and row.iloc[0]['recovery_key'] == zasifruj(rk):
                            if rnp and len(rnp) > 0:
                                df_u.at[row.index[0], 'password'] = zasifruj(rnp)
                                uloz_csv(df_u, SOUBOR_UZIVATELE, f"Rec {ru}")
                                st.success("Hotovo! Můžeš se přihlásit.")
                            else:
                                st.error("Chyba v novém hesle.")
                        else:
                            st.error("Záchranný kód nebo jméno nesedí.")
