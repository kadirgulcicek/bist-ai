"""KAP bildirimlerinden nokta-zaman uyumlu model ozellikleri uretir."""

from __future__ import annotations

from pathlib import Path
import json
import sqlite3

import numpy as np
import pandas as pd

from gunluk_veri_deposu import VARSAYILAN_DB


KAP_OZELLIK_KOLONLARI = (
    "KAP_Bildirim_24s",
    "KAP_Bildirim_7g",
    "KAP_Gecikmeli_30g",
    "KAP_Piyasa_Olayi_24s",
    "KAP_Is_Iliskisi_7g",
    "KAP_Sermaye_7g",
    "KAP_Pay_Islemi_7g",
    "KAP_Finansal_7g",
    "KAP_Negatif_7g",
)
SEANS_ACILIS_SAATI = (9, 40)


def _normalize(metin: str) -> str:
    return str(metin or "").lower().translate(str.maketrans("çğıöşü", "cgiosu"))


def _olay_siniflari(konu: str, ham_json: str) -> set[str]:
    try:
        ham = json.loads(ham_json or "{}")
    except (TypeError, ValueError):
        ham = {}
    metin = _normalize(" ".join((konu, str(ham.get("summary") or ""))))
    siniflar = set()
    if any(kelime in metin for kelime in ("olagan disi fiyat", "devre kesici", "bistech")):
        siniflar.add("piyasa")
    if any(kelime in metin for kelime in ("yeni is iliskisi", "ihale", "siparis", "sozlesme imzalan")):
        siniflar.add("is_iliskisi")
    if any(kelime in metin for kelime in ("sermaye artir", "sermaye azalt", "birlesme islemi", "bolunme", "paylarin geri alin")):
        siniflar.add("sermaye")
    if "pay alim satim bildirimi" in metin:
        siniflar.add("pay_islemi")
    if any(kelime in metin for kelime in ("finansal rapor", "faaliyet raporu", "sorumluluk beyani")):
        siniflar.add("finansal")
    if any(kelime in metin for kelime in (
        "ceza", "sorusturma", "iflas", "konkordato", "faaliyetlerin durdurul",
        "sozlesme fes", "ihale iptal", "dava acil", "zarar acikla",
    )):
        siniflar.add("negatif")
    return siniflar


def _sonraki_hafta_ici(gun: pd.Timestamp) -> pd.Timestamp:
    sonraki = gun + pd.Timedelta(days=1)
    while sonraki.weekday() >= 5:
        sonraki += pd.Timedelta(days=1)
    return sonraki


def _sinyal_kesim_zamanlari(indeks: pd.Index) -> pd.DatetimeIndex:
    gunler = pd.DatetimeIndex(pd.to_datetime(indeks)).tz_localize(None).normalize()
    kesimler = []
    for konum, gun in enumerate(gunler):
        sonraki = gunler[konum + 1] if konum + 1 < len(gunler) else _sonraki_hafta_ici(gun)
        kesimler.append(
            pd.Timestamp(sonraki).tz_localize("Europe/Istanbul")
            + pd.Timedelta(hours=SEANS_ACILIS_SAATI[0], minutes=SEANS_ACILIS_SAATI[1])
        )
    return pd.DatetimeIndex(kesimler).tz_convert("UTC")


def _aralik_sayilari(zamanlar: np.ndarray, kesimler: np.ndarray, gun: int) -> np.ndarray:
    ust = np.searchsorted(zamanlar, kesimler, side="left")
    alt = np.searchsorted(zamanlar, kesimler - pd.Timedelta(days=gun).value, side="left")
    return (ust - alt).astype(float)


def kap_ozelliklerini_ekle(
    veri: pd.DataFrame,
    sembol: str,
    db: str | Path = VARSAYILAN_DB,
) -> pd.DataFrame:
    """Her fiyat satirina, sonraki seans acilisindan once bilinen KAP sayilarini ekler."""
    sonuc = veri.copy()
    for kolon in KAP_OZELLIK_KOLONLARI:
        sonuc[kolon] = 0.0
    if sonuc.empty or not sembol or not Path(db).exists():
        return sonuc

    temiz_sembol = str(sembol).strip().upper().replace(".IS", "")
    kesimler = _sinyal_kesim_zamanlari(sonuc.index)
    try:
        with sqlite3.connect(db) as baglanti:
            satirlar = baglanti.execute(
                """
                SELECT b.yayin_zamani, b.gecikmeli, b.konu, b.ham_json
                FROM kap_bildirim AS b
                JOIN kap_bildirim_sembol AS s ON s.bildirim_id = b.bildirim_id
                WHERE s.sembol = ?
                ORDER BY b.yayin_zamani
                """,
                (temiz_sembol,),
            ).fetchall()
    except sqlite3.Error:
        return sonuc
    if not satirlar:
        return sonuc

    zamanlar = pd.to_datetime([satir[0] for satir in satirlar], utc=True).as_unit("ns").asi8
    gecikmeli_zamanlar = pd.to_datetime(
        [satir[0] for satir in satirlar if satir[1]], utc=True,
    ).as_unit("ns").asi8
    kesim_ns = kesimler.as_unit("ns").asi8
    sonuc["KAP_Bildirim_24s"] = _aralik_sayilari(zamanlar, kesim_ns, 1)
    sonuc["KAP_Bildirim_7g"] = _aralik_sayilari(zamanlar, kesim_ns, 7)
    sonuc["KAP_Gecikmeli_30g"] = _aralik_sayilari(gecikmeli_zamanlar, kesim_ns, 30)
    sinif_zamanlari = {
        sinif: pd.to_datetime(
            [satir[0] for satir in satirlar if sinif in _olay_siniflari(satir[2], satir[3])],
            utc=True,
        ).as_unit("ns").asi8
        for sinif in ("piyasa", "is_iliskisi", "sermaye", "pay_islemi", "finansal", "negatif")
    }
    sonuc["KAP_Piyasa_Olayi_24s"] = _aralik_sayilari(sinif_zamanlari["piyasa"], kesim_ns, 1)
    sonuc["KAP_Is_Iliskisi_7g"] = _aralik_sayilari(sinif_zamanlari["is_iliskisi"], kesim_ns, 7)
    sonuc["KAP_Sermaye_7g"] = _aralik_sayilari(sinif_zamanlari["sermaye"], kesim_ns, 7)
    sonuc["KAP_Pay_Islemi_7g"] = _aralik_sayilari(sinif_zamanlari["pay_islemi"], kesim_ns, 7)
    sonuc["KAP_Finansal_7g"] = _aralik_sayilari(sinif_zamanlari["finansal"], kesim_ns, 7)
    sonuc["KAP_Negatif_7g"] = _aralik_sayilari(sinif_zamanlari["negatif"], kesim_ns, 7)
    return sonuc