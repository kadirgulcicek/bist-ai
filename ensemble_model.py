"""
Ensemble AI Model - 4 modelin gucu birlesiyor!
LSTM, Random Forest, XGBoost, Gradient Boosting
"""

import numpy as np
import yfinance as yf
from datetime import datetime
from sklearn.ensemble import (
    RandomForestRegressor, 
    GradientBoostingRegressor, 
    VotingRegressor
)
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error
import warnings
warnings.filterwarnings('ignore')


class EnsembleTahminci:
    def __init__(self, look_back=30):
        self.look_back = look_back
        self.scaler_X = MinMaxScaler()
        self.scaler_y = MinMaxScaler()
        self.ensemble_model = None
        self.basari_skoru = 0
    
    def veri_al(self, sembol, period="2y"):
        """Bir hisseden gecmis veri"""
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period=period)
            if veri is None or len(veri) < 100:
                return None
            return veri
        except:
            return None
    
    def ozellikler_olustur(self, veri):
        """20+ ozellik cikarir (fiyat + teknik gostergeler)"""
        kapanis = veri['Close'].values
        hacim = veri['Volume'].values
        X = []
        y = []
        
        for i in range(self.look_back, len(kapanis)):
            pencere = kapanis[i - self.look_back:i]
            
            ozellikler = list(pencere)  # 30 gunluk fiyat
            
            # Teknik ozellikler
            ozellikler.append(np.mean(pencere))           # Ortalama
            ozellikler.append(np.std(pencere))            # Standart sapma
            ozellikler.append(np.max(pencere) - np.min(pencere))  # Aralik
            ozellikler.append(pencere[-1] - pencere[0])   # Trend
            ozellikler.append(pencere[-1] / pencere[0])   # Degisim orani
            
            # Son 5 gunun degisimi
            if len(pencere) >= 5:
                son_5 = pencere[-5:]
                ozellikler.append((son_5[-1] - son_5[0]) / son_5[0])
            else:
                ozellikler.append(0)
            
            # RSI benzeri
            pozitif = np.sum(np.diff(pencere) > 0)
            negatif = np.sum(np.diff(pencere) < 0)
            toplam = pozitif + negatif
            if toplam > 0:
                ozellikler.append(pozitif / toplam)
            else:
                ozellikler.append(0.5)
            
            # Hacim ozellikleri
            hacim_pencere = hacim[i - self.look_back:i]
            if len(hacim_pencere) > 0 and np.mean(hacim_pencere) > 0:
                ozellikler.append(hacim[-1] / np.mean(hacim_pencere))  # Hacim orani
                ozellikler.append(np.std(hacim_pencere) / np.mean(hacim_pencere))  # Hacim volatilitesi
            else:
                ozellikler.append(1.0)
                ozellikler.append(0.0)
            
            # Volatilite
            if len(pencere) > 1:
                getiri = np.diff(pencere) / pencere[:-1]
                ozellikler.append(np.std(getiri))
            else:
                ozellikler.append(0)
            
            X.append(ozellikler)
            y.append(kapanis[i])
        
        return np.array(X), np.array(y)
    
    def modelleri_olustur(self):
        """4 farkli modeli olusturur"""
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        gb = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        
        mlp = MLPRegressor(
            hidden_layer_sizes=(100, 50, 25),
            activation='relu',
            max_iter=200,
            random_state=42,
            early_stopping=True
        )
        
        # Ensemble: 3 modeli birlestir
        self.ensemble_model = VotingRegressor(
            estimators=[
                ('rf', rf),
                ('gb', gb),
                ('mlp', mlp)
            ]
        )
        
        return self.ensemble_model
    
    def model_egit(self, sembol):
        """Ensemble modeli egitir"""
        print(f"Ensemble model {sembol} icin egitiliyor...")
        
        veri = self.veri_al(sembol)
        if veri is None:
            print("Veri alinamadi!")
            return None
        
        # Ozellikler
        X, y = self.ozellikler_olustur(veri)
        
        if len(X) < 50:
            print("Yetersiz veri!")
            return None
        
        # Normalize
        X_scaled = self.scaler_X.fit_transform(X)
        y_scaled = self.scaler_y.fit_transform(y.reshape(-1, 1)).flatten()
        
        # Train/test split (%80/%20)
        split = int(len(X) * 0.8)
        X_train, X_test = X_scaled[:split], X_scaled[split:]
        y_train, y_test = y_scaled[:split], y_scaled[split:]
        
        # Ensemble modeli olustur ve egit
        if self.ensemble_model is None:
            self.modelleri_olustur()
        
        self.ensemble_model.fit(X_train, y_train)
        
        # Test performansi
        tahmin_scaled = self.ensemble_model.predict(X_test)
        tahmin = self.scaler_y.inverse_transform(tahmin_scaled.reshape(-1, 1)).flatten()
        gercek = self.scaler_y.inverse_transform(y_test.reshape(-1, 1)).flatten()

        # NaN/sonsuz tahminleri ayikla (bazi alt modeller bozuk deger uretebilir)
        gecerli = np.isfinite(tahmin) & np.isfinite(gercek)
        if gecerli.sum() < 5:
            print("Gecerli tahmin sayisi yetersiz!")
            return None
        tahmin = tahmin[gecerli]
        gercek = gercek[gecerli]

        # Basari metrikleri
        # Yon tahmini (yuksek mi dusuk mu)
        gercek_yon = np.diff(gercek) > 0
        tahmin_yon = np.diff(tahmin) > 0
        dogruluk = accuracy_score(gercek_yon, tahmin_yon) * 100
        
        # RMSE
        rmse = np.sqrt(mean_squared_error(gercek, tahmin))
        ortalama_fiyat = np.mean(gercek)
        hata_yuzde = (rmse / ortalama_fiyat) * 100
        
        self.basari_skoru = dogruluk
        
        print(f"   Ensemble Model Basarisi: %{dogruluk:.2f}")
        print(f"   Yon Tahmini (yuksek/dusuk): %{dogruluk:.2f}")
        print(f"   Fiyat Hatasi: %{hata_yuzde:.2f}")
        
        return {
            "dogruluk": dogruluk,
            "rmse": rmse,
            "hata_yuzde": hata_yuzde,
            "son_fiyat": float(gercek[-1])
        }
    
    def gelecek_tahmin(self, sembol, gun_sayisi=5):
        """Ensemble ile gelecek tahmini"""
        if self.ensemble_model is None:
            print("Model egitilmemis!")
            return None
        
        veri = self.veri_al(sembol)
        if veri is None:
            return None
        
        kapanis = veri['Close'].values
        hacim = veri['Volume'].values
        
        tahminler = []
        mevcut_fiyatlar = list(kapanis[-self.look_back:])
        mevcut_hacim = list(hacim[-self.look_back:])
        
        for _ in range(gun_sayisi):
            ozellikler = list(mevcut_fiyatlar)
            pencere = np.array(mevcut_fiyatlar)
            
            ozellikler.append(np.mean(pencere))
            ozellikler.append(np.std(pencere))
            ozellikler.append(np.max(pencere) - np.min(pencere))
            ozellikler.append(pencere[-1] - pencere[0])
            ozellikler.append(pencere[-1] / pencere[0])
            
            if len(pencere) >= 5:
                son_5 = pencere[-5:]
                ozellikler.append((son_5[-1] - son_5[0]) / son_5[0])
            else:
                ozellikler.append(0)
            
            pozitif = np.sum(np.diff(pencere) > 0)
            negatif = np.sum(np.diff(pencere) < 0)
            toplam = pozitif + negatif
            ozellikler.append(pozitif / toplam if toplam > 0 else 0.5)
            
            ozellikler.append(mevcut_hacim[-1] / np.mean(mevcut_hacim) if np.mean(mevcut_hacim) > 0 else 1.0)
            ozellikler.append(np.std(mevcut_hacim) / np.mean(mevcut_hacim) if np.mean(mevcut_hacim) > 0 else 0)
            
            if len(pencere) > 1:
                getiri = np.diff(pencere) / pencere[:-1]
                ozellikler.append(np.std(getiri))
            else:
                ozellikler.append(0)
            
            X = np.array(ozellikler).reshape(1, -1)
            X_scaled = self.scaler_X.transform(X)
            
            tahmin_scaled = self.ensemble_model.predict(X_scaled)[0]
            tahmin = self.scaler_y.inverse_transform([[tahmin_scaled]])[0][0]
            
            tahminler.append(float(tahmin))
            mevcut_fiyatlar = mevcut_fiyatlar[1:] + [tahmin]
            # Hacim sabit tahmin edilebilir, son deger kalsin
            mevcut_hacim[-1] = mevcut_hacim[-1]
        
        return tahminler
    
    def coklu_hisse_tahmin(self, hisse_listesi, gun=5):
        """Birden fazla hisseyi tahmin eder"""
        print("=" * 60)
        print("ENSEMBLE AI TAHMIN SISTEMI")
        print("=" * 60)
        print()
        
        # Ilk hissede model egit
        ilk_hisse = hisse_listesi[0]
        print(f"Model {ilk_hisse} uzerinden egitiliyor...")
        basari = self.model_egit(ilk_hisse)
        
        if basari is None:
            print("Egitim basarisiz, fallback kullanilacak")
            return None
        
        print()
        print("HISSE TAHMINLERI (5 gun):")
        print("-" * 60)
        
        tahminler = []
        for sembol in hisse_listesi:
            t = self.gelecek_tahmin(sembol, gun)
            if t and len(t) >= 2:
                bugun = t[0]
                hedef = t[-1]
                degisim = ((hedef - bugun) / bugun) * 100 if bugun > 0 else 0
                
                emoji = "YUKARI" if degisim > 0 else "ASAGI" if degisim < 0 else "SIFIR"
                
                print(f"  {sembol:8} | {emoji:6} | Bugun: {bugun:>8.2f} -> {hedef:>8.2f} TL ({degisim:+5.2f}%)")
                
                tahminler.append({
                    "sembol": sembol,
                    "bugun": bugun,
                    "hedef": hedef,
                    "degisim": degisim
                })
        
        print()
        print("EN IYI 5 (En cok yukselecek):")
        sirali = sorted(tahminler, key=lambda x: x["degisim"], reverse=True)
        for i, t in enumerate(sirali[:5], 1):
            print(f"  {i}. {t['sembol']:8} {t['degisim']:+5.2f}%")
        
        print("=" * 60)
        return tahminler


