import streamlit as st
import pandas as pd
import numpy as np
import random
import time
import uuid
from datetime import datetime

# Próba importu bibliotek do Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Badanie Decyzji", layout="centered")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 3em; font-weight: bold; }
    .instruction-card {
        background-color: #f8f9fa;
        border-left: 6px solid #003366;
        padding: 20px;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        color: #2c3e50;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- DANE GIEŁDOWE ---
DATA_A = [
    4000.00, 4020.00, 4100.00, 4080.00, 4150.00, 4200.00, 4220.00, 4300.00, 4350.00, 4400.00, 
    4380.00, 4350.00, 4320.00, 4400.00, 4450.00, 4500.00, 4550.00, 4600.00, 4580.00, 4650.00, 
    4700.00, 4750.00, 4800.00, 4750.00, 4600.00, 4400.00, 4200.00, 4100.00, 4050.00, 4150.00, 
    4200.00, 4250.00, 4300.00, 4350.00, 4320.00, 4400.00, 4450.00, 4420.00, 4480.00, 4500.00  
]
DATA_B = [
    11000.00, 11500.00, 11200.00, 11800.00, 12500.00, 12200.00, 12000.00, 12600.00, 13000.00, 12800.00, 
    13200.00, 13500.00, 14000.00, 13800.00, 13500.00, 13200.00, 13000.00, 13400.00, 13800.00, 14200.00, 
    14500.00, 14200.00, 14000.00, 14400.00, 14800.00, 15200.00, 15500.00, 15800.00, 15500.00, 15200.00, 
    15000.00, 14800.00, 14500.00, 14200.00, 13800.00, 13000.00, 12500.00, 12200.00, 12400.00, 12300.00  
]
LABELS_TEXT = [f"Miesiąc {i+1}" for i in range(40)]

def get_real_dates():
    dates = []
    y, m = 2022, 9
    for _ in range(40):
        dates.append(datetime(y, m, 1))
        m += 1
        if m > 12: m, y = 1, y + 1
    return dates
REAL_DATES = get_real_dates()

# --- PYTANIA ANKIETOWE ---
# (Tutaj wklej swoją listę FIXED_QUESTIONS z poprzedniego kodu - skróciłem dla czytelności, ale musi tam być)
FIXED_QUESTIONS = [
    {"id": "Q01_Overconfidence", "q": "Pytanie 1...", "opts": ["A", "B"]},
    # ... wklej resztę pytań tutaj ...
    {"id": "Q14_Hindsight_Bubble", "q": "Pytanie 14...", "opts": ["A", "B"]}
]

# --- INICJALIZACJA STANU ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
if 'page' not in st.session_state:
    st.session_state.page = 'intro'
if 'results' not in st.session_state:
    st.session_state.results = {
        'demographics': {},
        'game1_detailed_log': [], # ZMIANA: Lista słowników dla każdej rundy
        'game2_detailed_log': [], # ZMIANA: Lista słowników dla każdej rundy
        'survey_answers': {}
    }

# --- FUNKCJA ZAPISU DANYCH (KLUCZOWA ZMIANA) ---
def save_to_google_sheets():
    """Zapisuje dane do 3 oddzielnych arkuszy (Uczestnicy, Gielda, Moneta)"""
    
    # 1. Przygotowanie danych Uczestnika
    user_data = {
        "user_id": st.session_state.user_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "g1_final_capital": st.session_state.g1_history_user[-1],
        "g2_final_capital": st.session_state.g2_capital,
    }
    # Dodanie demografii i ankiety
    user_data.update(st.session_state.results['demographics'])
    user_data.update(st.session_state.results['survey_answers'])
    
    # Konwersja na DataFrame dla łatwiejszej obsługi
    df_users = pd.DataFrame([user_data])
    df_game1 = pd.DataFrame(st.session_state.results['game1_detailed_log'])
    df_game2 = pd.DataFrame(st.session_state.results['game2_detailed_log'])

    # Dodanie user_id do logów szczegółowych jeśli brakuje
    df_game1['user_id'] = st.session_state.user_id
    df_game2['user_id'] = st.session_state.user_id

    # ZAPIS
    if HAS_GSPREAD and 'gcp_service_account' in st.secrets:
        try:
            credentials = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            )
            gc = gspread.authorize(credentials)
            sh = gc.open("Wyniki_Badania") # UPEWNIJ SIĘ, ŻE MASZ TAKI PLIK
            
            # Helper function to append df to worksheet
            def append_df_to_sheet(worksheet_name, df):
                try:
                    ws = sh.worksheet(worksheet_name)
                    ws.append_rows(df.values.tolist())
                except Exception as ex:
                    st.error(f"Błąd zapisu do {worksheet_name}: {ex}")

            append_df_to_sheet("Uczestnicy", df_users)
            append_df_to_sheet("Giełda_Decyzje", df_game1)
            append_df_to_sheet("Moneta_Decyzje", df_game2)
            
            return True
        except Exception as e:
            st.error(f"Główny błąd Google Sheets: {e}")
            return False
    else:
        # Zapis lokalny do 3 plików CSV
        try:
            with open("wyniki_uczestnicy.csv", "a") as f:
                df_users.to_csv(f, header=f.tell()==0, index=False)
            with open("wyniki_gielda.csv", "a") as f:
                df_game1.to_csv(f, header=f.tell()==0, index=False)
            with open("wyniki_moneta.csv", "a") as f:
                df_game2.to_csv(f, header=f.tell()==0, index=False)
            return True
        except Exception as e:
            st.error(f"Błąd zapisu lokalnego: {e}")
            return False

