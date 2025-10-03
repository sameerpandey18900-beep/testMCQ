import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio
from datetime import datetime, timedelta

# --- Load environment variables ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
LITESHORT_API_KEY = os.environ.get("LITESHORT_API_KEY")
SERVER_URL = os.environ.get("SERVER_URL")

if not TELEGRAM_TOKEN or not LITESHORT_API_KEY or not SERVER_URL:
    raise ValueError("❌ Missing environment variables")

# --- Helper to shorten URLs ---
def shorten_url(long_url):
    try:
        api_url = f"https://liteshort.com/api?api={LITESHORT_API_KEY}&url={long_url}&format=text"
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.text.strip()
        return long_url
    except Exception as e:
        print("Error shortening URL:", e)
        return long_url

# --- Countdown storage ---
active_sessions = {}  # user_id: expiry_time

# --- /start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.utcnow()
    expiry = now + timedelta(hours=24)
    active_sessions[user_id] = expiry

    short_link = shorten_url(SERVER_URL)

    await update.message.reply_text(
        f"✅ 24h access granted!\n⏳ Countdown started at UTC {now.strftime('%Y-%m-%d %H:%M:%S')}\nAccess link: {short_link}"
    )

# --- Background task to remove expired sessions ---
async def check_sessions():
    while True:
        now = datetime.utcnow()
        expired_users = [uid for uid, exp in active_sessions.items() if now > exp]
        for uid in expired_users:
            print(f"Session expired for user {uid}")
            del active_sessions[uid]
        await asyncio.sleep(900)  # check every 15 minutes

# --- Run bot ---
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.create_task(check_sessions())
    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
