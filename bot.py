import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash-lite:generateContent"
)


def send_telegram_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=15
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

        if not response.ok:
            error = result.get("error", {})

            error_code = error.get("code", response.status_code)
            error_status = error.get("status", "UNKNOWN")
            error_message = error.get(
                "message",
                "Unknown Gemini API error"
            )

            answer = (
                f"❌ Gemini API Error\n\n"
                f"Code: {error_code}\n"
                f"Status: {error_status}\n"
                f"Message: {error_message}"
            )

        else:
            candidates = result.get("candidates", [])

            if not candidates:
                answer = (
                    "❌ Gemini لم يرجع إجابة.\n\n"
                    f"الرد:\n{result}"
                )
            else:
                answer = (
                    candidates[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "لم يتم العثور على نص في الرد.")
                )

    except requests.exceptions.Timeout:
        answer = "❌ Gemini API أخذ وقتًا طويلًا ولم يرد."

    except Exception as e:
        answer = (
            "❌ حصل خطأ في البوت.\n\n"
            f"{type(e).__name__}: {str(e)}"
        )

    send_telegram_message(chat_id, answer)

    return "OK", 200
