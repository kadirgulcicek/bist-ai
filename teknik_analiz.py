"""
Teknik Analiz Göstergeleri
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Hareketli Ortalamalar (SMA/EMA)
- Destek ve Direnç Seviyeleri
"""

import pandas as pd
import numpy as np


class TeknikAnaliz:
    
    @staticmethod
    def rsi_hesapla(fiyatlar, donem=14):
        """RSI (Göreceli Güç Endeksi) hesaplar"""
        delta = fiyatlar.diff()
        kazanc = (delta.where(delta > 0, 0)).rolling(window=donem).mean()
        kayip = (-delta.where(delta < 0, 0)).rolling(window=donem).mean()
        
        rs = kazanc / kayip
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd_hesapla(fiyatlar, kisa=12, uzun=26, sinyal=9):
        """MACD hesaplar"""
        ema_kisa = fiyatlar.ewm(span=kisa, adjust=False).mean()
        ema_uzun = fiyatlar.ewm(span=uzun, adjust=False).mean()
        macd = ema_kisa - ema_uzun
        sinyal_cizgi = macd.ewm(span=sinyal, adjust=False).mean()
        histogram = macd - sinyal_cizgi
        return macd, sinyal_cizgi, histogram
    
    @staticmethod
    def bollinger_bands(fiyatlar, donem=20, std_sayisi=2):
        """Bollinger Bands hesaplar"""
        sma = fiyatlar.rolling(window=donem).mean()
        std = fiyatlar.rolling(window=donem).std()
        ust_band = sma + (std * std_sayisi)
        alt_band = sma - (std * std_sayisi)
        return ust_band, sma, alt_band
    
    @staticmethod
    def hareketli_ortalama(fiyatlar, donem=20, tip='sma'):
        """Hareketli ortalama hesaplar (SMA veya EMA)"""
        if tip == 'sma':
            return fiyatlar.rolling(window=donem).mean()
        elif tip == 'ema':
            return fiyatlar.ewm(span=donem, adjust=False).mean()
    
    @staticmethod
    def destek_direnc(fiyatlar, pencere=20):
        """Destek ve direnç seviyelerini bulur"""
        son_fiyatlar = fiyatlar.tail(pencere)
        direnç = son_fiyatlar.max()
        destek = son_fiyatlar.min()
        return destek, direnç
    
    @staticmethod
    def sinyal_uret(rsi, macd, sinyal, fiyat, sma_20, sma_50):
        """Teknik göstergelere göre alım/satım sinyali üretir"""
        sinyaller = []
        skor = 0
        
        # RSI Analizi
        if rsi < 30:
            sinyaller.append("🟢 RSI aşırı satımda (Alım fırsatı)")
            skor += 2
        elif rsi > 70:
            sinyaller.append("🔴 RSI aşırı alımda (Satım bölgesi)")
            skor -= 2
        elif 40 < rsi < 60:
            sinyaller.append("🟡 RSI nötr bölgede")
        
        # MACD Analizi
        if macd > sinyal:
            sinyaller.append("🟢 MACD yukarı kesişimde (Yükseliş trendi)")
            skor += 2
        else:
            sinyaller.append("🔴 MACD aşağı kesişimde (Düşüş trendi)")
            skor -= 2
        
        # Hareketli Ortalama Analizi
        if sma_20 > sma_50:
            sinyaller.append("🟢 Kısa vade uzun vadenin üstünde (Pozitif trend)")
            skor += 1
        else:
            sinyaller.append("🔴 Kısa vade uzun vadenin altında (Negatif trend)")
            skor -= 1
        
        # Fiyat vs SMA
        if fiyat > sma_20:
            sinyaller.append("🟢 Fiyat 20 günlük ortalamanın üstünde")
            skor += 1
        else:
            sinyaller.append("🔴 Fiyat 20 günlük ortalamanın altında")
            skor -= 1
        
        # Genel Karar
        if skor >= 4:
            karar = "✅ GÜÇLÜ AL"
        elif skor >= 2:
            karar = "🟢 AL"
        elif skor <= -4:
            karar = "  GÜÇLÜ SAT"
        elif skor <= -2:
            karar = "🔴 SAT"
        else:
            karar = "⏸️ BEKLE"
        
        return karar, skor, sinyaller


def hisse_teknik_analiz(sembol, period="3mo"):
    """Tek bir hisse için tüm teknik analizi yapar"""
    import yfinance as yf
    
    ticker = yf.Ticker(sembol)
    veri = ticker.history(period=period)
    
    if len(veri) < 50:
        return None
    
    fiyatlar = veri['Close']
    analiz = TeknikAnaliz()
    
    # Hesaplamalar
    rsi = analiz.rsi_hesapla(fiyatlar).iloc[-1]
    macd, sinyal, hist = analiz.macd_hesapla(fiyatlar)
    macd_son = macd.iloc[-1]
    sinyal_son = sinyal.iloc[-1]
    hist_son = hist.iloc[-1]
    
    ust, orta, alt = analiz.bollinger_bands(fiyatlar)
    sma_20 = analiz.hareketli_ortalama(fiyatlar, 20).iloc[-1]
    sma_50 = analiz.hareketli_ortalama(fiyatlar, 50).iloc[-1]
    
    destek, direnç = analiz.destek_direnc(fiyatlar)
    fiyat = fiyatlar.iloc[-1]
    
    # Sinyal üret
    karar, skor, sinyaller = analiz.sinyal_uret(rsi, macd_son, sinyal_son, fiyat, sma_20, sma_50)
    
    return {
        'Sembol': sembol.replace('.IS', ''),
        'Fiyat': round(fiyat, 2),
        'RSI': round(rsi, 2),
        'MACD': round(macd_son, 3),
        'SMA 20': round(sma_20, 2),
        'SMA 50': round(sma_50, 2),
        'Destek': round(destek, 2),
        'Direnç': round(direnç, 2),
        'Skor': skor,
        'Karar': karar,
        'Sinyaller': sinyaller
    }


if __name__ == "__main__":
    # Test: Birkaç hisseyi analiz et
    test_hisseleri = ["THYAO.IS", "GARAN.IS", "ASELS.IS", "SISE.IS", "TUPRS.IS"]
    
    print("=" * 60)
    print("📊 TEKNİK ANALİZ TEST")
    print("=" * 60)
    
    for sembol in test_hisseleri:
        print(f"\n🔍 {sembol} analiz ediliyor...")
        sonuc = hisse_teknik_analiz(sembol)
        
        if sonuc:
            print(f"\n{sonuc['Karar']}  (Skor: {sonuc['Skor']})")
            print(f"   Fiyat: {sonuc['Fiyat']} TL")
            print(f"   RSI: {sonuc['RSI']} | MACD: {sonuc['MACD']}")
            print(f"   Destek: {sonuc['Destek']} | Direnç: {sonuc['Direnç']}")
            print(f"   Sinyaller:")
            for s in sonuc['Sinyaller']:
                print(f"      {s}")
        else:
            print(f"   ⚠️ Yeterli veri yok")
