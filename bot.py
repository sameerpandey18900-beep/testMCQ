
import os
import uuid
import sqlite3
import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio

TELEGRAM_TOKEN = os.environ.get("8379093665:AAFKQKg4K8Zsi0TS5b2p2evmSvbcBNSi_YQ")
LITESHORT_API_KEY = os.environ.get("be1528376cd25a510dce1e3e063ed856e5421250")
SERVER_URL = os.environ.get("https://testmcq.onrender.com")  # e.g., https://myapp.onrender.com/activate
DB = "database.db"

bot = Bot(TELEGRAM_TOKEN)
dp = Dispatcher()

# --- Database ---
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS tokens (
        user_id INTEGER,
        session_id TEXT,
        expiry TEXT,
        status TEXT
    )""")
    conn.commit()
    conn.close()

def save_session(user_id, session_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO tokens VALUES (?,?,?,?)",
              (user_id, session_id, None, "pending"))
    conn.commit()
    conn.close()

def activate_session(session_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    expiry = (datetime.now() + timedelta(hours=24)).isoformat()
    c.execute("UPDATE tokens SET expiry=?, status='active' WHERE session_id=?",
              (expiry, session_id))
    conn.commit()
    conn.close()

def check_access(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT expiry, status FROM tokens WHERE user_id=? ORDER BY rowid DESC LIMIT 1", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[1] == "active":
        expiry = datetime.fromisoformat(row[0])
        if expiry > datetime.now():
            return True, expiry
    return False, None

# --- LiteShort link generator ---
def shorten_link(session_id):
    long_url = f"{SERVER_URL}?session={session_id}"
    api_url = f"https://liteshort.com/api?api={LITESHORT_API_KEY}&url={long_url}&format=text"
    resp = requests.get(api_url)
    if resp.status_code == 200 and resp.text.strip():
        return resp.text.strip()
    return long_url

# --- Telegram Handlers ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    session_id = str(uuid.uuid4())
    save_session(user_id, session_id)
    short_url = shorten_link(session_id)
    await message.answer(f"🔓 Click this link to unlock 24h access:\n{short_url}")

@dp.message(Command("timeleft"))
async def timeleft_handler(message: types.Message):
    user_id = message.from_user.id
    ok, expiry = check_access(user_id)
    if ok:
        remaining = expiry - datetime.now()
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        await message.answer(f"⏱ You have {hours}h {minutes}m left of access.")
    else:
