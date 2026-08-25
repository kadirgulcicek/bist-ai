"""
Akıllı Alarm Sistemi
Anlik firsat ve tehlike uyaran sistemi
"""

import yfinance as yf
import time
from datetime import datetime
from collections import defaultdict


class AkilliAlarm:
    def __init__(self):
        self.gecmis_veriler = {}  # Hisse bazlı geçmiş fiyat verileri
        self.son_alarmlar = defaultdict(float)  # Spam önleme
        self.alarm_aralik = 300  # Aynı hisse için 5 dk aralık
        
        self.bot = None
    
    def fiyat_al(self, sembol):
        """Tek bir hissenin güncel fiyatını alır"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="1d", interval="5m")
            
            if veri is None or len(veri) < 1:
                return None
            
            return float(veri['Close'].iloc[-1])
        except:
            return None
    
    def volume_kontrol(self, sembol):
        """Volume spike tespiti"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="5d")
            
            if veri is None or len(veri) < 5:
                return None
            
            gunluk_volume = veri['Volume'].iloc[-1]
            ortalama_volume = veri['Volume'].mean()
            
            if ortalama_volume == 0:
                return None
            
            volume_orani = gunluk_volume / ortalama_volume
            
            return {
                "guncel": float(gunluk_volume),
                "ortalama": float(ortalama_volume),
                "orani": float(volume_orani),
                "spike": volume_orani > 2.0  # 2x normalden fazla
            }
        except:
            return None
    
    def ani_hareket_kontrol(self, sembol, esik=3.0):
        """Ani fiyat hareketi tespiti"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="1d", interval="5m")
            
            if veri is None or len(veri) < 5:
                return None
            
            fiyatlar = veri['Close'].values
            baslangic = float(fiyatlar[0])
            guncel = float(fiyatlar[-1])
            
            if baslangic == 0:
                return None
            
            degisim_yuzde = ((guncel - baslangic) / baslangic) * 100
            
            return {
                "baslangic": baslangic,
                "guncel": guncel,
                "degisim": degisim_yuzde,
                "ani": abs(degisim_yuzde) > esik
            }
        except:
            return None
    
    def destek_direnc_kontrol(self, sembol):
        """Destek ve direnç seviyesi kırılımı"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="3mo")
            
            if veri is None or len(veri) < 30:
                return None
            
            fiyatlar = veri['Close'].values
            guncel = float(fiyatlar[-1])
            
            # Son 30 günün max/min
            son_30 = fiyatlar[-30:]
            direnc = float(max(son_30))
            destek = float(min(son_30))
            
            kirildi = False
            yon = None
            
            if guncel >= direnc * 0.99:  # Dirence yaklaştı
                kirildi = True
                yon = "YUKARI"
            elif guncel <= destek * 1.01:  # Desteğe yaklaştı
                kirildi = True
                yon = "ASAGI"
            
            return {
                "destek": destek,
                "direnc": direnc,
                "guncel": guncel,
                "kirildi": kirildi,
                "yon": yon
            }
        except:
            return None
    
    def spam_kontrol(self, sembol):
        """Aynı hisse için arka arkaya alarm göndermeyi önler"""
        simdi = time.time()
        son_alarm = self.son_alarmlar.get(sembol, 0)
        
        if simdi - son_alarm < self.alarm_aralik:
            return False
        
        self.son_alarmlar[sembol] = simdi
        return True
    
    def hisse_kontrol(self, sembol):
        """Tek bir hisseyi tüm alarmlarla kontrol eder"""
        if not self.spam_kontrol(sembol):
            return None
        
        uyarilar = []
        
        # 1. Ani hareket
        hareket = self.ani_hareket_kontrol(sembol)
        if hareket and hareket["ani"]:
            yon = "📈" if hareket["degisim"] > 0 else "📉"
            uyarilar.append({
                "tip": "ANI_HAREKET",
                "oncelik": "YUKSEK",
                "mesaj": f"{yon} ANI HAREKET: {sembol} %{hareket['degisim']:+.2f} degisti!"
            })
        
        # 2. Volume spike
        volume = self.volume_kontrol(sembol)
        if volume and volume["spike"]:
            uyarilar.append({
                "tip": "VOLUME_SPIKE",
                "oncelik": "ORTA",
                "mesaj": f"🔊 VOLUME ARTIŞI: {sembol} normalin %{volume['orani']*100:.0f}'i islem hacmi!"
            })
        
        # 3. Destek/Direnç
        seviye = self.destek_direnc_kontrol(sembol)
        if seviye and seviye["kirildi"]:
            emoji = "⬆️" if seviye["yon"] == "YUKARI" else "⬇️"
            uyarilar.append({
                "tip": "SEVIYE_KIRILMA",
                "oncelik": "ORTA",
                "mesaj": f"{emoji} SEVIYE: {sembol} {seviye['yon']} kirilma (Destek: {seviye['destek']:.2f}, Direnc: {seviye['direnc']:.2f})"
            })
        
        return uyarilar if uyarilar else None
    
    def toplu_kontrol(self, hisse_listesi):
        """Birden fazla hisseyi kontrol eder"""
        print(f"{len(hisse_listesi)} hisse kontrol ediliyor...")
        
        tum_uyarilar = []
        
        for sembol in hisse_listesi:
            try:
                uyarilar = self.hisse_kontrol(sembol)
                if uyarilar:
                    tum_uyarilar.extend(uyarilar)
            except:
                continue
        
        return tum_uyarilar
    
    def uyari_bildir(self, uyarilar):
        """Uyarilari yerel olarak yazdirir."""
        if uyarilar:
            print(f"{len(uyarilar)} alarm tespit edildi.")
    
    def surekli_kontrol(self, hisse_listesi, aralik_dakika=5):
        """Belirli araliklarla surekli kontrol"""
        print(f"Surekli alarm sistemi baslatildi ({aralik_dakika} dk aralik)")
        print("Durdurmak icin Ctrl+C basin\n")
        
        while True:
            try:
                uyarilar = self.toplu_kontrol(hisse_listesi)
                
                if uyarilar:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(uyarilar)} uyari bulundu!")
                    self.uyari_bildir(uyarilar)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Tüm hisseler normal")
                
                time.sleep(aralik_dakika * 60)
            
            except KeyboardInterrupt:
                print("\nAlarm sistemi durduruldu.")
                break
            except Exception as e:
                print(f"Hata: {e}")
                time.sleep(60)


