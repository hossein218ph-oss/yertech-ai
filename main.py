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

PORT = int(os.getenv("PORT", "10000"))

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
            b"Yertech AI is running."
        )

    def log_message(self, format, *args):
        return


def start_http_server():
    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print(
        f"HTTP server active on port {PORT}"
    )

    server.serve_forever()


# =========================================================
# VALIDATE ENVIRONMENT
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
        print("ERROR: Missing environment variables:")

        for item in missing:
            print("-", item)

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
            "Used news read error:",
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
            "Used news save error:",
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
            "History read error:",
            e
        )

    return []


def save_history(history):

    try:

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
            "History save error:",
            e
        )


def add_to_history(news):

    history = load_history()

    history.append({
        "id": news.get("id", ""),
        "title": news.get("title", ""),
        "summary": news.get("summary", ""),
        "link": news.get("link", ""),
        "topic": news.get("topic", ""),
        "source": news.get("source", ""),
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
                body_intersection / body_union
            )

    return (
        title_similarity * 0.75
        + body_similarity * 0.25
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
# TOPICS
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
        "electric car",
        "self driving",
        "self-driving",
        "autonomous",
        "ev"
    ],

    "Hardware": [
        "nvidia",
        "gpu",
        "chip",
        "processor",
        "macbook",
        "laptop",
        "cpu",
        "graphics card"
    ]
}


def detect_topic(title, summary):

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

    recent = history[-6:]

    same_topic_count = 0

    for item in recent:

        if item.get("topic") == topic:
            same_topic_count += 1

    if same_topic_count >= 4:
        return 15

    if same_topic_count == 3:
        return 10

    if same_topic_count == 2:
        return 5

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
            time.time() - published_time
        ) / 3600

        if age_hours < 1:
            return 18

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
            return -7

        return -15

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
        "processor",
        "free",
        "update"
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
        "breaking",
        "today",
        "just",
        "latest"
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
        "quarterly earnings",
        "revenue",
        "investment"
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
# SOURCE
# =========================================================

def detect_source(feed_url):

    url = feed_url.lower()

    if "techcrunch" in url:
        return "TechCrunch"

    if "theverge" in url:
        return "The Verge"

    if "wired" in url:
        return "Wired"

    return "Unknown"


def source_score(source):

    scores = {
        "TechCrunch": 3,
        "The Verge": 4,
        "Wired": 3
    }

    return scores.get(
        source,
        1
    )


# =========================================================
# COLLECT NEWS
# =========================================================

