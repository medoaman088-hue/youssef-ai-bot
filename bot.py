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


def clean_telegram_text(text):

    if not text:
        return text

    replacements = {
        "$$": "",
        "$": "",
        r"\mathbf{": "",
        r"\text{": "",
        r"\mathrm{": "",
        r"\textbf{": "",
        r"\rightarrow": "→",
        r"\to": "→",
        r"\Rightarrow": "⇒",
        r"\Leftarrow": "⇐",
        r"\leftrightarrow": "⇌",
        r"\rightleftharpoons": "⇌",
        r"\times": "×",
        r"\div": "÷",
        r"\pm": "±",
        r"\approx": "≈",
        r"\neq": "≠",
        r"\leq": "≤",
        r"\geq": "≥",
        r"\left": "",
        r"\right": "",
        r"\,": " ",
        r"\;": " ",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.replace("{", "")
    text = text.replace("}", "")

    return text.strip()


def send_message(chat_id, text):

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


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
        raise Exception(
            "فشل الحصول على الصورة من Telegram"
        )

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
        raise Exception(
            "فشل تحميل الصورة"
        )

    return image_response.content


def ask_gemini_text(text):

    prompt = """
أنت Youssef AI Bot.

أجب باللغة العربية بطريقة واضحة وبسيطة ومباشرة.

قواعد مهمة جدًا:
- لا تستخدم LaTeX نهائيًا.
- لا تستخدم $ أو $$.
- لا تستخدم \\mathbf أو \\text أو \\mathrm.
- اكتب الصيغ الكيميائية بشكل نصي واضح.
- استخدم الرموز السفلية عند الحاجة مثل H₂O و CH₃COOH و C₂H₅OH.
- استخدم الأسهم العادية مثل → و ⇌.
- استخدم العناوين والنقاط عندما يكون ذلك مفيدًا.
- لا تقل إنك نموذج لغوي نصي.
- إذا طلب المستخدم إنشاء صورة، لا تدّعي أنك أنشأتها.

سؤال المستخدم:
""" + text

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

    answer = (
        result["candidates"][0]
        ["content"]["parts"][0]["text"]
    )

    return clean_telegram_text(answer)


def analyze_image(image_bytes, question):

    image_base64 = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    prompt = """
أنت Youssef AI Bot.

حلل الصورة التي أرسلها المستخدم وأجب بالعربية.

اشرح بطريقة بسيطة ومناسبة لطالب.
إذا كانت الصورة تحتوي على:
- سؤال: حله واشرح الخطوات.
- رسم: اشرح الرسم.
- معادلة كيميائية: اشرحها.
- صفحة محاضرة: لخص واشرح الجزء المطلوب.

مهم:
لا تستخدم LaTeX.
لا تستخدم $ أو $$.
