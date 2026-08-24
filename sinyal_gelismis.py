"""
Gelismis Sinyal Sistemi
Daha hassas ve akıllı kurallar
"""

import yfinance as yf
from datetime import datetime
from collections import defaultdict


def sinyal_analiz(sembol, maliyet=None):
    """Tek hisse icin detayli sinyal analizi"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="3mo")
        
        if veri is None or len(veri) < 30:
            return None
        
        kapanis = veri['Close'].values
        hacimler = veri['Volume'].values
        guncel = float(kapanis[-1])
        
        # Teknik göstergeler
        rsi = rsi_hesapla(kapanis)
        macd_val, sinyal_val = macd_hesapla(kapanis)
        ma_5 = kapanis[-5:].mean() if len(kapanis) >= 5 else guncel
        ma_20 = kapanis[-20:].mean() if len(kapanis) >= 20 else guncel
        ma_50 = kapanis[-50:].mean() if len(kapanis) >= 50 else guncel
        
        # Hacim analizi
        son_hacim = float(hacimler[-1])
        ort_hacim = float(hacimler[-20:].mean()) if len(hacimler) >= 20 else son_hacim
        hacim_orani = son_hacim / ort_hacim if ort_hacim > 0 else 1
        
        # Volatilite
        volatilite = volatilite_hesapla(kapanis[-20:])
        
        # Trend gücü (son 5 gün vs 20 gün)
        trend_5_20 = ((ma_5 - ma_20) / ma_20 * 100) if ma_20 > 0 else 0
        trend_20_50 = ((ma_20 - ma_50) / ma_50 * 100) if ma_50 > 0 else 0
        
        # Destek/Direnç (basit)
        son_30 = kapanis[-30:]
        direnc = float(son_30.max())
        destek = float(son_30.min())
        fiyat_direnc_farki = ((direnc - guncel) / guncel * 100)
        fiyat_destek_farki = ((guncel - destek) / destek * 100)
        
        # AL PUANI (daha esnek)
        al_puan = 0
        al_sebepler = []
        
        # RSI (max 3 puan)
        if rsi < 30:
            al_puan += 3
            al_sebepler.append(f"RSI cok asiri satim ({rsi:.1f})")
        elif rsi < 40:
            al_puan += 2
            al_sebepler.append(f"RSI asiri satim ({rsi:.1f})")
        elif rsi < 50 and trend_5_20 > 0:
            al_puan += 1
            al_sebepler.append(f"RSI yukselis trendinde ({rsi:.1f})")
        
        # MACD (max 2 puan)
        if macd_val > sinyal_val and macd_val > 0:
            al_puan += 2
            al_sebepler.append("MACD guclu pozitif")
        elif macd_val > sinyal_val:
            al_puan += 1
            al_sebepler.append("MACD pozitif donuyor")
        
        # Trend (max 3 puan)
        if ma_5 > ma_20 > ma_50:
            al_puan += 3
            al_sebepler.append("Guclu yukselis trendi (MA5>MA20>MA50)")
        elif ma_5 > ma_20:
            al_puan += 2
            al_sebepler.append("Kisa vade trend yukarida (MA5>MA20)")
        elif guncel > ma_20:
            al_puan += 1
            al_sebepler.append("Fiyat 20 gunluk ortalamanin ustunde")
        
        # Hacim (max 2 puan)
        if hacim_orani > 1.5:
            al_puan += 2
            al_sebepler.append(f"Yuksek hacim (x{hacim_orani:.1f})")
        elif hacim_orani > 1.2:
            al_puan += 1
            al_sebepler.append(f"Artan hacim (x{hacim_orani:.1f})")
        
        # Destek yakinligi (max 1 puan)
        if fiyat_destek_farki < 3:
            al_puan += 1
            al_sebepler.append("Destek seviyesine yakin")
        
        # SAT PUANI (daha esnek)
        sat_puan = 0
        sat_sebepler = []
        
        if maliyet is not None and maliyet > 0:
            kar_yuzde = ((guncel - maliyet) / maliyet) * 100
            
            # Kar alma (kademeli)
            if kar_yuzde >= 20:
                sat_puan += 4
                sat_sebepler.append(f"Hedef kar +%{kar_yuzde:.1f} (TAM)")
            elif kar_yuzde >= 10:
                sat_puan += 3
                sat_sebepler.append(f"Kar +%{kar_yuzde:.1f} (yarisi al)")
            elif kar_yuzde >= 5:
                sat_puan += 1
                sat_sebepler.append(f"Kar realizasyonu +%{kar_yuzde:.1f}")
            
            # Stop-loss (kademeli)
            if kar_yuzde <= -15:
                sat_puan += 5
                sat_sebepler.append(f"Stop-loss %{kar_yuzde:.1f} (ACIL)")
            elif kar_yuzde <= -8:
                sat_puan += 4
                sat_sebepler.append(f"Stop-loss %{kar_yuzde:.1f}")
            elif kar_yuzde <= -3:
                sat_puan += 2
                sat_sebepler.append(f"Zarar kontrolu %{kar_yuzde:.1f}")
        
        # RSI asiri alim
        if rsi > 75:
            sat_puan += 3
            sat_sebepler.append(f"RSI cok asiri alim ({rsi:.1f})")
        elif rsi > 65:
            sat_puan += 1
            sat_sebepler.append(f"RSI asiri alim ({rsi:.1f})")
        
        # MACD negatife donuyor
        if macd_val < sinyal_val and macd_val < 0:
            sat_puan += 2
            sat_sebepler.append("MACD guclu negatif")
        elif macd_val < sinyal_val:
            sat_puan += 1
            sat_sebepler.append("MACD negatif donuyor")
        
        # Trend asagi
        if ma_5 < ma_20 and ma_20 < ma_50:
            sat_puan += 3
            sat_sebepler.append("Guclu dusus trendi")
        elif ma_5 < ma_20:
            sat_puan += 1
            sat_sebepler.append("Kisa vade trend asagida")
        
        # KARAR
        if sat_puan >= 3:
            karar = "SAT"
            oncelik = "YUKSEK" if sat_puan >= 5 else "ORTA"
            sebepler = sat_sebepler if sat_sebepler else ["Kar hedefine ulasildi"]
        elif al_puan >= 3:
            karar = "AL"
            oncelik = "YUKSEK" if al_puan >= 5 else "ORTA"
            sebepler = al_sebepler if al_sebepler else ["Olumlu sinyal"]
        else:
            karar = "BEKLE"
            oncelik = "DUSUK"
            sebepler = []
        
        # NaN kontrolu
        rsi_clean = rsi if rsi == rsi else 50
        macd_clean = (macd_val - sinyal_val) if (macd_val - sinyal_val) == (macd_val - sinyal_val) else 0
        
        return {
            "sembol": sembol,
            "fiyat": round(guncel, 2),
            "rsi": round(rsi_clean, 1),
            "macd": round(macd_clean, 3),
            "karar": karar,
            "oncelik": oncelik,
            "sebepler": sebepler,
            "al_puan": al_puan,
            "sat_puan": sat_puan
        }
    except Exception as e:
        return {"sembol": sembol, "fiyat": 0, "karar": "HATA", "sebepler": [str(e)[:50]], "rsi": 50, "macd": 0, "oncelik": "DUSUK", "al_puan": 0, "sat_puan": 0}


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
        sinyal = macd * 0.8  # Basitleştirilmiş sinyal hesabı
        
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


def volatilite_hesapla(fiyatlar):
    """Volatilite (standart sapma yuzdesi)"""
    try:
        if len(fiyatlar) < 2:
            return 0.0
        
        ortalama = sum(fiyatlar) / len(fiyatlar)
        varyans = sum((f - ortalama) ** 2 for f in fiyatlar) / len(fiyatlar)
        std = varyans ** 0.5
        return (std / ortalama * 100) if ortalama > 0 else 0.0
    except:
        return 0.0


def portfoy_sinyalleri_al(kullanici_adi):
    """Portfoy ve yeni hisseler icin sinyaller"""
    try:
        from auth import KullaniciYoneticisi
        yon = KullaniciYoneticisi()
        portfoy = yon.portfoy_al(kullanici_adi)
    except:
        portfoy = []
    
    sinyaller = []
    
    # Portfoydekiler icin SAT sinyali
    for h in portfoy:
        s = sinyal_analiz(h["sembol"], maliyet=h["alis_fiyati"])
        if s and s["karar"] == "SAT":
            sinyaller.append(s)
    
    # Yeni hisseler icin AL sinyali
    yeni_hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                     "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK",
                     "ISCTR", "YKBNK", "SAHOL", "EKGYO", "TAVHL"]
    
    portfoy_semboller = [h["sembol"] for h in portfoy]
    
    for sembol in yeni_hisseler:
        if sembol not in portfoy_semboller:
            s = sinyal_analiz(sembol)
            if s and s["karar"] == "AL":
                sinyaller.append(s)
    
    # Oncelik siralamasi
    sirala = {"YUKSEK": 0, "ORTA": 1, "DUSUK": 2}
    sinyaller.sort(key=lambda x: (
        0 if x["karar"] == "SAT" else 1,
        sirala.get(x.get("oncelik", "DUSUK"), 3)
    ))
    
    return sinyaller


if __name__ == "__main__":
    print("=" * 70)
    print("GELISMIS SINYAL SISTEMI - Test")
    print("=" * 70)
    
    sinyaller = portfoy_sinyalleri_al("test")
    
    print(f"\nToplam {len(sinyaller)} sinyal bulundu\n")
    
    for s in sinyaller[:10]:
        print(f"\n{s['sembol']} - {s['karar']} - {s['fiyat']} TL")
        print(f"  Oncelik: {s['oncelik']} | AL:{s['al_puan']} SAT:{s['sat_puan']}")
        for sebep in s.get("sebepler", []):
            print(f"  - {sebep}")
    
    input("\nCikmak icin Enter'a basin...")