# ============================================
# ANA PROGRAM
# ============================================
if __name__ == "__main__":
    # BURAYA KENDI BILGILERINIZI YAZIN
    TOKEN = "BURAYA_TOKEN"
    CHAT_ID = "BURAYA_CHAT_ID"
    
    print("=" * 60)
    print("🚨 AKILLI ALARM SİSTEMİ")
    print("=" * 60)
    print()
    print("1. Tek seferlik kontrol")
    print("2. Surekli kontrol (5 dk aralik)")
    print("3. Surekli kontrol (1 dk aralik)")
    print("4. Cikis")
    print()
    
    secim = input("Seciminiz (1-4): ").strip()
    
    # Test hisseleri
    hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"]
    
    alarm = AkilliAlarm()
    
    if secim == "1":
        print("\nTek seferlik kontrol...")
        uyarilar = alarm.toplu_kontrol(hisseler)
        
        if uyarilar:
            print(f"\n✅ {len(uyarilar)} uyari bulundu:")
            for uyari in uyarilar:
                print(f"  [{uyari['oncelik']}] {uyari['mesaj']}")
            alarm.uyari_bildir(uyarilar)
        else:
            print("\nTüm hisseler normal, uyari yok.")
    
    elif secim == "2":
        alarm.surekli_kontrol(hisseler, aralik_dakika=5)
    
    elif secim == "3":
        alarm.surekli_kontrol(hisseler, aralik_dakika=1)
    
    input("\nCikmak icin Enter'a basin...")
