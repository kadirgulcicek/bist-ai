import yfinance as yf
import pandas as pd

print("BIST AI Sistemi - İlk Test")
print("=" * 40)

# BIST'ten popüler hisseleri çek
hisseler = ["THYAO.IS", "GARAN.IS", "ASELS.IS", "SISE.IS", "EREGL.IS"]

for hisse in hisseler:
    try:
        ticker = yf.Ticker(hisse)
        bilgi = ticker.info
        fiyat = bilgi.get('currentPrice', 'Yok')
        print(f"✅ {hisse}: {fiyat} TL")
    except:
        print(f"❌ {hisse}: Veri alınamadı")

print("=" * 40)
print("Sistem çalışıyor!")
