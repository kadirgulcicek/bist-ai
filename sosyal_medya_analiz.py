"""
Sosyal Medya + Teknik + AI + Haber = TAM SİSTEM
Final versiyon!
"""

from sosyal_medya_izleyici import SosyalMedyaIzleyici
from forum_izleyici import ForumIzleyici
from haber_toplayici import HaberToplayici
from duygu_analizi import DuyguAnalizi
from teknik_analiz import hisse_teknik_analiz
from ai_model import BISTTahminModeli
from hisse_listesi import hisse_listesi_getir
import time


class TamYatirimSistemi:
    def __init__(self):
        print("🚀 Tam Yatırım Sistemi Başlatılıyor...\n")
        self.ai = BISTTahminModeli()
        self.ai.model_yukle()
        self.sosyal = SosyalMedyaIzleyici()
        self.forum = ForumIzleyici()
        self.haber = HaberToplayici()
        self.duygu = DuyguAnalizi()
        print("✅ Tüm modüller hazır!\n")
    
    def tek_hisse_super_analiz(self, sembol):
        """Bir hisse için 5 analizi birden yapar"""
        print(f"\n{'='*60}")
        print(f"🔍 {sembol} - SUPER ANALİZ")
        print(f"{'='*60}")
        
        sonuc = {}
        
        # 1. Teknik Analiz
        print("\n📊 Teknik analiz...")
        teknik = hisse_teknik_analiz(sembol)
        if not teknik:
            return None
        sonuc['teknik_skor'] = teknik['Skor']
        sonuc['fiyat'] = teknik['Fiyat']
        
        # 2. AI
        print("🤖 AI tahmin...")
        ai_t = self.ai.hisse_tahmin_et(sembol)
        if ai_t:
            sonuc['ai_guven'] = ai_t['Yükselme_Olasılığı']
        else:
            sonuc['ai_guven'] = 50
        
        # 3. Haber
        print("📰 Haber analizi...")
        haberler = self.haber.hisse_haber_bul(sembol, [])
        if haberler:
            h_skor = self.duygu.haber_etki_skoru(haberler)
            sonuc['haber_etki'] = h_skor['toplam_etki']
            sonuc['haber_sayisi'] = h_skor['haber_sayisi']
        else:
            sonuc['haber_etki'] = 0
            sonuc['haber_sayisi'] = 0
        
        # 4. Sosyal Medya
        print("📱 Sosyal medya analizi...")
        sosyal_trend = self.sosyal.trend_analizi(sembol.replace('.IS', ''))
        ortalama_spek = sum(d['trend_skoru'] for d in sosyal_trend.values()) / len(sosyal_trend)
        sonuc['sosyal_risk'] = ortalama_spek
        sonuc['sosyal_tweet_sayisi'] = sum(d['tweet_sayisi'] for d in sosyal_trend.values())
        
        # 5. Forum
        print("💬 Forum konsensüsü...")
        forum_kons = self.forum.sembol_konsensusu(sembol.replace('.IS', ''))
        if forum_kons:
            sonuc['forum_skoru'] = forum_kons['konsensus_skoru']
        else:
            sonuc['forum_skoru'] = 0
        
        # SUPER SKOR HESAPLA
        # Ağırlıklar:
        # Teknik: %30 (kanıtlanmış yöntem)
        # AI: %30 (makine öğrenmesi)
        # Haber: %20 (güncel bilgi)
        # Sosyal: %10 (manipülasyon uyarısı)
        # Forum: %10 (genel kanı)
        
        super_skor = (
            sonuc['teknik_skor'] * 1.5 +        # -7.5 ile +7.5
            (sonuc['ai_guven'] - 50) / 5 +      # -10 ile +10
            sonuc['haber_etki'] * 3 +           # -9 ile +9
            -sonuc['sosyal_risk'] * 2 +          # Spekülasyon varsa negatif
            sonuc['forum_skoru'] / 10            # -10 ile +10
        )
        
        sonuc['super_skor'] = round(super_skor, 2)
        
        # Final Karar
        if super_skor >= 8:
            sonuc['karar'] = '🚀🚀 ACİL AL'
            sonuc['renk'] = '🟢🟢'
        elif super_skor >= 4:
            sonuc['karar'] = '✅ GÜÇLÜ AL'
            sonuc['renk'] = '🟢'
        elif super_skor >= 1:
            sonuc['karar'] = '🟢 AL'
            sonuc['renk'] = ' '
        elif super_skor <= -8:
            sonuc['karar'] = ' ⛔ ACİL SAT'
            sonuc['renk'] = '🔴🔴'
        elif super_skor <= -4:
            sonuc['karar'] = '  GÜÇLÜ SAT'
            sonuc['renk'] = '🔴'
        elif super_skor <= -1:
            sonuc['karar'] = '🔴 SAT'
            sonuc['renk'] = '🔴'
        else:
            sonuc['karar'] = '⏸️ BEKLE'
            sonuc['renk'] = '⚪'
        
        return sonuc
    
    def rapor_yazdir(self, sonuc):
        """Sonucu güzel formatta yazdırır"""
        if not sonuc:
            return
        
        print(f"\n{sonuc['renk']} {sonuc['karar']}")
        print(f"💰 Fiyat: {sonuc['fiyat']} TL")
        print(f"📊 Super Skor: {sonuc['super_skor']:+.2f}")
        print(f"\n📋 Detaylar:")
        print(f"   Teknik Analiz: {sonuc['teknik_skor']:+d}")
        print(f"   AI Güveni: %{sonuc['ai_guven']:.0f}")
        print(f"   Haber Etkisi: {sonuc['haber_etki']:+.2f} ({sonuc['haber_sayisi']} haber)")
        print(f"   Sosyal Medya: {sonuc['sosyal_tweet_sayisi']} tweet, Risk: {sonuc['sosyal_risk']:.2f}")
        print(f"   Forum Konsensüs: {sonuc['forum_skoru']:+.1f}")


if __name__ == "__main__":
    sistem = TamYatirimSistemi()
    
    # En çok takip edilen 5 hisseyi analiz et
    test_hisseler = ["THYAO.IS", "GARAN.IS", "ASELS.IS", "TUPRS.IS", "EREGL.IS"]
    
    tum_sonuclar = []
    for sembol in test_hisseler:
        sonuc = sistem.tek_hisse_super_analiz(sembol)
        if sonuc:
            tum_sonuclar.append((sembol, sonuc))
            sistem.rapor_yazdir(sonuc)
        time.sleep(2)
    
    # Final sıralama
    print("\n\n" + "="*70)
    print("🏆 FİNAL SIRALAMA")
    print("="*70)
    
    sirali = sorted(tum_sonuclar, key=lambda x: x[1]['super_skor'], reverse=True)
    
    for sembol, s in sirali:
        print(f"  {s['karar']:25} {sembol:12} {s['fiyat']:>8} TL  Skor: {s['super_skor']:+5.2f}")
