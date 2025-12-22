import streamlit as st
import pandas as pd
import numpy as np
import random
import time
import uuid
from datetime import datetime

# --- KONFIGURACJA ---
st.set_page_config(page_title="Badanie Decyzji", layout="centered")

# Próba importu bibliotek do Google Sheets (wymagane do wersji online)
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# --- STYLE ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; height: 3em; font-weight: bold; }
    .instruction-box { background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- INICJALIZACJA STANU ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8] # Unikalny ID
if 'page' not in st.session_state:
    st.session_state.page = 'intro'

# Inicjalizacja wyników
if 'results' not in st.session_state:
    st.session_state.results = {
        'demographics': {},
        'game1_history': [],
        'game2_history': [],
        'survey_answers': {}
    }

# [cite_start]--- BAZA PYTAŃ (Z pliku PDF) [cite: 76-144] ---
ALL_QUESTIONS = [
    # LOSS AVERSION
    {"id": "LA_1", "type": "Loss Aversion", "q": "Kupiłeś akcje 'NanoTech' po 50 PLN. Obecnie kosztują 80 PLN (+60%). Analitycy celują w 100 PLN, ale czujesz niepokój.", "opts": ["A: Sprzedajesz teraz, żeby 'zaksięgować zysk'.", "B: Trzymasz pozycję, pozwalając zyskom rosnąć."]},
    {"id": "LA_2", "type": "Loss Aversion", "q": "Masz akcje spółki węglowej kupione po 100 PLN. Obecnie kosztują 70 PLN (-30%). Fundamenty się pogarszają.", "opts": ["A: Sprzedajesz, akceptując stratę, by ochronić kapitał.", "B: Trzymasz, czekając aż wrócą do 90-100 PLN, żeby wyjść na zero."]},
    {"id": "LA_3", "type": "Loss Aversion", "q": "Inwestycja spadła z 200 PLN do 150 PLN, ale nagle odbiła do 198 PLN (prawie cena zakupu).", "opts": ["A: Sprzedajesz natychmiast, czując ulgę, że 'prawie nic nie straciłeś'.", "B: Trzymasz dalej dla zysku, analizując powód wzrostu."]},
    # FRAMING BIAS
    {"id": "FB_1", "type": "Framing", "q": "ZYSK: Otrzymałeś 100 000 PLN. Wybierz:", "opts": ["A: Pewny zysk 30 000 PLN.", "B: 30% szans na zysk 100 000 PLN i 70% szans na brak zysku."]},
    {"id": "FB_2", "type": "Framing", "q": "STRATA: Otrzymałeś wezwanie do zapłaty 100 000 PLN podatku. Wybierz:", "opts": ["A: Pewna strata (zapłata) 70 000 PLN.", "B: 30% szans, że nie zapłacisz nic, 70% szans, że zapłacisz 100 000 PLN."]},
    # AVAILABILITY BIAS
    {"id": "AB_1", "type": "Availability", "q": "Wybierasz fundusz akcji polskich. Który wolisz?", "opts": ["A: 'Lider Wzrostu' – nagroda 'Fundusz Roku', ostatni kwartał +15%, głośno w mediach.", "B: 'Systematyczny' – brak nagród, stabilne 7-8% rocznie od 10 lat, cichy."]},
    {"id": "AB_2", "type": "Availability", "q": "Wiadomości donoszą o katastrofie budowlanej w Azji. Masz akcje europejskiej budowlanki.", "opts": ["A: Rozważasz sprzedaż, bo masz obraz katastrofy przed oczami.", "B: Ignorujesz newsa z Azji jako nieistotny dla rynku europejskiego."]},
    {"id": "AB_3", "type": "Availability", "q": "Pracujesz w IT. Budujesz portfel emerytalny.", "opts": ["A: Inwestujesz 80% w spółki technologiczne, bo się na tym znasz.", "B: Dywersyfikujesz o surowce i banki, mimo że nie znasz tych branż."]},
    # CONFIRMATION BIAS
    {"id": "CB_1", "type": "Confirmation", "q": "Chcesz kupić Bitcoina. Co wpisujesz w Google?", "opts": ["A: 'Dlaczego Bitcoin to przyszłość' / 'Prognozy wzrostu'.", "B: 'Zagrożenia dla rynku krypto' / 'Analiza ryzyka'."]},
    {"id": "CB_2", "type": "Confirmation", "q": "Spółka ma zysk zgodny z oczekiwaniami, ale drastycznie wzrosło zadłużenie.", "opts": ["A: Skupiasz się na zysku ('Dowożą wyniki!') ignorując dług.", "B: Analizujesz strukturę długu, martwiąc się o płynność."]},
    {"id": "CB_3", "type": "Confirmation", "q": "Twój analityk rekomenduje 'Kupuj'. Inny analityk pisze 'Sprzedaj' (błędy w księgowości).", "opts": ["A: Czytasz raport swojego analityka, by się upewnić. Drugi odrzucasz.", "B: Czytasz uważnie negatywny raport, by sprawdzić, czy Twój analityk się nie myli."]},
    # HINDSIGHT BIAS
    {"id": "HB_1", "type": "Hindsight", "q": "Patrzysz na wykres krachu z 2008 roku. Co myślisz?", "opts": ["A: 'Wskaźniki były absurdalne, każdy rozsądny by to przewidział'.", "B: 'W tamtym czasie sytuacja była niejednoznaczna'."]},
    {"id": "HB_2", "type": "Hindsight", "q": "Fundusz zarobił 40% (rynek 5%) dzięki jednej ryzykownej transakcji na opcjach.", "opts": ["A: Powierzasz mu pieniądze – wynik dowodzi geniuszu zarządzającego.", "B: Rezygnujesz – uważasz, że miał po prostu szczęście (zbyt duże ryzyko)."]},
    {"id": "HB_3", "type": "Hindsight", "q": "Wspominasz bańkę na spółkach Growth. Jak oceniasz swoje ówczesne myśli?", "opts": ["A: 'Wiedziałem, że to bańka i tylko czekałem aż pęknie'.", "B: 'Wtedy argumenty za wzrostami wydawały się równie silne'."]}
]

