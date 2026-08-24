"""
Basit ve Calisan Al-Sat Sinyal Sistemi
RSI + MACD + Trend kontrolleri
"""

import yfinance as yf
from datetime import datetime
from collections import defaultdict


def sinyal_analiz(sembol, maliyet=None):
    """Tek hisse icin sinyal analizi"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="3mo")
        
        if veri is None or len(veri) < 30:
            return None
        
        kapanis = veri['Close'].values
        hacimler = veri['Volume'].values
        guncel = float(kapanis[-1])
        
        # RSI
        rsi = rsi_hesapla(kapanis)
        
        # MACD
        macd_val, sinyal_val = macd_hesapla(kapanis)
        
        # Trend
        ma_20 = kapanis[-20:].mean() if len(kapanis) >= 20 else kapanis.mean()
        trend = "YUKARI" if guncel > ma_20 else "ASAGI"
        
        # Hacim trendi
        son_hacim = float(hacimler[-1])
        ort_hacim = float(hacimler[-20:].mean()) if len(hacimler) >= 20 else son_hacim
        hacim_yuksek = son_hacim > ort_hacim * 1.3 if ort_hacim > 0 else False
        
        # AL PUANI
        al_puan = 0
        al_sebepler = []
        
        if rsi < 35:
            al_puan += 2
            al_sebepler.append(f"RSI asiri satim ({rsi:.1f})")
        if macd_val > sinyal_val:
            al_puan += 2
            al_sebepler.append("MACD pozitif")
        if trend == "YUKARI":
            al_puan += 1
            al_sebepler.append("Trend yukarida")
        if hacim_yuksek:
            al_puan += 1
            al_sebepler.append("Hacim yukseliyor")
        
        # SAT PUANI
        sat_puan = 0
        sat_sebepler = []
        
        if maliyet is not None and maliyet > 0:
            kar_yuzde = ((guncel - maliyet) / maliyet) * 100
            
            if kar_yuzde >= 15:
                sat_puan += 3
                sat_sebepler.append(f"Hedef kar +%{kar_yuzde:.1f}")
            elif kar_yuzde <= -10:
                sat_puan += 4
                sat_sebepler.append(f"Stop-loss %{kar_yuzde:.1f}")
        
        if rsi > 70:
            sat_puan += 2
            sat_sebepler.append(f"RSI asiri alim ({rsi:.1f})")
        if macd_val < sinyal_val:
            sat_puan += 1
            sat_sebepler.append("MACD negatif")
        
        # KARAR
        if sat_puan >= 2:
            karar = "SAT"
            oncelik = "YUKSEK" if sat_puan >= 4 else "ORTA"
            sebepler = sat_sebepler
        elif al_puan >= 3:
            karar = "AL"
            oncelik = "YUKSEK" if al_puan >= 5 else "ORTA"
            sebepler = al_sebepler
        else:
            karar = "BEKLE"
            oncelik = "DUSUK"
            sebepler = []
        
        # NaN kontrolu
        if any(s != s for s in sebepler):  # NaN kontrolu
            sebepler = [str(s) for s in sebepler if s == s]
        
        return {
            "sembol": sembol,
            "fiyat": round(guncel, 2),
            "rsi": round(rsi, 1) if rsi == rsi else 50,
            "macd": round(macd_val - sinyal_val, 3) if (macd_val - sinyal_val) == (macd_val - sinyal_val) else 0,
            "karar": karar,
            "oncelik": oncelik,
            "sebepler": sebepler
        }
    except Exception as e:
        return {"sembol": sembol, "fiyat": 0, "karar": "HATA", "sebepler": [str(e)[:50]], "rsi": 0, "macd": 0, "oncelik": "DUSUK"}


def rsi_hesapla(fiyatlar, pencere=14):
    """RSI hesapla"""
    try:
        if len(fiyatlar) < pencere + 1:
            return 50.0
        
        delta = []
        for i in range(1, len(fiyatlar)):
            delta.append(fiyatlar[i] - fiyatlar[i-1])
        
        pozitif = sum(d for d in delta[-pencere:] if d > 0) / pencere
        negatif = abs(sum(d for d in delta[-pencere:] if d < 0)) / pencere
        
        if negatif == 0:
            return 100.0
        if pozitif == 0:
            return 0.0
        
        rs = pozitif / negatif
        rsi = 100 - (100 / (1 + rs))
        return float(rsi) if rsi == rsi else 50.0
    except:
        return 50.0


def macd_hesapla(fiyatlar):
    """MACD hesapla"""
    try:
        if len(fiyatlar) < 26:
            return 0.0, 0.0
        
        ema12 = ema_hesapla(fiyatlar, 12)
        ema26 = ema_hesapla(fiyatlar, 26)
        macd = ema12 - ema26
        
        # Sinyal cizgisi (MACD'nin 9 donemlik EMA'si)
        macd_degerleri = []
        for i in range(26, len(fiyatlar)):
            macd_degerleri.append(ema12_hesapla(fiyatlar[:i+1], 12) - ema26_hesapla(fiyatlar[:i+1], 26))
        
        sinyal = ema_hesapla(macd_degerleri[-9:], 9) if len(macd_degerleri) >= 9 else macd
        
        return float(macd), float(sinyal)
    except:
        return 0.0, 0.0


def ema_hesapla(veriler, pencere):
    """EMA (Exponential Moving Average)"""
    try:
        if not veriler or len(veriler) < pencere:
            return sum(veriler) / len(veriler) if veriler else 0
        
        multiplier = 2 / (pencere + 1)
        ema = sum(veriler[:pencere]) / pencere
        
        for fiyat in veriler[pencere:]:
            ema = (fiyat - ema) * multiplier + ema
        
        return float(ema)
    except:
        return 0.0


def ema12_hesapla(veriler, pencere):
    return ema_hesapla(veriler, pencere)


def portfoy_sinyalleri_al(kullanici_adi):
    """Portfoy ve yeni hisseler icin sinyaller"""
    from auth import KullaniciYoneticisi
    yon = KullaniciYoneticisi()
    
    portfoy = yon.portfoy_al(kullanici_adi)
    
    sinyaller = []
    
    # Portfoydekiler icin SAT sinyali
    for h in portfoy:
        s = sinyal_analiz(h["sembol"], maliyet=h["alis_fiyati"])
        if s:
            sinyaller.append(s)
    
    # Yeni hisseler icin AL sinyali
    yeni_hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                     "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"]
    
    portfoy_semboller = [h["sembol"] for h in portfoy]
    
    for sembol in yeni_hisseler:
        if sembol not in portfoy_semboller:
            s = sinyal_analiz(sembol)
            if s and s["karar"] in ["AL", "SAT"]:
                sinyaller.append(s)
    
    # Oncelik siralamasi
    sirala = {"YUKSEK": 0, "ORTA": 1, "DUSUK": 2}
    sinyaller.sort(key=lambda x: (
        0 if x["karar"] == "SAT" else 1 if x["karar"] == "AL" else 2,
        sirala.get(x.get("oncelik", "DUSUK"), 3)
    ))
    
    return sinyaller


if __name__ == "__main__":
    print("Basit Sinyal Sistemi - Test")
    print("=" * 50)
    
    sinyaller = portfoy_sinyalleri_al("test")
    
    for s in sinyaller[:5]:
        print(f"\n{s['sembol']} - {s['karar']} - {s['fiyat']} TL")
        for sebep in s.get("sebepler", []):
            print(f"  - {sebep}")
    
    input("\nCikmak icin Enter'a basin...")
