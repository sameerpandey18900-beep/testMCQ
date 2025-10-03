from flask import Flask, request
from bot import activate_session

app = Flask(__name__)

@app.route("/activate")
def activate():
    session_id = request.args.get("session")
    user_id = request.args.get("user")
    if session_id and user_id:
        activate_session(session_id, int(user_id))
        return "✅ 24h access granted! Check your Telegram bot."
    return "❌ Invalid request"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
