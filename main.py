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

# RSS های فناوری
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
]

# هر چند دقیقه RSS بررسی شود
CHECK_INTERVAL = 10

# حداقل فاصله بین دو پست
POST_INTERVAL = 60 * 60

# فایل های وضعیت
STATE_FILE = "state.txt"
USED_NEWS_FILE = "used_news.txt"

# =========================
# اتصال به Groq
# =========================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)


# =========================
# وضعیت آخرین پست
# =========================

def load_last_post_time():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return float(f.read().strip())
    except Exception:
        return 0


def save_last_post_time():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(str(time.time()))


# =========================
# دریافت اخبار از RSS
# =========================

def get_news():
    news = []

    for rss_url in RSS_FEEDS:
        try:
            print(f"Checking RSS: {rss_url}")

            feed = feedparser.parse(rss_url)

            for entry in feed.entries[:10]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()

                if title and link:
                    news.append({
                        "title": title,
                        "link": link,
                        "summary": summary
                    })

        except Exception as e:
            print(f"RSS Error: {e}")

    return news


# =========================
# شناسه خبر
# =========================

def get_news_id(news):
    raw = news["link"] or news["title"]
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# =========================
# بررسی خبر تکراری
# =========================

def is_used(news_id):
    try:
        with open(USED_NEWS_FILE, "r", encoding="utf-8") as f:
            return news_id in f.read().splitlines()

    except FileNotFoundError:
        return False


def mark_used(news_id):
    with open(USED_NEWS_FILE, "a", encoding="utf-8") as f:
        f.write(news_id + "\n")


# =========================
# انتخاب خبر جدید
# =========================

def choose_news(news_list):
    for news in news_list:

        news_id = get_news_id(news)

        if not is_used(news_id):
            return news

    return None


# =========================
# بازنویسی خبر با Groq
# =========================

def rewrite_news(news):

    prompt = f"""
تو سردبیر یک کانال فناوری فارسی به نام «فناوری‌یار» هستی.

خبر زیر را به یک پست فارسی جذاب، کوتاه و حرفه‌ای برای کانال بله تبدیل کن.

قوانین مهم:

- ترجمه تحت‌اللفظی نکن.
- متن را روان و طبیعی به فارسی بنویس.
- اطلاعات اصلی خبر را حفظ کن.
- هیچ اطلاعاتی که در خبر وجود ندارد اضافه نکن.
- تیتر کوتاه و جذاب باشد.
- متن حدود 100 تا 180 کلمه باشد.
- لحن خبری، صمیمی و قابل فهم باشد.
- از ایموجی به اندازه استفاده کن.
- در پایان 4 تا 6 هشتگ مرتبط قرار بده.
- لینک منبع را در انتهای پست قرار بده.
- از عبارت «فناوری‌یار» در متن استفاده نکن، مگر در امضای پایانی.

ساختار پیشنهادی:

🔥 تیتر خبر

متن خبر...

🔗 منبع:
لینک

#فناوری #هوش_مصنوعی #تکنولوژی

عنوان خبر:
{news["title"]}

خلاصه خبر:
{news["summary"]}

لینک:
{news["link"]}
"""

    print("در حال بازنویسی خبر با Groq...")

    response = client.responses.create(
        model="llama-3.3-70b-versatile",
        input=prompt
    )

    return response.output_text.strip()


# =========================
# ارسال پیام به بله
# =========================

def send_to_bale(message):

    url = f"https://tapi.bale.ai/bot{BALE_BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": BALE_CHAT_ID,
        "text": message
    }

    response = requests.post(
        url,
        data=data,
        timeout=30
    )

    print("Bale response:", response.text)

    if response.ok:

        try:
            result = response.json()

            if result.get("ok"):
                return True

        except Exception:
            pass

    return False


# =========================
# پردازش خبر
# =========================

def process_news():

    last_post = load_last_post_time()

    # هنوز یک ساعت از پست قبلی نگذشته
    if time.time() - last_post < POST_INTERVAL:

        remaining = int(
            POST_INTERVAL - (time.time() - last_post)
        )

        print(
            f"هنوز زمان پست بعدی نرسیده. "
            f"حدود {remaining // 60} دقیقه باقی مانده."
        )

        return

    print("===================================")
    print("در حال دریافت اخبار...")
    print("===================================")

    news_list = get_news()

    if not news_list:

        print("هیچ خبری پیدا نشد.")

        return

    news = choose_news(news_list)

    if not news:

        print("خبر جدیدی پیدا نشد.")

        return

    print("===================================")
    print("خبر انتخاب شد:")
    print(news["title"])
    print("===================================")

    try:

        final_text = rewrite_news(news)

        print("===================================")
        print("متن تولید شده:")
        print(final_text)
        print("===================================")

        print("در حال ارسال به بله...")

        success = send_to_bale(final_text)

        if success:

            news_id = get_news_id(news)

            mark_used(news_id)

            save_last_post_time()

            print("===================================")
            print("✅ پست با موفقیت منتشر شد.")
            print("===================================")

        else:

            print("❌ ارسال به بله ناموفق بود.")

    except Exception as e:

        print("===================================")
        print("❌ ERROR:")
        print(e)
        print("===================================")


# =========================
# اجرای برنامه
# =========================

if __name__ == "__main__":

    print("===================================")
    print("🚀 فناوری‌یار شروع شد.")
    print("🤖 AI Engine: Groq")
    print("📰 RSS: Active")
    print("📢 Bale: Active")
    print("⏰ فاصله انتشار: 1 ساعت")
    print("===================================")

    while True:

        try:

            process_news()

        except Exception as e:

            print("MAIN ERROR:")
            print(e)

        print(
            f"بررسی بعدی {CHECK_INTERVAL} دقیقه دیگر..."
        )

        time.sleep(CHECK_INTERVAL * 60)