# --- STRONY (INTRO & DEMO BEZ ZMIAN) ---
def show_intro():
    st.title("Badanie Decyzji Finansowych")
    st.write(f"ID: {st.session_state.user_id}")
    if st.button("Start"): next_page('demographics')

def show_demographics():
    st.header("Metryczka")
    with st.form("demo"):
        age = st.selectbox("Wiek", ["<18", "18-24", "25-34", "35-44", "45-54", "55+"])
        gender = st.radio("Płeć", ["Kobieta", "Mężczyzna", "Inna"])
        risk = st.slider("Skłonność do ryzyka (1-7)", 1, 7, 4)
        # ... dodaj resztę pól z poprzedniego kodu ...
        
        if st.form_submit_button("Dalej"):
            st.session_state.results['demographics'] = {
                "age": age, "gender": gender, "risk_tolerance": risk
                # ... reszta pól ...
            }
            next_page('game1_intro')

def next_page(page_name):
    st.session_state.page = page_name
    st.rerun()

def pad_history(hist, length):
    return hist + [None]*(length - len(hist))

# --- GRA 1: GIEŁDA (MODYFIKACJA LOGIKI ZBIERANIA DANYCH) ---
def show_game1_intro():
    st.header("Część 1: Giełda")
    st.write("Twoim celem jest maksymalizacja zysku przez 40 rund.")
    
    # Inicjalizacja zmiennych gry
    if 'g1_round' not in st.session_state:
        st.session_state.g1_round = 0 
        st.session_state.g1_history_user = [10000.0]
        st.session_state.start_A = DATA_A[0]
        st.session_state.start_B = DATA_B[0]
        st.session_state.g1_history_A = [10000.0]
        st.session_state.g1_history_B = [10000.0]
        # Przechowywanie poprzednich zwrotów do analizy
        st.session_state.prev_ret_A = 0.0
        st.session_state.prev_ret_B = 0.0

    if st.button("Start Gry Giełdowej"):
        next_page('game1')

def show_game1():
    idx = st.session_state.g1_round
    if idx >= 39: 
        next_page('game2_intro')
        return

    current_cap = st.session_state.g1_history_user[-1]
    
    # Wykresy i UI (bez zmian wizualnych)
    st.subheader(f"Runda {idx + 1} / 40")
    st.metric("Kapitał", f"{current_cap:.2f} PLN")
    
    chart_data = pd.DataFrame({
        "S&P 500": pad_history(st.session_state.g1_history_A, 40),
        "Nasdaq": pad_history(st.session_state.g1_history_B, 40),
        "User": pad_history(st.session_state.g1_history_user, 40)
    })
    st.line_chart(chart_data)

    leverage_active = False
    if idx >= 20:
        st.warning("⚡ LEWAR DOSTĘPNY (x2)")
        leverage_active = st.checkbox("Użyj lewaru")

    col1, col2, col3 = st.columns(3)
    choice = None
    if col1.button("Indeks A"): choice = 'A'
    if col2.button("Indeks B"): choice = 'B'
    if col3.button("Gotówka"): choice = 'Cash'

    if choice:
        # Obliczenia nowej rundy
        next_idx = idx + 1
        
        # Obliczanie zwrotów rynkowych (zmienne niezależne)
        price_A_old, price_A_new = DATA_A[idx], DATA_A[next_idx]
        price_B_old, price_B_new = DATA_B[idx], DATA_B[next_idx]
        
        ret_A = (price_A_new - price_A_old) / price_A_old
        ret_B = (price_B_new - price_B_old) / price_B_old
        
        # Zwrot użytkownika
        base_ret = 0.0
        if choice == 'A': base_ret = ret_A
        elif choice == 'B': base_ret = ret_B
        
        final_ret = base_ret * 2 if leverage_active else base_ret
        new_cap = current_cap * (1 + final_ret)
        
        # --- ZBIERANIE DANYCH DLA HIPOTEZ (Long Format) ---
        log_entry = {
            "round": next_idx,
            "capital_before": current_cap,
            "choice": choice,
            "leverage_used": 1 if leverage_active else 0, # Do H3
            "market_ret_A": ret_A,      # Do H1 (sekwencje)
            "market_ret_B": ret_B,      # Do H1
            "user_return": final_ret,   # Do H2b (reakcja na stratę/zysk)
            "user_outcome_pln": new_cap - current_cap,
            "capital_after": new_cap
        }
        st.session_state.results['game1_detailed_log'].append(log_entry)
        
        # Aktualizacja stanu
        st.session_state.g1_history_user.append(new_cap)
        st.session_state.g1_history_A.append((price_A_new/st.session_state.start_A)*10000)
        st.session_state.g1_history_B.append((price_B_new/st.session_state.start_B)*10000)
        st.session_state.g1_round += 1
        st.rerun()

