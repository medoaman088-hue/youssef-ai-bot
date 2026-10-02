import os
import base64
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ==================================================
# تنظيف ردود Gemini من LaTeX
# ==================================================

def clean_telegram_text(text):

    if not text:
        return text

    # إزالة LaTeX delimiters
    text = text.replace("$$", "")
    text = text.replace("$", "")

    # أوامر التنسيق
    text = text.replace(r"\mathbf{", "")
    text = text.replace(r"\textbf{", "")
    text = text.replace(r"\mathrm{", "")
    text = text.replace(r"\text{", "")

    # الأسهم
    text = text.replace(r"\rightarrow", "→")
    text = text.replace(r"\to", "→")
    text = text.replace(r"\Rightarrow", "⇒")
    text = text.replace(r"\Leftarrow", "⇐")
    text = text.replace(r"\leftrightarrow", "⇌")
    text = text.replace(r"\rightleftharpoons", "⇌")

    # رموز رياضية
    text = text.replace(r"\times", "×")
    text = text.replace(r"\div", "÷")
    text = text.replace(r"\pm", "±")
    text = text.replace(r"\approx", "≈")
    text = text.replace(r"\neq", "≠")
    text = text.replace(r"\leq", "≤")
    text = text.replace(r"\geq", "≥")

    # بعض أوامر LaTeX الأخرى
    text = text.replace(r"\,", " ")
    text = text.replace(r"\;", " ")
    text = text.replace(r"\ ", " ")

    # الأقواس الناتجة عن أوامر التنسيق
    text = text.replace("{", "")
    text = text.replace("}", "")

    # إزالة بعض الـ backslashes المتبقية
    text = text.replace(r"\left", "")
    text = text.replace(r"\right", "")

    return text.strip()


# ==================================================
# إرسال رسالة Telegram
# ==================================================

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

        print(
            "Telegram sendMessage:",
            response.status_code
        )

        print(response.text)

    except Exception as e:

        print(
            "Telegram ERROR:",
            repr(e)
        )


# ==================================================
# إرسال صورة Telegram
# ==================================================

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

        print(
            "Telegram sendPhoto:",
            response.status_code
        )

        print(response.text)

        return response.ok

    except Exception as e:

        print(
            "sendPhoto ERROR:",
            repr(e)
        )

        return False


# ==================================================
# Gemini Chat
# ==================================================

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

                            "text": (

                                "أنت مساعد تعليمي ذكي.\n\n"

                                "أجب باللغة المناسبة لسؤال المستخدم، "
                                "ويفضل العربية المصرية عندما يكون السؤال "
                                "بالعامية المصرية.\n\n"

                                "اجعل الإجابة مناسبة للعرض داخل Telegram.\n\n"

                                "مهم جدًا:\n"

                                "لا تستخدم LaTeX.\n"

                                "لا تستخدم $$.\n"

                                "لا تستخدم $.\n"

                                "لا تستخدم \\mathbf{}.\n"

                                "لا تستخدم \\rightarrow.\n"

                                "لا تستخدم أوامر LaTeX الأخرى.\n\n"

                                "اكتب الصيغ الكيميائية كنص واضح، "
                                "مثل CH₃COOH و C₂H₄O₂.\n\n"

                                "استخدم الأسهم العادية مثل →.\n\n"

                                "اجعل الشرح واضحًا ومنظمًا وبسيطًا، "
                                "ولا تكتب مقدمات طويلة بدون داعٍ.\n\n"

                                f"سؤال المستخدم:\n{text}"

                            )

                        }

                    ]

                }

            ]

        },

        timeout=60
    )


    print(
        "Gemini chat status:",
        response.status_code
    )

    print(
        "Gemini chat response:",
        response.text[:3000]
    )


    try:

        result = response.json()

    except Exception:

        return "❌ Gemini رجع استجابة غير مفهومة."


    if not response.ok:

        error = result.get(
            "error",
            {}
        )

        return (

            "❌ Gemini Error\n\n"

            f"Code: "
            f"{error.get('code', response.status_code)}\n"

            f"Status: "
            f"{error.get('status', 'UNKNOWN')}\n"

            f"Message: "
            f"{error.get('message', 'Unknown error')}"

        )


    try:

        answer = (
            result["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

        return clean_telegram_text(answer)

    except Exception:

        return "❌ Gemini لم يرجع نصًا مفهومًا."


# ==================================================
# تحميل صورة
