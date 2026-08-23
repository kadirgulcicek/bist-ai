"""
Eğitim Modu (Simulator)
Sanal parayla gercek hisse fiyatlariyla pratik
Hata yapmadan ogrenme!
"""

import yfinance as yf
import json
import os
from datetime import datetime


class EgitimModu:
    def __init__(self, baslangic_sermaye=100000):
        self.dosya = "egitim_portfoy.json"
        self.veriler = self.yukle()
        
        if not self.veriler:
            self.veriler = {
                "baslangic": baslangic_sermaye,
                "nakit": baslangic_sermaye,
                "pozisyonlar": {},
                "islem_gecmisi": [],
                "olusturma": datetime.now().strftime("%Y-%m-%d")
            }
            self.kaydet()
    
    def yukle(self):
        if os.path.exists(self.dosya):
            with open(self.dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def kaydet(self):
        with open(self.dosya, "w", encoding="utf-8") as f:
            json.dump(self.veriler, f, indent=2, ensure_ascii=False)
    
    def fiyat_al(self, sembol):
        """Guncel fiyat"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="5d")
            if veri is None or len(veri) < 1:
                return None
            return float(veri['Close'].iloc[-1])
        except:
            return None
    
    def alis_yap(self, sembol, adet):
        """Sanal alim"""
        sembol = sembol.upper()
        fiyat = self.fiyat_al(sembol)
        
        if fiyat is None or fiyat <= 0:
            print(f"Fiyat alinamadi: {sembol}")
            return False
        
        tutar = adet * fiyat
        komisyon = tutar * 0.001  # %0.1 komisyon
        toplam = tutar + komisyon
        
        if toplam > self.veriler["nakit"]:
            print(f"Yetersiz bakiye! Gereken: {toplam:.2f} TL, Mevcut: {self.veriler['nakit']:.2f} TL")
            return False
        
        # Al
        if sembol in self.veriler["pozisyonlar"]:
            # Mevcut pozisyona ekle (ortalama fiyat)
            mevcut = self.veriler["pozisyonlar"][sembol]
            toplam_adet = mevcut["adet"] + adet
            yeni_ortalama = ((mevcut["adet"] * mevcut["alis_fiyati"]) + (adet * fiyat)) / toplam_adet
            
            mevcut["adet"] = toplam_adet
            mevcut["alis_fiyati"] = round(yeni_ortalama, 2)
        else:
            self.veriler["pozisyonlar"][sembol] = {
                "adet": adet,
                "alis_fiyati": round(fiyat, 2)
            }
        
        self.veriler["nakit"] -= toplam
        
        # Islem kaydi
        self.veriler["islem_gecmisi"].append({
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "sembol": sembol,
            "tip": "ALIS",
            "adet": adet,
            "fiyat": round(fiyat, 2),
            "tutar": round(tutar, 2),
            "komisyon": round(komisyon, 2)
        })
        
        self.kaydet()
        print(f"✅ ALIS: {adet} adet {sembol} @ {fiyat:.2f} TL = {tutar:.2f} TL")
        return True
    
    def satis_yap(self, sembol, adet):
        """Sanal satis"""
        sembol = sembol.upper()
        
        if sembol not in self.veriler["pozisyonlar"]:
            print(f"Portfoyde {sembol} yok!")
            return False
        
        pozisyon = self.veriler["pozisyonlar"][sembol]
        
        if adet > pozisyon["adet"]:
            print(f"Yetersiz adet! Mevcut: {pozisyon['adet']}, Sattiginiz: {adet}")
            return False
        
        fiyat = self.fiyat_al(sembol)
        if fiyat is None or fiyat <= 0:
            print(f"Fiyat alinamadi")
            return False
        
        tutar = adet * fiyat
        komisyon = tutar * 0.001
        net = tutar - komisyon
        
        alis_tutar = adet * pozisyon["alis_fiyati"]
        kar = net - alis_tutar
        kar_yuzde = (kar / alis_tutar) * 100 if alis_tutar > 0 else 0
        
        # Sat
        self.veriler["nakit"] += net
        pozisyon["adet"] -= adet
        
        if pozisyon["adet"] == 0:
            del self.veriler["pozisyonlar"][sembol]
        
        self.veriler["islem_gecmisi"].append({
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "sembol": sembol,
            "tip": "SATIS",
            "adet": adet,
            "fiyat": round(fiyat, 2),
            "tutar": round(tutar, 2),
            "komisyon": round(komisyon, 2),
            "kar": round(kar, 2),
            "kar_yuzde": round(kar_yuzde, 2)
        })
        
        self.kaydet()
        
        emoji = "✅" if kar >= 0 else "📉"
        print(f"{emoji} SATIS: {adet} adet {sembol} @ {fiyat:.2f} TL")
        print(f"   Kar/Zarar: {kar:+.2f} TL ({kar_yuzde:+.2f}%)")
        return True
    
    def portfoy_durumu(self):
        """Guncel portfoy durumu"""
        toplam_deger = self.veriler["nakit"]
        pozisyon_detay = []
        
        for sembol, poz in self.veriler["pozisyonlar"].items():
            fiyat = self.fiyat_al(sembol)
            if fiyat and fiyat > 0:
                deger = poz["adet"] * fiyat
                maliyet = poz["adet"] * poz["alis_fiyati"]
                kar = deger - maliyet
                kar_yuzde = (kar / maliyet) * 100 if maliyet > 0 else 0
                
                toplam_deger += deger
                
                pozisyon_detay.append({
                    "sembol": sembol,
                    "adet": poz["adet"],
                    "alis": poz["alis_fiyati"],
                    "guncel": round(fiyat, 2),
                    "deger": round(deger, 2),
                    "kar": round(kar, 2),
                    "kar_yuzde": round(kar_yuzde, 2)
                })
        
        baslangic = self.veriler["baslangic"]
        toplam_kar = toplam_deger - baslangic
        toplam_kar_yuzde = (toplam_kar / baslangic) * 100
        
        return {
            "nakit": self.veriler["nakit"],
            "toplam_deger": toplam_deger,
            "toplam_kar": toplam_kar,
            "toplam_kar_yuzde": toplam_kar_yuzde,
            "pozisyonlar": sorted(pozisyon_detay, key=lambda x: x["deger"], reverse=True)
        }
    
    def portfoy_yazdir(self):
        """Portfoyu goster"""
        durum = self.portfoy_durumu()
        
        print()
        print("=" * 60)
        print("SANAL PORTOFY (Egitim Modu)")
        print("=" * 60)
        print(f"Baslangic: {self.veriler['baslangic']:,.2f} TL")
        print(f"Nakit: {durum['nakit']:,.2f} TL")
        print(f"Toplam Deger: {durum['toplam_deger']:,.2f} TL")
        
        emoji = "✅" if durum['toplam_kar'] >= 0 else "📉"
        print(f"{emoji} Toplam Kar: {durum['toplam_kar']:+,.2f} TL ({durum['toplam_kar_yuzde']:+.2f}%)")
        print("=" * 60)
        
        if durum["pozisyonlar"]:
            print(f"\n{'Hisse':<8}{'Adet':<7}{'Alis':<10}{'Guncel':<10}{'Kar %':<10}")
            print("-" * 60)
            for p in durum["pozisyonlar"]:
                print(f"{p['sembol']:<8}{p['adet']:<7}{p['alis']:<10}{p['guncel']:<10}{p['kar_yuzde']:+.2f}")
        
        print("=" * 60)
    
    def sifirla(self):
        """Portfoyu sifirlar"""
        self.veriler = {
            "baslangic": self.veriler["baslangic"],
            "nakit": self.veriler["baslangic"],
            "pozisyonlar": {},
            "islem_gecmisi": [],
            "olusturma": datetime.now().strftime("%Y-%m-%d")
        }
        self.kaydet()
        print("✅ Portfoy sifirlandi!")


# ============================================
# MENU
# ============================================
def main():
    egitim = EgitimModu(100000)
    
    while True:
        print()
        print("=" * 60)
        print("EGITIM MODU - Sanal Portfoy Simulator")
        print("=" * 60)
        print("1. Hisse al")
        print("2. Hisse sat")
        print("3. Portfoyu gor")
        print("4. Portfoyu sifirla")
        print("5. Cikis")
        print()
        
        secim = input("Seciminiz (1-5): ").strip()
        
        if secim == "1":
            sembol = input("Hisse sembolu (orn: THYAO): ").strip()
            try:
                adet = int(input("Kac adet: "))
                if adet <= 0:
                    print("Gecersiz adet!")
                    continue
                egitim.alis_yap(sembol, adet)
            except ValueError:
                print("Gecersiz sayi!")
        
        elif secim == "2":
            sembol = input("Hisse sembolu: ").strip()
            try:
                adet = int(input("Kac adet: "))
                if adet <= 0:
                    print("Gecersiz adet!")
                    continue
                egitim.satis_yap(sembol, adet)
            except ValueError:
                print("Gecersiz sayi!")
        
        elif secim == "3":
            egitim.portfoy_yazdir()
        
        elif secim == "4":
            onay = input("Tum portfoy silinecek. Emin misiniz? (e/h): ").strip().lower()
            if onay == "e":
                egitim.sifirla()
        
        elif secim == "5":
            print("Gorusuruz!")
            break
        
        else:
            print("Gecersiz secim!")


if __name__ == "__main__":
    main()
    input("\nCikmak icin Enter'a basin...")