# --- GRA 2: MONETA (MODYFIKACJA LOGIKI ZBIERANIA DANYCH) ---
def show_game2_intro():
    st.header("Część 2: Moneta")
    st.write("Orzeł (60%) / Reszka (40%). Start: 100 PLN.")
    if 'g2_round' not in st.session_state:
        st.session_state.g2_round = 1
        st.session_state.g2_capital = 100.0
        st.session_state.g2_history_chart = [100.0]
    if st.button("Start Gry z Monetą"):
        next_page('game2')

def show_game2():
    idx = st.session_state.g2_round
    cap = st.session_state.g2_capital
    
    st.subheader(f"Rzut {idx} / 40")
    st.metric("Kapitał", f"{cap:.2f} PLN")

    if cap <= 0.01:
        st.error("Bankructwo.")
        if st.button("Do ankiety"): next_page('survey')
        return

    bet_val = st.number_input("Stawka", 0.0, float(cap), min(10.0, cap))
    bet_side = st.radio("Wybór", ["ORZEŁ", "RESZKA"])

    if st.button("RZUĆ"):
        is_heads = random.random() < 0.6
        res_str = "ORZEŁ" if is_heads else "RESZKA"
        win = (bet_side == res_str)
        pnl = bet_val if win else -bet_val
        
        # --- ZBIERANIE DANYCH DLA HIPOTEZ (Long Format) ---
        log_entry = {
            "round": idx,
            "capital_before": cap,
            "bet_amount": bet_val,          # Do H4 (Martingale)
            "bet_ratio": bet_val / cap if cap > 0 else 0, # Do H3 (Over-betting) i H5 (Kelly)
            "choice": "HEADS" if bet_side == "ORZEŁ" else "TAILS", # Do H1 (Gambler's Fallacy)
            "outcome_res": "HEADS" if is_heads else "TAILS",
            "is_win": 1 if win else 0,      # Do H4 (reakcja na przegraną)
            "capital_after": cap + pnl
        }
        st.session_state.results['game2_detailed_log'].append(log_entry)
        
        st.session_state.g2_capital += pnl
        st.session_state.g2_history_chart.append(st.session_state.g2_capital)
        st.session_state.g2_round += 1
        
        msg = f"Wypadł {res_str}. {'Wygrywasz' if win else 'Tracisz'} {bet_val:.2f}."
        if win: st.success(msg)
        else: st.error(msg)
        
        if st.session_state.g2_round > 40:
            time.sleep(1.5)
            next_page('survey')
        else:
            time.sleep(1.0)
            st.rerun()

# --- ANKIETA I KONIEC ---
def show_survey():
    # ... (Kod ankiety taki jak w Twoim oryginale) ...
    # Ważne: Zapisuj odpowiedzi do st.session_state.results['survey_answers']
    
    # Tymczasowe uproszczenie dla przykładu:
    st.header("Ankieta")
    if st.button("Zakończ i wyślij"):
        # Symulacja wypełnienia
        st.session_state.results['survey_answers'] = {"Q1": "A", "Q2": "B"} 
        next_page('finish')

def show_finish():
    st.header("Zapisywanie...")
    if 'saved' not in st.session_state:
        with st.spinner("Przesyłanie danych..."):
            success = save_to_google_sheets()
        
        if success:
            st.success("Dane zapisane pomyślnie!")
            st.balloons()
        else:
            st.error("Błąd zapisu.")
        st.session_state.saved = True

# --- ROUTER ---
if st.session_state.page == 'intro': show_intro()
elif st.session_state.page == 'demographics': show_demographics()
elif st.session_state.page == 'game1_intro': show_game1_intro()
elif st.session_state.page == 'game1': show_game1()
elif st.session_state.page == 'game2_intro': show_game2_intro()
elif st.session_state.page == 'game2': show_game2()
elif st.session_state.page == 'survey': show_survey()
elif st.session_state.page == 'finish': show_finish()