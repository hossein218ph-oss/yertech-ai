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

        with open(
            STATE_FILE,
            "r"
        ) as f:

            return float(
                f.read().strip()
            )

    except:

        return 0


def save_last_post_time():

    with open(
        STATE_FILE,
        "w"
    ) as f:

        f.write(
            str(time.time())
        )


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

        f.write(
            news_id + "\n"
        )


# ==============================
# News ID
# ==============================

def make_news_id(link, title):

    value = link + title

    return hashlib.md5(
        value.encode("utf-8")
    ).hexdigest()


# ==============================
# News Score
# ==============================

def calculate_score(title, summary):

    text = (
        title + " " + summary
    ).lower()

    score = 0

    # موضوعات بسیار جذاب برای مخاطب عمومی ایران
    high_priority = [
        "chatgpt",
        "openai",
        "artificial intelligence",
        "ai",
        "iphone",
        "ios",
        "android",
        "samsung",
        "google",
        "pixel",
        "telegram",
        "whatsapp",
        "instagram",
        "youtube",
        "playstation",
        "ps5",
        "xbox",
        "gaming",
        "game",
        "nvidia",
        "amd",
        "intel",
        "laptop",
        "smartphone",
        "phone",
        "cybersecurity",
        "hack",
        "hacked",
        "privacy",
        "robot",
        "robotics",
        "electric car",
        "tesla",
        "self driving",
        "autonomous"
    ]

    for keyword in high_priority:

        if keyword in text:
            score += 5


    # موضوعات جذاب ولی کمی تخصصی‌تر
    medium_priority = [
        "cloud",
        "chip",
        "processor",
        "gpu",
        "browser",
        "windows",
        "macos",
        "apple",
        "microsoft",
        "meta",
        "amazon",
        "web",
        "internet",
        "software",
        "hardware",
        "startup"
    ]

    for keyword in medium_priority:

        if keyword in text:
            score += 3


    # موضوعات کم‌جذاب برای مخاطب عمومی
    low_priority = [
        "enterprise",
        "funding",
        "venture capital",
        "corporate",
        "developer tools",
        "api pricing",
        "acquisition"
    ]

    for keyword in low_priority:

        if keyword in text:
            score -= 2


    # اخبار دارای کلمات جذاب خبری
    viral_words = [
        "new",
        "launch",
        "reveals",
        "revealed",
        "announces",
        "announced",
        "update",
        "major",
        "breakthrough",
        "secret",
        "free",
        "faster",
        "powerful",
        "first",
        "future"
    ]

    for keyword in viral_words:

        if keyword in text:
            score += 2


    return score


# ==============================
# Get News
# ==============================

def get_news():

    print("===================================")
    print("📰 در حال بررسی و رتبه‌بندی اخبار...")
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

                score = calculate_score(
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


    if not all_news:

        print(
            "❌ خبر جدیدی پیدا نشد."
        )

        return None


    # مرتب‌سازی بر اساس جذابیت
    all_news.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    print("===================================")
    print("🏆 اخبار برتر:")

    for item in all_news[:5]:

        print(
            f"{item['score']} امتیاز | "
            f"{item['title']}"
        )

    print("===================================")


    news = all_news[0]


    print(
        "🔥 خبر انتخاب شد:"
    )

    print(
        news["title"]
    )

    print(
        f"⭐ امتیاز جذابیت: {news['score']}"
    )

    print("===================================")


    return news


# ==============================
# Rewrite News With Groq
# ==============================

def rewrite_news(news):

    print(
        "🤖 در حال تبدیل خبر به محتوای جذاب فارسی..."
    )

    print("===================================")


    prompt = f"""
تو سردبیر حرفه‌ای یک کانال فناوری فارسی به نام «فناوری‌یار» هستی.

مخاطبان کانال عمدتاً کاربران ایرانی عادی هستند، نه برنامه‌نویسان یا متخصصان فناوری.

هدف این است که خبر خارجی زیر را به یک پست فارسی جذاب، قابل فهم و ارزشمند تبدیل کنی.

قوانین بسیار مهم:

1. متن را ترجمه کلمه‌به‌کلمه نکن.
2. فارسی طبیعی و محاوره‌ای اما حرفه‌ای بنویس.
3. تیتر باید جذاب و کنجکاوکننده باشد.
4. در دو جمله اول یک قلاب جذاب ایجاد کن.
5. اگر خبر درباره محصول یا قابلیت جدید است، خیلی واضح بگو چه چیزی تغییر کرده.
6. توضیح بده این خبر چرا برای یک کاربر معمولی مهم است.
7. اگر کاربرد واقعی برای کاربران دارد، آن را توضیح بده.
8. اطلاعاتی که در خبر اصلی نیست اضافه نکن.
9. از اغراق و تیتر دروغین استفاده نکن.
10. متن حدود 120 تا 200 کلمه باشد.
11. پاراگراف‌ها کوتاه باشند.
12. از ایموجی‌های مناسب و محدود استفاده کن.
13. در پایان 4 تا 6 هشتگ مرتبط فارسی قرار بده.
14. لینک منبع را در پایان قرار بده.
15. نام کانال یا @yartech را خودت اضافه نکن.
16. درباره هوش مصنوعی یا نحوه تولید این متن صحبت نکن.
17. متن باید مستقیماً قابل انتشار در بله باشد.
18. اگر خبر به یک محصول معروف مربوط است، نام محصول را به شکل واضح در تیتر بیاور.
19. اگر خبر قابلیت جالب یا عجیب دارد، روی همان قابلیت تمرکز کن.
20. از عبارت‌های کلیشه‌ای مثل «دنیای فناوری روزبه‌روز در حال پیشرفت است» استفاده نکن.

ساختار:

🚀 [تیتر جذاب]

[یک شروع کوتاه و کنجکاوکننده]

[توضیح ساده و کاربردی خبر]

[چرا این خبر مهم است یا چه کاربردی دارد؟]

🔗 منبع:
{news["link"]}

#فناوری #تکنولوژی #هوش_مصنوعی

عنوان اصلی خبر:
{news["title"]}

خلاصه خبر:
{news["summary"]}
"""


    response = client.chat.completions.create(

        model="openai/gpt-oss-120b",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.8,

        max_tokens=900
    )


    rewritten = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )


    # آیدی کانال
    rewritten += (
        f"\n\n📢 {CHANNEL_USERNAME}"
    )


    print("===================================")
    print(
        "✅ خبر با سبک مخصوص مخاطب ایرانی آماده شد."
    )
    print(
        "📢 آیدی کانال اضافه شد."
    )
    print("===================================")


    return rewritten


# ==============================
# Send To Bale
# ==============================

def send_to_bale(message):

    print(
        "📤 در حال ارسال به بله..."
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
                    "✅ پست با موفقیت در بله منتشر شد."
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
# Start
# ==============================

print("===================================")
print("🚀 فناوری‌یار شروع شد.")
print("🤖 AI Engine: Groq")
print("📰 Smart RSS Selection: Active")
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
                f"⏳ هنوز زمان انتشار نرسیده. "
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


        rewritten = rewrite_news(
            news
        )


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
