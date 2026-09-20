"""BIST hisseleri icin coklu analiz ve puanlama motoru."""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from gunluk_veri_deposu import GunlukVeriDeposu
from hedef_fiyat import hedef_fiyat_tahmin
from kap_ozellikleri import kap_ozelliklerini_ekle
from sektor_veritabani import hisse_sektor
from sosyal_medya import kap_aday_ozeti
from temel_analiz import temel_analiz
from takas_analiz import takas_analiz
from tavan_modeli import (
    MODEL_SURUMU,
    global_tavan_tahminleri,
    stokastik_k,
    tavana_ulasti,
    tavan_egitim_verisi,
    wilder_adx,
    wilder_atr,
    wilder_rsi,
    walk_forward_tavan_istatistigi,
)
from veri_kaynaklari import VeriKaynaklari, tcmb_piyasa_rejimi


ANALIZ_CACHE = os.environ.get("KAPSAMLI_ANALIZ_CACHE", "kapsamli_analiz_cache.json")
TAVAN_SINYAL_GECMISI = os.environ.get("TAVAN_SINYAL_GECMISI", "tavan_sinyal_gecmisi.json")
TAVAN_BACKTEST_RAPORU = os.environ.get(
    "TAVAN_BACKTEST_RAPORU",
    "reports/tavan_backtest_final_tum_bist.json",
)
ANALIZ_CACHE_TTL = int(os.environ.get("KAPSAMLI_ANALIZ_CACHE_TTL", "900"))
KAPSAMLI_ANALIZ_MAX_SEMBOL = int(os.environ.get("KAPSAMLI_ANALIZ_MAX_SEMBOL", "0"))
KAPSAMLI_ANALIZ_TOP_N = int(os.environ.get("KAPSAMLI_ANALIZ_TOP_N", "20"))
TAVAN_MIN_OLASILIK = float(os.environ.get("TAVAN_MIN_OLASILIK", "5"))
TAVAN_MIN_DOKUNMA_OLASILIK = float(os.environ.get("TAVAN_MIN_DOKUNMA_OLASILIK", "10"))
TAVAN_MIN_DEGERLENDIRME_KAPSAMI = float(os.environ.get("TAVAN_MIN_DEGERLENDIRME_KAPSAMI", "80"))
TAVAN_MAX_GUNLUK_GETIRI = float(os.environ.get("TAVAN_MAX_GUNLUK_GETIRI", "8"))
TAVAN_MAX_5G_GETIRI = float(os.environ.get("TAVAN_MAX_5G_GETIRI", "25"))
TAVAN_MAX_RSI = float(os.environ.get("TAVAN_MAX_RSI", "80"))
TAVAN_MIN_HAM_KAPANMA = float(os.environ.get("TAVAN_MIN_HAM_KAPANMA", "60"))
TAVAN_MIN_HAM_DOKUNMA = float(os.environ.get("TAVAN_MIN_HAM_DOKUNMA", "60"))
TAVAN_MIN_BEKLENEN_GETIRI = float(os.environ.get("TAVAN_MIN_BEKLENEN_GETIRI", "0"))
TAVAN_DEVAM_MIN_OLASILIK = float(os.environ.get("TAVAN_DEVAM_MIN_OLASILIK", "15"))
TAVAN_DEVAM_MIN_DOKUNMA = float(os.environ.get("TAVAN_DEVAM_MIN_DOKUNMA", "20"))
TAVAN_DEVAM_MIN_HACIM = float(os.environ.get("TAVAN_DEVAM_MIN_HACIM", "2"))
TAVAN_YUKSEK_MIN_OLASILIK = float(os.environ.get("TAVAN_YUKSEK_MIN_OLASILIK", "15"))
TAVAN_YUKSEK_MIN_DOKUNMA = float(os.environ.get("TAVAN_YUKSEK_MIN_DOKUNMA", "20"))
TAVAN_YUKSEK_MIN_HAM_GUVEN = float(os.environ.get("TAVAN_YUKSEK_MIN_HAM_GUVEN", "80"))
TAVAN_YUKSEK_MIN_BEKLENEN_GETIRI = float(os.environ.get("TAVAN_YUKSEK_MIN_BEKLENEN_GETIRI", "0.5"))
TAVAN_YUKSEK_MAX_DUSUS_RISKI = float(os.environ.get("TAVAN_YUKSEK_MAX_DUSUS_RISKI", "3"))
TAVAN_KAP_OZELLIKLERI = os.environ.get("TAVAN_KAP_OZELLIKLERI", "0") == "1"
ANALIZ_AGIRLIKLARI = {
    "teknik": 50,
    "temel": 10,
    "risk": 10,
    "takas": 10,
    "hedef": 10,
    "trade": 10,
}

TEKNIK_GOSTERGE_AGIRLIKLARI = {
    "ma": 12,
    "macd": 18,
    "bollinger": 10,
    "rsi": 18,
    "stokastik": 8,
    "fibonacci": 8,
    "ichimoku": 10,
    "atr": 5,
    "standart_sapma": 5,
    "adx": 6,
}


def _sayisal(deger: Any, varsayilan: float = 0.0) -> float:
    try:
        sonuc = float(deger)
        return sonuc if math.isfinite(sonuc) else varsayilan
    except (TypeError, ValueError):
        return varsayilan


def _sinirla(deger: float, alt: float = 0.0, ust: float = 100.0) -> float:
    return round(max(alt, min(ust, _sayisal(deger))), 1)


