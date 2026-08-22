"""
Risk Analizi Sistemi
Portfoy risklerini analiz eder ve uyarida bulunur
"""

import yfinance as yf
import numpy as np
from datetime import datetime
from collections import defaultdict
from portfoy import Portfoy
from sektor_analiz import HISSE_SEKTORLERI


def portfoy_verilerini_al():
    """Portfoy verilerini guncel fiyatlarla al"""
    p = Portfoy()
    
    if not p.hisseler:
        return None
    
    hisseler = []
    toplam_deger = 0
    
    for h in p.hisseler:
        try:
            ticker = yf.Ticker(h["sembol"] + ".IS")
            veri = ticker.history(period="3mo")
            
            if veri is None:
                continue
            
            fiyatlar = veri['Close'].to_numpy(dtype=float)
            fiyatlar = fiyatlar[np.isfinite(fiyatlar)]
            if len(fiyatlar) < 30:
                continue
            guncel = float(fiyatlar[-1])
            deger = h["adet"] * guncel
            toplam_deger += deger
            
            # Volatilite (standart sapma)
            volatilite = np.std(fiyatlar) / np.mean(fiyatlar) * 100
            
            # Max drawdown (en buyuk dusus)
            max_fiyat = np.max(fiyatlar)
            min_fiyat = np.min(fiyatlar)
            drawdown = ((max_fiyat - min_fiyat) / max_fiyat) * 100
            
            hisseler.append({
                "sembol": h["sembol"],
                "adet": h["adet"],
                "alis": h["alis_fiyati"],
                "guncel": guncel,
                "deger": deger,
                "sektor": HISSE_SEKTORLERI.get(h["sembol"], "Diger"),
                "volatilite": float(volatilite),
                "drawdown": float(drawdown),
                "fiyatlar": fiyatlar.tolist()
            })
        except:
            continue
    
    return {"hisseler": hisseler, "toplam_deger": toplam_deger}


def konsantrasyon_riski(hisseler, toplam_deger):
    """Tek hisse veya sektore yogunlasma riski"""
    uyarilar = []
    
    # Hisselerin portfoydeki yuzdesi
    print("\nHISSE DAGILIMI:")
    print("-" * 60)
    
    for h in sorted(hisseler, key=lambda x: x["deger"], reverse=True):
        yuzde = (h["deger"] / toplam_deger) * 100
        bar = "#" * int(yuzde / 2)
        
        if yuzde > 40:
            emoji = "[!]"
            uyari = f"  TEHLIKE: {h['sembol']} portfoyun %{yuzde:.1f}'i!"
            uyarilar.append(uyari)
        elif yuzde > 25:
            emoji = "[!]"
            uyari = f"  DIKKAT: {h['sembol']} portfoyun %{yuzde:.1f}'i (yuksek)"
            uyarilar.append(uyari)
        else:
            emoji = "[OK]"
        
        print(f"{emoji} {h['sembol']:8} {yuzde:>5.1f}%  {bar}")
    
    # Sektörel dağılım
    sektor_toplam = defaultdict(float)
    for h in hisseler:
        sektor_toplam[h["sektor"]] += h["deger"]
    
    print("\nSEKTOR DAGILIMI:")
    print("-" * 60)
    
    for sektor, deger in sorted(sektor_toplam.items(), key=lambda x: x[1], reverse=True):
        yuzde = (deger / toplam_deger) * 100
        bar = "#" * int(yuzde / 2)
        
        if yuzde > 50:
            emoji = "[!]"
            uyari = f"  TEHLIKE: {sektor} sektoru %{yuzde:.1f}!"
            uyarilar.append(uyari)
        elif yuzde > 35:
            emoji = "[!]"
            uyari = f"  DIKKAT: {sektor} sektoru %{yuzde:.1f}"
            uyarilar.append(uyari)
        else:
            emoji = "[OK]"
        
        print(f"{emoji} {sektor:15} {yuzde:>5.1f}%  {bar}")
    
    return uyarilar


