import os
import time
import hashlib
import feedparser
import requests
from openai import OpenAI

# =========================
# تنظیمات
# =========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

CHECK_INTERVAL = 10 * 60
POST_INTERVAL = 60 * 60

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss"
]

STATE_FILE = "state.txt"
USED_NEWS_FILE = "used_news.txt"

# =========================
# بررسی تنظیمات
# =========================

if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY تنظیم نشده است.")
    exit()

if not BALE_BOT_TOKEN:
    print("❌ BALE_BOT_TOKEN تنظیم نشده است.")
    exit()

if not BALE_CHAT_ID:
    print("❌ BALE_CHAT_ID تنظیم نشده است.")
    exit()

# =========================
# اتصال به Groq
# =========================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# =========================
# زمان آخرین انتشار
# =========================

def get_last_post_time():
    try:
        with open(STATE_FILE, "r") as f:
            return float(f.read().strip())
    except:
        return 0


def save_last_post_time():
    with open(STATE_FILE, "w") as f:
        f.write(str(time.time()))


# =========================
# اخبار استفاده‌شده
# =========================

def get_used_news():
    try:
        with open(USED_NEWS_FILE, "r", encoding="utf-8") as f:
            return set(
                line.strip()
                for line in f
                if line.strip()
            )
    except:
        return set()


def save_used_news(news_id):
    with open(USED_NEWS_FILE, "a", encoding="utf-8") as f:
        f.write(news_id + "\n")


# =========================
# ساخت شناسه خبر
# =========================

def make_news_id(link, title):
    value = link + title
    return hashlib.md5(
        value.encode("utf-8")
    ).hexdigest()


# =========================
# دریافت اخبار RSS
# =========================

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


# =========================
# بازنویسی خبر با Groq
# =========================

def rewrite_news(news):

    print("در حال بازنویسی خبر با Groq...")
    print("===================================")

    prompt = f"""
تو نویسنده کانال فناوری فارسی «فناوری‌یار» هستی.

خبر زیر را به یک پست جذاب و حرفه‌ای فارسی برای کانال بله تبدیل کن.

قوانین:

1. متن فارسی روان و طبیعی باشد.
2. اصل خبر را تغییر نده.
3. اطلاعاتی که در خبر وجود ندارد اضافه نکن.
4. متن حدود 100 تا 180 کلمه باشد.
5. شروع متن جذاب باشد.
6. از ایموجی‌های مناسب استفاده کن.
7. در پایان 4 تا 6 هشتگ مرتبط قرار بده.
8. لینک منبع خبر را در پایان قرار بده.
9. عبارت «فناوری‌یار» فقط در امضای پایانی استفاده شود.
10. متن برای انتشار مستقیم در کانال آماده باشد.
11. درباره نحوه تولید متن توضیح نده.

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

— فناوری‌یار
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

    rewritten = response.choices[0].message.content.strip()

    print("===================================")
    print("بازنویسی با موفقیت انجام شد.")
    print("===================================")

    return rewritten


# =========================
# ارسال پیام به بله
# =========================

def send_to_bale(message):

    print("در حال ارسال به بله...")

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
                print("پست با موفقیت در بله منتشر شد.")
                print("===================================")

                return True

        print(
            "❌ ارسال به بله ناموفق بود."
        )

        print(response.text)

        return False

    except Exception as e:

        print(
            f"❌ Bale Error: {e}"
        )

        return False


# =========================
# شروع برنامه
# =========================

print("===================================")
print("🚀 فناوری‌یار شروع شد.")
print("🤖 AI Engine: Groq")
print("📰 RSS: Active")
print("📢 Bale: Active")
print("⏰ فاصله انتشار: 1 ساعت")
print("===================================")


# =========================
# حلقه اصلی
# =========================

while True:

    try:

        last_post = get_last_post_time()
        current_time = time.time()

        # بررسی فاصله یک‌ساعته
        if current_time - last_post < POST_INTERVAL:

            remaining = int(
                POST_INTERVAL
                - (current_time - last_post)
            )

            minutes = remaining // 60

            print(
                f"هنوز زمان انتشار نرسیده. "
                f"حدود {minutes} دقیقه باقی مانده."
            )

            time.sleep(CHECK_INTERVAL)

            continue

        # دریافت خبر
        news = get_news()

        if not news:

            print(
                "بررسی بعدی 10 دقیقه دیگر..."
            )

            time.sleep(CHECK_INTERVAL)

            continue

        # بازنویسی
        rewritten = rewrite_news(news)

        # ارسال به بله
        success = send_to_bale(
            rewritten
        )

        if success:

            save_used_news(
                news["id"]
            )

            save_last_post_time()

            print(
                "چرخه انتشار با موفقیت انجام شد."
            )

        else:

            print(
                "ارسال انجام نشد؛ "
                "خبر به عنوان استفاده‌شده ثبت نشد."
            )

        print(
            "بررسی بعدی 10 دقیقه دیگر..."
        )

        time.sleep(CHECK_INTERVAL)

    except Exception as e:

        print("===================================")
        print("❌ ERROR:")
        print(e)
        print("===================================")

        print(
            "بررسی بعدی 10 دقیقه دیگر..."
        )

        time.sleep(CHECK_INTERVAL)
