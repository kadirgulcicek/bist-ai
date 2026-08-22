"""
BIST AI Tahmin Modeli
- Geçmiş veriden öğrenir
- Gelecek 1-5 günlük fiyat yönünü tahmin eder
- Modeli kaydeder ve tekrar kullanır
"""

import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os
from datetime import datetime

from teknik_analiz import TeknikAnaliz


class BISTTahminModeli:
    def __init__(self):
        self.model = None
        self.model_dosyasi = "bist_ai_modeli.pkl"
        self.tahminler = {}
    
    def veri_hazirla(self, sembol, period="2y"):
        """Bir hisse için AI'ın öğreneceği veriyi hazırlar"""
        ticker = yf.Ticker(sembol)
        veri = ticker.history(period=period)
        
        if len(veri) < 100:
            return None
        
        fiyatlar = veri['Close']
        hacim = veri['Volume']
        analiz = TeknikAnaliz()
        
        # Özellikler (Features) oluştur
        veri_ozellik = pd.DataFrame()
        
        # Fiyat özellikleri
        veri_ozellik['Fiyat'] = fiyatlar
        veri_ozellik['Degisim_1d'] = fiyatlar.pct_change(1) * 100
        veri_ozellik['Degisim_5d'] = fiyatlar.pct_change(5) * 100
        veri_ozellik['Degisim_10d'] = fiyatlar.pct_change(10) * 100
        
        # Hareketli ortalamalar
        veri_ozellik['SMA_5'] = analiz.hareketli_ortalama(fiyatlar, 5)
        veri_ozellik['SMA_10'] = analiz.hareketli_ortalama(fiyatlar, 10)
        veri_ozellik['SMA_20'] = analiz.hareketli_ortalama(fiyatlar, 20)
        veri_ozellik['SMA_50'] = analiz.hareketli_ortalama(fiyatlar, 50)
        
        # Fiyat / SMA oranları
        veri_ozellik['Fiyat_SMA5'] = fiyatlar / veri_ozellik['SMA_5']
        veri_ozellik['Fiyat_SMA20'] = fiyatlar / veri_ozellik['SMA_20']
        
        # RSI
        veri_ozellik['RSI'] = analiz.rsi_hesapla(fiyatlar)
        
        # MACD
        macd, sinyal, hist = analiz.macd_hesapla(fiyatlar)
        veri_ozellik['MACD'] = macd
        veri_ozellik['MACD_Sinyal'] = sinyal
        veri_ozellik['MACD_Hist'] = hist
        
        # Bollinger
        ust, orta, alt = analiz.bollinger_bands(fiyatlar)
        veri_ozellik['BB_Position'] = (fiyatlar - alt) / (ust - alt)
        
        # Hacim değişimi
        veri_ozellik['Hacim_Degisim'] = hacim.pct_change(1) * 100
        veri_ozellik['Hacim_Ortalama'] = hacim.rolling(20).mean()
        veri_ozellik['Hacim_Ratio'] = hacim / veri_ozellik['Hacim_Ortalama']
        
        # Volatilite
        veri_ozellik['Volatilite'] = fiyatlar.rolling(20).std()
        
        # Hedef değişken: 3 gün sonra yükselecek mi? (1: evet, 0: hayır)
        hedef_fiyat = fiyatlar.shift(-3)
        veri_ozellik['Hedef'] = (hedef_fiyat > fiyatlar).astype(int)
        
        # NaN temizle
        veri_ozellik = veri_ozellik.replace([np.inf, -np.inf], np.nan).dropna()
        
        if len(veri_ozellik) < 50:
            return None
        
        return veri_ozellik
    
    def model_egit(self, hisseler=None):
        """Birden fazla hisseden öğrenen model eğitir"""
        from hisse_listesi import hisse_listesi_getir
        
        if hisseler is None:
            # Eğitim için BIST'in en likit 30-40 hissesini kullan
            hisseler = hisse_listesi_getir()[:30]
        
        print(f"🧠 {len(hisseler)} hisseden AI öğreniyor...\n")
        
        tum_veriler = []
        
        for i, sembol in enumerate(hisseler, 1):
            print(f"[{i}/{len(hisseler)}] {sembol} öğreniliyor...", end=" ")
            try:
                veri = self.veri_hazirla(sembol)
                if veri is not None and len(veri) > 50:
                    tum_veriler.append(veri)
                    print(f"✅ {len(veri)} satır veri eklendi")
                else:
                    print("⚠️ Veri yetersiz")
            except Exception as e:
                print(f"❌ Hata")
        
        if not tum_veriler:
            print("\n❌ Yeterli veri toplanamadı!")
            return
        
        # Tüm verileri birleştir
        tum_veri_df = pd.concat(tum_veriler, ignore_index=True)
        
        # Özellikler ve hedef
        ozellik_sutunlari = [c for c in tum_veri_df.columns if c != 'Hedef']
        X = tum_veri_df[ozellik_sutunlari]
        y = tum_veri_df['Hedef']
        
        # Eğitim/Test böl
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        print(f"\n📚 Eğitim seti: {len(X_train)} örnek")
        print(f"📝 Test seti: {len(X_test)} örnek")
        
        # Model eğit (Gradient Boosting - daha güçlü)
        print("\n🎓 Model eğitiliyor...")
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        # Test doğruluğu
        tahmin = self.model.predict(X_test)
        dogruluk = accuracy_score(y_test, tahmin)
        print(f"\n✅ Model doğruluğu: %{dogruluk*100:.2f}")
        
        # Modeli kaydet
        joblib.dump({
            'model': self.model,
            'ozellik_sutunlari': ozellik_sutunlari
        }, self.model_dosyasi)
        
        print(f"💾 Model '{self.model_dosyasi}' olarak kaydedildi.")
        
        # Özellik önem sıralaması
        onem = pd.DataFrame({
            'Özellik': ozellik_sutunlari,
            'Önem': self.model.feature_importances_
        }).sort_values('Önem', ascending=False)
        
        print(f"\n🔍 En Önemli 5 Özellik:")
        print(onem.head(5).to_string(index=False))
    
    def model_yukle(self):
        """Kaydedilmiş modeli yükler"""
        if os.path.exists(self.model_dosyasi):
            kayit = joblib.load(self.model_dosyasi)
            self.model = kayit['model']
            self.ozellik_sutunlari = kayit['ozellik_sutunlari']
            print(f"✅ Model yüklendi: {self.model_dosyasi}")
            return True
        return False
    
    def hisse_tahmin_et(self, sembol):
        """Tek bir hisse için tahmin yapar"""
        if self.model is None:
            if not self.model_yukle():
                print("❌ Model bulunamadı. Önce model_egit() çalıştırın.")
                return None
        
        veri = self.veri_hazirla(sembol)
        if veri is None:
            return None
        
        ozellik_sutunlari = [c for c in veri.columns if c != 'Hedef']
        X = veri[ozellik_sutunlari].tail(1)  # Son günün verisi
        
        tahmin = self.model.predict(X)[0]
        olasilik = self.model.predict_proba(X)[0]
        
        return {
            'Sembol': sembol.replace('.IS', ''),
            'Tahmin': '🟢 YÜKSELİŞ' if tahmin == 1 else '🔴 DÜŞÜŞ',
            'Güven': round(olasilik[tahmin] * 100, 2),
            'Yükselme_Olasılığı': round(olasilik[1] * 100, 2),
            'Düşme_Olasılığı': round(olasilik[0] * 100, 2)
        }


def main():
    """AI modelini eğit ve test et"""
    print("=" * 60)
    print("🤖 BIST AI TAHMİN MODELİ")
    print("=" * 60)
    
    ai = BISTTahminModeli()
    
    # Modeli eğit (ilk seferde çalışır, sonra kayıttan yükler)
    ai.model_egit()
    
    # Test tahminleri
    print("\n" + "=" * 60)
    print("🎯 ÖRNEK TAHMİNLER")
    print("=" * 60)
    
    test_hisseleri = ["THYAO.IS", "GARAN.IS", "ASELS.IS", "SISE.IS", "EREGL.IS"]
    
    for sembol in test_hisseleri:
        tahmin = ai.hisse_tahmin_et(sembol)
        if tahmin:
            print(f"\n{tahmin['Sembol']}: {tahmin['Tahmin']}")
            print(f"   Güven: %{tahmin['Güven']}")
            print(f"   Yükselme: %{tahmin['Yükselme_Olasılığı']} | Düşme: %{tahmin['Düşme_Olasılığı']}")


if __name__ == "__main__":
    main()