def volatilite_riski(hisseler):
    """Fiyat dalgalanma riski"""
    uyarilar = []
    
    print("\nVOLATILITE ANALIZI (Fiyat Dalgalanmasi):")
    print("-" * 60)
    
    for h in sorted(hisseler, key=lambda x: x["volatilite"], reverse=True):
        if h["volatilite"] > 5:
            emoji = "[!]"
            seviye = "COK YUKSEK"
            uyari = f"  DIKKAT: {h['sembol']} cok volatil ({h['volatilite']:.2f}%)"
            uyarilar.append(uyari)
        elif h["volatilite"] > 3:
            emoji = "[!]"
            seviye = "YUKSEK"
        elif h["volatilite"] > 2:
            emoji = "[~]"
            seviye = "ORTA"
        else:
            emoji = "[OK]"
            seviye = "DUSUK"
        
        print(f"{emoji} {h['sembol']:8} Volatilite: {h['volatilite']:>5.2f}%  ({seviye})")
    
    return uyarilar


def drawdown_riski(hisseler):
    """En buyuk dusus (Drawdown) analizi"""
    uyarilar = []
    
    print("\nDRAWDOWN ANALIZI (En Kotu Senaryo):")
    print("-" * 60)
    
    for h in sorted(hisseler, key=lambda x: x["drawdown"], reverse=True):
        if h["drawdown"] > 40:
            emoji = "[!]"
            uyari = f"  TEHLIKE: {h['sembol']} son 3 ayda %{h['drawdown']:.1f} dustu!"
            uyarilar.append(uyari)
        elif h["drawdown"] > 25:
            emoji = "[!]"
            uyari = f"  DIKKAT: {h['sembol']} %{h['drawdown']:.1f} dustu"
            uyarilar.append(uyari)
        elif h["drawdown"] > 15:
            emoji = "[~]"
        else:
            emoji = "[OK]"
        
        print(f"{emoji} {h['sembol']:8} Max Drawdown: %{h['drawdown']:>5.1f}")
    
    return uyarilar


def cesitlendirme_puani(hisseler, toplam_deger):
    """Portfoy cesitlendirme puani (0-100)"""
    
    puan = 100
    
    # Tek hisse riski
    for h in hisseler:
        yuzde = (h["deger"] / toplam_deger) * 100
        if yuzde > 40:
            puan -= 30
        elif yuzde > 25:
            puan -= 15
        elif yuzde > 15:
            puan -= 5
    
    # Sektörel risk
    sektor_toplam = defaultdict(float)
    for h in hisseler:
        sektor_toplam[h["sektor"]] += h["deger"]
    
    for deger in sektor_toplam.values():
        yuzde = (deger / toplam_deger) * 100
        if yuzde > 60:
            puan -= 25
        elif yuzde > 40:
            puan -= 15
    
    # Hisse sayısı
    if len(hisseler) < 3:
        puan -= 20
    elif len(hisseler) < 5:
        puan -= 10
    elif len(hisseler) < 8:
        puan -= 5
    
    # Volatilite
    ortalama_volatilite = sum(h["volatilite"] for h in hisseler) / len(hisseler)
    if ortalama_volatilite > 4:
        puan -= 15
    elif ortalama_volatilite > 3:
        puan -= 10
    
    # Negatif olamaz
    puan = max(0, puan)
    
    return puan


def korelasyon_analizi(hisseler):
    """Hisseler arasi korelasyon"""
    if len(hisseler) < 2:
        return None
    
    print("\nKORELASYON ANALIZI (Hisseler Arasi Iliski):")
    print("-" * 60)
    
    uyarilar = []
    
    for i in range(len(hisseler)):
        for j in range(i + 1, len(hisseler)):
            h1 = hisseler[i]
            h2 = hisseler[j]
            
            # Pearson korelasyonu hesapla
            min_len = min(len(h1["fiyatlar"]), len(h2["fiyatlar"]))
            if min_len < 10:
                continue
            
            f1 = np.array(h1["fiyatlar"][-min_len:])
            f2 = np.array(h2["fiyatlar"][-min_len:])
            
            korelasyon = np.corrcoef(f1, f2)[0, 1]
            
            if abs(korelasyon) > 0.8:
                emoji = "[!]"
                yorum = "COK YUKSEK"
                if abs(korelasyon) > 0.8:
                    uyari = f"  DIKKAT: {h1['sembol']} - {h2['sembol']} korelasyon {korelasyon:.2f}"
                    uyarilar.append(uyari)
            elif abs(korelasyon) > 0.5:
                emoji = "[~]"
                yorum = "ORTA"
            else:
                emoji = "[OK]"
                yorum = "DUSUK"
            
            print(f"{emoji} {h1['sembol']:8} <-> {h2['sembol']:8}  Korelasyon: {korelasyon:+.2f}  ({yorum})")
    
    return uyarilar


