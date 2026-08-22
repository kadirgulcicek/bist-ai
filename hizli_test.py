"""
Hızlı Telegram Test - Tüm sistemi çalıştırır
"""

from telegram_bot import BISTTelegramBot
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise RuntimeError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env dosyasında tanımlı olmalı.")

bot = BISTTelegramBot(TOKEN, CHAT_ID)

mesaj = """
🎉 <b>TELEGRAM BOT TEST BAŞARILI!</b>

✅ Bot bağlantısı çalışıyor
✅ Mesaj gönderimi başarılı
✅ Sistem hazır

📱 Artık bildirim alacaksınız!

Devam etmek için /devam yazın.
"""

if bot.mesaj_gonder_sync(mesaj):
    print("✅ Telegram'a mesaj gönderildi!")
    print("📱 Telefonunuzu kontrol edin!")
else:
    print("❌ Mesaj gönderilemedi. Token/Chat ID kontrol edin.")
