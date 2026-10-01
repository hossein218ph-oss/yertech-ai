import os
import threading
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


def send_message(text):
    if not TOKEN:
        raise RuntimeError("BALE_BOT_TOKEN is not set.")

    url = f"{API_BASE}/sendMessage"

    payload = {
        "chat_id": CHANNEL,
        "text": text
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30
    )

    print("Bale API status:", response.status_code)
    print("Bale API response:", response.text)

    response.raise_for_status()

    data = response.json()

    if not data.get("ok", False):
        raise RuntimeError(
            f"Bale API error: {data}"
        )

    return data


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
        f"HTTP health server listening on port {PORT}"
    )

    server.serve_forever()


def main():

    if not TOKEN:
        raise RuntimeError(
            "BALE_BOT_TOKEN is not set."
        )

    threading.Thread(
        target=start_http_server,
        daemon=True
    ).start()

    print("Yertech AI starting...")

    send_message(TEST_MESSAGE)

    print(
        "Test message sent successfully to",
        CHANNEL
    )


if __name__ == "__main__":
    main()
