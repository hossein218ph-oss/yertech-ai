import os
import time
import hashlib
import threading
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import feedparser
import requests
from openai import OpenAI


# =========================================================
# تنظیمات
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

CHANNEL_USERNAME = "@yartech"

CHECK_INTERVAL = 10 * 60
POST_INTERVAL = 60 * 60

AI_CANDIDATES = 5

USED_FILE = "used_news.txt"
HISTORY_FILE = "news_history.json"

PORT = int(os.getenv("PORT", 10000))


# =========================================================
# RSS
# =========================================================

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
]


# =========================================================
# Groq
# =========================================================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

AI_MODEL = "openai/gpt-oss-120b"


# =========================================================
# Render HTTP Server
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

        self.wfile.write(
            "Yertech AI is running.\n".encode("utf-8")
        )

    def log_message(self, format, *args):
        return


def start_http_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)

    print(f"🌐 Render HTTP server فعال شد روی پورت {PORT}")

    server.serve_forever()


# =========================================================
# فایل‌های وضعیت
# =========================================================

def load_used_news():
    if not os.path.exists(USED_FILE):
        return set()

    try:
        with open(USED_FILE, "r", encoding="utf-8") as f:
            return set(
                line.strip()
                for line in f
                if line.strip()
            )
    except Exception:
        return set()


def save_used_news(news_id):
    try:
        with open(USED_FILE, "a", encoding="utf-8") as f:
            f.write(news_id + "\n")
    except Exception as e:
        print("⚠️ خطا در ذخیره used_news:", e)


# =========================================================
# تاریخچه خبرهای منتشرشده
# =========================================================

def load_history():

    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

            if isinstance(data, list):
                return data

    except Exception as e:
        print("⚠️ خطا در خواندن تاریخچه:", e)

    return []


def save_history(history):

    try:
        # فقط 100 خبر آخر نگهداری شود
        history = history[-100:]

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(
                history,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:
        print("⚠️ خطا در ذخیره تاریخچه:", e)


def add_to_history(news):

    history = load_history()

    item = {
        "id": news.get("id", ""),
        "title": news.get("title", ""),
        "summary": news.get("summary", ""),
        "link": news.get("link", ""),
        "published": news.get("published", ""),
        "timestamp": time.time()
    }

    history.append(item)

    save_history(history)


# =========================================================
# نرمال‌سازی متن
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    text = text.lower()

    # حذف URL
    text = re.sub(r"https?://\S+", " ", text)

    # حذف HTML
    text = re.sub(r"<[^>]+>", " ", text)

    # حذف علائم
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)

    # فاصله‌های اضافی
    text = re.sub(r"\s+", " ", text).strip()

    return text


def get_words(text):

    text = normalize_text(text)

    if not text:
        return set()

    words = text.split()

    # کلمات بسیار عمومی انگلیسی
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
        "new"
    }

    return {
        word
        for word in words
        if len(word) > 2 and word not in stopwords
    }


# =========================================================
# تشخیص شباهت دو خبر
# =========================================================

def similarity_score(title1, summary1, title2, summary2):

    title_words_1 = get_words(title1)
    title_words_2 = get_words(title2)

    body_words_1 = get_words(summary1)
    body_words_2 = get_words(summary2)

    if not title_words_1 or not title_words_2:
        return 0

    title_intersection = len(
        title_words_1 & title_words_2
    )

    title_union = len(
        title_words_1 | title_words_2
    )

    title_similarity = (
        title_intersection / title_union
        if title_union
        else 0
    )

    body_similarity = 0

    if body_words_1 and body_words_2:

        body_intersection = len(
            body_words_1 & body_words_2
        )

        body_union = len(
            body_words_1 | body_words_2
        )

        if body_union:
            body_similarity = (
                body_intersection / body_union
            )

    # تیتر مهم‌تر از خلاصه است
    return (
        title_similarity * 0.75
        +
        body_similarity * 0.25
    )


# =========================================================
# بررسی تکراری بودن
# =========================================================

def duplicate_score(news):

    history = load_history()

    if not history:
        return 0

    highest_similarity = 0

    for old in history:

        score = similarity_score(
            news.get("title", ""),
            news.get("summary", ""),
            old.get("title", ""),
            old.get("summary", "")
        )

        if score > highest_similarity:
            highest_similarity = score

    return highest_similarity


# =========================================================
# موضوع خبر
# =========================================================

def detect_topic(title, summary):

    text = normalize_text(
        f"{title} {summary}"
    )

    topics = {

        "AI": [
            "ai",
            "artificial intelligence",
            "chatgpt",
            "openai",
            "gemini",
            "claude",
            "copilot",
            "machine learning",
            "robot"
        ],

        "Mobile": [
            "iphone",
            "android",
            "samsung",
            "pixel",
            "smartphone",
            "mobile",
            "ios"
        ],

        "Gaming": [
            "playstation",
            "ps5",
            "xbox",
            "gaming",
            "game",
            "steam",
            "nintendo"
        ],

        "Security": [
            "hack",
            "hacked",
            "cyberattack",
            "security",
            "privacy",
            "malware"
        ],

        "Social": [
            "telegram",
            "whatsapp",
            "instagram",
            "youtube",
            "facebook",
            "tiktok"
        ],

        "Cars": [
            "tesla",
            "electric car",
            "self driving",
            "autonomous"
        ],

        "Hardware": [
            "nvidia",
            "gpu",
            "chip",
            "processor",
            "macbook",
            "laptop"
        ]
    }

    best_topic = "Technology"
    best_count = 0

    for topic, keywords in topics.items():

        count = 0

        for keyword in keywords:

            if keyword in text:
                count += 1

        if count > best_count:
            best_count = count
            best_topic = topic

    return best_topic


# =========================================================
# امتیاز تازگی
# =========================================================

def freshness_score(news):

    published_time = news.get("published_time")

    if not published_time:
        return 0

    try:

        now = time.time()

        hours_old = (
            now - published_time
        ) / 3600

        if