# Losowanie pytań RAZ na sesję
if 'shuffled_questions' not in st.session_state:
    q_copy = ALL_QUESTIONS.copy()
    random.shuffle(q_copy)
    st.session_state.shuffled_questions = q_copy

# --- FUNKCJE ---

def next_page(page_name):
    st.session_state.page = page_name
    st.rerun()

def save_to_google_sheets(data_dict):
    """Wysyła dane do Google Sheets lub zapisuje lokalnie jeśli brak konfiguracji"""
    # Przygotowanie płaskiego wiersza danych
    row = [
        data_dict.get('user_id'),
        data_dict.get('timestamp'),
        data_dict.get('age'),
        data_dict.get('gender'),
        data_dict.get('risk_tolerance'),
        data_dict.get('g1_final_capital'),
        data_dict.get('g2_final_capital'),
        # ... tu można dodać więcej kolumn
    ]
    # Dodanie odpowiedzi z ankiety w kolejności ID
    sorted_keys = sorted(data_dict.keys())
    # (Uproszczony zapis - w produkcji lepiej mapować konkretne kolumny)
    
    # 1. Próba zapisu do chmury (Google Sheets)
    if HAS_GSPREAD and 'gcp_service_account' in st.secrets:
        try:
            # Używamy sekretów Streamlit do autoryzacji
            credentials = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            gc = gspread.authorize(credentials)
            # Otwórz arkusz po kluczu lub nazwie
            sh = gc.open("Wyniki_Badania") 
            worksheet = sh.worksheet("Dane_Surowe")
            
            # Konwersja słownika na listę wartości
            values = list(data_dict.values())
            worksheet.append_row(values)
            return True
        except Exception as e:
            st.error(f"Błąd zapisu Google Sheets: {e}")
            return False
    else:
        # 2. Zapis lokalny (fallback)
        df = pd.DataFrame([data_dict])
        try:
            # Tryb 'append' do pliku csv
            with open("lokalne_wyniki.csv", "a") as f:
                df.to_csv(f, header=f.tell()==0, index=False)
            return True
        except Exception as e:
            st.error(f"Błąd zapisu lokalnego: {e}")
            return False

