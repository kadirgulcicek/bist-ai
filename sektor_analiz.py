"""
BIST Sektor Bazli Analiz
Coklu dogrulanmis veri kaynagi
"""

from datetime import datetime
from collections import defaultdict

from veri_kaynaklari import hisse_veri_al


HISSE_SEKTORLERI = {
    "AKBNK": "Bankacilik", "GARAN": "Bankacilik", "ISCTR": "Bankacilik",
    "YKBNK": "Bankacilik", "HALKB": "Bankacilik", "VAKBN": "Bankacilik",
    "SKBNK": "Bankacilik", "ALBRK": "Bankacilik",
    "THYAO": "Havacilik", "PGSUS": "Havacilik", "TAVHL": "Havacilik",
    "FROTO": "Otomotiv", "TOASO": "Otomotiv", "DOAS": "Otomotiv",
    "KARSN": "Otomotiv",
    "ASELS": "Savunma",
    "BIMAS": "Perakende", "MGROS": "Perakende", "SOKM": "Perakende",
    "TUPRS": "Enerji", "PETKM": "Enerji", "AYDEM": "Enerji",
    "AKSA": "Enerji",
    "EREGL": "Demir-Celik", "KRDMD": "Demir-Celik", "ISDMR": "Demir-Celik",
    "LOGO": "Teknoloji", "KONTR": "Teknoloji", "PAPIL": "Teknoloji",
    "ARCLK": "Teknoloji",
    "EKGYO": "Gayrimenkul", "KLGYO": "Gayrimenkul",
    "KCHOL": "Holding", "SAHOL": "Holding", "AGHOL": "Holding",
    "ULKER": "Gida", "CCOLA": "Gida", "AEFES": "Gida",
    "KORDS": "Tekstil", "MAVI": "Tekstil",
    "GOLTS": "Kimya", "BAGFS": "Kimya", "SASA": "Kimya",
    "KOZAA": "Madencilik", "KOZAL": "Madencilik",
    "VESTL": "Elektronik", "GESAN": "Elektronik",
    "ENKAI": "Insaat",
    "TUKAS": "Gida",
}


def yahoo_veri_al(sembol):
    try:
        import yfinance as yf
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="5d")
        if veri is None or len(veri) < 2:
            return None
        guncel = float(veri['Close'].iloc[-1])
        dun = float(veri['Close'].iloc[-2])
        if guncel != guncel or dun != dun or guncel <= 0 or dun <= 0:
            return None
        return {
            "sembol": sembol,
            "fiyat": guncel,
            "gunluk": ((guncel - dun) / dun) * 100,
            "kaynak": "Yahoo"
        }
    except:
        return None


def guvenli_veri_al(sembol):
    return hisse_veri_al(sembol)


def sektor_analiz_yap():
    print("=" * 60)
    print("BIST SEKTOR ANALIZI")
    print("=" * 60)
    print(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print()
    
    tum_hisseler = list(HISSE_SEKTORLERI.keys())
    print(f"{len(tum_hisseler)} hisse analiz ediliyor...")
    
    sektor_verileri = defaultdict(list)
    kaynak_dagilim = {}
    
    for sembol in tum_hisseler:
        veri = guvenli_veri_al(sembol)
        if veri is None:
            continue
        if veri["gunluk"] != veri["gunluk"]:
            continue
        sektor = HISSE_SEKTORLERI[sembol]
        sektor_verileri[sektor].append(veri)
        kaynak = veri.get("kaynak", "Bilinmiyor")
        kaynak_dagilim[kaynak] = kaynak_dagilim.get(kaynak, 0) + 1
    
    print()
    for kaynak, sayi in kaynak_dagilim.items():
        print(f"   {kaynak}: {sayi} hisse")
    print()
    
    return dict(sektor_verileri)


def sektor_raporu_goster(sektor_verileri):
    sektor_ozet = []
    for sektor, hisseler in sektor_verileri.items():
        gecerli = [h for h in hisseler if h["gunluk"] == h["gunluk"]]
        if not gecerli:
            continue
        ortalama = sum(h["gunluk"] for h in gecerli) / len(gecerli)
        sektor_ozet.append({
            "sektor": sektor,
            "hisse_sayisi": len(gecerli),
            "ortalama": ortalama,
            "hisseler": gecerli
        })
    
    sektor_ozet.sort(key=lambda x: x["ortalama"], reverse=True)
    
    print("SEKTOR SIRALAMASI (Gunluk)")
    print("-" * 60)
    for i, s in enumerate(sektor_ozet, 1):
        if s["ortalama"] > 0:
            emoji = "YUKARI"
        elif s["ortalama"] < 0:
            emoji = "ASAGI"
        else:
            emoji = "SIFIR"
        print(f"{i:2}. {emoji:6} {s['sektor']:15} Ort: {s['ortalama']:+6.2f}%  ({s['hisse_sayisi']} hisse)")
    
    tum = []
    for s in sektor_ozet:
        for h in s["hisseler"]:
            tum.append({**h, "sektor": s["sektor"]})
    tum.sort(key=lambda x: x["gunluk"], reverse=True)
    
    print("\n" + "=" * 60)
    print("EN IYI 10 HISSE")
    print("=" * 60)
    for i, h in enumerate(tum[:10], 1):
        print(f"{i:2}. {h['sembol']:8} {h['sektor']:15} {h['gunluk']:+6.2f}%")
    
    print("\nEN DUSUK 10 HISSE:")
    print("-" * 60)


if __name__ == "__main__":
    veriler = sektor_analiz_yap()
    sektor_raporu_goster(veriler)
