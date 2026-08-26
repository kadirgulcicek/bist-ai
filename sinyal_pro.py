import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor


def _benzersiz_hisse_havuzu():
    from hisse_listesi import hisse_listesi_getir
    return sorted({str(sembol).upper().replace(".IS", "") for sembol in hisse_listesi_getir()})


def guvenli_veri(sembol, period="6mo"):
    """Guvenli veri cekme"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period=period)
        if veri is None or len(veri) < 60:
            return None
        return veri
    except:
        return None


# ============================================
# 15+ TEKNIK GÖSTERGE
# ============================================

def rsi(fiyatlar, pencere=14):
    """RSI (0-100)"""
    try:
        if len(fiyatlar) < pencere + 1:
            return 50.0
        delta = np.diff(fiyatlar[-pencere-1:])
        pozitif = np.mean(delta[delta > 0]) if len(delta[delta > 0]) > 0 else 0
        negatif = abs(np.mean(delta[delta < 0])) if len(delta[delta < 0]) > 0 else 0.0001
        rs = pozitif / negatif
        return float(100 - (100 / (1 + rs)))
    except:
        return 50.0


def macd(fiyatlar):
    """MACD + Sinyal + Histogram"""
    try:
        if len(fiyatlar) < 26:
            return 0, 0, 0
        ema12 = ema(fiyatlar, 12)
        ema26 = ema(fiyatlar, 26)
        macd_line = ema12 - ema26
        signal_line = macd_line * 0.85
        histogram = macd_line - signal_line
        return float(macd_line), float(signal_line), float(histogram)
    except:
        return 0, 0, 0


def ema(veriler, pencere):
    """EMA"""
    try:
        if len(veriler) < pencere:
            return np.mean(veriler)
        multiplier = 2.0 / (pencere + 1)
        ema_deger = np.mean(veriler[:pencere])
        for fiyat in veriler[pencere:]:
            ema_deger = (fiyat - ema_deger) * multiplier + ema_deger
        return float(ema_deger)
    except:
        return 0


def sma(veriler, pencere):
    """SMA"""
    try:
        if len(veriler) < pencere:
            return np.mean(veriler) if len(veriler) > 0 else 0
        return float(np.mean(veriler[-pencere:]))
    except:
        return 0


def bollinger(fiyatlar, pencere=20, std=2):
    """Bollinger Bands"""
    try:
        if len(fiyatlar) < pencere:
            return 0, 0, 0, 0.5
        orta = sma(fiyatlar, pencere)
        standart = np.std(fiyatlar[-pencere:])
        ust = orta + (standart * std)
        alt = orta - (standart * std)
        guncel = fiyatlar[-1]
        pozisyon = (guncel - alt) / (ust - alt) if (ust - alt) > 0 else 0.5
        return float(alt), float(orta), float(ust), float(pozisyon)
    except:
        return 0, 0, 0, 0.5


def adx(fiyatlar, pencere=14):
    """ADX (Trend Gucu)"""
    try:
        if len(fiyatlar) < pencere * 2:
            return 20.0
        
        # Basit ADX hesaplamasi
        yuksekler = fiyatlar
        dusukler = fiyatlar
        
        # True Range
        tr_list = []
        for i in range(1, len(fiyatlar)):
            tr = max(
                yuksekler[i] - dusukler[i],
                abs(yuksekler[i] - yuksekler[i-1]),
                abs(dusukler[i] - dusukler[i-1])
            )
            tr_list.append(tr)
        
        # +DM ve -DM
        plus_dm = []
        minus_dm = []
        for i in range(1, len(fiyatlar)):
            up = yuksekler[i] - yuksekler[i-1] if yuksekler[i] > yuksekler[i-1] else 0
            down = dusukler[i-1] - dusukler[i] if dusukler[i] < dusukler[i-1] else 0
            plus_dm.append(up)
            minus_dm.append(down)
        
        # Son N pencere
        atr = np.mean(tr_list[-pencere:]) if tr_list else 0
        plus_di = np.mean(plus_dm[-pencere:]) if plus_dm else 0
        minus_di = np.mean(minus_dm[-pencere:]) if minus_dm else 0
        
        if atr == 0:
            return 20.0
        
        plus_dmi = (plus_di / atr) * 100
        minus_dmi = (minus_di / atr) * 100
        
        sum_dmi = plus_dmi + minus_dmi
        if sum_dmi == 0:
            return 20.0
        
        dx = abs(plus_dmi - minus_dmi) / sum_dmi * 100
        return float(min(100, max(0, dx)))
    except:
        return 20.0


def stochastic(fiyatlar, pencere=14):
    """Stochastic Oscillator (%K, %D)"""
    try:
        if len(fiyatlar) < pencere:
            return 50.0, 50.0
        son_n = fiyatlar[-pencere:]
        en_yuksek = max(son_n)
        en_dusuk = min(son_n)
        guncel = fiyatlar[-1]
        
        if en_yuksek == en_dusuk:
            return 50.0, 50.0
        
        k = ((guncel - en_dusuk) / (en_yuksek - en_dusuk)) * 100
        
        # %D = son 3 %K ortalamasi
        son_3_k = []
        for i in range(-3, 0):
            sn = fiyatlar[i-pencere+1:i+1] if i-pencere+1 >= -len(fiyatlar) else fiyatlar[:i+1]
            if len(sn) >= pencere:
                eh = max(sn)
                ed = min(sn)
                if eh != ed:
                    k_val = ((fiyatlar[i] - ed) / (eh - ed)) * 100
                    son_3_k.append(k_val)
        
        d = np.mean(son_3_k) if son_3_k else k
        return float(k), float(d)
    except:
        return 50.0, 50.0


def williams_r(fiyatlar, pencere=14):
    """Williams %R (-100 ile 0)"""
    try:
        if len(fiyatlar) < pencere:
            return -50.0
        son_n = fiyatlar[-pencere:]
        en_yuksek = max(son_n)
        en_dusuk = min(son_n)
        guncel = fiyatlar[-1]
        
        if en_yuksek == en_dusuk:
            return -50.0
        
        wr = ((en_yuksek - guncel) / (en_yuksek - en_dusuk)) * -100
        return float(wr)
    except:
        return -50.0


def cci(fiyatlar, pencere=20):
    """Commodity Channel Index"""
    try:
        if len(fiyatlar) < pencere:
            return 0.0
        tp_list = fiyatlar[-pencere:]  # Tipik fiyat = close (basitlestirilmis)
        sma_tp = np.mean(tp_list)
        mean_dev = np.mean([abs(tp - sma_tp) for tp in tp_list])
        if mean_dev == 0:
            return 0.0
        cci = (tp_list[-1] - sma_tp) / (0.015 * mean_dev)
        return float(cci)
    except:
        return 0.0


def fibonacci(fiyatlar, pencere=60):
    """Fibonacci Destek/Direnc"""
    try:
        if len(fiyatlar) < pencere:
            return None, None
        son_n = fiyatlar[-pencere:]
        max_fiyat = max(son_n)
        min_fiyat = min(son_n)
        aralik = max_fiyat - min_fiyat
        
        # %38.2, %50, %61.8 seviyeleri (destek)
        fib_382 = max_fiyat - aralik * 0.382
        fib_618 = max_fiyat - aralik * 0.618
        
        return float(fib_382), float(fib_618)
    except:
        return None, None


def hacim_analizi(fiyatlar, hacimler):
    """Detayli hacim analizi"""
    try:
        if len(hacimler) < 20:
            return {"trend": "BELIRSIZ", "guven": 0}
        
        son_5_hacim = np.mean(hacimler[-5:])
        onceki_5_hacim = np.mean(hacimler[-10:-5])
        genel_hacim = np.mean(hacimler[-20:])
        
        trend = "BELIRSIZ"
        if son_5_hacim > onceki_5_hacim * 1.2:
            trend = "YUKSELIYOR"
        elif son_5_hacim < onceki_5_hacim * 0.8:
            trend = "DUSUYOR"
        
        guven = min(100, (son_5_hacim / genel_hacim) * 50) if genel_hacim > 0 else 0
        
        return {"trend": trend, "guven": float(guven), "son_5": float(son_5_hacim), "genel": float(genel_hacim)}
    except:
        return {"trend": "BELIRSIZ", "guven": 0}


def formasyon_tespit(fiyatlar):
    """Basit formasyon tespiti"""
    try:
        if len(fiyatlar) < 30:
            return []
        
        formasyonlar = []
        son_5 = fiyatlar[-5:]
        onceki_5 = fiyatlar[-10:-5]
        
        # Yükseliş trendi
        if all(son_5[i] < son_5[i+1] for i in range(len(son_5)-1)):
            if all(onceki_5[i] < onceki_5[i+1] for i in range(len(onceki_5)-1)):
                formasyonlar.append("Yukselis trendi")
        
        # Düşüş trendi
        if all(son_5[i] > son_5[i+1] for i in range(len(son_5)-1)):
            if all(onceki_5[i] > onceki_5[i+1] for i in range(len(onceki_5)-1)):
                formasyonlar.append("Dusus trendi")
        
        # Dip oluşumu (V)
        if (son_5[2] < son_5[0] and son_5[2] < son_5[4] and 
            son_5[1] > son_5[2] and son_5[3] > son_5[2]):
            formasyonlar.append("Dip formasyonu (V)")
        
        # Tepe oluşumu
        if (son_5[2] > son_5[0] and son_5[2] > son_5[4] and 
            son_5[1] < son_5[2] and son_5[3] < son_5[2]):
            formasyonlar.append("Tepe formasyonu")
        
        return formasyonlar
    except:
        return []


# ============================================
# ANA SINYAL MOTORU
# ============================================

def sinyal_analiz(sembol, maliyet=None):
    """Ana sinyal analizi - 15+ gosterge"""
    try:
        veri = guvenli_veri(sembol, "6mo")
        if veri is None or len(veri) < 60:
            return {
                "sembol": sembol,
                "fiyat": 0, "karar": "VERI_YOK",
                "oncelik": "DUSUK",
                "sebepler": ["Veri alinamadi"],
                "rsi": 50, "macd": 0, "adx": 20,
                "al_puan": 0, "sat_puan": 0
            }
        
        kapanis = veri['Close'].values
        hacimler = veri['Volume'].values
        guncel = float(kapanis[-1])
        
        # Tum gostergeler
        rsi_v = rsi(kapanis)
        macd_v, sinyal_v, hist_v = macd(kapanis)
        ma_5 = sma(kapanis, 5)
        ma_10 = sma(kapanis, 10)
        ma_20 = sma(kapanis, 20)
        ma_50 = sma(kapanis, 50)
        ma_200 = sma(kapanis, 200) if len(kapanis) >= 200 else ma_50
        bb_alt, bb_orta, bb_ust, bb_pos = bollinger(kapanis)
        adx_v = adx(kapanis)
        stoch_k, stoch_d = stochastic(kapanis)
        wr_v = williams_r(kapanis)
        cci_v = cci(kapanis)
        fib_382, fib_618 = fibonacci(kapanis)
        hacim_bilgi = hacim_analizi(kapanis, hacimler)
        formasyonlar = formasyon_tespit(kapanis)
        
        # ============================
        # AL PUANI (agirlikli)
        # ============================
        al_puan = 0.0
        al_sebepler = []
        
        # RSI (agirlik: 1.5)
        if rsi_v < 25:
            al_puan += 2.5
            al_sebepler.append(f"RSI cok asiri satim ({rsi_v:.1f})")
        elif rsi_v < 35:
            al_puan += 1.5
            al_sebepler.append(f"RSI asiri satim ({rsi_v:.1f})")
        elif rsi_v < 45:
            al_puan += 0.5
            al_sebepler.append(f"RSI dusuk ({rsi_v:.1f})")
        
        # MACD (agirlik: 2.0)
        if macd_v > sinyal_v and macd_v > 0:
            al_puan += 2.0
            al_sebepler.append("MACD guclu pozitif")
        elif macd_v > sinyal_v:
            al_puan += 1.0
            al_sebepler.append("MACD pozitif donuyor")
        elif hist_v > 0:
            al_puan += 0.5
            al_sebepler.append("MACD histogram pozitif")
        
        # Trend (agirlik: 2.5)
        if ma_5 > ma_20 > ma_50:
            al_puan += 2.5
            al_sebepler.append("Guclu yukselis trendi")
        elif ma_5 > ma_20:
            al_puan += 1.5
            al_sebepler.append("Trend yukarida")
        elif guncel > ma_50:
            al_puan += 0.5
            al_sebepler.append("MA50 ustunde")
        
        # Bollinger (agirlik: 1.5)
        if bb_pos < 0.1:
            al_puan += 2.0
            al_sebepler.append("Bollinger altinda (satis baski)")
        elif bb_pos < 0.3:
            al_puan += 1.0
            al_sebepler.append("Bollinger alt bolgesinde")
        
        # Stochastic (agirlik: 1.5)
        if stoch_k < 20 and stoch_k > stoch_d:
            al_puan += 1.5
            al_sebepler.append("Stochastic asiri satim donuyor")
        elif stoch_k < 30:
            al_puan += 0.5
            al_sebepler.append("Stochastic dusuk")
        
        # Williams %R (agirlik: 1.0)
        if wr_v < -80:
            al_puan += 1.5
            al_sebepler.append("Williams %R asiri satim")
        
        # CCI (agirlik: 1.0)
        if cci_v < -150:
            al_puan += 1.5
            al_sebepler.append("CCI cok asiri satim")
        elif cci_v < -100:
            al_puan += 1.0
            al_sebepler.append("CCI asiri satim")
        
        # Hacim (agirlik: 1.5)
        if hacim_bilgi["trend"] == "YUKSELIYOR" and hacim_bilgi["guven"] > 80:
            al_puan += 1.5
            al_sebepler.append("Hacim yukseliyor ve guclu")
        elif hacim_bilgi["trend"] == "YUKSELIYOR":
            al_puan += 1.0
            al_sebepler.append("Hacim yukseliyor")
        
        # ADX (trend gucu) (agirlik: 1.0)
        if adx_v > 25 and ma_5 > ma_20:
            al_puan += 1.0
            al_sebepler.append(f"Guclu trend (ADX:{adx_v:.1f})")
        
        # Formasyon
        if "Yukselis trendi" in formasyonlar:
            al_puan += 1.0
            al_sebepler.append("Yukselis formasyonu")
        elif "Dip formasyonu (V)" in formasyonlar:
            al_puan += 1.5
            al_sebepler.append("Dip formasyonu (V)")
        
        # Fibonacci destege yakinligi
        if fib_618 and abs(guncel - fib_618) / guncel < 0.03:
            al_puan += 1.0
            al_sebepler.append("Fibonacci %61.8 destege yakin")
        elif fib_382 and abs(guncel - fib_382) / guncel < 0.03:
            al_puan += 0.5
            al_sebepler.append("Fibonacci %38.2 destege yakin")
        
        # ============================
        # SAT PUANI (agirlikli)
        # ============================
        sat_puan = 0.0
        sat_sebepler = []
        
        # Kar/zarar (portfoyde olanlar icin)
        if maliyet is not None and maliyet > 0:
            kar_yuzde = ((guncel - maliyet) / maliyet) * 100
            
            if kar_yuzde >= 30:
                sat_puan += 4.0
                sat_sebepler.append(f"Cok guclu kar +%{kar_yuzde:.1f}")
            elif kar_yuzde >= 15:
                sat_puan += 3.0
                sat_sebepler.append(f"Guclu kar +%{kar_yuzde:.1f}")
            elif kar_yuzde >= 8:
                sat_puan += 2.0
                sat_sebepler.append(f"Iyi kar +%{kar_yuzde:.1f}")
            elif kar_yuzde >= 3:
                sat_puan += 1.0
                sat_sebepler.append(f"Kar +%{kar_yuzde:.1f}")
            
            if kar_yuzde <= -20:
                sat_puan += 5.0
                sat_sebepler.append(f"ACIL stop-loss %{kar_yuzde:.1f}")
            elif kar_yuzde <= -10:
                sat_puan += 4.0
                sat_sebepler.append(f"Stop-loss %{kar_yuzde:.1f}")
            elif kar_yuzde <= -5:
                sat_puan += 2.0
                sat_sebepler.append(f"Zarar %{kar_yuzde:.1f}")
        
        # RSI (agirlik: 1.5)
        if rsi_v > 80:
            sat_puan += 2.5
            sat_sebepler.append(f"RSI cok asiri alim ({rsi_v:.1f})")
        elif rsi_v > 70:
            sat_puan += 1.5
            sat_sebepler.append(f"RSI asiri alim ({rsi_v:.1f})")
        
        # MACD (agirlik: 1.5)
        if macd_v < sinyal_v and macd_v < 0:
            sat_puan += 1.5
            sat_sebepler.append("MACD guclu negatif")
        elif macd_v < sinyal_v:
            sat_puan += 1.0
            sat_sebepler.append("MACD negatif donuyor")
        elif hist_v < 0:
            sat_puan += 0.5
            sat_sebepler.append("MACD histogram negatif")
        
        # Trend (agirlik: 2.5)
        if ma_5 < ma_20 < ma_50:
            sat_puan += 2.5
            sat_sebepler.append("Guclu dusus trendi")
        elif ma_5 < ma_20:
            sat_puan += 1.5
            sat_sebepler.append("Trend asagida")
        elif guncel < ma_50:
            sat_puan += 0.5
            sat_sebepler.append("MA50 altinda")
        
        # Bollinger (agirlik: 1.5)
        if bb_pos > 0.95:
            sat_puan += 2.0
            sat_sebepler.append("Bollinger ustunde (alis baski)")
        elif bb_pos > 0.8:
            sat_puan += 1.0
            sat_sebepler.append("Bollinger ust bolgesinde")
        
        # Stochastic (agirlik: 1.5)
        if stoch_k > 85 and stoch_k < stoch_d:
            sat_puan += 1.5
            sat_sebepler.append("Stochastic asiri alim donuyor")
        
        # Williams %R (agirlik: 1.0)
        if wr_v > -20:
            sat_puan += 1.5
            sat_sebepler.append("Williams %R asiri alim")
        
        # CCI (agirlik: 1.0)
        if cci_v > 150:
            sat_puan += 1.5
            sat_sebepler.append("CCI cok asiri alim")
        elif cci_v > 100:
            sat_puan += 1.0
            sat_sebepler.append("CCI asiri alim")
        
        # Hacim (agirlik: 1.0)
        if hacim_bilgi["trend"] == "DUSUYOR":
            sat_puan += 0.5
            sat_sebepler.append("Hacim dusuyor")
        
        # ADX (agirlik: 1.0)
        if adx_v > 25 and ma_5 < ma_20:
            sat_puan += 1.0
            sat_sebepler.append(f"Guclu dusus trendi (ADX:{adx_v:.1f})")
        
        # Formasyon
        if "Dusus trendi" in formasyonlar:
            sat_puan += 1.0
            sat_sebepler.append("Dusus formasyonu")
        elif "Tepe formasyonu" in formasyonlar:
            sat_puan += 1.5
            sat_sebepler.append("Tepe formasyonu")
        
        # Fibonacci direnci yakinligi
        if fib_382 and abs(guncel - fib_382) / guncel < 0.03:
            sat_puan += 0.5
            sat_sebepler.append("Fibonacci %38.2 direnc yakin")
        
        # ============================
        # KARAR (agirlikli puanlama)
        # ============================
        # Min esikler
        AL_ESIK = 3.0   # AL icin minimum 3 puan
        SAT_ESIK = 2.5  # SAT icin minimum 2.5 puan
        
        if sat_puan >= SAT_ESIK and sat_puan > al_puan:
            karar = "SAT"
            oncelik = "YUKSEK" if sat_puan >= 4.5 else "ORTA"
            sebepler = sat_sebepler
        elif al_puan >= AL_ESIK and al_puan > sat_puan:
            karar = "AL"
            oncelik = "YUKSEK" if al_puan >= 5 else "ORTA"
            sebepler = al_sebepler
        elif sat_puan > al_puan and sat_puan >= 1.5:
            karar = "SAT"
            oncelik = "DUSUK"
            sebepler = sat_sebepler
        elif al_puan > sat_puan and al_puan >= 1.5:
            karar = "AL"
            oncelik = "DUSUK"
            sebepler = al_sebepler
        else:
            karar = "BEKLE"
            oncelik = "DUSUK"
            sebepler = []
        
        # Sonuclari dondur
        return {
            "sembol": sembol,
            "fiyat": round(guncel, 2),
            "rsi": round(rsi_v, 1),
            "macd": round(hist_v, 3),
            "adx": round(adx_v, 1),
            "stoch": round(stoch_k, 1),
            "cci": round(cci_v, 1),
            "williams": round(wr_v, 1),
            "bb_pos": round(bb_pos * 100, 1),
            "karar": karar,
            "oncelik": oncelik,
            "sebepler": sebepler,
            "al_puan": round(al_puan, 2),
            "sat_puan": round(sat_puan, 2),
            "formasyonlar": formasyonlar
        }
    except Exception as e:
        return {
            "sembol": sembol,
            "fiyat": 0, "rsi": 50, "macd": 0, "adx": 20,
            "karar": "HATA", "oncelik": "DUSUK",
            "sebepler": [str(e)[:50]],
            "al_puan": 0, "sat_puan": 0,
            "stoch": 50, "cci": 0, "williams": -50, "bb_pos": 50,
            "formasyonlar": []
        }


def portfoy_sinyalleri_al(kullanici_adi):
    """Portfoy + yeni hisseler icin sinyaller"""
    try:
        from auth import KullaniciYoneticisi
        yon = KullaniciYoneticisi()
        portfoy = yon.portfoy_al(kullanici_adi)
    except:
        portfoy = []
    
    sinyaller = []
    
    # Portfoydekiler
    for h in portfoy:
        try:
            s = sinyal_analiz(h["sembol"], maliyet=h["alis_fiyati"])
            if s and s["karar"] in ["AL", "SAT", "BEKLE"]:
                sinyaller.append(s)
        except:
            continue
    
    # Portfoy disinda kalan tum benzersiz BIST hisselerini tara.
    portfoy_semboller = {str(h["sembol"]).upper().replace(".IS", "") for h in portfoy}
    taranacaklar = [sembol for sembol in _benzersiz_hisse_havuzu() if sembol not in portfoy_semboller]

    def tara(sembol):
        try:
            sonuc = sinyal_analiz(sembol)
            return sonuc if sonuc and sonuc.get("karar") in ["AL", "SAT"] else None
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as havuz:
        sinyaller.extend(sonuc for sonuc in havuz.map(tara, taranacaklar) if sonuc)
    
    # Oncelik siralamasi
    sirala = {"YUKSEK": 0, "ORTA": 1, "DUSUK": 2}
    sinyaller.sort(key=lambda x: (
        0 if x["karar"] == "AL" else 1,
        sirala.get(x.get("oncelik", "DUSUK"), 3),
        -(x.get("al_puan", 0) if x["karar"] == "AL" else x.get("sat_puan", 0)),
    ))
    
    return sinyaller


def test_calistir():
    """Test - 15 hisse, cesitli durumlar"""
    print("=" * 70)
    print("PRO SINYAL SISTEMI - TEST")
    print("=" * 70)
    
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
        ("ISCTR", 8),
        ("YKBNK", 25),
        ("SAHOL", 90),
        ("EKGYO", 12),
        ("TAVHL", 200),
    ]
    
    print(f"\n{len(test_hisseler)} hisse analiz ediliyor...\n")
    
    al_sayisi = 0
    sat_sayisi = 0
    beklenen = 0
    
    for sembol, maliyet in test_hisseler:
        s = sinyal_analiz(sembol, maliyet=float(maliyet))
        if s:
            karar = s["karar"]
            if karar == "AL":
                al_sayisi += 1
                emoji = "🟢"
            elif karar == "SAT":
                sat_sayisi += 1
                emoji = "🔴"
            else:
                beklenen += 1
                emoji = "⏸️"
            
            print(f"{emoji} {sembol}: {karar} | {s['fiyat']} TL | ADX:{s['adx']} | RSI:{s['rsi']}")
            print(f"   Puan: AL:{s['al_puan']} SAT:{s['sat_puan']}")
            for sebep in s.get("sebepler", [])[:3]:
                print(f"   - {sebep}")
            print()
    
    print("=" * 70)
    print(f"SONUC: 🟢 {al_sayisi} AL  🔴 {sat_sayisi} SAT  ⏸️ {beklenen} BEKLE")
    print("=" * 70)


if __name__ == "__main__":
    test_calistir()
    input("\nCikmak icin Enter'a basin...")