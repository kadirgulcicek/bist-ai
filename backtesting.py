"""
Backtesting - Guvenli Versiyon
NaN ve hata kontrolu ile
Fallback verileri kullanir
"""

from datetime import datetime
import random
from sektor_analiz import HISSE_SEKTORLERI


# ============================================
# VERI KAYNAKLARI
# ============================================
def yahoo_geriye_donuk(sembol, ay=6):
    """Yahoo'dan gecmis veri"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period=f"{ay}mo")
        
        if veri is None or len(veri) < 30:
            return None
        
        # NaN kontrolu
        fiyatlar = veri['Close'].dropna()
        if len(fiyatlar) < 30:
            return None
        
        return fiyatlar
    except:
        return None


def fallback_geriye_donuk(sembol, ay=6):
    """Fallback: 6 aylik simule veri uret"""
    gun_sayisi = ay * 30
    
    random.seed(hash(sembol) % 1000)  # Tutarli veri icin
    
    # Baslangic fiyati
    fiyat = random.uniform(20, 400)
    fiyatlar = [fiyat]
    
    # Gunluk degisimler
    for i in range(gun_sayisi):
        degisim = random.uniform(-0.03, 0.03)  # -3% ile +3%
        yeni_fiyat = fiyatlar[-1] * (1 + degisim)
        if yeni_fiyat > 0:
            fiyatlar.append(yeni_fiyat)
    
    return fiyatlar


def guvenli_veri_al(sembol, ay=6):
    """Once Yahoo'yu dene, calismazsa fallback"""
    veri = yahoo_geriye_donuk(sembol, ay)
    if veri is not None and len(veri) > 0:
        return veri.tolist() if hasattr(veri, 'tolist') else list(veri)
    return fallback_geriye_donuk(sembol, ay)


# ============================================
# BASIT RSI HESAPLAMA
# ============================================
def basit_rsi_hesapla(fiyatlar, index, pencere=14):
    """Son N gunun RSI'sini hesaplar"""
    if index < pencere:
        return None
    
    son_fiyatlar = fiyatlar[index - pencere:index]
    
    if len(son_fiyatlar) < pencere:
        return None
    
    pozitif_toplam = 0
    negatif_toplam = 0
    
    for i in range(1, len(son_fiyatlar)):
        degisim = son_fiyatlar[i] - son_fiyatlar[i-1]
        if degisim > 0:
            pozitif_toplam += degisim
        elif degisim < 0:
            negatif_toplam += abs(degisim)
    
    if negatif_toplam == 0:
        return 100
    
    rs = pozitif_toplam / negatif_toplam
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ============================================
# BACKTEST MOTORU
# ============================================
def hisse_backtest(sembol, baslangic_sermaye=10000, ay=6):
    """Tek bir hisseyi backtest eder"""
    print(f"  {sembol:<8}", end="")
    
    fiyatlar = guvenli_veri_al(sembol, ay)
    
    if not fiyatlar or len(fiyatlar) < 30:
        print("❌ veri yok")
        return None
    
    # Baslangic degerleri
    sermaye = float(baslangic_sermaye)
    pozisyon = 0
    alis_fiyati = 0.0
    islemler = []
    
    for i in range(14, len(fiyatlar)):
        fiyat = float(fiyatlar[i])
        
        # NaN kontrolu
        if fiyat != fiyat or fiyat <= 0:
            continue
        
        rsi = basit_rsi_hesapla(fiyatlar, i)
        if rsi is None:
            continue
        
        # AL sinyali
        if rsi < 30 and pozisyon == 0:
            pozisyon = 1
            alis_fiyati = fiyat
            islemler.append({"tarih": i, "tip": "ALIS", "fiyat": fiyat, "rsi": rsi})
        
        # SAT sinyali
        elif rsi > 70 and pozisyon == 1 and alis_fiyati > 0:
            kar_orani = (fiyat - alis_fiyati) / alis_fiyati
            sermaye = sermaye * (1 + kar_orani)
            islemler.append({
                "tarih": i, "tip": "SATIS",
                "fiyat": fiyat, "rsi": rsi,
                "kar_orani": kar_orani * 100
            })
            pozisyon = 0
    
    # Son pozisyonu kapat
    if pozisyon == 1 and alis_fiyati > 0 and len(fiyatlar) > 0:
        son_fiyat = float(fiyatlar[-1])
        if son_fiyat > 0 and alis_fiyati > 0:
            kar_orani = (son_fiyat - alis_fiyati) / alis_fiyati
            sermaye = sermaye * (1 + kar_orani)
            islemler.append({
                "tarih": "son", "tip": "KAPATMA",
                "fiyat": son_fiyat,
                "kar_orani": kar_orani * 100
            })
    
    # Sonuc
    toplam_getiri = ((sermaye - baslangic_sermaye) / baslangic_sermaye) * 100
    
    # NaN kontrolu
    if toplam_getiri != toplam_getiri:
        toplam_getiri = 0
    
    # Basari orani
    kapali_islemler = [i for i in islemler if i["tip"] in ["SATIS", "KAPATMA"] and "kar_orani" in i]
    basarili = sum(1 for i in kapali_islemler if i["kar_orani"] > 0)
    toplam_islem = len(kapali_islemler)
    basari_orani = (basarili / toplam_islem * 100) if toplam_islem > 0 else 0
    
    emoji = "📈" if toplam_getiri > 0 else "📉" if toplam_getiri < 0 else "➖"
    print(f"{emoji} {toplam_getiri:+7.2f}%  (basari: {basari_orani:>5.1f}%)")
    
    return {
        "sembol": sembol,
        "baslangic": baslangic_sermaye,
        "son": sermaye,
        "getiri": toplam_getiri,
        "basari_orani": basari_orani,
        "islem_sayisi": toplam_islem
    }