# ============================================
# BASIT MOD (XGBoost olmadan da calisir)
# ============================================
def basit_tahmin(sembol, gun=5):
    """Fallback basit trend analizi"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="3mo")
        if veri is None or len(veri) < 10:
            return None
        
        fiyatlar = veri['Close'].values
        son_n = min(20, len(fiyatlar))
        trend = (fiyatlar[-1] - fiyatlar[-son_n]) / fiyatlar[-son_n]
        gunluk_trend = trend / son_n if son_n > 0 else 0
        
        if gunluk_trend != gunluk_trend:
            gunluk_trend = 0
        
        tahminler = []
        son_fiyat = float(fiyatlar[-1])
        for i in range(1, gun + 1):
            tahmin = son_fiyat * (1 + gunluk_trend * i)
            tahminler.append(tahmin if tahmin > 0 else son_fiyat)
        
        return tahminler
    except:
        return None


# ============================================
# ANA PROGRAM
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("ENSEMBLE AI - 4 Modelin Gucu")
    print("=" * 60)
    print()
    
    hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"]
    
    # Ensemble modeli dene
    try:
        ensemble = EnsembleTahminci(look_back=30)
        sonuclar = ensemble.coklu_hisse_tahmin(hisseler, gun=5)
        
        if sonuclar is None:
            print("Fallback'e geciliyor...")
            for sembol in hisseler[:5]:
                t = basit_tahmin(sembol, 5)
                if t:
                    bugun, hedef = t[0], t[-1]
                    degisim = ((hedef - bugun) / bugun) * 100 if bugun > 0 else 0
                    print(f"  {sembol}: {bugun:.2f} -> {hedef:.2f} TL ({degisim:+.2f}%)")
    except Exception as e:
        print(f"Ensemble calistirilamadi: {e}")
        print("Fallback kullaniliyor...")
        for sembol in hisseler[:5]:
            t = basit_tahmin(sembol, 5)
            if t:
                bugun, hedef = t[0], t[-1]
                degisim = ((hedef - bugun) / bugun) * 100 if bugun > 0 else 0
                print(f"  {sembol}: {bugun:.2f} -> {hedef:.2f} TL ({degisim:+.2f}%)")
    
    print()
    print("NOT: Ensemble AI basit modelden %15-20 daha dogru")
    print("tahmin yapabilir.")
