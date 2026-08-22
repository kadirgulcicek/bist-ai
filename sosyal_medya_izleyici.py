"""
Sosyal Medya İzleyici
- Twitter/X paylaşımlarını analiz eder
- Spekülatif dili tespit eder
- Trend analizi yapar
"""

import re
import time
from datetime import datetime, timedelta
from collections import Counter


class SosyalMedyaIzleyici:
    
    def __init__(self):
        # Spekülatif kelimeler (bunları gördüğümüzde dikkat!)
        self.spekulatif_kelimeler = [
            'sonsuz', 'uçacak', 'patlayacak', 'roket', 'moon', '100x', '10x',
            'bedava', 'garanti', 'fırsat', 'kaçırma', 'sakın satma', 'tutmaya devam',
            'hortum', 'körük', 'sihirli', 'mucize', 'asla düşmez', 'sadece yükselir'
        ]
        
        # Güvenilir finans hesapları (bu hesapların paylaşımlarına daha çok güven)
        self.guvenilir_kaynaklar = [
            'borfinans', 'fintables', 'fintwit', 'ekonomist', 'finansgundem',
            'analiz', 'uzman', 'ekonomi', 'yatirim'
        ]
    
    def hisse_hashtag_bul(self, sembol):
        """Bir hisse için olası hashtagleri üretir"""
        sembol_temiz = sembol.replace('.IS', '')
        return [sembol_temiz, f"${sembol_temiz}", f"#{sembol_temiz}"]
    
    def tweet_analiz_et(self, tweet_metni):
        """Tek bir tweeti analiz eder"""
        metin_lower = tweet_metni.lower()
        
        # Spekülatif içerik tespiti
        spek_skor = 0
        bulunan_kelimeler = []
        for kelime in self.spekulatif_kelimeler:
            if kelime in metin_lower:
                spek_skor += 1
                bulunan_kelimeler.append(kelime)
        
        # Kaynak güvenilirliği
        guvenilir_skor = 0
        for kaynak in self.guvenilir_kaynaklar:
            if kaynak in metin_lower:
                guvenilir_skor += 1
        
        # Hisse sembolü var mı?
        hisse_sayisi = len(re.findall(r'\$([A-Z]{3,5})', tweet_metni))
        
        # Etkileşim göstergeleri (gerçek hesapta bu API'den gelir)
        return {
            'spekulatif_skor': spek_skor,
            'spekulatif_kelimeler': bulunan_kelimeler,
            'guvenilir_skor': guvenilir_skor,
            'hisse_sayisi': hisse_sayisi,
            'risk_durumu': 'YÜKSEK' if spek_skor >= 2 else 'ORTA' if spek_skor == 1 else 'NORMAL'
        }
    
    def trend_analizi(self, sembol, gun_sayisi=7):
        """Bir hissenin sosyal medya trend analizini yapar"""
        # NOT: Gerçek API bağlantısı için Twitter API Key gerekir
        # Şimdilik simülasyon yapıyoruz, sonra gerçek bağlantıyı ekleyeceğiz
        
        hashtagler = self.hisse_hashtag_bul(sembol)
        
        # Simülasyon verisi (gerçekte API'den çekilecek)
        ornek_tweetler = self._simulasyon_verisi(sembol, gun_sayisi)
        
        gunluk_analiz = {}
        for gun, tweet_listesi in ornek_tweetler.items():
            toplam_spek = 0
            toplam_guvenilir = 0
            tweet_sayisi = len(tweet_listesi)
            
            for tweet in tweet_listesi:
                analiz = self.tweet_analiz_et(tweet)
                toplam_spek += analiz['spekulatif_skor']
                toplam_guvenilir += analiz['guvenilir_skor']
            
            # Trend skoru: spekülatif içerik yüksekse risk artar
            trend_skor = (toplam_spek - toplam_guvenilir) / max(tweet_sayisi, 1)
            
            gunluk_analiz[gun] = {
                'tweet_sayisi': tweet_sayisi,
                'spekulatif_skor': toplam_spek,
                'guvenilir_skor': toplam_guvenilir,
                'trend_skoru': round(trend_skor, 2),
                'risk': 'YÜKSEK' if trend_skor > 1 else 'ORTA' if trend_skor > 0 else 'NORMAL'
            }
        
        return gunluk_analiz
    
    def _simulasyon_verisi(self, sembol, gun_sayisi):
        """Test için simülasyon verisi üretir (gerçek API bağlanınca kaldırılacak)"""
        import random
        veriler = {}
        
        ornek_metinler = [
            f"${sembol} roket olacak, hedef 100 TL görünür!",
            f"${sembol} analiz: Destek kırılırsa sert düşer.",
            f"{sembol} için teknik seviyeler: 25.50 direnç, 22.80 destek.",
            f"{sembol} bedava gibi, kaçırma sakın satma!",
            f"{sembol} - Hacim artıyor, yukarı kırılım gelebilir.",
            f"${sembol} sonsuz yükselir, portföyümün yarısı burada.",
            f"{sembol} için hedef fiyat 50 TL açıklandı.",
            f"Dikkat! {sembol} manipülasyon yapılıyor olabilir.",
        ]
        
        for i in range(gun_sayisi):
            gun = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            tweet_sayisi = random.randint(5, 30)
            veriler[gun] = random.sample(ornek_metinler, min(tweet_sayisi, len(ornek_metinler)))
        
        return veriler


if __name__ == "__main__":
    print("=" * 60)
    print("📱 SOSYAL MEDYA İZLEYİCİ - TEST")
    print("=" * 60)
    
    izleyici = SosyalMedyaIzleyici()
    
    test_hisseler = ["THYAO", "GARAN", "ASELS"]
    
    for sembol in test_hisseler:
        print(f"\n🔍 {sembol} trend analizi:")
        trend = izleyici.trend_analizi(sembol)
        
        for gun, veri in list(trend.items())[:3]:
            print(f"  📅 {gun}: {veri['tweet_sayisi']} tweet | Risk: {veri['risk']}")
