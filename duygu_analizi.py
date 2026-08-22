"""
Haber Duygu Analizi
- Pozitif/Nötr/Negatif sınıflandırma
- Hisse üzerindeki olası etkiyi değerlendirme
"""

from transformers import pipeline
import re


class DuyguAnalizi:
    def __init__(self):
        print("🧠 Duygu analizi modeli yükleniyor... (bir kez yüklenir)")
        # Türkçe sentiment modeli (veya çok dilli model)
        try:
            self.analyzer = pipeline(
                "sentiment-analysis",
                model="savasy/bert-base-multilingual-text-classification"
            )
            print("✅ Model yüklendi!")
        except Exception as e:
            print(f"⚠️ Model yüklenemedi, basit analiz kullanılacak: {e}")
            self.analyzer = None
    
    def basit_analiz(self, metin):
        """Model yoksa basit kelime tabanlı analiz"""
        pozitif = ['artış', 'yükseliş', 'rekor', 'büyüme', 'kâr', 'başarı', 'olumlu', 
                   'güçlü', 'prim', 'talep', 'olumlu', 'kazanç', 'iyi']
        negatif = ['düşüş', 'gerileme', 'zarar', 'kayıp', 'kriz', 'olumsuz', 'risk',
                   'satış', 'baskı', 'daralma', 'kötü', 'tehlike', 'sorun']
        
        metin_lower = metin.lower()
        pozitif_skor = sum(1 for k in pozitif if k in metin_lower)
        negatif_skor = sum(1 for k in negatif if k in metin_lower)
        
        if pozitif_skor > negatif_skor:
            return {'label': 'POSITIVE', 'score': 0.7}
        elif negatif_skor > pozitif_skor:
            return {'label': 'NEGATIVE', 'score': 0.7}
        else:
            return {'label': 'NEUTRAL', 'score': 0.5}
    
    def analiz_et(self, metin):
        """Metnin duygusunu analiz eder"""
        if not metin or len(metin) < 10:
            return {'label': 'NEUTRAL', 'score': 0.5, 'etki': 'nötr'}
        
        # Metni kısalt (modelin sınırları var)
        metin = metin[:512]
        
        if self.analyzer:
            try:
                sonuc = self.analyzer(metin)[0]
                label = sonuc['label']
                score = sonuc['score']
            except:
                sonuc = self.basit_analiz(metin)
                label = sonuc['label']
                score = sonuc['score']
        else:
            sonuc = self.basit_analiz(metin)
            label = sonuc['label']
            score = sonuc['score']
        
        # Etki skorunu hesapla
        if 'POSITIVE' in label.upper() or 'OLUMLU' in label.upper():
            etki = 'pozitif'
            sayisal_etki = score
        elif 'NEGATIVE' in label.upper() or 'OLUMSUZ' in label.upper():
            etki = 'negatif'
            sayisal_etki = -score
        else:
            etki = 'nötr'
            sayisal_etki = 0
        
        return {
            'label': label,
            'score': round(score, 3),
            'etki': etki,
            'sayisal_etki': round(sayisal_etki, 3)
        }
    
    def haber_etki_skoru(self, haber_listesi):
        """Bir hisse için tüm haberlerin toplam etkisini hesaplar"""
        toplam_etki = 0
        pozitif_sayisi = 0
        negatif_sayisi = 0
        
        analiz_sonuclari = []
        
        for haber in haber_listesi:
            analiz = self.analiz_et(haber.get('baslik', '') + ' ' + haber.get('ozet', ''))
            analiz['baslik'] = haber.get('baslik', '')[:80]
            analiz_sonuclari.append(analiz)
            
            toplam_etki += analiz['sayisal_etki']
            if analiz['etki'] == 'pozitif':
                pozitif_sayisi += 1
            elif analiz['etki'] == 'negatif':
                negatif_sayisi += 1
        
        return {
            'toplam_etki': round(toplam_etki, 3),
            'pozitif_haber': pozitif_sayisi,
            'negatif_haber': negatif_sayisi,
            'nötr_haber': len(haber_listesi) - pozitif_sayisi - negatif_sayisi,
            'haber_sayisi': len(haber_listesi),
            'detaylar': analiz_sonuclari
        }


if __name__ == "__main__":
    print("🧠 Duygu Analizi Testi\n")
    analiz = DuyguAnalizi()
    
    test_haberler = [
        {"baslik": "THY rekor kâr açıkladı, hisseler tırmanışa geçti", "ozet": "yükseliş"},
        {"baslik": "Aselsan yeni sözleşme ile prim yaptı", "ozet": "olumlu"},
        {"baslik": "Garanti bankası zarar açıklamasıyla düştü", "ozet": "olumsuz"},
        {"baslik": "BIST 100'de dalgalı seyir devam ediyor", "ozet": "nötr"},
    ]
    
    sonuc = analiz.haber_etki_skoru(test_haberler)
    print(f"\n📊 Toplam Etki: {sonuc['toplam_etki']}")
    print(f"   ✅ Pozitif: {sonuc['pozitif_haber']} | ❌ Negatif: {sonuc['negatif_haber']}")
