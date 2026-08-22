"""
Derin Ogrenme Benzeri AI Tahmin Sistemi
TensorFlow gerekmez - scikit-learn kullanir
"""

import numpy as np
import yfinance as yf
from datetime import datetime
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import MinMaxScaler


class DerinOgrenmeTahminci:
    def __init__(self, look_back=30):
        self.look_back = look_back
        self.scaler_X = MinMaxScaler()
        self.scaler_y = MinMaxScaler()
        self.model = None
    
    def veri_al(self, sembol, period="2y"):
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period=period)
            if veri is None or len(veri) < 100:
                return None
            fiyatlar = veri['Close'].to_numpy(dtype=float)
            fiyatlar = fiyatlar[np.isfinite(fiyatlar)]
            if len(fiyatlar) < 100:
                return None
            return fiyatlar
        except:
            return None
    
    def ozellikler_olustur(self, fiyatlar):
        X = []
        y = []
        for i in range(self.look_back, len(fiyatlar)):
            pencere = fiyatlar[i - self.look_back:i]
            ozellikler = list(pencere)
            ozellikler.append(np.mean(pencere))
            ozellikler.append(np.std(pencere))
            ozellikler.append(pencere[-1] - pencere[0])
            ozellikler.append(np.min(pencere))
            ozellikler.append(np.max(pencere))
            X.append(ozellikler)
            y.append(fiyatlar[i])
        return np.array(X), np.array(y)
    
    def model_egit(self, sembol):
        print(f"Model {sembol} icin egitiliyor...")
        fiyatlar = self.veri_al(sembol)
        if fiyatlar is None or len(fiyatlar) < 100:
            print("Veri yetersiz!")
            return None
        
        X, y = self.ozellikler_olustur(fiyatlar)
        X_scaled = self.scaler_X.fit_transform(X)
        y_scaled = self.scaler_y.fit_transform(y.reshape(-1, 1)).flatten()
        
        split = int(len(X) * 0.8)
        X_train, X_test = X_scaled[:split], X_scaled[split:]
        y_train, y_test = y_scaled[:split], y_scaled[split:]
        
        self.model = MLPRegressor(
            hidden_layer_sizes=(100, 50, 25),
            activation='relu',
            max_iter=100,
            random_state=42,
            verbose=False
        )
        self.model.fit(X_train, y_train)
        score = self.model.score(X_test, y_test)
        print(f"   Model basari: {score*100:.2f}%")
        return score
    
    def tahmin_et(self, sembol, gun=5):
        if self.model is None:
            return None
        fiyatlar = self.veri_al(sembol)
        if fiyatlar is None:
            return None
        
        mevcut = list(fiyatlar[-self.look_back:])
        tahminler = []
        
        for _ in range(gun):
            ozellikler = mevcut.copy()
            ozellikler.append(np.mean(mevcut))
            ozellikler.append(np.std(mevcut))
            ozellikler.append(mevcut[-1] - mevcut[0])
            ozellikler.append(np.min(mevcut))
            ozellikler.append(np.max(mevcut))
            
            X = np.array(ozellikler).reshape(1, -1)
            X_scaled = self.scaler_X.transform(X)
            tahmin_scaled = self.model.predict(X_scaled)[0]
            tahmin = self.scaler_y.inverse_transform([[tahmin_scaled]])[0][0]
            
            tahminler.append(float(tahmin))
            mevcut = mevcut[1:] + [tahmin]
        
        return tahminler


def basit_tahmin(sembol, gun=5):
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="3mo")
        if veri is None or len(veri) < 10:
            return None
        
        fiyatlar = veri['Close'].to_numpy(dtype=float)
        fiyatlar = fiyatlar[np.isfinite(fiyatlar)]
        if len(fiyatlar) < 10:
            return None
        son_n = min(20, len(fiyatlar))
        trend = (fiyatlar[-1] - fiyatlar[-son_n]) / fiyatlar[-son_n]
        gunluk_trend = trend / son_n
        if gunluk_trend != gunluk_trend:
            gunluk_trend = 0
        
        tahminler = []
        son_fiyat = float(fiyatlar[-1])
        for i in range(1, gun + 1):
            tahmin = son_fiyat * (1 + gunluk_trend * i)
            if tahmin != tahmin or tahmin <= 0:
                tahmin = son_fiyat
            tahminler.append(tahmin)
        return tahminler
    except:
        return None


def main():
    test_hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL", 
                      "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"]
    
    print("=" * 60)
    print("AI HISSE TAHMIN SISTEMI")
    print("=" * 60)
    print()
    
    print("Ilk hisse icin AI modeli egitiliyor...")
    tahminci = DerinOgrenmeTahminci(look_back=30)
    basari = tahminci.model_egit(test_hisseler[0])
    
    if basari and basari > 0.5:
        print("\nModel basarili!\n")
    else:
        print("\nFallback kullanilacak.\n")
        tahminci = None
    
    print("=" * 60)
    print("HISSE TAHMINLERI (5 gun)")
    print("=" * 60)
    
    tahminler_listesi = []
    for sembol in test_hisseler:
        if sembol == test_hisseler[0] and tahminci:
            tahminler = tahminci.tahmin_et(sembol, 5)
            kaynak = "AI"
        else:
            tahminler = basit_tahmin(sembol, 5)
            kaynak = "Trend"
        
        if tahminler:
            bugun = float(tahminler[0])
            hedef = float(tahminler[-1])
            degisim = ((hedef - bugun) / bugun) * 100 if bugun > 0 else 0
            emoji = "Y" if degisim > 0 else "D"
            print(f"{emoji} {sembol:8} ({kaynak}): {bugun:.2f} -> {hedef:.2f} TL ({degisim:+.2f}%)")
            tahminler_listesi.append({"sembol": sembol, "degisim": degisim, "hedef": hedef})
    
    print("\n" + "=" * 60)
    print("SIRALAMA")
    print("=" * 60)
    sirali = sorted(tahminler_listesi, key=lambda x: x["degisim"], reverse=True)
    for i, t in enumerate(sirali, 1):
        print(f"{i:2}. {t['sembol']:8} {t['degisim']:+6.2f}% -> {t['hedef']:.2f} TL")


if __name__ == "__main__":
    main()
    input("\nCikmak icin Enter'a basin...")
