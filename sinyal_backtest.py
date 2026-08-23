"""
Al-Sat Sinyal Kurallarinin Gecmis Performans Testi
"""

import yfinance as yf
import pandas as pd
import numpy as np


class SinyalBacktest:
    def __init__(self, baslangic_sermaye=100000):
        self.baslangic = baslangic_sermaye
    
    def veri_al(self, sembol, period="6mo"):
        try:
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period=period)
            if veri is None or len(veri) < 60:
                return None
            return veri
        except:
            return None
    
    def rsi_gunluk(self, fiyat_series, index, pencere=14):
        """Belirli bir gun icin RSI - pandas ile"""
        if index < pencere:
            return 50.0
        
        try:
            veri = fiyat_series.iloc[index-pencere:index]
            delta = veri.diff().dropna()
            
            if len(delta) == 0:
                return 50.0
            
            kazanc = delta.where(delta > 0, 0).mean()
            kayip = (-delta.where(delta < 0, 0)).mean()
            
            if kayip == 0 or pd.isna(kayip):
                return 100.0
            
            rs = kazanc / kayip
            if pd.isna(rs):
                return 50.0
            
            rsi = 100 - (100 / (1 + rs))
            return float(rsi) if not pd.isna(rsi) else 50.0
        except:
            return 50.0
    
    def macd_gunluk(self, fiyat_series, index):
        """Belirli bir gun icin MACD"""
        if index < 26:
            return 0.0
        
        try:
            veri = fiyat_series.iloc[:index+1]
            ema12 = veri.ewm(span=12, adjust=False).mean()
            ema26 = veri.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            sinyal = macd.ewm(span=9, adjust=False).mean()
            
            fark = float(macd.iloc[-1] - sinyal.iloc[-1])
            return fark if not pd.isna(fark) else 0.0
        except:
            return 0.0
    
    def hisse_backtest(self, sembol):
        print(f"  {sembol} test ediliyor...", end=" ")
        
        veri = self.veri_al(sembol)
        if veri is None:
            print("veri yok")
            return None
        
        kapanis = veri['Close']  # pandas Series
        hacimler = veri['Volume'].values  # numpy array
        tarihler = veri.index
        
        sermaye = float(self.baslangic)
        pozisyon = 0.0
        alis_fiyati = 0.0
        islemler = []
        
        for i in range(26, len(kapanis)):
            fiyat = float(kapanis.iloc[i])
            if fiyat <= 0 or pd.isna(fiyat):
                continue
            
            rsi = self.rsi_gunluk(kapanis, i)
            macd = self.macd_gunluk(kapanis, i)
            
            # SAT KURALLARI
            if pozisyon > 0 and alis_fiyati > 0:
                kar_yuzde = ((fiyat - alis_fiyati) / alis_fiyati) * 100
                
                sat_sinyali = False
                sat_sebebi = ""
                
                if kar_yuzde >= 15:
                    sat_sinyali = True
                    sat_sebebi = "Hedef kar"
                elif kar_yuzde <= -10:
                    sat_sinyali = True
                    sat_sebebi = "Stop-loss"
                elif rsi > 70:
                    sat_sinyali = True
                    sat_sebebi = "RSI asiri alim"
                
                if sat_sinyali:
                    kar_orani = (fiyat - alis_fiyati) / alis_fiyati
                    sermaye = sermaye * (1 + kar_orani)
                    islemler.append({
                        "tarih": tarihler[i].strftime("%Y-%m-%d"),
                        "tip": "SATIS",
                        "fiyat": fiyat,
                        "kar_orani": kar_orani * 100,
                        "sebep": sat_sebebi
                    })
                    pozisyon = 0.0
            
            # AL KURALLARI
            elif pozisyon == 0:
                al_skor = 0
                sebepler = []
                
                if rsi < 35:
                    al_skor += 1
                    sebepler.append("RSI<35")
                if macd > 0:
                    al_skor += 1
                    sebepler.append("MACD+")
                
                # Hacim kontrolu
                try:
                    if i > 20:
                        ort_hacim = float(np.mean(hacimler[i-20:i]))
                        if ort_hacim > 0 and float(hacimler[i]) > ort_hacim * 1.5:
                            al_skor += 1
                            sebepler.append("Hacim yuksek")
                except:
                    pass
                
                # Trend kontrolu
                try:
                    if i > 20:
                        sma20 = float(kapanis.iloc[i-20:i].mean())
                        if fiyat > sma20:
                            al_skor += 1
                            sebepler.append("Trend+")
                except:
                    pass
                
                if al_skor >= 3:
                    alis_fiyati = fiyat
                    pozisyon = sermaye / fiyat
                    islemler.append({
                        "tarih": tarihler[i].strftime("%Y-%m-%d"),
                        "tip": "ALIS",
                        "fiyat": fiyat,
                        "sebep": ", ".join(sebepler)
                    })
        
        # Son pozisyonu kapat
        if pozisyon > 0 and alis_fiyati > 0:
            son_fiyat = float(kapanis.iloc[-1])
            if son_fiyat > 0 and alis_fiyati > 0 and not pd.isna(son_fiyat):
                kar_orani = (son_fiyat - alis_fiyati) / alis_fiyati
                sermaye = sermaye * (1 + kar_orani)
                islemler.append({
                    "tarih": "Son",
                    "tip": "KAPATMA",
                    "fiyat": son_fiyat,
                    "kar_orani": kar_orani * 100,
                    "sebep": "Son kapanis"
                })
        
        toplam_getiri = ((sermaye - self.baslangic) / self.baslangic) * 100
        if pd.isna(toplam_getiri):
            toplam_getiri = 0.0
        
        kapali_islemler = [i for i in islemler if i["tip"] in ["SATIS", "KAPATMA"]]
        basarili = sum(1 for i in kapali_islemler if i.get("kar_orani", 0) > 0)
        toplam_islem = len(kapali_islemler)
        basari_orani = (basarili / toplam_islem * 100) if toplam_islem > 0 else 0.0
        
        emoji = "🟢" if toplam_getiri > 0 else "🔴"
        print(f"{emoji} {toplam_getiri:+6.2f}% (islem: {toplam_islem}, basari: {basari_orani:.0f}%)")
        
        return {
            "sembol": sembol,
            "baslangic": self.baslangic,
            "son": sermaye,
            "getiri": toplam_getiri,
            "basari_orani": basari_orani,
            "islem_sayisi": toplam_islem,
            "islemler": islemler
        }
    
    def toplu_backtest(self, hisse_listesi=None):
        if hisse_listesi is None:
            hisse_listesi = [
                "THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"
            ]
        
        print("=" * 70)
        print("AL-SAT KURALLARI BACKTESTING")
        print("=" * 70)
        print(f"Dönem: Son 6 ay")
        print(f"Başlangıç sermayesi: {self.baslangic:,.0f} TL (her hisse)")
        print()
        print("KURALLAR:")
        print("  AL: RSI<35 + MACD+ + Hacim + Trend (3/4 koşul)")
        print("  SAT: Kar>%15 veya Stop-loss -%10 veya RSI>70")
        print("=" * 70)
        print()
        
        sonuclar = []
        for sembol in hisse_listesi:
            sonuc = self.hisse_backtest(sembol)
            if sonuc:
                sonuclar.append(sonuc)
        
        if not sonuclar:
            print("\nHicbir hisse test edilemedi!")
            return
        
        print("\n" + "=" * 70)
        print("HISSE BAZLI SONUCLAR")
        print("=" * 70)
        
        sirali = sorted(sonuclar, key=lambda x: x["getiri"], reverse=True)
        
        for s in sirali:
            emoji = "🟢" if s["getiri"] > 0 else "🔴"
            print(f"{emoji} {s['sembol']:<8} Getiri: {s['getiri']:+7.2f}%  İşlem: {s['islem_sayisi']:>2}  Başarı: %{s['basari_orani']:>5.1f}")
        
        print("\n" + "=" * 70)
        print("GENEL SONUÇLAR")
        print("=" * 70)
        
        ortalama_getiri = sum(s["getiri"] for s in sonuclar) / len(sonuclar)
        en_iyi = sirali[0]
        en_kotu = sirali[-1]
        ortalama_basari = sum(s["basari_orani"] for s in sonuclar) / len(sonuclar)
        
        pozitif = len([s for s in sonuclar if s["getiri"] > 0])
        negatif = len(sonuclar) - pozitif
        
        print(f"📈 Ortalama Getiri: {ortalama_getiri:+.2f}%")
        print(f"🏆 En İyi: {en_iyi['sembol']} ({en_iyi['getiri']:+.2f}%)")
        print(f"📉 En Kötü: {en_kotu['sembol']} ({en_kotu['getiri']:+.2f}%)")
        print(f"🎯 Ortalama Başarı: %{ortalama_basari:.1f}")
        print(f"✅ Pozitif: {pozitif}/{len(sonuclar)} hisse")
        print(f"❌ Negatif: {negatif}/{len(sonuclar)} hisse")
        
        toplam_baslangic = self.baslangic * len(sonuclar)
        toplam_son = sum(s["son"] for s in sonuclar)
        toplam_getiri = ((toplam_son - toplam_baslangic) / toplam_baslangic) * 100
        
        print(f"\n💰 SANAL PORTFÖY:")
        print(f"   Başlangıç: {toplam_baslangic:,.0f} TL")
        print(f"   Son: {toplam_son:,.0f} TL")
        print(f"   Toplam Getiri: {toplam_getiri:+.2f}%")
        
        print("\n" + "=" * 70)
        print("YORUM")
        print("=" * 70)
        
        if toplam_getiri > 10:
            print("✅ Mükemmel! Kurallar çok başarılı.")
        elif toplam_getiri > 0:
            print("🟢 İyi. Kurallar kârlı.")
        elif toplam_getiri > -10:
            print("🟡 Orta. Kurallar geliştirilebilir.")
        else:
            print("🔴 Zayıf. Kurallar gözden geçirilmeli.")
        
        if ortalama_basari > 60:
            print("✅ Yüksek başarı oranı - güvenilir.")
        elif ortalama_basari > 50:
            print("🟡 Orta başarı - iyileştirilebilir.")


if __name__ == "__main__":
    bt = SinyalBacktest(baslangic_sermaye=100000)
    bt.toplu_backtest()
    input("\nCikmak icin Enter'a basin...")
