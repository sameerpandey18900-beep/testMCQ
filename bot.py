import os
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
import requests

# --- Credentials from environment variables ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
LITESHORT_API_KEY = os.environ.get("LITESHORT_API_KEY")
SERVER_URL = os.environ.get("SERVER_URL")

if not TELEGRAM_TOKEN or not LITESHORT_API_KEY or not SERVER_URL:
    raise ValueError("❌ Missing environment variables")

# --- Bot setup ---
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- Database ---
DB = "database.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER,
            expiry TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Activate session ---
def activate_session(session_id, user_id=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    expiry = (datetime.now() + timedelta(hours=24)).isoformat()
    c.execute("""
        INSERT OR REPLACE INTO tokens (session_id, user_id, expiry, status)
        VALUES (?, ?, ?, 'active')
    """, (session_id, user_id, expiry))
    conn.commit()
    conn.close()

    if user_id:
        asyncio.create_task(send_access_message(user_id, expiry))

# --- Send access granted message with edited countdown ---
async def send_access_message(user_id, expiry):
    hours = (expiry - datetime.now()).seconds // 3600
    minutes = ((expiry - datetime.now()).seconds % 3600) // 60
    msg: Message = await bot.send_message(user_id, f"✅ Access granted!\n⏱ Time left: {hours}h {minutes}m")

    while True:
        await asyncio.sleep(900)  # 15 minutes
        remaining = expiry - datetime.now()
        if remaining.total_seconds() <= 0:
            await msg.edit_text("⏰ Your 24h access has expired!")
            break
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        try:
            await msg.edit_text(f"✅ Access granted!\n⏱ Time left: {hours}h {minutes}m")
        except:
            # Message might have been deleted, ignore errors
            break

# --- Commands ---
@dp.message(commands=["start"])
async def start(message: types.Message):
    session_id = os.urandom(8).hex()
    user_id = message.from_user.id
    activate_session(session_id, user_id)

    # LiteShort link
    short_link = requests.get(
        f"https://liteshort.com/api?api={LITESHORT_API_KEY}&url={SERVER_URL}?session={session_id}&user={user_id}&format=text"
    ).text

    await message.answer(f"Click this link to activate 24h access:\n{short_link}")

@dp.message(commands=["timeleft"])
async def timeleft(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT expiry FROM tokens WHERE user_id=? AND status='active'", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        expiry = datetime.fromisoformat(row[0])
        remaining = expiry - datetime.now()
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        await message.answer(f"⏱ Time left: {hours}h {minutes}m")
    else:
        await message.answer("❌ You have no active access.")

# --- Run bot ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


#TELEGRAM_TOKEN = os.environ.get("8379093665:AAFKQKg4K8Zsi0TS5b2p2evmSvbcBNSi_YQ")
#LITESHORT_API_KEY = os.environ.get("be1528376cd25a510dce1e3e063ed856e5421250")
#SERVER_URL = os.environ.get("SERVER_URL")  # e.g., https://yourapp.onrender.com/activate
#DB = "database.db"
