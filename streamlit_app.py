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
        'g2_pre_survey': {}, # NOWE POLE NA ODPOWIEDZI PRZED GRĄ 2
        'survey_answers': {}
    }
if 'survey_page_num' not in st.session_state:
    st.session_state.survey_page_num = 1

# --- PYTANIA ANKIETOWE (STAŁA KOLEJNOŚĆ) ---
FIXED_QUESTIONS = [
    {
        "id": "Q01_Overconfidence",
        "q": "Pytanie 1: Pracujesz w branży IT i budujesz portfel emerytalny na 30 lat. Twoja wiedza o technologii jest bardzo szeroka.",
        "opts": [
            "A: Inwestujesz 80% środków w spółki technologiczne, bo na tym się znasz i potrafisz ocenić ich produkty lepiej niż przeciętny inwestor.",
            "B: Dywersyfikujesz portfel o sektory, których nie znasz (banki, surowce), mimo że czujesz się w nich mniej pewnie."
        ]
    },
    {
        "id": "Q02_LossAversion_Loss",
        "q": "Pytanie 2: Kupiłeś akcje po 100 PLN, obecnie kosztują 70 PLN (-30%). Fundamenty branży pogarszają się przez nowe regulacje, a spółka tnie dywidendy.",
        "opts": [
            "A: Natychmiast zamykasz pozycję, by przenieść pozostały kapitał tam, gdzie ma on większy potencjał wzrostu.",
            "B: Trzymasz akcje. Czekasz na korektę wzrostową, by sprzedać je chociaż po 90 PLN i zminimalizować odczuwaną stratę."
        ]
    },
    {
        "id": "Q03_Recency",
        "q": "Pytanie 3: Masz do wyboru dwa fundusze akcyjne o identycznych opłatach:",
        "opts": [
            "A: Fundusz \"Lider Wzrostu\" – właśnie otrzymał nagrodę \"Fundusz Roku\", a w ostatnim kwartale zarobił spektakularne 15%.",
            "B: Fundusz \"Systematyczny\" – od 10 lat dowozi stabilne 7-8%, ale w tym roku nikt o nim nie pisze w mediach."
        ]
    },
    {
        "id": "Q04_Framing_Gain",
        "q": "Pytanie 4: Otrzymałeś spadek 100 000 PLN. Masz dwie opcje:",
        "opts": [
            "A: Bezpieczna obligacja, która gwarantuje Ci pewne 30 000 PLN zysku ponad inflację.",
            "B: Ryzykowny fundusz, w którym masz 30% szans na zysk 100 000 PLN i 70% szans na brak zysku."
        ]
    },
    {
        "id": "Q05_LossAversion_Gain",
        "q": "Pytanie 5: Kupiłeś akcje po 50 PLN, dziś kosztują 80 PLN (+60%). Analiza fundamentalna sugeruje, że są warte 100 PLN, ale czujesz niepokój, że rynek może spaść.",
        "opts": [
            "A: Sprzedajesz teraz, aby \"zaksięgować zysk\" i nie pozwolić mu uciec.",
            "B: Trzymasz pozycję zgodnie z analizą, pozwalając zyskom rosnąć do wyznaczonego celu."
        ]
    },
    {
        "id": "Q06_Confirmation",
        "q": "Pytanie 6: Spółka, którą lubisz, publikuje raport. Zysk jest dobry, ale zadłużenie niebezpiecznie wzrosło.",
        "opts": [
            "A: Skupiasz się na zyskach (\"Wiedziałem, że to dobra firma!\") i uznajesz dług za niezbędny koszt rozwoju.",
            "B: Analizujesz strukturę długu, dopuszczając myśl, że Twoja dotychczasowa pozytywna opinia o spółce może wymagać rewizji."
        ]
    },
    {
        "id": "Q07_Framing_Loss",
        "q": "Pytanie 7: Otrzymałeś wezwanie do zapłaty 100 000 PLN podatku. Możesz wybrać:",
        "opts": [
            "A: Godzisz się na ugodę i płacisz na pewno 70 000 PLN.",
            "B: Idziesz do sądu: masz 30% szans, że nie zapłacisz nic, i 70% szans, że zapłacisz pełne 100 000 PLN."
        ]
    },
    {
        "id": "Q08_Anchoring",
        "q": "Pytanie 8: Kupiłeś akcje po 200 PLN, spadły do 150 PLN. Dziś nagle odbiły do 198 PLN.",
        "opts": [
            "A: Sprzedajesz natychmiast, czując ulgę, że prawie nic nie straciłeś.",
            "B: Oceniasz spółkę po obecnej cenie (198 PLN), ignorując fakt, że kiedyś płaciłeś za nią 200 PLN."
        ]
    },
    {
        "id": "Q09_Hindsight",
        "q": "Pytanie 9: Patrzysz na wykres historyczny wielkiego krachu finansowego. Co myślisz?",
        "opts": [
            "A: \"To było oczywiste – wyceny były absurdalne, wskaźniki świeciły na czerwono, każdy mógł to przewidzieć\".",
            "B: \"Sytuacja wtedy była bardzo niejasna, a głosy o krachu mieszały się z bardzo silnymi argumentami za dalszymi wzrostami\"."
        ]
    },
    {
        "id": "Q10_Availability_Fear",
        "q": "Pytanie 10: Widzisz w mediach materiał o katastrofie budowlanej w Azji. Masz akcje solidnej firmy budowlanej z Europy, które lekko spadają przez ogólny sentyment.",
        "opts": [
            "A: Rozważasz sprzedaż, bo obraz katastrofy wywołuje w Tobie silny lęk przed ryzykiem w tej branży.",
            "B: Ignorujesz newsa jako nieistotny dla fundamentów Twojej europejskiej firmy."
        ]
    },
    {
        "id": "Q11_Confirmation_Search",
        "q": "Pytanie 11: Chcesz kupić Bitcoina. Jakich informacji szukasz w internecie?",
        "opts": [
            "A: Wpisujesz: \"Prognozy wzrostu Bitcoina 2025\" lub \"Dlaczego krypto to przyszłość\".",
            "B: Wpisujesz: \"Największe zagrożenia dla Bitcoina\" lub \"Dlaczego Bitcoin może spaść\"."
        ]
    },
    {
        "id": "Q12_OutcomeBias",
        "q": "Pytanie 12: Fundusz \"Alpha\" zarobił 40% w rok (rynek 5%). Wynik to efekt jednej, ekstremalnie ryzykownej transakcji (wszystko na jedną kartę). Zarządzający twierdzi, że \"miał nosa\".",
        "opts": [
            "A: Inwestujesz tam. Wynik 40% to namacalny dowód na skuteczność tego człowieka.",
            "B: Rezygnujesz. Uważasz, że wynik to efekt szczęścia, a proces decyzyjny jest zbyt ryzykowny."
        ]
    },
    {
        "id": "Q13_Confirmation_Auth",
        "q": "Pytanie 13: Twój ulubiony analityk mówi \"Kupuj X\". Inny, nieznany Ci analityk, publikuje raport \"Sprzedaj X\", wytykając błędy w księgowości firmy.",
        "opts": [
            "A: Ignorujesz raport \"Sprzedaj\", bo ten drugi analityk pewnie chce manipulować kursem lub się myli.",
            "B: Czytasz raport \"Sprzedaj\" z dużą uwagą, szukając dziur w argumentacji swojego ulubionego analityka."
        ]
    },
    {
        "id": "Q14_Hindsight_Bubble",
        "q": "Pytanie 14: Pamiętasz okres szalonych wzrostów na spółkach technologicznych przed ich spadkiem. Jak oceniasz swoje ówczesne nastawienie?",
        "opts": [
            "A: \"Od początku czułem, że to bańka i tylko czekałem na krach, to było logiczne\".",
            "B: \"W tamtym czasie czułem dużą niepewność i przyznaję, że argumenty za wzrostami też wydawały mi się wtedy sensowne\"."
        ]
    }
]

