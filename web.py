from flask import Flask, request, redirect
from bot import activate_session

REDIRECT_AD = "https://www.youtube.com"  # Replace with your ad/video link

app = Flask(__name__)

@app.route("/activate")
def activate():
    session_id = request.args.get("session")
    if session_id:
        activate_session(session_id)
    return redirect(REDIRECT_AD)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
