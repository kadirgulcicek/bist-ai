"""
Chat ID ve Token Doğrulama Testi
"""

import asyncio
import os

import telegram
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise RuntimeError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env dosyasında tanımlı olmalı.")

print("=" * 50)
print("🧪 CHAT ID DOĞRULAMA TESTİ")
print("=" * 50)
async def main():
    try:
        async with telegram.Bot(token=TOKEN) as bot:
            bot_info = await bot.get_me()
            print("\n✅ Bot bağlantısı başarılı!")
            print(f"   Bot adı: @{bot_info.username}")

            mesaj = await bot.send_message(
                chat_id=CHAT_ID,
                text="✅ Doğrulama başarılı!"
            )
            print("\n✅ Telegram'a mesaj gönderildi!")
            print(f"   Mesaj ID: {mesaj.message_id}")

    except telegram.error.Unauthorized:
        print("\n❌ TOKEN GEÇERSİZ!")
        print("   BotFather'dan yeni token alın")
    except telegram.error.BadRequest as hata:
        print(f"\n❌ CHAT ID HATASI: {hata}")
        print("   Bot ile /start yazın ve Chat ID'yi kontrol edin")
    except Exception as hata:
        print(f"\n❌ Hata: {hata}")


asyncio.run(main())
