"""BIST piyasasini toplu tarayip yuksek momentum adaylarini siralar."""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import requests
import yfinance as yf

CACHE_FILE = os.environ.get("PIYASA_TARAMA_CACHE", "piyasa_tarama_cache.json")
CACHE_TTL = int(os.environ.get("PIYASA_TARAMA_CACHE_TTL", "300"))
TIMEOUT = (3, 8)
TRADINGVIEW_URL = "https://scanner.tradingview.com/turkey/scan"


def _yerel_liste() -> list[str]:
    from hisse_listesi import hisse_listesi_getir
    return sorted({str(s).upper().replace(".IS", "") for s in hisse_listesi_getir()})


def _cache_oku() -> dict[str, Any]:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as dosya:
            cache = json.load(dosya)
        if time.time() - float(cache.get("zaman", 0)) < CACHE_TTL:
            return cache
    except (OSError, ValueError, TypeError):
        pass
    return {}


def _cache_yaz(veri: dict[str, Any]) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as dosya:
            json.dump(veri, dosya, ensure_ascii=False, indent=2)
    except OSError:
        pass


def sembolleri_al() -> list[str]:
    """TradingView Turkey tarayicisindan guncel BIST hisse sembollerini al."""
    sorgu = {
        "symbols": {"query": {"types": ["stock"]}, "tickers": []},
        "columns": ["name"],
        "range": [0, 1000],
    }
    try:
        cevap = requests.post(TRADINGVIEW_URL, json=sorgu, timeout=TIMEOUT)
        cevap.raise_for_status()
        semboller = []
        for satir in cevap.json().get("data", []):
            sembol = str(satir.get("d", [""])[0]).upper()
            if sembol.endswith(".IS"):
                sembol = sembol[:-3]
            if sembol and sembol.isalnum() and 3 <= len(sembol) <= 6:
                semboller.append(sembol)
        if len(semboller) >= 150:
            return sorted(set(semboller))
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
    return _yerel_liste()


def _toplu_veri_al(semboller: list[str]) -> list[dict[str, Any]]:
    """Yahoo chart endpointinden sembolleri paralel ve kucuk veri setiyle tara."""
    def tara(sembol: str) -> dict[str, Any] | None:
        try:
            veri = yf.Ticker(f"{sembol}.IS").history(period="3mo", auto_adjust=True)
            if veri is None or len(veri) < 20 or "Close" not in veri or "Volume" not in veri:
                return None
            kapanis = veri["Close"].dropna().astype(float)
            hacim = veri["Volume"].dropna().astype(float)
            if len(kapanis) < 20 or len(hacim) < 20 or kapanis.iloc[-1] <= 0:
                return None
            gunluk = (kapanis.iloc[-1] / kapanis.iloc[-2] - 1) * 100
            ort_hacim = hacim.iloc[-21:-1].mean()
            ma20 = kapanis.tail(20).mean()
            getiriler = kapanis.pct_change().dropna()
            volatilite = getiriler.tail(20).std() * 100
            return {
                "sembol": sembol,
                "fiyat": round(float(kapanis.iloc[-1]), 2),
                "gunluk": round(float(gunluk), 2),
                "hacim": int(hacim.iloc[-1]),
                "hacim_orani": round(float(hacim.iloc[-1] / ort_hacim), 2) if ort_hacim > 0 else 1.0,
                "ma20": round(float(ma20), 2),
                "trend": round(float((kapanis.iloc[-1] / ma20 - 1) * 100), 2) if ma20 else 0.0,
                "volatilite": round(float(volatilite), 2) if volatilite == volatilite else 0.0,
                "veri_gunu": len(kapanis),
            }
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=12) as havuz:
        return [sonuc for sonuc in havuz.map(tara, semboller) if sonuc]


def _puanla(veri: dict[str, Any]) -> dict[str, Any]:
    puan = 0.0
    sebepler = []
    if veri["gunluk"] >= 3:
        puan += 25
        sebepler.append("Guclu gunluk momentum")
    elif veri["gunluk"] > 0:
        puan += min(15, veri["gunluk"] * 3)
    if veri["hacim_orani"] >= 2:
        puan += 30
        sebepler.append("Hacim patlamasi")
    elif veri["hacim_orani"] >= 1.3:
        puan += 18
        sebepler.append("Hacim ortalamanin uzerinde")
    if veri["trend"] > 5:
        puan += 25
        sebepler.append("MA20 uzerinde guclu trend")
    elif veri["trend"] > 0:
        puan += 12
    if 1 <= veri["gunluk"] <= 8 and veri["volatilite"] >= 2:
        puan += 10
        sebepler.append("Yuksek hareket potansiyeli")
    veri["aday_puani"] = round(min(100, puan), 1)
    veri["aday_seviyesi"] = "YUKSEK" if puan >= 70 else "ORTA" if puan >= 45 else "IZLE"
    veri["sebepler"] = sebepler or ["Momentum teyidi zayif"]
    return veri


def piyasa_taramasi(force: bool = False) -> dict[str, Any]:
    cache = {} if force else _cache_oku()
    if cache.get("sonuclar"):
        return cache
    semboller = sembolleri_al()
    sonuclar = [_puanla(veri) for veri in _toplu_veri_al(semboller)]
    sonuclar.sort(key=lambda veri: (veri["aday_puani"], veri["gunluk"], veri["hacim_orani"]), reverse=True)
    sonuc = {
        "sonuclar": sonuclar,
        "adaylar": [veri for veri in sonuclar if veri["aday_puani"] >= 45][:30],
        "sembol_sayisi": len(semboller),
        "veri_sayisi": len(sonuclar),
        "son_guncelleme": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "kaynak": "Toplu piyasa verisi",
    }
    _cache_yaz({"zaman": time.time(), **sonuc})
    return sonuc