def collect_news():

    used_news = load_used_news()

    candidates = []

    print(
        "\nChecking news sources..."
    )

    for feed_url in RSS_FEEDS:

        source = detect_source(
            feed_url
        )

        try:

            feed = feedparser.parse(
                feed_url
            )

            for entry in feed.entries[:25]:

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
                    link.encode("utf-8")
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
                        published_time = None

                elif entry.get(
                    "updated_parsed"
                ):

                    try:
                        published_time = time.mktime(
                            entry.updated_parsed
                        )
                    except Exception:
                        published_time = None

                news = {
                    "id": news_id,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": source,
                    "published_time": published_time,
                    "topic": detect_topic(
                        title,
                        summary
                    )
                }

                duplicate = duplicate_score(
                    news
                )

                if duplicate >= 0.55:

                    print(
                        "Duplicate removed:",
                        title
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

                source_bonus = source_score(
                    source
                )

                total = (
                    viral
                    + fresh
                    + source_bonus
                    - topic_pen
                    - duplicate_pen
                )

                news["viral_score"] = viral
                news["freshness_score"] = fresh
                news["topic_penalty"] = topic_pen
                news["duplicate_score"] = duplicate
                news["source_score"] = source_bonus
                news["total_score"] = total

                candidates.append(
                    news
                )

        except Exception as e:

            print(
                f"RSS error ({source}):",
                e
            )

    return candidates


# =========================================================
# REMOVE CURRENT DUPLICATES
# =========================================================

def remove_current_duplicates(
    candidates
):

    candidates.sort(
        key=lambda x: x["total_score"],
        reverse=True
    )

    selected = []

    for news in candidates:

        duplicate = False

        for existing in selected:

            similarity = similarity_score(
                news["title"],
                news["summary"],
                existing["title"],
                existing["summary"]
            )

            if similarity >= 0.50:

                print(
                    "Similar news removed:",
                    news["title"]
                )

                duplicate = True
                break

        if not duplicate:
            selected.append(
                news
            )

    return selected


# =========================================================
# AI SELECT
# =========================================================

def ai_select_best_news(
    candidates
):

    if not candidates:
        return None

    candidates = candidates[
        :AI_CANDIDATES
    ]

    news_text = ""

    for i, news in enumerate(
        candidates,
        start=1
    ):

        news_text += (
            f"\nخبر {i}\n"
            f"عنوان: {news['title']}\n"
            f"منبع: {news['source']}\n"
            f"موضوع: {news['topic']}\n"
            f"امتیاز کلی: {news['total_score']}\n"
            f"امتیاز وایرال: {news['viral_score']}\n"
            f"تازگی: {news['freshness_score']}\n"
        )

    prompt = f"""
تو سردبیر ارشد یک کانال فناوری فارسی برای مخاطبان عمومی ایران هستی.

از بین خبرهای زیر فقط یک خبر را برای انتشار انتخاب کن.

اولویت‌ها:
- جذابیت عمومی
- احتمال وایرال شدن
- تازگی
- کاربرد واقعی
- شگفت‌انگیز بودن
- قابلیت اشتراک‌گذاری
- هوش مصنوعی
- موبایل
- گیمینگ
- امنیت
- شبکه‌های اجتماعی
- محصولات و قابلیت‌های جدید

خبرهای خشک مالی، سرمایه‌گذاری، سازمانی و مخصوص توسعه‌دهندگان را تا حد امکان انتخاب نکن.

اگر خبری برای کاربر عادی جذاب‌تر و قابل فهم‌تر است، آن را ترجیح بده.

فقط شماره خبر را برگردان.
هیچ توضیح دیگری ننویس.

{news_text}
"""

    try:

        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.15,
            max_tokens=20
        )

        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        match = re.search(
            r"\d+",
            result
        )

        if match:

            index = (
                int(match.group()) - 1
            )

            if 0 <= index < len(candidates):

                return candidates[
                    index
                ]

    except Exception as e:

        print(
            "AI selection error:",
            e
        )

    return candidates[0]


# =========================================================
# GET BEST NEWS
# =========================================================

def get_news():

    candidates = collect_news()

    if not candidates:

        print(
            "No suitable new news found."
        )

        return None

    candidates = remove_current_duplicates(
        candidates
    )

    candidates.sort(
        key=lambda x: x["total_score"],
        reverse=True
    )

    print(
        "\nNEWS RANKING:"
    )

    for i, news in enumerate(
        candidates[:10],
        start=1
    ):

        print(
            f"{i}. {news['title']}"
        )

        print(
            f"   "
            f"{news['source']} | "
            f"{news['topic']} | "
            f"viral={news['viral_score']} | "
            f"fresh={news['freshness_score']} | "
            f"duplicate={news['duplicate_score']:.2f} | "
            f"total={news['total_score']}"
        )

    selected = ai_select_best_news(
        candidates
    )

    if selected:

        print(
            "\nAI FINAL SELECTION:"
        )

        print(
            selected["title"]
        )

        print(
            "Source:",
            selected["source"]
        )

        print(
            "Topic:",
            selected["topic"]
        )

        print(
            "Score:",
            selected["total_score"]
        )

    return selected


# =========================================================
# PERSIAN REWRITE
# =========================================================

