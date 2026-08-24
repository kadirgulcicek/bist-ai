import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict


def hisse_getirisi_hesapla(fiyatlar):
    """Gunluk getiriler"""
    try:
        return np.diff(fiyatlar) / fiyatlar[:-1]
    except:
        return np.array([])


def sharpe_ratio(fiyatlar, risksiz_oran=0.10):
    """Sharpe Ratio: (Getiri - Risksiz) / Risk"""
    try:
        getiriler = hisse_getirisi_hesapla(fiyatlar)
        if len(getiriler) < 30 or np.std(getiriler) == 0:
            return 0.0
        # Yilliklandirilmis getiri ve risk
        yillik_getiri = np.mean(getiriler) * 252
        yillik_risk = np.std(getiriler) * np.sqrt(252)
        sharpe = (yillik_getiri - risksiz_oran) / yillik_risk
        return float(sharpe)
    except:
        return 0.0


def max_drawdown(fiyatlar):
    """Maximum Drawdown (en buyuk kayip)"""
    try:
        if len(fiyatlar) < 2:
            return 0.0
        maksimum = fiyatlar[0]
        max_dd = 0.0
        for fiyat in fiyatlar:
            if fiyat > maksimum:
                maksimum = fiyat
            dd = (maksimum - fiyat) / maksimum * 100
            if dd > max_dd:
                max_dd = dd
        return float(max_dd)
    except:
        return 0.0


def volatilite_hesapla(fiyatlar):
    """Volatilite (yillik standart sapma %)"""
    try:
        getiriler = hisse_getirisi_hesapla(fiyatlar)
        if len(getiriler) < 30:
            return 0.0
        yillik_volatilite = np.std(getiriler) * np.sqrt(252) * 100
        return float(yillik_volatilite)
    except:
        return 0.0


def value_at_risk(fiyatlar, guven=0.95):
    """VaR: X kadar kayip olma olasiligi"""
    try:
        getiriler = hisse_getirisi_hesapla(fiyatlar)
        if len(getiriler) < 30:
            return 0.0
        # Tarihsel simulasyon
        sirali = np.sort(getiriler)
        index = int((1 - guven) * len(sirali))
        var = -sirali[index] * 100
        return float(var)
    except:
        return 0.0


def beta_hesapla(hisse_fiyatlar, endeks_fiyatlar):
    """Beta: Piyasa ile iliski"""
    try:
        if len(hisse_fiyatlar) < 30 or len(endeks_fiyatlar) < 30:
            return 1.0
        min_len = min(len(hisse_fiyatlar), len(endeks_fiyatlar))
        hisse_getiriler = hisse_getirisi_hesapla(hisse_fiyatlar[-min_len:])
        endeks_getiriler = hisse_getirisi_hesapla(endeks_fiyatlar[-min_len:])
        
        if np.var(endeks_getiriler) == 0:
            return 1.0
        
        cov = np.cov(hisse_getiriler, endeks_getiriler)[0][1]
        var_e = np.var(endeks_getiriler)
        beta = cov / var_e
        return float(beta)
    except:
        return 1.0


def korelasyon_hesapla(fiyatlar1, fiyatlar2):
    """Iki hisse arasi korelasyon (-1 ile 1)"""
    try:
        min_len = min(len(fiyatlar1), len(fiyatlar2))
        if min_len < 30:
            return 0.0
        g1 = hisse_getirisi_hesapla(fiyatlar1[-min_len:])
        g2 = hisse_getirisi_hesapla(fiyatlar2[-min_len:])
        korelasyon = np.corrcoef(g1, g2)[0][1]
        return float(korelasyon) if not np.isnan(korelasyon) else 0.0
    except:
        return 0.0


