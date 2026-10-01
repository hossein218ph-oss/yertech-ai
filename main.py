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
# CONFIG
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

CHANNEL_USERNAME = "@yartech"

CHECK_INTERVAL = 10 * 60
POST_INTERVAL = 60 * 60

AI_CANDIDATES = 7

USED_FILE = "used_news.txt"
HISTORY_FILE = "news_history.json"

PORT = int(os.getenv("PORT", 10000))

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
# GROQ
# =========================================================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)


# =========================================================
# RENDER HEALTH SERVER
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

            return set(
                line.strip()
                for line in f
                if line.strip()
            )

    except Exception:
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
            "⚠️ خطا در خواندن تاریخچه:",
            e
        )

    return []


def save_history(history):

    try:

        history = history[-150:]

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
            "⚠️ خطا در ذخیره تاریخچه:",
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
        "what"
    }

    return {
        word
        for word in text.split()
        if len(word) > 2
        and word not in stopwords
    }


# =========================================================
# SIMILARITY
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

            news.get(
                "title",
                ""
            ),

            news.get(
                "summary",
                ""
            ),

            old.get(
                "title",
                ""
            ),

            old.get(
                "summary",
                ""
            )
        )

        if score > highest:
            highest = score

    return highest


# =========================================================
# TOPIC DETECTION
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
        "robotics"
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
        "self-driving",
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


def detect_topic(
    title,
    summary
):

    text = normalize_text(
        f"{title} {summary}"
    )

    best_topic = "Technology"
    best_count = 0

    for topic, keywords in TOPICS.items():

        count = 0

        for keyword in keywords:

            if keyword in text:
                count += 1

        if count > best_count:

            best_count = count
            best_topic = topic

    return best_topic


# =========================================================
# TOPIC DIVERSITY
# =========================================================

def topic_penalty(topic):

    history = load_history()

    if not history:
        return 0

    recent = history[-5:]

    same_topic_count = 0

    for item in recent:

        if item.get(
            "topic"
        ) == topic:

            same_topic_count += 1

    if same_topic_count >= 3:
        return 12

    if same_topic_count == 2:
        return 6

    if same_topic_count == 1:
        return 2

    return 0


# =========================================================
# FRESHNESS
# =========================================================

def freshness_score(news):

    published_time = news.get(
        "published_time"
    )

    if not published_time:
        return 0

    try:

        age_hours = (
            time.time() -
            published_time
        ) / 3600

        if age_hours < 2:
            return 15

        if age_hours < 6:
            return 11

        if age_hours < 12:
            return 8

        if age_hours < 24:
            return 4

        if age_hours < 48:
            return 0

        if age_hours < 72:
            return -5

        return -12

    except Exception:

        return 0


# =========================================================
# VIRAL SCORE
# =========================================================

def calculate_viral_score(
    title,
    summary
):

    text = normalize_text(
        f"{title} {summary}"
    )

    score = 0

    high_priority = [

        "chatgpt",
        "openai",
        "iphone",
        "ios",
        "android",
        "samsung",
        "google",
        "playstation",
        "ps5",
        "xbox",
        "gaming",
        "game",
        "telegram",
        "whatsapp",
        "instagram",
        "youtube",
        "nvidia",
        "tesla",
        "robot",
        "robotics",
        "ai"
    ]

    for keyword in high_priority:

        if keyword in text:
            score += 6

    secondary = [

        "smartphone",
        "phone",
        "pixel",
        "macbook",
        "laptop",
        "windows",
        "macos",
        "microsoft",
        "meta",
        "amazon",
        "browser",
        "internet",
        "privacy",
        "security",
        "hack",
        "hacked",
        "cyberattack",
        "electric car",
        "self-driving",
        "autonomous",
        "chip",
        "gpu",
        "processor"
    ]

    for keyword in secondary:

        if keyword in text:
            score += 3

    viral_words = [

        "new",
        "just announced",
        "announced",
        "launches",
        "launched",
        "reveals",
        "revealed",
        "first",
        "major",
        "breakthrough",
        "surprising",
        "unexpected",
        "secret",
        "free",
        "faster",
        "powerful",
        "finally",
        "now available",
        "update",
        "new feature",
        "breaking"
    ]

    for keyword in viral_words:

        if keyword in text:
            score += 2

    boring_words = [

        "enterprise",
        "venture capital",
        "funding round",
        "funding",
        "corporate",
        "developer tools",
        "api pricing",
        "acquisition",
        "board of directors",
        "quarterly earnings"
    ]

    for keyword in boring_words:

        if keyword in text:
            score -= 6

    title_length = len(
        title.split()
    )

    if 5 <= title_length <= 14:
        score += 3

    return score


# =========================================================
# NEWS COLLECTION
# =========================================================

def collect_news():

    used_news = load_used_news()

    candidates = []

    print(
        "\n🔎 بررسی منابع خبری..."
    )

    for feed_url in RSS_FEEDS:

        try:

            feed = feedparser.parse(
                feed_url
            )

            for entry in feed.entries[:20]:

                title = entry.get(
                    "title",
                    ""
                ).strip()

                summary = entry.get(
                    "summary",
                    ""
                ).strip()

                link = entry.get(
                    "link",
                    ""
                ).strip()

                if not title or not link:
                    continue

                news_id = hashlib.md5(
                    link.encode(
                        "utf-8"
                    )
                ).hexdigest()

                if news_id in used_news:
                    continue

                published_time = None

                if entry.get(
                    "published_parsed"
                ):

                    try:

                        published_time = time.mktime(
                            entry.published_parsed
                        )

                    except Exception:
                        pass

                elif entry.get(
                    "updated_parsed"
                ):

                    try:

                        published_time = time.mktime(
                            entry.updated_parsed
                        )

                    except Exception:
                        pass

                news = {

                    "id": news_id,

                    "title": title,

                    "summary": summary,

                    "link": link,

                    "published_time":
                        published_time,

                    "topic":
                        detect_topic(
                            title,
                            summary
                        )
                }

                duplicate = duplicate_score(
                    news
                )

                if duplicate >= 0.55:

                    print(
                        f"♻️ تکراری حذف شد: "
                        f"{title}"
                    )

                    continue

                viral = calculate_viral_score(
                    title,
                    summary
                )

                fresh = freshness_score(
                    news
                )

                topic_pen = topic_penalty(
                    news["topic"]
                )

                duplicate_pen = int(
                    duplicate * 20
                )

                total = (
                    viral
                    +
                    fresh
                    -
                    topic_pen
                    -
                    duplicate_pen
                )

                news["viral_score"] = viral
                news["freshness_score"] = fresh
                news["topic_penalty"] = topic_pen
                news["duplicate_score"] = duplicate
                news["total_score"] = total

                candidates.append(
                    news
                )

        except Exception as e:

            print(
                "⚠️ RSS Error:",
                e
            )

    return candidates


# =========================================================
# REMOVE SAME-DAY / CURRENT BATCH DUPLICATES
# =========================================================

def remove_current_duplicates(
    candidates
):

    candidates.sort(
        key=lambda x:
        x["total_score"],
        reverse=True
    )

    selected = []

    for news in candidates:

        is_duplicate = False

        for existing in selected:

            similarity = similarity_score(

                news["title"],
                news["summary"],

                existing["title"],
                existing["summary"]
            )

            if similarity >= 0.50:

                print(
                    f"♻️ خبر مشابه حذف شد
