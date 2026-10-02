import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.8-flash:generateContent"
)


@app.route("/api", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}

    if "message" not in data:
        return "OK", 200

    message = data["message"]
    chat_id = message["chat"]["id"]
    user_text = message.get("text", "").strip()

    if not user_text:
        return "OK", 200

    try:
        response = requests.post(
            GEMINI_URL,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": user_text
                            }
                        ]
                    }
                ]
            },
            timeout=30
        )

        result = response.json()

        if response.ok:
            answer = result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            answer = "حصل خطأ في الاتصال بالذكاء الاصطناعي. جرّب تاني."

    except Exception:
        answer = "حصل خطأ وأنا بحاول أجيب الرد. جرّب تاني."

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": answer
        },
        timeout=15
    )

    return "OK", 200
