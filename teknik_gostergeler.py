"""BIST hisseleri icin AI yorumunda kullanilan teknik gostergeler."""

from __future__ import annotations

from typing import Any

import numpy as np
import yfinance as yf


def guvenli_veri(sembol: str, period: str = "6mo"):
    try:
        veri = yf.Ticker(f"{sembol.upper().replace('.IS', '')}.IS").history(period=period, auto_adjust=True)
        return veri if veri is not None and len(veri) >= 60 else None
    except Exception:
        return None


def _seri(fiyatlar):
    return np.asarray(fiyatlar, dtype=float)


def _ema(fiyatlar, pencere):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) == 0:
        return 0.0
    alpha = 2 / (pencere + 1)
    sonuc = float(fiyatlar[0])
    for fiyat in fiyatlar[1:]:
        sonuc = alpha * float(fiyat) + (1 - alpha) * sonuc
    return sonuc


def rsi(fiyatlar, pencere=14):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < pencere + 1:
        return 50.0, "N/A"
    fark = np.diff(fiyatlar[-(pencere + 1):])
    kazanc = np.mean(np.maximum(fark, 0))
    kayip = np.mean(np.maximum(-fark, 0))
    deger = 100.0 if kayip == 0 else 100 - (100 / (1 + kazanc / kayip))
    yorum = "Asiri alim" if deger > 70 else "Asiri satim" if deger < 30 else "Normal"
    return round(float(deger), 1), yorum


def macd(fiyatlar):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < 26:
        return 0.0, 0.0, "N/A"
    macd_cizgisi = _ema(fiyatlar, 12) - _ema(fiyatlar, 26)
    histogram = macd_cizgisi - (_ema(fiyatlar[-9:], 9) if len(fiyatlar) >= 9 else macd_cizgisi)
    yorum = "Pozitif" if histogram > 0 else "Negatif"
    return round(macd_cizgisi, 4), round(histogram, 4), yorum


def bollinger(fiyatlar, pencere=20):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < pencere:
        return 0.0, 0.0, 0.0, 0.5, "N/A"
    son = fiyatlar[-pencere:]
    orta = float(np.mean(son))
    sapma = float(np.std(son))
    alt, ust = orta - 2 * sapma, orta + 2 * sapma
    pozisyon = (float(fiyatlar[-1]) - alt) / (ust - alt) if ust > alt else 0.5
    yorum = "Ust bolge" if pozisyon > 0.8 else "Alt bolge" if pozisyon < 0.2 else "Orta bolge"
    return round(ust, 2), round(alt, 2), round(orta, 2), round(float(pozisyon), 2), yorum


def stochastic(fiyatlar, pencere=14):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < pencere:
        return 50.0, "N/A"
    son = fiyatlar[-pencere:]
    deger = (son[-1] - min(son)) / (max(son) - min(son)) * 100 if max(son) > min(son) else 50.0
    return round(float(deger), 1), "Asiri alim" if deger > 80 else "Asiri satim" if deger < 20 else "Normal"


def adx(fiyatlar, pencere=14):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < pencere * 2:
        return 20.0, "N/A"
    getiriler = np.diff(fiyatlar[-(pencere + 1):])
    toplam = np.sum(np.abs(getiriler))
    deger = min(100.0, abs(float(np.sum(getiriler))) / toplam * 100) if toplam else 20.0
    return round(deger, 1), "Guclu trend" if deger > 25 else "Zayif trend"


def williams_r(fiyatlar, pencere=14):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < pencere:
        return -50.0, "N/A"
    son = fiyatlar[-pencere:]
    deger = (max(son) - son[-1]) / (max(son) - min(son)) * -100 if max(son) > min(son) else -50.0
    return round(float(deger), 1), "Asiri alim" if deger > -20 else "Asiri satim" if deger < -80 else "Normal"


def cci(fiyatlar, pencere=20):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < pencere:
        return 0.0, "N/A"
    son = fiyatlar[-pencere:]
    ortalama = float(np.mean(son))
    sapma = float(np.mean(np.abs(son - ortalama)))
    deger = (float(son[-1]) - ortalama) / (0.015 * sapma) if sapma else 0.0
    return round(deger, 1), "Asiri alim" if deger > 100 else "Asiri satim" if deger < -100 else "Normal"


