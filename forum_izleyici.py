"""
Finans Forumları İzleyici
- Ekşi, Kripto Forum, Ekonomist Forum vb.
- Hisse ile ilgili tartışmaları takip eder
- Genel kanı (consensus) hesaplar
"""

import re
from collections import Counter
from datetime import datetime


class ForumIzleyici:
    
    def __init__(self):
        self.forum_kaynaklari = {
            'Eksi Sözlük': 'eksisozluk.com',
            'Finans Forum': 'finans.forum',
            'Borsa Forum': 'borsaforum.com',
        }
        
        # Olumlu/Olumsuz ifadeler
        self.olumlu_ifadeler = [
            'tutmaya devam', 'güzel', 'iyi', 'başarılı', 'yükselir',
            'alın', 'topla', 'fırsat', 'potansiyel', 'güçlü', 'kârlı'
        ]
        
        self.olumsuz_ifadeler = [
            'sat', 'satın', 'düşer', 'kaybettirir', 'riskli', 'kötü',
            'uzak dur', 'temkinli', 'dibe gider', 'batık', 'zararda'
        ]
    
    def yorum_analiz_et(self, yorum_metni):
        """Tek bir yorumu analiz eder"""
        metin_lower = yorum_metni.lower()
        
        olumlu_skor = sum(1 for k in self.olumlu_ifadeler if k in metin_lower)
        olumsuz_skor = sum(1 for k in self.olumsuz_ifadeler if k in metin_lower)
        
        if olumlu_skor > olumsuz_skor:
            sentiment = 'OLUMLU'
        elif olumsuz_skor > olumlu_skor:
            sentiment = 'OLUMSUZ'
        else:
            sentiment = 'NÖTR'
        
        return {
            'sentiment': sentiment,
            'olumlu': olumlu_skor,
            'olumsuz': olumsuz_skor,
            'skor': olumlu_skor - olumsuz_skor
        }
    
    def sembol_konsensusu(self, sembol, yorum_listesi=None):
        """Bir sembol için forum konsensüsü"""
        if yorum_listesi is None:
            # Simülasyon verisi
            yorum_listesi = self._simulasyon_yorumlar(sembol)
        
        toplam_olumlu = 0
        toplam_olumsuz = 0
        toplam_notr = 0
        detaylar = []
        
        for yorum in yorum_listesi:
            analiz = self.yorum_analiz_et(yorum)
            detaylar.append(analiz)
            
            if analiz['sentiment'] == 'OLUMLU':
                toplam_olumlu += 1
            elif analiz['sentiment'] == 'OLUMSUZ':
                toplam_olumsuz += 1
            else:
                toplam_notr += 1
        
        toplam = len(yorum_listesi)
        if toplam == 0:
            return None
        
        # Konsensüs skoru: -100 ile +100 arası
        konsensus_skor = ((toplam_olumlu - toplam_olumsuz) / toplam) * 100
        
        if konsensus_skor > 30:
            durum = '🚀 ÇOK OLUMLU'
        elif konsensus_skor > 10:
            durum = '🟢 OLUMLU'
        elif konsensus_skor < -30:
            durum = '📉 ÇOK OLUMSUZ'
        elif konsensus_skor < -10:
            durum = '🔴 OLUMSUZ'
        else:
            durum = '⚪ KARARSIZ'
        
        return {
            'sembol': sembol,
            'toplam_yorum': toplam,
            'olumlu': toplam_olumlu,
            'olumsuz': toplam_olumsuz,
            'notr': toplam_notr,
            'konsensus_skoru': round(konsensus_skor, 1),
            'durum': durum
        }
    
    def _simulasyon_yorumlar(self, sembol):
        """Test için simülasyon yorum verisi"""
        ornekler = [
            f"{sembol} tutmaya devam ediyorum, hedef yukarı.",
            f"{sembol} güzel hareket yapıyor.",
            f"Bu seviyeden {sembol} alınır, fırsat kaçmaz.",
            f"{sembol} sat sat sat, daha çok düşer.",
            f"Temkinli yaklaşmak lazım {sembol} konusunda.",
            f"{sembol} dipte, alım fırsatı olabilir.",
            f"Bu hisse riskli, uzak durun derim.",
            f"{sembol} için beklemedeyim, kararsızım.",
            f"{sembol} yükselir, potansiyel var.",
            f"{sembol} batık bir hisse, kaybettirir.",
        ]
        return ornekler


if __name__ == "__main__":
    print("=" * 60)
    print("💬 FORUM İZLEYİCİ - TEST")
    print("=" * 60)
    
    izleyici = ForumIzleyici()
    
    for sembol in ["THYAO", "GARAN", "ASELS"]:
        print(f"\n📊 {sembol} Forum Konsensüsü:")
        konsensus = izleyici.sembol_konsensusu(sembol)
        print(f"   Durum: {konsensus['durum']}")
        print(f"   Skor: {konsensus['konsensus_skoru']:+.1f}")
        print(f"   ✅ {konsensus['olumlu']} olumlu | ❌ {konsensus['olumsuz']} olumsuz | ⚪ {konsensus['notr']} nötr")
