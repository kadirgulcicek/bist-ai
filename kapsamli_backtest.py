"""Tavan adaylari icin tarih bazli, hisseler arasi global backtest."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from gunluk_veri_deposu import GunlukVeriDeposu, VARSAYILAN_DB
from kap_ozellikleri import kap_ozelliklerini_ekle
from tavan_modeli import KAP_MODEL_SURUMU, MODEL_SURUMU, _model_adaylari, erken_tavan_adayi_mi, tavan_egitim_verisi


RAPOR_SEMA_SURUMU = 3


def _wilson_guven_araligi(basari: int, toplam: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if toplam <= 0:
        return None, None
    oran = basari / toplam
    payda = 1 + z ** 2 / toplam
    merkez = (oran + z ** 2 / (2 * toplam)) / payda
    yari_genislik = z * np.sqrt((oran * (1 - oran) + z ** 2 / (4 * toplam)) / toplam) / payda
    return float(max(0.0, merkez - yari_genislik)), float(min(1.0, merkez + yari_genislik))


def _ortalama_guven_alt(degerler: list[float], z: float = 1.96) -> float | None:
    if not degerler:
        return None
    if len(degerler) == 1:
        return float(degerler[0])
    dizi = np.asarray(degerler, dtype=float)
    return float(dizi.mean() - z * dizi.std(ddof=1) / np.sqrt(len(dizi)))


def temsili_sembol_ornekle(semboller: list[str], limit: int) -> list[str]:
    """Limitli backtestte alfabetik evrenin tamamini esit araliklarla temsil eder."""
    if limit <= 0 or limit >= len(semboller):
        return semboller.copy()
    konumlar = np.linspace(0, len(semboller) - 1, num=limit, dtype=int)
    return [semboller[konum] for konum in konumlar]


def tarih_bazli_global_backtest(
    veri_setleri: dict[str, dict[str, Any]],
    top_n: int = 5,
    min_egitim_tarihi: int = 60,
    son_test_gunu: int = 60,
    yeniden_egit_araligi: int = 5,
    islem_maliyeti_bps: float = 20,
    erken_filtre: bool = False,
    kapanma_agirligi: float = 60,
    dokunma_agirligi: float = 40,
    getiri_agirligi: float = 0,
    risk_agirligi: float = 0,
    minimum_kapanma_olasiligi: float = 0.0,
    minimum_dokunma_olasiligi: float = 0.0,
    minimum_beklenen_getiri: float = -0.10,
    momentum_hacim_filtresi: bool = False,
    purge_gunu: int = 1,
    gunluk_maruz_kalma: float = 0.25,
) -> dict[str, Any]:
    """Her test tarihinde sadece daha eski satirlarla global siralama modeli kurar."""
    tarihe_gore: dict[str, list[tuple[str, list[float], int, int, float]]] = {}
    for sembol, egitim in veri_setleri.items():
        getiriler = egitim.get("sonraki_getiriler", [])
        kapanma_etiketleri = egitim.get("kapanma_y", [])
        dokunma_etiketleri = egitim.get("dokunma_y", kapanma_etiketleri)
        for indeks, (tarih, ozellik, dokunma, kapanma) in enumerate(zip(
            egitim.get("tarihler", []), egitim.get("x", []),
            dokunma_etiketleri, kapanma_etiketleri,
        )):
            sonraki_getiri = float(getiriler[indeks]) if indeks < len(getiriler) else 0.0
            tarihe_gore.setdefault(str(tarih), []).append(
                (sembol, ozellik, int(dokunma), int(kapanma), sonraki_getiri)
            )
    tarihler = sorted(tarihe_gore)
    if len(tarihler) <= min_egitim_tarihi:
        return {"gunler": [], "ozet": {"test_gunu": 0, "precision_at_n": None, "recall_at_n": None}}

    test_tarihleri = tarihler[min_egitim_tarihi:][-son_test_gunu:]
    model = None
    dokunma_modeli = None
    dokunma_taban = 0.0
    getiri_modeli = None
    risk_modeli = None
    gunler = []
    toplam_dogru = toplam_aday = toplam_gercek = 0
    toplam_dokunma_dogru = toplam_dokunma_gercek = 0
    tum_gercekler = []
    tum_olasiliklar = []
    gunluk_net_getiriler = []
    model_secimleri: dict[str, int] = {}
    filtre_akisi = {
        adim: {"aday": 0, "gercek_tavan": 0}
        for adim in ("tum", "erken_filtre", "kapanma", "dokunma", "getiri", "momentum_hacim")
    }
    filtresiz_top_n_dogru = 0
    filtresiz_top_n_tahmin = 0
    for konum, test_tarihi in enumerate(test_tarihleri):
        onceki_tarihler = [tarih for tarih in tarihler if tarih < test_tarihi]
        egitim_tarihleri = onceki_tarihler[:-purge_gunu] if purge_gunu > 0 else onceki_tarihler
        if model is None or konum % max(1, yeniden_egit_araligi) == 0:
            egitim_satirlari = [satir for tarih in egitim_tarihleri for satir in tarihe_gore[tarih]]
            egitim_x = [satir[1] for satir in egitim_satirlari]
            egitim_dokunma_y = [satir[2] for satir in egitim_satirlari]
            egitim_y = [satir[3] for satir in egitim_satirlari]
            egitim_getirileri = np.clip([satir[4] for satir in egitim_satirlari], -0.10, 0.10)
            if len(set(egitim_y)) < 2:
                continue
            dogrulama_tarihleri = egitim_tarihleri[max(1, int(len(egitim_tarihleri) * 0.8)):]
            dogrulama_baslangici = dogrulama_tarihleri[0] if dogrulama_tarihleri else test_tarihi
            model_tarihleri = [tarih for tarih in egitim_tarihleri if tarih < dogrulama_baslangici]
            if purge_gunu > 0:
                model_tarihleri = model_tarihleri[:-purge_gunu]
            model_egitim_satirlari = [
                satir for tarih in model_tarihleri
                for satir in tarihe_gore[tarih]
            ]
            dogrulama_satirlari = [
                satir for tarih in egitim_tarihleri if tarih >= dogrulama_baslangici
                for satir in tarihe_gore[tarih]
            ]
            aday_sonuclari = []
            if model_egitim_satirlari and dogrulama_satirlari and len({satir[3] for satir in model_egitim_satirlari}) >= 2:
                for model_adi, model_uret in _model_adaylari():
                    aday_model = model_uret()
                    aday_model.fit(
                        [satir[1] for satir in model_egitim_satirlari],
                        [satir[3] for satir in model_egitim_satirlari],
                    )
                    aday_olasilik = aday_model.predict_proba([satir[1] for satir in dogrulama_satirlari])[:, 1]
                    dogrulama_y = [satir[3] for satir in dogrulama_satirlari]
                    aday_sonuclari.append((
                        average_precision_score(dogrulama_y, aday_olasilik),
                        brier_score_loss(dogrulama_y, aday_olasilik),
                        model_adi,
                        model_uret,
                    ))
            if aday_sonuclari:
                _, _, secilen_model, model_uret = min(aday_sonuclari, key=lambda sonuc: (-sonuc[0], sonuc[1]))
            else:
                secilen_model, model_uret = _model_adaylari()[0]
            model_secimleri[secilen_model] = model_secimleri.get(secilen_model, 0) + 1
            model = model_uret()
            model.fit(egitim_x, egitim_y)
            dokunma_taban = float(np.mean(egitim_dokunma_y))
            dokunma_modeli = None
            if len(set(egitim_dokunma_y)) >= 2:
                dokunma_modeli = model_uret()
                dokunma_modeli.fit(egitim_x, egitim_dokunma_y)
            getiri_modeli = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
            risk_modeli = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
            getiri_modeli.fit(egitim_x, egitim_getirileri)
            risk_modeli.fit(egitim_x, np.maximum(-egitim_getirileri, 0))

        test_satirlari = tarihe_gore[test_tarihi]
        test_x = [satir[1] for satir in test_satirlari]
        olasiliklar = model.predict_proba(test_x)[:, 1]
        dokunma_olasiliklari = (
            dokunma_modeli.predict_proba(test_x)[:, 1]
            if dokunma_modeli is not None
            else np.full(len(test_x), dokunma_taban)
        )
        beklenen_getiriler = np.clip(getiri_modeli.predict(test_x), -0.10, 0.10)
        dusus_riskleri = np.clip(risk_modeli.predict(test_x), 0, 0.10)
        skorlar = (
            olasiliklar * kapanma_agirligi
            + dokunma_olasiliklari * dokunma_agirligi
            + beklenen_getiriler * getiri_agirligi
            - dusus_riskleri * risk_agirligi
        )
        puanlananlar = [
            (satir, olasilik, dokunma_olasilik, beklenen_getiri, skor)
            for satir, olasilik, dokunma_olasilik, beklenen_getiri, skor in zip(
                test_satirlari, olasiliklar, dokunma_olasiliklari, beklenen_getiriler, skorlar
            )
        ]

        def filtre_adimi(adim: str, satirlar: list[tuple], kosul: Any) -> list[tuple]:
            kalanlar = [satir for satir in satirlar if kosul(satir)]
            filtre_akisi[adim]["aday"] += len(kalanlar)
            filtre_akisi[adim]["gercek_tavan"] += sum(satir[0][3] for satir in kalanlar)
            return kalanlar

        filtre_akisi["tum"]["aday"] += len(puanlananlar)
        filtre_akisi["tum"]["gercek_tavan"] += sum(satir[0][3] for satir in puanlananlar)
        filtresiz_ilk_n = sorted(puanlananlar, key=lambda oge: oge[4], reverse=True)[:max(1, top_n)]
        filtresiz_top_n_dogru += sum(satir[0][3] for satir in filtresiz_ilk_n)
        filtresiz_top_n_tahmin += len(filtresiz_ilk_n)

        kalanlar = filtre_adimi(
            "erken_filtre", puanlananlar,
            lambda oge: not erken_filtre or erken_tavan_adayi_mi(oge[0][1]),
        )
        kalanlar = filtre_adimi("kapanma", kalanlar, lambda oge: oge[1] >= minimum_kapanma_olasiligi)
        kalanlar = filtre_adimi("dokunma", kalanlar, lambda oge: oge[2] >= minimum_dokunma_olasiligi)
        kalanlar = filtre_adimi("getiri", kalanlar, lambda oge: oge[3] >= minimum_beklenen_getiri)
        kalanlar = filtre_adimi(
            "momentum_hacim", kalanlar,
            lambda oge: not momentum_hacim_filtresi or len(oge[0][1]) < 20 or (
                    oge[0][1][13] > 0
                    and oge[0][1][2] > 0
                    and np.expm1(oge[0][1][4]) >= 1.1
                    and oge[0][1][13] < 0.08
                    and oge[0][1][2] < 0.25
                    and oge[0][1][0] <= 0.80
                ),
        )
        sirali = sorted(
            (
                (satir, olasilik, dokunma_olasilik, skor)
                for satir, olasilik, dokunma_olasilik, _, skor in kalanlar
            ),
            key=lambda oge: oge[3],
            reverse=True,
        )
        adaylar = sirali[: max(1, top_n)]
        gercek_dokunmalar = {satir[0] for satir in test_satirlari if satir[2] == 1}
        gercekler = {satir[0] for satir in test_satirlari if satir[3] == 1}
        tahminler = {satir[0] for satir, _, _, _ in adaylar}
        dogrular = tahminler & gercekler
        dokunma_dogrulari = tahminler & gercek_dokunmalar
        net_getiri = (
            (float(np.mean([satir[4] for satir, _, _, _ in adaylar])) - islem_maliyeti_bps / 10000)
            * gunluk_maruz_kalma
            if adaylar else 0.0
        )
        gunluk_net_getiriler.append(net_getiri)
        tum_gercekler.extend(satir[3] for satir in test_satirlari)
        tum_olasiliklar.extend(float(olasilik) for olasilik in olasiliklar)
        toplam_dogru += len(dogrular)
        toplam_dokunma_dogru += len(dokunma_dogrulari)
        toplam_aday += len(tahminler)
        toplam_gercek += len(gercekler)
        toplam_dokunma_gercek += len(gercek_dokunmalar)
        gunler.append({
            "tarih": test_tarihi,
            "adaylar": [satir[0] for satir, _, _, _ in adaylar],
            "puanlananlar": [
                {
                    "sembol": satir[0],
                    "kapanma_olasiligi": round(float(olasilik), 6),
                    "dokunma_olasiligi": round(float(dokunma_olasilik), 6),
                    "beklenen_getiri": round(float(beklenen_getiri), 6),
                    "dusus_riski": round(float(dusus_riski), 6),
                    "gercek_getiri": round(float(satir[4]), 6),
                    "tavanda_kapandi": bool(satir[3]),
                    "tavana_dokundu": bool(satir[2]),
                }
                for satir, olasilik, dokunma_olasilik, beklenen_getiri, dusus_riski in zip(
                    test_satirlari, olasiliklar, dokunma_olasiliklari, beklenen_getiriler, dusus_riskleri
                )
            ],
            "dogrular": sorted(dogrular),
            "gercek_tavanlar": sorted(gercekler),
            "dokunma_dogrulari": sorted(dokunma_dogrulari),
            "gercek_tavana_dokunanlar": sorted(gercek_dokunmalar),
            "precision": round(len(dogrular) / len(tahminler) * 100, 1) if tahminler else 0.0,
            "recall": round(len(dogrular) / len(gercekler) * 100, 1) if gercekler else 0.0,
            "net_getiri": round(net_getiri * 100, 3),
        })
    sermaye = 1.0
    zirve = 1.0
    maksimum_dusus = 0.0
    for gunluk_getiri in gunluk_net_getiriler:
        sermaye *= 1 + gunluk_getiri
        zirve = max(zirve, sermaye)
        maksimum_dusus = min(maksimum_dusus, sermaye / zirve - 1)
    return {
        "gunler": gunler,
        "ozet": {
            "test_gunu": len(gunler),
            "top_n": top_n,
            "dogru": toplam_dogru,
            "tahmin": toplam_aday,
            "gercek_tavan": toplam_gercek,
            "precision_at_n": round(toplam_dogru / toplam_aday * 100, 1) if toplam_aday else None,
            "recall_at_n": round(toplam_dogru / toplam_gercek * 100, 1) if toplam_gercek else 0.0,
            "dokunma_precision_at_n": round(toplam_dokunma_dogru / toplam_aday * 100, 1) if toplam_aday else None,
            "dokunma_recall_at_n": round(toplam_dokunma_dogru / toplam_dokunma_gercek * 100, 1) if toplam_dokunma_gercek else 0.0,
            "brier": round(brier_score_loss(tum_gercekler, tum_olasiliklar), 4) if tum_gercekler else None,
            "ortalama_gunluk_net_getiri": round(float(np.mean(gunluk_net_getiriler)) * 100, 3) if gunluk_net_getiriler else None,
            "bilesik_net_getiri": round((sermaye - 1) * 100, 2) if gunluk_net_getiriler else None,
            "maksimum_dusus": round(maksimum_dusus * 100, 2) if gunluk_net_getiriler else None,
            "islem_maliyeti_bps": islem_maliyeti_bps,
            "gunluk_maruz_kalma": gunluk_maruz_kalma,
            "purge_gunu": purge_gunu,
            "erken_filtre": erken_filtre,
            "momentum_hacim_filtresi": momentum_hacim_filtresi,
            "minimum_kapanma_olasiligi": minimum_kapanma_olasiligi,
            "minimum_dokunma_olasiligi": minimum_dokunma_olasiligi,
            "minimum_beklenen_getiri": minimum_beklenen_getiri,
            "model_secimleri": model_secimleri,
            "filtre_akisi": filtre_akisi,
            "filtresiz_precision_at_n": round(
                filtresiz_top_n_dogru / filtresiz_top_n_tahmin * 100, 1
            ) if filtresiz_top_n_tahmin else None,
            "filtresiz_dogru": filtresiz_top_n_dogru,
            "filtresiz_tahmin": filtresiz_top_n_tahmin,
        },
    }


def _aday_profili_metrikleri(
    gunler: list[dict[str, Any]],
    profil: dict[str, Any],
    islem_maliyeti_bps: float,
    gunluk_maruz_kalma: float,
) -> dict[str, Any]:
    toplam_tahmin = toplam_dogru = toplam_gercek = 0
    gunluk_net_getiriler = []
    for gun in gunler:
        puanlananlar = gun.get("puanlananlar", [])
        toplam_gercek += sum(bool(aday.get("tavanda_kapandi")) for aday in puanlananlar)
        uygunlar = [
            aday for aday in puanlananlar
            if aday.get("kapanma_olasiligi", 0) >= profil["minimum_kapanma_olasiligi"]
            and aday.get("dokunma_olasiligi", 0) >= profil["minimum_dokunma_olasiligi"]
            and aday.get("beklenen_getiri", -1) >= profil.get("minimum_beklenen_getiri", -1)
            and aday.get("dusus_riski", 1) <= profil.get("maksimum_dusus_riski", 1)
        ]
        sirali = sorted(
            uygunlar,
            key=lambda aday: (
                aday.get("kapanma_olasiligi", 0) * profil["kapanma_agirligi"]
                + aday.get("dokunma_olasiligi", 0) * profil["dokunma_agirligi"]
            ),
            reverse=True,
        )
        secilenler = sirali[:profil["top_n"]]
        toplam_tahmin += len(secilenler)
        toplam_dogru += sum(bool(aday.get("tavanda_kapandi")) for aday in secilenler)
        gunluk_net_getiriler.append(
            (
                float(np.mean([aday.get("gercek_getiri", 0.0) for aday in secilenler]))
                - islem_maliyeti_bps / 10000
            ) * gunluk_maruz_kalma
            if secilenler else 0.0
        )

    sermaye = zirve = 1.0
    maksimum_dusus = 0.0
    for gunluk_getiri in gunluk_net_getiriler:
        sermaye *= 1 + gunluk_getiri
        zirve = max(zirve, sermaye)
        maksimum_dusus = min(maksimum_dusus, sermaye / zirve - 1)
    precision_alt, precision_ust = _wilson_guven_araligi(toplam_dogru, toplam_tahmin)
    ortalama_net_getiri = float(np.mean(gunluk_net_getiriler)) if gunluk_net_getiriler else None
    getiri_guven_alt = _ortalama_guven_alt(gunluk_net_getiriler)
    return {
        "gun": len(gunler),
        "tahmin": toplam_tahmin,
        "dogru": toplam_dogru,
        "gercek_tavan": toplam_gercek,
        "aktif_gun": sum(getiri != 0 for getiri in gunluk_net_getiriler),
        "precision": round(toplam_dogru / toplam_tahmin * 100, 1) if toplam_tahmin else None,
        "precision_guven95_alt": round(precision_alt * 100, 1) if precision_alt is not None else None,
        "precision_guven95_ust": round(precision_ust * 100, 1) if precision_ust is not None else None,
        "recall": round(toplam_dogru / toplam_gercek * 100, 1) if toplam_gercek else 0.0,
        "ortalama_gunluk_net_getiri": round(ortalama_net_getiri * 100, 3) if ortalama_net_getiri is not None else None,
        "ortalama_gunluk_net_getiri_guven95_alt": round(getiri_guven_alt * 100, 3) if getiri_guven_alt is not None else None,
        "bilesik_net_getiri": round((sermaye - 1) * 100, 2),
        "maksimum_dusus": round(maksimum_dusus * 100, 2),
    }


def ayrilmis_kabul_testi(
    rapor: dict[str, Any],
    kabul_test_gunu: int = 30,
    dogrulama_gunu: int = 30,
    minimum_tahmin: int = 10,
    minimum_precision: float = 10.0,
    minimum_precision_guven_alt: float = 5.0,
    minimum_net_getiri: float = 0.0,
    minimum_getiri_guven_alt: float = 0.0,
    minimum_maksimum_dusus: float = -15.0,
    profiller: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Profili eski gunlerde secer, kilitli profili son gunlerde kabul testine sokar."""
    gunler = rapor.get("gunler", [])
    veri_kapsami = rapor.get("veri_kapsami")
    if veri_kapsami and (
        veri_kapsami.get("kapsam_yuzde", 0) < 90
        or veri_kapsami.get("kullanilan_sembol", 0) < 100
    ):
        return {"durum": "yetersiz_evren_kapsami", "kabul": False}
    if (
        len(gunler) <= kabul_test_gunu + dogrulama_gunu
        or any("puanlananlar" not in gun for gun in gunler)
    ):
        return {"durum": "yetersiz_veri", "kabul": False}

    if profiller is None:
        profiller = [
            {
                "ad": (
                    f"k{kapanma:.2f}_d{dokunma:.2f}_g{minimum_getiri:.2f}"
                    f"_r{maksimum_risk:.2f}_n{top_n}"
                ),
                "minimum_kapanma_olasiligi": kapanma,
                "minimum_dokunma_olasiligi": dokunma,
                "minimum_beklenen_getiri": minimum_getiri,
                "maksimum_dusus_riski": maksimum_risk,
                "kapanma_agirligi": 60,
                "dokunma_agirligi": 40,
                "top_n": top_n,
            }
            for kapanma in (0.15, 0.20, 0.25)
            for dokunma in (0.20, 0.25, 0.30)
            for minimum_getiri in (0.0, 0.01)
            for maksimum_risk in (0.03, 0.02)
            for top_n in (1, 2, 3)
        ]

    kalibrasyon_sonu = -(kabul_test_gunu + dogrulama_gunu)
    kalibrasyon_gunleri = gunler[:kalibrasyon_sonu]
    dogrulama_gunleri = gunler[kalibrasyon_sonu:-kabul_test_gunu] if dogrulama_gunu else []
    kabul_gunleri = gunler[-kabul_test_gunu:]
    islem_maliyeti_bps = float(rapor.get("ozet", {}).get("islem_maliyeti_bps", 20))
    gunluk_maruz_kalma = float(rapor.get("ozet", {}).get("gunluk_maruz_kalma", 1.0))
    sonuclar = [
        (
            profil,
            _aday_profili_metrikleri(
                kalibrasyon_gunleri, profil, islem_maliyeti_bps, gunluk_maruz_kalma,
            ),
        )
        for profil in profiller
    ]
    yeterli_sonuclar = [
        sonuc for sonuc in sonuclar
        if sonuc[1]["tahmin"] >= minimum_tahmin
        and sonuc[1]["precision"] is not None
        and sonuc[1]["precision"] >= minimum_precision
        and sonuc[1]["precision_guven95_alt"] is not None
        and sonuc[1]["precision_guven95_alt"] >= minimum_precision_guven_alt
        and sonuc[1]["bilesik_net_getiri"] > minimum_net_getiri
        and sonuc[1]["ortalama_gunluk_net_getiri_guven95_alt"] is not None
        and sonuc[1]["ortalama_gunluk_net_getiri_guven95_alt"] > minimum_getiri_guven_alt
        and sonuc[1]["maksimum_dusus"] >= minimum_maksimum_dusus
    ]
    if not yeterli_sonuclar:
        return {
            "durum": "kalibrasyonda_uygun_profil_yok",
            "kabul": False,
            "degerlendirilen_profil": len(sonuclar),
        }
    secilen_profil, kalibrasyon = max(
        yeterli_sonuclar,
        key=lambda sonuc: (
            sonuc[1]["precision"] if sonuc[1]["precision"] is not None else -1,
            sonuc[1]["bilesik_net_getiri"],
            sonuc[1]["maksimum_dusus"],
        ),
    )
    dogrulama = _aday_profili_metrikleri(
        dogrulama_gunleri, secilen_profil, islem_maliyeti_bps, gunluk_maruz_kalma,
    ) if dogrulama_gunleri else None
    kabul_sonucu = _aday_profili_metrikleri(
        kabul_gunleri, secilen_profil, islem_maliyeti_bps, gunluk_maruz_kalma,
    )

    def kabul_kosullari(metrikler: dict[str, Any]) -> dict[str, bool]:
        return {
            "yeterli_tahmin": metrikler["tahmin"] >= minimum_tahmin,
            "precision": metrikler["precision"] is not None
            and metrikler["precision"] >= minimum_precision,
            "precision_guven_alt": metrikler["precision_guven95_alt"] is not None
            and metrikler["precision_guven95_alt"] >= minimum_precision_guven_alt,
            "net_getiri": metrikler["bilesik_net_getiri"] > minimum_net_getiri,
            "getiri_guven_alt": metrikler["ortalama_gunluk_net_getiri_guven95_alt"] is not None
            and metrikler["ortalama_gunluk_net_getiri_guven95_alt"] > minimum_getiri_guven_alt,
            "maksimum_dusus": metrikler["maksimum_dusus"] >= minimum_maksimum_dusus,
        }

    dogrulama_kosullari = kabul_kosullari(dogrulama) if dogrulama else {}
    kosullar = kabul_kosullari(kabul_sonucu)
    return {
        "durum": "tamamlandi",
        "kabul": all(dogrulama_kosullari.values()) and all(kosullar.values()),
        "secilen_profil": secilen_profil,
        "kalibrasyon": kalibrasyon,
        "dogrulama": dogrulama,
        "kabul_testi": kabul_sonucu,
        "dogrulama_kosullari": dogrulama_kosullari,
        "kabul_kosullari": kosullar,
    }


