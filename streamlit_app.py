import streamlit as st
import streamlit.components.v1 as components
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

# --- STYLE CSS (High Finance Vibe) ---
st.markdown("""
    <style>
    /* Przycisk */
    .stButton>button { width: 100%; height: 3em; font-weight: bold; }
    
    /* Nowoczesny, "finansowy" box z instrukcją */
    .instruction-card {
        background-color: #f8f9fa;
        border-left: 6px solid #003366; /* Deep Navy Blue */
        padding: 20px;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        color: #2c3e50;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    .instruction-card h3 {
        margin-top: 0;
        color: #003366; /* Deep Navy Blue */
        font-weight: 700;
        text-transform: uppercase;
        font-size: 1rem;
        letter-spacing: 1px;
    }
    .instruction-card ul {
        padding-left: 20px;
        line-height: 1.6;
    }
    .instruction-card li {
        margin-bottom: 10px;
    }
    .important-text {
        color: #003366;
        font-weight: 800;
        font-size: 1.1em;
        text-decoration: underline;
    }
    
    /* Legenda skali Likerta */
    .likert-legend {
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 0.9rem;
        border: 1px solid #90caf9;
    }
    
    /* Ukrycie menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- DANE GIEŁDOWE (WERSJA TRUDNA) ---
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
LABELS_TEXT = [
    "wrz 22", "paź 22", "lis 22", "gru 22", "sty 23", "lut 23", "mar 23", "kwi 23", "maj 23", "cze 23",
    "lip 23", "sie 23", "wrz 23", "paź 23", "lis 23", "gru 23", "sty 24", "lut 24", "mar 24", "kwi 24",
    "maj 24", "cze 24", "lip 24", "sie 24", "wrz 24", "paź 24", "lis 24", "gru 24", "sty 25", "lut 25",
    "mar 25", "kwi 25", "maj 25", "cze 25", "lip 25", "sie 25", "wrz 25", "paź 25", "lis 25", "gru 25"
]

def get_real_dates():
    dates = []
    y = 2022
    m = 9
    for _ in range(40):
        dates.append(datetime(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return dates

REAL_DATES = get_real_dates()

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
        'g2_pre_survey': {}, 
        'survey_answers': {}
    }
if 'survey_page_num' not in st.session_state:
    st.session_state.survey_page_num = 1

# --- NOWE PYTANIA ANKIETOWE (SKALA 1-5) ---
FIXED_QUESTIONS = [
    {
        "id": "Q01_HomeBias_Competence",
        "q": "1. \"Inwestowanie w sektory, które doskonale rozumiem dzięki mojej pracy zawodowej (np. lekarz inwestujący w spółki z branży medycznej), pozwala mi zminimalizować ryzyko pomyłki lepiej niż dywersyfikacja.\""
    },
    {
        "id": "Q02_Disposition_Gain",
        "q": "2. \"Dla bezpieczeństwa portfela ważniejsze jest dla mnie regularne realizowanie zysków, gdy akcje wzrosną, niż trzymanie ich w nadziei na dalsze, niepewne rekordy.\""
    },
    {
        "id": "Q03_Disposition_Loss",
        "q": "3. \"Jeśli jestem przekonany o wartości spółki, a jej kurs spada poniżej ceny, za którą ją kupiłem, zazwyczaj czekam ze sprzedażą, aż cena wróci do poziomu wyjściowego, by nie tracić kapitału.\""
    },
    {
        "id": "Q04_OutcomeBias",
        "q": "4. \"Skuteczność doradcy lub zarządzającego funduszem najlepiej oceniać po jego wyniku z ostatniego roku – liczby są najbardziej obiektywnym dowodem umiejętności.\""
    },
    {
        "id": "Q05_Recency_Trend",
        "q": "5. \"Szukając funduszu inwestycyjnego, najbezpieczniej jest wybierać te, które w ostatnich 12-24 miesiącach radziły sobie lepiej niż średnia rynkowa.\""
    },
    {
        "id": "Q06_Confirmation",
        "q": "6. \"Gdy posiadam akcje spółki, którą dokładnie przeanalizowałem, traktuję większość negatywnych newsów jako szum informacyjny, który nie powinien wpływać na moją długoterminową wizję.\""
    },
    {
        "id": "Q07_Hindsight",
        "q": "7. \"Analizując historię krachów giełdowych, uważam, że większość z nich była poprzedzona logicznymi sygnałami ekonomicznymi, które były możliwe do zauważenia przed faktem.\""
    },
    {
        "id": "Q08_SafetyFirst",
        "q": "8. \"Mając do wyboru dwie inwestycje o podobnej średniej stopie zwrotu, zazwyczaj wybieram tę, która oferuje niższy maksymalny zysk, ale daje gwarancję ochrony wpłaconego kapitału.\""
    },
    {
        "id": "Q09_Authority",
        "q": "9. \"W skomplikowanym świecie finansów racjonalne jest oparcie swoich decyzji na rekomendacjach znanych autorytetów giełdowych, którzy mają szerszy dostęp do danych.\""
    },
    {
        "id": "Q10_Herding",
        "q": "10. \"Jeśli znaczna część rynku i mediów finansowych zwraca się ku nowej klasie aktywów (np. AI, surowce), zazwyczaj oznacza to trwały trend, którego nie warto ignorować.\""
    },
    {
        "id": "Q11_MentalAccounting",
        "q": "11. \"Uważam, że środki otrzymane niespodziewanie (np. wysoka premia, nagroda) można zainwestować w aktywa o wyższym profilu ryzyka niż te, w które inwestuję moje comiesięczne oszczędności.\""
    },
    {
        "id": "Q12_HomeBias_Geo",
        "q": "12. \"Czuję się bardziej komfortowo, inwestując w spółki z mojego kraju, ponieważ łatwiej jest mi monitorować ich działalność i otoczenie prawne.\""
    }
]

# --- FUNKCJE ---

def next_page(page_name):
    st.session_state.page = page_name
    st.rerun()

def scroll_to_top():
    # POPRAWKA: Dodanie losowego klucza (key) oraz setTimeout wymusza 
    # ponowne wykonanie skryptu przy każdym odświeżeniu strony.
    js = """
    <script>
        setTimeout(function() {
            var body = window.parent.document.querySelector(".main");
            var appView = window.parent.document.querySelector(".stApp");
            if (body) { body.scrollTop = 0; }
            if (appView) { appView.scrollTop = 0; }
            window.scrollTo(0, 0);
        }, 50);
    </script>
    """
    # Key=uuid sprawia, że komponent jest unikalny przy każdym wywołaniu,
    # co zapobiega cache'owaniu przez Streamlit i wymusza wykonanie JS.
    components.html(js, height=0, key=str(uuid.uuid4()))

# --- ZAAWANSOWANE ZBIERANIE DANYCH (WIELOWYMIAROWE + HEADERy) ---

def save_data_multi_sheet(data_package):
    """
    Zapisuje dane do trzech oddzielnych arkuszy/plików.
    Dodaje czytelne nagłówki kolumn.
    Zabezpieczona przed brakiem pliku secrets.toml.
    """
    
    # --- DEFINICJA NAZW KOLUMN (NAGŁÓWKI) ---
    # ZMIANA: Mamy teraz 12 pytań Likerta
    q_headers = [f"Pytanie_{i+1:02d}" for i in range(12)]
    
    HEADERS_MAIN = [
        "User_ID", "Data_Badania", 
        "Wiek", "Plec", "Wyksztalcenie", "Branza_Fin", "Dosw_Inv", "Real_Inv", "Ryzyko",
        "Pre_G2_Zwrot", "Pre_G2_Prawdo_Straty", "Pre_G2_Ryzyko_Bankructwa",
        "G1_Kapital_Koncowy", "G2_Kapital_Koncowy"
    ] + q_headers

    HEADERS_G1 = [
        "User_ID", "Runda", 
        "Zwrot_S&P500", "Kierunek_S&P", "Zwrot_Nasdaq", "Kierunek_Nasdaq",
        "Decyzja_Gracza", "Lewar_Aktywny", "Zmiana_Strategii",
        "Zwrot_Gracza", "Zysk_Strata_PLN", "Czy_Zysk", "Kapital_Po_Rundzie"
    ]

    HEADERS_G2 = [
        "User_ID", "Runda", "Kapital_Przed",
        "Wybor_Strony", "Stawka", "Bet_Ratio_%", "Odchylenie_Kelly", 
        "Martingale_Flag", "Zmiana_Strony",
        "Wynik_Rzutu", "Czy_Wygrana", "Kapital_Po_Rundzie"
    ]

    # Mapowanie kluczy
    HEADERS_MAP = {
        "main": HEADERS_MAIN,
        "g1": HEADERS_G1,
        "g2": HEADERS_G2
    }

    # Nazwy arkuszy w GSheets
    SHEET_NAMES = {
        "main": "Uczestnicy_Ankieta",
        "g1": "G1_Gielda_Szczegoly",
        "g2": "G2_Moneta_Szczegoly"
    }

    # --- ZAPIS DO GOOGLE SHEETS (ZABEZPIECZONY) ---
    try:
        can_use_gsheets = False
        try:
             if HAS_GSPREAD and 'gcp_service_account' in st.secrets:
                 can_use_gsheets = True
        except Exception:
             pass

        if can_use_gsheets:
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
                
                for key, rows in data_package.items():
                    if not rows: continue
                    try:
                        ws = sh.worksheet(SHEET_NAMES[key])
                        if not ws.get_all_values():
                            ws.append_row(HEADERS_MAP[key])
                        ws.append_rows(rows)
                    except Exception as inner_e:
                        st.warning(f"Nie znaleziono arkusza {SHEET_NAMES[key]}, pomijam. ({inner_e})")
                return True # Sukces Google Sheets
            except Exception as e:
                st.error(f"Błąd GSheets API: {e}")
                pass # Błąd API - lecimy dalej do zapisu lokalnego
    except Exception:
        pass

    # --- ZAPIS LOKALNY DO CSV (FALLBACK) ---
    try:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        for key, rows in data_package.items():
            if not rows: continue
            
            df = pd.DataFrame(rows, columns=HEADERS_MAP[key])
            filename = f"wyniki_{key}_{timestamp_str}.csv"
            
            df.to_csv(filename, index=False, header=True, encoding='utf-8-sig')
            
        return True
    except Exception as e:
        st.error(f"Błąd zapisu lokalnego: {e}")
        return False

def show_finish():
    st.success("Badanie zakończone! Trwa przetwarzanie i zapisywanie metryk...")
    
    uid = st.session_state.user_id
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    demo = st.session_state.results['demographics']
    
    # Pobranie odpowiedzi z nowej ankiety przed grą 2
    pre_g2 = st.session_state.results.get('g2_pre_survey', {})

    # --- 1. PRZYGOTOWANIE ARKUSZA GŁÓWNEGO (UCZESTNICY + ANKIETA) ---
    survey_flat = []
    # Sortowanie po ID pytania (Q01, Q02...), aby kolumny się zgadzały
    sorted_q_ids = sorted(st.session_state.results['survey_answers'].keys())
    
    for q_id in sorted_q_ids:
        raw_ans = st.session_state.results['survey_answers'][q_id]
        # ZMIANA: raw_ans to teraz liczba (int) ze suwaka, nie trzeba splitować
        survey_flat.append(raw_ans)

    main_row = [
        uid, ts,
        demo.get('age'), demo.get('gender'), demo.get('education'), 
        demo.get('finance_related'), demo.get('inv_experience'), 
        demo.get('real_investing'), demo.get('risk_tolerance'),
        pre_g2.get('return_expect'), pre_g2.get('loss_prob'), pre_g2.get('ruin_prob'),
        st.session_state.g1_history_user[-1], # Wynik G1
        st.session_state.g2_capital           # Wynik G2
    ] + survey_flat
    
    # --- 2. PRZYGOTOWANIE ARKUSZA G1 (GIEŁDA) ---
    g1_rows = []
    g1_hist = st.session_state.results['game1_history']
    prev_choice = None
    prev_cap = 10000.0
    
    for i, rec in enumerate(g1_hist):
        idx_curr = rec['round'] 
        idx_prev = idx_curr - 1
        
        val_a_curr = DATA_A[idx_curr] if idx_curr < len(DATA_A) else DATA_A[-1]
        val_a_prev = DATA_A[idx_prev] if idx_prev < len(DATA_A) else DATA_A[0]
        ret_a = (val_a_curr - val_a_prev) / val_a_prev
        
        val_b_curr = DATA_B[idx_curr] if idx_curr < len(DATA_B) else DATA_B[-1]
        val_b_prev = DATA_B[idx_prev] if idx_prev < len(DATA_B) else DATA_B[0]
        ret_b = (val_b_curr - val_b_prev) / val_b_prev

        choice = rec['choice']
        user_ret = rec['return']
        cap_curr = rec['capital']
        pnl = cap_curr - prev_cap
        
        # Features
        dir_a = 1 if ret_a >= 0 else -1
        dir_b = 1 if ret_b >= 0 else -1
        user_win = 1 if pnl > 0 else 0
        is_switch = 1 if (prev_choice is not None and choice != prev_choice) else 0
        lev_bin = 1 if rec['leverage'] else 0

        row = [
            uid, rec['round'],
            round(ret_a, 4), dir_a,
            round(ret_b, 4), dir_b,
            choice, lev_bin, is_switch,
            round(user_ret, 4), round(pnl, 2), user_win, round(cap_curr, 2)
        ]
        g1_rows.append(row)
        prev_cap = cap_curr
        prev_choice = choice

    # --- 3. PRZYGOTOWANIE ARKUSZA G2 (MONETA) ---
    g2_rows = []
    g2_hist = st.session_state.results['game2_history']
    cap_runner = 100.0
    prev_bet = 0.0
    prev_result_type = None
    prev_side = None

    for rec in g2_hist:
        bet = rec['bet_amount']
        choice = rec['choice']
        outcome = rec['coin_result']
        res_type = rec['result']
        cap_after = rec['capital_after']
        
        # Features
        ratio = (bet / cap_runner) if cap_runner > 0 else 0.0
        kelly_diff = ratio - 0.20
        
        is_martingale = 0
        if prev_result_type == 'LOSS' and prev_bet > 0:
            if bet >= (prev_bet * 2):
                is_martingale = 1
                
        side_switch = 1 if (prev_side is not None and choice != prev_side) else 0
        win_bin = 1 if res_type == 'WIN' else 0

        row = [
            uid, rec['round'], round(cap_runner, 2),
            choice, bet, round(ratio, 4), round(kelly_diff, 4),
            is_martingale, side_switch,
            outcome, win_bin, round(cap_after, 2)
        ]
        g2_rows.append(row)
        
        cap_runner = cap_after
        prev_bet = bet
        prev_result_type = res_type
        prev_side = choice

    # --- ZAPIS ---
    package = {
        "main": [main_row],
        "g1": g1_rows,
        "g2": g2_rows
    }
    
    if 'saved' not in st.session_state:
        success = save_data_multi_sheet(package)
        if success:
            st.session_state.saved = True
            st.balloons()
            st.markdown("### Dziękujemy!")
            st.markdown("Dane zostały pomyślnie zapisane.")
        else:
            st.error("Problem z zapisem danych.")

def pad_history(history_list, total_length):
    base = history_list[:total_length]
    padding = [None] * (total_length - len(base))
    return base + padding

def color_outcome(val):
    if isinstance(val, str):
        if "WYGRANA" in val:
            return 'color: #2e7d32; font-weight: bold'
        elif "PRZEGRANA" in val:
            return 'color: #c62828; font-weight: bold'
    return ''

# --- STRONY ---

def show_intro():
    st.title("Badanie Decyzji Finansowych")
    st.markdown(f"""
    Dzień dobry!
    Twój identyfikator: **{st.session_state.user_id}**.
    
    Badanie zajmie ok. 10 minut i składa się z 3 części:
    1. Gra Giełdowa (40 rund).
    2. Rzuty Monetą (zarządzanie stawką - 30 rund).
    3. Krótka Ankieta.
    """)
    if st.button("Rozpocznij badanie"):
        next_page('demographics')

def show_demographics():
    st.header("Metryczka")
    st.markdown("Proszę uzupełnić podstawowe informacje. **Wszystkie pola są wymagane.**")
    
    with st.form("demo"):
        # Pytanie 1: Wiek
        age = st.selectbox(
            "1. Ile masz lat?",
            ["poniżej 18", "18–24", "25–34", "35–44", "45–54", "55–64", "65 lub więcej"],
            index=None,
            placeholder="Wybierz..."
        )
        
        # Pytanie 2: Płeć
        gender = st.radio(
            "2. Jakiej jesteś płci?",
            ["Kobieta", "Mężczyzna", "Inna / nie chcę podawać"],
            index=None
        )
        
        # Pytanie 3: Wykształcenie
        edu = st.selectbox(
            "3. Najwyższy ukończony poziom wykształcenia:",
            ["Podstawowe", "Średnie", "Licencjat / inżynier", "Magister", "Doktorat lub wyżej"],
            index=None,
            placeholder="Wybierz..."
        )
        
        # Pytanie 4: Dziedzina
        field = st.radio(
            "4. Czy Twoje wykształcenie lub praca są związane z finansami, ekonomią lub rynkami kapitałowymi?",
            ["Tak", "Częściowo", "Nie"],
            index=None
        )
        
        # Pytanie 5: Doświadczenie inwestycyjne
        inv_exp = st.selectbox(
            "5. Jak oceniasz swoje doświadczenie w inwestowaniu?",
            ["Brak doświadczenia", "Początkujące", "Średnie", "Zaawansowane", "Profesjonalne"],
            index=None,
            placeholder="Wybierz..."
        )
        
        # Pytanie 6: Doświadczenie realne
        real_inv = st.radio(
            "6. Czy kiedykolwiek inwestowałeś/-aś realne pieniądze (np. akcje, ETF-y, kryptowaluty)?",
            ["Tak", "Nie"],
            index=None
        )
        
        # Pytanie 7: Ryzyko
        st.write("7. Jak oceniasz swoją skłonność do podejmowania ryzyka finansowego? (1-bardzo niska, 7-bardzo wysoka)")
        risk = st.slider("Poziom ryzyka", 1, 7, 4, label_visibility="collapsed")
        
        submitted = st.form_submit_button("Dalej")
        
        if submitted:
            # WALIDACJA
            required_fields = [age, gender, edu, field, inv_exp, real_inv]
            if any(f is None for f in required_fields):
                st.error("⚠️ Proszę odpowiedzieć na wszystkie pytania przed przejściem dalej.")
            else:
                st.session_state.results['demographics'] = {
                    "age": age,
                    "gender": gender,
                    "education": edu,
                    "finance_related": field,
                    "inv_experience": inv_exp,
                    "real_investing": real_inv,
                    "risk_tolerance": risk
                }
                next_page('game1_intro')

# --- GRA 1: GIEŁDA ---

def show_game1_intro():
    st.header("Część 1: Gra Inwestycyjna")
    st.markdown("# 📈 📉 💰")
    
    st.markdown("""
<div class="instruction-card">
    <h3>Instrukcja:</h3>
    Wcielasz się w rolę inwestora. Masz przed sobą <b>40 rund</b> (reprezentujących 40 miesięcy).
    <ul>
        <li>Na start otrzymujesz <b>10 000 PLN</b> wirtualnego kapitału.</li>
        <li>W każdej rundzie decydujesz, gdzie ulokować pieniądze:</li>
        <ul>
            <li><b>Indeks A:</b> S&P 500 </li>
            <li><b>Indeks B:</b> Nasdaq</li>
            <li><b>Gotówka:</b> Bezpieczna przystań (0% zysku).</li>
        </ul>
        <li class="important-text">Twoim celem jest maksymalizacja zysku.</li>
        <li>Od 20. rundy dostępny będzie <b>Lewar (x2)</b>.</li>
    </ul>
</div>
    """, unsafe_allow_html=True)
    
    if 'g1_round' not in st.session_state:
        st.session_state.g1_round = 0
        st.session_state.g1_capital = 10000.0
        st.session_state.g1_history_user = [10000.0]
        st.session_state.start_A = DATA_A[0]
        st.session_state.start_B = DATA_B[0]
        st.session_state.g1_history_A = [10000.0]
        st.session_state.g1_history_B = [10000.0]

    if st.button("Rozumiem, gramy!"):
        next_page('game1')

def show_game1():
    current_idx = st.session_state.g1_round
    total_len = 40
    
    if current_idx >= 39: 
        next_page('game1_summary')
        return

    current_cap = st.session_state.g1_history_user[-1]
    prev_cap = st.session_state.g1_history_user[-2] if len(st.session_state.g1_history_user) > 1 else 10000.0
    pct_change_show = ((current_cap - prev_cap) / prev_cap) * 100
    
    st.subheader(f"Runda {current_idx + 1} / {total_len} ({LABELS_TEXT[current_idx]})")
    
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Twój Kapitał", f"{current_cap:.2f} PLN", f"{pct_change_show:.2f}%")
    
    chart_data = pd.DataFrame({
        "S&P 500": pad_history(st.session_state.g1_history_A, total_len),
        "Nasdaq": pad_history(st.session_state.g1_history_B, total_len),
        "Twój Kapitał (🔴)": pad_history(st.session_state.g1_history_user, total_len)
    })
    
    st.line_chart(chart_data.iloc[:total_len], color=["#AAAAAA", "#4444FF", "#FF0000"])
    
    leverage_active = False
    if current_idx >= 20:
        st.warning("⚡ ODBLOKOWANO DŹWIGNIĘ (LEWAR x2)")
        leverage_active = st.checkbox("Użyj dźwigni (x2 zyski/straty)")

    st.write("W co inwestujesz na kolejny miesiąc?")
    col1, col2, col3 = st.columns(3)
    choice = None
    if col1.button("Indeks A (S&P 500)"): choice = 'A'
    if col2.button("Indeks B (Nasdaq)"): choice = 'B'
    if col3.button("Gotówka"): choice = 'Cash'

    if choice:
        next_idx = current_idx + 1
        
        price_A_prev = DATA_A[current_idx]
        price_A_curr = DATA_A[next_idx]
        ret_A = (price_A_curr - price_A_prev) / price_A_prev
        
        price_B_prev = DATA_B[current_idx]
        price_B_curr = DATA_B[next_idx]
        ret_B = (price_B_curr - price_B_prev) / price_B_prev
        
        user_ret = 0.0
        if choice == 'A': user_ret = ret_A
        elif choice == 'B': user_ret = ret_B
        
        if leverage_active:
            user_ret = user_ret * 2
            
        new_cap = current_cap * (1 + user_ret)
        
        st.session_state.g1_history_user.append(new_cap)
        st.session_state.g1_round += 1
        
        norm_A = (DATA_A[next_idx] / st.session_state.start_A) * 10000
        norm_B = (DATA_B[next_idx] / st.session_state.start_B) * 10000
        
        st.session_state.g1_history_A.append(norm_A)
        st.session_state.g1_history_B.append(norm_B)
        
        st.session_state.results['game1_history'].append({
            "round": next_idx,
            "choice": choice,
            "leverage": leverage_active,
            "return": user_ret,
            "capital": new_cap
        })
        st.rerun()

def show_game1_summary():
    st.header("Podsumowanie Gry Giełdowej")
    st.markdown("Gratulacje, ukończyłeś pierwszą część badania! Oto Twoje wyniki na tle rynku.")

    start_cap = 10000.0
    end_cap = st.session_state.g1_history_user[-1]
    user_ret_pct = ((end_cap - start_cap) / start_cap) * 100

    start_A_val = DATA_A[0]
    end_A_val = DATA_A[-1]
    idx_a_ret_pct = ((end_A_val - start_A_val) / start_A_val) * 100
    idx_a_cap = 10000.0 * (end_A_val / start_A_val)

    start_B_val = DATA_B[0]
    end_B_val = DATA_B[-1]
    idx_b_ret_pct = ((end_B_val - start_B_val) / start_B_val) * 100
    idx_b_cap = 10000.0 * (end_B_val / start_B_val)

    c1, c2, c3 = st.columns(3)
    c1.metric("Twój Wynik", f"{end_cap:.2f} PLN", f"{user_ret_pct:.2f}%")
    c2.metric("S&P 500 (Pasywnie)", f"{idx_a_cap:.2f} PLN", f"{idx_a_ret_pct:.2f}%")
    c3.metric("Nasdaq (Pasywnie)", f"{idx_b_cap:.2f} PLN", f"{idx_b_ret_pct:.2f}%")

    st.markdown("---")
    st.write("**Wykres porównawczy:**")
    
    chart_data = pd.DataFrame({
        "S&P 500": pad_history(st.session_state.g1_history_A, 40),
        "Nasdaq": pad_history(st.session_state.g1_history_B, 40),
        "Twój Kapitał (🔴)": pad_history(st.session_state.g1_history_user, 40)
    })
    st.line_chart(chart_data, color=["#AAAAAA", "#4444FF", "#FF0000"])

    st.markdown("Gdy będziesz gotowy, przejdź do drugiej części badania.")
    
    if st.button("Dalej: Część 2 (Moneta)"):
        next_page('game2_intro')

# --- GRA 2: MONETA ---

def show_game2_intro():
    st.header("Część 2: Zakład o rzut monetą")
    
    st.markdown("""
<div class="instruction-card">
    <h3>Zasady:</h3>
    <ul>
        <li>💰 <b>Start:</b> Otrzymujesz na start <b>100 PLN</b>.</li>
        <li>🎲 <b>Długość:</b> Czeka Cię <b>30 rzutów</b> wirtualną monetą.</li>
        <li>📊 <b>Prawdopodobieństwa (stałe):</b>
            <ul>
                <li>🦅 <b>ORZEŁ:</b> 60% szans (Wygrana)</li>
                <li>📉 <b>RESZKA:</b> 40% szans (Wygrana)</li>
            </ul>
        </li>
        <li>⚙️ <b>Twoja decyzja w każdej rundzie:</b>
            <ul>
                <li>Na co stawiasz (Orzeł czy Reszka).</li>
                <li>Jaki % kapitału stawiasz (suwakiem).</li>
            </ul>
        </li>
    </ul>
</div>
    """, unsafe_allow_html=True)
    
    if 'g2_round' not in st.session_state:
        st.session_state.g2_round = 1
        st.session_state.g2_capital = 100.0
        st.session_state.g2_history_chart = [100.0]
        st.session_state.g2_table_data = []

    if st.button("Start gry z monetą"):
        next_page('game2_questions')

def show_game2_questions():
    st.header("Twoje przewidywania")
    st.markdown("Zanim zaczniesz grę, odpowiedz proszę na 3 pytania dotyczące Twoich oczekiwań.")

    with st.form("pre_game2_survey"):
        
        st.markdown("**Pytanie 1 — oczekiwana stopa zwrotu**")
        st.markdown("Jakiej łącznej stopy zwrotu spodziewasz się po 30 rundach?")
        q1 = st.radio(
            "Wybierz jedną opcję:",
            [
                "strata większa niż −50%",
                "od −50% do −20%",
                "od −20% do 0%",
                "od 0% do +20%",
                "od +20% do +50%",
                "powyżej +50%"
            ],
            index=None
        )
        st.markdown("---")

        st.markdown("**Pytanie 2 — prawdopodobieństwo straty**")
        st.markdown("Jakie jest prawdopodobieństwo, że po 30 rundach Twój kapitał będzie niższy niż 100 zł?")
        q2 = st.radio(
            "Wybierz zakres:",
            [
                "0–10%",
                "11–25%",
                "26–50%",
                "51–75%",
                "76–100%"
            ],
            index=None
        )
        st.markdown("---")

        st.markdown("**Pytanie 3 — ryzyko dużej straty / bankructwa**")
        st.markdown("Jakie jest prawdopodobieństwo, że w trakcie gry stracisz większość kapitału (co najmniej 80%)?")
        q3 = st.radio(
            "Wybierz zakres:",
            [
                "0–5%",
                "6–15%",
                "16–30%",
                "31–50%",
                "powyżej 50%"
            ],
            index=None
        )
        st.markdown("---")

        submitted = st.form_submit_button("Zapisz odpowiedzi i przejdź do gry")

        if submitted:
            if not all([q1, q2, q3]):
                st.error("⚠️ Proszę odpowiedzieć na wszystkie 3 pytania.")
            else:
                st.session_state.results['g2_pre_survey'] = {
                    "return_expect": q1,
                    "loss_prob": q2,
                    "ruin_prob": q3
                }
                next_page('game2')

def show_game2():
    if st.session_state.g2_round > 30:
        next_page('survey')
        return

    st.subheader(f"Rzut Monetą: Runda {st.session_state.g2_round} / 30")
    cap = st.session_state.g2_capital
    
    col_main, col_hist = st.columns([1, 1])
    
    with col_main:
        st.metric("Twoje środki", f"{cap:.2f} PLN")
        
        if cap <= 0.01:
            st.error("Bankructwo! Nie masz środków na dalszą grę.")
            if st.button("Przejdź do ankiety"):
                next_page('survey')
            return

        st.markdown("---")
        
        st.write("Decyzja o stawce:")
        c_slider, c_val = st.columns([3, 2])
        
        with c_slider:
            bet_pct = st.slider(
                "Jaki % kapitału stawiasz?", 
                min_value=0, 
                max_value=100, 
                value=10, 
                step=1
            )
        
        bet_amount = round(cap * (bet_pct / 100.0), 2)

        with c_val:
            st.metric("Wartość zakładu", f"{bet_amount:.2f}")

        bet_side = st.radio("Obstawiam:", ["ORZEŁ", "RESZKA"], horizontal=True)
        
        st.markdown("---")

        if st.button("RZUĆ MONETĄ", type="primary"):
            is_heads = random.random() < 0.6
            coin_result = "ORZEŁ" if is_heads else "RESZKA"
            
            user_chose_heads = "ORZEŁ" in bet_side
            
            if (user_chose_heads and is_heads) or (not user_chose_heads and not is_heads):
                win = True
                pnl = bet_amount
                result_label = f"WYGRANA ({coin_result})"
                st.success(f"Wypadł {coin_result}! Wygrywasz {bet_amount:.2f} PLN.")
            else:
                win = False
                pnl = -bet_amount
                result_label = f"PRZEGRANA ({coin_result})"
                st.error(f"Wypadł {coin_result}. Tracisz {bet_amount:.2f} PLN.")

            st.session_state.g2_capital += pnl
            st.session_state.g2_history_chart.append(st.session_state.g2_capital)
            
            st.session_state.g2_table_data.insert(0, {
                "Runda": st.session_state.g2_round,
                "Twój Wybór": "ORZEŁ" if user_chose_heads else "RESZKA",
                "Rezultat": result_label,
                "Stawka": f"{bet_amount:.2f} PLN",
                "% Kapitału": f"{bet_pct}%"
            })
            
            st.session_state.results['game2_history'].append({
                "round": st.session_state.g2_round,
                "bet_amount": bet_amount,
                "choice": "HEADS" if user_chose_heads else "TAILS",
                "coin_result": "HEADS" if is_heads else "TAILS",
                "result": "WIN" if win else "LOSS",
                "capital_after": st.session_state.g2_capital
            })
            
            st.session_state.g2_round += 1
            
            if st.session_state.g2_round > 30:
                time.sleep(1.5)
                next_page('survey')
            else:
                time.sleep(1.0)
                st.rerun()
        
        st.line_chart(st.session_state.g2_history_chart)

    with col_hist:
        st.write("### Historia Gier")
        if st.session_state.g2_table_data:
            df_hist = pd.DataFrame(st.session_state.g2_table_data)
            st.dataframe(
                df_hist.style.map(color_outcome, subset=['Rezultat']),
                height=500,
                width="stretch",
                hide_index=True
            )

# --- ANKIETA (ZMIENIONA: SKALA LIKERTA) ---

# --- SŁOWNIK DO MAPOWANIA ODPOWIEDZI NA LICZBY ---
LIKERT_MAP = {
    "1 – Zdecydowanie się nie zgadzam": 1,
    "2 – Raczej się nie zgadzam": 2,
    "3 – Trudno powiedzieć / Neutralnie": 3,
    "4 – Raczej się zgadzam": 4,
    "5 – Zdecydowanie się zgadzam": 5
}
# Lista opcji do wyświetlenia na suwaku
LIKERT_OPTIONS = list(LIKERT_MAP.keys())


def show_survey():
    # --- NOWE: Przewiń do góry przy każdym załadowaniu tej funkcji ---
    scroll_to_top()
    # -----------------------------------------------------------------

    st.header("Część 3: Opinie")
    
    # --- CSS WYMUSZAJĄCY CZARNĄ CZCIONKĘ ---
    st.markdown("""
    <style>
    .survey-question {
        color: #ffffff !important; /* Wymuszona czerń dla pytań */
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 10px;
    }
    .likert-legend {
        background-color: #ffffff; /* Białe tło */
        color: #000000;            /* Czarny tekst */
        padding: 15px;
        border: 1px solid #cccccc;
        border-radius: 8px;
        margin-bottom: 25px;
        font-size: 0.9rem;
    }
    /* Poprawka widoczności etykiet suwaka */
    .stSlider [data-baseweb="slider"] div[data-testid="stMarkdownContainer"] p {
        font-weight: bold;
        color: #000000 !important; /* Wymuszenie czerni na etykietach suwaka */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("Proszę określić, w jakim stopniu zgadzasz się z poniższymi stwierdzeniami.")

    # Legenda
    st.markdown("""
    <div class="likert-legend">
        <b>Skala:</b> Przesuwaj suwak, aby wybrać odpowiednie stwierdzenie.<br>
        Od <b>1 (Nie zgadzam się)</b> do <b>5 (Zgadzam się)</b>.
    </div>
    """, unsafe_allow_html=True)
    
    page_num = st.session_state.survey_page_num
    
    # Dzielimy 12 pytań na 2 strony po 6
    QUESTIONS_PER_PAGE = 6
    start_idx = (page_num - 1) * QUESTIONS_PER_PAGE
    end_idx = start_idx + QUESTIONS_PER_PAGE
    
    current_questions = FIXED_QUESTIONS[start_idx:end_idx]
    
    # Pasek postępu
    if page_num == 1:
        st.progress(50)
        btn_label = "Dalej (Strona 2/2)"
    else:
        st.progress(100)
        btn_label = "Zakończ badanie"

    with st.form(f"survey_form_likert_{page_num}"):
        for q_data in current_questions:
            # Użycie HTML class="survey-question" dla czarnego koloru
            st.markdown(f'<div class="survey-question">{q_data["q"]}</div>', unsafe_allow_html=True)
            
            # SUWAK Z ETYKIETAMI SŁOWNYMI
            val_str = st.select_slider(
                "Twoja ocena:",
                options=LIKERT_OPTIONS,
                value="3 – Trudno powiedzieć / Neutralnie", # Domyślna wartość
                key=q_data['id'],
                label_visibility="collapsed"
            )
            st.markdown("---")
        
        submitted = st.form_submit_button(btn_label)
        
        if submitted:
            # Zbieramy odpowiedzi
            current_answers = {}
            for q in current_questions:
                selected_text = st.session_state[q['id']]
                numerical_val = LIKERT_MAP[selected_text]
                current_answers[q['id']] = numerical_val
            
            st.session_state.results['survey_answers'].update(current_answers)
            
            if page_num == 1:
                st.session_state.survey_page_num = 2
                st.rerun() # To przeładuje stronę, a scroll_to_top() na początku funkcji zadziała
            else:
                next_page('finish')

# --- ROUTER ---
if st.session_state.page == 'intro': show_intro()
elif st.session_state.page == 'demographics': show_demographics()
elif st.session_state.page == 'game1_intro': show_game1_intro()
elif st.session_state.page == 'game1': show_game1()
elif st.session_state.page == 'game1_summary': show_game1_summary()
elif st.session_state.page == 'game2_intro': show_game2_intro()
elif st.session_state.page == 'game2_questions': show_game2_questions()
elif st.session_state.page == 'game2': show_game2()
elif st.session_state.page == 'survey': show_survey()
elif st.session_state.page == 'finish': show_finish()