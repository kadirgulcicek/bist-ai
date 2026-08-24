"""
Canli Takip - Gercek Zamanli Fiyat Takibi
Piyasa acikken her dakika kontrol
"""

import yfinance as yf
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict


class CanliTakip:
    def __init__(self):
        self.gecmis = self.yukle()
    
    def yukle(self):
        if os.path.exists("canli_gecmis.json"):
            with open("canli_gecmis.json", "r") as f:
                return json.load(f)
        return {}
    
    def kaydet(self):
        with open("canli_gecmis.json", "w") as f:
            json.dump(self.gecmis, f, indent=2)
    
    def anlik_fiyat_al(self, sembol):
        """Bir hissenin anlik fiyatini al"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="1d", interval="1m")
            if veri is None or len(veri) < 1:
                return None
            
            fiyat = float(veri['Close'].iloc[-1])
            onceki = float(veri['Close'].iloc[0]) if len(veri) > 1 else fiyat
            degisim = ((fiyat - onceki) / onceki * 100) if onceki > 0 else 0
            
            return {
                "sembol": sembol,
                "fiyat": round(fiyat, 2),
                "degisim": round(degisim, 2),
                "zaman": datetime.now().strftime("%H:%M:%S")
            }
        except:
            return None
    
    def gunluk_ozet(self, sembol):
        """Gunluk ozet - en dusuk, en yuksek, hacim"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="1d", interval="5m")
            
            if veri is None or len(veri) < 1:
                return None
            
            fiyatlar = veri['Close']
            return {
                "acilis": float(fiyatlar.iloc[0]),
                "en_yuksek": float(fiyatlar.max()),
                "en_dusuk": float(fiyatlar.min()),
                "guncel": float(fiyatlar.iloc[-1]),
                "hacim": int(veri['Volume'].iloc[-1])
            }
        except:
            return None
    
    def coklu_hisse_takip(self, hisse_listesi):
        """Birden fazla hisseyi anlik takip"""
        sonuclar = []
        for sembol in hisse_listesi:
            veri = self.anlik_fiyat_al(sembol)
            if veri:
                sonuclar.append(veri)
        return sonuclar
    
    def buyuk_hareket_kontrol(self, sembol, esik=2.0):
        """Buyuk hareket oldu mu kontrol et"""
        anlik = self.anlik_fiyat_al(sembol)
        if anlik and abs(anlik["degisim"]) >= esik:
            return anlik
        return None


def canli_takip_demo():
    """Demo"""
    takip = CanliTakip()
    
    print("=" * 60)
    print("CANLI TAKIP - GERCEK ZAMANLI FIYATLAR")
    print("=" * 60)
    print(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print()
    
    hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]
    
    print("ANLIK FIYATLAR:")
    print("-" * 60)
    
    for sembol in hisseler:
        veri = takip.anlik_fiyat_al(sembol)
        if veri:
            emoji = "YUKARI" if veri["degisim"] > 0 else "ASAGI" if veri["degisim"] < 0 else "SIFIR"
            print(f"  {sembol:8} {veri['fiyat']:>10.2f} TL  {emoji} %{veri['degisim']:+6.2f}")
        else:
            print(f"  {sembol:8} veri yok")
    
    print()
    print("BUYUK HAREKET VAR MI?")
    print("-" * 60)
    
    for sembol in hisseler:
        hareket = takip.buyuk_hareket_kontrol(sembol)
        if hareket:
            print(f"  ALARM: {hareket['sembol']} %{hareket['degisim']:+.2f} hareket etti!")


if __name__ == "__main__":
    canli_takip_demo()
    input("\nCikmak icin Enter'a basin...")
