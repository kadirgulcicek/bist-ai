"""
Teknik Analiz + AI Tahmin Birleşik Rapor
- İki sistemi birleştirip daha güvenilir karar üretir
"""

from teknik_analiz import hisse_teknik_analiz
from ai_model import BISTTahminModeli
from hisse_listesi import hisse_listesi_getir
import time

def birlesik_sinyal(teknik_skor, ai_yukselme_olasilik):
    """Teknik analiz ve AI'ı birleştirir"""
    # Skorları normalize et (-5 ile +5 arası)
    teknik_normalized = teknik_skor
    ai_normalized = (ai_yukselme_olasilik - 50) / 10  # %50'den fark
    
    birlesik_skor = teknik_normalized + ai_normalized
    
    if birlesik_skor >= 4:
        return "✅✅ ÇOK GÜÇLÜ AL"
    elif birlesik_skor >= 2:
        return "✅ GÜÇLÜ AL"
    elif birlesik_skor >= 0.5:
        return "🟢 AL"
    elif birlesik_skor <= -4:
        return "⛔⛔ ÇOK GÜÇLÜ SAT"
    elif birlesik_skor <= -2:
        return "⛔ GÜÇLÜ SAT"
    elif birlesik_skor <= -0.5:
        return "🔴 SAT"
    else:
        return "⏸️ BEKLE"


def birlesik_tarama():
    """Tüm hisseleri hem teknik hem AI ile analiz eder"""
    hisseler = hisse_listesi_getir()
    
    # Model yükle veya eğit
    ai = BISTTahminModeli()
    if not ai.model_yukle():
        print("⚠️ Model yok. Eğitim başlıyor...")
        ai.model_egit(hisseler[:30])
    
    print(f"\n  {len(hisseler)} hisse için BİRLEŞİK analiz başlıyor...\n")
    print("=" * 70)
    
    sonuclar = []
    
    for i, sembol in enumerate(hisseler, 1):
        print(f"[{i}/{len(hisseler)}] {sembol}...", end=" ")
        
        try:
            # Teknik analiz
            teknik = hisse_teknik_analiz(sembol)
            if not teknik:
                print("⚠️ Teknik analiz yapılamadı")
                continue
            
            # AI tahmin
            ai_tahmin = ai.hisse_tahmin_et(sembol)
            if not ai_tahmin:
                print("⚠️ AI tahmin yapılamadı")
                continue
            
            # Birleşik karar
            karar = birlesik_sinyal(teknik['Skor'], ai_tahmin['Yükselme_Olasılığı'])
            
            sonuc = {
                'Sembol': sembol.replace('.IS', ''),
                'Fiyat': teknik['Fiyat'],
                'Teknik Skor': teknik['Skor'],
                'AI Güven': ai_tahmin['Yükselme_Olasılığı'],
                'Karar': karar
            }
            sonuclar.append(sonuc)
            
            print(f"{karar}  (T:{teknik['Skor']:+d} | AI:%{ai_tahmin['Yükselme_Olasılığı']:.0f})")
            
        except Exception as e:
            print(f"❌ Hata")
        
        time.sleep(0.3)
    
    # Özet
    if sonuclar:
        print("\n" + "=" * 70)
        print("🏆 EN İYİ AL FIRSATLARI (Birleşik Skor)")
        print("=" * 70)
        
        # Skor hesapla
        for s in sonuclar:
            s['Birleşik Skor'] = s['Teknik Skor'] + (s['AI Güven'] - 50) / 10
        
        sirali = sorted(sonuclar, key=lambda x: x['Birleşik Skor'], reverse=True)
        
        for s in sirali[:10]:
            print(f"  {s['Karar']:30} {s['Sembol']:10} {s['Fiyat']:>8} TL")
    
    return sonuclar


if __name__ == "__main__":
    sonuclar = birlesik_tarama()
    
    # Excel'e kaydet
    if sonuclar:
        import pandas as pd
        df = pd.DataFrame(sonuclar)
        df.to_excel("birlesik_analiz_sonuclar.xlsx", index=False)
        print(f"\n💾 Sonuçlar 'birlesik_analiz_sonuclar.xlsx' dosyasına kaydedildi.")
