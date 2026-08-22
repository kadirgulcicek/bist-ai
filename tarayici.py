"""
BIST Tüm Hisseleri Tarayıcı
- Güncel fiyat
- Günlük değişim
- Hacim
- 52 hafta yüksek/düşük
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import time
from hisse_listesi import hisse_listesi_getir

class BISTTarayici:
    def __init__(self):
        self.hisseler = hisse_listesi_getir()
        self.sonuclar = []
    
    def tek_hisse_tara(self, sembol):
        """Tek bir hissenin verilerini çeker"""
        try:
            ticker = yf.Ticker(sembol)
            bilgi = ticker.info
            
            # Son 5 günlük veriyi çek (değişim hesaplamak için)
            gecmis = ticker.history(period="5d")
            
            if len(gecmis) < 2:
                return None
            
            simdi = gecmis['Close'].iloc[-1]
            dun = gecmis['Close'].iloc[-2]
            degisim_yuzde = ((simdi - dun) / dun) * 100
            
            sonuc = {
                'Sembol': sembol.replace('.IS', ''),
                'Fiyat': round(simdi, 2),
                'Değişim %': round(degisim_yuzde, 2),
                'Hacim': gecmis['Volume'].iloc[-1],
                '52H Yüksek': bilgi.get('fiftyTwoWeekHigh', 'N/A'),
                '52H Düşük': bilgi.get('fiftyTwoWeekLow', 'N/A'),
                'Piyasa Değeri': bilgi.get('marketCap', 'N/A'),
                'Sektör': bilgi.get('sector', 'Bilinmiyor')
            }
            
            return sonuc
        
        except Exception as e:
            print(f"⚠️ {sembol} atlandı: {str(e)[:50]}")
            return None
    
    def tumunu_tara(self):
        """Tüm hisseleri tarar"""
        print(f"🔍 {len(self.hisseler)} hisse taranıyor...\n")
        
        for i, sembol in enumerate(self.hisseler, 1):
            print(f"[{i}/{len(self.hisseler)}] {sembol} taranıyor...", end=" ")
            sonuc = self.tek_hisse_tara(sembol)
            
            if sonuc:
                self.sonuclar.append(sonuc)
                print(f"✅ {sonuc['Fiyat']} TL ({sonuc['Değişim %']}%)")
            else:
                print("❌")
            
            # Yahoo'ya yüklenmeyi önlemek için kısa bekleme
            time.sleep(0.5)
        
        return self.sonuclar
    
    def en_cok_yukselenler(self, n=10):
        """En çok yükselen hisseleri gösterir"""
        df = pd.DataFrame(self.sonuclar)
        df = df.sort_values('Değişim %', ascending=False)
        print(f"\n🚀 EN ÇOK YÜKSELENLER (İlk {n}):")
        print(df.head(n).to_string(index=False))
        return df.head(n)
    
    def en_cok_dusenler(self, n=10):
        """En çok düşen hisseleri gösterir"""
        df = pd.DataFrame(self.sonuclar)
        df = df.sort_values('Değişim %', ascending=True)
        print(f"\n📉 EN ÇOK DÜŞENLER (İlk {n}):")
        print(df.head(n).to_string(index=False))
        return df.head(n)
    
    def en_yuksek_hacimli(self, n=10):
        """En yüksek hacimli hisseleri gösterir"""
        df = pd.DataFrame(self.sonuclar)
        df = df[df['Hacim'].apply(lambda x: isinstance(x, (int, float)))]
        df['Hacim'] = pd.to_numeric(df['Hacim'], errors='coerce')
        df = df.sort_values('Hacim', ascending=False)
        print(f"\n💰 EN YÜKSEK HACİMLİLER (İlk {n}):")
        print(df.head(n).to_string(index=False))
        return df.head(n)
    
    def excele_kaydet(self, dosya_adi=f"bist_tarama_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"):
        """Sonuçları Excel dosyasına kaydeder"""
        df = pd.DataFrame(self.sonuclar)
        df.to_excel(dosya_adi, index=False)
        print(f"\n💾 Excel dosyası kaydedildi: {dosya_adi}")


def main():
    print("=" * 50)
    print("📊 BIST HİSSE TARAYICI")
    print("=" * 50)
    
    tarayici = BISTTarayici()
    sonuclar = tarayici.tumunu_tara()
    
    if not sonuclar:
        print("\n❌ Hiç veri alınamadı. İnternet bağlantınızı kontrol edin.")
        return
    
    # Özet istatistikler
    df = pd.DataFrame(sonuclar)
    print(f"\n📈 ÖZET:")
    print(f"   Toplam hisse: {len(df)}")
    print(f"   Yükselen: {len(df[df['Değişim %'] > 0])}")
    print(f"   Düşen: {len(df[df['Değişim %'] < 0])}")
    print(f"   Ortalama değişim: %{df['Değişim %'].mean():.2f}")
    
    # Detaylı listeler
    tarayici.en_cok_yukselenler(5)
    tarayici.en_cok_dusenler(5)
    tarayici.en_yuksek_hacimli(5)
    
    # Excel'e kaydet
    tarayici.excele_kaydet()


if __name__ == "__main__":
    main()
