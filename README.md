# Yertech AI - Bale Bot

نسخه آزمایشی ربات کانال فناوری‌یار (`@Yertech`).

## کار نسخه اول

ربات با استفاده از Bale Bot API یک پیام آزمایشی را به کانال ارسال می‌کند.

## متغیرهای محیطی

- `BALE_BOT_TOKEN`: توکن ربات که از BotFather گرفته‌اید.
- `BALE_CHANNEL`: به صورت پیش‌فرض `@Yertech`
- `TEST_MESSAGE`: متن پیام آزمایشی.

## نکته امنیتی

توکن ربات را داخل کد، GitHub یا پیام چت قرار ندهید.
توکن فقط باید در Environment Variables / Secrets سرویس میزبانی قرار بگیرد.

## اجرای محلی

```bash
pip install -r requirements.txt
BALE_BOT_TOKEN="YOUR_TOKEN" python main.py
```

## Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
python main.py
```

Environment Variable:

```text
BALE_BOT_TOKEN = YOUR_BOT_TOKEN
BALE_CHANNEL = @Yertech
```
