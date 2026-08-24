"""
Hedef Fiyat Tahmini Sistemi
Kisa vadeli fiyat hedefleri ve zaman tahminleri
"""

import yfinance as yf
import numpy as np
from datetime import datetime, timedelta


def trend_yonu(fiyatlar):
    """Trend yonunu belirle (yukari mi asagi mi)"""
    if len(fiyatlar) < 5:
        return "BELIRSIZ"
    
    son_5 = fiyatlar[-5:]
    ilk = son_5[0]
    son = son_5[-1]
    
    fark = ((son - ilk) / ilk) * 100
    
    if fark > 2:
        return "YUKARI"
    elif fark < -2:
        return "ASAGI"
    else:
        return "YATAY"


def volatilite_hesapla(fiyatlar):
    """Volatilite (risk olcusu)"""
    if len(fiyatlar) < 2:
        return 0
    
    getiriler = []
    for i in range(1, len(fiyatlar)):
        getiri = (fiyatlar[i] - fiyatlar[i-1]) / fiyatlar[i-1]
        getiriler.append(getiri)
    
    return np.std(getiriler) * 100 if getiriler else 0


def hareketli_ortalama(fiyatlar, pencere):
    """Basit hareketli ortalama"""
    if len(fiyatlar) < pencere:
        return sum(fiyatlar) / len(fiyatlar)
    return sum(fiyatlar[-pencere:]) / pencere


def hedef_fiyat_tahmin(sembol, gun_hedef=5):
    """Bir hisse icin hedef fiyat tahmini"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="3mo")
        
        if veri is None or len(veri) < 20:
            return None
        
        fiyatlar = veri['Close'].values
        guncel = float(fiyatlar[-1])
        
        # Trend analizi
        trend = trend_yonu(fiyatlar)
        
        # Volatilite
        volatilite = volatilite_hesapla(fiyatlar[-30:])
        
        # Hareketli ortalamalar
        ma_5 = hareketli_ortalama(fiyatlar, 5)
        ma_20 = hareketli_ortalama(fiyatlar, 20)
        
        # Trend gucu (son 5 gunun ortalama artisi)
        if len(fiyatlar) >= 6:
            son_5_artis = ((fiyatlar[-1] - fiyatlar[-6]) / fiyatlar[-6]) * 100
        else:
            son_5_artis = 0
        
        # Hedef hesapla
        if trend == "YUKARI":
            # Yukselis trendinde - hedef yukarida
            beklenen_degisim = min(son_5_artis * 1.5, volatilite * 1.2)
            hedef = guncel * (1 + beklenen_degisim / 100)
            guven_araligi = (guncel * 0.95, guncel * 1.15)
            risk = "ORTA"
        elif trend == "ASAGI":
            # Dusus trendinde - hedef asagida
            beklenen_degisim = max(son_5_artis * 1.5, -volatilite * 0.8)
            hedef = guncel * (1 + beklenen_degisim / 100)
            guven_araligi = (guncel * 0.85, guncel * 1.05)
            risk = "YUKSEK"
        else:
            # Yatay - hedef yaklasik ayni
            hedef = guncel * (1 + volatilite * 0.3 / 100)
            guven_araligi = (guncel * 0.95, guncel * 1.05)
            risk = "DUSUK"
        
        # Zaman tahmini
        gun_sayisi = max(1, int(abs(hedef - guncel) / max(0.5, volatilite / 4)))
        gun_sayisi = min(gun_sayisi, 30)  # Maksimum 30 gun
        
        # Sonuc
        return {
            "sembol": sembol,
            "guncel": round(guncel, 2),
            "hedef": round(hedef, 2),
            "degisim": round(((hedef - guncel) / guncel) * 100, 2),
            "guven_alt": round(guven_araligi[0], 2),
            "guven_ust": round(guven_araligi[1], 2),
            "zaman_gun": gun_sayisi,
            "trend": trend,
            "risk": risk,
            "volatilite": round(volatilite, 2),
            "ma_5": round(ma_5, 2),
            "ma_20": round(ma_20, 2),
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    except Exception as e:
        return None


def coklu_hisse_tahmin(hisse_listesi, gun=5):
    """Birden fazla hisse icin tahmin"""
    print("=" * 70)
    print("HEDEF FIYAT TAHMINI")
    print("=" * 70)
    print(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print()
    
    sonuclar = []
    for sembol in hisse_listesi:
        tahmin = hedef_fiyat_tahmin(sembol, gun_hedef=gun)
        if tahmin:
            sonuclar.append(tahmin)
    
    # Siralama - en yuksek potansiyel
    sirali = sorted(sonuclar, key=lambda x: x["degisim"], reverse=True)
    
    print(f"{'Hisse':<8}{'Guncel':<10}{'Hedef':<10}{'Degisim':<10}{'Zaman':<8}{'Risk':<8}")
    print("-" * 70)
    
    for t in sirali:
        emoji = "YUKARI" if t["degisim"] > 0 else "ASAGI"
        print(f"{t['sembol']:<8}{t['guncel']:<10}{t['hedef']:<10}{t['degisim']:+5.2f}%{'':<4}{t['zaman_gun']} gun{'':<2}{t['risk']}")
    
    print()
    print("NOT: Bu tahminler gecmis verilere dayanir, garanti vermez.")
    
    return sonuclar


if __name__ == "__main__":
    hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"]
    coklu_hisse_tahmin(hisseler)
    input("\nCikmak icin Enter'a basin...")
