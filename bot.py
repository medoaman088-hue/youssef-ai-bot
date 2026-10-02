import os
import base64
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash-lite:generateContent"
)


# =========================
# إرسال رسالة إلى Telegram
# =========================

def send_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


# =========================
# تحميل صورة Telegram
# =========================

def get_telegram_image(file_id):

    response = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        params={
            "file_id": file_id
        },
        timeout=30
    )

    result = response.json()

    if not result.get("ok"):
        raise Exception("فشل الحصول على ملف الصورة من Telegram")

    file_path = result["result"]["file_path"]

    image_url = (
        f"https://api.telegram.org/file/bot"
        f"{BOT_TOKEN}/{file_path}"
    )

    image_response = requests.get(
        image_url,
        timeout=30
    )

    if not image_response.ok:
        raise Exception("فشل تحميل الصورة")

    return image_response.content


# =========================
# الشات العادي
# =========================

def ask_gemini_text(text):

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

    result = response.json()

    if not response.ok:
        error = result.get("error", {})

        raise Exception(
            error.get(
                "message",
                "Gemini Error"
            )
        )

    return (
        result["candidates"][0]
        ["content"]["parts"][0]["text"]
    )


# =========================
# تحليل الصورة
# =========================

def analyze_image(image_bytes, question):

    image_base64 = base64.b64encode(
        image_bytes
    ).decode("utf-8")

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
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {
                            "text": question
                        }
                    ]
                }
            ]
        },
        timeout=90
    )

    result = response.json()

    if not response.ok:
        error = result.get("error", {})

        raise Exception(
            error.get(
                "message",
                "Image analysis error"
            )
        )

    return (
        result["candidates"][0]
        ["content"]["parts"][0]["text"]
    )


# =========================
# Webhook
# =========================

@app.route("/api", methods=["POST"])
def webhook():

    data = request.get_json(
        silent=True
    ) or {}

    if "message" not in data:
        return "OK", 200

    message = data["message"]

    chat_id = message["chat"]["id"]

    try:

        # =====================
        # لو المستخدم بعت صورة
        # =====================

        if "photo" in message:

            photo = message["photo"][-1]

            file_id = photo["file_id"]

            image_bytes = get_telegram_image(
                file_id
            )

            question = message.get(
                "caption",
                "اشرح لي هذه الصورة بالتفصيل وبطريقة بسيطة."
            )

            answer = analyze_image(
                image_bytes,
                question
            )

            send_message(
                chat_id,
                answer
            )

            return "OK", 200


        # =====================
        # رسالة نصية
        # =====================

        text = message.get(
            "text",
            ""
        ).strip()

        if not text:
            return "OK", 200

        answer = ask_gemini_text(
            text
        )

        send_message(
            chat_id,
            answer
        )

    except Exception as e:

        print(
            "ERROR:",
            repr(e)
        )

        send_message(
            chat_id,
            "❌ حصل خطأ:\n\n"
            + str(e)
        )

    return "OK", 200


# =========================
# الصفحة الرئيسية
# =========================

@app.route("/", methods=["GET"])
def home():

    return "Youssef AI Bot is running."


# =========================
# تشغيل التطبيق
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
