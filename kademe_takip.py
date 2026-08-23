"""
Al-Sat Kademe Takibi
Destek/Direnç seviyeleri ve kademeli alım-satım stratejileri
"""

import yfinance as yf
import json
import os
from datetime import datetime
import time


class KademeTakip:
    def __init__(self):
        self.dosya = "kademe_planlari.json"
        self.planlar = self.yukle()
    
    def yukle(self):
        if os.path.exists(self.dosya):
            with open(self.dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def kaydet(self):
        with open(self.dosya, "w", encoding="utf-8") as f:
            json.dump(self.planlar, f, indent=2, ensure_ascii=False)
    
    def fiyat_al(self, sembol):
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="5d")
            if veri is None or len(veri) < 1:
                return None
            return float(veri['Close'].iloc[-1])
        except:
            return None
    
    def destek_direnc_kademeleri(self, sembol, kademe_sayisi=5):
        """Destek ve direnc seviyelerini hesaplar"""
        sembol = sembol.upper()
        
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="6mo")
            
            if veri is None or len(veri) < 60:
                return None
            
            fiyatlar = veri['Close'].values
            hacimler = veri['Volume'].values
            guncel = float(fiyatlar[-1])
            
            # Son 6 ayın min/max
            max_fiyat = float(fiyatlar.max())
            min_fiyat = float(fiyatlar.min())
            
            aralik = max_fiyat - min_fiyat
            
            # Kademe buyuklugu
            kademe = aralik / (kademe_sayisi * 2)
            
            direnc_kademeleri = []
            destek_kademeleri = []
            
            # Direnc kademeleri (yukaridan asagiya)
            for i in range(kademe_sayisi):
                seviye = max_fiyat - (kademe * i)
                if seviye > guncel:
                    direnc_kademeleri.append(round(seviye, 2))
            
            # Destek kademeleri (asagidan yukariya)
            for i in range(1, kademe_sayisi + 1):
                seviye = min_fiyat + (kademe * (i - 1))
                if seviye < guncel:
                    destek_kademeleri.append(round(seviye, 2))
            
            # Fibonacci seviyeleri
            fib_destek = min_fiyat + (aralik * 0.382)
            fib_direnc = max_fiyat - (aralik * 0.382)
            
            return {
                "sembol": sembol,
                "guncel": round(guncel, 2),
                "max_6ay": round(max_fiyat, 2),
                "min_6ay": round(min_fiyat, 2),
                "direnc_kademeleri": direnc_kademeleri,
                "destek_kademeleri": destek_kademeleri,
                "fib_destek": round(fib_destek, 2),
                "fib_direnc": round(fib_direnc, 2),
                "tarih": datetime.now().strftime("%Y-%m-%d")
            }
        except Exception as e:
            print(f"Hata: {e}")
            return None
    
    def kademeli_alim_plani(self, sembol, toplam_butce, kademe_sayisi=4):
        """Kademeli alım planı oluşturur"""
        seviyeler = self.destek_direnc_kademeleri(sembol)
        if not seviyeler:
            return None
        
        sembol = sembol.upper()
        guncel = seviyeler["guncel"]
        
        # Strateji: %25 ini guncel fiyattan, %75 ini desteklerden
        alimlar = []
        
        # İlk alım: şimdi
        ilk_adet = int((toplam_butce * 0.25) / guncel)
        alimlar.append({
            "seviye": "ŞİMDİ",
            "fiyat": guncel,
            "adet": ilk_adet,
            "tutar": round(ilk_adet * guncel, 2),
            "tetik": "Hemen al"
        })
        
        # Destek kademelerinden al
        kalan_butce = toplam_butce * 0.75
        destekler = seviyeler["destek_kademeleri"][:kademe_sayisi - 1]
        
        for i, destek in enumerate(destekler):
            butce_parca = kalan_butce / len(destekler) if len(destekler) > 0 else 0
            adet = int(butce_parca / destek) if destek > 0 else 0
            alimlar.append({
                "seviye": f"Destek {i+1}",
                "fiyat": destek,
                "adet": adet,
                "tutar": round(adet * destek, 2),
                "tetik": f"Fiyat {destek} TL'ye duserse al"
            })
        
        # Ortalama maliyet hesapla
        toplam_adet = sum(a["adet"] for a in alimlar)
        toplam_tutar = sum(a["tutar"] for a in alimlar)
        ortalama_maliyet = toplam_tutar / toplam_adet if toplam_adet > 0 else 0
        
        return {
            "sembol": sembol,
            "plan_tipi": "KADEMELI ALIM",
            "toplam_butce": toplam_butce,
            "alimlar": alimlar,
            "ortalama_maliyet": round(ortalama_maliyet, 2),
            "toplam_adet": toplam_adet,
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    
    def kademeli_satim_plani(self, sembol, mevcut_adet, maliyet):
        """Kademeli satım planı"""
        seviyeler = self.destek_direnc_kademeleri(sembol)
        if not seviyeler:
            return None
        
        sembol = sembol.upper()
        guncel = seviyeler["guncel"]
        direncler = seviyeler["direnc_kademeleri"][:3]
        
        satimlar = []
        kalan_adet = mevcut_adet
        
        # İlk satım: maliyetin %10 üstünde
        if direncler:
            ilk_hedef = maliyet * 1.10
            ilk_adet = int(mevcut_adet * 0.25)
            satimlar.append({
                "seviye": "İLK HEDEF",
                "fiyat": round(ilk_hedef, 2),
                "adet": ilk_adet,
                "tutar": round(ilk_adet * ilk_hedef, 2),
                "kar_pct": 10,
                "tetik": f"Fiyat {ilk_hedef:.2f} TL'ye ulasirsa"
            })
            kalan_adet -= ilk_adet
        
        # Direnç seviyelerinde sat
        for i, direnc in enumerate(direncler):
            oran = 0.25 if i < 2 else (kalan_adet / mevcut_adet if mevcut_adet > 0 else 0)
            adet = int(mevcut_adet * oran)
            if adet > 0:
                kar_pct = ((direnc - maliyet) / maliyet) * 100 if maliyet > 0 else 0
                satimlar.append({
                    "seviye": f"DİRENÇ {i+1}",
                    "fiyat": direnc,
                    "adet": adet,
                    "tutar": round(adet * direnc, 2),
                    "kar_pct": round(kar_pct, 1),
                    "tetik": f"Fiyat {direnc} TL'ye ulasirsa"
                })
        
        return {
            "sembol": sembol,
            "plan_tipi": "KADEMELI SATIM",
            "mevcut_adet": mevcut_adet,
            "maliyet": maliyet,
            "satimlar": satimlar,
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    
    def plan_kaydet(self, sembol, plan):
        sembol = sembol.upper()
        sembol_planlari = self.planlar.get(sembol, [])
        sembol_planlari.append(plan)
        self.planlar[sembol] = sembol_planlari
        self.kaydet()
    
    def planlari_goster(self, sembol=None):
        if not self.planlar:
            print("Henuz plan yok!")
            return
        
        if sembol:
            sembol = sembol.upper()
            planlar = self.planlar.get(sembol, [])
            if not planlar:
                print(f"{sembol} icin plan yok")
                return
        else:
            planlar = []
            for s, p in self.planlar.items():
                planlar.extend(p)
        
        print("=" * 70)
        print("KAYITLI PLANLAR")
        print("=" * 70)
        
        for plan in planlar:
            print(f"\n{plan['sembol']} - {plan.get('plan_tipi', 'GENEL')}")
            print(f"  Tarih: {plan.get('tarih', 'N/A')}")
            if "alimlar" in plan:
                print("  Alimlar:")
                for a in plan["alimlar"]:
                    print(f"    - {a['seviye']}: {a['adet']} adet @ {a['fiyat']} TL = {a['tutar']} TL")
            if "satimlar" in plan:
                print("  Satimlar:")
                for s in plan["satimlar"]:
                    print(f"    - {s['seviye']}: {s['adet']} adet @ {s['fiyat']} TL (Kar: %{s.get('kar_pct', 0)})")


# ============================================
# ANA PROGRAM
# ============================================
def main():
    takip = KademeTakip()
    
    print("=" * 60)
    print("AL-SAT KADEME TAKIBI")
    print("=" * 60)
    print()
    print("1. Destek/Direnc kademeleri goster")
    print("2. Kademeli alim plani olustur")
    print("3. Kademeli satis plani olustur")
    print("4. Planlari goster")
    print("5. Cikis")
    print()
    
    secim = input("Seciminiz (1-5): ").strip()
    
    if secim == "1":
        sembol = input("Hisse sembolu: ").strip()
        seviyeler = takip.destek_direnc_kademeleri(sembol)
        
        if seviyeler:
            print(f"\n{seviyeler['sembol']} - Destek/Direnc Kademeleri")
            print("=" * 60)
            print(f"Guncel Fiyat: {seviyeler['guncel']} TL")
            print(f"6 Ay Max: {seviyeler['max_6ay']} TL")
            print(f"6 Ay Min: {seviyeler['min_6ay']} TL")
            print()
            print("DIRENC KADEMELERI (Sat):")
            for d in seviyeler["direnc_kademeleri"]:
                fark = ((d - seviyeler["guncel"]) / seviyeler["guncel"]) * 100
                print(f"  {d} TL  (+{fark:.1f}%)")
            print()
            print("DESTEK KADEMELERI (Al):")
            for d in seviyeler["destek_kademeleri"]:
                fark = ((seviyeler["guncel"] - d) / seviyeler["guncel"]) * 100
                print(f"  {d} TL  (-{fark:.1f}%)")
    
    elif secim == "2":
        sembol = input("Hisse sembolu: ").strip()
        try:
            butce = float(input("Toplam butce (TL): "))
        except ValueError:
            print("Gecersiz sayi!")
            return
        
        plan = takip.kademeli_alim_plani(sembol, butce)
        
        if plan:
            print(f"\n{plan['sembol']} - KADEMELİ ALIM PLANI")
            print("=" * 60)
            print(f"Toplam Butce: {plan['toplam_butce']:,.2f} TL")
            print(f"Ortalama Maliyet: {plan['ortalama_maliyet']:.2f} TL")
            print(f"Toplam Adet: {plan['toplam_adet']}")
            print()
            print("ALIM ADIMLARI:")
            for a in plan["alimlar"]:
                print(f"\n{a['seviye']}: {a['adet']} adet @ {a['fiyat']} TL")
                print(f"  Tutar: {a['tutar']:,.2f} TL")
                print(f"  Zamanlama: {a['tetik']}")
            
            takip.plan_kaydet(sembol, plan)
            print("\nPlan kaydedildi!")
    
    elif secim == "3":
        sembol = input("Hisse sembolu: ").strip()
        try:
            adet = int(input("Mevcut adet: "))
            maliyet = float(input("Ortalama maliyet: "))
        except ValueError:
            print("Gecersiz sayi!")
            return
        
        plan = takip.kademeli_satim_plani(sembol, adet, maliyet)
        
        if plan:
            print(f"\n{plan['sembol']} - KADEMELİ SATIM PLANI")
            print("=" * 60)
            print(f"Mevcut Adet: {plan['mevcut_adet']}")
            print(f"Ortalama Maliyet: {plan['maliyet']} TL")
            print()
            print("SATIM ADIMLARI:")
            for s in plan["satimlar"]:
                print(f"\n{s['seviye']}: {s['adet']} adet @ {s['fiyat']} TL")
                print(f"  Tutar: {s['tutar']:,.2f} TL")
                print(f"  Kar: %{s.get('kar_pct', 0)}")
                print(f"  Zamanlama: {s['tetik']}")
            
            takip.plan_kaydet(sembol, plan)
            print("\nPlan kaydedildi!")
    
    elif secim == "4":
        takip.planlari_goster()


if __name__ == "__main__":
    main()
    input("\nCikmak icin Enter'a basin...")
