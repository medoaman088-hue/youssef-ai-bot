import os
import io
import time
import requests

from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash-lite:generateContent"
)


# =========================
# Telegram
# =========================

def telegram(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    response = requests.post(
        url,
        data=data,
        files=files,
        timeout=60
    )

    return response


def send_message(chat_id, text):
    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


# =========================
# Gemini
# =========================

def ask_gemini(prompt):

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
                            "text": prompt
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

        return (
            "❌ Gemini API Error\n\n"
            f"Code: {error.get('code', response.status_code)}\n"
            f"Status: {error.get('status', 'UNKNOWN')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    candidates = result.get("candidates", [])

    if not candidates:
        return "❌ Gemini لم يرجع إجابة."

    return (
        candidates[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "لم يتم العثور على إجابة.")
    )


# =========================
# Font
# =========================

def get_font(size):

    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# =========================
# Create educational video
# =========================

def create_video(topic):

    width = 640
    height = 360

    frames = []

    title_font = get_font(32)
    text_font = get_font(22)
    small_font = get_font(18)

    # Ask Gemini for a simple educational storyboard
    prompt = f"""
أنت مصمم فيديوهات تعليمية قصيرة.

الموضوع:
{topic}

اكتب 4 مشاهد قصيرة جدًا للفيديو.
كل مشهد في سطر واحد فقط.
اجعل الشرح مناسبًا للطلاب وبسيطًا ودقيقًا.
لا تستخدم رموز غريبة أو Markdown.
"""

    storyboard = ask_gemini(prompt)

    scenes = [
        line.strip()
        for line in storyboard.splitlines()
        if line.strip()
    ]

    if not scenes:
        scenes = [
            f"شرح مبسط عن: {topic}",
            "المشهد الثاني",
            "المشهد الثالث",
            "الخلاصة"
        ]

    scenes = scenes[:4]

    # Create animated frames
    for scene_index, scene in enumerate(scenes):

        for frame_number in range(15):

            image = Image.new(
                "RGB",
                (width, height),
                (245, 248, 252)
            )

            draw = ImageDraw.Draw(image)

            # Header
            draw.rectangle(
                (0, 0, width, 70),
                fill=(30, 80, 140)
            )

            title = "AI Educational Video"

            draw.text(
                (20, 18),
                title,
                font=title_font,
                fill="white"
            )

            # Topic
            draw.text(
                (25, 95),
                topic[:45],
                font=text_font,
                fill=(20, 20, 20)
            )

            # Animated circles = simple visual representation
            progress = frame_number / 14

            x1 = int(150 + progress * 120)
            x2 = int(490 - progress * 120)

            draw.ellipse(
                (x1 - 35, 180 - 35,
                 x1 + 35, 180 + 35),
                fill=(80, 150, 230)
            )

            draw.ellipse(
                (x2 - 35, 180 - 35,
                 x2 + 35, 180 + 35),
                fill=(230, 100, 100)
            )

            # Connection
            draw.line(
                (x1 + 35, 180, x2 - 35, 180),
                fill=(100, 100, 100),
                width=5
            )

            # Scene text
            words = scene[:180]

            # Simple wrapping
            lines = []

            current = ""

            for word in words.split():

                test = current + " " + word

                if len(test) > 45:
                    lines.append(current)
                    current = word
                else:
                    current = test

            if current:
                lines.append(current)

            y = 250

            for line in lines[:4]:

                draw.text(
                    (25, y),
                    line,
                    font=small_font,
                    fill=(30, 30, 30)
                )

                y += 25

            frames.append(image)

    # Save GIF in temporary directory
    filename = f"/tmp/video_{int(time.time())}.gif"

    frames[0].save(
        filename,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0
    )

    return filename


# =========================
# Send video/animation
# =========================

def send_video(chat_id, filename):

    with open(filename, "rb") as video_file:

        telegram(
            "sendAnimation",
            data={
                "chat_id": chat_id,
                "caption": "🎬 تم إنشاء الفيديو التعليمي"
            },
            files={
                "animation": (
                    "educational_video.gif",
                    video_file,
                    "image/gif"
                )
            }
        )


# =========================
# Main Webhook
# =========================

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

    # =====================
    # VIDEO COMMAND
    # =====================

    if user_text.startswith("/video"):

        topic = user_text[6:].strip()

        if not topic:

            send_message(
                chat_id,
                "🎬 اكتب موضوع الفيديو بعد الأمر.\n\n"
                "مثال:\n"
                "/video تفاعل حمض الهيدروكلوريك مع هيدروكسيد الصوديوم"
            )

            return "OK", 200

        send_message(
            chat_id,
            "🎬 جاري إنشاء الفيديو...\n\n"
            f"الموضوع: {topic}"
        )

        try:

            filename = create_video(topic)

            send_video(
                chat_id,
                filename
            )

        except Exception as e:

            send_message(
                chat_id,
                "❌ حصل خطأ أثناء إنشاء الفيديو.\n\n"
                f"{type(e).__name__}: {str(e)}"
            )

        return "OK", 200

    # =====================
    # NORMAL AI CHAT
    # =====================

    answer = ask_gemini(user_text)

    send_message(
        chat_id,
        answer
    )

    return "OK", 200
