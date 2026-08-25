"""
BIST Risk Analizi
Borsa Istanbul hisseleri icin gelismis risk analizi
Sharpe Ratio, Max Drawdown, VaR, Beta, Volatilite, Korelasyon
"""

import yfinance as yf
import numpy as np
from datetime import datetime
from collections import defaultdict


# ============================================
# YARDIMCI FONKSIYONLAR
# ============================================

def guvenli_veri(sembol, period="6mo"):
    """Yahoo'dan guvenli veri cekme"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period=period)
        if veri is None or len(veri) < 60:
            return None
        return veri
    except Exception as e:
        print(f"Veri hatasi ({sembol}): {e}")
        return None


def getiri_hesapla(fiyatlar):
    """Gunluk getirileri hesapla"""
    try:
        if len(fiyatlar) < 2:
            return np.array([])
        return np.diff(fiyatlar) / fiyatlar[:-1]
    except:
        return np.array([])


def nan_kontrol(deger, varsayilan=0.0):
    """NaN kontrolu"""
    if deger is None or (isinstance(deger, float) and (deger != deger)):
        return varsayilan
    return deger


# ============================================
# TEKNIK GOSTERGELER
# ============================================

def volatilite(fiyatlar, yillik=True):
    """Volatilite (standart sapma)"""
    try:
        getiriler = getiri_hesapla(fiyatlar)
        if len(getiriler) < 30:
            return 0.0
        vol = float(np.std(getiriler))
        if yillik:
            vol *= np.sqrt(252)  # Yillik volatilite
        return vol * 100  # Yuzde olarak
    except:
        return 0.0


def sharpe_ratio(fiyatlar, risksiz_oran=0.40):
    """Sharpe Ratio: (Getiri - Risksiz) / Risk"""
    try:
        getiriler = getiri_hesapla(fiyatlar)
        if len(getiriler) < 30 or np.std(getiriler) == 0:
            return 0.0
        # Yillik getiri ve risk
        yillik_getiri = float(np.mean(getiriler)) * 252 * 100  # Yuzde
        yillik_risk = float(np.std(getiriler)) * np.sqrt(252) * 100
        
        if yillik_risk == 0:
            return 0.0
        
        sharpe = (yillik_getiri - risksiz_oran) / yillik_risk
        return float(sharpe)
    except:
        return 0.0


def max_drawdown(fiyatlar):
    """Maximum Drawdown (en buyuk kayip yuzdesi)"""
    try:
        if len(fiyatlar) < 2:
            return 0.0
        
        maksimum = float(fiyatlar[0])
        max_dd = 0.0
        
        for fiyat in fiyatlar:
            fiyat = float(fiyat)
            if fiyat > maksimum:
                maksimum = fiyat
            if maksimum > 0:
                dd = ((maksimum - fiyat) / maksimum) * 100
                if dd > max_dd:
                    max_dd = dd
        
        return float(max_dd)
    except:
        return 0.0


def value_at_risk(fiyatlar, guven=0.95):
    """VaR: %95 guvenle maksimum kayip"""
    try:
        getiriler = getiri_hesapla(fiyatlar)
        if len(getiriler) < 30:
            return 0.0
        # Tarihsel simulasyon
        sirali = np.sort(getiriler)
        index = int((1 - guven) * len(sirali))
        if index >= len(sirali):
            index = len(sirali) - 1
        var = float(-sirali[index] * 100)
        return var
    except:
        return 0.0


def beta_hesapla(hisse_fiyatlar, endeks_fiyatlar):
    """Beta: Piyasa ile korelasyon"""
    try:
        if len(hisse_fiyatlar) < 30 or len(endeks_fiyatlar) < 30:
            return 1.0
        
        min_len = min(len(hisse_fiyatlar), len(endeks_fiyatlar))
        h_getiriler = getiri_hesapla(hisse_fiyatlar[-min_len:])
        e_getiriler = getiri_hesapla(endeks_fiyatlar[-min_len:])
        
        if len(h_getiriler) < 2 or len(e_getiriler) < 2:
            return 1.0
        
        var_e = float(np.var(e_getiriler))
        if var_e == 0:
            return 1.0
        
        cov = float(np.cov(h_getiriler, e_getiriler)[0][1])
        return cov / var_e
    except:
        return 1.0


def korelasyon(fiyatlar1, fiyatlar2):
    """Iki hisse arasi korelasyon"""
    try:
        min_len = min(len(fiyatlar1), len(fiyatlar2))
        if min_len < 30:
            return 0.0
        
        g1 = getiri_hesapla(fiyatlar1[-min_len:])
        g2 = getiri_hesapla(fiyatlar2[-min_len:])
        
        if len(g1) < 2 or len(g2) < 2:
            return 0.0
        
        kor = float(np.corrcoef(g1, g2)[0][1])
        if kor != kor:  # NaN kontrolu
            return 0.0
        return kor
    except:
        return 0.0


def risk_skor_hesapla(vol, mdd, beta, agirlik):
    """0-10 arasi risk skoru"""
    skor = 0
    
    # Volatilite (0-3 puan)
    if vol > 60:
        skor += 3
    elif vol > 40:
        skor += 2
    elif vol > 25:
        skor += 1
    
    # Max Drawdown (0-3 puan)
    if mdd > 50:
        skor += 3
    elif mdd > 30:
        skor += 2
    elif mdd > 15:
        skor += 1
    
    # Beta (0-2 puan)
    if beta > 1.5:
        skor += 2
    elif beta > 1.2:
        skor += 1
    elif beta < 0.5:
        skor += 1
    
    # Agirlik yogunlugu (0-2 puan)
    if agirlik > 50:
        skor += 2
    elif agirlik > 30:
        skor += 1
    
    return min(10, skor)


# ============================================
# ANA FONKSIYON
# ============================================

def portfoy_risk_analizi(portfoy_hisseler):
    """
    Ana risk analiz fonksiyonu
    
    portfoy_hisseler: [{"sembol": "THYAO", "adet": 100, "alis_fiyati": 250}, ...]
    
    Returns: dict veya None
    """
    if not portfoy_hisseler:
        return None
    
    try:
        # BIST 100 endeks verisi
        endeks = yf.Ticker("XU030.IS")
        endeks_veri = endeks.history(period="6mo")
        endeks_fiyatlar = endeks_veri['Close'].values if endeks_veri is not None and len(endeks_veri) > 0 else np.array([])
        
        toplam_deger = 0
        toplam_maliyet = 0
        hisse_verileri = []
        fiyatlar_dict = {}
        
        # Her hisse icin veri
        for h in portfoy_hisseler:
            try:
                sembol = h.get("sembol", "").upper()
                if not sembol:
                    continue
                
                veri = guvenli_veri(sembol)
                if veri is None or len(veri) < 60:
                    continue
                
                kapanis = veri['Close'].values.astype(float)
                fiyatlar_dict[sembol] = kapanis
                
                guncel = float(kapanis[-1])
                adet = int(h.get("adet", 0))
                maliyet = float(h.get("alis_fiyati", 0))
                
                if adet <= 0 or maliyet <= 0:
                    continue
                
                deger = adet * guncel
                maliyet_toplam = adet * maliyet
                kar = deger - maliyet_toplam
                kar_yuzde = ((guncel - maliyet) / maliyet) * 100
                
                toplam_deger += deger
                toplam_maliyet += maliyet_toplam
                
                # Risk metrikleri
                vol = volatilite(kapanis)
                sr = sharpe_ratio(kapanis)
                mdd = max_drawdown(kapanis)
                var95 = value_at_risk(kapanis)
                beta = beta_hesapla(kapanis, endeks_fiyatlar) if len(endeks_fiyatlar) > 0 else 1.0
                
                hisse_verileri.append({
                    "sembol": sembol,
                    "adet": adet,
                    "maliyet": maliyet,
                    "guncel": round(guncel, 2),
                    "deger": round(deger, 2),
                    "maliyet_toplam": round(maliyet_toplam, 2),
                    "kar": round(kar, 2),
                    "kar_yuzde": round(kar_yuzde, 2),
                    "agirlik": 0,  # Sonra hesaplanacak
                    "volatilite": round(vol, 2),
                    "sharpe": round(sr, 2),
                    "max_drawdown": round(mdd, 2),
                    "var_95": round(var95, 2),
                    "beta": round(beta, 2),
                    "risk_skor": 0  # Sonra hesaplanacak
                })
            except Exception as e:
                print(f"Hisse hatasi ({h.get('sembol', '?')}): {e}")
                continue
        
        if not hisse_verileri:
            return None
        
        # Agirlik ve risk skoru
        for hv in hisse_verileri:
            if toplam_deger > 0:
                hv["agirlik"] = round((hv["deger"] / toplam_deger) * 100, 2)
            else:
                hv["agirlik"] = 0
            
            hv["risk_skor"] = risk_skor_hesapla(
                hv["volatilite"],
                hv["max_drawdown"],
                hv["beta"],
                hv["agirlik"]
            )
        
        # Korelasyonlar
        korelasyonlar = []
        semboller = [hv["sembol"] for hv in hisse_verileri]
        
        for i in range(len(semboller)):
            for j in range(i + 1, len(semboller)):
                try:
                    if semboller[i] in fiyatlar_dict and semboller[j] in fiyatlar_dict:
                        kor = korelasyon(
                            fiyatlar_dict[semboller[i]],
                            fiyatlar_dict[semboller[j]]
                        )
                        if abs(kor) > 0.7:
                            korelasyonlar.append({
                                "hisse1": semboller[i],
                                "hisse2": semboller[j],
                                "korelasyon": round(kor, 2),
                                "tip": "YUKSEK" if kor > 0.7 else "TERS"
                            })
                except:
                    continue
        
        # Portfoy genel metrikleri
        portfoy_volatilite = round(np.mean([hv["volatilite"] for hv in hisse_verileri]), 2) if hisse_verileri else 0
        portfoy_sharpe = round(np.mean([hv["sharpe"] for hv in hisse_verileri]), 2) if hisse_verileri else 0
        portfoy_var = round(np.mean([hv["var_95"] for hv in hisse_verileri]), 2) if hisse_verileri else 0
        portfoy_beta = round(np.mean([hv["beta"] for hv in hisse_verileri]), 2) if hisse_verileri else 0
        
        # Cesitlendirme puani (0-100)
        cesitlendirme = 100
        
        if len(hisse_verileri) < 3:
            cesitlendirme -= 30
        elif len(hisse_verileri) < 5:
            cesitlendirme -= 15
        elif len(hisse_verileri) < 8:
            cesitlendirme -= 5
        
        max_agirlik = max([hv["agirlik"] for hv in hisse_verileri]) if hisse_verileri else 0
        if max_agirlik > 50:
            cesitlendirme -= 30
        elif max_agirlik > 35:
            cesitlendirme -= 20
        elif max_agirlik > 25:
            cesitlendirme -= 10
        
        yuksek_korelasyon = len([k for k in korelasyonlar if abs(k["korelasyon"]) > 0.8])
        if yuksek_korelasyon > 3:
            cesitlendirme -= 25
        elif yuksek_korelasyon > 1:
            cesitlendirme -= 15
        elif yuksek_korelasyon > 0:
            cesitlendirme -= 5

        cesitlendirme = max(0, min(100, cesitlendirme))

        # Genel risk puani
        genel_risk = 0
        if portfoy_volatilite > 40:
            genel_risk += 30
        elif portfoy_volatilite > 25:
            genel_risk += 20
        elif portfoy_volatilite > 15:
            genel_risk += 10

        if portfoy_var > 5:
            genel_risk += 25
        elif portfoy_var > 3:
            genel_risk += 15

        if portfoy_beta > 1.2:
            genel_risk += 15

        if cesitlendirme > 70:
            genel_risk = max(0, genel_risk - 15)
        elif cesitlendirme < 30:
            genel_risk += 20

        genel_risk = min(100, genel_risk)

        if genel_risk < 30:
            risk_seviye = "DUSUK"
            risk_renk = "#4caf50"
        elif genel_risk < 60:
            risk_seviye = "ORTA"
            risk_renk = "#ff9800"
        else:
            risk_seviye = "YUKSEK"
            risk_renk = "#f44336"

        toplam_kar = toplam_deger - toplam_maliyet
        toplam_kar_yuzde = ((toplam_kar / toplam_maliyet) * 100) if toplam_maliyet > 0 else 0

        oneriler = []

        if max_agirlik > 30:
            oneriler.append(f"Tek hisse cok agir ({max_agirlik:.1f}%). Cesitlendirin.")

        if yuksek_korelasyon > 0:
            oneriler.append(f"{yuksek_korelasyon} hisse cok korelasyonlu. Farkli sektor ekleyin.")

        if portfoy_volatilite > 35:
            oneriler.append("Portfoy cok volatil. Dusuk volatiliteli hisseler ekleyin.")

        if portfoy_var > 5:
            oneriler.append(f"Gunluk VaR yuksek (%{portfoy_var:.1f}). Pozisyon boyutunu azaltin.")

        if len(hisse_verileri) < 5:
            oneriler.append("Portfoyde az hisse var. En az 5-8 hisseye cikar.")

        if not oneriler:
            oneriler.append("Portfoy dengeli gorunuyor.")

        return {
            "hisse_verileri": hisse_verileri,
            "korelasyonlar": korelasyonlar,
            "toplam_deger": round(toplam_deger, 2),
            "toplam_maliyet": round(toplam_maliyet, 2),
            "toplam_kar": round(toplam_kar, 2),
            "toplam_kar_yuzde": round(toplam_kar_yuzde, 2),
            "portfoy_sharpe": round(portfoy_sharpe, 2),
            "portfoy_volatilite": round(portfoy_volatilite, 2),
            "portfoy_var": round(portfoy_var, 2),
            "portfoy_beta": round(portfoy_beta, 2),
            "cesitlendirme": cesitlendirme,
            "genel_risk": genel_risk,
            "risk_seviye": risk_seviye,
            "risk_renk": risk_renk,
            "oneriler": oneriler,
            "tarih": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
    except Exception as e:
        print(f"Risk analizi hatasi: {e}")
        return None


if __name__ == "__main__":
    ornek_portfoy = [
        {"sembol": "THYAO", "adet": 10, "alis_fiyati": 250},
        {"sembol": "GARAN", "adet": 10, "alis_fiyati": 100},
        {"sembol": "ASELS", "adet": 20, "alis_fiyati": 35},
    ]

    sonuc = portfoy_risk_analizi(ornek_portfoy)
    if sonuc is None:
        print("Risk analizi yapilamadi. Hisse verisi alinamadi.")
    else:
        print("Portfoy Risk Analizi")
        print(f"Toplam deger: {sonuc['toplam_deger']} TL")
        print(f"Toplam kar: {sonuc['toplam_kar_yuzde']}%")
        print(f"Cesitlendirme: {sonuc['cesitlendirme']}/100")
        print(f"Genel risk: {sonuc['genel_risk']}/100 ({sonuc['risk_seviye']})")
        print(f"Oneriler: {sonuc['oneriler']}")