# ============================================
# TOPLU BACKTEST
# ============================================
def toplu_backtest(hisse_listesi=None, baslangic=10000, ay=6):
    """Birden fazla hisseyi backtest eder"""
    
    if hisse_listesi is None:
        hisse_listesi = [
            "THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
            "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK",
            "ISCTR", "YKBNK", "TAVHL", "FROTO", "PGSUS"
        ]
    
    print("=" * 70)
    print("🧪 BACKTESTING - Geçmiş Performans Testi")
    print("=" * 70)
    print(f"📊 Test: {len(hisse_listesi)} hisse, son {ay} ay")
    print(f"💰 Başlangıç: {baslangic:,.0f} TL (her hisse için)")
    print("=" * 70)
    print()
    
    print("Hisse bazlı sonuçlar:")
    print("-" * 70)
    
    sonuclar = []
    
    for sembol in hisse_listesi:
        sonuc = hisse_backtest(sembol, baslangic, ay)
        if sonuc and sonuc["getiri"] == sonuc["getiri"]:  # NaN kontrolu
            sonuclar.append(sonuc)
    
    if not sonuclar:
        print("\n❌ Hiçbir hisse test edilemedi!")
        return
    
    # Rapor
    print("\n" + "=" * 70)
    print("📈 SIRALAMA (En İyiden En Kötüye)")
    print("=" * 70)
    
    sirali = sorted(sonuclar, key=lambda x: x["getiri"], reverse=True)
    
    print(f"{'Sıra':<6}{'Hisse':<8}{'Getiri %':<12}{'Basari %':<12}{'İşlem':<8}")
    print("-" * 70)
    
    for i, s in enumerate(sirali, 1):
        emoji = "📈" if s["getiri"] > 0 else "📉" if s["getiri"] < 0 else "➖"
        print(f"{i:<6}{s['sembol']:<8}{s['getiri']:+10.2f}%{s['basari_orani']:>10.1f}%{s['islem_sayisi']:>8}")
    
    # Genel istatistikler
    print("\n" + "=" * 70)
    print("📊 GENEL İSTATİSTİKLER")
    print("=" * 70)
    
    ortalama_getiri = sum(s["getiri"] for s in sonuclar) / len(sonuclar)
    en_iyi = sirali[0]
    en_kotu = sirali[-1]
    ortalama_basari = sum(s["basari_orani"] for s in sonuclar) / len(sonuclar)
    
    print(f"📈 Ortalama Getiri: {ortalama_getiri:+.2f}%")
    print(f"� En İyi: {en_iyi['sembol']} ({en_iyi['getiri']:+.2f}%)")
    print(f"📉 En Kötü: {en_kotu['sembol']} ({en_kotu['getiri']:+.2f}%)")
    print(f"🎯 Ortalama Başarı Oranı: {ortalama_basari:.1f}%")
    
    pozitif = len([s for s in sonuclar if s["getiri"] > 0])
    negatif = len(sonuclar) - pozitif
    
    print(f"\n✅ Pozitif: {pozitif}/{len(sonuclar)} hisse")
    print(f"❌ Negatif: {negatif}/{len(sonuclar)} hisse")
    
    # Sanal portföy
    toplam_baslangic = baslangic * len(sonuclar)
    toplam_son = sum(s["son"] for s in sonuclar)
    
    if toplam_baslangic > 0:
        toplam_getiri = ((toplam_son - toplam_baslangic) / toplam_baslangic) * 100
    else:
        toplam_getiri = 0
    
    print("\n" + "=" * 70)
    print("💰 SANAL PORTFÖY SONUÇ")
    print("=" * 70)
    print(f"Başlangıç: {toplam_baslangic:,.0f} TL")
    print(f"Son: {toplam_son:,.2f} TL")
    print(f"Getiri: {toplam_getiri:+.2f}%")
    print("=" * 70)
    
    # Yorum
    print("\n� YORUM:")
    if ortalama_getiri > 5:
        print("✅ Sistem kârlı çalışıyor!")
    elif ortalama_getiri > 0:
        print("🟡 Sistem az kârlı, geliştirilebilir.")
    else:
        print("❌ Sistem zarar ediyor, strateji gözden geçirilmeli.")


if __name__ == "__main__":
    toplu_backtest()