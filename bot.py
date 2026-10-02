import os
import base64
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# =========================
# Telegram
# =========================

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=30
        )

        print("Telegram sendMessage:", response.status_code)
        print(response.text)

    except Exception as e:
        print("Telegram error:", repr(e))


def send_photo(chat_id, image_bytes):
    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendPhoto",
            data={
                "chat_id": chat_id
            },
            files={
                "photo": (
                    "generated_image.jpg",
                    image_bytes,
                    "image/jpeg"
                )
            },
            timeout=60
        )

        print("Telegram sendPhoto:", response.status_code)
        print(response.text)

        return response.ok

    except Exception as e:
        print("sendPhoto error:", repr(e))
        return False


# =========================
# Gemini Chat
# =========================

GEMINI_CHAT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash-lite:generateContent"
)


def ask_gemini(text):

    response = requests.post(
        GEMINI_CHAT_URL,
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

    print("Gemini chat status:", response.status_code)
    print("Gemini chat response:", response.text)

    result = response.json()

    if not response.ok:
        error = result.get("error", {})

        return (
            "❌ Gemini Error\n\n"
            f"Code: {error.get('code', response.status_code)}\n"
            f"Status: {error.get('status', 'UNKNOWN')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    try:
        return (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

    except Exception:
        return "❌ Gemini لم يرجع نصًا مفهومًا."


# =========================
# Gemini Image
# =========================

GEMINI_IMAGE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/interactions"
)


def generate_image(prompt):

    response = requests.post(
        GEMINI_IMAGE_URL,
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
                "aspect_ratio": "16:9",
                "image_size": "1K"
            }
        },
        timeout=120
    )

    print("Gemini image status:", response.status_code)
    print("Gemini image response:", response.text[:3000])

    if not response.ok:
        try:
            error = response.json().get("error", {})

            return None, (
                "❌ فشل إنشاء الصورة.\n\n"
                f"Code: {error.get('code', response.status_code)}\n"
                f"Message: {error.get('message', 'Unknown error')}"
            )

        except Exception:
            return None, "❌ فشل إنشاء الصورة."

    try:
        result = response.json()

        # الطريقة الأساسية في Interactions API
        image_data = result["output_image"]["data"]

        image_bytes = base64.b64decode(image_data)

        return image_bytes, None

    except Exception as e:

        print("Image parsing error:", repr(e))

        return None, (
            "❌ تم إنشاء استجابة من Gemini "
            "لكن لم أستطع استخراج الصورة منها."
        )


# =========================
# Telegram Webhook
# =========================

@app.route("/api", methods=["POST"])
def webhook():

    data = request.get_json(silent=True) or {}

    print("Telegram update:", data)

    if "message" not in data:
        return "OK", 200

    message = data["message"]

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    text = message.get("text", "").strip()

    if not chat_id or not text:
        return "OK", 200

    # =========================
    # /image
    # =========================

    if text.startswith("/image"):

        prompt = text[len("/image"):].strip()

        if not prompt:

            send_message(
                chat_id,
                "🖼️ اكتب وصف الصورة بعد الأمر.\n\n"
                "مثال:\n"
                "/image قطة كرتونية في الفضاء"
            )

            return "OK", 200

        send_message(
            chat_id,
            "🎨 جاري إنشاء الصورة...\n"
            "⏳ انتظر قليلًا."
        )

        try:

            image_bytes, error = generate_image(prompt)

            if error:

                send_message(
                    chat_id,
                    error
                )

                return "OK", 200

            if image_bytes:

                success = send_photo(
                    chat_id,
                    image_bytes
                )

                if not success:

                    send_message(
                        chat_id,
                        "❌ تم إنشاء الصورة، "
                        "لكن حدث خطأ أثناء إرسالها إلى Telegram."
                    )

            else:

                send_message(
                    chat_id,
                    "❌ لم يتم الحصول على صورة."
                )

        except Exception as e:

            print("IMAGE ERROR:", repr(e))

            send_message(
                chat_id,
                "❌ حصل خطأ أثناء إنشاء الصورة:\n\n"
                f"{type(e).__name__}: {str(e)}"
            )

        return "OK", 200

    # =========================
    # /start
    # =========================

    if text == "/start":

        send_message(
            chat_id,
            "🤖 أهلاً بك في Youssef AI Bot!\n\n"
            "💬 اكتب أي سؤال للدردشة مع الذكاء الاصطناعي.\n\n"
            "🖼️ لإنشاء صورة:\n"
            "/image قطة كرتونية في الفضاء"
        )

        return "OK", 200

    # =========================
    # Normal AI Chat
    # =========================

    try:

        answer = ask_gemini(text)

        send_message(
            chat_id,
            answer
        )

    except Exception as e:

        print("CHAT ERROR:", repr(e))

        send_message(
            chat_id,
            "❌ حصل خطأ:\n\n"
            f"{type(e).__name__}: {str(e)}"
        )

    return "OK", 200


# =========================
# Home
# =========================

@app.route("/", methods=["GET"])
def home():

    return "Youssef AI Bot is running."


# =========================
# Local
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
            )
