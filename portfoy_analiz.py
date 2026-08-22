"""
Portföy Analiz - Kâr/Zarar Hesaplama ve Raporlama
"""

import yfinance as yf
from portfoy import Portfoy
from datetime import datetime


def portfoy_analiz_yap():
    """Portföyü analiz eder"""
    p = Portfoy()
    
    if not p.hisseler:
        print("📭 Portföy boş! Önce hisse ekleyin.")
        return None
    
    print("\n🔍 Portföy analiz ediliyor...\n")
    
    sonuclar = []
    toplam_maliyet = 0
    toplam_deger = 0
    
    for h in p.hisseler:
        sembol = h["sembol"]
        sembol_yf = f"{sembol}.IS"
        
        try:
            ticker = yf.Ticker(sembol_yf)
            veri = ticker.history(period="5d")
            
            if len(veri) < 1:
                print(f"⚠️ {sembol}: Veri alınamadı")
                continue
            
            guncel_fiyat = veri['Close'].iloc[-1]
            
            maliyet = h["adet"] * h["alis_fiyati"]
            deger = h["adet"] * guncel_fiyat
            kar = deger - maliyet
            kar_yuzde = (kar / maliyet) * 100 if maliyet > 0 else 0
            
            toplam_maliyet += maliyet
            toplam_deger += deger
            
            sonuc = {
                "sembol": sembol,
                "adet": h["adet"],
                "alis": h["alis_fiyati"],
                "guncel": round(guncel_fiyat, 2),
                "maliyet": round(maliyet, 2),
                "deger": round(deger, 2),
                "kar_tl": round(kar, 2),
                "kar_yuzde": round(kar_yuzde, 2)
            }
            sonuclar.append(sonuc)
            
            emoji = "✅" if kar >= 0 else " "
            print(f"{emoji} {sembol}: {h['adet']} adet | "
                  f"{h['alis_fiyati']:.2f} → {guncel_fiyat:.2f} | "
                  f"Kâr: {kar:+.2f} TL ({kar_yuzde:+.2f}%)")
        
        except Exception as e:
            print(f"❌ {sembol}: Hata - {str(e)[:30]}")
    
    # Özet
    toplam_kar = toplam_deger - toplam_maliyet
    toplam_kar_yuzde = (toplam_kar / toplam_maliyet * 100) if toplam_maliyet > 0 else 0
    
    print("\n" + "=" * 50)
    print("📊 PORTFÖY ÖZETİ")
    print("=" * 50)
    print(f"💰 Toplam Maliyet: {toplam_maliyet:,.2f} TL")
    print(f"📈 Toplam Değer:   {toplam_deger:,.2f} TL")
    print(f"{'✅' if toplam_kar >= 0 else '📉'} Toplam Kâr:     "
          f"{toplam_kar:+,.2f} TL ({toplam_kar_yuzde:+.2f}%)")
    print("=" * 50)
    
    # En iyiler ve en kötüler
    if sonuclar:
        sirali = sorted(sonuclar, key=lambda x: x["kar_yuzde"], reverse=True)
        
        print("\n🏆 En İyiler:")
        for s in sirali[:3]:
            if s["kar_yuzde"] > 0:
                print(f"   ✅ {s['sembol']}: +{s['kar_yuzde']:.2f}% ({s['kar_tl']:+.0f} TL)")
        
        print("\n📉 En Kötüler:")
        for s in sirali[-3:]:
            if s["kar_yuzde"] < 0:
                print(f"   ❌ {s['sembol']}: {s['kar_yuzde']:.2f}% ({s['kar_tl']:.0f} TL)")
    
    return {
        "sonuclar": sonuclar,
        "toplam_maliyet": toplam_maliyet,
        "toplam_deger": toplam_deger,
        "toplam_kar": toplam_kar,
        "toplam_kar_yuzde": toplam_kar_yuzde
    }


if __name__ == "__main__":
    portfoy_analiz_yap()
    input("\nÇıkmak için Enter'a basın...")
