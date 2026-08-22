"""
Her Şey Bir Arada - Portföy + Alarm Kontrolü + Telegram Raporu
"""

from portfoy import Portfoy
from portfoy_analiz import portfoy_analiz_yap
from alarm_sistemi import AlarmSistemi
from telegram_bot import BISTTelegramBot
from datetime import datetime

# BURAYA KENDİ BİLGİLERİNİ YAZ
TOKEN = "BURAYA_TOKEN"
CHAT_ID = "BURAYA_CHAT_ID"

def sabah_raporu_gonder():
    """Sabah raporunu Telegram'a gönderir"""
    print(f"[{datetime.now()}] 📊 Rapor hazırlanıyor...")
    
    # Portföy analizi
    analiz = portfoy_analiz_yap()
    
    if not analiz:
        print("Portföy boş, rapor gönderilmedi.")
        return
    
    # Alarm kontrolü
    alarm = AlarmSistemi(TOKEN, CHAT_ID)
    alarm.alarm_kontrol()
    
    # Telegram mesajı hazırla
    toplam_kar = analiz["toplam_kar"]
    toplam_kar_yuzde = analiz["toplam_kar_yuzde"]
    emoji = "✅" if toplam_kar >= 0 else "📉"
    
    mesaj = f"""
💼 <b>PORTFÖY RAPORU</b>
🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}

💰 Toplam Değer: {analiz['toplam_deger']:,.0f} TL
💵 Maliyet: {analiz['toplam_maliyet']:,.0f} TL
{emoji} <b>Kâr: {toplam_kar:+,.0f} TL ({toplam_kar_yuzde:+.2f}%)</b>

📊 <b>Hisseler:</b>
"""
    
    # En iyi 3
    sirali = sorted(analiz["sonuclar"], key=lambda x: x["kar_yuzde"], reverse=True)
    
    for s in sirali[:5]:
        e = "✅" if s["kar_tl"] >= 0 else " "
        mesaj += f"\n{e} {s['sembol']}: {s['guncel']} TL ({s['kar_yuzde']:+.1f}%)"
    
    # Telegram'a gönder
    bot = BISTTelegramBot(TOKEN, CHAT_ID)
    if bot.mesaj_gonder_sync(mesaj):
        print(f"[{datetime.now()}] ✅ Rapor gönderildi!")
    else:
        print(f"[{datetime.now()}] ❌ Gönderilemedi!")


if __name__ == "__main__":
    sabah_raporu_gonder()
    input("\nÇıkmak için Enter'a basın...")
