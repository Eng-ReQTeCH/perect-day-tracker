import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CONFIG_FILE = "tasks.json"
EXCEL_FILE = "perfect_day_log.xlsx"
ACHIEVEMENTS_FILE = "achievements.json"
THEME_COLOR = "#1DB954"
BG_COLOR = '#121212'
TEXT_COLOR = '#FFFFFF'
GRID_COLOR = '#333333'

# ---- Data Loading & Persistence ----
def load_tasks():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            tasks = json.load(f)
        for name, props in list(tasks.items()):
            if isinstance(props, int):
                tasks[name] = {"weight": props, "color": THEME_COLOR}
        return tasks
    default = {
        "Study": {"weight": 20, "color": THEME_COLOR},
        "Bible Reading": {"weight": 15, "color": "#FF5722"},
        "Skincare": {"weight": 10, "color": "#9C27B0"},
        "Haircare": {"weight": 10, "color": "#03A9F4"},
        "Sunscreen": {"weight": 10, "color": "#FFC107"},
        "Exercise": {"weight": 10, "color": "#E91E63"},
        "Hydration": {"weight": 10, "color": "#2196F3"},
        "Meditation": {"weight": 5,  "color": "#8BC34A"},
        "Journaling": {"weight": 5,  "color": "#FF9800"},
        "Sleep Hygiene": {"weight": 5,  "color": "#607D8B"}
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(default, f, indent=4)
    return default


def load_achievements():
    if os.path.exists(ACHIEVEMENTS_FILE):
        with open(ACHIEVEMENTS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_achievements(achievements):
    with open(ACHIEVEMENTS_FILE, 'w') as f:
        json.dump(achievements, f, indent=4)


def has_n_day_streak(n, min_score=1):
    if not os.path.exists(EXCEL_FILE):
        return False
    df = pd.read_excel(EXCEL_FILE)
    df['Date'] = pd.to_datetime(df['Date'])
    daily = df.groupby('Date').Score.max().reset_index()
    today = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    days = set(today - pd.Timedelta(days=i) for i in range(n))
    good_days = set(daily[daily.Score >= min_score].Date.dt.normalize())
    return days.issubset(good_days)


def get_current_streak(min_score=1):
    if not os.path.exists(EXCEL_FILE):
        return 0
    df = pd.read_excel(EXCEL_FILE)
    df['Date'] = pd.to_datetime(df['Date'])
    daily = df.groupby('Date').Score.max().reset_index().sort_values('Date', ascending=False)
    streak = 0
    today = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    for _, row in daily.iterrows():
        expected = today - pd.Timedelta(days=streak)
        if row['Date'].normalize() == expected and row['Score'] >= min_score:
            streak += 1
        else:
            break
    return streak


def check_achievements(score, achievements):
    new = {}
    conditions = {
        "First 50%": lambda s: s >= 50,
        "First 100%": lambda s: s == 100,
        "Three Days Streak": lambda s: has_n_day_streak(3)
    }
    for key, cond in conditions.items():
        if key not in achievements and cond(score):
            achievements[key] = True
            new[key] = True
    return new


def submit_day(entry, tasks):
    score = sum(tasks[t]['weight'] for t, done in entry.items() if done)
    date = datetime.now().strftime('%Y-%m-%d')
    record = entry.copy()
    record.update({'Date': date, 'Score': score})
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
    else:
        df = pd.DataFrame(columns=['Date'] + list(tasks) + ['Score'])
    df = pd.concat([pd.DataFrame([record]), df[df.Date != date]], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)
    return df, score

# ---- Plotting ----
def plot_score(df):
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    fig, ax = plt.subplots(facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.plot(df['Date'], df['Score'], marker='o', color=THEME_COLOR)
    # constrain x-axis to data range
    ax.set_xlim(df['Date'].min(), df['Date'].max())
    # Show only day ticks
    locator = mdates.DayLocator()
    formatter = mdates.DateFormatter('%b %d')
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.autofmt_xdate()
    ax.set_title("Score Over Time", color=THEME_COLOR)
    ax.set_xlabel("Date", color=TEXT_COLOR)
    ax.set_ylabel("Score", color=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR)
    ax.grid(True, color=GRID_COLOR)
    return fig

# ---- Streamlit App ----
st.set_page_config(page_title="Perfect Day Tracker", layout="wide")
st.markdown("<style>body {background-color: #121212; color: #FFFFFF;} </style>", unsafe_allow_html=True)
st.title("🌟 My Perfect Day Tracker")

# Load data
tasks = load_tasks()
achievements = load_achievements()

# Read existing data
df_all = pd.read_excel(EXCEL_FILE) if os.path.exists(EXCEL_FILE) else pd.DataFrame()

# Layout: two columns
grid = st.columns([1, 2], gap="large")

with grid[0]:
    st.subheader("📝 Daily Checklist")
    with st.form("daily_form"):
        entry = {task: st.checkbox(f"{task} ({props['weight']}%)") for task, props in tasks.items()}
        submitted = st.form_submit_button("✅ Submit Day")
        if submitted:
            df_all, score = submit_day(entry, tasks)
            new_ach = check_achievements(score, achievements)
            save_achievements(achievements)
            st.success(f"🎯 Your Score: {score}%")
            if new_ach:
                st.balloons()
                st.info("New Achievements Unlocked:\n" + "\n".join(new_ach.keys()))

    # larger, bold streak
    streak = get_current_streak()
    st.markdown(f"<p style='font-size:24px; font-weight:bold; color:{THEME_COLOR};'>🔥 Current Streak: {streak} day{'s' if streak != 1 else ''}</p>", unsafe_allow_html=True)

    st.subheader("🏆 Achievements")
    for key in ["First 50%", "First 100%", "Three Days Streak"]:
        status = "✅" if achievements.get(key) else "❌"
        st.write(f"{status} {key}")

with grid[1]:
    if not df_all.empty:
        st.subheader("📈 Score Over Time")
        fig = plot_score(df_all)
        st.pyplot(fig)
