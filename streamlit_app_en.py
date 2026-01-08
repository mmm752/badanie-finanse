import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import random
import time
import uuid
from datetime import datetime

# Attempt to import Google Sheets libraries
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Decision Making Study", layout="centered")

# --- CSS STYLES (High Finance Vibe) ---
st.markdown("""
    <style>
    /* Button */
    .stButton>button { width: 100%; height: 3em; font-weight: bold; }
    
    /* Modern, "financial" instruction box */
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
    
    /* Likert Legend */
    .likert-legend {
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 0.9rem;
        border: 1px solid #90caf9;
    }
    
    /* Hide Menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- MARKET DATA (HARD VERSION) ---
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
    "Sep 22", "Oct 22", "Nov 22", "Dec 22", "Jan 23", "Feb 23", "Mar 23", "Apr 23", "May 23", "Jun 23",
    "Jul 23", "Aug 23", "Sep 23", "Oct 23", "Nov 23", "Dec 23", "Jan 24", "Feb 24", "Mar 24", "Apr 24",
    "May 24", "Jun 24", "Jul 24", "Aug 24", "Sep 24", "Oct 24", "Nov 24", "Dec 24", "Jan 25", "Feb 25",
    "Mar 25", "Apr 25", "May 25", "Jun 25", "Jul 25", "Aug 25", "Sep 25", "Oct 25", "Nov 25", "Dec 25"
]

# --- STATE INITIALIZATION ---
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

# --- SURVEY QUESTIONS (Translated) ---
FIXED_QUESTIONS = [
    {
        "id": "Q01_HomeBias_Competence",
        "q": "1. \"Investing in sectors I understand perfectly due to my job (e.g., a doctor investing in medical companies) allows me to minimize risk better than diversification.\""
    },
    {
        "id": "Q02_Disposition_Gain",
        "q": "2. \"For portfolio safety, it is more important to regularly realize profits when stocks rise than to hold them in hopes of further, uncertain records.\""
    },
    {
        "id": "Q03_Disposition_Loss",
        "q": "3. \"If I am convinced of a company's value, and its price drops below my purchase price, I usually wait to sell until the price returns to the entry level to avoid losing capital.\""
    },
    {
        "id": "Q04_OutcomeBias",
        "q": "4. \"The effectiveness of an advisor or fund manager is best judged by their last year's performance – numbers are the most objective proof of skill.\""
    },
    {
        "id": "Q05_Recency_Trend",
        "q": "5. \"When looking for an investment fund, it is safest to choose those that have performed better than the market average in the last 12-24 months.\""
    },
    {
        "id": "Q06_Confirmation",
        "q": "6. \"When I own shares of a company I have thoroughly analyzed, I treat most negative news as noise that should not affect my long-term vision.\""
    },
    {
        "id": "Q07_Hindsight",
        "q": "7. \"Analyzing the history of market crashes, I believe most of them were preceded by logical economic signals that were possible to notice beforehand.\""
    },
    {
        "id": "Q08_SafetyFirst",
        "q": "8. \"Given a choice between two investments with a similar average return, I usually choose the one that offers a lower maximum profit but guarantees protection of the invested capital.\""
    },
    {
        "id": "Q09_Authority",
        "q": "9. \"In the complex world of finance, it is rational to base decisions on recommendations from known market authorities who have broader access to data.\""
    },
    {
        "id": "Q10_Herding",
        "q": "10. \"If a significant part of the market and financial media turns towards a new asset class (e.g., AI, commodities), it usually means a lasting trend that is not worth ignoring.\""
    },
    {
        "id": "Q11_MentalAccounting",
        "q": "11. \"I believe that unexpectedly received funds (e.g., a high bonus, prize) can be invested in higher-risk assets than my monthly savings.\""
    },
    {
        "id": "Q12_HomeBias_Geo",
        "q": "12. \"I feel more comfortable investing in companies from my own country because it is easier for me to monitor their activities and legal environment.\""
    }
]

# --- FUNCTIONS ---

def next_page(page_name):
    st.session_state.page = page_name
    st.rerun()

def scroll_to_top():
    unique_id = time.time()
    js = f"""
    <script>
        setTimeout(function() {{
            var main = window.parent.document.querySelector('section.main');
            if (main) {{
                main.scrollTo(0, 0);
            }}
            window.parent.scrollTo(0, 0);
        }}, 100); 
    </script>
    """
    components.html(js, height=0)

def save_data_multi_sheet(data_package):
    """
    Saves data to Google Sheets (Target Name: Study_Results_EN) or local CSV.
    """
    
    # Headers translated to English for consistency
    q_headers = [f"Question_{i+1:02d}" for i in range(12)]
    
    HEADERS_MAIN = [
        "User_ID", "Date_Time", 
        "Age", "Gender", "Education", "Finance_Sector", "Inv_Experience", "Real_Inv_History", "Risk_Level",
        "Pre_G2_Exp_Return", "Pre_G2_Loss_Prob", "Pre_G2_Ruin_Prob",
        "G1_Final_Capital", "G2_Final_Capital"
    ] + q_headers

    HEADERS_G1 = [
        "User_ID", "Round", 
        "Return_S&P500", "Dir_S&P", "Return_Nasdaq", "Dir_Nasdaq",
        "User_Decision", "Leverage_Active", "Strategy_Switch",
        "User_Return", "PnL_Currency", "Is_Profit", "Capital_Post_Round"
    ]

    HEADERS_G2 = [
        "User_ID", "Round", "Capital_Pre",
        "Side_Choice", "Bet_Size", "Bet_Ratio_%", "Kelly_Dev", 
        "Martingale_Flag", "Side_Switch",
        "Coin_Result", "Is_Win", "Capital_Post_Round"
    ]

    HEADERS_MAP = {
        "main": HEADERS_MAIN,
        "g1": HEADERS_G1,
        "g2": HEADERS_G2
    }

    # Sheet Names
    SHEET_NAMES = {
        "main": "Participants_Survey",
        "g1": "G1_Market_Details",
        "g2": "G2_Coin_Details"
    }

    # --- SAVE TO GOOGLE SHEETS ---
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
                
                # --- IMPORTANT: TARGET SHEET NAME CHANGED HERE ---
                sh = gc.open("Study_Results_EN") 
                
                for key, rows in data_package.items():
                    if not rows: continue
                    try:
                        ws = sh.worksheet(SHEET_NAMES[key])
                        if not ws.get_all_values():
                            ws.append_row(HEADERS_MAP[key])
                        ws.append_rows(rows)
                    except Exception as inner_e:
                        st.warning(f"Sheet {SHEET_NAMES[key]} not found. ({inner_e})")
                return True 
            except Exception as e:
                st.error(f"GSheets API Error: {e}")
                pass 
    except Exception:
        pass

    # --- SAVE LOCAL CSV (FALLBACK) ---
    try:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        for key, rows in data_package.items():
            if not rows: continue
            
            df = pd.DataFrame(rows, columns=HEADERS_MAP[key])
            filename = f"results_en_{key}_{timestamp_str}.csv"
            
            df.to_csv(filename, index=False, header=True, encoding='utf-8-sig')
            
        return True
    except Exception as e:
        st.error(f"Local save error: {e}")
        return False

def show_finish():
    st.success("Study Completed! Processing and saving metrics...")
    
    uid = st.session_state.user_id
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    demo = st.session_state.results['demographics']
    pre_g2 = st.session_state.results.get('g2_pre_survey', {})

    # --- PREPARE MAIN SHEET ---
    survey_flat = []
    sorted_q_ids = sorted(st.session_state.results['survey_answers'].keys())
    
    for q_id in sorted_q_ids:
        raw_ans = st.session_state.results['survey_answers'][q_id]
        survey_flat.append(raw_ans)

    main_row = [
        uid, ts,
        demo.get('age'), demo.get('gender'), demo.get('education'), 
        demo.get('finance_related'), demo.get('inv_experience'), 
        demo.get('real_investing'), demo.get('risk_tolerance'),
        pre_g2.get('return_expect'), pre_g2.get('loss_prob'), pre_g2.get('ruin_prob'),
        st.session_state.g1_history_user[-1], 
        st.session_state.g2_capital           
    ] + survey_flat
    
    # --- PREPARE G1 SHEET ---
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

    # --- PREPARE G2 SHEET ---
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
            st.markdown("### Thank you!")
            st.markdown("Data has been successfully saved.")
        else:
            st.error("Problem saving data.")

def pad_history(history_list, total_length):
    base = history_list[:total_length]
    padding = [None] * (total_length - len(base))
    return base + padding

def color_outcome(val):
    if isinstance(val, str):
        if "WIN" in val:
            return 'color: #2e7d32; font-weight: bold'
        elif "LOSS" in val:
            return 'color: #c62828; font-weight: bold'
    return ''

# --- PAGES ---

def show_intro():
    st.title("Financial Decision Study")
    st.markdown(f"""
    Hello!
    Your ID: **{st.session_state.user_id}**.
    
    The study will take about 10 minutes and consists of 3 parts:
    1. Stock Market Game (40 rounds).
    2. Coin Flip Game (stake management - 30 rounds).
    3. Short Survey.
    """)
    if st.button("Start Study"):
        next_page('demographics')

def show_demographics():
    st.header("Demographics")
    st.markdown("Please fill in the basic information. **All fields are required.**")
    
    with st.form("demo"):
        # Q1: Age
        age = st.selectbox(
            "1. How old are you?",
            ["Under 18", "18–24", "25–34", "35–44", "45–54", "55–64", "65 or older"],
            index=None,
            placeholder="Select..."
        )
        
        # Q2: Gender
        gender = st.radio(
            "2. What is your gender?",
            ["Female", "Male", "Other / Prefer not to say"],
            index=None
        )
        
        # Q3: Education
        edu = st.selectbox(
            "3. Highest level of education completed:",
            ["Primary", "Secondary", "Bachelor/Engineer", "Master's", "PhD or higher"],
            index=None,
            placeholder="Select..."
        )
        
        # Q4: Field
        field = st.radio(
            "4. Is your education or job related to finance, economics, or capital markets?",
            ["Yes", "Partially", "No"],
            index=None
        )
        
        # Q5: Experience
        inv_exp = st.selectbox(
            "5. How do you rate your investment experience?",
            ["No experience", "Beginner", "Intermediate", "Advanced", "Professional"],
            index=None,
            placeholder="Select..."
        )
        
        # Q6: Real Investing
        real_inv = st.radio(
            "6. Have you ever invested real money (e.g., stocks, ETFs, crypto)?",
            ["Yes", "No"],
            index=None
        )
        
        # Q7: Risk
        st.write("7. How do you rate your willingness to take financial risk? (1-Very Low, 7-Very High)")
        risk = st.slider("Risk Level", 1, 7, 4, label_visibility="collapsed")
        
        submitted = st.form_submit_button("Next")
        
        if submitted:
            # VALIDATION
            required_fields = [age, gender, edu, field, inv_exp, real_inv]
            if any(f is None for f in required_fields):
                st.error("⚠️ Please answer all questions before proceeding.")
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

# --- GAME 1: MARKET ---

def show_game1_intro():
    st.header("Part 1: Investment Game")
    st.markdown("# 📈 📉 💰")
    
    st.markdown("""
<div class="instruction-card">
    <h3>Instructions:</h3>
    You are taking on the role of an investor. You have <b>40 rounds</b> (representing 40 months).
    <ul>
        <li>You start with <b>10,000 PLN</b> of virtual capital.</li>
        <li>In each round, you decide where to allocate your money:</li>
        <ul>
            <li><b>Index A:</b> S&P 500 </li>
            <li><b>Index B:</b> Nasdaq</li>
            <li><b>Cash:</b> Safe haven (0% return).</li>
        </ul>
        <li class="important-text">Your goal is to maximize profit.</li>
        <li>From round 20, <b>Leverage (x2)</b> will be available.</li>
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

    if st.button("I understand, let's play!"):
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
    
    st.subheader(f"Round {current_idx + 1} / {total_len} ({LABELS_TEXT[current_idx]})")
    
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Your Capital", f"{current_cap:.2f} PLN", f"{pct_change_show:.2f}%")
    
    chart_data = pd.DataFrame({
        "S&P 500": pad_history(st.session_state.g1_history_A, total_len),
        "Nasdaq": pad_history(st.session_state.g1_history_B, total_len),
        "Your Capital (🔴)": pad_history(st.session_state.g1_history_user, total_len)
    })
    
    st.line_chart(chart_data.iloc[:total_len], color=["#AAAAAA", "#4444FF", "#FF0000"])
    
    leverage_active = False
    if current_idx >= 20:
        st.warning("⚡ LEVERAGE UNLOCKED (x2)")
        leverage_active = st.checkbox("Use Leverage (x2 gains/losses)")

    st.write("Where do you invest for the next month?")
    col1, col2, col3 = st.columns(3)
    choice = None
    if col1.button("Index A (S&P 500)"): choice = 'A'
    if col2.button("Index B (Nasdaq)"): choice = 'B'
    if col3.button("Cash"): choice = 'Cash'

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
    st.header("Stock Market Game Summary")
    st.markdown("Congratulations, you finished Part 1! Here are your results against the market.")

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
    c1.metric("Your Result", f"{end_cap:.2f} PLN", f"{user_ret_pct:.2f}%")
    c2.metric("S&P 500 (Passive)", f"{idx_a_cap:.2f} PLN", f"{idx_a_ret_pct:.2f}%")
    c3.metric("Nasdaq (Passive)", f"{idx_b_cap:.2f} PLN", f"{idx_b_ret_pct:.2f}%")

    st.markdown("---")
    st.write("**Comparison Chart:**")
    
    chart_data = pd.DataFrame({
        "S&P 500": pad_history(st.session_state.g1_history_A, 40),
        "Nasdaq": pad_history(st.session_state.g1_history_B, 40),
        "Your Capital (🔴)": pad_history(st.session_state.g1_history_user, 40)
    })
    st.line_chart(chart_data, color=["#AAAAAA", "#4444FF", "#FF0000"])

    st.markdown("When you are ready, proceed to Part 2.")
    
    if st.button("Next: Part 2 (Coin Flip)"):
        next_page('game2_intro')

# --- GAME 2: COIN ---

def show_game2_intro():
    st.header("Part 2: The Coin Flip Bet")
    
    st.markdown("""
<div class="instruction-card">
    <h3>Rules:</h3>
    <ul>
        <li>💰 <b>Start:</b> You receive <b>100 PLN</b>.</li>
        <li>🎲 <b>Duration:</b> <b>30 rounds</b> of virtual coin flips.</li>
        <li>📊 <b>Probabilities (Fixed):</b>
            <ul>
                <li>🦅 <b>HEADS:</b> 60% chance (Win)</li>
                <li>📉 <b>TAILS:</b> 40% chance (Win)</li>
            </ul>
        </li>
        <li>⚙️ <b>Your decision in each round:</b>
            <ul>
                <li>Which side to bet on (Heads or Tails).</li>
                <li>What % of capital to bet (using slider).</li>
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

    if st.button("Start Coin Game"):
        next_page('game2_questions')

def show_game2_questions():
    st.header("Your Predictions")
    st.markdown("Before you start, please answer 3 questions regarding your expectations.")

    with st.form("pre_game2_survey"):
        
        st.markdown("**Question 1 — Expected Return**")
        st.markdown("What total return do you expect after 30 rounds?")
        q1 = st.radio(
            "Select one option:",
            [
                "Loss greater than −50%",
                "−50% to −20%",
                "−20% to 0%",
                "0% to +20%",
                "+20% to +50%",
                "Over +50%"
            ],
            index=None
        )
        st.markdown("---")

        st.markdown("**Question 2 — Loss Probability**")
        st.markdown("What is the probability that your capital will be lower than 100 PLN after 30 rounds?")
        q2 = st.radio(
            "Select range:",
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

        st.markdown("**Question 3 — Ruin Probability**")
        st.markdown("What is the probability that you will lose most of your capital (at least 80%) during the game?")
        q3 = st.radio(
            "Select range:",
            [
                "0–5%",
                "6–15%",
                "16–30%",
                "31–50%",
                "Over 50%"
            ],
            index=None
        )
        st.markdown("---")

        submitted = st.form_submit_button("Save Answers and Start Game")

        if submitted:
            if not all([q1, q2, q3]):
                st.error("⚠️ Please answer all 3 questions.")
            else:
                st.session_state.results['g2_pre_survey'] = {
                    "return_expect": q1,
                    "loss_prob": q2,
                    "ruin_prob": q3
                }
                next_page('game2')

def show_game2():
    if st.session_state.g2_round > 30:
        next_page('game2_summary')
        return

    st.subheader(f"Coin Flip: Round {st.session_state.g2_round} / 30")
    cap = st.session_state.g2_capital
    
    col_main, col_hist = st.columns([1, 1])
    
    with col_main:
        st.metric("Your Funds", f"{cap:.2f} PLN")
        
        if cap <= 0.01:
            st.error("Bankruptcy! You don't have funds to continue.")
            if st.button("Go to Summary"):
                next_page('game2_summary')
            return

        st.markdown("---")
        
        st.write("Betting Decision:")
        c_slider, c_val = st.columns([3, 2])
        
        with c_slider:
            bet_pct = st.slider(
                "% of capital to bet?", 
                min_value=0, 
                max_value=100, 
                value=10, 
                step=1
            )
        
        bet_amount = round(cap * (bet_pct / 100.0), 2)

        with c_val:
            st.metric("Bet Value", f"{bet_amount:.2f}")

        bet_side = st.radio("I bet on:", ["HEADS", "TAILS"], horizontal=True)
        
        st.markdown("---")

        if st.button("FLIP COIN", type="primary"):
            is_heads = random.random() < 0.6
            coin_result = "HEADS" if is_heads else "TAILS"
            
            user_chose_heads = "HEADS" in bet_side
            
            if (user_chose_heads and is_heads) or (not user_chose_heads and not is_heads):
                win = True
                pnl = bet_amount
                result_label = f"WIN ({coin_result})"
                st.success(f"It's {coin_result}! You win {bet_amount:.2f} PLN.")
            else:
                win = False
                pnl = -bet_amount
                result_label = f"LOSS ({coin_result})"
                st.error(f"It's {coin_result}. You lose {bet_amount:.2f} PLN.")

            st.session_state.g2_capital += pnl
            st.session_state.g2_history_chart.append(st.session_state.g2_capital)
            
            st.session_state.g2_table_data.insert(0, {
                "Round": st.session_state.g2_round,
                "Your Pick": "HEADS" if user_chose_heads else "TAILS",
                "Result": result_label,
                "Stake": f"{bet_amount:.2f} PLN",
                "% Cap": f"{bet_pct}%"
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
                time.sleep(0.5) 
                next_page('game2_summary')
            else:
                time.sleep(0.5)
                st.rerun()
        
        st.line_chart(st.session_state.g2_history_chart)

    with col_hist:
        st.write("### History")
        if st.session_state.g2_table_data:
            df_hist = pd.DataFrame(st.session_state.g2_table_data)
            st.dataframe(
                df_hist.style.map(color_outcome, subset=['Result']),
                height=500,
                width="stretch",
                hide_index=True
            )

def show_game2_summary():
    st.header("Summary: Coin Flip")
    
    start_cap = 100.0
    end_cap = st.session_state.g2_capital
    profit_pln = end_cap - start_cap
    roi_percent = (profit_pln / start_cap) * 100
    
    col1, col2 = st.columns(2)
    col1.metric("Final Capital", f"{end_cap:.2f} PLN", f"{roi_percent:.2f}%")
    col2.metric("Net Profit/Loss", f"{profit_pln:.2f} PLN")
    
    st.markdown("---")
    st.subheader("Capital History")
    
    st.line_chart(st.session_state.g2_history_chart)
    
    st.markdown("That's the end of the practical part. Only a short survey remains.")
    
    if st.button("Go to Survey"):
        next_page('survey')

# --- SURVEY (LIKERT) ---

LIKERT_MAP = {
    "1 – Strongly Disagree": 1,
    "2 – Disagree": 2,
    "3 – Neutral / Hard to say": 3,
    "4 – Agree": 4,
    "5 – Strongly Agree": 5
}
LIKERT_OPTIONS = list(LIKERT_MAP.keys())

def show_survey():
    scroll_to_top()

    st.header("Part 3: Opinions")
    
    st.markdown("""
    <style>
    .survey-question {
        color: #ffffff !important; 
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 10px;
    }
    .likert-legend {
        background-color: #ffffff;
        color: #000000;
        padding: 15px;
        border: 1px solid #cccccc;
        border-radius: 8px;
        margin-bottom: 25px;
        font-size: 0.9rem;
    }
    .stSlider [data-baseweb="slider"] div[data-testid="stMarkdownContainer"] p {
        font-weight: bold;
        color: #000000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("Please indicate to what extent you agree with the following statements.")

    st.markdown("""
    <div class="likert-legend">
        <b>Scale:</b> Move the slider to choose your answer.<br>
        From <b>1 (Strongly Disagree)</b> to <b>5 (Strongly Agree)</b>.
    </div>
    """, unsafe_allow_html=True)
    
    page_num = st.session_state.survey_page_num
    
    QUESTIONS_PER_PAGE = 6
    start_idx = (page_num - 1) * QUESTIONS_PER_PAGE
    end_idx = start_idx + QUESTIONS_PER_PAGE
    
    current_questions = FIXED_QUESTIONS[start_idx:end_idx]
    
    if page_num == 1:
        st.progress(50)
        btn_label = "Next (Page 2/2)"
    else:
        st.progress(100)
        btn_label = "Finish Study"

    with st.form(f"survey_form_likert_{page_num}"):
        for q_data in current_questions:
            st.markdown(f'<div class="survey-question">{q_data["q"]}</div>', unsafe_allow_html=True)
            
            val_str = st.select_slider(
                "Your rating:",
                options=LIKERT_OPTIONS,
                value="3 – Neutral / Hard to say",
                key=q_data['id'],
                label_visibility="collapsed"
            )
            st.markdown("---")
        
        submitted = st.form_submit_button(btn_label)
        
        if submitted:
            current_answers = {}
            for q in current_questions:
                selected_text = st.session_state[q['id']]
                numerical_val = LIKERT_MAP[selected_text]
                current_answers[q['id']] = numerical_val
            
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
elif st.session_state.page == 'game1_summary': show_game1_summary()
elif st.session_state.page == 'game2_intro': show_game2_intro()
elif st.session_state.page == 'game2_questions': show_game2_questions()
elif st.session_state.page == 'game2': show_game2()
elif st.session_state.page == 'game2_summary': show_game2_summary() 
elif st.session_state.page == 'survey': show_survey()
elif st.session_state.page == 'finish': show_finish()