def rewrite_news(news):

    prompt = f"""
تو نویسنده ارشد یک کانال فناوری فارسی برای کاربران عمومی ایران هستی.

خبر زیر را به یک پست جذاب و حرفه‌ای برای کانال بله تبدیل کن.

عنوان:
{news['title']}

خلاصه:
{news['summary']}

منبع:
{news['source']}

لینک:
{news['link']}

موضوع:
{news['topic']}

قوانین:
- فارسی روان و طبیعی
- ترجمه کلمه‌به‌کلمه ممنوع
- حدود 120 تا 200 کلمه
- شروع با تیتر جذاب
- ابتدای متن Hook قوی
- خیلی سریع بگو چه اتفاقی افتاده
- توضیح بده چرا مهم است
- اگر کاربرد عملی دارد توضیح بده
- پاراگراف‌ها کوتاه باشند
- لحن مدرن و قابل اشتراک‌گذاری
- 4 تا 6 هشتگ مرتبط
- لینک منبع در پایان
- هیچ اطلاعاتی اختراع نکن
- عبارت @yartech را اضافه نکن
- از جمله‌های کلیشه‌ای مثل «در دنیای امروز فناوری» استفاده نکن
- بیش از حد رسمی نباش

مخاطب:
کاربران عمومی ایرانی علاقه‌مند به فناوری،
هوش مصنوعی، موبایل، گیمینگ و اینترنت.
"""

    try:

        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=700
        )

        text = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        text += (
            "\n\n📢 "
            + CHANNEL_USERNAME
        )

        return text

    except Exception as e:

        print(
            "Rewrite error:",
            e
        )

        return None


# =========================================================
# BALE
# =========================================================

def send_to_bale(message):

    url = (
        "https://tapi.bale.ai/bot"
        + BALE_BOT_TOKEN
        + "/sendMessage"
    )

    payload = {
        "chat_id": BALE_CHAT_ID,
        "text": message
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=30
        )

        print(
            "BALE STATUS:",
            response.status_code
        )

        if response.status_code == 200:

            print(
                "Post successfully published to Bale."
            )

            return True

        print(
            "Bale response:",
            response.text
        )

        return False

    except Exception as e:

        print(
            "Bale send error:",
            e
        )

        return False


# =========================================================
# ONE CYCLE
# =========================================================

def run_cycle():

    print("\n")
    print("=" * 70)

    print(
        "STARTING NEWS CYCLE"
    )

    news = get_news()

    if not news:

        print(
            "Cycle finished without publishing."
        )

        return False

    message = rewrite_news(
        news
    )

    if not message:

        print(
            "News rewrite failed."
        )

        return False

    print(
        "\nGENERATED POST:"
    )

    print(
        message
    )

    success = send_to_bale(
        message
    )

    if success:

        save_used_news(
            news["id"]
        )

        add_to_history(
            news
        )

        print(
            "News history saved."
        )

        print(
            "NEWS CYCLE COMPLETED."
        )

        return True

    print(
        "Publish failed."
    )

    return False


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 70)

    print(
        "YERTECH AI NEWS ENGINE"
    )

    print(
        "Viral Detection: ACTIVE"
    )

    print(
        "Anti-Duplicate: ACTIVE"
    )

    print(
        "AI Selection: ACTIVE"
    )

    print(
        "Freshness Engine: ACTIVE"
    )

    print(
        "Topic Detection: ACTIVE"
    )

    print(
        "Topic Diversity: ACTIVE"
    )

    print(
        "RSS: ACTIVE"
    )

    print(
        "Bale: ACTIVE"
    )

    print(
        "Channel:",
        CHANNEL_USERNAME
    )

    print(
        "Render: ACTIVE"
    )

    print(
        "Publish interval: 1 hour"
    )

    print("=" * 70)

    if not validate_environment():

        print(
            "Application stopped."
        )

        return

    run_cycle()

    last_post_time = time.time()

    while True:

        try:

            now = time.time()

            elapsed = (
                now - last_post_time
            )

            if elapsed >= POST_INTERVAL:

                run_cycle()

                last_post_time = time.time()

            else:

                remaining = int(
                    POST_INTERVAL - elapsed
                )

                print(
                    f"Next publish in "
                    f"{remaining // 60} minutes."
                )

            time.sleep(
                CHECK_INTERVAL
            )

        except Exception as e:

            print(
                "MAIN ERROR:",
                e
            )

            time.sleep(
                CHECK_INTERVAL
            )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    server_thread = threading.Thread(
        target=start_http_server,
        daemon=True
    )

    server_thread.start()

    main()
