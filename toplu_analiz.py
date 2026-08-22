"""
Tüm BIST Hisseleri İçin Toplu Teknik Analiz
- Her hisse için skor hesaplar
- Sıralı liste çıkarır
- Al/Sat önerilerini gösterir
"""

from teknik_analiz import hisse_teknik_analiz
from hisse_listesi import hisse_listesi_getir
import pandas as pd
import time

def toplu_analiz_yap():
    hisseler = hisse_listesi_getir()
    sonuclar = []
    
    print(f"📊 {len(hisseler)} hisse için teknik analiz başlıyor...\n")
    
    for i, sembol in enumerate(hisseler, 1):
        print(f"[{i}/{len(hisseler)}] {sembol}...", end=" ")
        try:
            sonuc = hisse_teknik_analiz(sembol)
            if sonuc:
                sonuclar.append(sonuc)
                print(f"{sonuc['Karar']} (Skor: {sonuc['Skor']})")
            else:
                print("⚠️ Veri yetersiz")
        except Exception as e:
            print(f"  Hata")
        
        time.sleep(0.3)
    
    return sonuclar


def sonuclari_goster(sonuclar):
    """Sonuçları güzel formatta gösterir"""
    df = pd.DataFrame(sonuclar)
    
    print("\n" + "=" * 70)
    print("🎯 AL SİNYALLERİ (Skor: +2 ve üstü)")
    print("=" * 70)
    al_liste = df[df['Skor'] >= 2].sort_values('Skor', ascending=False)
    if len(al_liste) > 0:
        print(al_liste[['Sembol', 'Fiyat', 'RSI', 'Skor', 'Karar']].to_string(index=False))
    else:
        print("Şu anda güçlü al sinyali veren hisse yok.")
    
    print("\n" + "=" * 70)
    print("⛔ SAT SİNYALLERİ (Skor: -2 ve altı)")
    print("=" * 70)
    sat_liste = df[df['Skor'] <= -2].sort_values('Skor', ascending=True)
    if len(sat_liste) > 0:
        print(sat_liste[['Sembol', 'Fiyat', 'RSI', 'Skor', 'Karar']].to_string(index=False))
    else:
        print("Şu anda güçlü sat sinyali veren hisse yok.")
    
    print("\n" + "=" * 70)
    print("⏸️ BEKLE (Skor: -1, 0, +1)")
    print("=" * 70)
    bekle_liste = df[df['Skor'].between(-1, 1)]
    print(f"   {len(bekle_liste)} hisse nötr bölgede")


if __name__ == "__main__":
    sonuclar = toplu_analiz_yap()
    
    if sonuclar:
        sonuclari_goster(sonuclar)
        
        # Excel'e kaydet
        df = pd.DataFrame(sonuclar)
        dosya = f"teknik_analiz_sonuclar.xlsx"
        df.to_excel(dosya, index=False)
        print(f"\n💾 Sonuçlar '{dosya}' dosyasına kaydedildi.")
