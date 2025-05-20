import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---- Configuration ----
CONFIG_FILE = "tasks.json"
SHEET_NAME = "Perfect Day Log"
ACHIEVEMENTS_FILE = "achievements.json"
THEME_COLOR = "#1DB954"
BG_COLOR = '#121212'
TEXT_COLOR = '#FFFFFF'
GRID_COLOR = '#333333'

# ---- Google Sheets Setup ----
def get_gsheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_json = st.secrets['gcp_service_account']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds)

# ---- Load Sheet ----
def load_sheet(task_names):
    client = get_gsheet_client()
    try:
        sheet = client.open(SHEET_NAME).sheet1
    except Exception:
        sheet = client.create(SHEET_NAME).sheet1
        sheet.append_row(['Date'] + task_names + ['Score'])
    try:
        records = sheet.get_all_records()
    except Exception:
        records = []
    df = pd.DataFrame(records)
    if df.empty or 'Date' not in df.columns:
        df = pd.DataFrame(columns=['Date'] + task_names + ['Score'])
    return df, sheet

# ---- Data Loading & Persistence ----
def load_tasks():
    if st.secrets.get('tasks_json'):
        return st.secrets['tasks_json']
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'Study': {'weight': 20, 'color': THEME_COLOR},
            'Bible Reading': {'weight': 15, 'color': '#FF5722'},
            'Skincare': {'weight': 10, 'color': '#9C27B0'},
            'Haircare': {'weight': 10, 'color': '#03A9F4'},
            'Sunscreen': {'weight': 10, 'color': '#FFC107'},
            'Exercise': {'weight': 10, 'color': '#E91E63'},
            'Hydration': {'weight': 10, 'color': '#2196F3'},
            'Meditation': {'weight': 5,  'color': '#8BC34A'},
            'Journaling': {'weight': 5,  'color': '#FF9800'},
            'Sleep Hygiene': {'weight': 5,  'color': '#607D8B'}
        }


def load_achievements():
    if os.path.exists(ACHIEVEMENTS_FILE):
        with open(ACHIEVEMENTS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_achievements(achievements):
    with open(ACHIEVEMENTS_FILE, 'w') as f:
        json.dump(achievements, f, indent=4)

# ---- Streak & Achievements ----
def has_n_day_streak(df, n, min_score=1):
    if df.empty:
        return False
    df['Date'] = pd.to_datetime(df['Date'])
    daily = df.groupby('Date').Score.max().reset_index()
    today = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    days = set(today - pd.Timedelta(days=i) for i in range(n))
    good = set(daily[daily.Score >= min_score].Date.dt.normalize())
    return days.issubset(good)


def get_current_streak(df, min_score=1):
    if df.empty:
        return 0
    df['Date'] = pd.to_datetime(df['Date'])
    daily = df.groupby('Date').Score.max().reset_index().sort_values('Date', ascending=False)
    streak = 0
    today = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    for _, row in daily.iterrows():
        if row['Date'].normalize() == today - pd.Timedelta(days=streak) and row['Score'] >= min_score:
            streak += 1
        else:
            break
    return streak


def check_achievements(score, achievements, df):
    new = {}
    conds = {
        'First 50%': lambda s: s >= 50,
        'First 100%': lambda s: s == 100,
        'Three Days Streak': lambda s: has_n_day_streak(df, 3)
    }
    for k, cond in conds.items():
        if k not in achievements and cond(score):
            achievements[k] = True
            new[k] = True
    return new

# ---- Plotting ----
def plot_score(df):
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    fig, ax = plt.subplots(facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.plot(df['Date'], df['Score'], marker='o', color=THEME_COLOR)
    if not df.empty:
        start = df['Date'].min() - pd.Timedelta(days=1)
        end = df['Date'].max() + pd.Timedelta(days=1)
        ax.set_xlim(start, end)
    ax.set_ylim(0, 100)
    locator = mdates.DayLocator()
    formatter = mdates.DateFormatter('%b %d')
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate()
    ax.set_title('Score Over Time', color=THEME_COLOR)
    ax.set_xlabel('Date', color=TEXT_COLOR)
    ax.set_ylabel('Score', color=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR)
    ax.grid(True, color=GRID_COLOR)
    return fig

# ---- Streamlit UI ----
st.set_page_config(page_title='Perfect Day Tracker', layout='wide')
st.markdown(f"<style>body{{background-color:{BG_COLOR};color:{TEXT_COLOR}}}</style>", unsafe_allow_html=True)
st.title("🌟 My Perfect Day Tracker")

# Load tasks
tasks = load_tasks()
task_names = list(tasks.keys())

# Load sheet
df_all, sheet = load_sheet(task_names)
achievements = load_achievements()

# Layout
cols = st.columns([1, 2], gap='large')

with cols[0]:
    st.subheader('📝 Daily Checklist')
    with st.form('daily_form'):
        entry = {t: st.checkbox(f"{t} ({tasks[t]['weight']}%)") for t in task_names}
        if st.form_submit_button('✅ Submit Day'):
            date = datetime.now().strftime('%Y-%m-%d')
            if date in df_all['Date'].astype(str).tolist():
                st.warning("You've already submitted your perfect day today.")
            else:
                score = sum(tasks[t]['weight'] for t, done in entry.items() if done)
                row = [date] + [int(entry[t]) for t in task_names] + [score]
                sheet.append_row(row)
                df_all.loc[len(df_all)] = row
                new = check_achievements(score, achievements, df_all)
                save_achievements(achievements)
                st.success(f"Your Score: {score}%")
                if new:
                    st.balloons()
                    st.info("Unlocked:\n" + "\n".join(new.keys()))

    streak = get_current_streak(df_all)
    st.markdown(
        f"<p style='font-size:24px;font-weight:bold;color:{THEME_COLOR}'>🔥 Current Streak: {streak} day{'s' if streak!=1 else ''}</p>",
        unsafe_allow_html=True
    )
    st.subheader('🏆 Achievements')
    for k in ['First 50%', 'First 100%', 'Three Days Streak']:
        st.write(f"{'✅' if achievements.get(k) else '❌'} {k}")

with cols[1]:
    if not df_all.empty:
        st.subheader('📈 Score Over Time')
        st.pyplot(plot_score(df_all))
