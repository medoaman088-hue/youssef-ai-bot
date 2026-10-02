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


def send_message(chat_id, text):
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )

    print("Telegram:", response.text)


@app.route("/api", methods=["POST"])
def webhook():

    data = request.get_json(silent=True) or {}

    print("Telegram update:", data)

    if "message" not in data:
        return "OK", 200

    message = data["message"]

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text:
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
                                "text": text
                            }
                        ]
                    }
                ]
            },
            timeout=60
        )

        print("Gemini status:", response.status_code)
        print("Gemini response:", response.text)

        result = response.json()

        if response.ok:

            answer = (
                result["candidates"][0]
                ["content"]["parts"][0]["text"]
            )

        else:

            error = result.get("error", {})

            answer = (
                "❌ Gemini Error\n\n"
                f"Code: {error.get('code', response.status_code)}\n"
                f"Status: {error.get('status', 'UNKNOWN')}\n"
                f"Message: {error.get('message', 'Unknown error')}"
            )

        send_message(
            chat_id,
            answer
        )

    except Exception as e:

        print("ERROR:", repr(e))

        send_message(
            chat_id,
            "❌ حصل خطأ:\n\n"
            f"{type(e).__name__}: {str(e)}"
        )

    return "OK", 200


@app.route("/", methods=["GET"])
def home():

    return "Youssef AI Bot is running."


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
