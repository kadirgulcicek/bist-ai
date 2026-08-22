"""
Portfoy Grafikleri - Guvenli Versiyon
"""

import yfinance as yf
import matplotlib.pyplot as plt
from portfoy import Portfoy


def guvenli_veri_al(sembol, adet, alis):
    """Bir hisseden guvenli veri ceker"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="5d")
        if len(veri) < 1:
            return None
        guncel = float(veri['Close'].iloc[-1])
        if guncel != guncel:  # NaN kontrolu
            return None
        return {
            "sembol": sembol,
            "adet": adet,
            "alis": alis,
            "guncel": guncel,
            "deger": adet * guncel,
            "kar_yuzde": ((guncel - alis) / alis) * 100 if alis > 0 else 0
        }
    except:
        return None


def dagilim_grafigi():
    p = Portfoy()
    if not p.hisseler:
        print("Portfoy bos!")
        return None
    
    print("Dagilim grafigi olusturuluyor...")
    
    hisseler = []
    degerler = []
    
    for h in p.hisseler:
        veri = guvenli_veri_al(h["sembol"], h["adet"], h["alis_fiyati"])
        if veri is None:
            print("  Atlandi: " + h["sembol"])
            continue
        if veri["deger"] <= 0:
            continue
        hisseler.append(veri["sembol"])
        degerler.append(veri["deger"])
    
    if not degerler or len(degerler) == 0:
        print("Grafik icin yeterli veri yok!")
        return None
    
    plt.figure(figsize=(10, 8))
    plt.pie(degerler, labels=hisseler, autopct='%1.1f%%', startangle=90)
    plt.title('Portfoy Daglilimi')
    
    dosya = "dagilim.png"
    plt.savefig(dosya)
    plt.close()
    print("Kaydedildi: " + dosya)
    return dosya


def kar_zarar_grafigi():
    p = Portfoy()
    if not p.hisseler:
        print("Portfoy bos!")
        return None
    
    print("Kar/zarar grafigi olusturuluyor...")
    
    hisseler = []
    kar_yuzdeler = []
    renkler = []
    
    for h in p.hisseler:
        veri = guvenli_veri_al(h["sembol"], h["adet"], h["alis_fiyati"])
        if veri is None:
            print("  Atlandi: " + h["sembol"])
            continue
        hisseler.append(veri["sembol"])
        kar_yuzdeler.append(veri["kar_yuzde"])
        renkler.append('green' if veri["kar_yuzde"] >= 0 else 'red')
    
    if not hisseler:
        print("Grafik icin yeterli veri yok!")
        return None
    
    plt.figure(figsize=(12, 6))
    plt.bar(hisseler, kar_yuzdeler, color=renkler)
    plt.title('Hisse Bazli Kar/Zarar (%)')
    plt.axhline(y=0, color='black', linewidth=0.5)
    plt.xticks(rotation=45)
    plt.grid(axis='y', alpha=0.3)
    
    dosya = "kar_zarar.png"
    plt.savefig(dosya)
    plt.close()
    print("Kaydedildi: " + dosya)
    return dosya


def fiyat_grafigi(sembol):
    print(sembol + " fiyat grafigi olusturuluyor...")
    
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="30d")
        
        if len(veri) < 1:
            print("Veri yok!")
            return None
        
        plt.figure(figsize=(12, 6))
        plt.plot(veri.index, veri['Close'], color='blue', linewidth=2)
        plt.title(sembol + ' - Son 30 Gun')
        plt.xlabel('Tarih')
        plt.ylabel('Fiyat (TL)')
        plt.grid(True)
        
        dosya = sembol + "_fiyat.png"
        plt.savefig(dosya)
        plt.close()
        print("Kaydedildi: " + dosya)
        return dosya
    except Exception as e:
        print("Hata: " + str(e))
        return None


def tum_grafikler():
    olusturulanlar = []
    
    d = dagilim_grafigi()
    if d:
        olusturulanlar.append(d)
    
    k = kar_zarar_grafigi()
    if k:
        olusturulanlar.append(k)
    
    p = Portfoy()
    if p.hisseler:
        sembol = p.hisseler[0]["sembol"]
        f = fiyat_grafigi(sembol)
        if f:
            olusturulanlar.append(f)
    
    if olusturulanlar:
        print("\nToplam " + str(len(olusturulanlar)) + " grafik olusturuldu:")
        for dosya in olusturulanlar:
            print("  - " + dosya)
    else:
        print("\nHic grafik olusturulamadi.")
    
    return olusturulanlar


if __name__ == "__main__":
    print("=" * 50)
    print("GRAFIK PANELI")
    print("=" * 50)
    print("1. Tum grafikleri olustur")
    print("2. Sadece dagilim")
    print("3. Sadece kar/zarar")
    print("4. Belirli hissenin fiyat grafigi")
    print("5. Cikis")
    
    while True:
        secim = input("\nSeciminiz (1-5): ").strip()
        
        if secim == "1":
            tum_grafikler()
        elif secim == "2":
            dagilim_grafigi()
        elif secim == "3":
            kar_zarar_grafigi()
        elif secim == "4":
            s = input("Hisse: ").strip()
            fiyat_grafigi(s)
        elif secim == "5":
            break
    
    input("\nCikmak icin Enter'a basin...")