# --- STRONY ---

def show_intro():
    st.title("Badanie Decyzji Finansowych")
    st.markdown("""
    Dzień dobry!
    
    Zapraszam do udziału w badaniu naukowym dotyczącym psychologii inwestowania.
    Badanie jest w pełni anonimowe. Twoim identyfikatorem jest losowy kod: **{}**.
    
    **Badanie składa się z 3 części:**
    1. **Gra alokacyjna** – zarządzanie portfelem w czasie.
    2. **Wyzwanie monety** – zarządzanie stawką i ryzykiem.
    3. **Scenariusze decyzyjne** – krótkie pytania sytuacyjne.
    
    Całość zajmie około 10-15 minut.
    """.format(st.session_state.user_id))
    
    if st.button("Rozpocznij badanie"):
        next_page('demographics')

def show_demographics():
    st.header("Metryczka")
    with st.form("demo"):
        age = st.selectbox("Wiek", ["18-24", "25-34", "35-44", "45-54", "55+"])
        gender = st.radio("Płeć", ["Kobieta", "Mężczyzna", "Inna"])
        risk = st.slider("Jak oceniasz swoją skłonność do ryzyka? (1-Brak, 7-Wysoka)", 1, 7, 4)
        
        if st.form_submit_button("Dalej"):
            st.session_state.results['demographics'] = {"age": age, "gender": gender, "risk_tolerance": risk}
            next_page('game1_intro')

# --- GRA 1 ---

def show_game1_intro():
    st.header("Część 1: Gra Inwestycyjna")
    st.markdown("""
    <div class="instruction-box">
    <strong>Instrukcja:</strong><br>
    Wcielasz się w rolę inwestora. Masz przed sobą <b>40 rund</b> decyzyjnych.<br>
    
    1. [cite_start]Na start otrzymujesz <b>10 000 PLN</b> wirtualnego kapitału. [cite: 3]
    2. [cite_start]W każdej rundzie decydujesz, gdzie ulokować pieniądze na <u>jeden okres</u>: [cite: 4]
       - <b>Indeks A</b>: Inwestycja giełdowa (wyższa zmienność).
       - <b>Indeks B</b>: Inwestycja alternatywna (inna charakterystyka zmian).
       - <b>Gotówka</b>: Bezpieczna przystań (0% zysku/straty, ale chroni kapitał).
    3. Ceny zmieniają się losowo, ale mogą tworzyć trendy. Twoim celem jest maksymalizacja zysku.
    
    W drugiej połowie gry (od rundy 21) pojawi się opcja <b>Lewaru (Dźwigni)</b>. Używaj jej rozważnie!
    </div>
    """, unsafe_allow_html=True)
    
    # Inicjalizacja zmiennych gry 1
    if 'g1_round' not in st.session_state:
        st.session_state.g1_round = 1
        st.session_state.g1_capital = 10000.0
        st.session_state.g1_data = {'A': [100.0], 'B': [100.0]}
        st.session_state.g1_cap_history = [10000.0]

    if st.button("Rozumiem, gramy!"):
        next_page('game1')