def destek_direnc(fiyatlar, pencere=30):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < pencere:
        return [], []
    son = fiyatlar[-pencere:]
    dusuk, yuksek = float(min(son)), float(max(son))
    aralik = yuksek - dusuk
    destek = [round(dusuk, 2), round(dusuk + aralik * 0.382, 2), round(dusuk + aralik * 0.618, 2)]
    direnc = [round(yuksek - aralik * 0.618, 2), round(yuksek - aralik * 0.382, 2), round(yuksek, 2)]
    return destek, direnc


def formasyon_tespit(fiyatlar):
    fiyatlar = _seri(fiyatlar)
    if len(fiyatlar) < 10:
        return []
    son, onceki = fiyatlar[-5:], fiyatlar[-10:-5]
    sonuc = []
    if np.all(np.diff(son) > 0) and np.all(np.diff(onceki) > 0):
        sonuc.append("Yukselis trendi")
    elif np.all(np.diff(son) < 0) and np.all(np.diff(onceki) < 0):
        sonuc.append("Dusus trendi")
    if son[2] < son[0] and son[2] < son[4] and son[1] > son[2] and son[3] > son[2]:
        sonuc.append("Dip (V) formasyonu")
    return sonuc


def tum_gostergeleri_al(sembol: str) -> dict[str, Any] | None:
    veri = guvenli_veri(sembol)
    if veri is None:
        return None
    kapanis = veri["Close"].to_numpy(dtype=float)
    hacim = veri["Volume"].to_numpy(dtype=float)
    guncel = float(kapanis[-1])
    onceki = float(kapanis[-2])
    rsi_v, rsi_yorum = rsi(kapanis)
    macd_v, macd_hist, macd_yorum = macd(kapanis)
    bb_ust, bb_alt, bb_orta, bb_pos, bb_yorum = bollinger(kapanis)
    stoch_v, stoch_yorum = stochastic(kapanis)
    wr_v, wr_yorum = williams_r(kapanis)
    cci_v, cci_yorum = cci(kapanis)
    adx_v, adx_yorum = adx(kapanis)
    destekler, direncler = destek_direnc(kapanis)
    getiriler = np.diff(kapanis) / kapanis[:-1]
    ort_hacim = float(np.mean(hacim[-20:])) if len(hacim) >= 20 else 0.0
    return {
        "sembol": sembol.upper().replace(".IS", ""), "fiyat": round(guncel, 2),
        "degisim_yuzde": round((guncel / onceki - 1) * 100, 2) if onceki else 0.0,
        "rsi": rsi_v, "rsi_yorum": rsi_yorum, "macd": macd_v,
        "macd_histogram": macd_hist, "macd_yorum": macd_yorum,
        "bollinger_ust": bb_ust, "bollinger_alt": bb_alt, "bollinger_orta": bb_orta,
        "bollinger_pozisyon": bb_pos, "bollinger_yorum": bb_yorum,
        "stochastic": stoch_v, "stochastic_yorum": stoch_yorum,
        "williams": wr_v, "williams_yorum": wr_yorum, "cci": cci_v, "cci_yorum": cci_yorum,
        "adx": adx_v, "adx_yorum": adx_yorum,
        "ma5": round(float(np.mean(kapanis[-5:])), 2), "ma20": round(float(np.mean(kapanis[-20:])), 2),
        "ma50": round(float(np.mean(kapanis[-50:])), 2),
        "ma200": round(float(np.mean(kapanis[-min(200, len(kapanis)):])), 2),
        "cross_yorum": "Golden Cross" if np.mean(kapanis[-50:]) > np.mean(kapanis[-min(200, len(kapanis)):]) else "Death Cross",
        "destekler": destekler, "direncler": direncler, "formasyonlar": formasyon_tespit(kapanis),
        "volatilite": round(float(np.std(getiriler) * np.sqrt(252) * 100), 2),
        "atr": round(float(np.mean(np.abs(np.diff(kapanis)[-14:]))) if len(kapanis) > 14 else 0.0, 2),
        "yuksek_20": round(float(max(kapanis[-20:])), 2), "dusuk_20": round(float(min(kapanis[-20:])), 2),
        "hacim_orani": round(float(hacim[-1] / ort_hacim), 2) if ort_hacim else 1.0,
    }