def yahoo_veri_setlerini_al(
    semboller: list[str],
    period: str = "2y",
    kap_ozellikleri: bool = False,
) -> dict[str, dict[str, Any]]:
    """Backtest icin Yahoo'dan ham OHLCV indirip model veri setine cevirir."""
    sonuc = {}
    for sembol in semboller:
        try:
            veri = yf.Ticker(f"{sembol}.IS").history(period=period, auto_adjust=False)
            if kap_ozellikleri:
                veri = kap_ozelliklerini_ekle(veri, sembol)
            egitim = tavan_egitim_verisi(veri)
            if egitim["x"]:
                sonuc[sembol] = egitim
        except Exception:
            continue
    return sonuc


def _yerel_egitim_verisi_al(girdi: tuple[str, str, int, bool]) -> tuple[str, dict[str, Any]]:
    sembol, db, azami_satir, kap_ozellikleri = girdi
    veri = GunlukVeriDeposu(db).oku(sembol)
    if azami_satir > 0:
        veri = veri.tail(azami_satir)
    if kap_ozellikleri:
        veri = kap_ozelliklerini_ekle(veri, sembol, db)
    return sembol, tavan_egitim_verisi(veri)


def yerel_veri_setlerini_al(
    semboller: list[str],
    db: str = VARSAYILAN_DB,
    azami_satir: int = 550,
    max_calisan: int = 1,
    kap_ozellikleri: bool = False,
) -> dict[str, dict[str, Any]]:
    """Tekrarlanabilir backtest icin yerel OHLCV deposundan model verisi uretir."""
    sonuc = {}
    girdiler = [(sembol, db, azami_satir, kap_ozellikleri) for sembol in semboller]
    if max_calisan > 1:
        with ProcessPoolExecutor(max_workers=max_calisan) as havuz:
            egitimler = havuz.map(_yerel_egitim_verisi_al, girdiler)
    else:
        egitimler = map(_yerel_egitim_verisi_al, girdiler)
    for sembol, egitim in egitimler:
        if egitim["x"]:
            sonuc[sembol] = egitim
    return sonuc


