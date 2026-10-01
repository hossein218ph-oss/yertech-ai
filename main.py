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

        print("Bale API status:", response.status_code)
        print("Bale API response:", response.text)

        if response.status_code != 200:
            print("WARNING: Bale API returned an error.")
            return

        data = response.json()

        if not data.get("ok", False):
            print("WARNING: Bale API did not return ok=true.")
            print(data)
            return

        print("SUCCESS: Test message sent to", CHANNEL)

    except Exception as e:

        print("Bale API request failed:", repr(e))


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


def start_http_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print(
        f"HTTP server running on 0.0.0.0:{PORT}"
    )

    server.serve_forever()


def main():

    if not TOKEN:
        print("WARNING: BALE_BOT_TOKEN is not set.")

    # Start Render HTTP server first
    server_thread = threading.Thread(
        target=start_http_server,
        daemon=True
    )

    server_thread.start()

    # Give the server a moment to start
    time.sleep(2)

    print("Yertech AI started.")

    # Send Bale message without killing the web server
    send_thread = threading.Thread(
        target=send_message,
        daemon=True
    )

    send_thread.start()

    # Keep the main process alive
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
