import os
import time
import hashlib
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from openai import OpenAI

# =========================
# تنظیمات
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")
BALE_CHAT_ID = os.getenv("BALE_CHAT_ID")

# RSSهای فناوری
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
]

# هر چند دقیقه یک بار بررسی شود
CHECK_INTERVAL = 10

# حداقل فاصله بین دو پست
POST_INTERVAL = 60 * 60

# فایل ذخیره وضعیت
STATE_FILE = "state.txt"

client = OpenAI(api_key=OPENAI_API_KEY)


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
# دریافت RSS
# =========================

def get_news():
    news = []

    for rss_url in RSS_FEEDS:
        try:
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
# جلوگیری از تکرار خبر
# =========================

def get_news_id(news):
    raw = news["link"] or news["title"]
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def is_used(news_id):
    try:
        with open("used_news.txt", "r", encoding="utf-8") as f:
            return news_id in f.read().splitlines()
    except FileNotFoundError:
        return False


def mark_used(news_id):
    with open("used_news.txt", "a", encoding="utf-8") as f:
        f.write(news_id + "\n")


# =========================
# انتخاب خبر
# =========================

def choose_news(news_list):
    for news in news_list:
        news_id = get_news_id(news)

        if not is_used(news_id):
            return news

    return None


# =========================
# بازنویسی با OpenAI
# =========================

def rewrite_news(news):
    prompt = f"""
تو سردبیر کانال فناوری فارسی «فناوری‌یار» هستی.

خبر زیر را به یک پست فارسی جذاب، کوتاه و حرفه‌ای برای کانال بله تبدیل کن.

قوانین:
- ترجمه تحت‌اللفظی نکن.
- متن را روان و طبیعی بنویس.
- اطلاعات اصلی خبر حفظ شود.
- چیزی که در خبر وجود ندارد اضافه نکن.
- از لحن خبری و صمیمی استفاده کن.
- تیتر جذاب و کوتاه باشد.
- متن حدود 100 تا 180 کلمه باشد.
- در پایان 4 تا 6 هشتگ مرتبط قرار بده.
- لینک منبع را در انتهای پست قرار بده.
- از ایموجی به اندازه استفاده کن.
- نام «فناوری‌یار» در متن نیاید مگر در امضای پایانی.

عنوان خبر:
{news["title"]}

خلاصه خبر:
{news["summary"]}

لینک:
{news["link"]}
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text.strip()


# =========================
# ارسال به بله
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
# اجرای اصلی
# =========================

def process_news():

    last_post = load_last_post_time()

    # هنوز یک ساعت نشده
    if time.time() - last_post < POST_INTERVAL:
        print("هنوز یک ساعت از پست قبلی نگذشته است.")
        return

    print("در حال دریافت اخبار...")

    news_list = get_news()

    if not news_list:
        print("هیچ خبری پیدا نشد.")
        return

    news = choose_news(news_list)

    if not news:
        print("خبر جدیدی پیدا نشد.")
        return

    print("خبر انتخاب شد:")
    print(news["title"])

    try:
        print("در حال بازنویسی با OpenAI...")

        final_text = rewrite_news(news)

        print("متن تولید شده:")
        print(final_text)

        print("در حال ارسال به بله...")

        success = send_to_bale(final_text)

        if success:
            news_id = get_news_id(news)
            mark_used(news_id)
            save_last_post_time()

            print("✅ پست با موفقیت منتشر شد.")

        else:
            print("❌ ارسال به بله ناموفق بود.")

    except Exception as e:
        print("ERROR:", e)


# =========================
# Loop
# =========================

if __name__ == "__main__":

    print("🚀 فناوری‌یار شروع شد.")

    while True:

        try:
            process_news()

        except Exception as e:
            print("MAIN ERROR:", e)

        print(f"بررسی بعدی {CHECK_INTERVAL} دقیقه دیگر...")

        time.sleep(CHECK_INTERVAL * 60)
