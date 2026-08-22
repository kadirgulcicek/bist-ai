"""
BIST AI - Telegram Bildirim Botu
- Günlük analiz raporu gönderir
- Belirli sinyaller geldiğinde uyarır
- Hızlı hisse sorgusu yapılabilir
"""

import asyncio
import os
from datetime import datetime
import time
import telegram
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class BISTTelegramBot:
    def __init__(self, token, chat_id):
        """Bot başlat"""
        self.token = token
        self.chat_id = chat_id
        self.bot = telegram.Bot(token=token)
    
    async def mesaj_gonder(self, mesaj):
        """Basit mesaj gönder"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='HTML'
            )
            return True
        except Exception as e:
            print(f"❌ Mesaj gönderilemedi: {e}")
            return False
    
    def mesaj_gonder_sync(self, mesaj):
        """Senkron mesaj gönder (async olmadan)"""
        try:
            return asyncio.run(self.mesaj_gonder(mesaj))
        except Exception as e:
            print(f"  Hata: {e}")
            return False
    
    async def gunluk_rapor(self, hisse_sonuclari):
        """Günlük analiz raporu gönder"""
        baslik = f"""
📊 <b>BIST AI - GÜNLÜK RAPOR</b>
🗓️ {datetime.now().strftime('%d.%m.%Y %H:%M')}

{'='*30}
"""
        
        # En iyi 3 al fırsatı
        sirali = sorted(hisse_sonuclari, key=lambda x: x.get('super_skor', 0), reverse=True)
        
        al_listesi = "\n🚀 <b>EN İYİ AL FIRSATLARI</b>\n"
        for s in sirali[:3]:
            if s.get('super_skor', 0) > 0:
                al_listesi += f"✅ {s['sembol']}: {s['fiyat']} TL (Skor: {s['super_skor']:+.2f})\n"
        
        # Sat sinyalleri
        sat_listesi = "\n📉 <b>SAT SİNYALLERİ</b>\n"
        for s in sirali[-3:]:
            if s.get('super_skor', 0) < 0:
                sat_listesi += f"🔴 {s['sembol']}: {s['fiyat']} TL (Skor: {s['super_skor']:+.2f})\n"
        
        uyari = "\n⚠️ <i>Bu yatırım tavsiyesi değildir. Kendi araştırmanızı yapın.</i>"
        
        tam_mesaj = baslik + al_listesi + sat_listesi + uyari
        await self.mesaj_gonder(tam_mesaj)
    
    async def sinyal_bildirimi(self, sembol, sinyal_tipi, detaylar):
        """Anlık sinyal bildirimi"""
        if sinyal_tipi == 'güçlü_al':
            emoji = '🚀'
            renk = 'YEŞİL'
        elif sinyal_tipi == 'güçlü_sat':
            emoji = '⛔'
            renk = 'KIRMIZI'
        else:
            emoji = '⚠️'
            renk = 'SARI'
        
        mesaj = f"""
{emoji} <b>{sembol} - {sinyal_tipi.upper()}</b>

💰 Fiyat: {detaylar.get('fiyat', 'N/A')} TL
📊 Skor: {detaylar.get('super_skor', 0):+.2f}
📈 Teknik: {detaylar.get('teknik_skor', 0):+d}
🤖 AI Güven: %{detaylar.get('ai_guven', 0):.0f}

  {datetime.now().strftime('%H:%M')}
"""
        await self.mesaj_gonder(mesaj)
    
    async def haber_uyarisi(self, baslik, hisse, sentiment):
        """Önemli haber uyarısı"""
        if sentiment == 'pozitif':
            emoji = '📈'
        else:
            emoji = '📉'
        
        mesaj = f"""
{emoji} <b>ÖNEMLİ HABER</b>

📰 {baslik}
🏷️ Hisse: {hisse}
💭 Etki: {sentiment}

⏰ {datetime.now().strftime('%H:%M')}
"""
        await self.mesaj_gonder(mesaj)


# Basit test fonksiyonu
if __name__ == "__main__":
    print("=" * 50)
    print("📱 TELEGRAM BOT TEST")
    print("=" * 50)
    
    load_dotenv()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    if not TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env dosyasında tanımlı olmalı.")
        raise SystemExit(1)
    
    bot = BISTTelegramBot(TOKEN, CHAT_ID)
    
    test_mesaj = """
🎉 <b>BIST AI Bot Aktif!</b>

Bot başarıyla çalışıyor. Artık:
✅ Günlük rapor alacaksınız
✅ Önemli sinyaller size bildirilecek
✅ Hisse sorguları yapabileceksiniz

/yardım yazarak komutları görebilirsiniz.
"""
    
    basarili = bot.mesaj_gonder_sync(test_mesaj)
    if basarili:
        print("✅ Test mesajı gönderildi! Telegram'ı kontrol edin.")
    else:
        print("❌ Mesaj gönderilemedi. Token veya Chat ID yanlış olabilir.")
