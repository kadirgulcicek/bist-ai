"""
BIST AI - Portföy Takip Sistemi
Hisselerinizi kaydedin, kâr/zararınızı takip edin
"""

import json
import os
from datetime import datetime


class Portfoy:
    def __init__(self, dosya="portfoy.json"):
        self.dosya = dosya
        self.hisseler = self.yukle()
    
    def yukle(self):
        """Portföyü dosyadan yükler"""
        if os.path.exists(self.dosya):
            with open(self.dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def kaydet(self):
        """Portföyü dosyaya kaydeder"""
        with open(self.dosya, "w", encoding="utf-8") as f:
            json.dump(self.hisseler, f, indent=2, ensure_ascii=False)
    
    def hisse_ekle(self, sembol, adet, alis_fiyati):
        """Yeni hisse ekler"""
        sembol = sembol.upper().replace(".IS", "")
        
        # Aynı hisseden varsa ortalama al
        for h in self.hisseler:
            if h["sembol"] == sembol:
                toplam_adet = h["adet"] + adet
                yeni_ortalama = ((h["adet"] * h["alis_fiyati"]) + 
                                (adet * alis_fiyati)) / toplam_adet
                h["adet"] = toplam_adet
                h["alis_fiyati"] = round(yeni_ortalama, 2)
                self.kaydet()
                print(f"✅ {sembol}: {toplam_adet} adet, ortalama {yeni_ortalama:.2f} TL")
                return
        
        # Yeni hisse
        self.hisseler.append({
            "sembol": sembol,
            "adet": adet,
            "alis_fiyati": alis_fiyati,
            "ekleme_tarihi": datetime.now().strftime("%Y-%m-%d")
        })
        self.kaydet()
        print(f"✅ {sembol}: {adet} adet, {alis_fiyati} TL'den eklendi")
    
    def hisse_sil(self, sembol):
        """Hisse siler (sattığınızda)"""
        sembol = sembol.upper()
        self.hisseler = [h for h in self.hisseler if h["sembol"] != sembol]
        self.kaydet()
        print(f"✅ {sembol} portföyden çıkarıldı")
    
    def liste_goster(self):
        """Portföyü gösterir"""
        if not self.hisseler:
            print("  Portföy boş!")
            return
        
        print("\n" + "=" * 50)
        print("💼 PORTFÖY LİSTESİ")
        print("=" * 50)
        print(f"{'Sembol':<8}{'Adet':<8}{'Alış':<10}{'Tarih':<12}")
        print("-" * 50)
        for h in self.hisseler:
            print(f"{h['sembol']:<8}{h['adet']:<8}{h['alis_fiyati']:<10}{h['ekleme_tarihi']:<12}")
        print("=" * 50)


# Basit kullanım için örnek menü
if __name__ == "__main__":
    p = Portfoy()
    
    print("=" * 50)
    print("💼 PORTFÖY YÖNETİMİ")
    print("=" * 50)
    print("1. Hisse Ekle")
    print("2. Hisse Sil")
    print("3. Portföyü Göster")
    print("4. Çıkış")
    
    while True:
        secim = input("\nSeçiminiz (1-4): ").strip()
        
        if secim == "1":
            sembol = input("Hisse sembolü (örn: THYAO): ").strip()
            adet = int(input("Kaç adet: "))
            fiyat = float(input("Alış fiyatı (TL): "))
            p.hisse_ekle(sembol, adet, fiyat)
        
        elif secim == "2":
            sembol = input("Silinecek hisse: ").strip()
            p.hisse_sil(sembol)
        
        elif secim == "3":
            p.liste_goster()
        
        elif secim == "4":
            print("👋 Görüşürüz!")
            break
