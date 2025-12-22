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

# --- STYLE CSS (Visual Upgrade) ---
st.markdown("""
    <style>
    /* Przycisk */
    .stButton>button { width: 100%; height: 3em; font-weight: bold; }
    
    /* Nowoczesny box z instrukcją */
    .instruction-card {
        background-color: #ffffff;
        border-left: 5px solid #4CAF50;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 25px;
        color: #333;
    }
    .instruction-card h3 {
        margin-top: 0;
        color: #2E7D32;
    }
    .instruction-card ul {
        padding-left: 20px;
    }
    
    /* Ukrycie domyślnego menu Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- DANE GIEŁDOWE (HARDCODED) ---
# Dane odwrócone chronologicznie (od Rundy 1: wrz 2022 do Rundy 40: gru 2025)

# Indeks A (S&P 500)
DATA_A = [
    3585.62, 3871.98, 4080.11, 3839.50, 4076.60, 3970.15, 4109.31, 4169.48, 4179.83, 4450.38, # 1-10
    4588.96, 4507.66, 4288.05, 4193.80, 4567.80, 4769.83, 4845.65, 5096.27, 5254.35, 5035.69, # 11-20
    5277.51, 5460.48, 5522.30, 5648.40, 5762.48, 5705.45, 6032.38, 5881.63, 6040.53, 5954.50, # 21-30
    5611.85, 5569.06, 5911.69, 6204.95, 6339.39, 6460.26, 6688.46, 6840.20, 6849.09, 6834.50  # 31-40
]

# Indeks B (Nasdaq)
DATA_B = [
    10575.62, 10988.15, 11468.00, 10466.48, 11584.55, 11455.54, 12221.91, 12226.58, 12935.29, 13787.92, # 1-10
    14346.02, 14034.97, 13219.32, 12851.24, 14226.22, 15011.35, 15164.01, 16091.92, 16379.46, 15657.82, # 11-20
    16735.02, 17732.60, 17599.40, 17713.63, 18189.17, 18095.15, 19218.17, 19310.79, 19627.44, 18847.28, # 21-30
    17299.29, 17446.34, 19113.77, 20369.73, 21122.45, 21455.55, 22660.01, 23724.96, 23365.69, 23307.62  # 31-40
]

# Etykiety dat (Rundy 1-40)
LABELS = [
    "wrz 22", "paź 22", "lis 22", "gru 22", "sty 23", "lut 23", "mar 23", "kwi 23", "maj 23", "cze 23",
    "lip 23", "sie 23", "wrz 23", "paź 23", "lis 23", "gru 23", "sty 24", "lut 24", "mar 24", "kwi 24",
    "maj 24", "cze 24", "lip 24", "sie 24", "wrz 24", "paź 24", "lis 24", "gru 24", "sty 25", "lut 25",
    "mar 25", "kwi 25", "maj 25", "cze 25", "lip 25", "sie 25", "wrz 25", "paź 25", "lis 25", "gru 25"
]

# --- INICJALIZACJA STANU ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
if 'page' not in st.session_state:
    st.session_state.page = 'intro'
if 'results' not in st.session_state:
    st.session_state.results = {
        'demographics': {},
        'game1_history': [],
        'game2_history': [],
        'survey_answers': {}
    }

# Pytania ankietowe
ALL_QUESTIONS = [
    {"id": "LA_1", "type": "Loss Aversion", "q": "Kupiłeś akcje 'NanoTech' po 50 PLN. Obecnie kosztują 80 PLN (+60%). Analitycy celują w 100 PLN, ale czujesz niepokój.", "opts": ["A: Sprzedajesz teraz, żeby 'zaksięgować zysk'.", "B: Trzymasz pozycję, pozwalając zyskom rosnąć."]},
    {"id": "LA_2", "type": "Loss Aversion", "q": "Masz akcje spółki węglowej kupione po 100 PLN. Obecnie kosztują 70 PLN (-30%). Fundamenty się pogarszają.", "opts": ["A: Sprzedajesz, akceptując stratę, by ochronić kapitał.", "B: Trzymasz, czekając aż wrócą do 90-100 PLN, żeby wyjść na zero."]},
    {"id": "LA_3", "type": "Loss Aversion", "q": "Inwestycja spadła z 200 PLN do 150 PLN, ale nagle odbiła do 198 PLN (prawie cena zakupu).", "opts": ["A: Sprzedajesz natychmiast, czując ulgę, że 'prawie nic nie straciłeś'.", "B: Trzymasz dalej dla zysku, analizując powód wzrostu."]},
    {"id": "FB_1", "type": "Framing", "q": "ZYSK: Otrzymałeś 100 000 PLN. Wybierz:", "opts": ["A: Pewny zysk 30 000 PLN.", "B: 30% szans na zysk 100 000 PLN i 70% szans na brak zysku."]},
    {"id": "FB_2", "type": "Framing", "q": "STRATA: Otrzymałeś wezwanie do zapłaty 100 000 PLN podatku. Wybierz:", "opts": ["A: Pewna strata (zapłata) 70 000 PLN.", "B: 30% szans, że nie zapłacisz nic, 70% szans, że zapłacisz 100 000 PLN."]},
    {"id": "AB_1", "type": "Availability", "q": "Wybierasz fundusz akcji polskich. Który wolisz?", "opts": ["A: 'Lider Wzrostu' – nagroda 'Fundusz Roku', ostatni kwartał +15%, głośno w mediach.", "B: 'Systematyczny' – brak nagród, stabilne 7-8% rocznie od 10 lat, cichy."]},
    {"id": "AB_2", "type": "Availability", "q": "Wiadomości donoszą o katastrofie budowlanej w Azji. Masz akcje europejskiej budowlanki.", "opts": ["A: Rozważasz sprzedaż, bo masz obraz katastrofy przed oczami.", "B: Ignorujesz newsa z Azji jako nieistotny dla rynku europejskiego."]},
    {"id": "AB_3", "type": "Availability", "q": "Pracujesz w IT. Budujesz portfel emerytalny.", "opts": ["A: Inwestujesz 80% w spółki technologiczne, bo się na tym znasz.", "B: Dywersyfikujesz o surowce i banki, mimo że nie znasz tych branż."]},
    {"id": "CB_1", "type": "Confirmation", "q": "Chcesz kupić Bitcoina. Co wpisujesz w Google?", "opts": ["A: 'Dlaczego Bitcoin to przyszłość' / 'Prognozy wzrostu'.", "B: 'Zagrożenia dla rynku krypto' / 'Analiza ryzyka'."]},
    {"id": "CB_2", "type": "Confirmation", "q": "Spółka ma zysk zgodny z oczekiwaniami, ale drastycznie wzrosło zadłużenie.", "opts": ["A: Skupiasz się na zysku ('Dowożą wyniki!') ignorując dług.", "B: Analizujesz strukturę długu, martwiąc się o płynność."]},
    {"id": "CB_3", "type": "Confirmation", "q": "Twój analityk rekomenduje 'Kupuj'. Inny analityk pisze 'Sprzedaj' (błędy w księgowości).", "opts": ["A: Czytasz raport swojego analityka, by się upewnić. Drugi odrzucasz.", "B: Czytasz uważnie negatywny raport, by sprawdzić, czy Twój analityk się nie myli."]},
    {"id": "HB_1", "type": "Hindsight", "q": "Patrzysz na wykres krachu z 2008 roku. Co myślisz?", "opts": ["A: 'Wskaźniki były absurdalne, każdy rozsądny by to przewidział'.", "B: 'W tamtym czasie sytuacja była niejednoznaczna'."]},
    {"id": "HB_2", "type": "Hindsight", "q": "Fundusz zarobił 40% (rynek 5%) dzięki jednej ryzykownej transakcji na opcjach.", "opts": ["A: Powierzasz mu pieniądze – wynik dowodzi geniuszu zarządzającego.", "B: Rezygnujesz – uważasz, że miał po prostu szczęście (zbyt duże ryzyko)."]},
    {"id": "HB_3", "type": "Hindsight", "q": "Wspominasz bańkę na spółkach Growth. Jak oceniasz swoje ówczesne myśli?", "opts": ["A: 'Wiedziałem, że to bańka i tylko czekałem aż pęknie'.", "B: 'Wtedy argumenty za wzrostami wydawały się równie silne'."]}
]

if 'shuffled_questions' not in st.session_state:
    q_copy = ALL_QUESTIONS.copy()
    random.shuffle(q_copy)
    st.session_state.shuffled_questions = q_copy

# --- FUNKCJE ---

def next_page(page_name):
    st.session_state.page = page_name
    st.rerun()

def save_to_google_sheets(data_dict):
    """Wysyła dane do Google Sheets - wersja naprawiona (konwersja na str + fix błędu 200)"""
    if HAS_GSPREAD and 'gcp_service_account' in st.secrets:
        try:
            credentials = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ],
            )
            gc = gspread.authorize(credentials)
            sh = gc.open("Wyniki_Badania") 
            worksheet = sh.worksheet("Dane_Surowe")
            
            # Konwersja wszystkiego na tekst
            values = [str(v) for v in data_dict.values()]
            worksheet.append_row(values)
            return True
        except Exception as e:
            if "200" in str(e): return True
            st.error(f"Błąd zapisu Google Sheets: {e}")
            return False
    else:
        df = pd.DataFrame([data_dict])
        try:
            with open("lokalne_wyniki.csv", "a") as f:
                df.to_csv(f, header=f.tell()==0, index=False)
            return True
        except Exception as e:
            st.error(f"Błąd zapisu lokalnego: {e}")
            return False

# --- STRONY ---

def show_intro():
    st.title("Badanie Decyzji Finansowych")
    st.markdown(f"""
    Dzień dobry!
    Twój identyfikator: **{st.session_state.user_id}**.
    
    Badanie zajmie ok. 10 minut i składa się z 3 części:
    1. Gra Giełdowa (40 rund).
    2. Rzuty Monetą (zarządzanie stawką).
    3. Krótka Ankieta.
    """)
    if st.button("Rozpocznij badanie"):
        next_page('demographics')

def show_demographics():
    st.header("Metryczka")
    with st.form("demo"):
        age = st.selectbox("Wiek", ["18-24", "25-34", "35-44", "45-54", "55+"])
        gender = st.radio("Płeć", ["Kobieta", "Mężczyzna", "Inna"])
        risk = st.slider("Skłonność do ryzyka (1-Niska, 7-Wysoka)", 1, 7, 4)
        if st.form_submit_button("Dalej"):
            st.session_state.results['demographics'] = {"age": age, "gender": gender, "risk_tolerance": risk}
            next_page('game1_intro')

# --- GRA 1: GIEŁDA ---

def show_game1_intro():
    st.header("Część 1: Gra Inwestycyjna")
    
    # Grafika (emoji header)
    st.markdown("# 📈 📉 💰")
    
    st.markdown("""
    <div class="instruction-card">
        <h3>Instrukcja:</h3>
        Wcielasz się w rolę inwestora. Masz przed sobą <b>40 rund</b> (reprezentujących 40 miesięcy).
        <ul>
            <li>Na start otrzymujesz <b>10 000 PLN</b> wirtualnego kapitału.</li>
            <li>W każdej rundzie decydujesz, gdzie ulokować pieniądze:</li>
            <ul>
                <li><b>Indeks A (S&P 500):</b> Rynek akcji USA (szeroki).</li>
                <li><b>Indeks B (Nasdaq):</b> Spółki technologiczne (wyższa zmienność).</li>
                <li><b>Gotówka:</b> Bezpieczna przystań (0% zysku).</li>
            </ul>
            <li>Twoim celem jest maksymalizacja zysku.</li>
            <li>Od 21. rundy dostępny będzie <b>Lewar (x2)</b>.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Inicjalizacja Gry 1
    if 'g1_round' not in st.session_state:
        st.session_state.g1_round = 0 # Start index (0 = Round 1 data)
        st.session_state.g1_capital = 10000.0
        # Historia do wykresu (zaczynamy od startu)
        st.session_state.g1_history_user = [10000.0]
        # Aby wykres był czytelny, znormalizujemy indeksy, żeby też startowały od 10k
        st.session_state.start_A = DATA_A[0]
        st.session_state.start_B = DATA_B[0]
        st.session_state.g1_history_A = [10000.0]
        st.session_state.g1_history_B = [10000.0]
        st.session_state.g1_labels = [LABELS[0]]

    if st.button("Rozumiem, gramy!"):
        next_page('game1')

def show_game1():
    current_idx = st.session_state.g1_round
    
    # Jeśli koniec danych
    if current_idx >= 39: 
        next_page('game2_intro')
        return

    # Obliczenie zmiany procentowej dla wyświetlenia
    current_cap = st.session_state.g1_history_user[-1]
    prev_cap = st.session_state.g1_history_user[-2] if len(st.session_state.g1_history_user) > 1 else 10000.0
    pct_change_show = ((current_cap - prev_cap) / prev_cap) * 100
    
    st.subheader(f"Runda {current_idx + 1} / 40 ({LABELS[current_idx]})")
    
    # Metryki
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Twój Kapitał", f"{current_cap:.2f} PLN", f"{pct_change_show:.2f}%")
    
    # Przygotowanie danych do wykresu (kolorowa linia)
    chart_data = pd.DataFrame({
        "Data": st.session_state.g1_labels,
        "Twój Kapitał (🔴)": st.session_state.g1_history_user,
        "S&P 500": st.session_state.g1_history_A,
        "Nasdaq": st.session_state.g1_history_B
    }).set_index("Data")
    
    # Wykres z kolorami (czerwony dla gracza)
    st.line_chart(chart_data, color=["#FF0000", "#AAAAAA", "#4444FF"]) 
    # Uwaga: Kolejność kolorów zależy od sortowania kolumn, 
    # w Streamlit color mapuje się alfabetycznie po kolumnach:
    # 1. Nasdaq, 2. S&P 500, 3. Twój Kapitał.
    # Żeby mieć pewność, w nowszym Streamlit można użyć color=["#4444FF", "#AAAAAA", "#FF0000"]
    # (Nasdaq=Blue, SP500=Grey, User=Red).
    
    # Logika Lewaru
    leverage_active = False
    if current_idx >= 20: # Od rundy 21 (index 20)
        st.warning("⚡ ODBLOKOWANO DŹWIGNIĘ (LEWAR x2)")
        leverage_active = st.checkbox("Użyj dźwigni (x2 zyski/straty)")

    st.write("W co inwestujesz na kolejny miesiąc?")
    col1, col2, col3 = st.columns(3)
    choice = None
    if col1.button("Indeks A (S&P 500)"): choice = 'A'
    if col2.button("Indeks B (Nasdaq)"): choice = 'B'
    if col3.button("Gotówka"): choice = 'Cash'

    if choice:
        # Pobieramy realną zmianę z następnego kroku
        next_idx = current_idx + 1
        
        price_A_prev = DATA_A[current_idx]
        price_A_curr = DATA_A[next_idx]
        ret_A = (price_A_curr - price_A_prev) / price_A_prev
        
        price_B_prev = DATA_B[current_idx]
        price_B_curr = DATA_B[next_idx]
        ret_B = (price_B_curr - price_B_prev) / price_B_prev
        
        # Obliczamy wynik gracza
        user_ret = 0.0
        if choice == 'A': user_ret = ret_A
        elif choice == 'B': user_ret = ret_B
        
        if leverage_active:
            user_ret = user_ret * 2
            
        new_cap = current_cap * (1 + user_ret)
        
        # Aktualizacja stanu
        st.session_state.g1_history_user.append(new_cap)
        st.session_state.g1_round += 1
        
        # Aktualizacja historii indeksów (znormalizowanych) do wykresu
        # Normalizacja: (Cena / Cena_Startowa) * 10000
        norm_A = (DATA_A[next_idx] / st.session_state.start_A) * 10000
        norm_B = (DATA_B[next_idx] / st.session_state.start_B) * 10000
        
        st.session_state.g1_history_A.append(norm_A)
        st.session_state.g1_history_B.append(norm_B)
        st.session_state.g1_labels.append(LABELS[next_idx])
        
        # Zapis
        st.session_state.results['game1_history'].append({
            "round": next_idx, 
            "choice": choice, 
            "leverage": leverage_active, 
            "return": user_ret,
            "capital": new_cap
        })
        
        st.rerun()

# --- GRA 2: MONETA ---

def show_game2_intro():
    st.header("Część 2: Wyzwanie Monety")
    st.markdown("""
    <div class="instruction-card">
        <h3>Zasady:</h3>
        1. Masz <b>100 PLN</b>.
        2. Rzucasz wirtualną monetą (ok. 20 razy).
        3. Prawdopodobieństwa:
           <ul>
               <li>🦅 <b>ORZEŁ (60% szans):</b> Wygrywasz tyle, ile postawiłeś.</li>
               <li>📉 <b>RESZKA (40% szans):</b> Tracisz stawkę.</li>
           </ul>
        4. Decydujesz, jaki % kapitału stawiasz w każdym rzucie.
    </div>
    """, unsafe_allow_html=True)
    
    if 'g2_round' not in st.session_state:
        st.session_state.g2_round = 1
        st.session_state.g2_capital = 100.0
        st.session_state.g2_history_chart = [100.0]
        st.session_state.g2_table_data = []

    if st.button("Start gry z monetą"):
        next_page('game2')

def show_game2():
    st.subheader(f"Rzut Monetą: Runda {st.session_state.g2_round}")
    cap = st.session_state.g2_capital
    
    col_main, col_hist = st.columns([2, 1])
    
    with col_main:
        st.metric("Dostępne środki", f"{cap:.2f} PLN")
        st.line_chart(st.session_state.g2_history_chart)
        
        if cap < 1.0:
            st.error("Bankructwo! Nie masz środków na dalszą grę.")
            if st.button("Przejdź do ankiety"):
                next_page('survey')
            return

        bet_pct = st.slider("Jaki % kapitału stawiasz na ORŁA?", 0, 100, 10)
        bet_val = cap * (bet_pct / 100)
        st.info(f"Stawiasz: **{bet_val:.2f} PLN**")
        
        if st.button("RZUĆ MONETĄ"):
            is_win = random.random() < 0.6
            pnl = bet_val if is_win else -bet_val
            st.session_state.g2_capital += pnl
            
            result_str = "WYGRANA" if is_win else "PRZEGRANA"
            
            st.session_state.g2_history_chart.append(st.session_state.g2_capital)
            st.session_state.g2_table_data.insert(0, {
                "Runda": st.session_state.g2_round,
                "Stawka": f"{bet_pct}%",
                "Wynik": result_str,
                "Kapitał": f"{st.session_state.g2_capital:.2f}"
            })
            
            st.session_state.results['game2_history'].append({
                "round": st.session_state.g2_round,
                "bet_pct": bet_pct,
                "result": "WIN" if is_win else "LOSS",
                "capital_after": st.session_state.g2_capital
            })
            
            st.session_state.g2_round += 1
            if st.session_state.g2_round > 20:
                time.sleep(0.5)
                next_page('survey')
            else:
                st.rerun()

    with col_hist:
        st.write("### Historia")
        if st.session_state.g2_table_data:
            df_hist = pd.DataFrame(st.session_state.g2_table_data)
            st.dataframe(df_hist, height=400, hide_index=True)

# --- ANKIETA ---

def show_survey():
    st.header("Część 3: Scenariusze")
    with st.form("survey_form"):
        answers = {}
        for i, q_data in enumerate(st.session_state.shuffled_questions):
            st.markdown(f"**Sytuacja {i+1}**")
            st.write(q_data['q'])
            answers[q_data['id']] = st.radio("Decyzja:", q_data['opts'], key=q_data['id'], index=None)
            st.markdown("---")
        
        if st.form_submit_button("Zakończ badanie"):
            if any(v is None for v in answers.values()):
                st.warning("Proszę odpowiedzieć na wszystkie pytania.")
            else:
                st.session_state.results['survey_answers'] = answers
                next_page('finish')

def show_finish():
    st.success("Badanie zakończone! Dziękujemy.")
    
    final_data = {
        "user_id": st.session_state.user_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **st.session_state.results['demographics'],
        "g1_final": st.session_state.g1_history_user[-1],
        "g2_final": st.session_state.g2_capital,
        **st.session_state.results['survey_answers']
    }
    
    if 'saved' not in st.session_state:
        save_to_google_sheets(final_data)
        st.session_state.saved = True
        st.balloons()

# --- ROUTER ---
if st.session_state.page == 'intro': show_intro()
elif st.session_state.page == 'demographics': show_demographics()
elif st.session_state.page == 'game1_intro': show_game1_intro()
elif st.session_state.page == 'game1': show_game1()
elif st.session_state.page == 'game2_intro': show_game2_intro()
elif st.session_state.page == 'game2': show_game2()
elif st.session_state.page == 'survey': show_survey()
elif st.session_state.page == 'finish': show_finish()