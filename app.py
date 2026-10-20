from __future__ import annotations

import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent
DB_PATH = Path(os.getenv("STUDYMATE_DB", ROOT / "data" / "studymate.db"))
TIMETABLE_PATH = ROOT / "data" / "timetable.xlsx"
DAYS = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين", "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}
st.set_page_config(page_title="StudyMate | المساعد الأكاديمي", page_icon="🎓", layout="wide")

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, student_no TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL, year INTEGER NOT NULL, salt BLOB NOT NULL, password_hash BLOB NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL, course TEXT NOT NULL DEFAULT '', due_date TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.commit()
    return con

def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

@st.cache_data
def load_timetable(file_bytes: bytes):
    book = pd.ExcelFile(io.BytesIO(file_bytes))
    out = []
    for sheet in book.sheet_names:
        raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=None, dtype=object)
        hdr = None
        for r in range(min(8, len(raw))):
            vals = [norm(v).lower() for v in raw.iloc[r].tolist()]
            if "day" in vals and "time" in vals:
                hdr = r
                break
        if hdr is None:
            continue
        vals = [norm(v).lower() for v in raw.iloc[hdr].tolist()]
        day_col, time_col = vals.index("day"), vals.index("time")
        group_row = hdr + 1
        group_cols = []
        for c, v in enumerate(raw.iloc[group_row].tolist()):
            if c > time_col and pd.notna(v) and norm(v).isdigit():
                group_cols.append((c, norm(v)))
        if not group_cols:
            group_cols = [(c, str(c - time_col)) for c in range(time_col + 1, raw.shape[1])]
        current_day = ""
        for r in range(group_row + 1, len(raw)):
            day_val, time_val = raw.iat[r, day_col], raw.iat[r, time_col]
            if pd.notna(day_val) and norm(day_val):
                current_day = norm(day_val)
            if not current_day or pd.isna(time_val) or not norm(time_val):
                continue
            for c, group in group_cols:
                if c >= raw.shape[1]:
                    continue
                cell = raw.iat[r, c]
                if pd.notna(cell) and norm(cell):
                    out.append({"year": int(re.search(r"\d+", sheet).group()), "day_en": current_day, "day": DAYS.get(current_day, current_day), "time": norm(time_val), "group": group, "details": norm(cell), "subject": norm(cell).split("\n")[0], "sheet": sheet})
    return pd.DataFrame(out)

if not TIMETABLE_PATH.exists():
    st.error("ملف الجدول الرسمي غير موجود في data/timetable.xlsx")
    st.stop()
