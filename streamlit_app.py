import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---- Configuration ----
SHEET_NAME = "Perfect Day Log"
META_SHEET_NAME = "Meta"
ACH_SHEET_NAME = "Achievements"
OBJ_SHEET_NAME = "Objectives"
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

# ---- Ensure Worksheet ----
def ensure_ws(spreadsheet, title, headers):
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=100, cols=len(headers))
        ws.append_row(headers)
    return ws

# ---- Load Sheets ----
def load_sheets():():
    client = get_gsheet_client()
    try:
        spreadsheet = client.open(SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        spreadsheet = client.create(SHEET_NAME)
    # Objectives sheet
    obj_ws = ensure_ws(spreadsheet, OBJ_SHEET_NAME, ['Objective', 'Weight'])
    obj_records = obj_ws.get_all_records()
    tasks = {r['Objective']: int(r['Weight']) for r in obj_records}
    # Data sheet
    sheet = spreadsheet.sheet1
    headers = ['Date'] + list(tasks.keys()) + ['Score']
    if sheet.row_values(1) != headers:
        sheet.clear(); sheet.append_row(headers)
    df = pd.DataFrame(sheet.get_all_records())
    if df.empty or 'Date' not in df.columns:
        df = pd.DataFrame(columns=headers)
    # Meta and Achievements
    meta = ensure_ws(spreadsheet, META_SHEET_NAME, ['Streak'])
    ach_ws = ensure_ws(spreadsheet, ACH_SHEET_NAME, ['Achievement', 'Unlocked'])
    return tasks, df, sheet, meta, ach_ws

# ---- Streak & Achievements ----
def has_n_day_streak(df, n):
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    dates = set(df['Date'].dt.normalize().dropna())
    today = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    return all((today - pd.Timedelta(days=i)) in dates for i in range(n))

def get_current_streak(df):
    if df.empty: return 0
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    dates = sorted(set(df['Date'].dt.normalize().dropna()), reverse=True)
    streak = 0; today = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    for i, d in enumerate(dates):
        if today - pd.Timedelta(days=i) == d: streak += 1
        else: break
    return streak

def check_achievements(score, df, ach_ws):
    existing = [r['Achievement'] for r in ach_ws.get_all_records()]
    new = []
    for name, cond in [('First 50%', score>=50), ('First 100%', score==100), ('Three Days Streak', has_n_day_streak(df,3))]:
        if cond and name not in existing:
            ach_ws.append_row([name, datetime.now().strftime('%Y-%m-%d')])
            new.append(name)
    return new

# ---- Plotting ----
def plot_score(df):
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.sort_values('Date')
    fig, ax = plt.subplots(facecolor=BG_COLOR); ax.set_facecolor(BG_COLOR)
    ax.plot(df['Date'], df['Score'], marker='o', color=THEME_COLOR)
    if not df.empty:
        ax.set_xlim(df['Date'].min()-pd.Timedelta(days=1), df['Date'].max()+pd.Timedelta(days=1))
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_locator(mdates.DayLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    fig.autofmt_xdate(); ax.set_title('Score Over Time', color=THEME_COLOR)
    ax.set_xlabel('Date', color=TEXT_COLOR); ax.set_ylabel('Score', color=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR); ax.grid(True, color=GRID_COLOR)
    return fig

# ---- App ----
st.set_page_config(page_title='Perfect Day Tracker', layout='wide')
st.markdown(f"<style>body{{background-color:{BG_COLOR};color:{TEXT_COLOR}}}</style>", unsafe_allow_html=True)
st.title('🌟 My Perfect Day Tracker')

tasks, df_all, sheet, meta, ach_ws = load_sheets()
names = list(tasks.keys())
cols = st.columns([1,2], gap='large')
with cols[0]:
    st.subheader('📝 Daily Checklist')
    with st.form('f'):
        entry = {t: st.checkbox(f"{t} ({tasks[t]}%)") for t in names}
        if st.form_submit_button('✅ Submit Day'):
            date = datetime.now().strftime('%Y-%m-%d')
            row = [date] + [int(entry[t]) for t in names] + [sum(tasks[t] for t,done in entry.items() if done)]
            if date in df_all['Date'].astype(str).tolist(): df_all.loc[df_all['Date'].astype(str)==date] = row
            else: df_all.loc[len(df_all)] = row
            sheet.clear(); sheet.append_row(['Date']+names+['Score']); sheet.append_rows(df_all.values.tolist())
            streak = get_current_streak(df_all)
            meta.clear(); meta.append_row(['Streak']); meta.append_row([streak])
            new = check_achievements(row[-1], df_all, ach_ws)
            if new: st.balloons(); st.info('Unlocked:\n'+"\n".join(new))
            st.success(f"Your Score: {row[-1]}%")
    cs = meta.cell(2,1).value or '0'
    st.markdown(f"<p style='font-size:24px;color:{THEME_COLOR}'>🔥 Current Streak: {cs} day{'s' if cs!='1' else ''}</p>", unsafe_allow_html=True)
    st.subheader('🏆 Achievements')
    for rec in ach_ws.get_all_records(): st.write(f"✅ {rec['Achievement']} ({rec['Unlocked']})")
with cols[1]:
    if not df_all.empty: st.subheader('📈 Score Over Time'); st.pyplot(plot_score(df_all))
