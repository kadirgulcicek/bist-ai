"""
Token ve Chat ID Testi
"""

TOKEN = "BURAYA_BOT_TOKENINI_YAZ"
CHAT_ID = "BURAYA_CHAT_ID_YAZ"

import telegram
from telegram.error import BadRequest, InvalidToken

print("=" * 50)
print("🧪 TOKEN VE CHAT ID TESTİ")
print("=" * 50)

try:
    bot = telegram.Bot(token=TOKEN)
    print(f"✅ Bot oluşturuldu")
    print(f"   Token uzunluğu: {len(TOKEN)} karakter")
    
    # Chat ID kontrolü
    print(f"   Chat ID: {CHAT_ID}")
    
    # Mesaj gönder
    sonuc = bot.send_message(
        chat_id=CHAT_ID,
        text="🎉 Test başarılı! Bot çalışıyor."
    )
    print(f"✅ Mesaj gönderildi! Mesaj ID: {sonuc.message_id}")
    print("\n📱 Şimdi Telegram'ı kontrol edin!")
    
except InvalidToken:
    print("❌ TOKEN YANLIŞ!")
    print("   → BotFather'dan yeni token alın")
    
except BadRequest as e:
    print(f"❌ CHAT ID YANLIŞ veya bot ile /start yazılmamış!")
    print(f"   Hata: {e}")
    print("   → Botunuza gidin ve /start yazın")
    print("   → getUpdates'den doğru chat ID'yi alın")
    
except Exception as e:
    print(f"❌ Beklenmeyen hata: {e}")

input("\nÇıkmak için Enter'a basın...")
