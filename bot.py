import os
import base64
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

CHAT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash-lite:generateContent"
)

IMAGE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "interactions"
)


# =========================
# Telegram
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


def send_photo(chat_id, image_bytes):
    return requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data={
            "chat_id": chat_id
        },
        files={
            "photo": (
                "generated.jpg",
                image_bytes,
                "image/jpeg"
            )
        },
        timeout=60
    )


# =========================
# Gemini Chat
# =========================

def chat_with_gemini(text):

    response = requests.post(
        CHAT_URL,
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
                "Gemini chat error"
            )
        )

    return (
        result["candidates"][0]
        ["content"]["parts"][0]["text"]
    )


# =========================
# Telegram Image Download
# =========================

def download_telegram_photo(file_id):

    result = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        params={
            "file_id": file_id
        },
        timeout=30
    ).json()

    if not result.get("ok"):
        raise Exception("فشل الحصول على الصورة من Telegram")

    file_path = result["result"]["file_path"]

    image_url = (
        f"https://api.telegram.org/file/bot"
        f"{BOT_TOKEN}/{file_path}"
    )

    image = requests.get(
        image_url,
        timeout=30
    )

    if not image.ok:
        raise Exception("فشل تحميل الصورة")

    return image.content


# =========================
# Gemini Image Understanding
# =========================

def analyze_image(image_bytes, question):

    image_b64 = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    response = requests.post(
        IMAGE_URL,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        json={
            "model": "gemini-3.8-flash",
            "input": [
                {
                    "type": "text",
                    "text": question
                },
                {
                    "type": "image",
                    "data": image_b64,
                    "mime_type": "image/jpeg"
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

    # محاولة الحصول على النص
    if result.get("output_text"):
        return result["output_text"]

    if result.get("output"):
        for item in result["output"]:
            if item.get("type") == "text":
                return item.get("text", "")

    return "❌ لم أستطع استخراج إجابة من الصورة."


# =========================
# Gemini Image Generation
# =========================

def generate_image(prompt):

    response = requests.post(
        IMAGE_URL,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        json={
            "model": "gemini-3.1-flash-image",
            "input": prompt,
            "response_format": {
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": "1:1",
                "image_size": "1K"
            }
        },
        timeout=120
    )

    result = response.json()

    if not response.ok:
        error = result.get("error", {})

        raise Exception(
            error.get(
                "message",
                "Image generation error"
            )
        )

    image_data = None

    if result.get("output_image"):
        image_data = result["output_image"].get("data")

    if not image_data and result.get("output"):
        for item in result["output"]:
            if item.get("type") == "image":
                image_data = item.get("data")
                break

    if not image_data:
        raise Exception(
            "Gemini لم يرجع صورة."
        )

    return base64.b64decode(image_data)


# =========================
# Main Webhook
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
        # IMAGE MESSAGE
        # =====================

        if "photo" in message:

            photo = message["photo"][-1]

            file_id = photo["file_id"]

            image_bytes = download_telegram_photo(
                file_id
            )

            question = message.get(
                "caption",
                "اشرح لي الصورة بالتفصيل وبطريقة بسيطة."
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
        # TEXT MESSAGE
        # =====================

        text = message.get(
            "text",
            ""
        ).strip()

        if not text:
            return "OK", 200


        # =====================
        # /image
        # =====================

        if text.startswith("/image"):

            prompt = text[
                len("/image"):
            ].strip()

            if not prompt:

                send_message(
                    chat_id,
                    "اكتب وصف الصورة بعد الأمر.\n\n"
                    "مثال:\n"
                    "/image قطة كرتونية في الفضاء"
                )

                return "OK", 200

            image_bytes = generate_image(
                prompt
            )

            result = send_photo(
                chat_id,
                image_bytes
            )

            if not result.ok:

                send_message(
                    chat_id,
                    "❌ تم إنشاء الصورة لكن فشل إرسالها إلى Telegram."
                )

            return "OK", 200


        # =====================
        # NORMAL CHAT
        # =====================

        answer = chat_with_gemini(
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
# Home
# =========================

@app.route("/", methods=["GET"])
def home():

    return "Youssef AI Bot is running."


# =========================
# Run
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
