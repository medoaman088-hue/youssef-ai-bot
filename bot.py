import os
import json
import base64
import shutil
import subprocess
import tempfile
import threading

import requests

from flask import Flask, request, jsonify
from google import genai

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

client = genai.Client(
    api_key=GEMINI_API_KEY
)

CHAT_MODEL = "gemini-3.8-flash"
IMAGE_MODEL = "gemini-3.1-flash-image"
TTS_MODEL = "gemini-3.8-flash-tts"


# ==========================================
# TELEGRAM
# ==========================================

def telegram(method, data=None, files=None, timeout=120):

    return requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        json=data,
        files=files,
        timeout=timeout
    )


def send_message(chat_id, text):

    try:

        telegram(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text
            }
        )

    except Exception as e:

        print("Telegram message error:", e)


def send_video(chat_id, path, caption):

    try:

        with open(path, "rb") as video:

            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
                data={
                    "chat_id": str(chat_id),
                    "caption": caption
                },
                files={
                    "video": (
                        "video.mp4",
                        video,
                        "video/mp4"
                    )
                },
                timeout=600
            )

        print("Telegram video:", response.text)

    except Exception as e:

        print("Telegram video error:", e)


# ==========================================
# SCRIPT
# ==========================================

def create_script(topic, minutes):

    target_words = int(minutes * 125)

    prompt = f"""
أنت كاتب محتوى تعليمي محترف.

اكتب سيناريو فيديو عربي باللهجة العربية الفصحى البسيطة.

الموضوع:
{topic}

مدة الفيديو المطلوبة:
{minutes} دقيقة.

عدد الكلمات التقريبي:
{target_words}

قسّم السيناريو إلى مشاهد.

كل مشهد يجب أن يحتوي:
- narration: الكلام الذي سيقوله المعلق الصوتي.
- image_prompt: وصف تفصيلي للصورة المطلوبة.
- seconds: مدة المشهد بالثواني.

استخدم مشاهد كثيرة بحيث يكون الفيديو متنوعًا.

أرجع JSON فقط بهذا الشكل:

{{
  "title": "عنوان الفيديو",
  "scenes": [
    {{
      "narration": "النص",
      "image_prompt": "وصف الصورة",
      "seconds": 10
    }}
  ]
}}
"""

    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=prompt
    )

    text = response.text.strip()

    # إزالة markdown إن وُجد
    if text.startswith("```"):

        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)


# ==========================================
# IMAGE
# ==========================================

def create_image(prompt, path):

    interaction = client.interactions.create(
        model=IMAGE_MODEL,
        input=prompt,
        response_format={
            "type": "image",
            "aspect_ratio": "16:9"
        }
    )

    if not interaction.output_image:

        raise Exception(
            "Gemini لم يرجع صورة."
        )

    data = base64.b64decode(
        interaction.output_image.data
    )

    with open(path, "wb") as f:

        f.write(data)


# ==========================================
# TTS
# ==========================================

def create_voice(text, path):

    interaction = client.interactions.create(

        model=TTS_MODEL,

        input=[
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": (
                                    "clear educational Arabic "
                                    "narration, friendly and natural"
                                )
                            }
                        ]
                    }
                ]
            }
        ],

        response_format={
            "type": "audio"
        },

        generation_config={
            "speech_config": [
                {
                    "voice": "Kore"
                }
            ]
        }
    )

    if not interaction.output_audio:

        raise Exception(
            "Gemini لم يرجع صوتًا."
        )

    audio = base64.b64decode(
        interaction.output_audio.data
    )

    with open(path, "wb") as f:

        f.write(audio)


# ==========================================
# FFMPEG
# ==========================================

def run_ffmpeg(command):

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:

        print(result.stderr)

        raise Exception(
            "FFmpeg error"
        )


# ==========================================
# CREATE IMAGE VIDEO
# ==========================================

def create_scene_video(
    image,
    audio,
    output,
    seconds
):

    # Zoom بسيط على الصورة
    frames = int(seconds * 30)

    filter_complex = (
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,"
        f"zoompan=z='min(zoom+0.0008,1.12)':"
        f"d={frames}:"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        "s=1920x1080:"
        "fps=30"
    )

    command = [
        "ffmpeg",
        "-y",

        "-loop",
        "1",

        "-i",
        image,

        "-i",
        audio,

        "-vf",
        filter_complex,

        "-t",
        str(seconds),

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",

        "-shortest",

        output
    ]

    run_ffmpeg(command)