def risk_raporu():
    """Tum risk analizi raporu"""
    print("=" * 70)
    print("RISK ANALIZI RAPORU")
    print("=" * 70)
    print(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print()
    
    veri = portfoy_verilerini_al()
    if not veri or not veri["hisseler"]:
        print("\n[!] Portfoy bos veya veri alinamadi!")
        print("Once portfoy.py ile hisse ekleyin.")
        return
    
    hisseler = veri["hisseler"]
    toplam_deger = veri["toplam_deger"]
    
    print(f"Toplam Portfoy Degeri: {toplam_deger:,.2f} TL")
    print(f"Hisse Sayisi: {len(hisseler)}")
    print()
    
    tum_uyarilar = []
    
    # 1. Konsantrasyon riski
    uyarilar = konsantrasyon_riski(hisseler, toplam_deger)
    tum_uyarilar.extend(uyarilar)
    
    # 2. Volatilite
    uyarilar = volatilite_riski(hisseler)
    tum_uyarilar.extend(uyarilar)
    
    # 3. Drawdown
    uyarilar = drawdown_riski(hisseler)
    tum_uyarilar.extend(uyarilar)
    
    # 4. Korelasyon
    if len(hisseler) >= 2:
        uyarilar = korelasyon_analizi(hisseler)
        if uyarilar:
            tum_uyarilar.extend(uyarilar)
    
    # 5. Çeşitlendirme puanı
    puan = cesitlendirme_puani(hisseler, toplam_deger)
    
    print("\n" + "=" * 70)
    print("CESITLENDIRME PUANI")
    print("=" * 70)
    
    if puan >= 80:
        emoji = "[OK]"
        yorum = "MUHTESEM! Portfoy cok iyi cesitlendirilmis."
    elif puan >= 60:
        emoji = "[OK]"
        yorum = "IYI. Cesitlendirme yeterli."
    elif puan >= 40:
        emoji = "[~]"
        yorum = "ORTA. Cesitlendirme artirilabilir."
    elif puan >= 20:
        emoji = "[!]"
        yorum = "ZAYIF. Cesitlendirme gerekli!"
    else:
        emoji = "[X]"
        yorum = "COK TEHLIKELI! Acil cesitlendirme gerekli!"
    
    print(f"\n{emoji} PUAN: {puan}/100")
    print(f"Yorum: {yorum}")
    
    # Tüm uyarılar
    print("\n" + "=" * 70)
    print("UYARILAR VE ONERILER")
    print("=" * 70)
    
    if tum_uyarilar:
        print("\nDIKKAT EDILMESI GEREKENLER:")
        for uyari in tum_uyarilar[:10]:
            print(uyari)
    else:
        print("\nTebrikler! Onemli bir risk tespit edilmedi.")
    
    # Genel öneriler
    print("\n" + "=" * 70)
    print("GENEL ONERILER")
    print("=" * 70)
    
    oneriler = []
    
    if len(hisseler) < 5:
        oneriler.append("Hisse sayisini 5-10 arasina cikar")
    
    sektor_sayisi = len(set(h["sektor"] for h in hisseler))
    if sektor_sayisi < 3:
        oneriler.append("En az 3-4 farkli sektor hissesi al")
    
    max_yuzde = max((h["deger"] / toplam_deger) * 100 for h in hisseler)
    if max_yuzde > 30:
        oneriler.append(f"Tek hissede max %{30:.0f} olsun (simdi: %{max_yuzde:.1f})")
    
    ortalama_volatilite = sum(h["volatilite"] for h in hisseler) / len(hisseler)
    if ortalama_volatilite > 3:
        oneriler.append("Dusuk volatiliteli hisselere yonel")
    
    if not oneriler:
        oneriler.append("Portfoyun cok iyi! Boyle devam et.")
    
    for oneri in oneriler:
        print(f"  -> {oneri}")
    
    print("=" * 70)
    
    print("\nNOT: Bu analiz yatirim tavsiyesi degildir.")
    print("Risk yonetiminde profesyonel yardim alin.")


if __name__ == "__main__":
    risk_raporu()
    input("\nCikmak icin Enter'a basin...")
