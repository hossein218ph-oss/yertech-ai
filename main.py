import os
import time
import hashlib
import threading
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

import feedparser
import requests
from openai import OpenAI


# =========================================================
# YERTECH AI - FINAL VERSION
# =========================================================

# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

CHANNEL_USERNAME = "@yartech"

# هر چند دقیقه منابع بررسی شوند
CHECK_INTERVAL = 10 * 60

# فاصله انتشار
POST_INTERVAL = 60 * 60

# تعداد کاندیداهایی که به AI داده می‌شود
AI_CANDIDATES = 7

# فایل‌های وضعیت
USED_FILE = "used_news.txt"
HISTORY_FILE = "news_history.json"

# Render
PORT = int(os.getenv("PORT", 10000))

# Groq
AI_MODEL = "openai/gpt-oss-120b"


# =========================================================
# RSS SOURCES
# =========================================================

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
]


# =========================================================
# AI CLIENT
# =========================================================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)


# =========================================================
# HEALTH SERVER FOR RENDER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            "Yertech AI is running.\n".encode("utf-8")
        )

    def log_message(self, format, *args):
        return


def start_http_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print(
        f"🌐 Render HTTP server فعال شد روی پورت {PORT}"
    )

    server.serve_forever()


# =========================================================
# BASIC VALIDATION
# =========================================================

def validate_environment():

    missing = []

    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")

    if not BALE_BOT_TOKEN:
        missing.append("BALE_BOT_TOKEN")

    if not BALE_CHAT_ID:
        missing.append("BALE_CHAT_ID")

    if missing:

        print(
            "❌ متغیرهای محیطی ناقص هستند:"
        )

        for item in missing:
            print(
                f"   - {item}"
            )

        return False

    return True


# =========================================================
# USED NEWS
# =========================================================

def load_used_news():

    if not os.path.exists(USED_FILE):
        return set()

    try:

        with open(
            USED_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return {
                line.strip()
                for line in f
                if line.strip()
            }

    except Exception as e:

        print(
            "⚠️ خطا در خواندن used_news:",
            e
        )

        return set()


def save_used_news(news_id):

    try:

        with open(
            USED_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                news_id + "\n"
            )

    except Exception as e:

        print(
            "⚠️ خطا در ذخیره used_news:",
            e
        )


# =========================================================
# HISTORY
# =========================================================

def load_history():

    if not os.path.exists(HISTORY_FILE):
        return []

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, list):
                return data

    except Exception as e:

        print(
            "⚠️ خطا در خواندن history:",
            e
        )

    return []


def save_history(history):

    try:

        # حداکثر 200 خبر آخر
        history = history[-200:]

        with open(
            HISTORY_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                history,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print(
            "⚠️ خطا در ذخیره history:",
            e
        )


def add_to_history(news):

    history = load_history()

    history.append({

        "id": news.get(
            "id",
            ""
        ),

        "title": news.get(
            "title",
            ""
        ),

        "summary": news.get(
            "summary",
            ""
        ),

        "link": news.get(
            "link",
            ""
        ),

        "topic": news.get(
            "topic",
            ""
        ),

        "source": news.get(
            "source",
            ""
        ),

        "timestamp": time.time()

    })

    save_history(history)


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def get_words(text):

    text = normalize_text(text)

    if not text:
        return set()

    stopwords = {

        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "is",
        "are",
        "this",
        "that",
        "from",
        "by",
        "as",
        "at",
        "it",
        "its",
        "new",
        "how",
        "what",
        "why",
        "after",
        "before"
    }

    return {
        word
        for word in text.split()
        if len(word) > 2
        and word not in stopwords
    }


# =========================================================
# SIMILARITY ENGINE
# =========================================================

def similarity_score(
    title1,
    summary1,
    title2,
    summary2
):

    title1_words = get_words(title1)
    title2_words = get_words(title2)

    body1_words = get_words(summary1)
    body2_words = get_words(summary2)

    if not title1_words or not title2_words:
        return 0

    title_intersection = len(
        title1_words & title2_words
    )

    title_union = len(
        title1_words | title2_words
    )

    title_similarity = (
        title_intersection / title_union
        if title_union
        else 0
    )

    body_similarity = 0

    if body1_words and body2_words:

        body_intersection = len(
            body1_words & body2_words
        )

        body_union = len(
            body1_words | body2_words
        )

        if body_union:

            body_similarity = (
                body_intersection /
                body_union
            )

    return (
        title_similarity * 0.75
        +
        body_similarity * 0.25
    )


def duplicate_score(news):

    history = load_history()

    highest = 0

    for old in history:

        score = similarity_score(

            news.get("title", ""),
            news.get("summary", ""),

            old.get("title", ""),
            old.get("summary", "")
        )

        if score > highest:
            highest = score

    return highest


# =========================================================
# TOPIC ENGINE
# =========================================================

TOPICS = {

    "AI": [
        "ai",
        "artificial intelligence",
        "chatgpt",
        "openai",
        "gemini",
        "claude",
        "copilot",
        "machine learning",
        "robot",
        "robotics",
        "generative ai"
    ],

    "Mobile": [
        "iphone",
        "android",
        "samsung",
        "pixel",
        "smartphone",
        "mobile",
        "ios",
        "galaxy"
    ],

    "Gaming": [
        "playstation",
        "ps5",
        "ps6",
        "xbox",
        "gaming",
        "game",
        "steam",
        "nintendo",
        "console"
    ],

    "Security": [
        "hack",
        "hacked",
        "cyberattack",
        "security",
        "privacy",
        "malware",
        "ransomware",
        "password"
    ],

    "Social": [
        "telegram",
        "whatsapp",
        "instagram",
        "youtube",
        "facebook",
        "tiktok",
        "social media"
    ],

    "Cars": [
        "tesla",
        "
