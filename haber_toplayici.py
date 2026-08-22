"""
BIST İlgili Haber Toplayıcı
- Türk finans haber sitelerini tarar
- Hisse ile ilgili haberleri filtreler
- Tarih ve kaynak bilgisi ile birlikte saklar
"""

import feedparser
import requests
from datetime import datetime, timedelta
from newspaper import Article
import re
import time


class HaberToplayici:
    
    def __init__(self):
        # Türk finans haber kaynakları (RSS feeds)
        self.kaynaklar = {
            "Anadolu Ajansı Finans": "https://www.aa.com.tr/tr/finans/rss",
            "Bloomberg HT": "https://www.bloomberght.com/rss",
            "Dünya Gazetesi": "https://www.dunya.com/rss",
            "Hürriyet Ekonomi": "https://www.hurriyet.com.tr/rss/ekonomi",
            "Sabah Ekonomi": "https://www.sabah.com.tr/rss/ekonomi",
        }
        
        # Anahtar kelimeler - hangi haberler bizim için önemli?
        self.anahtar_kelimeler = {
            'yukselis': ['artış', 'yükseliş', 'rekor', 'tarihi zirve', 'prim', 'rağbet'],
            'dusus': ['düşüş', 'gerileme', 'değer kaybı', 'satış', 'baskı', 'eridi'],
            'sirket': ['hisse', 'şirket', 'ortaklık', 'birleşme', 'satın alma', 'temettü'],
            'sektor': ['bankacılık', 'havacılık', 'enerji', 'sanayi', 'teknoloji', 'otomotiv'],
            'ekonomi': ['faiz', 'enflasyon', 'merkez bankası', 'TCMB', 'kur', 'dolar'],
        }
    
    def rss_haberleri_al(self, kaynak_url, max_haber=20):
        """Bir kaynaktan RSS ile haber çeker"""
        try:
            feed = feedparser.parse(kaynak_url)
            haberler = []
            
            for entry in feed.entries[:max_haber]:
                haber = {
                    'baslik': entry.title,
                    'link': entry.link,
                    'tarih': datetime.now(),
                    'kaynak': kaynak_url,
                    'ozet': entry.get('summary', '')[:300]
                }
                haberler.append(haber)
            
            return haberler
        except Exception as e:
            print(f"⚠️ RSS hatası: {str(e)[:50]}")
            return []
    
    def hisse_haber_bul(self, sembol_adi, hisse_listesi):
        """Belirli bir hisse ile ilgili haberleri filtreler"""
        tum_haberler = self.tum_haberleri_topla()
        ilgili_haberler = []
        
        sembol_temiz = sembol_adi.replace('.IS', '').lower()
        # Şirket isim eşleştirmesi (basit)
        sirket_esleme = {
            'THYAO': ['thy', 'türk hava yolları', 'havacılık'],
            'GARAN': ['garanti', 'garanti bankası', 'bankacılık'],
            'ASELS': ['aselsan', 'savunma', 'elektronik'],
            'TUPRS': ['tüpraş', 'petrol', 'rafineri'],
            'EREGL': ['ereğli', 'demir çelik', 'çelik'],
            'BIMAS': ['bim', 'perakende', 'market'],
            'KCHOL': ['koç', 'koç holding'],
            'SISE': ['şİşe cam', 'cam'],
            'PETKM': ['petkim', 'petrokimya'],
            'TAVHL': ['tav', 'havalimanı'],
        }
        
        ilgili_anahtar = sirket_esleme.get(sembol_temiz, [sembol_temiz.lower()])
        
        for haber in tum_haberler:
            baslik_lower = haber['baslik'].lower()
            if any(kelime in baslik_lower for kelime in ilgili_anahtar):
                haber['ilgililik'] = 'yüksek'
                ilgili_haberler.append(haber)
        
        return ilgili_haberler
    
    def tum_haberleri_topla(self):
        """Tüm kaynaklardan haberleri toplar"""
        tum_haberler = []
        
        for kaynak_adi, url in self.kaynaklar.items():
            print(f"   📡 {kaynak_adi} taranıyor...", end=" ")
            haberler = self.rss_haberleri_al(url, max_haber=10)
            tum_haberler.extend(haberler)
            print(f"{len(haberler)} haber")
            time.sleep(0.5)
        
        return tum_haberler
    
    def haber_detay_al(self, url):
        """Bir haberin tam metnini çeker"""
        try:
            article = Article(url, language='tr')
            article.download()
            article.parse()
            return {
                'baslik': article.title,
                'metin': article.text[:1000],
                'yazarlar': article.authors,
                'tarih': article.publish_date
            }
        except:
            return None


if __name__ == "__main__":
    print("=" * 60)
    print("📰 BIST HABER TOPLAYICI - TEST")
    print("=" * 60)
    
    toplayici = HaberToplayici()
    haberler = toplayici.tum_haberleri_topla()
    
    print(f"\n📊 Toplam {len(haberler)} haber toplandı.\n")
    
    if haberler:
        print("📌 Son 10 Haber Özeti:\n")
        for i, h in enumerate(haberler[:10], 1):
            print(f"{i}. {h['baslik'][:80]}")
            print(f"   {h['ozet'][:120]}...")
            print()