# ==========================================
# CONCAT VIDEOS
# ==========================================

def concat_videos(files, output):

    list_file = output + ".txt"

    with open(list_file, "w", encoding="utf-8") as f:

        for file in files:

            safe = os.path.abspath(file).replace(
                "'",
                "'\\''"
            )

            f.write(
                f"file '{safe}'\n"
            )

    command = [
        "ffmpeg",
        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        list_file,

        "-c",
        "copy",

        output
    ]

    run_ffmpeg(command)

    os.remove(list_file)


# ==========================================
# FULL VIDEO JOB
# ==========================================

def make_video(chat_id, minutes, topic):

    work = tempfile.mkdtemp(
        prefix="ai_video_"
    )

    try:

        send_message(
            chat_id,
            "🧠 جاري كتابة السيناريو وتقسيمه لمشاهد..."
        )

        script = create_script(
            topic,
            minutes
        )

        scenes = script["scenes"]

        # لا نسمح بعدد ضخم جدًا من الصور
        max_scenes = 120

        scenes = scenes[:max_scenes]

        send_message(
            chat_id,
            f"🎬 عدد المشاهد: {len(scenes)}\n"
            "🖼️ جاري إنشاء الصور..."
        )

        scene_videos = []

        for index, scene in enumerate(scenes):

            number = index + 1

            image_path = os.path.join(
                work,
                f"image_{number}.png"
            )

            audio_path = os.path.join(
                work,
                f"audio_{number}.wav"
            )

            video_path = os.path.join(
                work,
                f"scene_{number}.mp4"
            )

            seconds = float(
                scene.get(
                    "seconds",
                    10
                )
            )

            # منع قيم غريبة
            seconds = max(
                3,
                min(seconds, 30)
            )

            print(
                f"Scene {number}/{len(scenes)}"
            )

            create_image(
                scene["image_prompt"],
                image_path
            )

            create_voice(
                scene["narration"],
                audio_path
            )

            create_scene_video(
                image_path,
                audio_path,
                video_path,
                seconds
            )

            scene_videos.append(
                video_path
            )

            send_message(
                chat_id,
                f"🖼️🎬 تم تجهيز المشهد "
                f"{number}/{len(scenes)}"
            )


        send_message(
            chat_id,
            "🔧 جاري تجميع كل المشاهد..."
        )

        final_path = os.path.join(
            work,
            "final.mp4"
        )

        concat_videos(
            scene_videos,
            final_path
        )

        send_message(
            chat_id,
            "📤 الفيديو اكتمل، جاري إرساله..."
        )

        send_video(
            chat_id,
            final_path,
            f"🎬 {script.get('title', topic)}"
        )

    except Exception as e:

        print(
            "VIDEO ERROR:",
            repr(e)
        )

        send_message(
            chat_id,
            "❌ حصل خطأ أثناء صناعة الفيديو:\n\n"
            + str(e)
        )

    finally:

        shutil.rmtree(
            work,
            ignore_errors=True
        )


# ==========================================
# API
# ==========================================

@app.route(
    "/make-video",
    methods=["POST"]
)
def make_video_endpoint():

    data = request.get_json(
        silent=True
    ) or {}

    chat_id = data.get("chat_id")
    minutes = data.get("minutes")
    topic = data.get("topic")

    if not chat_id:
        return jsonify({
            "error": "chat_id required"
        }), 400

    if not minutes:
        return jsonify({
            "error": "minutes required"
        }), 400

    if not topic:
        return jsonify({
            "error": "topic required"
        }), 400


    thread = threading.Thread(
        target=make_video,
        args=(
            chat_id,
            float(minutes),
            topic
        ),

        daemon=True
    )

    thread.start()

    return jsonify({
        "ok": True,
        "message": "Video job started"
    })


@app.route("/", methods=["GET"])
def home():

    return "AI Video Worker is running."


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
