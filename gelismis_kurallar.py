"""
Gelismis Al-Sat Kurallari - Basit Versiyon
10+ gosterge ile profesyonel analiz
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime


def guvenli_rsi(fiyatlar, pencere=14):
    try:
        delta = fiyatlar.diff().dropna()
        if len(delta) < pencere:
            return 50.0
        kazanc = delta.where(delta > 0, 0).rolling(pencere).mean().iloc[-1]
        kayip = (-delta.where(delta < 0, 0)).rolling(pencere).mean().iloc[-1]
        if kayip == 0 or pd.isna(kayip):
            return 100.0
        if pd.isna(kazanc):
            return 50.0
        rs = kazanc / kayip
        rsi = 100 - (100 / (1 + rs))
        return float(rsi) if not pd.isna(rsi) else 50.0
    except:
        return 50.0


def guvenli_macd(fiyatlar):
    try:
        ema12 = fiyatlar.ewm(span=12, adjust=False).mean()
        ema26 = fiyatlar.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        sinyal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - sinyal
        h_val = histogram.iloc[-1]
        return {
            "histogram": float(h_val) if not pd.isna(h_val) else 0,
            "pozitif": bool(macd.iloc[-1] > sinyal.iloc[-1])
        }
    except:
        return {"histogram": 0, "pozitif": False}


def guvenli_bollinger(fiyatlar, pencere=20, std=2):
    try:
        sma = fiyatlar.rolling(pencere).mean()
        std_d = fiyatlar.rolling(pencere).std()
        ust = sma + (std_d * std)
        alt = sma - (std_d * std)
        guncel = float(fiyatlar.iloc[-1])
        ust_s = float(ust.iloc[-1])
        alt_s = float(alt.iloc[-1])
        pozisyon = (guncel - alt_s) / (ust_s - alt_s) if (ust_s - alt_s) > 0 else 0.5
        return {
            "pozisyon": max(0, min(1, pozisyon)),
            "alt_break": guncel < alt_s,
            "ust_break": guncel > ust_s
        }
    except:
        return {"pozisyon": 0.5, "alt_break": False, "ust_break": False}


def guvenli_mfi(fiyatlar, hacimler, pencere=14):
    try:
        tipik = fiyatlar
        pozitif = 0
        negatif = 0
        for i in range(1, min(pencere + 1, len(tipik))):
            t_i = float(tipik.iloc[-i])
            v_i = float(hacimler.iloc[-i])
            t_ip1 = float(tipik.iloc[-(i+1)])
            if t_i > t_ip1:
                pozitif += t_i * v_i
            else:
                negatif += t_i * v_i
        if negatif == 0:
            return 100.0
        oran = pozitif / negatif
        mfi = 100 - (100 / (1 + oran))
        return float(mfi)
    except:
        return 50.0


def guvenli_roc(fiyatlar, pencere=10):
    try:
        if len(fiyatlar) < pencere + 1:
            return 0.0
        simdi = float(fiyatlar.iloc[-1])
        once = float(fiyatlar.iloc[-(pencere+1)])
        if once == 0:
            return 0.0
        return ((simdi - once) / once) * 100
    except:
        return 0.0


def analiz_uret(sembol, maliyet=None):
    try:
        ticker = yf.Ticker(sembol + ".IS")
        veri = ticker.history(period="6mo")
        if veri is None or len(veri) < 60:
            return None
        
        kapanis = veri['Close']
        hacimler = veri['Volume']
        guncel = float(kapanis.iloc[-1])
        
        rsi_v = guvenli_rsi(kapanis)
        macd_v = guvenli_macd(kapanis)
        bb_v = guvenli_bollinger(kapanis)
        mfi_v = guvenli_mfi(kapanis, hacimler)
        roc_v = guvenli_roc(kapanis)
        
        al_puan = 0
        al_sebepler = []
        
        if rsi_v < 30:
            al_puan = al_puan + 3
            al_sebepler.append("RSI asiri satim")
        elif rsi_v < 40:
            al_puan = al_puan + 2
            al_sebepler.append("RSI asiri satim bolgesi")
        
        if macd_v["histogram"] > 0 and macd_v["pozitif"]:
            al_puan = al_puan + 2
            al_sebepler.append("MACD pozitif")
        
        if bb_v["alt_break"]:
            al_puan = al_puan + 2
            al_sebepler.append("Bollinger alt kirildi")
        elif bb_v["pozisyon"] < 0.2:
            al_puan = al_puan + 1
            al_sebepler.append("Bollinger alt bolge")
        
        if mfi_v < 20:
            al_puan = al_puan + 2
            al_sebepler.append("MFI cok dusuk")
        elif mfi_v < 30:
            al_puan = al_puan + 1
            al_sebepler.append("MFI dusuk")
        
        if roc_v > 5:
            al_puan = al_puan + 1
            al_sebepler.append("Momentum pozitif")
        
        sat_puan = 0
        sat_sebepler = []
        
        if maliyet is not None and maliyet > 0:
            kar_yuzde = ((guncel - maliyet) / maliyet) * 100
            
            if kar_yuzde >= 25:
                sat_puan = sat_puan + 3
                sat_sebepler.append("Hedef kar +25%")
            elif kar_yuzde >= 15:
                sat_puan = sat_puan + 2
                sat_sebepler.append("Hedef kar +15%")
            elif kar_yuzde >= 8:
                sat_puan = sat_puan + 1
                sat_sebepler.append("Kar realizasyonu")
            
            if kar_yuzde <= -10:
                sat_puan = sat_puan + 4
                sat_sebepler.append("Stop-loss")
        
        if rsi_v > 75:
            sat_puan = sat_puan + 2
            sat_sebepler.append("RSI asiri alim")
        
        if not macd_v["pozitif"] and macd_v["histogram"] < 0:
            sat_puan = sat_puan + 1
            sat_sebepler.append("MACD negatif")
        
        if mfi_v > 80:
            sat_puan = sat_puan + 1
            sat_sebepler.append("MFI cok yuksek")
        
        if sat_puan >= 3:
            karar = "SAT"
            oncelik = "YUKSEK" if sat_puan >= 5 else "ORTA"
            sebepler = sat_sebepler
        elif al_puan >= 6:
            karar = "AL"
            oncelik = "YUKSEK" if al_puan >= 9 else "ORTA"
            sebepler = al_sebepler
        else:
            karar = "BEKLE"
            oncelik = "DUSUK"
            sebepler = []
        
        return {
            "sembol": sembol,
            "fiyat": round(guncel, 2),
            "al_puan": al_puan,
            "sat_puan": sat_puan,
            "karar": karar,
            "oncelik": oncelik,
            "sebepler": sebepler,
            "gostergeler": {
                "rsi": round(rsi_v, 1),
                "macd": round(macd_v["histogram"], 3),
                "bb_pos": round(bb_v["pozisyon"], 2),
                "mfi": round(mfi_v, 1),
                "roc": round(roc_v, 2)
            },
            "risk_reward": 1.5 if maliyet else None
        }
    except Exception as e:
        return {"sembol": sembol, "fiyat": 0, "karar": "HATA", "sebepler": [str(e)[:50]]}


def portfoy_analiz():
    from portfoy import Portfoy
    p = Portfoy()
    sonuclar = []
    
    for h in p.hisseler:
        s = analiz_uret(h["sembol"], maliyet=h["alis_fiyati"])
        if s and s["karar"] in ["AL", "SAT"]:
            s["tip"] = "PORTFOY"
            s["adet"] = h["adet"]
            sonuclar.append(s)
    
    adaylar = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL", "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"]
    
    for sembol in adaylar:
        if any(h["sembol"] == sembol for h in p.hisseler):
            continue
        s = analiz_uret(sembol)
        if s and s["karar"] == "AL":
            s["tip"] = "ADAY"
            sonuclar.append(s)
    
    return sonuclar


def rapor_yazdir(sonuclar):
    print("=" * 70)
    print("GELISMIS AL-SAT ANALIZ SISTEMI")
    print("=" * 70)
    print("10 gosterge: RSI, MACD, Bollinger, MFI, ROC")
    print("Tarih: " + datetime.now().strftime('%d.%m.%Y %H:%M'))
    print()
    
    if not sonuclar:
        print("Aktif sinyal yok.")
        return
    
    satlar = [s for s in sonuclar if s["karar"] == "SAT"]
    alar = [s for s in sonuclar if s["karar"] == "AL"]
    
    if satlar:
        print("SAT SINYALLERI:")
        print("-" * 70)
        for s in satlar:
            print("")
            print("  " + s['sembol'] + " | " + str(s['fiyat']) + " TL | Oncelik: " + s['oncelik'])
            for sebep in s["sebepler"]:
                print("    - " + sebep)
            g = s["gostergeler"]
            print("  RSI=" + str(g['rsi']) + " | MACD=" + str(g['macd']) + " | MFI=" + str(g['mfi']))
    
    if alar:
        print("")
        print("")
        print("AL SINYALLERI:")
        print("-" * 70)
        for s in alar:
            print("")
            print("  " + s['sembol'] + " | " + str(s['fiyat']) + " TL | Oncelik: " + s['oncelik'])
            for sebep in s["sebepler"]:
                print("    - " + sebep)
            if s.get("risk_reward"):
                print("  Risk/Reward: 1:" + str(s['risk_reward']))
            g = s["gostergeler"]
            print("  RSI=" + str(g['rsi']) + " | MACD=" + str(g['macd']) + " | MFI=" + str(g['mfi']))


if __name__ == "__main__":
    sonuclar = portfoy_analiz()
    rapor_yazdir(sonuclar)
    input("\nCikmak icin Enter'a basin...")