# --- FUNKCJE ---

def next_page(page_name):
    st.session_state.page = page_name
    st.rerun()

# --- ZAAWANSOWANE ZBIERANIE DANYCH (WIELOWYMIAROWE + HEADERy) ---

def save_data_multi_sheet(data_package):
    """
    Zapisuje dane do trzech oddzielnych arkuszy/plików.
    Dodaje czytelne nagłówki kolumn.
    """
    
    # --- DEFINICJA NAZW KOLUMN (NAGŁÓWKI) ---
    q_headers = [f"Pytanie_{i+1:02d}" for i in range(14)]
    
    # ZAKTUALIZOWANE NAGŁÓWKI DLA GŁÓWNEGO ARKUSZA (dodano 3 nowe kolumny)
    HEADERS_MAIN = [
        "User_ID", "Data_Badania", 
        "Wiek", "Plec", "Wyksztalcenie", "Branza_Fin", "Dosw_Inv", "Real_Inv", "Ryzyko",
        "Pre_G2_Zwrot", "Pre_G2_Prawdo_Straty", "Pre_G2_Ryzyko_Bankructwa",  # <-- NOWE KOLUMNY
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

    # ZAPIS DO GOOGLE SHEETS
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
            
            for key, rows in data_package.items():
                if not rows: continue
                try:
                    ws = sh.worksheet(SHEET_NAMES[key])
                    # Jeśli arkusz pusty, dodaj nagłówek
                    if not ws.get_all_values():
                        ws.append_row(HEADERS_MAP[key])
                    ws.append_rows(rows)
                except Exception as inner_e:
                    st.warning(f"Nie znaleziono arkusza {SHEET_NAMES[key]}, pomijam. ({inner_e})")
            return True
        except Exception as e:
            st.error(f"Błąd GSheets API: {e}")
            pass # Fallback do lokalnego

    # ZAPIS LOKALNY DO CSV (z nagłówkami)
    try:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        for key, rows in data_package.items():
            if not rows: continue
            
            df = pd.DataFrame(rows, columns=HEADERS_MAP[key])
            filename = f"wyniki_{key}_{timestamp_str}.csv"
            
            # Zawsze zapisujemy z nagłówkiem (nowy plik dla każdego usera)
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
    sorted_q_ids = sorted(st.session_state.results['survey_answers'].keys())
    for q_id in sorted_q_ids:
        raw_ans = st.session_state.results['survey_answers'][q_id]
        ans_letter = raw_ans.split(":")[0] if ":" in raw_ans else raw_ans
        survey_flat.append(ans_letter)

    main_row = [
        uid, ts,
        demo.get('age'), demo.get('gender'), demo.get('education'), 
        demo.get('finance_related'), demo.get('inv_experience'), 
        demo.get('real_investing'), demo.get('risk_tolerance'),
        # Dodanie nowych pól do zapisu:
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
    1. Gra Giełdowa (30 rund).
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
        risk = st.slider("", 1, 7, 4)
        
        submitted = st.form_submit_button("Dalej")
        
        if submitted:
            # WALIDACJA: Czy wszystko (poza suwakiem) jest wypełnione?
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
    Wcielasz się w rolę inwestora. Masz przed sobą <b>30 rund</b> (reprezentujących 30 miesięcy).
    <ul>
        <li>Na start otrzymujesz <b>10 000 PLN</b> wirtualnego kapitału.</li>
        <li>W każdej rundzie decydujesz, gdzie ulokować pieniądze:</li>
        <ul>
            <li><b>Indeks A:</b> S&P 500 </li>
            <li><b>Indeks B:</b> Nasdaq</li>
            <li><b>Gotówka:</b> Bezpieczna przystań (0% zysku).</li>
        </ul>
        <li class="important-text">Twoim celem jest maksymalizacja zysku.</li>
        <li>Od 15. rundy dostępny będzie <b>Lewar (x2)</b>.</li>
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
    # ZMIANA: Skrócenie gry do 30 rund
    total_len = 30
    
    if current_idx >= 29: # Koniec po 30 rundach (indeksy 0-29)
        next_page('game2_intro')
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
    
    # Wykres wyświetlamy z odpowiednią osią X (do 30 okresów)
    st.line_chart(chart_data.iloc[:total_len], color=["#AAAAAA", "#4444FF", "#FF0000"])
    
    leverage_active = False
    # ZMIANA: Lewar dostępny od 15 rundy (połowa)
    if current_idx >= 15:
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
        # ZMIANA: PRZEKIEROWANIE DO NOWEJ STRONY Z PYTANIAMI
        next_page('game2_questions')

# --- NOWA STRONA: PYTANIA PRZED GRĄ 2 ---
def show_game2_questions():
    st.header("Twoje przewidywania")
    st.markdown("Zanim zaczniesz grę, odpowiedz proszę na 3 pytania dotyczące Twoich oczekiwań.")

    with st.form("pre_game2_survey"):
        
        # Pytanie 1
        st.markdown("**Pytanie 1 — oczekiwana stopa zwrotu (overconfidence, neglect of compounding)**")
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

        # Pytanie 2
        st.markdown("**Pytanie 2 — prawdopodobieństwo straty (miscalibration, optimism bias)**")
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

        # Pytanie 3
        st.markdown("**Pytanie 3 — ryzyko dużej straty / bankructwa (fat-tail neglect, illusion of control)**")
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
                # Zapis odpowiedzi do stanu sesji
                st.session_state.results['g2_pre_survey'] = {
                    "return_expect": q1,
                    "loss_prob": q2,
                    "ruin_prob": q3
                }
                next_page('game2')

def show_game2():
    # --- GUARD CLAUSE ---
    # Jeśli runda > 30, przekieruj do ankiety
    if st.session_state.g2_round > 30:
        next_page('survey')
        return

    st.subheader(f"Rzut Monetą: Runda {st.session_state.g2_round} / 30")
    cap = st.session_state.g2_capital
    
    # Główny układ: Lewa strona (Sterowanie), Prawa strona (Tabela historii)
    col_main, col_hist = st.columns([1, 1])
    
    with col_main:
        # Wyświetlanie głównego kapitału
        st.metric("Twoje środki", f"{cap:.2f} PLN")
        
        # Sprawdzenie bankructwa
        if cap <= 0.01:
            st.error("Bankructwo! Nie masz środków na dalszą grę.")
            if st.button("Przejdź do ankiety"):
                next_page('survey')
            return

        st.markdown("---")
        
        # --- ZMIANA: SUWAK ZAMIAST WPISYWANIA KWOTY ---
        st.write("Decyzja o stawce:")
        
        # Dwie kolumny: Suwak (szeroki) i Przeliczona kwota (wąski)
        c_slider, c_val = st.columns([3, 2])
        
        with c_slider:
            bet_pct = st.slider(
                "Jaki % kapitału stawiasz?", 
                min_value=0, 
                max_value=100, 
                value=10, 
                step=1
            )
        
        # Obliczenie kwoty na podstawie suwaka
        bet_amount = cap * (bet_pct / 100.0)

        with c_val:
            # Wyświetlenie kwoty w ładnym formacie
            st.metric("Wartość zakładu", f"{bet_amount:.2f} PLN")

        # Wybór strony monety
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

            # Aktualizacja stanu
            st.session_state.g2_capital += pnl
            st.session_state.g2_history_chart.append(st.session_state.g2_capital)
            
            # Dodanie wpisu do tabeli (wyświetlanej w prawej kolumnie)
            st.session_state.g2_table_data.insert(0, {
                "Runda": st.session_state.g2_round,
                "Twój Wybór": "ORZEŁ" if user_chose_heads else "RESZKA",
                "Rezultat": result_label,
                "Stawka": f"{bet_amount:.2f} PLN",
                "% Kapitału": f"{bet_pct}%"
            })
            
            # Zapis do logów (CSV/Sheets)
            st.session_state.results['game2_history'].append({
                "round": st.session_state.g2_round,
                "bet_amount": bet_amount,
                "choice": "HEADS" if user_chose_heads else "TAILS",
                "coin_result": "HEADS" if is_heads else "TAILS",
                "result": "WIN" if win else "LOSS",
                "capital_after": st.session_state.g2_capital
            })
            
            st.session_state.g2_round += 1
            
            # Obsługa końca gry i przeładowania
            if st.session_state.g2_round > 30:
                time.sleep(1.5)
                next_page('survey')
            else:
                time.sleep(1.0)
                st.rerun()
        
        # Wykres pod spodem
        st.line_chart(st.session_state.g2_history_chart)

    with col_hist:
        st.write("### Historia Gier")
        if st.session_state.g2_table_data:
            df_hist = pd.DataFrame(st.session_state.g2_table_data)
            st.dataframe(
                df_hist.style.map(color_outcome, subset=['Rezultat']),
                height=500,
                use_container_width=True,
                hide_index=True
            )

# --- ANKIETA (PODZIELONA NA 2 STRONY) ---

def show_survey():
    st.header("Część 3: Scenariusze")
    
    page_num = st.session_state.survey_page_num
    
    if page_num == 1:
        st.progress(50)
        current_questions = FIXED_QUESTIONS[:7]
        btn_label = "Dalej (Strona 2/2)"
    else:
        st.progress(100)
        current_questions = FIXED_QUESTIONS[7:]
        btn_label = "Zakończ badanie"

    with st.form(f"survey_form_{page_num}"):
        for q_data in current_questions:
            st.markdown(f"**{q_data['q']}**")
            val = st.radio("Wybierz opcję:", q_data['opts'], key=q_data['id'], index=None)
            st.markdown("---")
        
        submitted = st.form_submit_button(btn_label)
        
        if submitted:
            missing = False
            current_answers = {}
            for q in current_questions:
                ans = st.session_state.get(q['id'])
                if ans is None:
                    missing = True
                else:
                    current_answers[q['id']] = ans
            
            if missing:
                st.warning("Proszę odpowiedzieć na wszystkie pytania na tej stronie.")
            else:
                st.session_state.results['survey_answers'].update(current_answers)
                
                if page_num == 1:
                    st.session_state.survey_page_num = 2
                    st.rerun()
                else:
                    next_page('finish')

# --- ROUTER ---
if st.session_state.page == 'intro': show_intro()
elif st.session_state.page == 'demographics': show_demographics()
elif st.session_state.page == 'game1_intro': show_game1_intro()
elif st.session_state.page == 'game1': show_game1()
elif st.session_state.page == 'game2_intro': show_game2_intro()
elif st.session_state.page == 'game2_questions': show_game2_questions() # <-- NOWA STRONA W ROUTERZE
elif st.session_state.page == 'game2': show_game2()
elif st.session_state.page == 'survey': show_survey()
elif st.session_state.page == 'finish': show_finish()