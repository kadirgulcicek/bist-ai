import yfinance as yf
from datetime import datetime


def guvenli_veri_al(sembol, period="3mo"):
    """Yahoo'dan veri guvenli al"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period=period)
        if veri is None or len(veri) < 30:
            return None
        return veri
    except Exception as e:
        print(f"[{sembol}] Veri hatasi: {e}")
        return None


def rsi_hesapla(fiyatlar, pencere=14):
    """RSI hesapla (0-100)"""
    try:
        if len(fiyatlar) < pencere + 1:
            return 50.0
        
        # Son 'pencere' kadar fiyat degisimi
        degisimler = []
        for i in range(-pencere, 0):
            fark = fiyatlar[i] - fiyatlar[i-1]
            degisimler.append(fark)
        
        pozitif = sum(d for d in degisimler if d > 0) / pencere
        negatif = abs(sum(d for d in degisimler if d < 0)) / pencere
        
        if negatif < 0.0001:
            return 100.0
        if pozitif < 0.0001:
            return 0.0
        
        rs = pozitif / negatif
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)
    except Exception as e:
        print(f"RSI hatasi: {e}")
        return 50.0


def macd_hesapla(fiyatlar):
    """MACD hesapla"""
    try:
        if len(fiyatlar) < 26:
            return 0.0, 0.0
        
        # EMA 12 ve 26
        ema12 = ema_hesapla(fiyatlar, 12)
        ema26 = ema_hesapla(fiyatlar, 26)
        macd = ema12 - ema26
        sinyal = macd * 0.8  # Basit sinyal hesabi
        
        return float(macd), float(sinyal)
    except:
        return 0.0, 0.0


def ema_hesapla(veriler, pencere):
    """Exponential Moving Average"""
    try:
        if not veriler or len(veriler) < pencere:
            return sum(veriler) / len(veriler) if veriler else 0.0
        
        multiplier = 2.0 / (pencere + 1)
        # Ilk EMA = basit ortalama
        ema = sum(veriler[:pencere]) / pencere
        
        # Sonraki degerler
        for fiyat in veriler[pencere:]:
            ema = (fiyat - ema) * multiplier + ema
        
        return float(ema)
    except:
        return 0.0


def sma_hesapla(veriler, pencere):
    """Simple Moving Average"""
    try:
        if not veriler or len(veriler) < pencere:
            return sum(veriler) / len(veriler) if veriler else 0.0
        return sum(veriler[-pencere:]) / pencere
    except:
        return 0.0


def sinyal_analiz(sembol, maliyet=None):
    """Bir hisse icin detayli sinyal analizi"""
    try:
        veri = guvenli_veri_al(sembol)
        if veri is None:
            return {
                "sembol": sembol,
                "fiyat": 0,
                "rsi": 50,
                "macd": 0,
                "karar": "VERI_YOK",
                "oncelik": "DUSUK",
                "sebepler": ["Yahoo Finance veri vermedi"],
                "al_puan": 0,
                "sat_puan": 0
            }
        
        kapanis = veri['Close'].values
        hacimler = veri['Volume'].values
        guncel = float(kapanis[-1])
        
        # Teknik göstergeler
        rsi = rsi_hesapla(kapanis)
        macd_val, sinyal_val = macd_hesapla(kapanis)
        ma_5 = sma_hesapla(kapanis, 5)
        ma_20 = sma_hesapla(kapanis, 20)
        ma_50 = sma_hesapla(kapanis, 50) if len(kapanis) >= 50 else ma_20
        
        # Hacim analizi
        son_hacim = float(hacimler[-1])
        ort_hacim = float(hacimler[-20:].mean()) if len(hacimler) >= 20 else son_hacim
        hacim_orani = son_hacim / ort_hacim if ort_hacim > 0 else 1.0
        
        # AL PUANI (min 2)
        al_puan = 0
        al_sebepler = []
        
        if rsi < 30:
            al_puan += 2
            al_sebepler.append(f"RSI cok asiri satim ({rsi:.1f})")
        elif rsi < 40:
            al_puan += 1
            al_sebepler.append(f"RSI asiri satim ({rsi:.1f})")
        
        if macd_val > sinyal_val:
            al_puan += 1
            al_sebepler.append("MACD pozitif donuyor")
        if macd_val > 0 and macd_val > sinyal_val:
            al_puan += 1
            al_sebepler.append("MACD guclu pozitif")
        
        if ma_5 > ma_20:
            al_puan += 1
            al_sebepler.append("Trend yukarida (MA5>MA20)")
        if guncel > ma_50 and ma_5 > ma_20:
            al_puan += 1
            al_sebepler.append("Guclu yukselis trendi")
        
        if hacim_orani > 1.5:
            al_puan += 1
            al_sebepler.append(f"Yuksek hacim (x{hacim_orani:.1f})")
        
        # SAT PUANI (min 1)
        sat_puan = 0
        sat_sebepler = []
        
        # Kar/zarar kontrolu (sadece portfoyde olanlar icin)
        if maliyet is not None and maliyet > 0:
            kar_yuzde = ((guncel - maliyet) / maliyet) * 100
            
            if kar_yuzde >= 20:
                sat_puan += 3
                sat_sebepler.append(f"Cok guclu kar +%{kar_yuzde:.1f}")
            elif kar_yuzde >= 10:
                sat_puan += 2
                sat_sebepler.append(f"Guclu kar +%{kar_yuzde:.1f}")
            elif kar_yuzde >= 5:
                sat_puan += 1
                sat_sebepler.append(f"Kar +%{kar_yuzde:.1f}")
            
            if kar_yuzde <= -15:
                sat_puan += 3
                sat_sebepler.append(f"ACIL stop-loss %{kar_yuzde:.1f}")
            elif kar_yuzde <= -8:
                sat_puan += 2
                sat_sebepler.append(f"Stop-loss %{kar_yuzde:.1f}")
            elif kar_yuzde <= -3:
                sat_puan += 1
                sat_sebepler.append(f"Zarar %{kar_yuzde:.1f}")
        
        # RSI (portfoy disi icin de calisir)
        if rsi > 75:
            sat_puan += 2
            sat_sebepler.append(f"RSI cok asiri alim ({rsi:.1f})")
        elif rsi > 65:
            sat_puan += 1
            sat_sebepler.append(f"RSI asiri alim ({rsi:.1f})")
        
        if macd_val < sinyal_val:
            sat_puan += 1
            sat_sebepler.append("MACD negatif")
        
        if ma_5 < ma_20 and ma_20 < ma_50:
            sat_puan += 2
            sat_sebepler.append("Guclu dusus trendi")
        elif ma_5 < ma_20:
            sat_puan += 1
            sat_sebepler.append("Trend asagida")
        
        # KARAR
        if sat_puan >= 2 and (sat_puan >= al_puan or al_puan == 0):
            karar = "SAT"
            oncelik = "YUKSEK" if sat_puan >= 4 else "ORTA"
            sebepler = sat_sebepler if sat_sebepler else ["Sat sinyali"]
        elif al_puan >= 2 and (al_puan > sat_puan or sat_puan == 0):
            karar = "AL"
            oncelik = "YUKSEK" if al_puan >= 4 else "ORTA"
            sebepler = al_sebepler if al_sebepler else ["Al sinyali"]
        elif sat_puan > al_puan and sat_puan >= 1:
            karar = "SAT"
            oncelik = "DUSUK"
            sebepler = sat_sebepler if sat_sebepler else ["Hafif sat"]
        elif al_puan > sat_puan and al_puan >= 1:
            karar = "AL"
            oncelik = "DUSUK"
            sebepler = al_sebepler if al_sebepler else ["Hafif al"]
        else:
            karar = "BEKLE"
            oncelik = "DUSUK"
            sebepler = []
        
        # Temiz degerler
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
        return {
            "sembol": sembol,
            "fiyat": 0,
            "rsi": 50,
            "macd": 0,
            "karar": "HATA",
            "oncelik": "DUSUK",
            "sebepler": [str(e)[:50]],
            "al_puan": 0,
            "sat_puan": 0
        }


def portfoy_sinyalleri_al(kullanici_adi):
    """Kullanicinin portfoyu ve yeni hisseler icin sinyaller"""
    try:
        from auth import KullaniciYoneticisi
        yon = KullaniciYoneticisi()
        portfoy = yon.portfoy_al(kullanici_adi)
    except:
        portfoy = []
    
    sinyaller = []
    
    # Portfoydekiler icin
    for h in portfoy:
        try:
            s = sinyal_analiz(h["sembol"], maliyet=h["alis_fiyati"])
            if s and s["karar"] in ["AL", "SAT", "BEKLE"]:
                sinyaller.append(s)
        except:
            continue
    
    # Yeni hisseler icin
    yeni_hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                     "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK",
                     "ISCTR", "YKBNK", "SAHOL", "EKGYO", "TAVHL"]
    
    portfoy_semboller = [h["sembol"] for h in portfoy]
    
    for sembol in yeni_hisseler:
        if sembol in portfoy_semboller:
            continue
        try:
            s = sinyal_analiz(sembol)
            if s and s["karar"] in ["AL", "SAT"]:
                sinyaller.append(s)
        except:
            continue
    
    # Oncelik siralamasi
    sirala = {"YUKSEK": 0, "ORTA": 1, "DUSUK": 2}
    sinyaller.sort(key=lambda x: (
        0 if x["karar"] == "SAT" else 1 if x["karar"] == "AL" else 2,
        sirala.get(x.get("oncelik", "DUSUK"), 3)
    ))
    
    return sinyaller


def test_ile_calistir():
    """Test verileri ile calistir"""
    print("=" * 70)
    print("SINYAL TEST - 10 HISSE")
    print("=" * 70)
    
    # Test hisseleri ve maliyetleri
    test_hisseler = [
        ("THYAO", 250),
        ("GARAN", 95),
        ("ASELS", 35),
        ("TUPRS", 80),
        ("EREGL", 45),
        ("KCHOL", 150),
        ("PETKM", 20),
        ("BIMAS", 280),
        ("SISE", 50),
        ("AKBNK", 65),
    ]
    
    al_sayisi = 0
    sat_sayisi = 0
    beklenen = 0
    
    print(f"\n{len(test_hisseler)} hisse analiz ediliyor...\n")
    
    for sembol, maliyet in test_hisseler:
        s = sinyal_analiz(sembol, maliyet=float(maliyet))
        if s:
            karar = s["karar"]
            fiyat = s["fiyat"]
            rsi = s["rsi"]
            oncelik = s["oncelik"]
            
            if karar == "AL":
                al_sayisi += 1
                emoji = "🟢"
            elif karar == "SAT":
                sat_sayisi += 1
                emoji = "🔴"
            else:
                beklenen += 1
                emoji = "⏸️"
            
            print(f"{emoji} {sembol}: {karar} | {fiyat} TL | RSI:{rsi} | Oncelik:{oncelik}")
            print(f"   AL:{s['al_puan']} SAT:{s['sat_puan']}")
            for sebep in s.get("sebepler", [])[:2]:
                print(f"   - {sebep}")
            print()
    
    print("=" * 70)
    print(f"SONUC: 🟢 {al_sayisi} AL  🔴 {sat_sayisi} SAT  ⏸️ {beklenen} BEKLE")
    print("=" * 70)


if __name__ == "__main__":
    test_ile_calistir()
    input("\nCikmak icin Enter'a basin...")