lessons = load_timetable(TIMETABLE_PATH.read_bytes())
LIGHT_THEME = bool(st.session_state.get("light_mode", False))

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
html{font-size:16px!important} html,body,[class*="css"]{font-family:'Cairo','Noto Sans Arabic',Tahoma,Arial,sans-serif} .stApp{background:#071226;color:#e7eaf0;font-size:16px!important;line-height:1.65}
[data-testid="stHeader"]{background:rgba(11,15,25,.96)}
[data-testid="stSidebar"]{background:#071326;border-right:1px solid #172e52;min-width:300px!important}
[data-testid="stSidebar"] .block-container{padding:1.15rem .85rem}
section.main>div.block-container{max-width:1400px;padding:1.25rem 2rem 8rem}
.brand-row{display:flex;align-items:center;gap:.65rem;font-size:1.18rem;font-weight:800;letter-spacing:.01em;padding:.35rem .25rem .65rem;color:#f6f7f9}
.brand-icon{width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;border-radius:11px;background:linear-gradient(140deg,#786cff,#5248c8);box-shadow:0 5px 18px #625cff38}
.profile-chip{display:flex;align-items:center;gap:.65rem;padding:.72rem .75rem;margin:.45rem 0 1rem;border:1px solid #292c34;background:#17191f;border-radius:14px;color:#e8e9ed;font-size:.88rem}
.profile-avatar{width:34px;height:34px;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#282a34;color:#c4bcff;font-weight:700}
.section-label{font-size:.9rem;font-weight:750;letter-spacing:.04em;color:#a9b9d3;text-transform:uppercase;margin:.9rem .6rem .45rem}
.chat-head{display:flex;align-items:center;justify-content:space-between;padding:.55rem .15rem 1rem;margin-bottom:.35rem;border-bottom:1px solid #20232a;color:#f0f1f4;font-size:.94rem;font-weight:650}
.hero{padding:1rem 1.15rem;border:1px solid #272d3b;border-radius:18px;background:linear-gradient(125deg,#141a27,#12151e);margin:.2rem 0 1rem}
.hero h1{margin:0;color:#f4f6fb;font-size:1.55rem!important}.hero p{margin:.3rem 0 0;color:#9ca6b8;font-size:.88rem}
.chat-status{padding:.28rem .7rem;border:1px solid #25416b;background:#102347;border-radius:999px;color:#b7c8e5;font-size:.88rem;font-weight:650}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:.25rem 0 .9rem;border-bottom:1px solid #232731;margin-bottom:1rem}
.hero-panel{position:relative;overflow:hidden;min-height:218px;padding:1.6rem 1.8rem;border:1px solid #203864;border-radius:20px;background:radial-gradient(ellipse at 88% 20%,#253f89 0,transparent 36%),linear-gradient(120deg,#0e1b38,#111d3c 58%,#15163b);box-shadow:0 18px 50px #0003;margin-bottom:1rem}
.hero-panel:after{content:'✦';position:absolute;right:7%;top:12%;font-size:5rem;color:#8ba5ff44;text-shadow:0 0 40px #555bff66}
.hero-kicker{color:#91aaff;font-size:.8rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.hero-panel h1{font-size:1.95rem!important;line-height:1.45;color:#f7f8ff;margin:.4rem 0 .3rem;max-width:650px}
.hero-panel p{color:#b5c4e3;font-size:.92rem;line-height:1.75;max-width:650px;margin:0}
.tool-card{border:1px solid #26344f;border-radius:16px;background:linear-gradient(145deg,#121b2c,#111722);padding:.9rem 1rem;min-height:82px;margin-bottom:.65rem}
.tool-card b{display:block;font-size:1.05rem;color:#ecf0fa;margin-bottom:.18rem}.tool-card span{font-size:.92rem;color:#aebbd2}
.rail-card{border:1px solid #242c3c;border-radius:18px;background:linear-gradient(150deg,#111a2a,#10141f);padding:1rem 1.05rem;margin-bottom:.8rem}
.rail-card h3{font-size:1.12rem!important;margin:.1rem 0 .7rem;color:#eef2fc}.rail-card p{font-size:.98rem;color:#b6c3d8;line-height:1.7;margin:.2rem 0}
.progress-line{display:flex;justify-content:space-between;gap:.5rem;border-top:1px solid #263957;padding:.6rem 0 .15rem;color:#bdcbe0;font-size:.95rem}
.home-composer{border:1px solid #30394d;background:#101827;border-radius:16px;padding:.6rem;margin-top:.9rem}
.conversation-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:.5rem;margin-top:-.35rem}
.delete-confirm{padding:.9rem 1rem;border:1px solid #603c43;border-radius:14px;background:#24171b;color:#f3dfe2;margin:.5rem 0 1rem}
.welcome-chat{min-height:40vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:1rem 1.2rem .5rem}
.welcome-mark{width:66px;height:66px;border-radius:21px;background:linear-gradient(145deg,#8a7dff 0%,#6855ee 55%,#4d47cc 100%);display:flex;align-items:center;justify-content:center;font-size:2rem;color:#fff;box-shadow:0 12px 40px #7163ff3b, inset 0 1px 0 #ffffff55;margin-bottom:1.1rem}
.welcome-chat h1{font-size:2.15rem!important;letter-spacing:-.035em;color:#f7f8fa;margin:.15rem 0 .45rem;font-weight:750}
.welcome-chat p{max-width:570px;color:#a0a4af;font-size:1rem;line-height:1.85;margin:0}
.suggestion-label{font-size:.8rem;font-weight:600;color:#868a95;margin:.3rem 0 .7rem}
.suggestion-grid{border:1px solid #292c34;border-radius:16px;background:linear-gradient(140deg,#15171e,#12141a);padding:.35rem;}
.profile-chip span:last-child{display:block}
.sidebar-caption{font-size:.86rem;color:#a8b6cd}
.stButton>button{border-radius:12px;border:1px solid #303746;background:#151a25;color:#e8ebf2;min-height:2.8rem;transition:all .16s ease}
[data-testid="stButton"]>button{font-family:'Cairo',sans-serif}
[data-testid="stSidebar"] [data-testid="stButton"]>button{min-height:2.8rem;border-color:transparent;background:transparent;text-align:right;padding:.5rem .8rem;font-size:1rem;font-weight:600;color:#d0def3}
[data-testid="stSidebar"] [data-testid="stButton"]>button:hover{border-color:#30333c;background:#1b1d24;color:#fff}
[data-testid="stSidebar"] [data-testid="stButton"]>button[kind="primary"]{background:#252631;border-color:#333541;color:#fff}
.stButton>button:hover{border-color:#776dff;background:#1d1c2a;color:white;transform:translateY(-1px)}
[data-testid="stChatMessage"]{border:1px solid #1d3559;border-radius:20px;padding:1.15rem 1.3rem;margin:1rem 0;background:linear-gradient(145deg,#0e1b31,#101d33)}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){background:linear-gradient(145deg,#15254a,#111d38);border-color:#304c82}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"]{font-size:1.08rem;line-height:1.85;font-weight:500}
[data-testid="stChatInput"]{border:1px solid #393b45;border-radius:20px;background:#181a21;box-shadow:0 14px 50px #0007;padding:.4rem}
[data-testid="stChatInput"] textarea{font-family:'Cairo',sans-serif;font-size:1.12rem;color:#f2f4f8;min-height:3.3rem}
[data-testid="stChatInput"]:focus-within{border-color:#8278ff;box-shadow:0 0 0 1px #8278ff44,0 14px 50px #0007}
[data-testid="stSelectbox"] div[data-baseweb="select"]>div{background:#17191f;border-color:#30333b;border-radius:10px}
[data-testid="stRadio"] label{padding:.2rem 0}
.stCaption{color:#8f99a9}
.stMarkdown p,.stMarkdown li,.stText,.stCaption,div[data-testid="stWidgetLabel"]{font-size:1rem;line-height:1.75}
.stButton>button{font-size:1rem;font-weight:650;min-height:3rem}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"]{font-size:.95rem;font-weight:700}
.hero{background:linear-gradient(125deg,#0f1c35,#111b32);border-color:#20365b}.hero p{font-size:1rem;color:#b7c4da}.hero h1,.chat-head{font-weight:800}
@media(max-width:700px){section.main>div.block-container{padding:1rem .75rem 7rem}.welcome-chat{min-height:35vh}.welcome-chat h1{font-size:1.65rem!important}[data-testid="stSidebar"]{min-width:250px!important}.stMarkdown p,.stMarkdown li{font-size:.98rem}}
</style>""", unsafe_allow_html=True)
if LIGHT_THEME:
    st.markdown("""
    <style>
    .stApp{background:#f4f6fb!important;color:#202636!important}
    [data-testid="stSidebar"]{background:#fff!important;border-color:#e5e8f0!important}
    [data-testid="stSidebar"] *,section.main *{color:inherit}
    .brand-row,.profile-chip,.rail-card h3,.tool-card b{color:#202636!important}
    .profile-chip,.rail-card,.tool-card,.suggestion-grid{background:#fff!important;border-color:#e1e5ee!important}
    .section-label,.sidebar-caption,.suggestion-label{color:#737b8c!important}
    .hero-panel{background:radial-gradient(ellipse at 88% 20%,#cbd7ff 0,transparent 36%),linear-gradient(120deg,#eaf0ff,#f2f3ff 58%,#eeedff)!important;border-color:#d7def4!important}
    .hero-panel h1{color:#1e2946!important}.hero-panel p{color:#586886!important}
    [data-testid="stChatMessage"]{background:#fff!important;border-color:#e2e5ec!important}
    [data-testid="stChatInput"]{background:#fff!important;border-color:#d9deea!important}
    [data-testid="stChatInput"] textarea{color:#202636!important}
    .chat-head{color:#202636!important;border-color:#e2e5ec!important}
    </style>""", unsafe_allow_html=True)

def header(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)

def tr(ar, en):
    return ar if st.session_state.get("language", "العربية") == "العربية" else en

def configured_api_key():
    key = os.getenv("GROQ_API_KEY", "")
    if key:
        return key
    try:
        return str(st.secrets.get("GROQ_API_KEY", ""))
    except Exception:
        return ""

def configured_gemini_api_key():
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        return str(st.secrets.get("GEMINI_API_KEY", ""))
    except Exception:
        return ""

def transcribe_audio(audio_bytes: bytes, mime_type: str, api_key: str) -> str:
    import base64
    import requests
    payload = {"contents": [{"role": "user", "parts": [
        {"text": "Transcribe the spoken audio accurately, preserving its language. Return only the transcript."},
        {"inline_data": {"mime_type": mime_type or "audio/wav", "data": base64.b64encode(audio_bytes).decode("ascii")}},
    ]}]}
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
        params={"key": api_key}, json=payload, timeout=60,
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

def voice_player(message: str, lang: str):
    # Uses the browser's built-in speech voices; audio stays on the user's device.
    text_json = json.dumps(message, ensure_ascii=False)
    lang_json = json.dumps(lang)
    button_label = html.escape(tr("استمع للرد", "Listen to reply"))
    components.html(f'''<button id="speak" style="font:600 14px Cairo,Arial;color:#dbe8ff;background:#142747;border:1px solid #355589;border-radius:10px;padding:8px 13px;cursor:pointer">🔊 {button_label}</button>
    <script>
      const text = {text_json}, lang = {lang_json};
      document.getElementById('speak').onclick = () => {{
        if (!('speechSynthesis' in window)) {{ alert('Speech synthesis is unavailable in this browser.'); return; }}
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang; utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
      }};
    </script>''', height=52)

def current_user():
    if "user_id" not in st.session_state:
        return None
    with db() as con:
        return con.execute("SELECT * FROM users WHERE id=?", (st.session_state.user_id,)).fetchone()

def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)

def auth_screen():
    st.sidebar.radio("Language / اللغة", ["العربية", "English"], key="language", horizontal=True)
    ar = st.session_state.language == "العربية"
    header("🎓 StudyMate", tr("رفيقك الأكاديمي — جدول رسمي، ملفات، ومحادثات محفوظة", "Your academic companion — official timetable, files, and saved chats"))
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("### " + tr("مساحة دراسية في مكان واحد", "Your study space in one place"))
        st.write(tr("تابع جدول علوم البيانات للفرق الأربعة، اسأل مساعدك، ارفع محاضراتك، ونظّم مذاكرتك.", "View the four-year Data Science timetable, ask your assistant, upload lectures, and plan your study."))
        st.caption(tr("تسجيل الحساب هنا تجريبي ولا يتحقق من الرقم الجامعي عبر نظام الجامعة.", "Demo registration does not verify student numbers with the university."))
    with right:
        mode = st.radio(tr("الحساب", "Account"), [tr("تسجيل الدخول", "Sign in"), tr("إنشاء حساب", "Create account")], horizontal=True)
        with st.form("auth"):
            student_no = st.text_input(tr("الرقم الجامعي", "Student number"))
            name = st.text_input(tr("الاسم الظاهر", "Display name")) if mode == tr("إنشاء حساب", "Create account") else ""
            year = st.selectbox(tr("الفرقة", "Year"), [1, 2, 3, 4]) if mode == tr("إنشاء حساب", "Create account") else 1
            password = st.text_input(tr("كلمة المرور", "Password"), type="password")
            go = st.form_submit_button(tr("متابعة", "Continue"), type="primary", use_container_width=True)
        if go:
            no = student_no.strip()
            if not no or not password:
                st.error(tr("أدخل الرقم الجامعي وكلمة المرور.", "Enter your student number and password."))
            elif mode == tr("إنشاء حساب", "Create account") and (len(password) < 8 or not name.strip()):
                st.error(tr("اكتب اسمك واختر كلمة مرور من 8 أحرف على الأقل.", "Enter your name and choose a password with at least 8 characters."))
            else:
                with db() as con:
                    user = con.execute("SELECT * FROM users WHERE student_no=?", (no,)).fetchone()
                    if mode == tr("إنشاء حساب", "Create account"):
                        if user:
                            st.error(tr("هذا الرقم مسجل بالفعل.", "That student number is already registered."))
                        else:
                            salt = secrets.token_bytes(16)
                            cur = con.execute("INSERT INTO users(student_no,display_name,year,salt,password_hash) VALUES(?,?,?,?,?)", (no, name.strip(), year, salt, hash_password(password, salt)))
                            con.commit(); st.session_state.user_id = cur.lastrowid; st.rerun()
                    elif user and hmac.compare_digest(user["password_hash"], hash_password(password, user["salt"])):
                        st.session_state.user_id = user["id"]; st.rerun()
                    else:
                        st.error(tr("بيانات الدخول غير صحيحة.", "Incorrect sign-in details."))

user = current_user()
if not user:
    auth_screen(); st.stop()

if st.session_state.get("app_ui_version") != "reference-layout-1":
    st.session_state.app_ui_version = "reference-layout-1"
    st.session_state.app_page = "home"

with st.sidebar:
    st.markdown('<div class="brand-row"><span class="brand-icon">✦</span>StudyMate</div>', unsafe_allow_html=True)
    display_name = html.escape(user["display_name"])
    st.markdown(f'<div class="profile-chip"><span class="profile-avatar">{display_name[:1]}</span><span><b>{display_name}</b><br><span class="sidebar-caption">{tr("الفرقة", "Year")} {user["year"]} · Data Science</span></span></div>', unsafe_allow_html=True)
    st.radio("Language / اللغة", ["العربية", "English"], key="language", horizontal=True)
    with db() as con:
        chats = con.execute("SELECT c.* FROM chats c LEFT JOIN messages m ON m.chat_id=c.id WHERE c.user_id=? GROUP BY c.id HAVING COUNT(m.id)>0 OR c.id=(SELECT MAX(id) FROM chats WHERE user_id=?) ORDER BY c.id DESC", (user["id"], user["id"])).fetchall()
        if st.button(tr("＋ محادثة جديدة", "＋ New chat"), use_container_width=True, type="primary") or not chats:
            cur = con.execute("INSERT INTO chats(user_id,title) VALUES(?,?)", (user["id"], tr("محادثة جديدة", "New chat")))
            con.commit(); st.session_state.active_chat_id = cur.lastrowid; st.rerun()
    chat_ids = [c["id"] for c in chats]
    if chat_ids:
        active = st.session_state.get("active_chat_id", chat_ids[0])
        if active not in chat_ids:
            active = chat_ids[0]
            st.session_state.active_chat_id = active
        st.markdown(f'<div class="section-label">{tr("محادثاتك", "Your chats")}</div>', unsafe_allow_html=True)
        for chat in chats[:12]:
            chat_title = html.escape(chat["title"][:32])
            icon = "✦" if chat["id"] == active else "·"
            title_col, delete_col = st.columns([.83, .17])
            if title_col.button(f"{icon}  {chat_title}", key=f"chat_{chat['id']}", use_container_width=True, type="primary" if chat["id"] == active else "secondary"):
                st.session_state.active_chat_id = chat["id"]; st.rerun()
            if delete_col.button("🗑", key=f"delete_chat_{chat['id']}", help=tr("حذف المحادثة", "Delete chat")):
                st.session_state.confirm_delete_chat_id = chat["id"]; st.rerun()
    st.markdown(f'<div class="section-label">{tr("مساحة العمل", "Workspace")}</div>', unsafe_allow_html=True)
    nav_items = [("home", "الرئيسية", "Home", "⌂"), ("chat", "المحادثة", "Chat", "◉"), ("quiz", "الاختبارات", "Quizzes", "☑"), ("tasks", "المهام والتكليفات", "Tasks & assignments", "✓"), ("timetable", "الجدول الرسمي", "Timetable", "▦"), ("doctors", "البحث عن دكتور", "Find an instructor", "♙"), ("files", "الملفات وPDF", "Files & PDF", "▤"), ("flashcards", "البطاقات التعليمية", "Flashcards", "▧"), ("planner", "خطة المذاكرة", "Study planner", "◷"), ("reports", "المشاريع والتقارير", "Projects & reports", "▣"), ("resources", "مصادر الدراسة", "Study resources", "⌕"), ("about", "عن المشروع", "About", "ⓘ")]
    current_page = st.session_state.get("app_page", "home")
    for key, ar_label, en_label, icon in nav_items:
        label = ar_label if st.session_state.language == "العربية" else en_label
        if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True, type="primary" if current_page == key else "secondary"):
            st.session_state.app_page = key; st.rerun()
    page = st.session_state.get("app_page", "home")
    if st.button(tr("تسجيل الخروج", "Sign out"), use_container_width=True):
        st.session_state.pop("user_id", None); st.rerun()

if st.session_state.get("confirm_delete_chat_id") and st.session_state.get("confirm_delete_chat_id") != st.session_state.get("active_chat_id"):
    delete_id = st.session_state.confirm_delete_chat_id
    delete_title = next((c["title"] for c in chats if c["id"] == delete_id), tr("هذه المحادثة", "this conversation"))
    st.sidebar.markdown(f'<div class="delete-confirm">{tr("حذف المحادثة؟", "Delete this chat?")}<br><span class="sidebar-caption">{html.escape(delete_title)}</span></div>', unsafe_allow_html=True)
    confirm_col, cancel_col = st.sidebar.columns(2)
    if confirm_col.button(tr("حذف", "Delete"), key="confirm_chat_delete", type="primary", use_container_width=True):
        with db() as con:
            con.execute("DELETE FROM chats WHERE id=? AND user_id=?", (delete_id, user["id"]))
            con.commit()
        if st.session_state.get("active_chat_id") == delete_id:
            st.session_state.pop("active_chat_id", None)
        st.session_state.pop("confirm_delete_chat_id", None)
        st.rerun()
    if cancel_col.button(tr("إلغاء", "Cancel"), key="cancel_chat_delete", use_container_width=True):
        st.session_state.pop("confirm_delete_chat_id", None); st.rerun()

if page == "home":
    main_col, rail_col = st.columns([3.15, 1.05], gap="medium")
    with main_col:
        brand_col, ask_col, send_col, theme_col = st.columns([1.25, 3.2, .38, .55], vertical_alignment="center")
        with brand_col:
            st.markdown('<div class="brand-row"><span class="brand-icon">✦</span><span>StudyMate</span></div>', unsafe_allow_html=True)
        with ask_col:
            home_ask = st.text_input("", placeholder=tr("اسأل عن مادة أو مفهوم أو واجب...", "Ask about a course, concept, or assignment..."), label_visibility="collapsed", key="home_ask")
        with send_col:
            send_home = st.button("➤", key="send_home_ask", help=tr("إرسال", "Send"), use_container_width=True)
        with theme_col:
            st.toggle(tr("فاتح", "Light"), key="light_mode", help=tr("تبديل المظهر", "Toggle appearance"))

        name = html.escape(user["display_name"].split()[0])
        st.markdown(f'<div class="hero-panel"><div class="hero-kicker">SMART ACADEMIC ASSISTANT</div><h1>{tr("أهلاً بيك", "Hello")}, {name} 👋<br>{tr("أنا مساعدك الأكاديمي الذكي", "I’m your Smart Academic Assistant")}</h1><p>{tr("اسألني عن دراستك، جدولك، البرمجة، أو ارفع محاضرة عشان نشتغل عليها سوا.", "Ask about your courses, timetable, coding, or upload a lecture and we’ll work through it together.")}</p></div>', unsafe_allow_html=True)

        st.markdown(f'<div class="section-label">{tr("ابدأ من هنا", "GET STARTED")}</div>', unsafe_allow_html=True)
        tools = [
            ("💡", tr("شرح المفاهيم", "Explain a concept"), tr("شرح مبسط خطوة بخطوة", "Clear, step-by-step explanations"), "chat", tr("اشرحلي مفهوم صعب في علوم البيانات بمثال بسيط" , "Explain a difficult Data Science concept with a simple example")),
            ("▦", tr("الجدول الدراسي", "Official timetable"), tr("ابحث حسب الفرقة والمجموعة", "Search by year and group"), "timetable", None),
            ("▤", tr("الملفات والمحاضرات", "Files & lectures"), tr("استخرج النص ولخص PDF وDOCX", "Extract and summarize PDF or DOCX"), "files", None),
            ("◷", tr("خطة المذاكرة", "Study planner"), tr("قسّم هدفك على أيام واضحة", "Break goals into daily sessions"), "planner", None),
            ("☑", tr("اختبارات قصيرة", "Quick quizzes"), tr("حوّل ملاحظاتك لأسئلة استرجاع", "Turn notes into recall prompts"), "quiz", None),
            ("✓", tr("المهام والتكليفات", "Tasks & assignments"), tr("رتّب التسليمات ومواعيدها", "Track coursework and due dates"), "tasks", None),
        ]
        for row in range(3):
            card_cols = st.columns(2, gap="small")
            for col, (icon, title, desc, route, prompt_text) in zip(card_cols, tools[row*2:row*2+2]):
                with col:
                    st.markdown(f'<div class="tool-card"><b>{icon} &nbsp; {title}</b><span>{desc}</span></div>', unsafe_allow_html=True)
                    if st.button(tr("فتح الأداة  ↗", "Open tool  ↗"), key=f"home_tool_{route}", use_container_width=True):
                        st.session_state.app_page = route
                        if prompt_text: st.session_state.pending_prompt = prompt_text
                        st.rerun()

        st.markdown(f'<div class="section-label">{tr("ابدأ محادثة", "START A CONVERSATION")}</div>', unsafe_allow_html=True)
        ask_col, send_col = st.columns([5, .7])
        with ask_col:
            st.markdown(f'<div class="home-composer"><span style="color:#8e9bb2">{tr("اكتب رسالتك هنا... اسأل، خطط، أو اطلب شرحاً", "Type a message... ask, plan, or request an explanation")}</span></div>', unsafe_allow_html=True)
        with send_col:
            if st.button(tr("دردشة", "Chat"), key="home_open_chat", use_container_width=True):
                st.session_state.app_page = "chat"; st.rerun()
        if send_home and home_ask.strip():
            st.session_state.app_page = "chat"; st.session_state.pending_prompt = home_ask.strip(); st.rerun()
        home_prompt = st.chat_input(tr("اكتب رسالتك إلى StudyMate...", "Type your message to StudyMate..."), key="home_message_input")
        if home_prompt:
            st.session_state.app_page = "chat"; st.session_state.pending_prompt = home_prompt; st.rerun()

    with rail_col:
        st.markdown(f'<div class="rail-card"><h3>✦ {tr("ذاكر بذكاء", "Study Smarter")}</h3><p>{tr("خطوات صغيرة كل يوم تصنع فرقاً كبيراً. خلينا نرتب يومك الدراسي.", "Small steps every day lead to big results. Let’s organize your study day.")}</p></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-label">{tr("وصول سريع", "QUICK ACTIONS")}</div>', unsafe_allow_html=True)
        rail_actions = [("💬", tr("المساعد الأكاديمي", "Chat assistant"), "chat"), ("📄", tr("تحليل ملف", "Analyze a file"), "files"), ("☑", tr("إنشاء اختبار", "Create a quiz"), "quiz"), ("✓", tr("إضافة مهمة", "Add a task"), "tasks"), ("▦", tr("عرض الجدول", "View timetable"), "timetable"), ("♙", tr("البحث عن دكتور", "Find an instructor"), "doctors")]
        for icon, label, route in rail_actions:
            if st.button(f"{icon}  {label}  ›", key=f"rail_{route}", use_container_width=True):
                st.session_state.app_page = route; st.rerun()
        with db() as con:
            stats = con.execute("SELECT COUNT(DISTINCT CASE WHEN m.id IS NOT NULL THEN c.id END), COUNT(m.id) FROM chats c LEFT JOIN messages m ON m.chat_id=c.id WHERE c.user_id=?", (user["id"],)).fetchone()
            open_tasks = con.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND done=0", (user["id"],)).fetchone()[0]
        course_count = int(lessons[lessons.year == user["year"]].subject.nunique())
        st.markdown(f'<div class="rail-card"><h3>◌ {tr("تقدمك", "Your activity")}</h3><div class="progress-line"><span>{tr("مواد في الجدول", "Courses in timetable")}</span><b>{course_count}</b></div><div class="progress-line"><span>{tr("محادثات محفوظة", "Saved chats")}</span><b>{stats[0]}</b></div><div class="progress-line"><span>{tr("رسائل", "Messages")}</span><b>{stats[1]}</b></div><div class="progress-line"><span>{tr("مهام مفتوحة", "Open tasks")}</span><b>{open_tasks}</b></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="rail-card"><h3>✧ {tr("نصيحة اليوم", "Tip for today")}</h3><p>{tr("جرّب تراجع المعلومة بعد ما تخلص المحاضرة مباشرة؛ الاسترجاع النشط يساعدك تثبتها.", "Review a concept soon after class. Active recall helps it stick.")}</p></div>', unsafe_allow_html=True)

elif page == "chat":
    chat_col, tools_rail = st.columns([3.25, 1.1], gap="large")
    with chat_col:
        with db() as con:
            selected = st.session_state.get("active_chat_id", chat_ids[0] if chat_ids else None)
            if selected is None:
                cur = con.execute("INSERT INTO chats(user_id,title) VALUES(?,?)", (user["id"], tr("محادثة جديدة", "New chat")))
                con.commit(); selected = cur.lastrowid; st.session_state.active_chat_id = selected
            msgs = con.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id", (selected,)).fetchall()
            title = con.execute("SELECT title FROM chats WHERE id=?", (selected,)).fetchone()["title"]
        safe_title = html.escape(title)
        head_col, action_col = st.columns([5.8, 1.2])
        with head_col:
            st.markdown(f'<div class="chat-head" style="color:#f0f1f4!important;opacity:1!important"><span style="color:#f0f1f4!important">StudyMate <span style="color:#a5a7b0!important;font-weight:450">· {safe_title}</span></span><span class="chat-status">{tr("محفوظة", "Saved")}</span></div>', unsafe_allow_html=True)
        with action_col:
            if action_col.button(tr("🗑 حذف", "🗑 Delete"), key=f"delete_open_chat_{selected}", help=tr("حذف هذه المحادثة", "Delete this conversation"), use_container_width=True):
                st.session_state.confirm_delete_chat_id = selected; st.rerun()
        if st.session_state.get("confirm_delete_chat_id") == selected:
            st.warning(tr(f'سيتم حذف «{title}» وكل رسائلها نهائياً. هل تريد المتابعة؟', f'Delete “{title}” and all its messages permanently?'))
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button(tr("تأكيد الحذف", "Confirm delete"), key=f"confirm_open_chat_{selected}", type="primary"):
                with db() as con:
                    con.execute("DELETE FROM chats WHERE id=? AND user_id=?", (selected, user["id"]))
                    con.commit()
                st.session_state.pop("active_chat_id", None)
                st.session_state.pop("confirm_delete_chat_id", None)
                st.rerun()
            if cancel_col.button(tr("إلغاء", "Cancel"), key=f"cancel_open_chat_{selected}"):
                st.session_state.pop("confirm_delete_chat_id", None); st.rerun()
        if not msgs:
            st.markdown(f'<div class="welcome-chat"><div class="welcome-mark">✦</div><h1>{tr("أهلاً بيك، أقدر أساعدك في إيه؟", "What can I help you with?")}</h1><p>{tr("مساعدك الأكاديمي للدراسة والبرمجة والجدول. اكتب سؤالك بطريقتك، وهنتكلم بشكل طبيعي.", "Your study partner for courses, coding, and your timetable. Ask naturally and we’ll work through it together.")}</p></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="suggestion-label">{tr("اختار نقطة بداية", "Choose a starting point")}</div>', unsafe_allow_html=True)
            prompts = [tr("▦  جدول", "▦  timetable"), tr("✦  اشرحلي مفهوم صعب", "✦  Explain a difficult concept"), tr("▤  ساعدني ألخص محاضرة", "▤  Summarize a lecture with me"), tr("◷  اعملي خطة مذاكرة", "◷  Build a study plan")]
            for row in range(2):
                cols = st.columns(2)
                for col, suggestion in zip(cols, prompts[row*2:row*2+2]):
                    if col.button(suggestion, use_container_width=True, key=f"suggest_{row}_{suggestion}"):
                        st.session_state.pending_prompt = suggestion.split(" ", 1)[1].strip()
                        st.rerun()
        else:
            for msg in msgs:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg["role"] == "assistant":
                        voice_player(msg["content"], "ar-EG" if st.session_state.get("language", "العربية") == "العربية" else "en-US")
        api_key = configured_api_key()
        gemini_api_key = configured_gemini_api_key()
        audio_col, upload_col = st.columns([1, 1])
        with audio_col:
            audio_recording = st.audio_input(tr("🎙️ سجّل رسالتك الصوتية", "🎙️ Record a voice message"), key=f"voice_{selected}")
        with upload_col:
            audio_file = st.file_uploader(tr("📎 أو ارفع تسجيلًا", "📎 Or upload a recording"), type=["wav", "mp3", "m4a", "ogg", "webm", "flac"], key=f"voice_file_{selected}")
        prompt = st.chat_input(tr("اكتب رسالتك أو سجّل صوتك...", "Type or record your message..."))
        audio_source = None
        audio_hash_key = f"last_audio_hash_{selected}"
        if audio_recording is not None:
            recording_hash = hashlib.sha256(audio_recording.getvalue()).hexdigest()
            if recording_hash != st.session_state.get(audio_hash_key):
                audio_source = audio_recording
        if audio_source is None and audio_file is not None:
            upload_hash = hashlib.sha256(audio_file.getvalue()).hexdigest()
            if upload_hash != st.session_state.get(audio_hash_key):
                audio_source = audio_file
        if audio_source is not None:
            audio_bytes = audio_source.getvalue()
            audio_hash = hashlib.sha256(audio_bytes).hexdigest()
            if not gemini_api_key:
                st.session_state[audio_hash_key] = audio_hash
                st.warning(tr("التسجيل وصل، لكن تحويل الصوت إلى نص يحتاج إضافة مفتاح Gemini في إعدادات التطبيق. تقدر تكتب رسالتك الآن.", "Recording received. Speech transcription needs a Gemini API key in app settings; you can type your message meanwhile."))
            elif len(audio_bytes) > 15 * 1024 * 1024:
                st.error(tr("التسجيل كبير جدًا. ارفع ملفًا أصغر من 15 ميجابايت.", "The recording is too large. Upload a file under 15 MB."))
                st.session_state[audio_hash_key] = audio_hash
            else:
                try:
                    with st.spinner(tr("بفهم التسجيل الصوتي...", "Transcribing your recording...")):
                        prompt = transcribe_audio(audio_bytes, audio_source.type, gemini_api_key)
                    st.session_state[audio_hash_key] = audio_hash
                    if prompt:
                        st.caption(tr("النص المستخرج من التسجيل:", "Transcript:"))
                        st.info(prompt)
                except Exception as exc:
                    st.session_state[audio_hash_key] = audio_hash
                    st.error(tr(f"تعذر فهم التسجيل ({type(exc).__name__}). جرّب تسجيلًا أقصر أو اكتب رسالتك.", f"Couldn't transcribe the recording ({type(exc).__name__}). Try a shorter clip or type your message."))
        prompt = prompt or st.session_state.pop("pending_prompt", None)
        if prompt:
            with db() as con:
                con.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)", (selected, "user", prompt))
                if len(msgs) == 0: con.execute("UPDATE chats SET title=? WHERE id=?", (prompt[:42], selected))
                con.commit()
            answer = None
            if re.search(r"جدول|محاضرة|مادة|قاعة|lecture|timetable|class", prompt, re.I):
                terms = [x for x in re.findall(r"[A-Za-z][A-Za-z ]{2,}|[\u0600-\u06ff]{3,}(?:\s+[\u0600-\u06ff]{3,})?", prompt) if x.lower() not in {"جدول", "محاضرة", "مادة", "قاعة", "timetable", "lecture", "class"}]
                subset = lessons[lessons.year == user["year"]]
                if terms:
                    mask = False
                    for term in terms: mask = mask | subset.details.str.contains(re.escape(term.strip()), case=False, na=False)
                    subset = subset[mask]
                if len(subset):
                    lines = [f"• **{r.day}، {r.time} — مجموعة {r.group}:** {r.details.replace(chr(10), ' · ')}" for r in subset.head(12).itertuples()]
                    answer = "لقيت دي في جدول الفرقة " + str(user["year"]) + ":\n\n" + "\n".join(lines)
                else: answer = "ما لقيتش تطابق واضح في جدول الفرقة. جرّب اسم المادة بالإنجليزية أو افتح صفحة الجدول واختر المجموعة المناسبة."
            api_key = configured_api_key()
            if not answer and api_key:
                try:
                    from groq import Groq

                    client = Groq(api_key=api_key)

                    history = [
                        {
                            "role": (
                                "assistant"
                                if m["role"] == "assistant"
                                else "user"
                            ),
                            "content": m["content"],
                        }
                        for m in msgs[-12:]
                    ]

                    history.append({
                        "role": "user",
                        "content": prompt,
                    })

                    system_text = (
                        "You are StudyMate, a helpful academic assistant. "
                        "Help with studying, programming, writing, planning, "
                        "and general questions. Reply in the user's language, "
                        "including Arabic when appropriate. Be clear and "
                        "natural. Do not invent facts or references."
                    )

                    response = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[
                            {
                                "role": "system",
                                "content": system_text,
                            },
                            *history,
                        ],
                        temperature=0.7,
                        max_tokens=1500,
                    )

                    answer = (
                        response.choices[0].message.content
                        or "معلش، مجاليش رد. جرّب تاني."
                    )

                except Exception as exc:
                    answer = (
                        f"حصل خطأ في Groq ({type(exc).__name__}). "
                        "راجع مفتاح API والاتصال وحدود الاستخدام."
                    )
            if not answer:
                answer = "أقدر أبحث لك في الجدول الرسمي وأحفظ المحادثة، لكن الرد المفتوح يحتاج إضافة GROQ_API_KEY اختياري في إعدادات الاستضافة. اكتب مثلاً: جدول مادة Statistics أو موعد Web Application Development."
            with db() as con:
                con.execute("INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)", (selected, "assistant", answer)); con.commit()
            st.rerun()

    with tools_rail:
        st.markdown(f'<div class="rail-card"><h3>✦ {tr("أدوات الذكاء الاصطناعي", "AI Tools")}</h3><p>{tr("اختار أداة وابدأ فورًا", "Choose a tool to get started")}</p></div>', unsafe_allow_html=True)
        chat_tools = [("💬", tr("مساعد عام", "General assistant"), "chat"), ("⌘", tr("مساعد البرمجة", "Code assistant"), "chat"), ("📄", tr("تحليل الملفات", "Document analyzer"), "files"), ("☑", tr("إنشاء اختبار", "Quiz generator"), "quiz"), ("◷", tr("خطة مذاكرة", "Study planner"), "planner")]
        for icon, label, destination in chat_tools:
            if st.button(f"{icon}  {label}", key=f"chat_tool_{destination}_{label}", use_container_width=True):
                st.session_state.app_page = destination
                st.rerun()
        st.markdown(f'<div class="rail-card"><h3>🔗 {tr("روابط سريعة", "Quick links")}</h3><p>{tr("الجدول الرسمي", "Official timetable")}</p><p>{tr("المهام والتكليفات", "Tasks & assignments")}</p><p>{tr("الملفات والمصادر", "Files & resources")}</p></div>', unsafe_allow_html=True)

elif page == "tasks":
    header(tr("✅ المهام والتكليفات", "✅ Tasks & assignments"), tr("تابع واجباتك ومواعيد التسليم في مكان واحد.", "Keep coursework and due dates organized in one place."))
    with st.form("create_task", clear_on_submit=True):
        task_title = st.text_input(tr("اسم المهمة أو التكليف", "Task or assignment"))
        task_course = st.text_input(tr("المادة", "Course"))
        task_due = st.date_input(tr("موعد التسليم", "Due date"), value=date.today() + timedelta(days=7))
        add_task = st.form_submit_button(tr("＋ إضافة مهمة", "＋ Add task"), type="primary", use_container_width=True)
    if add_task and task_title.strip():
        with db() as con:
            con.execute("INSERT INTO tasks(user_id,title,course,due_date) VALUES(?,?,?,?)", (user["id"], task_title.strip(), task_course.strip(), task_due.isoformat()))
            con.commit()
        st.success(tr("تمت إضافة المهمة.", "Task added."))
    with db() as con:
        task_rows = con.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY done, due_date, id DESC", (user["id"],)).fetchall()
    if not task_rows:
        st.info(tr("مافيش مهام لسه. أضف أول تكليف من النموذج.", "No tasks yet. Add your first assignment above."))
    for task in task_rows:
        check_col, info_col, delete_col = st.columns([.55, 5, .7])
        checked = check_col.checkbox("✓", value=bool(task["done"]), key=f"task_check_{task['id']}", label_visibility="collapsed")
        if checked != bool(task["done"]):
            with db() as con:
                con.execute("UPDATE tasks SET done=? WHERE id=? AND user_id=?", (int(checked), task["id"], user["id"]))
                con.commit()
            st.rerun()
        info_col.markdown(f"**{html.escape(task['title'])}**  \n{html.escape(task['course'] or tr('بدون مادة محددة', 'No course selected'))} · {task['due_date']}")
        if delete_col.button("🗑", key=f"task_delete_{task['id']}", help=tr("حذف المهمة", "Delete task")):
            st.session_state.confirm_delete_task_id = task["id"]; st.rerun()
    delete_task_id = st.session_state.get("confirm_delete_task_id")
    if delete_task_id:
        st.warning(tr("حذف هذه المهمة؟", "Delete this task?"))
        yes_col, no_col = st.columns(2)
        if yes_col.button(tr("تأكيد الحذف", "Confirm delete"), key="task_delete_yes", type="primary"):
            with db() as con:
                con.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (delete_task_id, user["id"]))
                con.commit()
            st.session_state.pop("confirm_delete_task_id", None); st.rerun()
        if no_col.button(tr("إلغاء", "Cancel"), key="task_delete_no"):
            st.session_state.pop("confirm_delete_task_id", None); st.rerun()

elif page == "quiz":
    header(tr("❓ منشئ الاختبارات", "❓ Quiz generator"), tr("حوّل نص المحاضرة إلى أسئلة استرجاع مع إجابات مرجعية.", "Turn lecture notes into recall questions with reference answers."))
    quiz_text = st.text_area(tr("الصق جزءاً من المحاضرة أو ملاحظاتك", "Paste a lecture passage or your notes"), height=210, key="quiz_source")
    quiz_count = st.slider(tr("عدد الأسئلة", "Number of questions"), 1, 10, 5)
    if st.button(tr("إنشاء أسئلة", "Generate questions"), type="primary"):
        candidates = [s.strip() for s in re.split(r"(?<=[.!؟?])\s+|\n+", quiz_text) if len(s.strip().split()) >= 5]
        st.session_state.quiz_items = candidates[:quiz_count]
        if not candidates: st.warning(tr("أضف نصاً فيه جمل واضحة علشان أقدر أشتق منه أسئلة.", "Add clear sentences so questions can be derived from the passage."))
    for idx, sentence in enumerate(st.session_state.get("quiz_items", []), 1):
        st.markdown(f"**{idx}. {tr('اشرح الفكرة دي بكلماتك:', 'Explain this idea in your own words:')}**")
        with st.expander(tr("إظهار الإجابة المرجعية", "Show reference answer")):
            st.write(sentence)
    st.caption(tr("الأسئلة مشتقة من النص المقدم وليست مولدة دلالياً. استخدم مفتاح Groq للمحادثة التوليدية العامة.", "Questions are derived from the text, not generated semantically. General generative chat requires a Groq API key."))

elif page == "doctors":
    header(tr("🔎 البحث في جدول أعضاء التدريس", "🔎 Find an instructor in the timetable"), tr("ابحث بالاسم أو المادة أو القاعة في جدول فرقتك.", "Search instructor, course, or room in your year’s timetable."))
    teacher_query = st.text_input(tr("اسم الدكتور أو جزء منه", "Instructor name or keyword"))
    teacher_rows = lessons[lessons.year == user["year"]]
    if teacher_query.strip():
        teacher_rows = teacher_rows[teacher_rows.details.str.contains(teacher_query.strip(), case=False, na=False)]
    else:
        st.info(tr("اكتب اسماً أو مادة لعرض النتائج المطابقة.", "Enter an instructor or course name to see matching classes."))
    if len(teacher_rows):
        result = teacher_rows[["day", "time", "group", "subject", "details"]].rename(columns={"day":tr("اليوم","Day"),"time":tr("الوقت","Time"),"group":tr("المجموعة","Group"),"subject":tr("المادة","Course"),"details":tr("التفاصيل","Details")})
        st.dataframe(result, use_container_width=True, hide_index=True)
    elif teacher_query.strip():
        st.warning(tr("ما لقيتش تطابق في جدول الفرقة الحالية.", "No matching entries found for your year."))

elif page == "flashcards":
    header(tr("🗂️ البطاقات التعليمية", "🗂️ Flashcards"), tr("حوّل ملاحظاتك إلى بطاقات مراجعة سريعة.", "Turn your notes into quick review cards."))
    notes = st.text_area(tr("الصق ملاحظاتك أو تعريفاتك", "Paste your notes or definitions"), height=180, key="flashcard_notes")
    if st.button(tr("إنشاء بطاقات", "Create flashcards"), type="primary"):
        st.session_state.flashcard_items = [s.strip() for s in re.split(r"(?<=[.!؟?])\s+|\n+", notes) if len(s.strip().split()) >= 4][:20]
    for idx, sentence in enumerate(st.session_state.get("flashcard_items", []), 1):
        with st.expander(f"{tr('بطاقة', 'Card')} {idx} · {tr('اكشف الإجابة', 'Reveal answer')}"):
            st.write(sentence)
    if not st.session_state.get("flashcard_items"):
        st.caption(tr("كل جملة واضحة تصبح بطاقة. الأداة محلية ولا ترسل النص إلى خدمة خارجية.", "Each clear sentence becomes a card. This tool runs locally and does not send notes to an external service."))

elif page == "reports":
    header(tr("📝 المشاريع والتقارير", "📝 Projects & reports"), tr("ابدأ بهيكل تقرير منظم وعدّله قبل التسليم.", "Start from a structured report outline and edit it before submission."))
    report_title = st.text_input(tr("عنوان المشروع", "Project title"), value=tr("مشروع علوم البيانات", "Data Science project"))
    sections = [tr("المقدمة", "Introduction"), tr("المشكلة", "Problem statement"), tr("الأهداف", "Objectives"), tr("المنهجية", "Methodology"), tr("النتائج", "Results"), tr("المراجع", "References")]
    default_report = f"# {report_title}\n\n" + "\n\n".join(f"## {section}\n\n{tr('اكتب محتوى هذا القسم هنا.', 'Write this section here.') }" for section in sections)
    report_body = st.text_area(tr("حرر التقرير", "Edit the report"), default_report, height=360)
    st.download_button(tr("تنزيل التقرير بصيغة Markdown", "Download Markdown report"), report_body, file_name="study-report.md", mime="text/markdown")

elif page == "resources":
    header(tr("📚 مصادر وأدوات الدراسة", "📚 Study resources & tools"), tr("اختصارات مباشرة لأدوات المشروع ومقررات الفرقة.", "Shortcuts to project tools and courses in your year."))
    res_cols = st.columns(2)
    for col, label, route in [(res_cols[0],tr("الجدول الرسمي","Official timetable"),"timetable"),(res_cols[1],tr("تحليل الملفات","Document analyzer"),"files"),(res_cols[0],tr("اختبار من ملاحظاتك","Quiz from notes"),"quiz"),(res_cols[1],tr("خطة المذاكرة","Study plan"),"planner")]:
        if col.button(label, key=f"resource_{route}", use_container_width=True): st.session_state.app_page=route; st.rerun()
    subjects = sorted(lessons[lessons.year == user["year"]].subject.dropna().unique().tolist())
    st.subheader(tr("مواد ظاهرة في جدولك", "Courses in your timetable"))
    st.write(" · ".join(subjects) if subjects else tr("لا توجد مواد في الجدول.", "No courses found."))

elif page == "timetable":
    header(tr("🗓️ الجدول الرسمي", "🗓️ Official timetable"), tr("الفرقة والمجموعة مأخوذتان من حسابك؛ تقدر تغيّر المجموعة للعرض.", "Your year is selected from your account; choose a group to view."))
    year = st.selectbox(tr("الفرقة", "Year"), [1, 2, 3, 4], index=user["year"] - 1)
    year_data = lessons[lessons.year == year]
    groups = sorted(year_data.group.unique(), key=lambda x: int(x) if x.isdigit() else x)
    group = st.selectbox(tr("المجموعة", "Group"), groups) if groups else None
    query = st.text_input(tr("ابحث باسم المادة أو المدرس أو القاعة", "Search subject, instructor, or room"))
    view = year_data[year_data.group == group] if group else year_data
    if query.strip(): view = view[view.details.str.contains(query.strip(), case=False, na=False)]
    st.caption(f"{len(view)} محاضرة أو معمل · مصدر البيانات: ملف الكلية المرفق")
    show = view.rename(columns={"day":"اليوم", "time":"الوقت", "group":"المجموعة", "details":"المادة / المدرس / القاعة"})[["اليوم", "الوقت", "المجموعة", "المادة / المدرس / القاعة"]]
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.download_button("تنزيل الجدول المعروض CSV", show.to_csv(index=False).encode("utf-8-sig"), "timetable.csv", "text/csv")
    st.caption("الفرقة الأولى والثانية بها مجموعات متعددة. بيانات الخلايا المنسقة جُمعت من ورقة كل فرقة، وقد توجد صيغ قاعات بديلة داخل الخلية كما وردت في الملف.")

elif page == "files":
    header(tr("📚 قراءة المحاضرات", "📚 Lecture reader"), tr("PDF وDOCX وTXT مع استخراج النص؛ OCR للملفات المصورة عند تثبيت Tesseract.", "Extract text from PDF, DOCX, and TXT; scanned PDF OCR requires Tesseract."))
    f = st.file_uploader(tr("ارفع ملف محاضرة", "Upload a lecture file"), type=["pdf", "docx", "txt"])
    if f:
        extracted = ""
        try:
            if f.name.lower().endswith(".pdf"):
                from pypdf import PdfReader
                extracted = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(f.getvalue())).pages)
                if not extracted.strip():
                    try:
                        import pytesseract
                        from pdf2image import convert_from_bytes
                        images = convert_from_bytes(f.getvalue(), dpi=180)
                        extracted = "\n".join(pytesseract.image_to_string(im, lang="ara+eng") for im in images)
                    except Exception:
                        st.warning("الملف يبدو مصوراً. ثبّت Tesseract مع حزم اللغات العربية والإنجليزية وPoppler لتفعيل OCR.")
            elif f.name.lower().endswith(".docx"):
                from docx import Document
                extracted = "\n".join(p.text for p in Document(io.BytesIO(f.getvalue())).paragraphs)
            else: extracted = f.getvalue().decode("utf-8", errors="replace")
            if extracted.strip():
                st.text_area("النص المستخرج", extracted, height=300)
                sentences = [s.strip() for s in re.split(r"(?<=[.!؟?])\s+|\n+", extracted) if s.strip()]
                summary = "\n".join("• " + s for s in sentences[:10])
                st.subheader("ملخص استخراجي سريع"); st.write(summary)
                st.download_button("تنزيل النص", extracted, f"{Path(f.name).stem}-text.txt")
        except Exception as exc: st.error(f"تعذرت قراءة الملف: {exc}")
    st.caption("الملفات تُعالج داخل جلسة التطبيق ولا تُحفظ في قاعدة البيانات. لا ترفع بيانات شخصية حساسة.")

elif page == "planner":
    header(tr("📆 خطتك الدراسية", "📆 Your study plan"), tr("خطة بسيطة قابلة للتعديل تساعدك تبدأ.", "A simple editable plan to help you get started."))
    subject = st.text_input(tr("المادة أو الهدف", "Subject or goal"))
    days = st.slider(tr("عدد الأيام", "Number of days"), 1, 21, 7)
    hrs = st.slider(tr("ساعات يومياً", "Hours per day"), 1, 8, 2)
    if st.button(tr("إنشاء الخطة", "Create plan"), type="primary"):
        plan = pd.DataFrame([{"اليوم": (date.today()+timedelta(days=i)).isoformat(), "الموضوع": subject or "مراجعة المحاضرات", "الجلسة": f"{hrs} ساعة: فهم المفاهيم، استرجاع نشط، وحل أسئلة"} for i in range(days)])
        st.dataframe(plan, use_container_width=True, hide_index=True)
        st.download_button("تنزيل الخطة CSV", plan.to_csv(index=False).encode("utf-8-sig"), "study-plan.csv")

else:
    header(tr("عن المشروع", "About the project"), tr("نسخة عرض قابلة للتطوير ومناسبة لفتحها في VS Code.", "An extensible demo project, ready to open in VS Code."))
    st.markdown("""
**المتاح:** تسجيل وحسابات محلية، حفظ محادثات SQLite، بحث من أوراق Excel الرسمية للأربع فرق، دعم عربي وإنجليزي، استخراج PDF النصي/DOCX/TXT، وOCR اختياري.

**مهم:** التسجيل لا يتحقق من هوية الطالب عبر الجامعة. لتشغيل دردشة توليدية عامة أضف `GROQ_API_KEY` كـ Secret؛ تكاليف وحدود الخدمة تتبع حساب Groq. تحويل التسجيلات الصوتية إلى نص اختياري ويحتاج `GEMINI_API_KEY`. بدون مفتاح Groq، يتوفر البحث في الجدول فقط. OCR العربي يحتاج برامج خارجية مثبتة على خادم الاستضافة.

قاعدة SQLite المحلية مناسبة للديمو. على الاستضافة المجانية قد يُعاد ضبط القرص؛ فعّل قرصاً دائماً أو استخدم قاعدة بيانات مُدارة قبل مشاركة الحسابات الفعلية. استخدم HTTPS ولا تضع المفتاح داخل الكود أو Git.
""")
