import os
import time
import hashlib
import threading
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import feedparser
import requests
from openai import OpenAI


# ==============================
# Environment Variables
# ==============================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

PORT = int(os.getenv("PORT", 10000))


# ==============================
# Settings
# ==============================

CHECK_INTERVAL = 10 * 60
POST_INTERVAL = 60 * 60

CHANNEL_USERNAME = "@yartech"

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss"
]

STATE_FILE = "state.txt"
USED_NEWS_FILE = "used_news.txt"

# تعداد خبرهایی که برای داوری نهایی AI ارسال می‌شوند
AI_CANDIDATES = 5


# ==============================
# Check Environment
# ==============================

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY تنظیم نشده است.")
    exit()

if not BALE_BOT_TOKEN:
    print("❌ BALE_BOT_TOKEN تنظیم نشده است.")
    exit()

if not BALE_CHAT_ID:
    print("❌ BALE_CHAT_ID تنظیم نشده است.")
    exit()


# ==============================
# Groq Client
# ==============================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)


# ==============================
# Render HTTP Server
# ==============================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(
            b"Yertech AI is running."
        )

    def log_message(self, format, *args):
        return


def start_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print("===================================")
    print(
        f"🌐 Render HTTP server فعال شد روی پورت {PORT}"
    )
    print("===================================")

    server.serve_forever()


server_thread = threading.Thread(
    target=start_server,
    daemon=True
)

server_thread.start()


# ==============================
# State
# ==============================

def get_last_post_time():

    try:
        with open(STATE_FILE, "r") as f:
            return float(f.read().strip())
    except:
        return 0


def save_last_post_time():

    with open(STATE_FILE, "w") as f:
        f.write(str(time.time()))


# ==============================
# Used News
# ==============================