def show_game1():
    round_num = st.session_state.g1_round
    st.subheader(f"Runda {round_num} / 40")
    
    current_cap = st.session_state.g1_cap_history[-1]
    st.metric("Twój Kapitał", f"{current_cap:.2f} PLN")
    
    # Wykres
    chart_df = pd.DataFrame(st.session_state.g1_data)
    st.line_chart(chart_df)
    
    # [cite_start]Logika lewaru [cite: 11]
    leverage_active = False
    if round_num > 20:
        st.warning("⚡ ODBLOKOWANO DŹWIGNIĘ (LEWAR x2)")
        st.info("Zaznaczenie lewaru podwaja Twój zysk, ale też podwaja stratę w danej rundzie.")
        leverage_active = st.checkbox("Użyj dźwigni finansowej w tej rundzie")

    col1, col2, col3 = st.columns(3)
    choice = None
    if col1.button("Inwestuj w INDEKS A"): choice = 'A'
    if col2.button("Inwestuj w INDEKS B"): choice = 'B'
    if col3.button("Zostań w GOTÓWCE"): choice = 'Cash'

    if choice:
        # [cite_start]Symulacja ruchu cen [cite: 8]
        change_A = np.random.normal(0.005, 0.03) # Średnia +0.5%, odchylenie 3%
        change_B = np.random.normal(0.003, 0.04) # Średnia +0.3%, odchylenie 4%
        
        # Aktualizacja indeksów
        st.session_state.g1_data['A'].append(st.session_state.g1_data['A'][-1] * (1 + change_A))
        st.session_state.g1_data['B'].append(st.session_state.g1_data['B'][-1] * (1 + change_B))
        
        # Obliczenie wyniku
        round_ret = 0
        if choice == 'A': round_ret = change_A
        elif choice == 'B': round_ret = change_B
        
        if leverage_active:
            round_ret = round_ret * 2 - 0.005 # Koszt lewaru
            
        new_cap = current_cap * (1 + round_ret)
        st.session_state.g1_cap_history.append(new_cap)
        
        # Zapis rundy
        st.session_state.results['game1_history'].append({
            "round": round_num, "choice": choice, "leverage": leverage_active, "result_pct": round_ret, "capital": new_cap
        })
        
        st.session_state.g1_round += 1
        if st.session_state.g1_round > 40:
            next_page('game2_intro')
        else:
            st.rerun()

# --- GRA 2 (KELLY) ---

def show_game2_intro():
    st.header("Część 2: Wyzwanie Monety")
    st.markdown("""
    <div class="instruction-box">
    <strong>Instrukcja:</strong><br>
    To zadanie bada zarządzanie ryzykiem.<br>
    1. Zaczynasz z kwotą <b>100 PLN</b>.
    2. Masz możliwość rzucania wirtualną monetą.
    3. [cite_start]<b>Prawdopodobieństwa są znane:</b> [cite: 43-45]
       - 🦅 <b>ORZEŁ (60% szans):</b> Wygrywasz tyle, ile postawiłeś (+100% stawki).
       - 📉 <b>RESZKA (40% szans):</b> Tracisz to, co postawiłeś (-100% stawki).
    
    Twoim zadaniem jest zdecydować, <b>jaki procent (%)</b> swojego aktualnego kapitału chcesz postawić w każdym rzucie, aby zmaksymalizować zysk końcowy, ale nie zbankrutować.
    </div>
    """, unsafe_allow_html=True)
    
    # Init gry 2
    if 'g2_round' not in st.session_state:
        st.session_state.g2_round = 1
        st.session_state.g2_capital = 100.0
        st.session_state.g2_history_chart = [100.0]
        # Tabela szczegółowa dla użytkownika
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

        # Suwak decyzji
        bet_pct = st.slider("Jaki % kapitału stawiasz na ORŁA?", 0, 100, 10)
        bet_val = cap * (bet_pct / 100)
        st.info(f"Stawiasz: **{bet_val:.2f} PLN**. \n\n Wygrana: +{bet_val:.2f} | Przegrana: -{bet_val:.2f}")
        
        if st.button("RZUĆ MONETĄ"):
            is_win = random.random() < 0.6
            pnl = bet_val if is_win else -bet_val
            st.session_state.g2_capital += pnl
            
            result_str = "WYGRANA (Orzeł)" if is_win else "PRZEGRANA (Reszka)"
            
            # Zapis do historii (dla wykresu i tabeli)
            st.session_state.g2_history_chart.append(st.session_state.g2_capital)
            st.session_state.g2_table_data.insert(0, {
                "Runda": st.session_state.g2_round,
                "Decyzja (%)": f"{bet_pct}%",
                "Wynik": result_str,
                "Zysk/Strata": f"{pnl:.2f}",
                "Kapitał po": f"{st.session_state.g2_capital:.2f}"
            })
            
            # Zapis do bazy danych
            st.session_state.results['game2_history'].append({
                "round": st.session_state.g2_round,
                "bet_pct": bet_pct,
                "result": "WIN" if is_win else "LOSS",
                "capital_after": st.session_state.g2_capital
            })
            
            st.session_state.g2_round += 1
            if st.session_state.g2_round > 20: #
                time.sleep(0.5)
                next_page('survey')
            else:
                st.rerun()

    with col_hist:
        st.write("### Historia rzutów")
        if st.session_state.g2_table_data:
            df_hist = pd.DataFrame(st.session_state.g2_table_data)
            st.dataframe(df_hist, height=400, hide_index=True)
        else:
            st.write("Brak rozegranych rund.")