def portfoy_risk_analiz(portfoy_hisseler):
    """Ana portfoy risk analizi"""
    try:
        # XU030 endeksini al
        endeks = yf.Ticker("XU030.IS")
        endeks_veri = endeks.history(period="6mo")
        endeks_fiyat = endeks_veri['Close'].values if endeks_veri is not None else np.array([])
        
        if not portfoy_hisseler:
            return None
        
        toplam_deger = 0
        toplam_maliyet = 0
        hisse_verileri = []
        fiyatlar_dict = {}
        
        # Her hisse icin veri
        for h in portfoy_hisseler:
            try:
                ticker = yf.Ticker(h["sembol"] + ".IS")
                veri = ticker.history(period="6mo")
                if veri is None or len(veri) < 60:
                    continue
                
                kapanis = veri['Close'].values
                fiyatlar_dict[h["sembol"]] = kapanis
                
                guncel = float(kapanis[-1])
                maliyet = h["alis_fiyati"]
                adet = h["adet"]
                deger = adet * guncel
                maliyet_toplam = adet * maliyet
                kar = deger - maliyet_toplam
                kar_yuzde = ((guncel - maliyet) / maliyet) * 100
                
                toplam_deger += deger
                toplam_maliyet += maliyet_toplam
                
                # Risk metrikleri
                sr = sharpe_ratio(kapanis)
                mdd = max_drawdown(kapanis)
                vol = volatilite_hesapla(kapanis)
                var = value_at_risk(kapanis)
                beta = beta_hesapla(kapanis, endeks_fiyat) if len(endeks_fiyat) > 0 else 1.0
                
                hisse_verileri.append({
                    "sembol": h["sembol"],
                    "adet": adet,
                    "maliyet": maliyet,
                    "guncel": round(guncel, 2),
                    "deger": round(deger, 2),
                    "maliyet_toplam": round(maliyet_toplam, 2),
                    "kar": round(kar, 2),
                    "kar_yuzde": round(kar_yuzde, 2),
                    "agirlik": 0,  # Sonra hesaplanacak
                    "sharpe": round(sr, 2),
                    "max_drawdown": round(mdd, 2),
                    "volatilite": round(vol, 2),
                    "var_95": round(var, 2),
                    "beta": round(beta, 2),
                    "risk_skor": 0  # Sonra hesaplanacak
                })
            except:
                continue
        
        if not hisse_verileri:
            return None
        
        # Agirliklari hesapla
        for hv in hisse_verileri:
            hv["agirlik"] = round((hv["deger"] / toplam_deger) * 100, 2)
        
        # Risk skorlari (her hisse icin)
        for hv in hisse_verileri:
            risk_skor = 0
            # Volatiliteye gore
            if hv["volatilite"] > 50:
                risk_skor += 3
            elif hv["volatilite"] > 30:
                risk_skor += 2
            elif hv["volatilite"] > 20:
                risk_skor += 1
            
            # Drawdown'a gore
            if hv["max_drawdown"] > 40:
                risk_skor += 3
            elif hv["max_drawdown"] > 25:
                risk_skor += 2
            elif hv["max_drawdown"] > 15:
                risk_skor += 1
            
            # Beta'ya gore (yuksek beta = piyasadan fazla hareket)
            if hv["beta"] > 1.3:
                risk_skor += 2
            elif hv["beta"] < 0.7:
                risk_skor += 1
            
            # Agirligi yuksekse (tek hisse cok agir)
            if hv["agirlik"] > 40:
                risk_skor += 3
            elif hv["agirlik"] > 25:
                risk_skor += 2
            elif hv["agirlik"] > 15:
                risk_skor += 1
            
            hv["risk_skor"] = min(10, risk_skor)
        
        # Korelasyonlar
        korelasyonlar = []
        semboller = [hv["sembol"] for hv in hisse_verileri]
        for i in range(len(semboller)):
            for j in range(i+1, len(semboller)):
                try:
                    kor = korelasyon_hesapla(
                        fiyatlar_dict[semboller[i]],
                        fiyatlar_dict[semboller[j]]
                    )
                    if abs(kor) > 0.7:  # Yuksek korelasyon
                        korelasyonlar.append({
                            "hisse1": semboller[i],
                            "hisse2": semboller[j],
                            "korelasyon": round(kor, 2),
                            "tip": "YUKSEK" if kor > 0.7 else "TERS"
                        })
                except:
                    continue
        
        # Portfoy genel metrikleri
        portfoy_sharpe = np.mean([hv["sharpe"] for hv in hisse_verileri]) if hisse_verileri else 0
        portfoy_volatilite = np.mean([hv["volatilite"] for hv in hisse_verileri]) if hisse_verileri else 0
        portfoy_var = np.mean([hv["var_95"] for hv in hisse_verileri]) if hisse_verileri else 0
        portfoy_beta = np.mean([hv["beta"] for hv in hisse_verileri]) if hisse_verileri else 0
        
        # Cesitlendirme puani (0-100)
        cesitlendirme = 100
        
        # Az hisse cezasi
        if len(hisse_verileri) < 3:
            cesitlendirme -= 30
        elif len(hisse_verileri) < 5:
            cesitlendirme -= 15
        
        # Tek hisse agirligi
        max_agirlik = max([hv["agirlik"] for hv in hisse_verileri]) if hisse_verileri else 0
        if max_agirlik > 40:
            cesitlendirme -= 25
        elif max_agirlik > 25:
            cesitlendirme -= 15
        
        # Yuksek korelasyon cezasi
        yuksek_korelasyon = len([k for k in korelasyonlar if abs(k["korelasyon"]) > 0.8])
        if yuksek_korelasyon > 2:
            cesitlendirme -= 20
        elif yuksek_korelasyon > 0:
            cesitlendirme -= 10
        
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
        
        # Cesitlendirme puani yuksekse risk dusur
        if cesitlendirme > 70:
            genel_risk = max(0, genel_risk - 15)
        elif cesitlendirme < 30:
            genel_risk += 20
        
        genel_risk = min(100, genel_risk)
        
        # Risk seviyesi
        if genel_risk < 30:
            risk_seviye = "DUSUK"
            risk_renk = "#4caf50"
        elif genel_risk < 60:
            risk_seviye = "ORTA"
            risk_renk = "#ff9800"
        else:
            risk_seviye = "YUKSEK"
            risk_renk = "#f44336"
        
        # Toplam kar/zarar
        toplam_kar = toplam_deger - toplam_maliyet
        toplam_kar_yuzde = ((toplam_kar / toplam_maliyet) * 100) if toplam_maliyet > 0 else 0
        
        # Oneriler
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


