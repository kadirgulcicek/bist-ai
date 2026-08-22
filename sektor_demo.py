"""
Sektor Analiz - DEMO VERI (Yahoo Finance sorunu icin gecici)
Gerçek veri gelince otomatik degistirilebilir
"""

from datetime import datetime
from sektor_veritabani import HISSE_SEKTORLERI
from collections import defaultdict
import random


def demo_veri_uret():
    """Demo sektor verisi uretir (gercek veri gelince silinecek)"""
    print("⚠️  DEMO VERİ MODU AKTIF")
    print("Yahoo Finance su an veri vermedigi icin simule verilerle gosteriliyor\n")
    
    sektor_verileri = defaultdict(list)
    
    # Her hisse icin rastgele ama gercekci veriler
    random.seed(42)  # Tutarlilik icin
    
    for sembol, sektor in HISSE_SEKTORLERI.items():
        # Sektore gore rastgele degisim (-5 ile +5 arasinda)
        if sektor == "Bankacilik":
            degisim = random.uniform(-2, 4)
        elif sektor == "Havacilik":
            degisim = random.uniform(-3, 3)
        elif sektor == "Enerji":
            degisim = random.uniform(-4, 2)
        elif sektor == "Otomotiv":
            degisim = random.uniform(-1, 5)
        else:
            degisim = random.uniform(-3, 3)
        
        sektor_verileri[sektor].append({
            "sembol": sembol,
            "fiyat": random.uniform(10, 500),
            "gunluk": degisim
        })
    
    return sektor_verileri


def sektor_analiz_demo():
    """Demo veri ile sektor analizi"""
    print("=" * 60)
    print("📊 BIST SEKTOR ANALIZI")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print()
    
    sektor_verileri = demo_veri_uret()
    
    # Rapor
    print("🏆 SEKTOR SIRALAMASI (Gunluk)")
    print("-" * 60)
    
    sektor_ozet = []
    for sektor, hisseler in sektor_verileri.items():
        ortalama = sum(h["gunluk"] for h in hisseler) / len(hisseler)
        sektor_ozet.append({
            "sektor": sektor,
            "hisse_sayisi": len(hisseler),
            "ortalama": ortalama,
            "hisseler": hisseler
        })
    
    sektor_ozet.sort(key=lambda x: x["ortalama"], reverse=True)
    
    for i, s in enumerate(sektor_ozet, 1):
        emoji = "📈" if s["ortalama"] > 0 else "�" if s["ortalama"] < 0 else "➖"
        print(f"{i:2}. {emoji} {s['sektor']:15} Ort: {s['ortalama']:+6.2f}%  ({s['hisse_sayisi']} hisse)")
    
    print("\n" + "=" * 60)
    print("🌟 EN IYI 10 HISSE")
    print("=" * 60)
    
    tum = []
    for s in sektor_ozet:
        for h in s["hisseler"]:
            tum.append({**h, "sektor": s["sektor"]})
    tum.sort(key=lambda x: x["gunluk"], reverse=True)
    
    for i, h in enumerate(tum[:10], 1):
        print(f"{i:2}. {h['sembol']:8} {h['sektor']:15} {h['gunluk']:+6.2f}%")
    
    print("\n📉 EN DUSUK 10 HISSE:")
    print("-" * 60)
    for i, h in enumerate(tum[-10:], 1):
        print(f"{i:2}. {h['sembol']:8} {h['sektor']:15} {h['gunluk']:+6.2f}%")
    
    print("\n" + "=" * 60)
    print("💡 SEKTOR ONERILERI")
    print("=" * 60)
    
    if len(sektor_ozet) >= 2:
        en_iyi = sektor_ozet[0]
        en_kotu = sektor_ozet[-1]
        
        print(f"✅ Guclu sektor: {en_iyi['sektor']} ({en_iyi['ortalama']:+.2f}%)")
        print(f"⚠️  Zayif sektor: {en_kotu['sektor']} ({en_kotu['ortalama']:+.2f}%)")
        
        pozitif = [s for s in sektor_ozet if s["ortalama"] > 1]
        negatif = [s for s in sektor_ozet if s["ortalama"] < -1]
        
        print(f"🚀 Yukselis trendi: {len(pozitif)} sektor")
        print(f"📉 Dusus trendi: {len(negatif)} sektor")
    
    print("\n⚠️  NOT: Bu DEMO verilerdir.")
    print("Yahoo Finance duzelince gercek verilerle degistirilecek.")
    print("=" * 60)


if __name__ == "__main__":
    sektor_analiz_demo()
    input("\nCikmak icin Enter'a basin...")
