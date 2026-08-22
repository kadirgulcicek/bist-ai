"""
TAM ANALİZ SİSTEMİ
Teknik Analiz + AI Tahmin + Haber Duygu Analizi
"""

from teknik_analiz import hisse_teknik_analiz
from ai_model import BISTTahminModeli
from haber_toplayici import HaberToplayici
from duygu_analizi import DuyguAnalizi
from hisse_listesi import hisse_listesi_getir
import time


class TamAnalizSistemi:
    def __init__(self):
        self.ai = BISTTahminModeli()
        self.ai.model_yukle()  # Modeli yükle
        self.haber = HaberToplayici()
        self.duygu = DuyguAnalizi()
    
    def tek_hise_tam_analiz(self, sembol):
        """Bir hisse için TÜM analizleri yapar"""
        print(f"\n🔍 {sembol} tam analiz ediliyor...")
        
        sonuc = {'Sembol': sembol.replace('.IS', '')}
        
        # 1. Teknik Analiz
        teknik = hisse_teknik_analiz(sembol)
        if not teknik:
            return None
        
        sonuc['Fiyat'] = teknik['Fiyat']
        sonuc['Teknik_Skor'] = teknik['Skor']
        sonuc['Teknik_Karar'] = teknik['Karar']
        sonuc['RSI'] = teknik['RSI']
        sonuc['Destek'] = teknik['Destek']
        sonuc['Direnç'] = teknik['Direnç']
        
        # 2. AI Tahmini
        ai_tahmin = self.ai.hisse_tahmin_et(sembol)
        if ai_tahmin:
            sonuc['AI_Tahmin'] = ai_tahmin['Tahmin']
            sonuc['AI_Güven'] = ai_tahmin['Yükselme_Olasılığı']
        else:
            sonuc['AI_Tahmin'] = '❓'
            sonuc['AI_Güven'] = 50
        
        # 3. Haber Analizi
        print(f"   📰 Haberler aranıyor...")
        hisse_haberleri = self.haber.hisse_haber_bul(sembol, [])
        if hisse_haberleri:
            haber_skor = self.duygu.haber_etki_skoru(hisse_haberleri)
            sonuc['Haber_Etki'] = haber_skor['toplam_etki']
            sonuc['Pozitif_Haber'] = haber_skor['pozitif_haber']
            sonuc['Negatif_Haber'] = haber_skor['negatif_haber']
            sonuc['Haber_Sayısı'] = haber_skor['haber_sayisi']
        else:
            sonuc['Haber_Etki'] = 0
            sonuc['Pozitif_Haber'] = 0
            sonuc['Negatif_Haber'] = 0
            sonuc['Haber_Sayısı'] = 0
        
        # 4. Birleşik Final Skoru
        # Teknik: -5 ile +5
        # AI: %0-100, %50 nötr
        # Haber: -3 ile +3 arası normalize
        
        teknik_katki = teknik['Skor'] * 1.5  # Ağırlık
        ai_katki = (sonuc['AI_Güven'] - 50) / 5
        haber_katki = sonuc['Haber_Etki'] * 2
        
        final_skor = teknik_katki + ai_katki + haber_katki
        sonuc['Final_Skor'] = round(final_skor, 2)
        
        # Final Karar
        if final_skor >= 5:
            sonuc['Final_Karar'] = '🚀 ÇOK GÜÇLÜ AL'
        elif final_skor >= 2.5:
            sonuc['Final_Karar'] = '✅ GÜÇLÜ AL'
        elif final_skor >= 1:
            sonuc['Final_Karar'] = '🟢 AL'
        elif final_skor <= -5:
            sonuc['Final_Karar'] = '⛔  ÇOK GÜÇLÜ SAT'
        elif final_skor <= -2.5:
            sonuc['Final_Karar'] = '⛔ GÜÇLÜ SAT'
        elif final_skor <= -1:
            sonuc['Final_Karar'] = '🔴 SAT'
        else:
            sonuc['Final_Karar'] = '⏸️ BEKLE'
        
        return sonuc
    
    def toplu_tam_analiz(self, sembol_listesi=None, max_hisse=15):
        """Birden fazla hisseyi tam analiz eder"""
        if sembol_listesi is None:
            sembol_listesi = hisse_listesi_getir()[:max_hisse]
        
        print("=" * 70)
        print("🎯 TAM ANALİZ SİSTEMİ - TEKNİK + AI + HABER")
        print("=" * 70)
        
        sonuclar = []
        
        for i, sembol in enumerate(sembol_listesi, 1):
            print(f"\n[{i}/{len(sembol_listesi)}] {sembol}")
            sonuc = self.tek_hise_tam_analiz(sembol)
            if sonuc:
                sonuclar.append(sonuc)
                print(f"   💰 Fiyat: {sonuc['Fiyat']} TL")
                print(f"   📊 Teknik: {sonuc['Teknik_Karar']} (Skor: {sonuc['Teknik_Skor']:+d})")
                print(f"   🤖 AI: {sonuc['AI_Tahmin']} (Güven: %{sonuc['AI_Güven']:.0f})")
                print(f"   📰 Haber Etkisi: {sonuc['Haber_Etki']:+.2f} ({sonuc['Haber_Sayısı']} haber)")
                print(f"   🎯 FİNAL: {sonuc['Final_Karar']} (Skor: {sonuc['Final_Skor']:+.2f})")
            time.sleep(1)
        
        return sonuclar


if __name__ == "__main__":
    sistem = TamAnalizSistemi()
    
    # Popüler hisseleri analiz et
    test = ["THYAO.IS", "GARAN.IS", "ASELS.IS", "SISE.IS", "TUPRS.IS",
            "EREGL.IS", "KCHOL.IS", "PETKM.IS", "BIMAS.IS", "TAVHL.IS"]
    
    sonuclar = sistem.toplu_tam_analiz(test)
    
    # Final sıralama
    if sonuclar:
        print("\n" + "=" * 70)
        print("🏆 FİNAL SIRALAMA (En İyiden En Kötüye)")
        print("=" * 70)
        
        sirali = sorted(sonuclar, key=lambda x: x['Final_Skor'], reverse=True)
        
        for s in sirali:
            print(f"  {s['Final_Karar']:25} {s['Sembol']:10} Skor: {s['Final_Skor']:+5.2f}")
        
        # Excel kaydet
        import pandas as pd
        df = pd.DataFrame(sonuclar)
        df.to_excel("tam_analiz_sonuclar.xlsx", index=False)
        print(f"\n💾 Sonuçlar 'tam_analiz_sonuclar.xlsx' dosyasına kaydedildi.")