def main() -> None:
    parser = argparse.ArgumentParser(description="BIST global tavan adayi backtesti")
    parser.add_argument("--semboller", default="bist_sembol_cache.json")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--test-gunu", type=int, choices=(60, 120), default=60)
    parser.add_argument("--yeniden-egit-araligi", type=int, default=10)
    parser.add_argument("--islem-maliyeti-bps", type=float, default=20)
    parser.add_argument("--maruz-kalma", type=float, default=0.25)
    parser.add_argument("--veri-kaynagi", choices=("yerel", "yahoo"), default="yerel")
    parser.add_argument("--db", default=VARSAYILAN_DB)
    parser.add_argument("--azami-satir", type=int, default=550)
    parser.add_argument("--veri-calisan", type=int, default=1)
    parser.add_argument("--kap-ozellikleri", action="store_true")
    parser.add_argument("--cikti", default="reports/tavan_backtest.json")
    args = parser.parse_args()
    tum_semboller = json.loads(Path(args.semboller).read_text(encoding="utf-8"))
    semboller = temsili_sembol_ornekle(tum_semboller, args.limit)
    veri_setleri = (
        yerel_veri_setlerini_al(
            semboller,
            db=args.db,
            azami_satir=args.azami_satir,
            max_calisan=args.veri_calisan,
            kap_ozellikleri=args.kap_ozellikleri,
        )
        if args.veri_kaynagi == "yerel"
        else yahoo_veri_setlerini_al(semboller, kap_ozellikleri=args.kap_ozellikleri)
    )
    rapor = tarih_bazli_global_backtest(
        veri_setleri,
        top_n=args.top,
        son_test_gunu=args.test_gunu,
        yeniden_egit_araligi=args.yeniden_egit_araligi,
        islem_maliyeti_bps=args.islem_maliyeti_bps,
        gunluk_maruz_kalma=args.maruz_kalma,
        minimum_kapanma_olasiligi=0.15,
        minimum_dokunma_olasiligi=0.20,
        purge_gunu=1,
    )
    rapor["veri_kapsami"] = {
        "kaynak": args.veri_kaynagi,
        "istenen_sembol": len(semboller),
        "kullanilan_sembol": len(veri_setleri),
        "kapsam_yuzde": round(len(veri_setleri) / len(semboller) * 100, 1) if semboller else 0.0,
        "azami_satir": args.azami_satir if args.veri_kaynagi == "yerel" else None,
    }
    rapor["metadata"] = {
        "rapor_sema_surumu": RAPOR_SEMA_SURUMU,
        "model_surumu": KAP_MODEL_SURUMU if args.kap_ozellikleri else MODEL_SURUMU,
        "kap_ozellikleri": args.kap_ozellikleri,
        "uretim_zamani": datetime.now(timezone.utc).isoformat(),
        "yeniden_egit_araligi": args.yeniden_egit_araligi,
        "model_adaylari": [ad for ad, _ in _model_adaylari()],
    }
    rapor["ayrilmis_kabul_testi"] = ayrilmis_kabul_testi(rapor)
    cikti = Path(args.cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ozet": rapor["ozet"],
        "ayrilmis_kabul_testi": rapor["ayrilmis_kabul_testi"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()