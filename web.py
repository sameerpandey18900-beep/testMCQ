from flask import Flask, request, redirect
from bot import activate_session

# Replace this with your ad/landing page link
REDIRECT_AD = "https://www.youtube.com"

app = Flask(__name__)

# --- Root route ---
@app.route("/")
def index():
    return "🟢 Telegram 24h Access Bot is running!"

# --- Activation route ---
@app.route("/activate")
def activate():
    session_id = request.args.get("session")
    if session_id:
        activate_session(session_id)
    return redirect(REDIRECT_AD)

if __name__ == "__main__":
    # Render requires host 0.0.0.0 and port 8080
    app.run(host="0.0.0.0", port=8080)
