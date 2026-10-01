import os
import time
import requests

TOKEN = os.getenv("BALE_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("BALE_CHANNEL", "@Yertech").strip()
TEST_MESSAGE = os.getenv(
    "TEST_MESSAGE",
    "🚀 سلام از Yertech AI!\n\nاتصال ربات به کانال فناوری‌یار با موفقیت تست شد. 🤖"
)

API_BASE = f"https://tapi.bale.ai/bot{TOKEN}"


def send_message(text: str):
    if not TOKEN:
        raise RuntimeError("BALE_BOT_TOKEN is not set.")

    url = f"{API_BASE}/sendMessage"
    payload = {
        "chat_id": CHANNEL,
        "text": text,
    }

    response = requests.post(url, json=payload, timeout=30)
    print("Bale API status:", response.status_code)
    print("Bale API response:", response.text)

    response.raise_for_status()
    data = response.json()

    if not data.get("ok", False):
        raise RuntimeError(f"Bale API error: {data}")

    return data


def main():
    print("Yertech AI starting...")
    print("Channel:", CHANNEL)

    send_message(TEST_MESSAGE)

    # Keep the Render Web Service alive for the first test.
    # The production scheduler will replace this loop later.
    while True:
        time.sleep(300)


if __name__ == "__main__":
    main()