# --- ANKIETA (SCENARIUSZE) ---

def show_survey():
    st.header("Część 3: Scenariusze")
    st.write("Przeczytaj opis sytuacji i wybierz decyzję, która jest Ci bliższa.")
    st.progress(0) # Placeholder na pasek postępu
    
    with st.form("survey_form"):
        answers = {}
        # Wyświetlamy wylosowane wcześniej pytania
        for i, q_data in enumerate(st.session_state.shuffled_questions):
            st.markdown(f"**Pytanie {i+1}** ({q_data['type']})")
            st.write(q_data['q'])
            answers[q_data['id']] = st.radio("Twoja decyzja:", q_data['opts'], key=q_data['id'], index=None)
            st.markdown("---")
        
        if st.form_submit_button("Wyślij odpowiedzi i zakończ"):
            # Sprawdzenie czy wszystko wypełnione (opcjonalne)
            if any(v is None for v in answers.values()):
                st.warning("Proszę odpowiedzieć na wszystkie pytania.")
            else:
                st.session_state.results['survey_answers'] = answers
                next_page('finish')

# --- KONIEC ---

def show_finish():
    st.success("Badanie zakończone! Dziękujemy.")
    
    # Agregacja wszystkich danych do jednego słownika
    final_data = {
        "user_id": st.session_state.user_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **st.session_state.results['demographics'],
        
        # Wyniki Gry 1
        "g1_final_capital": st.session_state.g1_cap_history[-1],
        "g1_leverage_count": sum(1 for r in st.session_state.results['game1_history'] if r['leverage']),
        
        # Wyniki Gry 2
        "g2_final_capital": st.session_state.g2_capital,
        "g2_avg_bet": np.mean([r['bet_pct'] for r in st.session_state.results['game2_history']]) if st.session_state.results['game2_history'] else 0,
        
        # Ankieta (spłaszczenie)
        **{k: v for k, v in st.session_state.results['survey_answers'].items()}
    }
    
    # Zapis
    if 'saved' not in st.session_state:
        success = save_to_google_sheets(final_data)
        if success:
            st.session_state.saved = True
            st.balloons()
            st.info("Twoje wyniki zostały bezpiecznie zapisane w bazie danych.")
        else:
            st.error("Wystąpił problem z zapisem do bazy online. Zapisano kopię lokalną.")
            st.json(final_data) # Wyświetlenie awaryjne

# --- ROUTER ---
if st.session_state.page == 'intro': show_intro()
elif st.session_state.page == 'demographics': show_demographics()
elif st.session_state.page == 'game1_intro': show_game1_intro()
elif st.session_state.page == 'game1': show_game1()
elif st.session_state.page == 'game2_intro': show_game2_intro()
elif st.session_state.page == 'game2': show_game2()
elif st.session_state.page == 'survey': show_survey()
elif st.session_state.page == 'finish': show_finish()