def test_risk():
    """Test"""
    print("=" * 70)
    print("RISK ANALIZI - TEST")
    print("=" * 70)
    
    # Test portfoyu
    test_portfoy = [
        {"sembol": "THYAO", "adet": 100, "alis_fiyati": 250},
        {"sembol": "GARAN", "adet": 50, "alis_fiyati": 95},
        {"sembol": "ASELS", "adet": 200, "alis_fiyati": 35},
        {"sembol": "TUPRS", "adet": 80, "alis_fiyati": 80},
        {"sembol": "EREGL", "adet": 150, "alis_fiyati": 45},
    ]
    
    sonuc = portfoy_risk_analiz(test_portfoy)
    
    if sonuc:
        print(f"\nToplam Deger: {sonuc['toplam_deger']} TL")
        print(f"Toplam Kar: {sonuc['toplam_kar_yuzde']}%")
        print(f"Sharpe: {sonuc['portfoy_sharpe']}")
        print(f"Volatilite: {sonuc['portfoy_volatilite']}%")
        print(f"VaR (95%): {sonuc['portfoy_var']}%")
        print(f"Beta: {sonuc['portfoy_beta']}")
        print(f"Cesitlendirme: {sonuc['cesitlendirme']}/100")
        print(f"Genel Risk: {sonuc['genel_risk']}/100 ({sonuc['risk_seviye']})")
        
        print(f"\nHisse Detaylari:")
        for h in sonuc['hisse_verileri']:
            print(f"  {h['sembol']}: Risk={h['risk_skor']}/10, Vol={h['volatilite']}%")
        
        print(f"\nOneriler:")
        for o in sonuc['oneriler']:
            print(f"  - {o}")
    
    input("\nCikmak icin Enter'a basin...")


if __name__ == "__main__":
    test_risk()