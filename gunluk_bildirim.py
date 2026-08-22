"""
Her gün otomatik rapor gönderir
- Sabah açılışta analiz
- Öğlen güncelleme
- Akşam kapanış özeti
"""

from telegram_bot import BISTTelegramBot
from sosyal_medya_analiz import TamYatirimSistemi
from hisse_listesi import hisse_listesi_getir
from datetime import datetime
import time
import schedule


class GunlukBildirim:
    def __init__(self, token, chat_id):
        self.bot = BISTTelegramBot(token, chat_id)
        self.sistem = TamYatirimSistemi()
    
    def sabah_raporu(self):
        """Piyasa açılışında rapor"""
        print("📊 Sabah raporu hazırlanıyor...")
        hisseler = hisse_listesi_getir()[:10]  # İlk 10 hisse
        sonuclar = []
        
        for sembol in hisseler:
            try:
                sonuc = self.sistem.tek_hisse_super_analiz(sembol)
                if sonuc:
                    sonuc['sembol'] = sembol.replace('.IS', '')
                    sonuclar.append(sonuc)
                time.sleep(1)
            except:
                continue
        
        # Async çalıştır
        asyncio.run(self.bot.gunluk_rapor(sonuclar))
        print("✅ Sabah raporu gönderildi!")
    
    def oglen_guncelleme(self):
        """Öğlen güncelleme"""
        mesaj = f"""
🔔 <b>ÖĞLEN GÜNCELLEMESİ</b>
⏰ {datetime.now().strftime('%H:%M')}

  Piyasalar aktif takip ediliyor.
Yeni sinyaller geldiğinde bildirim alacaksınız.

Detaylı analiz için /analiz yazın.
"""
        self.bot.mesaj_gonder_sync(mesaj)
    
    def aksam_ozeti(self):
        """Akşam kapanış özeti"""
        mesaj = f"""
🌙 <b>AKŞAM KAPANIŞ ÖZETİ</b>
  {datetime.now().strftime('%d.%m.%Y')}

📊 Bugünkü analizler tamamlandı.
📁 Detaylı rapor dosyaları kaydedildi.

Yarın sabah 09:00'da yeni rapor ile görüşmek üzere!
💤 İyi geceler...
"""
        self.bot.mesaj_gonder_sync(mesaj)
    
    def baslat(self):
        """Zamanlayıcıyı başlat"""
        schedule.every().day.at("09:00").do(self.sabah_raporu)
        schedule.every().day.at("13:00").do(self.oglen_guncelleme)
        schedule.every().day.at("18:00").do(self.aksam_ozeti)
        
        print("⏰ Zamanlayıcı başlatıldı!")
        print("   09:00 - Sabah raporu")
        print("   13:00 - Öğlen güncelleme")
        print("   18:00 - Akşam özeti")
        print("\n  Test için şimdi bir rapor göndermek ister misiniz? (e/h)")
        
        cevap = input("> ").lower()
        if cevap == 'e':
            self.sabah_raporu()
        
        print("\n🔄 Program arka planda çalışıyor... (Durdurmak için Ctrl+C)")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


import asyncio

if __name__ == "__main__":
    print("=" * 50)
    print("⏰ GÜNLÜK BİLDİRİM SİSTEMİ")
    print("=" * 50)
    
    TOKEN = "8767340022:AAFCRoyZGCqDRdjgGLpcX56oHEXmml4D-ec"
    CHAT_ID = "2035245736"
    
    bildirim = GunlukBildirim(TOKEN, CHAT_ID)
    bildirim.baslat()
