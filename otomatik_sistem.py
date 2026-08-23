"""
Otomatik Al-Sat Öneri Sistemi
Kural tabanlı karar motoru - Gerçek para riski YOK
Sadece ÖNERİ verir, siz onaylarsınız
"""

import yfinance as yf
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict


class OtomatikSistem:
    def __init__(self):
        self.dosya = "sinyal_gecmisi.json"
        self.gecmis = self.yukle()
    
    def yukle(self):
        if os.path.exists(self.dosya):
            with open(self.dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def kaydet(self):
        with open(self.dosya, "w", encoding="utf-8") as f:
            json.dump(self.gecmis, f, indent=2, ensure_ascii=False)
    
    def veri_al(self, sembol, period="3mo"):
        """Son 3 ay veri"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period=period)
            if veri is None or len(veri) < 30:
                return None
            return veri
        except:
            return None
    
    def rsi_hesapla(self, fiyatlar, pencere=14):
        """RSI hesapla"""
        try:
            delta = fiyatlar.diff()
            kazanc = delta.where(delta > 0, 0).rolling(pencere).mean()
            kayip = (-delta.where(delta < 0, 0)).rolling(pencere).mean()
            
            if kayip.iloc[-1] == 0:
                return 100
            
            rs = kazanc.iloc[-1] / kayip.iloc[-1]
            rsi = 100 - (100 / (1 + rs))
            
            if rsi != rsi:  # NaN
                return 50
            return float(rsi)
        except:
            return 50
    
    def macd_hesapla(self, fiyatlar):
        """MACD hesapla"""
        try:
            ema12 = fiyatlar.ewm(span=12, adjust=False).mean()
            ema26 = fiyatlar.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            sinyal = macd.ewm(span=9, adjust=False).mean()
            return float(macd.iloc[-1] - sinyal.iloc[-1])
        except:
            return 0
    
    def sinyal_uret(self, sembol, maliyet=None):
        """Bir hisse için al/sat sinyali üret"""
        veri = self.veri_al(sembol)
        if veri is None:
            return None
        
        kapanis = veri['Close']
        hacim = veri['Volume']
        guncel_fiyat = float(kapanis.iloc[-1])
        
        # Hesaplamalar
        rsi = self.rsi_hesapla(kapanis)
        macd_fark = self.macd_hesapla(kapanis)
        
        # 20 günlük ortalama
        sma_20 = float(kapanis.tail(20).mean())
        
        # Hacim oranı
        ortalama_hacim = float(hacim.tail(20).mean())
        hacim_orani = float(hacim.iloc[-1]) / ortalama_hacim if ortalama_hacim > 0 else 1
        
        # AL KURALLARI
        al_skor = 0
        al_sebepler = []
        
        if rsi < 35:
            al_skor += 1
            al_sebepler.append(f"RSI={rsi:.1f} (Asiri satim)")
        
        if macd_fark > 0:
            al_skor += 1
            al_sebepler.append("MACD pozitif")
        
        if hacim_orani > 1.5:
            al_skor += 1
            al_sebepler.append(f"Hacim x{hacim_orani:.1f}")
        
        if guncel_fiyat > sma_20:
            al_skor += 1
            al_sebepler.append("Trend yukselis")
        
        # SAT KURALLARI (eger maliyet varsa)
        sat_skor = 0
        sat_sebepler = []
        
        if maliyet and maliyet > 0:
            kar_yuzde = ((guncel_fiyat - maliyet) / maliyet) * 100
            
            if kar_yuzde >= 15:
                sat_skor += 2
                sat_sebepler.append(f"Hedef kâr %{kar_yuzde:.1f}")
            
            if kar_yuzde <= -10:
                sat_skor += 3
                sat_sebepler.append(f"Stop-loss %{kar_yuzde:.1f}")
        
        if rsi > 70:
            sat_skor += 1
            sat_sebepler.append(f"RSI={rsi:.1f} (Asiri alim)")
        
        # KARAR
        if sat_skor >= 2:
            karar = "SAT"
            oncelik = "YUKSEK" if sat_skor >= 3 else "ORTA"
            sebepler = sat_sebepler
        elif al_skor >= 3:
            karar = "AL"
            oncelik = "YUKSEK" if al_skor == 4 else "ORTA"
            sebepler = al_sebepler
        else:
            karar = "BEKLE"
            oncelik = "DUSUK"
            sebepler = []
        
        return {
            "sembol": sembol,
            "fiyat": round(guncel_fiyat, 2),
            "rsi": round(rsi, 1),
            "macd": round(macd_fark, 3),
            "hacim_orani": round(hacim_orani, 2),
            "sma_20": round(sma_20, 2),
            "al_skor": al_skor,
            "sat_skor": sat_skor,
            "karar": karar,
            "oncelik": oncelik,
            "sebepler": sebepler,
            "zaman": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    
    def portfoy_analiz(self, portfoy_hisseler):
        """Portfoydeki her hisse için sinyal üret"""
        from portfoy import Portfoy
        p = Portfoy()
        
        sonuclar = []
        
        # Portfoydekileri kontrol et (SAT sinyali için)
        for h in p.hisseler:
            sembol = h["sembol"]
            sinyal = self.sinyal_uret(sembol, maliyet=h["alis_fiyati"])
            if sinyal:
                sinyal["tip"] = "PORTFOY"
                sinyal["adet"] = h["adet"]
                sinyal["maliyet"] = h["alis_fiyati"]
                sonuclar.append(sinyal)
        
        # Yeni fırsatları kontrol et (AL sinyali için)
        # Tum BIST'ten belli basli hisseler
        aday_hisseler = [
            "THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
            "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK",
            "ISCTR", "YKBNK", "TAVHL", "FROTO", "PGSUS",
            "SAHOL", "EKGYO", "ENKAI", "TUPRS", "ARCLK"
        ]
        
        for sembol in aday_hisseler:
            # Portfoyde zaten var mi?
            if any(h["sembol"] == sembol for h in p.hisseler):
                continue
            
            sinyal = self.sinyal_uret(sembol, maliyet=None)
            if sinyal and sinyal["karar"] == "AL":
                sinyal["tip"] = "ADAY"
                sonuclar.append(sinyal)
        
        # Oncelik siralamasi
        oncelik_sirasi = {"YUKSEK": 0, "ORTA": 1, "DUSUK": 2}
        sonuclar.sort(key=lambda x: (
            0 if x["karar"] == "SAT" else 1 if x["karar"] == "AL" else 2,
            oncelik_sirasi.get(x["oncelik"], 3)
        ))
        
        return sonuclar
    
    def sonuc_yazdir(self, sonuclar):
        """Sonuclari guzel formatta yazdirir"""
        print("=" * 70)
        print("OTOMATIK AL-SAT ONERI SISTEMI")
        print("=" * 70)
        print(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        print()
        
        # SAT sinyalleri
        sat_sinyalleri = [s for s in sonuclar if s["karar"] == "SAT"]
        if sat_sinyalleri:
            print("SAT SINYALLERI (Portfoydeki):")
            print("-" * 70)
            for s in sat_sinyalleri:
                print(f"  SAT - {s['sembol']:<8} | Fiyat: {s['fiyat']:>8.2f} TL")
                print(f"    Oncelik: {s['oncelik']}")
                for sebep in s["sebepler"]:
                    print(f"    - {sebep}")
                print()
        
        # AL sinyalleri
        al_sinyalleri = [s for s in sonuclar if s["karar"] == "AL"]
        if al_sinyalleri:
            print("AL SINYALLERI (Yeni Firsatlar):")
            print("-" * 70)
            for s in al_sinyalleri:
                print(f"  AL - {s['sembol']:<8} | Fiyat: {s['fiyat']:>8.2f} TL")
                print(f"    Oncelik: {s['oncelik']}")
                for sebep in s["sebepler"]:
                    print(f"    - {sebep}")
                print()
        
        if not sat_sinyalleri and not al_sinyalleri:
            print("Su an icin al veya sat sinyali yok.")
            print("Piyasa sakin, beklemeye devam.")
        
        print("=" * 70)
        print()
        print("NOT: Bu sistem ONERI verir.")
        print("Gerçek alım-satım için kendi kararınızı kullanın.")


# ============================================
# ANA PROGRAM
# ============================================
if __name__ == "__main__":
    sistem = OtomatikSistem()
    sonuclar = sistem.portfoy_analiz(None)
    sistem.sonuc_yazdir(sonuclar)
    input("\nCikmak icin Enter'a basin...")