def get_used_news():

    try:

        with open(
            USED_NEWS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return set(
                line.strip()
                for line in f
                if line.strip()
            )

    except:

        return set()


def save_used_news(news_id):

    with open(
        USED_NEWS_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(news_id + "\n")


# ==============================
# News ID
# ==============================

def make_news_id(link, title):

    value = link + title

    return hashlib.md5(
        value.encode("utf-8")
    ).hexdigest()


# ==============================
# Local Viral Score
# ==============================

def calculate_viral_score(title, summary):

    text = (
        title + " " + summary
    ).lower()

    score = 0


    # --------------------------------
    # بسیار مهم برای مخاطب عمومی
    # --------------------------------

    very_high = [
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
        "artificial intelligence",
        "ai"
    ]

    for keyword in very_high:

        if keyword in text:
            score += 8


    # --------------------------------
    # موضوعات جذاب
    # --------------------------------

    high = [
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

    for keyword in high:

        if keyword in text:
            score += 5


    # --------------------------------
    # نشانه‌های خبر وایرال
    # --------------------------------

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
        "now",
        "available",
        "update",
        "new feature"
    ]

    for keyword in viral_words:

        if keyword in text:
            score += 3


    # --------------------------------
    # موضوعاتی که معمولاً برای مخاطب
    # عمومی جذابیت کمتری دارند
    # --------------------------------

    boring = [
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

    for keyword in boring:

        if keyword in text:
            score -= 5


    # --------------------------------
    # امتیاز برای عنوان کوتاه و خبری
    # --------------------------------

    title_words = title.split()

    if 5 <= len(title_words) <= 14:
        score += 3


    return score


# ==============================
# Collect News
# ==============================

def collect_news():

    print("===================================")
    print("📰 در حال جمع‌آوری اخبار...")
    print("===================================")

    used_news = get_used_news()

    all_news = []


    for feed_url in RSS_FEEDS:

        try:

            print(
                f"Checking RSS: {feed_url}"
            )

            feed = feedparser.parse(
                feed_url
            )


            for entry in feed.entries[:15]:

                title = entry.get(
                    "title",
                    ""
                ).strip()

                link = entry.get(
                    "link",
                    ""
                ).strip()

                summary = entry.get(
                    "summary",
                    ""
                ).strip()


                if not title or not link:
                    continue


                news_id = make_news_id(
                    link,
                    title
                )


                if news_id in used_news:
                    continue


                score = calculate_viral_score(
                    title,
                    summary
                )


                all_news.append({

                    "id": news_id,

                    "title": title,

                    "link": link,

                    "summary": summary,

                    "score": score

                })


        except Exception as e:

            print(
                f"❌ RSS Error: {e}"
            )


    return all_news


# ==============================
# AI Viral Selection
# ==============================

def ai_select_best_news(candidates):

    if not candidates:
        return None


    print("===================================")
    print("🤖 در حال تحلیل وایرال بودن اخبار...")
    print("===================================")


    news_text = ""


    for i, news in enumerate(
        candidates,
        start=1
    ):

        news_text += f"""

خبر شماره {i}

عنوان:
{news["title"]}

خلاصه:
{news["summary"][:1200]}

امتیاز اولیه:
{news["score"]}

"""


    prompt = f"""
تو سردبیر یک کانال فناوری فارسی با مخاطبان ایرانی هستی.

باید از بین اخبار زیر فقط یک خبر را برای انتشار انتخاب کنی.

هدف:
انتخاب خبری که بیشترین احتمال را دارد کاربران عادی آن را
بخوانند، برای دوستانشان بفرستند و درباره آن صحبت کنند.

معیارهای انتخاب:

1. جذابیت برای کاربر عادی ایرانی
2. تازگی و اهمیت خبر
3. کاربرد واقعی برای مردم
4. عجیب یا جالب بودن
5. مربوط بودن به AI، ChatGPT، موبایل، آیفون،
سامسونگ، اندروید، بازی، PS5، Xbox، اینترنت،
امنیت، خودروهای هوشمند و فناوری‌های روز
6. قابلیت ایجاد کنجکاوی
7. قابلیت وایرال شدن
8. اعتبار و اهمیت موضوع

اخبار خشک شرکتی، سرمایه‌گذاری، گزارش مالی،
ابزارهای بسیار تخصصی برنامه‌نویسی و اخبار کم‌اهمیت
را در اولویت پایین قرار بده.

فقط و فقط شماره خبر انتخاب‌شده را در خروجی بنویس.

مثلاً:

3

اخبار:

{news_text}
"""


    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.2,

            max_tokens=50
        )


        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )


        digits = ""

        for char in result:

            if char.isdigit():
                digits += char


        if not digits:

            print(
                "⚠️ AI شماره خبر را مشخص نکرد."
            )

            return candidates[0]


        index = int(digits) - 1


        if (
            index < 0
            or index >= len(candidates)
        ):

            return candidates[0]


        selected = candidates[index]


        print("===================================")
        print("🔥 AI خبر وایرال‌تر را انتخاب کرد:")
        print(selected["title"])
        print(
            f"⭐ امتیاز اولیه: {selected['score']}"
        )
        print("===================================")


        return selected


    except Exception as e:

        print(
            f"❌ AI Selection Error: {e}"
        )

        return candidates[0]


# ==============================
# Get Best News
# ==============================

def get_news():

    all_news = collect_news()


    if not all_news:

        print(
            "❌ خبر جدیدی پیدا نشد."
        )

        return None


    # مرتب‌سازی اولیه
    all_news.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    print("===================================")
    print("🏆 پنج خبر برتر اولیه:")


    for item in all_news[:5]:

        print(
            f"{item['score']} امتیاز | "
            f"{item['title']}"
        )


    print("===================================")


    # فقط چند گزینه برتر برای AI
    candidates = all_news[
        :AI_CANDIDATES
    ]


    selected = ai_select_best_news(
        candidates
    )


    return selected


# ==============================
# Rewrite News
# ==============================

def rewrite_news(news):

    print(
        "🤖 در حال تبدیل خبر به محتوای جذاب..."
    )

    print("===================================")


    prompt = f"""
تو سردبیر حرفه‌ای کانال فناوری فارسی «فناوری‌یار» هستی.

مخاطبان کانال عمدتاً کاربران ایرانی عادی هستند.

این خبر را به یک پست بسیار جذاب، طبیعی و قابل فهم فارسی تبدیل کن.

قوانین:

1. ترجمه کلمه‌به‌کلمه ممنوع.
2. فارسی روان و طبیعی بنویس.
3. تیتر باید کوتاه و بسیار جذاب باشد.
4. دو جمله اول باید قلاب داشته باشند.
5. توضیح بده دقیقاً چه اتفاقی افتاده.
6. توضیح بده چرا این خبر برای کاربر معمولی مهم است.
7. اگر قابلیت یا محصول جدید است، کاربردش را واضح توضیح بده.
8. اطلاعات جعلی یا خارج از خبر اضافه نکن.
9. اغراق در حد تی
