import os
import time
import hashlib
import threading
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
# Render Health Server
# ==============================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Yertech AI is running.")

    def log_message(self, format, *args):
        return


def start_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)

    print("===================================")
    print(f"🌐 Render HTTP server فعال شد روی پورت {PORT}")
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
# Get News
# ==============================

def get_news():

    print("===================================")
    print("در حال دریافت اخبار...")
    print("===================================")

    used_news = get_used_news()

    all_news = []

    for feed_url in RSS_FEEDS:

        try:

            print(f"Checking RSS: {feed_url}")

            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:10]:

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

                all_news.append({
                    "id": news_id,
                    "title": title,
                    "link": link,
                    "summary": summary
                })

        except Exception as e:

            print(
                f"❌ RSS Error: {e}"
            )

    if not all_news:

        print(
            "❌ خبر جدیدی پیدا نشد."
        )

        return None

    news = all_news[0]

    print("===================================")
    print("خبر انتخاب شد:")
    print(news["title"])
    print("===================================")

    return news


# ==============================
# Rewrite News With Groq
# ==============================

def rewrite_news(news):

    print(
        "در حال بازنویسی خبر با Groq..."
    )

    print("===================================")

    prompt = f"""
تو نویسنده حرفه‌ای یک کانال فناوری فارسی هستی.

خبر زیر را به یک پست جذاب و حرفه‌ای فارسی برای کانال بله تبدیل کن.

قوانین:

1. متن فارسی روان و طبیعی باشد.
2. اصل خبر را تغییر نده.
3. اطلاعاتی که در خبر وجود ندارد اضافه نکن.
4. متن حدود 100 تا 180 کلمه باشد.
5. تیتر کوتاه، جذاب و خبری باشد.
6. از ایموجی‌های مناسب استفاده کن.
7. در پایان 4 تا 6 هشتگ مرتبط قرار بده.
8. لینک منبع خبر را در پایان قرار بده.
9. متن آماده انتشار مستقیم در کانال باشد.
10. درباره نحوه تولید متن یا هوش مصنوعی توضیح نده.
11. نام کانال یا آیدی کانال را اضافه نکن. آیدی توسط سیستم اضافه خواهد شد.

عنوان خبر:

{news["title"]}

خلاصه خبر:

{news["summary"]}

لینک منبع:

{news["link"]}

فرمت خروجی:

🚀 [عنوان جذاب]

[متن خبر]

🔗 منبع:
{news["link"]}

#فناوری #تکنولوژی #هوش_مصنوعی
"""

    response = client.chat.completions.create(

        model="openai/gpt-oss-120b",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.7,

        max_tokens=700
    )

    rewritten = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    # اضافه کردن آیدی کانال
    rewritten += (
        f"\n\n📢 {CHANNEL_USERNAME}"
    )

    print("===================================")
    print("بازنویسی با موفقیت انجام شد.")
    print("آیدی کانال به انتهای پست اضافه شد.")
    print("===================================")

    return rewritten


# ==============================
# Send To Bale
# ==============================

def send_to_bale(message):

    print(
        "در حال ارسال به بله..."
    )

    url = (
        f"https://tapi.bale.ai/"
        f"bot{BALE_BOT_TOKEN}/sendMessage"
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

            data = response.json()

            if data.get("ok") is True:

                print("===================================")
                print(
                    "پست با موفقیت در بله منتشر شد."
                )
                print("===================================")

                return True

        print(
            "❌ ارسال به بله ناموفق بود."
        )

        print(
            response.text
        )

        return False

    except Exception as e:

        print(
            f"❌ Bale Error: {e}"
        )

        return False


# ==============================
# Start Bot
# ==============================

print("===================================")
print("🚀 فناوری‌یار شروع شد.")
print("🤖 AI Engine: Groq")
print("📰 RSS: Active")
print("📢 Bale: Active")
print("📢 Channel: @yartech")
print("🌐 Render Port: Active")
print("⏰ فاصله انتشار: 1 ساعت")
print("===================================")


# ==============================
# Main Loop
# ==============================

while True:

    try:

        last_post = get_last_post_time()

        current_time = time.time()

        if (
            current_time - last_post
            < POST_INTERVAL
        ):

            remaining = int(
                POST_INTERVAL
                - (
                    current_time
                    - last_post
                )
            )

            minutes = remaining // 60

            print(
                f"هنوز زمان انتشار نرسیده. "
                f"حدود {minutes} دقیقه باقی مانده."
            )

            time.sleep(
                CHECK_INTERVAL
            )

            continue


        news = get_news()

        if not news:

            print(
                "بررسی بعدی 10 دقیقه دیگر..."
            )

            time.sleep(
                CHECK_INTERVAL
            )

            continue


        rewritten = rewrite_news(news)

        success = send_to_bale(
            rewritten
        )


        if success:

            save_used_news(
                news["id"]
            )

            save_last_post_time()

            print(
                "🎉 چرخه انتشار با موفقیت انجام شد."
            )

        else:

            print(
                "⚠️ ارسال انجام نشد؛ "
                "خبر به عنوان استفاده‌شده ثبت نشد."
            )


        print(
            "بررسی بعدی 10 دقیقه دیگر..."
        )

        time.sleep(
            CHECK_INTERVAL
        )


    except Exception as e:

        print("===================================")
        print("❌ ERROR:")
        print(e)
        print("===================================")

        print(
            "بررسی بعدی 10 دقیقه دیگر..."
        )

        time.sleep(
            CHECK_INTERVAL
        )