def _gunluk_veri_tamamlandi_mi(veri_tarihi: str, simdi: datetime | None = None) -> bool:
    simdi = simdi or datetime.now(ZoneInfo("Europe/Istanbul"))
    if simdi.tzinfo is None:
        simdi = simdi.replace(tzinfo=ZoneInfo("Europe/Istanbul"))
    else:
        simdi = simdi.astimezone(ZoneInfo("Europe/Istanbul"))
    try:
        tarih = datetime.strptime(veri_tarihi, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return False
    if tarih < simdi.date():
        return True
    return bool(tarih == simdi.date() and simdi.weekday() < 5 and (simdi.hour, simdi.minute) >= (18, 10))


def _veri_guven_skoru(rapor: dict[str, Any]) -> float:
    mevcut = sum(1 for alan in ANALIZ_AGIRLIKLARI if rapor.get(alan) is not None)
    return round(mevcut / len(ANALIZ_AGIRLIKLARI) * 100, 1)


def _teknik_gosterge_skorlari(
    fiyat: float,
    kapanis: Any,
    yuksek: Any,
    dusuk: Any,
    ema21: Any,
    ema50: Any,
    macd: Any,
    sinyal: Any,
    rsi: Any,
    orta: Any,
    ust: Any,
    alt: Any,
) -> dict[str, float]:
    ma200 = kapanis.rolling(200).mean().iloc[-1]
    ma_degerleri = [ema21.iloc[-1], ema50.iloc[-1]]
    if not math.isnan(float(ma200)):
        ma_degerleri.append(ma200)
    ma_skoru = sum(fiyat > _sayisal(deger) for deger in ma_degerleri) / len(ma_degerleri) * 100

    macd_skoru = 80 if macd.iloc[-1] > sinyal.iloc[-1] else 25
    if macd.iloc[-1] > 0:
        macd_skoru += 20
    macd_skoru = _sinirla(macd_skoru)

    bant_genisligi = ust.iloc[-1] - alt.iloc[-1]
    bant_pozisyonu = (fiyat - alt.iloc[-1]) / bant_genisligi if bant_genisligi > 0 else 0.5
    bollinger_skoru = 100 if 0.35 <= bant_pozisyonu <= 0.75 else 80 if 0.2 <= bant_pozisyonu <= 0.9 else 55

    rsi_degeri = float(rsi.iloc[-1])
    rsi_skoru = 100 if 45 <= rsi_degeri <= 65 else 82 if 30 <= rsi_degeri < 45 or 65 < rsi_degeri <= 70 else 62

    stokastik = stokastik_k(yuksek, dusuk, kapanis, 14)
    stokastik_degeri = float(stokastik.iloc[-1])
    stokastik_skoru = 100 if 20 <= stokastik_degeri <= 80 else 72
    if stokastik_degeri < 20 and stokastik.iloc[-1] > stokastik.iloc[-2]:
        stokastik_skoru = 85

    fib_yuksek = float(kapanis.tail(120).max())
    fib_dusuk = float(kapanis.tail(120).min())
    fib_aralik = fib_yuksek - fib_dusuk
    fib_orani = (fiyat - fib_dusuk) / fib_aralik if fib_aralik > 0 else 0.5
    fib_seviyeleri = (0.236, 0.382, 0.5, 0.618, 0.786)
    fib_skoru = 85 if any(abs(fib_orani - seviye) <= 0.04 for seviye in fib_seviyeleri) else 72 if fib_orani >= 0.618 else 55

    high = yuksek.astype(float)
    low = dusuk.astype(float)
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    bulut_ust = max(span_a.iloc[-1], span_b.iloc[-1])
    bulut_alt = min(span_a.iloc[-1], span_b.iloc[-1])
    ichimoku_puan = (
        sum((fiyat > bulut_ust, tenkan.iloc[-1] > kijun.iloc[-1], span_a.iloc[-1] > span_b.iloc[-1])) / 3 * 100
        if np.isfinite([bulut_ust, bulut_alt]).all() else 50
    )

    atr = wilder_atr(high, low, kapanis, 14)
    atr_yuzde = float(atr.iloc[-1] / fiyat * 100) if fiyat else 0
    atr_skoru = 100 if atr_yuzde <= 2 else 80 if atr_yuzde <= 4 else 60 if atr_yuzde <= 6 else 35

    standart_sapma = float(kapanis.pct_change().rolling(20).std().iloc[-1] * np.sqrt(252) * 100)
    standart_sapma_skoru = 100 if standart_sapma <= 20 else 80 if standart_sapma <= 35 else 55 if standart_sapma <= 50 else 30

    adx, _, _ = wilder_adx(high, low, kapanis, 14)
    adx_degeri = float(adx.iloc[-1]) if np.isfinite(adx.iloc[-1]) else 0.0
    adx_skoru = _sinirla(35 + adx_degeri * 1.8)
    return {
        "ma": _sinirla(ma_skoru),
        "macd": macd_skoru,
        "bollinger": _sinirla(bollinger_skoru),
        "rsi": _sinirla(rsi_skoru),
        "stokastik": _sinirla(stokastik_skoru),
        "fibonacci": _sinirla(fib_skoru),
        "ichimoku": _sinirla(ichimoku_puan),
        "atr": _sinirla(atr_skoru),
        "standart_sapma": _sinirla(standart_sapma_skoru),
        "adx": adx_skoru,
    }


def _yarin_tavan_adayi_skoru(
    kapanis: Any,
    yuksek: Any,
    dusuk: Any,
    hacim: Any,
    macd: Any,
    sinyal: Any,
    rsi: Any,
    gosterge_skorlari: dict[str, float],
) -> tuple[float, list[str]]:
    """Ertesi gun guclu hareket adayi icin siralama skoru uretir.

    Bu skor tavan tahmini veya garanti degildir; sadece mevcut kapanisa kadar
    bilinen verilerle adaylari siralar.
    """
    son = float(kapanis.iloc[-1])
    onceki = float(kapanis.iloc[-2])
    gunluk = (son / onceki - 1) * 100 if onceki > 0 else 0.0
    getiri_5g = (son / float(kapanis.iloc[-6]) - 1) * 100 if len(kapanis) >= 6 else gunluk
    getiri_20g = (son / float(kapanis.iloc[-21]) - 1) * 100 if len(kapanis) >= 21 else getiri_5g
    ortalama_hacim = float(hacim.iloc[-21:-1].mean()) if hacim is not None else 0.0
    hacim_orani = float(hacim.iloc[-1] / ortalama_hacim) if ortalama_hacim > 0 else 1.0
    gun_araligi = float(yuksek.iloc[-1] - dusuk.iloc[-1])
    kapanis_gucu = (son - float(dusuk.iloc[-1])) / gun_araligi if gun_araligi > 0 else 0.5
    direnç = float(kapanis.iloc[-21:-1].max()) if len(kapanis) >= 21 else son

    puan = 0.0
    sebepler = []
    if 2 <= gunluk <= 8:
        puan += 15
        sebepler.append("Gunluk momentum")
    elif gunluk > TAVAN_MAX_GUNLUK_GETIRI:
        puan -= 25
        sebepler.append("Asiri gunluk hareket")
    elif gunluk > 0:
        puan += 7
    if getiri_5g >= 5:
        puan += 15
        sebepler.append("5 gunluk ivme")
    elif getiri_5g > 0:
        puan += 7
    if getiri_20g > 0:
        puan += 5
    if hacim_orani >= 2:
        puan += 25
        sebepler.append("Hacim patlamasi")
    elif hacim_orani >= 1.4:
        puan += 14
    if son >= direnç:
        puan += 15
        sebepler.append("20 gunluk kirilim")
    if kapanis_gucu >= 0.8:
        puan += 10
        sebepler.append("Gun ici kapanis guclu")
    elif kapanis_gucu >= 0.6:
        puan += 5
    if macd.iloc[-1] > sinyal.iloc[-1] and rsi.iloc[-1] >= 50:
        puan += 10
        sebepler.append("MACD ve RSI teyidi")
    if getiri_5g >= TAVAN_MAX_5G_GETIRI:
        puan -= 15
        sebepler.append("Asiri 5 gunluk hareket")
    if rsi.iloc[-1] > TAVAN_MAX_RSI:
        puan -= 15
        sebepler.append("Asiri RSI")
    if gosterge_skorlari.get("adx", 0) >= 65:
        puan += 5
        sebepler.append("ADX trend teyidi")
    return _sinirla(puan), sebepler


def _kisa_gecmis_kilitli_teknik(
    veri: Any,
    kaynak_bilgisi: dict[str, Any],
) -> dict[str, Any] | None:
    gerekli = {"Open", "High", "Low", "Close", "Volume"}
    if veri is None or len(veri) < 2 or not gerekli.issubset(veri.columns) or len(veri) >= 60:
        return None
    son = veri.iloc[-1]
    fiyatlar = [float(son[alan]) for alan in ("Open", "High", "Low", "Close")]
    if not np.isfinite(fiyatlar).all() or min(fiyatlar) <= 0 or max(fiyatlar) - min(fiyatlar) > 1e-8:
        return None
    hacim = float(son["Volume"])
    if not np.isfinite(hacim) or hacim <= 0:
        return None
    son_tarih = veri.index[-1]
    veri_yasi_gun = max(0, (datetime.now().date() - son_tarih.date()).days)
    if veri_yasi_gun > 4:
        return None
    onceki_kapanis = float(veri["Close"].iloc[-2])
    if onceki_kapanis <= 0 or not tavana_ulasti(onceki_kapanis, fiyatlar[-1]):
        return None
    gunluk_getiri = (fiyatlar[-1] / onceki_kapanis - 1) * 100
    return {
        "puan": 50.0,
        "fiyat": round(fiyatlar[-1], 2),
        "onceki_kapanis": round(onceki_kapanis, 2),
        "son_islem_tarihi": son_tarih.strftime("%Y-%m-%d"),
        "gunluk_veri_tamamlandi": _gunluk_veri_tamamlandi_mi(son_tarih.strftime("%Y-%m-%d")),
        "veri_kaynagi": kaynak_bilgisi["kaynak"],
        "yedek_veri_kullanildi": kaynak_bilgisi["yedek_kullanildi"],
        "veri_yasi_gun": veri_yasi_gun,
        "veri_bayat": False,
        "gunluk_getiri": round(gunluk_getiri, 2),
        "getiri_5g": gunluk_getiri,
        "getiri_20g": gunluk_getiri,
        "rsi": None,
        "yarin_tavan_adayi_skoru": 100.0,
        "tavan_adayi_sebepleri": ["Kisa fiyat gecmisinde kilitli kapanis"],
        "tavan_modeli_olasiligi": None,
        "tavan_modeli_ham_olasiligi": None,
        "tavan_modeli_precision": None,
        "tavana_dokunma_olasiligi": None,
        "tavana_dokunma_precision": None,
        "tavan_modeli_recall": None,
        "tavan_modeli_brier": None,
        "tavan_modeli_surumu": None,
        "tavan_modeli_ornek": 0,
        "tavan_siralama_skoru": 100.0,
        "hacim": int(hacim),
        "hacim_orani": 1.0,
        "yeni_halka_arz_tavan_devami": True,
        "sebepler": ["Kisa fiyat gecmisinde kilitli kapanis"],
    }


def _teknik_ve_trade(sembol: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        veri, kaynak_bilgisi = VeriKaynaklari().tarihsel_veri_al(sembol, periyot="1y", auto_adjust=False)
        if veri is None or "Close" not in veri.columns:
            return None, None
        if TAVAN_KAP_OZELLIKLERI:
            veri = kap_ozelliklerini_ekle(veri, sembol)
        if len(veri) < 60:
            return _kisa_gecmis_kilitli_teknik(veri, kaynak_bilgisi), None
        kapanis = veri["Close"].dropna().astype(float)
        hacim = veri["Volume"].fillna(0).astype(float) if "Volume" in veri else None
        if len(kapanis) < 60 or kapanis.iloc[-1] <= 0:
            return None, None

        ema21 = kapanis.ewm(span=21, adjust=False).mean()
        ema50 = kapanis.ewm(span=50, adjust=False).mean()
        macd = kapanis.ewm(span=12, adjust=False).mean() - kapanis.ewm(span=26, adjust=False).mean()
        sinyal = macd.ewm(span=9, adjust=False).mean()
        rsi = wilder_rsi(kapanis, 14).fillna(50)
        orta = kapanis.rolling(20).mean()
        sapma = kapanis.rolling(20).std()
        ust = orta + 2 * sapma
        alt = orta - 2 * sapma
        getiriler = kapanis.pct_change().dropna()
        hacim_orani = 1.0
        if hacim is not None:
            ortalama = hacim.iloc[-21:-1].mean()
            hacim_orani = float(hacim.iloc[-1] / ortalama) if ortalama > 0 else 1.0

        fiyat = float(kapanis.iloc[-1])
        onceki_fiyat = float(kapanis.iloc[-2])
        son_islem_tarihi = veri.index[-1].strftime("%Y-%m-%d")
        veri_yasi_gun = max(0, (datetime.now().date() - veri.index[-1].date()).days)
        gunluk_getiri = (fiyat / onceki_fiyat - 1) * 100 if onceki_fiyat > 0 else 0.0
        getiri_5g = (fiyat / float(kapanis.iloc[-6]) - 1) * 100 if len(kapanis) >= 6 else gunluk_getiri
        getiri_20g = (fiyat / float(kapanis.iloc[-21]) - 1) * 100 if len(kapanis) >= 21 else getiri_5g
        direnc = float(kapanis.iloc[-21:-1].max())
        bant = float((kapanis.tail(10).max() - kapanis.tail(10).min()) / fiyat)
        bb_width = float((ust.iloc[-1] - alt.iloc[-1]) / orta.iloc[-1]) if orta.iloc[-1] else 1.0
        macd_kesisim = macd.iloc[-1] > sinyal.iloc[-1] and macd.iloc[-2] <= sinyal.iloc[-2]
        breakout = fiyat > direnc
        rsi_donus = 30 < rsi.iloc[-1] < 60 and rsi.iloc[-1] > rsi.iloc[-2]

        yuksek = veri["High"].fillna(kapanis) if "High" in veri else kapanis
        dusuk = veri["Low"].fillna(kapanis) if "Low" in veri else kapanis
        gosterge_skorlari = _teknik_gosterge_skorlari(
            fiyat, kapanis, yuksek, dusuk,
            ema21, ema50, macd, sinyal, rsi, orta, ust, alt,
        )
        yarin_tavan_skoru, tavan_sebepleri = _yarin_tavan_adayi_skoru(
            kapanis, yuksek, dusuk, hacim, macd, sinyal, rsi, gosterge_skorlari,
        )
        tavan_egitim = tavan_egitim_verisi(veri)
        tavan_modeli = walk_forward_tavan_istatistigi(veri, tavan_egitim)
        teknik_puan = sum(
            gosterge_skorlari[alan] * agirlik
            for alan, agirlik in TEKNIK_GOSTERGE_AGIRLIKLARI.items()
        ) / sum(TEKNIK_GOSTERGE_AGIRLIKLARI.values())
        sebepler = []
        if fiyat > ema21.iloc[-1] > ema50.iloc[-1]:
            sebepler.append("EMA trendi yukari")
        if macd.iloc[-1] > sinyal.iloc[-1]:
            sebepler.append("MACD pozitif")
        if macd_kesisim:
            sebepler.append("MACD yukari kesisim")
        if rsi_donus:
            sebepler.append("RSI donus teyidi")
        if breakout:
            sebepler.append("20 gunluk direnc kirilimi")
        if hacim_orani >= 3:
            sebepler.append("3x hacim patlamasi")
        if bb_width < 0.05:
            sebepler.append("Bollinger sikismasi")

        trade_puan = 0.0
        trade_sebepler = []
        if 1.2 <= hacim_orani:
            trade_puan += 25
            trade_sebepler.append("Hacim teyidi")
        if breakout:
            trade_puan += 25
            trade_sebepler.append("Kapanis bazli breakout")
        if 30 <= rsi.iloc[-1] <= 70:
            trade_puan += 15
        if macd.iloc[-1] > sinyal.iloc[-1]:
            trade_puan += 15
        if bant < 0.05:
            trade_puan += 10
            trade_sebepler.append("Dar bant")
        if _sayisal(getiriler.tail(20).std() * 100) > 8:
            trade_puan -= 15
            trade_sebepler.append("Yuksek oynaklik")

        teknik = {
            "puan": _sinirla(teknik_puan),
            "fiyat": round(fiyat, 2),
            "onceki_kapanis": round(onceki_fiyat, 2),
            "son_islem_tarihi": son_islem_tarihi,
            "gunluk_veri_tamamlandi": _gunluk_veri_tamamlandi_mi(son_islem_tarihi),
            "veri_kaynagi": kaynak_bilgisi["kaynak"],
            "yedek_veri_kullanildi": kaynak_bilgisi["yedek_kullanildi"],
            "veri_yasi_gun": veri_yasi_gun,
            "veri_bayat": veri_yasi_gun > 4,
            "gunluk_getiri": round(gunluk_getiri, 2),
            "getiri_5g": round(getiri_5g, 2),
            "getiri_20g": round(getiri_20g, 2),
            "rsi": round(float(rsi.iloc[-1]), 2),
            "macd": round(float(macd.iloc[-1]), 4),
            "macd_sinyal": round(float(sinyal.iloc[-1]), 4),
            "ema21": round(float(ema21.iloc[-1]), 2),
            "ema50": round(float(ema50.iloc[-1]), 2),
            "gosterge_skorlari": gosterge_skorlari,
            "yarin_tavan_adayi_skoru": yarin_tavan_skoru,
            "tavan_adayi_sebepleri": tavan_sebepleri,
            "tavan_modeli_olasiligi": tavan_modeli["olasilik"],
            "tavan_modeli_ham_olasiligi": tavan_modeli.get("ham_olasilik"),
            "tavan_modeli_precision": tavan_modeli["precision"],
            "tavana_dokunma_olasiligi": tavan_modeli.get("dokunma_olasiligi"),
            "tavana_dokunma_precision": tavan_modeli.get("dokunma_precision"),
            "tavan_modeli_recall": tavan_modeli.get("recall"),
            "tavan_modeli_brier": tavan_modeli.get("brier"),
            "tavan_modeli_surumu": tavan_modeli.get("model_surumu"),
            "tavan_modeli_ornek": tavan_modeli["ornek"],
            "hacim": int(hacim.iloc[-1]) if hacim is not None else None,
            "hacim_orani": round(hacim_orani, 2),
            "breakout": breakout,
            "dar_bant": bant < 0.05,
            "bollinger_sikisma": bb_width < 0.05,
            "volatilite": round(float(getiriler.tail(60).std() * np.sqrt(252) * 100), 2),
            "sebepler": sebepler,
            "_tavan_egitim_verisi": tavan_egitim,
        }
        trade = {
            "puan": _sinirla(trade_puan),
            "karar": "TRADE ADAYI" if trade_puan >= 60 else "IZLE" if trade_puan >= 40 else "BEKLE",
            "sebepler": trade_sebepler,
        }
        return teknik, trade
    except Exception:
        return None, None


def _temel_puan(temel: dict[str, Any] | None) -> float | None:
    if not temel:
        return None
    puan = 0.0
    sayac = 0
    for deger, esikler in (
        (temel.get("fk"), (10, 15, 25)),
        (temel.get("pddd"), (1, 2, 3)),
    ):
        if deger is not None:
            sayac += 1
            puan += 25 if 0 < deger < esikler[0] else 18 if deger < esikler[1] else 8 if deger < esikler[2] else 0
    roe = temel.get("roe")
    buyume = temel.get("gelir_buyumesi")
    if roe is not None:
        sayac += 1
        puan += 25 if roe >= 20 else 18 if roe >= 15 else 8 if roe > 0 else 0
    if buyume is not None:
        sayac += 1
        puan += 25 if buyume >= 15 else 15 if buyume > 0 else 0
    return _sinirla(puan / max(1, sayac) * 4) if sayac else None


def _risk_puani(teknik: dict[str, Any] | None) -> tuple[float | None, str]:
    if not teknik:
        return None, "VERI YOK"
    volatilite = _sayisal(teknik.get("volatilite"))
    seviye = "YUKSEK" if volatilite >= 50 else "ORTA" if volatilite >= 30 else "DUSUK"
    return _sinirla(100 - min(100, volatilite * 2.5)), seviye


def _takas_puani(takas: dict[str, Any] | None) -> float | None:
    if not takas:
        return None
    puan = 50.0
    hacim = takas.get("hacim_orani")
    kurumsal = takas.get("kurumsal_oran")
    yabanci = takas.get("yabanci_oran")
    if hacim is not None:
        puan += 20 if hacim >= 1.5 else 10 if hacim >= 1.1 else -5
    if kurumsal is not None:
        puan += 15 if kurumsal >= 30 else 8 if kurumsal >= 10 else 0
    if yabanci is not None:
        puan += 15 if yabanci >= 20 else 5 if yabanci >= 10 else 0
    return _sinirla(puan)


def _hedef_puani(hedef: dict[str, Any] | None) -> float | None:
    if not hedef:
        return None
    return _sinirla(50 + _sayisal(hedef.get("degisim")) * 4)


def _guclu_tavan_devami_mi(teknik: dict[str, Any]) -> bool:
    onceki_kapanis = _sayisal(teknik.get("onceki_kapanis"))
    fiyat = _sayisal(teknik.get("fiyat"))
    if onceki_kapanis <= 0 or fiyat <= 0 or not tavana_ulasti(onceki_kapanis, fiyat):
        return False
    return bool(
        _sayisal(teknik.get("tavan_modeli_olasiligi")) >= TAVAN_DEVAM_MIN_OLASILIK
        and _sayisal(teknik.get("tavana_dokunma_olasiligi")) >= TAVAN_DEVAM_MIN_DOKUNMA
        and _sayisal(teknik.get("hacim_orani"), 1) >= TAVAN_DEVAM_MIN_HACIM
    )


def _tavan_devami_mi(teknik: dict[str, Any]) -> bool:
    onceki_kapanis = _sayisal(teknik.get("onceki_kapanis"))
    fiyat = _sayisal(teknik.get("fiyat"))
    return bool(
        _guclu_tavan_devami_mi(teknik)
        or (
            onceki_kapanis > 0
            and fiyat > 0
            and tavana_ulasti(onceki_kapanis, fiyat)
            and _sayisal(teknik.get("getiri_5g")) <= 0
            and _sayisal(teknik.get("tavan_modeli_olasiligi")) >= TAVAN_MIN_OLASILIK
            and _sayisal(teknik.get("tavana_dokunma_olasiligi")) >= TAVAN_MIN_DOKUNMA_OLASILIK
            and _sayisal(teknik.get("hacim_orani"), 1) >= 1.1
        )
    )


def _tavan_adayi_elenme_nedenleri(veri: dict[str, Any]) -> list[str]:
    teknik = veri.get("teknik") or {}
    if not teknik:
        return ["Teknik veri yok"]
    if teknik.get("yeni_halka_arz_tavan_devami"):
        return []
    nedenler = []
    tavan_devami = _tavan_devami_mi(teknik)
    if teknik.get("veri_bayat", False):
        nedenler.append("Veri bayat")
    if (
        _sayisal(teknik.get("tavan_modeli_olasiligi")) < TAVAN_MIN_OLASILIK
        or _sayisal(teknik.get("tavana_dokunma_olasiligi")) < TAVAN_MIN_DOKUNMA_OLASILIK
    ):
        nedenler.append("Model olasiligi esik altinda")
    if not tavan_devami and _sayisal(teknik.get("gunluk_getiri")) <= 0:
        nedenler.append("Gunluk momentum pozitif degil")
    if not tavan_devami and _sayisal(teknik.get("getiri_5g")) <= 0:
        nedenler.append("5 gunluk momentum pozitif degil")
    if _sayisal(teknik.get("hacim_orani"), 1) < 1.1:
        nedenler.append("Hacim teyidi 1.1 altinda")
    if not tavan_devami and _sayisal(teknik.get("gunluk_getiri")) >= TAVAN_MAX_GUNLUK_GETIRI:
        nedenler.append(f"Gunluk getiri %{TAVAN_MAX_GUNLUK_GETIRI:g} ve uzerinde")
    if _sayisal(teknik.get("getiri_5g")) >= TAVAN_MAX_5G_GETIRI:
        nedenler.append(f"5 gunluk getiri %{TAVAN_MAX_5G_GETIRI:g} ve uzerinde")
    if teknik.get("rsi") is not None and _sayisal(teknik.get("rsi")) > TAVAN_MAX_RSI:
        nedenler.append(f"RSI {TAVAN_MAX_RSI:g} uzerinde")
    if teknik.get("tavan_modeli_kapsami") == "GLOBAL":
        if _sayisal(teknik.get("tavan_modeli_ham_olasiligi")) < TAVAN_MIN_HAM_KAPANMA:
            nedenler.append(f"Ham kapanma guveni %{TAVAN_MIN_HAM_KAPANMA:g} altinda")
        if _sayisal(teknik.get("tavana_dokunma_ham_olasiligi")) < TAVAN_MIN_HAM_DOKUNMA:
            nedenler.append(f"Ham dokunma guveni %{TAVAN_MIN_HAM_DOKUNMA:g} altinda")
        if _sayisal(teknik.get("beklenen_getiri")) < TAVAN_MIN_BEKLENEN_GETIRI:
            nedenler.append(f"Beklenen getiri %{TAVAN_MIN_BEKLENEN_GETIRI:g} altinda")
    return nedenler


def _tavan_adaylarini_sec(analizler: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Model olasiligina gore ilk bes adayi secip eksik modeli sona atar."""
    uygunlar = [
        veri for veri in analizler
        if not _tavan_adayi_elenme_nedenleri(veri)
    ]
    return sorted(
        uygunlar,
        key=lambda veri: (
            _sayisal(
                (veri.get("teknik") or {}).get("tavan_nihai_skoru"),
                _sayisal((veri.get("teknik") or {}).get("tavan_siralama_skoru"), -1),
            ),
            _sayisal((veri.get("teknik") or {}).get("tavan_siralama_skoru"), -1),
            _sayisal((veri.get("teknik") or {}).get("tavan_modeli_olasiligi"), -1),
            _sayisal((veri.get("teknik") or {}).get("tavana_dokunma_olasiligi"), -1),
            _sayisal((veri.get("teknik") or {}).get("goreceli_guc_skoru"), -1),
            _sayisal((veri.get("teknik") or {}).get("hacim_orani"), -1),
            _sayisal((veri.get("teknik") or {}).get("tavan_modeli_precision"), -1),
            _sayisal((veri.get("teknik") or {}).get("yarin_tavan_adayi_skoru")),
        ),
        reverse=True,
    )[:max(1, limit)]


def _tavan_guven_eksikleri(aday: dict[str, Any]) -> list[str]:
    teknik = aday.get("teknik") or {}
    intraday = teknik.get("intraday") or {}
    kap = aday.get("kap_teyidi") or {}
    eksikler = []
    if teknik.get("gunluk_veri_tamamlandi") is not True:
        eksikler.append("Gunluk mum henuz kapanmadi")
    if not (teknik.get("fiyat_teyidi") or {}).get("guvenilir", False):
        eksikler.append("Fiyat ikinci kaynaktan dogrulanmadi")
    if teknik.get("tavan_modeli_kapsami") != "GLOBAL":
        eksikler.append("Yeterli gecmise sahip global model yok")
    if teknik.get("yeni_halka_arz_tavan_devami", False):
        eksikler.append("Kisa fiyat gecmisi; istatistiksel guven olusmadi")
    if (
        _sayisal(teknik.get("tavan_modeli_olasiligi")) < TAVAN_YUKSEK_MIN_OLASILIK
        or _sayisal(teknik.get("tavana_dokunma_olasiligi")) < TAVAN_YUKSEK_MIN_DOKUNMA
    ):
        eksikler.append("Kalibre model olasiligi yuksek guven esiginin altinda")
    if (
        _sayisal(teknik.get("tavan_modeli_ham_olasiligi")) < TAVAN_YUKSEK_MIN_HAM_GUVEN
        or _sayisal(teknik.get("tavana_dokunma_ham_olasiligi")) < TAVAN_YUKSEK_MIN_HAM_GUVEN
    ):
        eksikler.append("Ham model guveni yetersiz")
    if _sayisal(teknik.get("beklenen_getiri")) < TAVAN_YUKSEK_MIN_BEKLENEN_GETIRI:
        eksikler.append("Beklenen getiri yetersiz")
    if _sayisal(teknik.get("dusus_riski"), 100) > TAVAN_YUKSEK_MAX_DUSUS_RISKI:
        eksikler.append("Dusme riski yuksek veya hesaplanamadi")
    if not 0 < _sayisal(teknik.get("gunluk_getiri")) < TAVAN_MAX_GUNLUK_GETIRI:
        eksikler.append("Gunluk hareket erken giris araliginda degil")
    if not 0 < _sayisal(teknik.get("getiri_5g")) < TAVAN_MAX_5G_GETIRI:
        eksikler.append("5 gunluk momentum uygun degil")
    if _sayisal(teknik.get("hacim_orani"), 1) < 1.5:
        eksikler.append("Gunluk hacim teyidi 1.5x altinda")
    if teknik.get("rsi") is not None and _sayisal(teknik.get("rsi")) > 75:
        eksikler.append("RSI asiri alim bolgesinde")
    if _sayisal(intraday.get("momentum_15dk"), -100) <= 0:
        eksikler.append("Pozitif 15 dakika momentumu yok")
    if _sayisal(intraday.get("hacim_orani")) < 1.2:
        eksikler.append("Seans ici hacim teyidi 1.2x altinda")
    if _sayisal(kap.get("net_sinyal")) < 0:
        eksikler.append("KAP haber akisi negatif")
    return eksikler


def _yuksek_guvenli_tavan_adayi_mi(aday: dict[str, Any]) -> bool:
    """Yalniz birbirinden bagimsiz model, risk, hacim ve seans teyitleri uyusursa True doner."""
    return not _tavan_guven_eksikleri(aday)


def _backtest_kabul_durumu() -> dict[str, Any]:
    try:
        with open(TAVAN_BACKTEST_RAPORU, "r", encoding="utf-8") as dosya:
            rapor = json.load(dosya)
        kabul_testi = rapor.get("ayrilmis_kabul_testi") or {}
        metadata = rapor.get("metadata") or {}
        veri_kapsami = rapor.get("veri_kapsami") or {}
        uretim_zamani = datetime.fromisoformat(str(metadata.get("uretim_zamani")))
        if uretim_zamani.tzinfo is None:
            uretim_zamani = uretim_zamani.replace(tzinfo=timezone.utc)
        rapor_yasi_gun = (datetime.now(timezone.utc) - uretim_zamani).total_seconds() / 86400
        rapor_gecerli = bool(
            kabul_testi.get("durum") == "tamamlandi"
            and metadata.get("rapor_sema_surumu") == 3
            and metadata.get("model_surumu") == MODEL_SURUMU
            and veri_kapsami.get("kapsam_yuzde", 0) >= 90
            and veri_kapsami.get("kullanilan_sembol", 0) >= 100
            and (rapor.get("ozet") or {}).get("test_gunu", 0) >= 120
            and 0 <= rapor_yasi_gun <= 14
        )
        durum = kabul_testi.get("durum", "rapor_gecersiz") if rapor_gecerli else "rapor_gecersiz"
    except (OSError, ValueError, TypeError):
        kabul_testi = {}
        rapor_gecerli = False
        durum = "rapor_yok"
    return {
        "kabul": rapor_gecerli and kabul_testi.get("kabul") is True,
        "durum": durum,
        "rapor": TAVAN_BACKTEST_RAPORU,
        "detay": kabul_testi,
    }


def _tavan_listelerini_siniflandir(
    adaylar: list[dict[str, Any]],
    limit: int = 5,
    model_kabul: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    yuksek_guven, izleme = [], []
    for aday in adaylar:
        teknik = aday.get("teknik") or {}
        eksikler = _tavan_guven_eksikleri(aday)
        if not model_kabul:
            eksikler.insert(0, "Ayrilmis backtest kabul edilmedi")
        teknik["tavan_guven_eksikleri"] = eksikler
        teknik["tavan_guven_seviyesi"] = "YUKSEK" if not eksikler else "YUKSEK_RISK" if teknik.get(
            "yeni_halka_arz_tavan_devami"
        ) or _tavan_devami_mi(teknik) else "IZLEME"
        (yuksek_guven if not eksikler else izleme).append(aday)
    sirala = lambda aday: _sayisal((aday.get("teknik") or {}).get("tavan_nihai_skoru"), -1)
    return sorted(yuksek_guven, key=sirala, reverse=True)[:limit], sorted(izleme, key=sirala, reverse=True)[:limit]


def _tavan_gecmis_performans_ozeti() -> dict[str, Any]:
    try:
        with open(TAVAN_SINYAL_GECMISI, "r", encoding="utf-8") as dosya:
            gecmis = json.load(dosya)
    except (OSError, ValueError, TypeError):
        gecmis = []
    tamamlananlar = [
        kayit.get("sonuc") for kayit in gecmis
        if isinstance(kayit, dict)
        and isinstance(kayit.get("sonuc"), dict)
        and kayit["sonuc"].get("durum") == "TAMAMLANDI"
    ]
    tahmin = sum(int(sonuc.get("tahmin_sayisi") or 0) for sonuc in tamamlananlar)
    dogru = sum(len(sonuc.get("dogru_tahminler") or []) for sonuc in tamamlananlar)
    gercek = sum(int(sonuc.get("gercek_tavan_sayisi") or 0) for sonuc in tamamlananlar)
    precision = round(dogru / tahmin * 100, 1) if tahmin else None
    recall = round(dogru / gercek * 100, 1) if gercek else None
    seviye = (
        "YETERSIZ_VERI" if tahmin < 20 else
        "YUKSEK" if precision is not None and precision >= 40 and (recall or 0) >= 20 else
        "ORTA" if precision is not None and precision >= 25 else "DUSUK"
    )
    return {
        "seviye": seviye,
        "gun": len(tamamlananlar),
        "tahmin": tahmin,
        "dogru": dogru,
        "gercek_tavan": gercek,
        "precision": precision,
        "recall": recall,
    }


def _intraday_teyidini_ekle(adaylar: list[dict[str, Any]]) -> None:
    def teyit_et(aday: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        sembol = str(aday.get("sembol") or "")
        return aday, VeriKaynaklari().yahoo_intraday_ozeti(sembol)

    if not adaylar:
        return
    with ThreadPoolExecutor(max_workers=min(8, len(adaylar))) as havuz:
        sonuclar = list(havuz.map(teyit_et, adaylar))
    for aday, intraday in sonuclar:
        teknik = aday.get("teknik") or {}
        taban_skor = _sayisal(
            teknik.get("tavan_siralama_skoru"),
            _sayisal(teknik.get("tavan_modeli_olasiligi")),
        )
        teknik["intraday"] = intraday
        if not intraday:
            teknik["tavan_nihai_skoru"] = round(taban_skor, 2)
            continue
        intraday_puani = 0.0
        hacim_orani = intraday.get("hacim_orani")
        yukari_hacim = intraday.get("yukari_bar_hacim_orani")
        momentum = _sayisal(intraday.get("momentum_15dk"))
        mesafe = _sayisal(intraday.get("tavana_mesafe"), 100)
        if hacim_orani is not None:
            intraday_puani += 10 if _sayisal(hacim_orani) >= 2 else 5 if _sayisal(hacim_orani) >= 1.2 else 0
        if yukari_hacim is not None and _sayisal(yukari_hacim) >= 65:
            intraday_puani += 5
        intraday_puani += 3 if momentum > 0 else -5 if momentum < -1 else 0
        if 0 <= mesafe <= 3:
            intraday_puani += 4
        teknik["intraday_teyit_skoru"] = round(intraday_puani, 1)
        teknik["tavan_nihai_skoru"] = round(taban_skor + intraday_puani, 2)


def _kap_teyidini_ekle(adaylar: list[dict[str, Any]]) -> None:
    if not adaylar:
        return
    ozetler = kap_aday_ozeti([aday.get("sembol") for aday in adaylar])
    for aday in adaylar:
        sembol = str(aday.get("sembol") or "")
        ozet = ozetler.get(sembol, {"adet": 0, "net_sinyal": 0, "basliklar": [], "olaylar": []})
        aday["kap_teyidi"] = ozet
        teknik = aday.get("teknik") or {}
        kap_puani = max(-5.0, min(5.0, _sayisal(ozet.get("net_sinyal"))))
        teknik["kap_teyit_skoru"] = kap_puani
        teknik["tavan_nihai_skoru"] = round(
            _sayisal(teknik.get("tavan_nihai_skoru"), _sayisal(teknik.get("tavan_siralama_skoru")))
            + kap_puani,
            2,
        )


def _fiyat_teyidini_ekle(adaylar: list[dict[str, Any]]) -> None:
    kaynaklar = VeriKaynaklari()
    for aday in adaylar:
        teknik = aday.get("teknik") or {}
        teyit = kaynaklar.isyatirim_veri(str(aday.get("sembol") or ""))
        uyum = kaynaklar.kaynak_uyumu(
            teknik.get("fiyat") or aday.get("fiyat"),
            teyit.get("fiyat") if teyit else None,
        )
        if teyit:
            ana_hacim = _sayisal(teknik.get("hacim"))
            teyit_hacmi = _sayisal(teyit.get("hacim"))
            hacim_sapmasi = (
                abs(ana_hacim / teyit_hacmi - 1) * 100
                if ana_hacim > 0 and teyit_hacmi > 0 else None
            )
            uyum["hacim_sapma_yuzde"] = round(hacim_sapmasi, 2) if hacim_sapmasi is not None else None
            uyum["tarih_uyumu"] = teyit.get("veri_tarihi") == teknik.get("son_islem_tarihi")
            uyum["guvenilir"] = bool(
                uyum.get("teyit_edildi")
                and uyum["tarih_uyumu"]
                and (hacim_sapmasi is None or hacim_sapmasi <= 10)
            )
        else:
            uyum.update({"hacim_sapma_yuzde": None, "tarih_uyumu": False, "guvenilir": False})
        teknik["fiyat_teyidi"] = uyum


def _global_modeli_ve_goreceli_gucu_uygula(analizler: list[dict[str, Any]]) -> dict[str, Any]:
    veri_setleri = {
        str(veri.get("sembol")): (veri.get("teknik") or {}).get("_tavan_egitim_verisi")
        for veri in analizler
        if (veri.get("teknik") or {}).get("_tavan_egitim_verisi")
    }
    global_sonuc = global_tavan_tahminleri(veri_setleri)
    tahminler = global_sonuc.get("tahminler", {})
    teknik_getiriler = [
        _sayisal((veri.get("teknik") or {}).get("getiri_5g"))
        for veri in analizler if veri.get("teknik")
    ]
    piyasa_5g = float(np.median(teknik_getiriler)) if teknik_getiriler else 0.0
    teknik_volatiliteler = [
        _sayisal((veri.get("teknik") or {}).get("volatilite"))
        for veri in analizler if veri.get("teknik")
    ]
    piyasa_volatilitesi = float(np.median(teknik_volatiliteler)) if teknik_volatiliteler else 0.0
    piyasa_durumu = (
        "GUCLU" if piyasa_5g >= 3 else
        "POZITIF" if piyasa_5g > 0 else
        "ZAYIF" if piyasa_5g <= -3 else "NOTR"
    )
    piyasa_rejim_puani = float(np.clip(piyasa_5g, -5, 5))
    sektor_getirileri: dict[str, list[float]] = {}
    for veri in analizler:
        teknik = veri.get("teknik") or {}
        if not teknik:
            continue
        sektor = hisse_sektor(str(veri.get("sembol") or ""))
        sektor_getirileri.setdefault(sektor, []).append(_sayisal(teknik.get("getiri_5g")))

    for veri in analizler:
        teknik = veri.get("teknik") or {}
        sembol = str(veri.get("sembol") or "")
        tahmin = tahminler.get(sembol) or {}
        if tahmin.get("kapanma") is not None:
            teknik["tavan_modeli_olasiligi"] = tahmin["kapanma"]
            teknik["tavan_modeli_ham_olasiligi"] = tahmin.get("kapanma_ham")
            teknik["tavana_dokunma_olasiligi"] = tahmin.get("dokunma")
            teknik["tavana_dokunma_ham_olasiligi"] = tahmin.get("dokunma_ham")
            teknik["beklenen_getiri"] = tahmin.get("beklenen_getiri")
            teknik["dusus_riski"] = tahmin.get("dusus_riski")
            teknik["tavan_siralama_skoru"] = tahmin.get("siralama_skoru")
            teknik["tavan_modeli_kapsami"] = "GLOBAL"
        sektor = hisse_sektor(sembol)
        sektor_ortalama = float(np.median(sektor_getirileri.get(sektor, [0.0])))
        hisse_5g = _sayisal(teknik.get("getiri_5g"))
        teknik["sektor"] = sektor
        teknik["piyasaya_gore_guc"] = round(hisse_5g - float(piyasa_5g), 2)
        teknik["sektore_gore_guc"] = round(hisse_5g - sektor_ortalama, 2)
        teknik["sektor_momentumu"] = round(sektor_ortalama, 2)
        teknik["piyasa_rejimi"] = piyasa_durumu
        teknik["piyasa_momentumu"] = round(piyasa_5g, 2)
        teknik["piyasa_volatilitesi"] = round(piyasa_volatilitesi, 2)
        teknik["goreceli_guc_skoru"] = _sinirla(
            50 + (hisse_5g - float(piyasa_5g)) * 3 + (hisse_5g - sektor_ortalama) * 2
        )
        if teknik.get("tavan_siralama_skoru") is not None:
            teknik["tavan_siralama_skoru"] = round(
                _sayisal(teknik.get("tavan_siralama_skoru"))
                + piyasa_rejim_puani
                + float(np.clip(sektor_ortalama, -3, 3)),
                2,
            )
        teknik.pop("_tavan_egitim_verisi", None)
    global_sonuc["piyasa_rejimi"] = {
        "durum": piyasa_durumu,
        "getiri_5g_medyan": round(piyasa_5g, 2),
        "volatilite_medyan": round(piyasa_volatilitesi, 2),
    }
    return global_sonuc


def _tavan_gecmisini_yaz(gecmis: list[dict[str, Any]]) -> bool:
    gecici_dosya = None
    try:
        klasor = os.path.dirname(os.path.abspath(TAVAN_SINYAL_GECMISI))
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=klasor, delete=False) as dosya:
            gecici_dosya = dosya.name
            json.dump(gecmis[-90:], dosya, ensure_ascii=False, indent=2)
            dosya.flush()
            os.fsync(dosya.fileno())
        os.replace(gecici_dosya, TAVAN_SINYAL_GECMISI)
        return True
    except OSError:
        if gecici_dosya:
            try:
                os.remove(gecici_dosya)
            except OSError:
                pass
        return False


def _tavan_sinyalini_kaydet(
    adaylar: list[dict[str, Any]],
    analizler: list[dict[str, Any]] | None = None,
) -> None:
    """Gunluk tahminleri ertesi gun gerceklerle karsilastirmak icin saklar."""
    evren_verileri = analizler if analizler is not None else adaylar
    veri_tarihleri = [
        (veri.get("teknik") or {}).get("son_islem_tarihi")
        for veri in evren_verileri
        if (veri.get("teknik") or {}).get("son_islem_tarihi")
    ]
    bugun = max(veri_tarihleri) if veri_tarihleri else datetime.now().strftime("%Y-%m-%d")
    try:
        with open(TAVAN_SINYAL_GECMISI, "r", encoding="utf-8") as dosya:
            gecmis = json.load(dosya)
        if not isinstance(gecmis, list):
            gecmis = []
    except (OSError, ValueError, TypeError):
        gecmis = []

    def gecerli_aday_var(kayit: dict[str, Any]) -> bool:
        return any(
            isinstance(aday, dict)
            and aday.get("sembol")
            and (
                aday.get("olasilik") is not None
                or aday.get("dokunma_olasiligi") is not None
                or aday.get("yeni_halka_arz_tavan_devami") is True
            )
            for aday in kayit.get("adaylar", [])
        )

    gecmis = [
        kayit for kayit in gecmis
        if isinstance(kayit, dict) and (kayit.get("sonuc") or gecerli_aday_var(kayit))
    ]
    ayni_gunun_tamamlanmis_kaydi = any(
        kayit.get("tarih") == bugun
        and isinstance(kayit.get("sonuc"), dict)
        for kayit in gecmis
    )
    if ayni_gunun_tamamlanmis_kaydi:
        return
    gecmis = [
        kayit for kayit in gecmis
        if not isinstance(kayit, dict) or kayit.get("tarih") != bugun
    ]
    secilen_semboller = {str(aday.get("sembol") or "") for aday in adaylar}
    evren = []
    for veri in evren_verileri:
        sembol = str(veri.get("sembol") or "")
        teknik = veri.get("teknik") or {}
        if not sembol or teknik.get("son_islem_tarihi") != bugun:
            continue
        nedenler = _tavan_adayi_elenme_nedenleri(veri)
        if not nedenler and sembol not in secilen_semboller:
            nedenler = ["Ilk 5 siralama sinirinda elendi"]
        evren.append({
            "sembol": sembol,
            "olasilik": teknik.get("tavan_modeli_olasiligi"),
            "dokunma_olasiligi": teknik.get("tavana_dokunma_olasiligi"),
            "gunluk_getiri": teknik.get("gunluk_getiri"),
            "getiri_5g": teknik.get("getiri_5g"),
            "hacim_orani": teknik.get("hacim_orani"),
            "aday_skoru": teknik.get("yarin_tavan_adayi_skoru"),
            "yeni_halka_arz_tavan_devami": teknik.get("yeni_halka_arz_tavan_devami", False),
            "elenme_nedenleri": nedenler,
        })

    gecmis.append({
        "sema_surumu": 3,
        "tarih": bugun,
        "kayit_zamani": datetime.now().isoformat(timespec="seconds"),
        "model_surumu": next(
            (
                (aday.get("teknik") or {}).get("tavan_modeli_surumu")
                for aday in adaylar
                if (aday.get("teknik") or {}).get("tavan_modeli_surumu")
            ),
            None,
        ),
        "esikler": {
            "kapanma_olasiligi": TAVAN_MIN_OLASILIK,
            "dokunma_olasiligi": TAVAN_MIN_DOKUNMA_OLASILIK,
            "hacim_orani": 1.1,
            "maksimum_gunluk_getiri": TAVAN_MAX_GUNLUK_GETIRI,
            "maksimum_5g_getiri": TAVAN_MAX_5G_GETIRI,
            "maksimum_rsi": TAVAN_MAX_RSI,
            "minimum_ham_kapanma": TAVAN_MIN_HAM_KAPANMA,
            "minimum_ham_dokunma": TAVAN_MIN_HAM_DOKUNMA,
            "minimum_beklenen_getiri": TAVAN_MIN_BEKLENEN_GETIRI,
            "devam_minimum_kapanma": TAVAN_DEVAM_MIN_OLASILIK,
            "devam_minimum_dokunma": TAVAN_DEVAM_MIN_DOKUNMA,
            "devam_minimum_hacim": TAVAN_DEVAM_MIN_HACIM,
            "gercek_tavan_getirisi": 9.5,
        },
        "evren_sayisi": len(evren),
        "evren": evren,
        "adaylar": [
            {
                "sembol": aday.get("sembol"),
                "kapanis": aday.get("fiyat"),
                "olasilik": (aday.get("teknik") or {}).get("tavan_modeli_olasiligi"),
                "dokunma_olasiligi": (aday.get("teknik") or {}).get("tavana_dokunma_olasiligi"),
                "ham_olasilik": (aday.get("teknik") or {}).get("tavan_modeli_ham_olasiligi"),
                "ham_dokunma_olasiligi": (aday.get("teknik") or {}).get("tavana_dokunma_ham_olasiligi"),
                "precision": (aday.get("teknik") or {}).get("tavan_modeli_precision"),
                "aday_skoru": (aday.get("teknik") or {}).get("yarin_tavan_adayi_skoru"),
                "siralama_skoru": (aday.get("teknik") or {}).get("tavan_siralama_skoru"),
                "nihai_skor": (aday.get("teknik") or {}).get("tavan_nihai_skoru"),
                "beklenen_getiri": (aday.get("teknik") or {}).get("beklenen_getiri"),
                "dusus_riski": (aday.get("teknik") or {}).get("dusus_riski"),
                "gunluk_getiri": (aday.get("teknik") or {}).get("gunluk_getiri"),
                "getiri_5g": (aday.get("teknik") or {}).get("getiri_5g"),
                "hacim_orani": (aday.get("teknik") or {}).get("hacim_orani"),
                "tavan_devam_adayi": _guclu_tavan_devami_mi(aday.get("teknik") or {}),
                "yeni_halka_arz_tavan_devami": (aday.get("teknik") or {}).get(
                    "yeni_halka_arz_tavan_devami", False
                ),
                "veri_kaynagi": (aday.get("teknik") or {}).get("veri_kaynagi"),
            }
            for aday in adaylar
        ],
    })
    _tavan_gecmisini_yaz(gecmis)


def _yanlis_pozitif_nedenleri(aday: dict[str, Any], guncel: dict[str, Any]) -> list[str]:
    nedenler = []
    if _sayisal(aday.get("olasilik")) < TAVAN_DEVAM_MIN_OLASILIK:
        nedenler.append(f"Kapanma olasiligi yuksek guven esigi %{TAVAN_DEVAM_MIN_OLASILIK:g} altinda")
    if _sayisal(aday.get("dokunma_olasiligi")) < TAVAN_MIN_DOKUNMA_OLASILIK:
        nedenler.append(f"Dokunma olasiligi secim esigi %{TAVAN_MIN_DOKUNMA_OLASILIK:g} altinda")
    if aday.get("precision") is None or _sayisal(aday.get("precision")) <= 0:
        nedenler.append("Tarihsel precision tahmini desteklemiyor")
    if _sayisal(aday.get("hacim_orani"), 1) >= 2:
        nedenler.append("Hacim artisi tavan hareketine donusmedi")
    gercek_getiri = _sayisal((guncel.get("teknik") or {}).get("gunluk_getiri"))
    if gercek_getiri <= 0:
        nedenler.append("Ertesi gun momentum tersine dondu")
    elif gercek_getiri < 9.5:
        nedenler.append("Ertesi gun yukselisi tavan seviyesine ulasmadi")
    return nedenler or ["Model sinyali gerceklesmedi; belirgin tekil neden bulunamadi"]


def _tavan_sinyallerini_degerlendir(analizler: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Onceki tahminleri mevcut son islem gununun tavan kapanislariyla karsilastirir."""
    try:
        with open(TAVAN_SINYAL_GECMISI, "r", encoding="utf-8") as dosya:
            gecmis = json.load(dosya)
        if not isinstance(gecmis, list):
            return None
    except (OSError, ValueError, TypeError):
        return None

    tarihli_analizler = [
        veri for veri in analizler
        if (veri.get("teknik") or {}).get("son_islem_tarihi")
    ]
    if not tarihli_analizler:
        return None
    son_tarih = max((veri.get("teknik") or {})["son_islem_tarihi"] for veri in tarihli_analizler)
    gercek_tavanlar = sorted({
        veri.get("sembol")
        for veri in tarihli_analizler
        if (veri.get("teknik") or {}).get("son_islem_tarihi") == son_tarih
        and (
            tavana_ulasti(
                _sayisal((veri.get("teknik") or {}).get("onceki_kapanis")),
                _sayisal((veri.get("teknik") or {}).get("fiyat") or veri.get("fiyat")),
            )
            if _sayisal((veri.get("teknik") or {}).get("onceki_kapanis")) > 0
            else _sayisal((veri.get("teknik") or {}).get("gunluk_getiri")) >= 9.5
        )
        and veri.get("sembol")
    })

    tamamlananlar = [
        kayit["sonuc"] for kayit in gecmis
        if isinstance(kayit, dict) and isinstance(kayit.get("sonuc"), dict)
    ]
    son_performans = tamamlananlar[-1] if tamamlananlar else None
    bekleyenler = [
        kayit for kayit in gecmis
        if isinstance(kayit, dict)
        and not kayit.get("sonuc")
        and str(kayit.get("tarih") or "") < son_tarih
        and any(
            isinstance(aday, dict)
            and aday.get("sembol")
            and (
                aday.get("olasilik") is not None
                or aday.get("dokunma_olasiligi") is not None
                or aday.get("yeni_halka_arz_tavan_devami") is True
            )
            for aday in kayit.get("adaylar", [])
        )
    ]
    degisti = False
    if bekleyenler:
        kayit = max(bekleyenler, key=lambda veri: str(veri.get("tarih") or ""))
        beklenen_tarih = GunlukVeriDeposu().sonraki_islem_tarihi(str(kayit.get("tarih") or ""))
        if beklenen_tarih and son_tarih != beklenen_tarih:
            kayit["sonuc"] = {
                "durum": "DEGERLENDIRILEMEDI",
                "beklenen_tarih": beklenen_tarih,
                "mevcut_tarih": son_tarih,
                "uyari": "Tahmin sonraki ilk islem gununde degerlendirilemedi",
            }
            _tavan_gecmisini_yaz(gecmis)
            return kayit["sonuc"]
        adaylar = [
            aday for aday in kayit.get("adaylar", [])
            if isinstance(aday, dict)
            and aday.get("sembol")
            and (
                aday.get("olasilik") is not None
                or aday.get("dokunma_olasiligi") is not None
                or aday.get("yeni_halka_arz_tavan_devami") is True
            )
        ]
        tahminler = {str(aday["sembol"]) for aday in adaylar}
        guncel_veriler = {
            str(veri.get("sembol")): veri
            for veri in tarihli_analizler
            if (veri.get("teknik") or {}).get("son_islem_tarihi") == son_tarih and veri.get("sembol")
        }
        tahmin_evreni = {
            str(veri.get("sembol"))
            for veri in kayit.get("evren", [])
            if isinstance(veri, dict) and veri.get("sembol")
        }
        kapsama = (
            len(tahmin_evreni & set(guncel_veriler)) / len(tahmin_evreni) * 100
            if tahmin_evreni else None
        )
        if kapsama is not None and kapsama < TAVAN_MIN_DEGERLENDIRME_KAPSAMI:
            return {
                "durum": "YETERSIZ_KAPSAM",
                "gercek_tarih": son_tarih,
                "tahmin_sayisi": len(tahminler),
                "gercek_tavan_sayisi": None,
                "dogru_tahminler": [],
                "yanlis_pozitifler": [],
                "kacirilan_tavanlar": [],
                "precision": None,
                "recall": None,
                "evren_kapsami": round(kapsama, 1),
                "uyari": "Tarama evreni eksik; performans sonucu kaydedilmedi",
            }
        gercekler = set(gercek_tavanlar)
        dogru = sorted(tahminler & gercekler)
        onceki_evren = {
            str(veri.get("sembol")): veri
            for veri in kayit.get("evren", [])
            if isinstance(veri, dict) and veri.get("sembol")
        }
        aday_haritasi = {str(aday["sembol"]): aday for aday in adaylar}
        sonuc = {
            "durum": "TAMAMLANDI",
            "gercek_tarih": son_tarih,
            "tahmin_sayisi": len(tahminler),
            "gercek_tavan_sayisi": len(gercekler),
            "gercek_tavanlar": sorted(gercekler),
            "dogru_tahminler": dogru,
            "yanlis_pozitifler": sorted(tahminler - gercekler),
            "yanlis_pozitif_nedenleri": {
                sembol: _yanlis_pozitif_nedenleri(
                    aday_haritasi[sembol],
                    guncel_veriler.get(sembol, {}),
                )
                for sembol in sorted(tahminler - gercekler)
            },
            "kacirilan_tavanlar": sorted(gercekler - tahminler),
            "kacirilan_nedenleri": {
                sembol: (onceki_evren.get(sembol) or {}).get(
                    "elenme_nedenleri", ["Tahmin gunu evren verisi bulunamadi"]
                )
                for sembol in sorted(gercekler - tahminler)
            },
            "precision": round(len(dogru) / len(tahminler) * 100, 1),
            "recall": round(len(dogru) / len(gercekler) * 100, 1) if gercekler else 0.0,
            "evren_kapsami": round(kapsama, 1) if kapsama is not None else None,
            "guvenilir": kapsama is not None and kapsama >= 90,
            "tahmin_sonuclari": [
                {
                    "sembol": sembol,
                    "gercek_getiri": (guncel_veriler.get(sembol, {}).get("teknik") or {}).get("gunluk_getiri"),
                    "tavan_oldu": sembol in gercekler,
                }
                for sembol in sorted(tahminler)
            ],
        }
        kayit["sonuc"] = sonuc
        son_performans = sonuc
        degisti = True

    if degisti:
        _tavan_gecmisini_yaz(gecmis)
    return son_performans


def hisse_analiz_et(sembol: str, kullanici: str | None = None) -> dict[str, Any]:
    sembol = str(sembol).upper().replace(".IS", "").strip()
    teknik, trade = _teknik_ve_trade(sembol)
    try:
        temel = temel_analiz(sembol)
    except Exception:
        temel = None
    try:
        hedef = hedef_fiyat_tahmin(sembol, gun_hedef=5)
    except Exception:
        hedef = None
    try:
        takas = takas_analiz(sembol, kullanici=kullanici)
    except Exception:
        takas = None
    risk, risk_seviyesi = _risk_puani(teknik)
    parcalar = {
        "teknik": teknik["puan"] if teknik else None,
        "temel": _temel_puan(temel),
        "risk": risk,
        "takas": _takas_puani(takas),
        "hedef": _hedef_puani(hedef),
        "trade": trade["puan"] if trade else None,
    }
    agirlikli = sum(parcalar[alan] * agirlik for alan, agirlik in ANALIZ_AGIRLIKLARI.items() if parcalar[alan] is not None)
    mevcut_agirlik = sum(agirlik for alan, agirlik in ANALIZ_AGIRLIKLARI.items() if parcalar[alan] is not None)
    return {
        "sembol": sembol,
        "fiyat": teknik.get("fiyat") if teknik else None,
        "skor": _sinirla(agirlikli / mevcut_agirlik if mevcut_agirlik else 0),
        "skorlar": parcalar,
        "veri_guveni": _veri_guven_skoru(parcalar),
        "risk_seviyesi": risk_seviyesi,
        "teknik": teknik,
        "temel": temel,
        "takas": takas,
        "hedef": hedef,
        "trade": trade,
        "durum": (
            "GUCLU ADAY" if agirlikli / mevcut_agirlik >= 70
            else "IZLE" if agirlikli / mevcut_agirlik >= 50
            else "BEKLE"
        ) if mevcut_agirlik else "VERI YOK",
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def kapsamli_tarama(
    semboller: list[str],
    force: bool = False,
    kullanici: str | None = None,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Verilen tum sembolleri paralel analiz eder ve skora gore siralar."""
    if not force:
        try:
            with open(ANALIZ_CACHE, "r", encoding="utf-8") as dosya:
                cache = json.load(dosya)
            sonuc = cache.get("sonuc")
            if (
                isinstance(sonuc, dict)
                and cache.get("kullanici") == kullanici
                and "tavan_gecmis_ozeti" in sonuc
                and "tavan_izleme_listesi" in sonuc
            ):
                analizler = sonuc.get("analizler") or []
                if time.time() - float(cache.get("zaman", 0)) < ANALIZ_CACHE_TTL and len(analizler) >= max(1, KAPSAMLI_ANALIZ_TOP_N):
                    return sonuc
        except (OSError, ValueError, TypeError, KeyError):
            pass
    temiz = sorted({str(s).upper().replace(".IS", "") for s in semboller if s})
    if KAPSAMLI_ANALIZ_MAX_SEMBOL > 0:
        temiz = temiz[:KAPSAMLI_ANALIZ_MAX_SEMBOL]
    if progress_callback:
        progress_callback(0, len(temiz))
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(temiz)))) as havuz:
        gorevler = [havuz.submit(hisse_analiz_et, sembol, kullanici) for sembol in temiz]
        analizler = []
        for tamamlanan in as_completed(gorevler):
            analizler.append(tamamlanan.result())
            if progress_callback:
                progress_callback(len(analizler), len(temiz))
    analizler = [veri for veri in analizler if isinstance(veri, dict)]
    global_model = _global_modeli_ve_goreceli_gucu_uygula(analizler)
    backtest_kabul = _backtest_kabul_durumu()
    tavan_performansi = _tavan_sinyallerini_degerlendir(analizler)
    tavan_kisa_liste = _tavan_adaylarini_sec(analizler, limit=20)
    _intraday_teyidini_ekle(tavan_kisa_liste)
    _kap_teyidini_ekle(tavan_kisa_liste)
    _fiyat_teyidini_ekle(tavan_kisa_liste)
    tavan_adaylari, tavan_izleme_listesi = _tavan_listelerini_siniflandir(
        tavan_kisa_liste,
        model_kabul=backtest_kabul["kabul"],
    )
    _tavan_sinyalini_kaydet(tavan_adaylari, analizler)
    analizler.sort(
        key=lambda veri: (
            (veri.get("teknik") or {}).get("yarin_tavan_adayi_skoru", 0),
            veri["skor"],
            veri["veri_guveni"],
        ),
        reverse=True,
    )
    en_iyiler = analizler[: max(1, KAPSAMLI_ANALIZ_TOP_N)]
    sonuc = {
        "analizler": en_iyiler,
        "sembol_sayisi": len(temiz),
        "analiz_sayisi": len(en_iyiler),
        "tavan_adaylari": tavan_adaylari,
        "tavan_izleme_listesi": tavan_izleme_listesi,
        "tavan_performansi": tavan_performansi,
        "tavan_gecmis_ozeti": _tavan_gecmis_performans_ozeti(),
        "global_model": {
            "metrikler": global_model.get("metrikler", {}),
            "model_surumu": global_model.get("model_surumu"),
        },
        "backtest_kabul": backtest_kabul,
        "son_guncelleme": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "agirliklar": ANALIZ_AGIRLIKLARI,
        "teknik_gosterge_agirliklari": TEKNIK_GOSTERGE_AGIRLIKLARI,
        "piyasa_rejimi": {
            "bist": global_model.get("piyasa_rejimi"),
            "makro": tcmb_piyasa_rejimi(),
        },
        "kaynak": "Yahoo Finance / Is Yatirim OHLCV + KAP + TCMB",
    }
    try:
        with open(ANALIZ_CACHE, "w", encoding="utf-8") as dosya:
            json.dump({
                "zaman": time.time(),
                "kullanici": kullanici,
                "sonuc": sonuc,
            }, dosya, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return sonuc