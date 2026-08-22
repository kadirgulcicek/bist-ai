"""
Fiyat Alarm Sistemi
Belirli fiyat seviyelerine gelince Telegram'dan uyarı gönderir
"""

import json
import os
import yfinance as yf
from datetime import datetime
from telegram_bot import BISTTelegramBot


class AlarmSistemi:
    def __init__(self, telegram_token=None, chat_id=None):
        self.dosya = "alarmlar.json"
        self.alarmlar = self.yukle()
        self.bot = None
        
        if telegram_token and chat_id:
            self.bot = BISTTelegramBot(telegram_token, chat_id)
    
    def yukle(self):
        """Alarmları yükler"""
        if os.path.exists(self.dosya):
            with open(self.dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def kaydet(self):
        """Alarmları kaydeder"""
        with open(self.dosya, "w", encoding="utf-8") as f:
            json.dump(self.alarmlar, f, indent=2, ensure_ascii=False)
    
    def alarm_ekle(self, sembol, hedef_fiyat, yon="yukari"):
        """
        Alarm ekler
        yon: "yukari" (fiyat yükselince) veya "asagi" (fiyat düşünce)
        """
        sembol = sembol.upper().replace(".IS", "")
        alarm = {
            "sembol": sembol,
            "hedef": hedef_fiyat,
            "yon": yon,
            "aktif": True,
            "ekleme": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        self.alarmlar.append(alarm)
        self.kaydet()
        print(f"✅ Alarm eklendi: {sembol} {hedef_fiyat} TL ({yon})")
    
    def alarm_kontrol(self):
        """Tüm aktif alarmları kontrol eder"""
        if not self.alarmlar:
            print("📭 Aktif alarm yok!")
            return []
        
        tetiklenenler = []
        
        for alarm in self.alarmlar:
            if not alarm["aktif"]:
                continue
            
            sembol = alarm["sembol"]
            sembol_yf = f"{sembol}.IS"
            
            try:
                ticker = yf.Ticker(sembol_yf)
                veri = ticker.history(period="2d")
                
                if len(veri) < 1:
                    continue
                
                guncel = veri['Close'].iloc[-1]
                hedef = alarm["hedef"]
                yon = alarm["yon"]
                
                tetiklendi = False
                if yon == "yukari" and guncel >= hedef:
                    tetiklendi = True
                elif yon == "asagi" and guncel <= hedef:
                    tetiklendi = True
                
                if tetiklendi:
                    print(f"🚨 ALARM: {sembol} {guncel:.2f} TL (hedef: {hedef})")
                    tetiklenenler.append({
                        "sembol": sembol,
                        "fiyat": guncel,
                        "hedef": hedef,
                        "yon": yon
                    })
                    alarm["aktif"] = False  # Bir kere çalışsın
                    
            except Exception as e:
                print(f"⚠️ {sembol}: {e}")
        
        if tetiklenenler:
            self.kaydet()
            
            # Telegram bildirimi gönder
            if self.bot:
                self.telegram_bildir(tetiklenenler)
        
        return tetiklenenler
    
    def telegram_bildir(self, alarmlar):
        """Telegram'a alarm bildirimi gönderir"""
        mesaj = "🚨 <b>FİYAT ALARM!</b>\n\n"
        
        for a in alarmlar:
            yon_emoji = "📈" if a["yon"] == "yukari" else "📉"
            mesaj += f"{yon_emoji} <b>{a['sembol']}</b>\n"
            mesaj += f"   Hedef: {a['hedef']} TL\n"
            mesaj += f"   Güncel: {a['fiyat']:.2f} TL\n\n"
        
        mesaj += f"⏰ {datetime.now().strftime('%H:%M')}"
        
        self.bot.mesaj_gonder_sync(mesaj)
    
    def liste_goster(self):
        """Aktif alarmları gösterir"""
        aktif = [a for a in self.alarmlar if a["aktif"]]
        
        print("\n" + "=" * 50)
        print("🔔 AKTİF ALARMLAR")
        print("=" * 50)
        
        if not aktif:
            print("📭 Aktif alarm yok!")
        else:
            for a in aktif:
                yon_ok = "📈" if a["yon"] == "yukari" else "📉"
                print(f"{yon_ok} {a['sembol']}: {a['hedef']} TL "
                      f"({a['yon']}) - {a['ekleme']}")
        print("=" * 50)


# Örnek menü
if __name__ == "__main__":
    alarm = AlarmSistemi()
    
    print("=" * 50)
    print("🔔 ALARM SİSTEMİ")
    print("=" * 50)
    print("1. Alarm Ekle")
    print("2. Alarmları Göster")
    print("3. Alarmları Kontrol Et")
    print("4. Çıkış")
    
    while True:
        secim = input("\nSeçiminiz (1-4): ").strip()
        
        if secim == "1":
            sembol = input("Hisse (örn: THYAO): ").strip()
            hedef = float(input("Hedef fiyat: "))
            yon = input("Yön (yukari/asagi): ").strip().lower()
            alarm.alarm_ekle(sembol, hedef, yon)
        
        elif secim == "2":
            alarm.liste_goster()
        
        elif secim == "3":
            alarm.alarm_kontrol()
        
        elif secim == "4":
            break
