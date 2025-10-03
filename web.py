import os
import requests
from flask import Flask, request

# --- Load environment variables ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
LITESHORT_API_KEY = os.environ.get("LITESHORT_API_KEY")
SERVER_URL = os.environ.get("SERVER_URL")

if not TELEGRAM_TOKEN or not LITESHORT_API_KEY or not SERVER_URL:
    raise ValueError("❌ Missing environment variables")

app = Flask(__name__)

# --- Helper to shorten URLs ---
def shorten_url(long_url):
    try:
        api_url = f"https://liteshort.com/api?api={LITESHORT_API_KEY}&url={long_url}&format=text"
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.text.strip()
        return long_url
    except:
        return long_url

# --- Active sessions ---
active_sessions = {}  # user_id: expiry_time

@app.route("/")
def home():
    return "Bot is running! Use /activate to get 24h access."

@app.route("/activate")
def activate():
    user_id = request.args.get("user_id", "web_user")
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    expiry = now + timedelta(hours=24)
    active_sessions[user_id] = expiry

    short_link = shorten_url(SERVER_URL)

    return (
        f"✅ 24h access granted!<br>"
        f"⏳ Countdown started at UTC {now.strftime('%Y-%m-%d %H:%M:%S')}<br>"
        f"Access link: <a href='{short_link}' target='_blank'>{short_link}</a>"
    )

# --- Cleanup expired sessions every 15 min ---
def cleanup_sessions():
    import time
    from datetime import datetime
    while True:
        now = datetime.utcnow()
        expired = [uid for uid, exp in active_sessions.items() if now > exp]
        for uid in expired:
            del active_sessions[uid]
        time.sleep(900)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=cleanup_sessions, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
