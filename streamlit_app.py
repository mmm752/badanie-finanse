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
st.set_page_config(page_title="Badanie Decyzji (v2)", layout="centered")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 3em; font-weight: bold; }
    .instruction-card {
        background-color: #f8f9fa;
        border-left: 6px solid #003366;
        padding: 20px;
        border-radius: 4px;
        margin-bottom: 25px;
        color: #2c3e50;
    }
    .instruction-card h3 { color: #003366; margin-top: 0; }
    .important-text { color: #003366; font-weight: 800; text-decoration: underline; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- DANE GIEŁDOWE (40 OKRESÓW) ---
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
    y = 2022; m = 9
    for _ in range(40):
        dates.append(datetime(y, m, 1))
        m += 1
        if m > 12: m = 1; y += 1
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
        'pre_game2_survey': {}, # NOWE POLE
        'game1_history': [],
        'game2_history': [],
        'survey_answers': {}
    }
if 'survey_page_num' not in st.session_state:
    st.session_state.survey_page_num = 1

# --- PYTANIA ANKIETOWE (SCENARIUSZE) ---
FIXED_QUESTIONS = [
    {"id": "Q01_Overconfidence", "q": "Pytanie 1: Pracujesz w branży IT i budujesz portfel emerytalny na 30 lat. Twoja wiedza o technologii jest bardzo szeroka.", "opts": ["A: Inwestujesz 80% środków w spółki technologiczne...", "B: Dywersyfikujesz portfel o sektory, których nie znasz..."]},
    {"id": "Q02_LossAversion_Loss", "q": "Pytanie 2: Kupiłeś akcje po 100 PLN, obecnie kosztują 70 PLN (-30%)...", "opts": ["A: Natychmiast zamykasz pozycję...", "B: Trzymasz akcje. Czekasz na korektę..."]},
    {"id": "Q03_Recency", "q": "Pytanie 3: Masz do wyboru dwa fundusze akcyjne o identycznych opłatach:", "opts": ["A: Fundusz \"Lider Wzrostu\" (ostatnio +15%)...", "B: Fundusz \"Systematyczny\" (stabilne 7-8%)..."]},
    {"id": "Q04_Framing_Gain", "q": "Pytanie 4: Otrzymałeś spadek 100 000 PLN. Masz dwie opcje:", "opts": ["A: Bezpieczna obligacja (pewne 30 000 PLN zysku)...", "B: Ryzykowny fundusz (30% szans na 100k zysku, 70% na zero)..."]},
    {"id": "Q05_LossAversion_Gain", "q": "Pytanie 5: Kupiłeś akcje po 50 PLN, dziś kosztują 80 PLN (+60%)...", "opts": ["A: Sprzedajesz teraz, aby \"zaksięgować zysk\"...", "B: Trzymasz pozycję zgodnie z analizą..."]},
    {"id": "Q06_Confirmation", "q": "Pytanie 6: Spółka, którą lubisz, publikuje raport. Zysk dobry, dług wysoki.", "opts": ["A: Skupiasz się na zyskach...", "B: Analizujesz strukturę długu..."]},
    {"id": "Q07_Framing_Loss", "q": "Pytanie 7: Otrzymałeś wezwanie do zapłaty 100 000 PLN podatku.", "opts": ["A: Płacisz ugodę 70 000 PLN.", "B: Sąd: 30% szansy na 0, 70% na 100 000 PLN."]},
    {"id": "Q08_Anchoring", "q": "Pytanie 8: Kupiłeś akcje po 200 PLN, spadły do 150, odbiły do 198.", "opts": ["A: Sprzedajesz, czując ulgę...", "B: Oceniasz spółkę po cenie 198 PLN..."]},
    {"id": "Q09_Hindsight", "q": "Pytanie 9: Patrzysz na wykres historyczny krachu.", "opts": ["A: \"To było oczywiste...\"", "B: \"Sytuacja była niejasna...\""]},
    {"id": "Q10_Availability_Fear", "q": "Pytanie 10: Katastrofa budowlana w Azji, masz akcje budowlane z Europy.", "opts": ["A: Rozważasz sprzedaż przez lęk...", "B: Ignorujesz newsa..."]},
    {"id": "Q11_Confirmation_Search", "q": "Pytanie 11: Chcesz kupić Bitcoina. Czego szukasz?", "opts": ["A: \"Prognozy wzrostu...\"", "B: \"Zagrożenia dla Bitcoina...\""]},
    {"id": "Q12_OutcomeBias", "q": "Pytanie 12: Fundusz zarobił 40% na jednej ryzykownej transakcji.", "opts": ["A: Inwestujesz (dowód skuteczności)...", "B: Rezygnujesz (szczęście)..."]},
    {"id": "Q13_Confirmation_Auth", "q": "Pytanie 13: Analityk \"Sprzedaj\" vs Twój ulubiony \"Kupuj\".", "opts": ["A: Ignorujesz \"Sprzedaj\"...", "B: Czytasz uważnie \"Sprzedaj\"..."]},
    {"id": "Q14_Hindsight_Bubble", "q": "Pytanie 14: Pamiętasz bańkę technologiczną. Co wtedy myślałeś?", "opts": ["A: \"Wiedziałem, że to bańka...\"", "B: \"Czułem niepewność...\""]}
]

# --- FUNKCJE POMOCNICZE ---
def next_page(page_name):
    st.session_state.page = page_name
    st.rerun()

def pad_history(history_list, total_length):
    base = history_list[:total_length]
    padding = [None] * (total_length - len(base))
    return base + padding

def color_outcome(val):
    if isinstance(val, str):
        if "WYGRANA" in val: return 'color: #2e7d32; font-weight: bold'
        elif "PRZEGRANA" in val: return 'color: #c62828; font-weight: bold'
    return ''

# --- ZAPIS DANYCH ---
def save_data_multi_sheet(data_package):
    # Nagłówki
    q_headers = [f"Pytanie_{i+1:02d}" for i in range(14)]
    HEADERS_MAIN = [
        "User_ID", "Data_Badania", 
        "Wiek", "Plec", "Wyksztalcenie", "Branza_Fin", "Dosw_Inv", "Real_Inv", "Ryzyko",
        "PreG2_Exp_Return", "PreG2_Loss_Prob", "PreG2_Ruin_Prob", # NOWE KOLUMNY
        "G1_Kapital_Koncowy", "G2_Kapital_Koncowy"
    ] + q_headers

    HEADERS_G1 = ["User_ID", "Runda", "Zwrot_SP", "Kier_SP", "Zwrot_NDQ", "Kier_NDQ", "Decyzja", "Lewar", "Zmiana", "Zwrot_User", "PnL", "Win", "Kapital"]
    HEADERS_G2 = ["User_ID", "Runda", "Kapital_Przed", "Strona", "Stawka", "Ratio", "Kelly_Diff", "Martingale", "Zmiana_Strony", "Wynik", "Win", "Kapital_Po"]
    
    HEADERS_MAP = {"main": HEADERS_MAIN, "g1": HEADERS_G1, "g2": HEADERS_G2}
    SHEET_NAMES = {"main": "Uczestnicy_Ankieta", "g1": "G1_Gielda_Szczegoly", "g2": "G2_Moneta_Szczegoly"}

    # GSheets
    if HAS_GSPREAD and 'gcp_service_account' in st.secrets:
        try:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
            gc = gspread.authorize(creds)
            sh = gc.open("Wyniki_Badania")
            for key, rows in data_package.items():
                if not rows: continue
                try:
                    ws = sh.worksheet(SHEET_NAMES[key])
                    if not ws.get_all_values(): ws.append_row(HEADERS_MAP[key])
                    ws.append_rows(rows)
                except Exception: pass
            return True
        except Exception as e: st.error(f"GSheets Error: {e}")

    # CSV
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for key, rows in data_package.items():
            if not rows: continue
            df = pd.DataFrame(rows, columns=HEADERS_MAP[key])
            df.to_csv(f"wyniki_{key}_{ts}.csv", index=False, header=True, encoding='utf-8-sig')
        return True
    except Exception as e:
        st.error(f"CSV Error: {e}")
        return False

def show_finish():
    st.success("Badanie zakończone! Trwa zapisywanie...")
    uid = st.session_state.user_id
    demo = st.session_state.results['demographics']
    pre_g2 = st.session_state.results.get('pre_game2_survey', {})
    
    # Ankieta płaska
    survey_flat = []
    for k in sorted(st.session_state.results['survey_answers'].keys()):
        ans = st.session_state.results['survey_answers'][k]
        survey_flat.append(ans.split(":")[0] if ":" in ans else ans)

    main_row = [
        uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        demo.get('age'), demo.get('gender'), demo.get('education'), 
        demo.get('finance_related'), demo.get('inv_experience'), 
        demo.get('real_investing'), demo.get('risk_tolerance'),
        pre_g2.get('expected_return'), pre_g2.get('loss_prob'), pre_g2.get('ruin_prob'),
        st.session_state.g1_history_user[-1], st.session_state.g2_capital
    ] + survey_flat

    # G1 History
    g1_rows = []
    prev_cap = 10000.0; prev_choice = None
    for rec in st.session_state.results['game1_history']:
        curr = rec['round']; prev = curr - 1
        ra = (DATA_A[curr]-DATA_A[prev])/DATA_A[prev] if curr < len(DATA_A) else 0
        rb = (DATA_B[curr]-DATA_B[prev])/DATA_B[prev] if curr < len(DATA_B) else 0
        row = [
            uid, curr, round(ra,4), 1 if ra>=0 else -1, round(rb,4), 1 if rb>=0 else -1,
            rec['choice'], 1 if rec['leverage'] else 0, 1 if (prev_choice and rec['choice']!=prev_choice) else 0,
            round(rec['return'],4), round(rec['capital']-prev_cap,2), 1 if rec['capital']>prev_cap else 0, round(rec['capital'],2)
        ]
        g1_rows.append(row)
        prev_cap = rec['capital']; prev_choice = rec['choice']

    # G2 History
    g2_rows = []
    prev_bet = 0.0; prev_res = None; prev_side = None; cap_runner = 100.0
    for rec in st.session_state.results['game2_history']:
        ratio = rec['bet_amount']/cap_runner if cap_runner>0 else 0
        martingale = 1 if (prev_res=='LOSS' and prev_bet>0 and rec['bet_amount']>=prev_bet*2) else 0
        row = [
            uid, rec['round'], round(cap_runner,2), rec['choice'], rec['bet_amount'], round(ratio,4), round(ratio-0.2,4),
            martingale, 1 if (prev_side and rec['choice']!=prev_side) else 0, rec['coin_result'], 1 if rec['result']=='WIN' else 0, round(rec['capital_after'],2)
        ]
        g2_rows.append(row)
        cap_runner = rec['capital_after']; prev_bet = rec['bet_amount']; prev_res = rec['result']; prev_side = rec['choice']

    if save_data_multi_sheet({"main": [main_row], "g1": g1_rows, "g2": g2_rows}):
        st.session_state.saved = True
        st.balloons()
        st.markdown("### Dziękujemy! Dane zapisane.")

# --- STRONY ---
def show_intro():
    st.title("Badanie Decyzji Finansowych (v2 - Nowe Pytania)")
    st.markdown(f"ID: **{st.session_state.user_id}**")
    st.info("Badanie składa się z: Giełdy (40 rund), Oszacowania ryzyka, Gry z monetą (30 rund) i Ankiety.")
    if st.button("Rozpocznij"): next_page('demographics')

def show_demographics():
    st.header("Metryczka")
    with st.form("demo"):
        age = st.selectbox("1. Wiek", ["<18", "18–24", "25–34", "35–44", "45–54", "55–64", "65+"])
        gender = st.radio("2. Płeć", ["Kobieta", "Mężczyzna", "Inna"])
        edu = st.selectbox("3. Wykształcenie", ["Podstawowe", "Średnie", "Licencjat/Inż", "Magister", "Doktorat"])
        field = st.radio("4. Związek z finansami", ["Tak", "Częściowo", "Nie"])
        exp = st.selectbox("5. Doświadczenie", ["Brak", "Początkujące", "Średnie", "Zaawansowane", "Pro"])
        real = st.radio("6. Inwestowałeś realnie?", ["Tak", "Nie"])
        risk = st.slider("7. Skłonność do ryzyka (1-7)", 1, 7, 4)
        if st.form_submit_button("Dalej"):
            if all([age, gender, edu, field, exp, real]):
                st.session_state.results['demographics'] = {"age":age, "gender":gender, "education":edu, "finance_related":field, "inv_experience":exp, "real_investing":real, "risk_tolerance":risk}
                next_page('game1_intro')
            else: st.error("Wypełnij wszystkie pola.")

def show_game1_intro():
    st.header("Część 1: Giełda")
    st.markdown("""
    <div class="instruction-card">
        <b>Zasady:</b> 40 rund (miesięcy). Kapitał 10 000 PLN.
        Wybierasz: Indeks A, Indeks B lub Gotówkę.
        Od 21. rundy dostępny LEWAR (x2).
    </div>
    """, unsafe_allow_html=True)
    
    # Inicjalizacja G1
    if 'g1_round' not in st.session_state:
        st.session_state.g1_round = 0
        st.session_state.g1_capital = 10000.0
        st.session_state.g1_history_user = [10000.0]
        st.session_state.start_A = DATA_A[0]; st.session_state.start_B = DATA_B[0]
        st.session_state.g1_history_A = [10000.0]; st.session_state.g1_history_B = [10000.0]

    if st.button("Start Giełdy"): next_page('game1')

def show_game1():
    idx = st.session_state.g1_round
    # TRIGGER: Po 40 rundzie (indeks 39) idziemy do PRE_GAME2_SURVEY
    if idx >= 40: 
        next_page('pre_game2_survey')
        return

    curr_cap = st.session_state.g1_history_user[-1]
    prev_cap = st.session_state.g1_history_user[-2] if len(st.session_state.g1_history_user)>1 else 10000.0
    pct = ((curr_cap - prev_cap)/prev_cap)*100
    
    st.subheader(f"Runda {idx+1} / 40")
    st.metric("Kapitał", f"{curr_cap:.2f} PLN", f"{pct:.2f}%")
    
    chart_data = pd.DataFrame({
        "S&P": pad_history(st.session_state.g1_history_A, 40),
        "Nasdaq": pad_history(st.session_state.g1_history_B, 40),
        "Ty": pad_history(st.session_state.g1_history_user, 40)
    })
    st.line_chart(chart_data, color=["#ccc", "#44f", "#f00"])

    lev = False
    if idx >= 20:
        st.warning("LEWAR DOSTĘPNY")
        lev = st.checkbox("Użyj lewaru x2")

    c1, c2, c3 = st.columns(3)
    choice = None
    if c1.button("Indeks A"): choice='A'
    if c2.button("Indeks B"): choice='B'
    if c3.button("Gotówka"): choice='Cash'

    if choice:
        # Logika rundy
        if idx < 39:
            nxt = idx + 1
            pa_old = DATA_A[idx]; pa_new = DATA_A[nxt]; ra = (pa_new-pa_old)/pa_old
            pb_old = DATA_B[idx]; pb_new = DATA_B[nxt]; rb = (pb_new-pb_old)/pb_old
            
            uret = 0.0
            if choice=='A': uret = ra
            elif choice=='B': uret = rb
            if lev: uret *= 2
            
            new_cap = curr_cap * (1+uret)
            st.session_state.g1_history_user.append(new_cap)
            st.session_state.g1_history_A.append((DATA_A[nxt]/st.session_state.start_A)*10000)
            st.session_state.g1_history_B.append((DATA_B[nxt]/st.session_state.start_B)*10000)
            
            st.session_state.results['game1_history'].append({"round":nxt, "choice":choice, "leverage":lev, "return":uret, "capital":new_cap})
            st.session_state.g1_round += 1
            st.rerun()
        else:
            # Ostatnia runda kliknięta - zapisz i przejdz
            st.session_state.g1_round += 1
            next_page('pre_game2_survey')

# --- NOWY ETAP: Ankieta Pośrednia ---
def show_pre_game2_survey():
    st.header("Ankieta: Oczekiwania i Ryzyko")
    with st.form("pre_g2"):
        q1 = st.radio("1. Jakiej stopy zwrotu spodziewasz się w grze z monetą (30 rund)?", 
                      ["Strata > -50%", "-50% do -20%", "-20% do 0%", "0% do +20%", "+20% do +50%", "> +50%"])
        q2 = st.radio("2. Prawdopodobieństwo, że skończysz poniżej 100 PLN?", 
                      ["0-10%", "11-25%", "26-50%", "51-75%", "76-100%"])
        q3 = st.radio("3. Prawdopodobieństwo bankructwa (strata >80%)?", 
                      ["0-5%", "6-15%", "16-30%", "31-50%", ">50%"])
        if st.form_submit_button("Dalej do Gry z Monetą"):
            if all([q1, q2, q3]):
                st.session_state.results['pre_game2_survey'] = {"expected_return":q1, "loss_prob":q2, "ruin_prob":q3}
                next_page('game2_intro')
            else: st.error("Odpowiedz na wszystkie pytania.")

def show_game2_intro():
    st.header("Część 2: Moneta")
    st.markdown("""
    <div class="instruction-card">
        <b>Zasady:</b> 30 rzutów. Start 100 PLN.
        Orzeł (60% szans), Reszka (40% szans).
        Ustawiasz stawkę suwakiem.
    </div>
    """, unsafe_allow_html=True)
    
    if 'g2_round' not in st.session_state:
        st.session_state.g2_round = 1
        st.session_state.g2_capital = 100.0
        st.session_state.g2_history_chart = [100.0]
        st.session_state.g2_table_data = []
        
    if st.button("Start Moneta"): next_page('game2')

def show_game2():
    idx = st.session_state.g2_round
    # TRIGGER: Koniec po 30 rundach
    if idx > 30:
        next_page('survey')
        return

    st.subheader(f"Rzut {idx} / 30")
    cap = st.session_state.g2_capital
    
    c_main, c_hist = st.columns([1,1])
    with c_main:
        st.metric("Kapitał", f"{cap:.2f} PLN")
        if cap <= 0.01:
            st.error("Bankructwo!"); time.sleep(2); next_page('survey'); return
            
        pct = st.slider("Stawka %", 0, 100, 10)
        bet_val = cap * (pct/100.0)
        st.write(f"Stawiasz: **{bet_val:.2f} PLN**")
        side = st.radio("Wybór:", ["ORZEŁ", "RESZKA"], horizontal=True)
        
        if st.button("RZUĆ"):
            res = "ORZEŁ" if random.random() < 0.6 else "RESZKA"
            win = (side == res)
            pnl = bet_val if win else -bet_val
            
            st.session_state.g2_capital += pnl
            st.session_state.g2_history_chart.append(st.session_state.g2_capital)
            
            res_txt = f"WYGRANA ({res})" if win else f"PRZEGRANA ({res})"
            if win: st.success(f"Brawo! {res_txt}")
            else: st.error(f"Niestety... {res_txt}")
            
            # Log
            st.session_state.g2_table_data.insert(0, {"Runda":idx, "Wynik":res_txt, "Stawka":f"{bet_val:.2f}", "Kapitał":f"{st.session_state.g2_capital:.2f}"})
            st.session_state.results['game2_history'].append({"round":idx, "bet_amount":bet_val, "choice":("HEADS" if side=="ORZEŁ" else "TAILS"), "coin_result":("HEADS" if res=="ORZEŁ" else "TAILS"), "result":("WIN" if win else "LOSS"), "capital_after":st.session_state.g2_capital})
            
            st.session_state.g2_round += 1
            time.sleep(1); st.rerun()
            
        st.line_chart(st.session_state.g2_history_chart)

    with c_hist:
        if st.session_state.g2_table_data:
            st.dataframe(pd.DataFrame(st.session_state.g2_table_data).style.map(color_outcome, subset=['Wynik']), hide_index=True)

def show_survey():
    st.header("Ankieta Końcowa")
    pg = st.session_state.survey_page_num
    qs = FIXED_QUESTIONS[:7] if pg==1 else FIXED_QUESTIONS[7:]
    
    with st.form("surv"):
        for q in qs:
            st.markdown(f"**{q['q']}**")
            st.radio("Opcja", q['opts'], key=q['id'])
            st.markdown("---")
        if st.form_submit_button("Dalej" if pg==1 else "Zakończ"):
            # Zapisz odpowiedzi
            saved_any = False
            for q in qs:
                val = st.session_state.get(q['id'])
                if val: st.session_state.results['survey_answers'][q['id']] = val; saved_any = True
            
            if saved_any:
                if pg==1: st.session_state.survey_page_num=2; st.rerun()
                else: next_page('finish')
            else: st.warning("Zaznacz odpowiedzi.")

# --- ROUTER ---
if st.session_state.page == 'intro': show_intro()
elif st.session_state.page == 'demographics': show_demographics()
elif st.session_state.page == 'game1_intro': show_game1_intro()
elif st.session_state.page == 'game1': show_game1()
elif st.session_state.page == 'pre_game2_survey': show_pre_game2_survey()
elif st.session_state.page == 'game2_intro': show_game2_intro()
elif st.session_state.page == 'game2': show_game2()
elif st.session_state.page == 'survey': show_survey()
elif st.session_state.page == 'finish': show_finish()