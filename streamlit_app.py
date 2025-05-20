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
META_SHEET_NAME = "Meta"
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

# ---- Load or Create Meta Sheet ----
def load_meta_sheet(spreadsheet):
    try:
        return spreadsheet.worksheet(META_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        meta = spreadsheet.add_worksheet(title=META_SHEET_NAME, rows=2, cols=2)
        meta.update_cell(1, 1, 'Streak')
        meta.update_cell(2, 1, 0)
        return meta

# ---- Load Data Sheet ----
def load_sheets(task_names):
    client = get_gsheet_client()
    try:
        spreadsheet = client.open(SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        spreadsheet = client.create(SHEET_NAME)
    # Data sheet
    sheet = spreadsheet.sheet1
    header = ['Date'] + task_names + ['Score']
    # ensure header
    existing = sheet.row_values(1)
    if existing != header:
        sheet.clear()
        sheet.append_row(header)
    # load data
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    if df.empty or 'Date' not in df.columns:
        df = pd.DataFrame(columns=header)
    # Meta sheet
    meta = load_meta_sheet(spreadsheet)
    return df, sheet, meta

# ---- Load Tasks & Achievements ----
def load_tasks():
    if st.secrets.get('tasks_json'):
        return st.secrets['tasks_json']
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_achievements():
    if os.path.exists(ACHIEVEMENTS_FILE):
        with open(ACHIEVEMENTS_FILE) as f:
            return json.load(f)
    return {}

def save_achievements(a):
    with open(ACHIEVEMENTS_FILE, 'w') as f:
        json.dump(a, f, indent=4)

# ---- Streak & Achievements ----
def has_n_day_streak(df, n):
    if df.empty: return False
    df['Date']=pd.to_datetime(df['Date'])
    daily = df.groupby('Date').Score.max().reset_index()
    today=pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    return all((today-pd.Timedelta(days=i)) in set(daily.Date.dt.normalize()) for i in range(n))

def get_current_streak(df):
    if df.empty: return 0
    df['Date']=pd.to_datetime(df['Date'])
    daily=df.groupby('Date').Score.max().reset_index().sort_values('Date',ascending=False)
    streak=0; today=pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    for _,row in daily.iterrows():
        if row.Date.normalize()==today-pd.Timedelta(days=streak): streak+=1
        else: break
    return streak

def check_achievements(score,a,df):
    new={}
    for k,cond in [('First 50%',score>=50),('First 100%',score==100),('Three Days Streak',has_n_day_streak(df,3))]:
        if cond and k not in a: a[k]=True; new[k]=True
    return new

# ---- Plotting ----
def plot_score(df):
    df['Date']=pd.to_datetime(df['Date'])
    df=df.sort_values('Date')
    fig,ax=plt.subplots(facecolor=BG_COLOR); ax.set_facecolor(BG_COLOR)
    ax.plot(df['Date'],df['Score'],marker='o',color=THEME_COLOR)
    if not df.empty:
        ax.set_xlim(df.Date.min()-pd.Timedelta(days=1),df.Date.max()+pd.Timedelta(days=1))
    ax.set_ylim(0,100)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    fig.autofmt_xdate()
    ax.set_title('Score Over Time',color=THEME_COLOR)
    ax.set_xlabel('Date',color=TEXT_COLOR); ax.set_ylabel('Score',color=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR); ax.grid(True,color=GRID_COLOR)
    return fig

# ---- App ----
st.set_page_config(page_title='Perfect Day Tracker',layout='wide')
st.markdown(f"<style>body{{background-color:{BG_COLOR};color:{TEXT_COLOR}}}</style>",unsafe_allow_html=True)
st.title('🌟 My Perfect Day Tracker')

tasks=load_tasks(); names=list(tasks.keys())
df_all,sheet,meta=load_sheets(names); ach=load_achievements()

cols=st.columns([1,2],gap='large')
with cols[0]:
    st.subheader('📝 Daily Checklist')
    with st.form('f'):
        entry={t:st.checkbox(f"{t} ({tasks[t]['weight']}%)") for t in names}
        if st.form_submit_button('✅ Submit Day'):
            date=datetime.now().strftime('%Y-%m-%d')
            score=sum(tasks[t]['weight'] for t,d in entry.items() if d)
            row=[date]+[int(entry[t]) for t in names]+[score]
            if date in df_all.Date.astype(str).tolist():
                df_all.loc[df_all.Date.astype(str)==date]=row
            else:
                df_all.loc[len(df_all)]=row
            # rewrite sheet
            sheet.clear()
            sheet.append_row(['Date']+names+['Score'])
            sheet.append_rows(df_all.values.tolist())
            new=check_achievements(score,ach,df_all)
            save_achievements(ach)
            streak=get_current_streak(df_all)
            meta.clear(); meta.update_cell(1,1,'Streak'); meta.update_cell(2,1,streak)
            st.success(f"Your Score: {score}%")
            if new: st.balloons(); st.info('Unlocked:\n'+"\n".join(new.keys()))
    # display streak
    raw=meta.acell('A2').value
    try: sv=int(raw)
    except: sv=0
    st.markdown(f"<p style='font-size:24px;color:{THEME_COLOR}'>🔥 Current Streak: {sv} day{'s' if sv!=1 else ''}</p>",unsafe_allow_html=True)
    st.subheader('🏆 Achievements')
    for k in ['First 50%','First 100%','Three Days Streak']: st.write(f"{'✅' if ach.get(k) else '❌'} {k}")
with cols[1]:
    if not df_all.empty: st.subheader('📈 Score Over Time'); st.pyplot(plot_score(df_all))
