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
            if hacim.iloc[-1] <= 0:
                return None
            gunluk = (kapanis.iloc[-1] / kapanis.iloc[-2] - 1) * 100
            getiri_5g = (kapanis.iloc[-1] / kapanis.iloc[-6] - 1) * 100 if len(kapanis) >= 6 else gunluk
            getiri_20g = (kapanis.iloc[-1] / kapanis.iloc[-21] - 1) * 100 if len(kapanis) >= 21 else getiri_5g
            ort_hacim = hacim.iloc[-21:-1].mean()
            ma20 = kapanis.tail(20).mean()
            getiriler = kapanis.pct_change().dropna()
            volatilite = getiriler.tail(20).std() * 100
            gecmis_sonuclar = []
            for indeks in range(21, len(kapanis) - 5):
                gecmis_fiyat = kapanis.iloc[:indeks + 1]
                gecmis_hacim = hacim.iloc[:indeks + 1]
                ortalama_hacim = gecmis_hacim.iloc[-21:-1].mean()
                gecmis_ma20 = gecmis_fiyat.tail(20).mean()
                gecmis_gunluk = (gecmis_fiyat.iloc[-1] / gecmis_fiyat.iloc[-2] - 1) * 100
                gecmis_5g = (gecmis_fiyat.iloc[-1] / gecmis_fiyat.iloc[-6] - 1) * 100
                gecmis_20g = (gecmis_fiyat.iloc[-1] / gecmis_fiyat.iloc[-21] - 1) * 100
                gecmis_getiriler = gecmis_fiyat.pct_change().dropna().tail(20)
                gecmis = {
                    "gunluk": gecmis_gunluk,
                    "getiri_5g": gecmis_5g,
                    "getiri_20g": gecmis_20g,
                    "hacim_orani": gecmis_hacim.iloc[-1] / ortalama_hacim if ortalama_hacim > 0 else 1.0,
                    "trend": (gecmis_fiyat.iloc[-1] / gecmis_ma20 - 1) * 100 if gecmis_ma20 else 0.0,
                    "volatilite": gecmis_getiriler.std() * 100,
                }
                puan = _puanla(dict(gecmis))["aday_puani"]
                gelecek_getiri = (kapanis.iloc[indeks + 5] / kapanis.iloc[indeks] - 1) * 100
                gecmis_sonuclar.append((puan, gelecek_getiri > 0))
            uygun_sinyaller = [olumlu for puan, olumlu in gecmis_sonuclar if puan >= 45]
            return {
                "sembol": sembol,
                "fiyat": round(float(kapanis.iloc[-1]), 2),
                "gunluk": round(float(gunluk), 2),
                "getiri_5g": round(float(getiri_5g), 2),
                "getiri_20g": round(float(getiri_20g), 2),
                "hacim": int(hacim.iloc[-1]),
                "hacim_orani": round(float(hacim.iloc[-1] / ort_hacim), 2) if ort_hacim > 0 else 1.0,
                "ma20": round(float(ma20), 2),
                "trend": round(float((kapanis.iloc[-1] / ma20 - 1) * 100), 2) if ma20 else 0.0,
                "volatilite": round(float(volatilite), 2) if volatilite == volatilite else 0.0,
                "veri_gunu": len(kapanis),
                "veri_guveni": round(min(100, len(kapanis) / 60 * 100), 1),
                "gecmis_ornek": len(uygun_sinyaller),
                "gecmis_basari": round(sum(uygun_sinyaller) / len(uygun_sinyaller) * 100, 1) if uygun_sinyaller else None,
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
    if veri.get("getiri_5g", 0) > 0:
        puan += 10
        sebepler.append("5 gunluk trend pozitif")
    if veri.get("getiri_20g", 0) > 0:
        puan += 10
        sebepler.append("20 gunluk trend pozitif")
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
    if veri["volatilite"] > 8:
        puan -= min(20, (veri["volatilite"] - 8) * 2)
        sebepler.append("Yuksek volatilite riski")
    if veri["gunluk"] > 9 and veri.get("getiri_5g", 0) < veri["gunluk"]:
        puan -= 8
        sebepler.append("Tek gunluk sivrama riski")
    if veri.get("getiri_5g", 0) > 0 and veri.get("getiri_20g", 0) < 0:
        puan -= 10
        sebepler.append("Orta vadeli trend teyitsiz")
    if veri.get("hacim_orani", 1) < 1.1 and veri["gunluk"] > 2:
        puan -= 8
        sebepler.append("Hacim teyidi zayif")
    veri["risk_uyarisi"] = (
        "Yuksek volatilite" if veri["volatilite"] > 8 else
        "Tek gunluk hareket" if veri["gunluk"] > 6 and veri.get("getiri_5g", 0) < veri["gunluk"] else
        "Orta vade teyitsiz" if veri.get("getiri_20g", 0) < 0 else "Normal"
    )
    veri["aday_puani"] = round(max(0, min(100, puan)), 1)
    gecmis_basari = veri.get("gecmis_basari")
    ornek_sayisi = veri.get("gecmis_ornek", 0)
    if gecmis_basari is not None and ornek_sayisi >= 5:
        veri["guven_skoru"] = round(veri["aday_puani"] * 0.65 + gecmis_basari * 0.35, 1)
    else:
        veri["guven_skoru"] = round(veri["aday_puani"] * 0.75, 1)
        veri["risk_uyarisi"] = "Yetersiz gecmis ornek" if not veri.get("risk_uyarisi") or veri.get("risk_uyarisi") == "Normal" else veri["risk_uyarisi"]
    veri["aday_seviyesi"] = (
        "YUKSEK" if veri["guven_skoru"] >= 70 and ornek_sayisi >= 5 else
        "ORTA" if veri["guven_skoru"] >= 45 and ornek_sayisi >= 3 else
        "IZLE"
    )
    veri["sebepler"] = sebepler or ["Momentum teyidi zayif"]
    return veri


def piyasa_taramasi(force: bool = False) -> dict[str, Any]:
    cache = {} if force else _cache_oku()
    if cache.get("sonuclar"):
        cache.setdefault("adaylar", [veri for veri in cache["sonuclar"] if veri.get("guven_skoru", 0) >= 45][:30])
        cache.setdefault("sembol_sayisi", len(cache["sonuclar"]))
        cache.setdefault("veri_sayisi", len(cache["sonuclar"]))
        return cache
    semboller = sembolleri_al()
    sonuclar = [_puanla(veri) for veri in _toplu_veri_al(semboller)]
    sonuclar.sort(key=lambda veri: (veri["guven_skoru"], veri["aday_puani"], veri["gunluk"]), reverse=True)
    sonuc = {
        "sonuclar": sonuclar,
        "adaylar": [veri for veri in sonuclar if veri.get("guven_skoru", 0) >= 45][:30],
        "sembol_sayisi": len(semboller),
        "veri_sayisi": len(sonuclar),
        "son_guncelleme": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "kaynak": "Toplu piyasa verisi",
    }
    _cache_yaz({"zaman": time.time(), **sonuc})
    return sonuc
