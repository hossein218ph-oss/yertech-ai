import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests


TOKEN = os.getenv("BALE_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("BALE_CHANNEL", "@Yertech").strip()

TEST_MESSAGE = os.getenv(
    "TEST_MESSAGE",
    "🚀 سلام از Yertech AI!\n\n"
    "اتصال ربات به کانال فناوری‌یار با موفقیت تست شد. 🤖"
)

PORT = int(os.getenv("PORT", "10000"))

API_BASE = f"https://tapi.bale.ai/bot{TOKEN}"


# -----------------------------------
# دریافت اطلاعات آپدیت‌های بله
# -----------------------------------

def get_updates():

    if not TOKEN:
        print("ERROR: BALE_BOT_TOKEN is not set.")
        return

    url = f"{API_BASE}/getUpdates"

    try:

        response = requests.get(
            url,
            timeout=30
        )

        print("")
        print("===================================")
        print("GET UPDATES STATUS:", response.status_code)
        print("GET UPDATES RESPONSE:")
        print(response.text)
        print("===================================")
        print("")

    except Exception as e:

        print("getUpdates failed:", repr(e))


# -----------------------------------
# ارسال پیام آزمایشی
# -----------------------------------

def send_message():

    if not TOKEN:
        print("ERROR: BALE_BOT_TOKEN is not set.")
        return

    url = f"{API_BASE}/sendMessage"

    payload = {
        "chat_id": CHANNEL,
        "text": TEST_MESSAGE
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=30
        )

        print("")
        print("BALE API STATUS:", response.status_code)
        print("BALE API RESPONSE:")
        print(response.text)
        print("")

        if response.status_code != 200:
            print("WARNING: Bale API returned an error.")
            return

        try:

            data = response.json()

            if data.get("ok", False):

                print(
                    "SUCCESS: Test message sent to",
                    CHANNEL
                )

            else:

                print(
                    "WARNING: Bale API did not return ok=true."
                )

                print(data)

        except Exception as e:

            print(
                "Could not parse Bale response:",
                repr(e)
            )

    except Exception as e:

        print(
            "Bale API request failed:",
            repr(e)
        )


# -----------------------------------
# سرور HTTP برای Render
# -----------------------------------

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path in ("/", "/health"):

            body = b"Yertech AI is running."

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )

            self.send_header(
                "Content-Length",
                str(len(body))
            )

            self.end_headers()

            self.wfile.write(body)

        else:

            self.send_response(404)

            self.end_headers()

    def log_message(self, format, *args):

        return


# -----------------------------------
# شروع سرور
# -----------------------------------

def start_http_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print(
        f"HTTP server running on 0.0.0.0:{PORT}"
    )

    server.serve_forever()


# -----------------------------------
# برنامه اصلی
# -----------------------------------

def main():

    if not TOKEN:

        print(
            "WARNING: BALE_BOT_TOKEN is not set."
        )

    # ابتدا سرور Render را اجرا می‌کنیم

    server_thread = threading.Thread(
        target=start_http_server,
        daemon=True
    )

    server_thread.start()

    # کمی زمان برای بالا آمدن سرور

    time.sleep(2)

    print("")
    print("===================================")
    print("Yertech AI started.")
    print("===================================")
    print("")

    # --------------------------------
    # دریافت Updates
    # --------------------------------

    print("Checking Bale updates...")

    get_updates()

    # --------------------------------
    # ارسال پیام آزمایشی
    # --------------------------------

    send_thread = threading.Thread(
        target=send_message,
        daemon=True
    )

    send_thread.start()

    # --------------------------------
    # زنده نگه داشتن برنامه
    # --------------------------------

    while True:

        time.sleep(60)


# -----------------------------------
# اجرای برنامه
# -----------------------------------

if __name__ == "__main__":

    main()
