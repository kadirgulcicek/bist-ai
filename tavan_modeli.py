"""Ertesi gun yuksek hareket adaylari icin walk-forward model."""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
import os
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from catboost import CatBoostClassifier
except ImportError:
    CatBoostClassifier = None


MIN_TRAIN_SAMPLES = 60
MODEL_SURUMU = "global-dual-v8-executable"
KAP_MODEL_SURUMU = "global-dual-v10-kap-events-experimental"
OZELLIK_GUNLUK_GETIRI = 13
OZELLIK_UST_FITIL = 14
OZELLIK_HACIM_TRENDI = 15
OZELLIK_KAP_24S = 16
OZELLIK_KAP_7G = 17
OZELLIK_KAP_GECIKMELI_30G = 18
OZELLIK_KAP_PIYASA_24S = 19
OZELLIK_KAP_IS_ILISKISI_7G = 20
OZELLIK_KAP_SERMAYE_7G = 21
OZELLIK_KAP_PAY_ISLEMI_7G = 22
OZELLIK_KAP_FINANSAL_7G = 23
OZELLIK_KAP_NEGATIF_7G = 24
OZELLIK_ONCEKI_TAVAN = 25
FIYAT_ADIMLARI = (
    (Decimal("20"), Decimal("0.01")),
    (Decimal("50"), Decimal("0.02")),
    (Decimal("100"), Decimal("0.05")),
    (Decimal("250"), Decimal("0.10")),
    (Decimal("500"), Decimal("0.25")),
    (Decimal("1000"), Decimal("0.50")),
    (Decimal("2500"), Decimal("1.00")),
    (Decimal("Infinity"), Decimal("2.50")),
)


def fiyat_adimi(fiyat: float | Decimal) -> Decimal:
    deger = Decimal(str(fiyat))
    for ust_sinir, adim in FIYAT_ADIMLARI:
        if deger < ust_sinir:
            return adim
    return FIYAT_ADIMLARI[-1][1]


def tavan_fiyati(baz_fiyat: float | Decimal) -> float:
    """Yuzde 10 ust limite fiyat adimi uygulayarak islem gorebilir tavan fiyatini hesaplar."""
    baz = Decimal(str(baz_fiyat))
    if not baz.is_finite() or baz <= 0:
        raise ValueError("Baz fiyat pozitif ve sonlu olmali")
    baz_adimi = fiyat_adimi(baz)
    baz = (baz / baz_adimi).to_integral_value(rounding=ROUND_HALF_UP) * baz_adimi
    teorik_tavan = baz * Decimal("1.10")
    adim = fiyat_adimi(teorik_tavan)
    return float((teorik_tavan / adim).to_integral_value(rounding=ROUND_FLOOR) * adim)


def tavana_ulasti(baz_fiyat: float, fiyat: float, tolerans: float = 1e-8) -> bool:
    tavan = tavan_fiyati(baz_fiyat)
    kayan_nokta_toleransi = abs(tavan) * 1e-6
    return float(fiyat) + max(tolerans, kayan_nokta_toleransi) >= tavan


def wilder_ortalama(seri: pd.Series, periyot: int = 14) -> pd.Series:
    """Wilder'in ilk basit ortalama ve devaminda rekursif duzeltme yontemi."""
    degerler = seri.astype(float)
    sonuc = pd.Series(np.nan, index=degerler.index, dtype=float)
    ilk_ortalamalar = degerler.rolling(periyot, min_periods=periyot).mean()
    gecerli = np.flatnonzero(ilk_ortalamalar.notna().to_numpy())
    if not len(gecerli):
        return sonuc
    ilk = int(gecerli[0])
    sonuc.iloc[ilk] = float(ilk_ortalamalar.iloc[ilk])
    for konum in range(ilk + 1, len(degerler)):
        deger = degerler.iloc[konum]
        if pd.isna(deger):
            sonuc.iloc[konum] = sonuc.iloc[konum - 1]
        else:
            sonuc.iloc[konum] = (sonuc.iloc[konum - 1] * (periyot - 1) + float(deger)) / periyot
    return sonuc


def wilder_rsi(kapanis: pd.Series, periyot: int = 14) -> pd.Series:
    delta = kapanis.astype(float).diff()
    ortalama_kazanc = wilder_ortalama(delta.clip(lower=0), periyot)
    ortalama_kayip = wilder_ortalama(-delta.clip(upper=0), periyot)
    rsi = pd.Series(np.nan, index=kapanis.index, dtype=float)
    ikisi_sifir = (ortalama_kazanc == 0) & (ortalama_kayip == 0)
    sadece_kayip_sifir = (ortalama_kazanc > 0) & (ortalama_kayip == 0)
    sadece_kazanc_sifir = (ortalama_kazanc == 0) & (ortalama_kayip > 0)
    normal = (ortalama_kazanc > 0) & (ortalama_kayip > 0)
    rsi.loc[ikisi_sifir] = 50.0
    rsi.loc[sadece_kayip_sifir] = 100.0
    rsi.loc[sadece_kazanc_sifir] = 0.0
    oran = ortalama_kazanc.loc[normal] / ortalama_kayip.loc[normal]
    rsi.loc[normal] = 100 - 100 / (1 + oran)
    return rsi


def true_range(yuksek: pd.Series, dusuk: pd.Series, kapanis: pd.Series) -> pd.Series:
    onceki_kapanis = kapanis.astype(float).shift()
    return pd.concat([
        yuksek.astype(float) - dusuk.astype(float),
        (yuksek.astype(float) - onceki_kapanis).abs(),
        (dusuk.astype(float) - onceki_kapanis).abs(),
    ], axis=1).max(axis=1)


def wilder_atr(
    yuksek: pd.Series,
    dusuk: pd.Series,
    kapanis: pd.Series,
    periyot: int = 14,
) -> pd.Series:
    return wilder_ortalama(true_range(yuksek, dusuk, kapanis), periyot)


def wilder_adx(
    yuksek: pd.Series,
    dusuk: pd.Series,
    kapanis: pd.Series,
    periyot: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    yukari_hareket = yuksek.astype(float).diff()
    asagi_hareket = -dusuk.astype(float).diff()
    pozitif_dm = yukari_hareket.where((yukari_hareket > asagi_hareket) & (yukari_hareket > 0), 0.0)
    negatif_dm = asagi_hareket.where((asagi_hareket > yukari_hareket) & (asagi_hareket > 0), 0.0)
    atr = wilder_atr(yuksek, dusuk, kapanis, periyot).replace(0, np.nan)
    pozitif_di = 100 * wilder_ortalama(pozitif_dm, periyot) / atr
    negatif_di = 100 * wilder_ortalama(negatif_dm, periyot) / atr
    di_toplam = (pozitif_di + negatif_di).replace(0, np.nan)
    dx = 100 * (pozitif_di - negatif_di).abs() / di_toplam
    return wilder_ortalama(dx, periyot), pozitif_di, negatif_di


def stokastik_k(
    yuksek: pd.Series,
    dusuk: pd.Series,
    kapanis: pd.Series,
    periyot: int = 14,
) -> pd.Series:
    en_yuksek = yuksek.astype(float).rolling(periyot).max()
    en_dusuk = dusuk.astype(float).rolling(periyot).min()
    aralik = (en_yuksek - en_dusuk).replace(0, np.nan)
    return ((kapanis.astype(float) - en_dusuk) / aralik * 100).fillna(50)


def erken_tavan_adayi_mi(ozellikler: list[float]) -> bool:
    """Asiri hareketi tamamlanmis hisseleri erken aday havuzundan cikarir."""
    if len(ozellikler) < 20:
        return True
    onceki_tavan_indeksi = OZELLIK_ONCEKI_TAVAN if len(ozellikler) >= 29 else 19 if len(ozellikler) >= 23 else 16
    return bool(
        -0.08 < ozellikler[OZELLIK_GUNLUK_GETIRI] < 0.08
        and ozellikler[2] < 0.25
        and ozellikler[0] <= 0.82
        and ozellikler[OZELLIK_UST_FITIL] <= 0.70
        and ozellikler[onceki_tavan_indeksi] < 0.5
    )


def _model_adaylari() -> list[tuple[str, Any]]:
    adaylar = [(
        "logistic_regression",
        lambda: make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=500, random_state=42),
        ),
    )]
    if CatBoostClassifier is not None and os.environ.get("TAVAN_CATBOOST", "1") == "1":
        adaylar.append((
            "catboost",
            lambda: CatBoostClassifier(
                iterations=250,
                depth=5,
                learning_rate=0.05,
                auto_class_weights="Balanced",
                loss_function="Logloss",
                random_seed=42,
                verbose=False,
                thread_count=1,
            ),
        ))
    return adaylar


def _ozellikler(veri: pd.DataFrame, indeks: int) -> list[float] | None:
    kapanis = veri["Close"].iloc[: indeks + 1].astype(float)
    hacim = veri["Volume"].iloc[: indeks + 1].astype(float).fillna(0)
    if len(kapanis) < MIN_TRAIN_SAMPLES or kapanis.iloc[-1] <= 0:
        return None

    getiriler = kapanis.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if len(getiriler) < 21:
        return None
    ema12 = kapanis.ewm(span=12, adjust=False).mean()
    ema26 = kapanis.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    sinyal = macd.ewm(span=9, adjust=False).mean()
    rsi = wilder_rsi(kapanis, 14).fillna(50)
    ortalama_hacim = hacim.iloc[-21:-1].mean()
    hacim_orani = hacim.iloc[-1] / ortalama_hacim if ortalama_hacim > 0 else 1.0
    son = float(kapanis.iloc[-1])
    aralik = float(veri["High"].iloc[-1] - veri["Low"].iloc[-1])
    kapanis_gucu = (son - float(veri["Low"].iloc[-1])) / aralik if aralik > 0 else 0.5
    ust_fitil = (float(veri["High"].iloc[-1]) - son) / aralik if aralik > 0 else 0.0
    yuksek = veri["High"].iloc[: indeks + 1].astype(float)
    dusuk = veri["Low"].iloc[: indeks + 1].astype(float)
    atr = wilder_atr(yuksek, dusuk, kapanis, 14)
    atr_yuzde = float(atr.iloc[-1] / son * 100)
    macd_histogram = macd - sinyal
    bollinger_orta = kapanis.rolling(20).mean()
    bollinger_sapma = kapanis.rolling(20).std()
    bollinger_genislik = (4 * bollinger_sapma / bollinger_orta.replace(0, np.nan)).fillna(0)
    _, pozitif_di, negatif_di = wilder_adx(yuksek, dusuk, kapanis, 14)
    tavan_serisi = 0
    for konum in range(indeks, 0, -1):
        if not tavana_ulasti(float(kapanis.iloc[konum - 1]), float(kapanis.iloc[konum])):
            break
        tavan_serisi += 1
    onceki_tavan = float(tavan_serisi > 0)
    onceki_hacim = float(hacim.iloc[-2]) if len(hacim) >= 2 else 0.0
    hacim_ivmesi = float(hacim.iloc[-1] / onceki_hacim - 1) if onceki_hacim > 0 else 0.0
    kisa_hacim = float(hacim.iloc[-5:].mean())
    onceki_hacim_ortalamasi = float(hacim.iloc[-20:-5].mean())
    hacim_trendi = kisa_hacim / onceki_hacim_ortalamasi - 1 if onceki_hacim_ortalamasi > 0 else 0.0
    acilis_boslugu = 0.0
    if "Open" in veri and pd.notna(veri["Open"].iloc[indeks]) and len(kapanis) >= 2:
        acilis_boslugu = float(float(veri["Open"].iloc[indeks]) / kapanis.iloc[-2] - 1)
    def kap_degeri(kolon: str, ust_sinir: float) -> float:
        if kolon not in veri or pd.isna(veri[kolon].iloc[indeks]):
            return 0.0
        return float(np.log1p(np.clip(float(veri[kolon].iloc[indeks]), 0, ust_sinir)) / np.log1p(ust_sinir))

    return [
        float(rsi.iloc[-1]) / 100,
        float((macd.iloc[-1] - sinyal.iloc[-1]) / son),
        float((son / kapanis.iloc[-6] - 1) if len(kapanis) >= 6 else 0),
        float((son / kapanis.iloc[-21] - 1) if len(kapanis) >= 21 else 0),
        float(np.log1p(max(0, hacim_orani))),
        float(kapanis_gucu),
        float(son / kapanis.iloc[-21:-1].max() - 1),
        float(getiriler.tail(20).std()),
        float(atr_yuzde / 100),
        float((macd_histogram.iloc[-1] - macd_histogram.iloc[-2]) / son),
        float((rsi.iloc[-1] - rsi.iloc[-3]) / 100),
        float(bollinger_genislik.iloc[-1] - bollinger_genislik.iloc[-3]),
        float(((pozitif_di.iloc[-1] - negatif_di.iloc[-1]) / 100) if pd.notna(pozitif_di.iloc[-1]) and pd.notna(negatif_di.iloc[-1]) else 0),
        float(son / kapanis.iloc[-2] - 1),
        float(np.clip(ust_fitil, 0, 1)),
        float(np.clip(hacim_trendi, -1, 10) / 10),
        kap_degeri("KAP_Bildirim_24s", 20),
        kap_degeri("KAP_Bildirim_7g", 100),
        kap_degeri("KAP_Gecikmeli_30g", 20),
        kap_degeri("KAP_Piyasa_Olayi_24s", 20),
        kap_degeri("KAP_Is_Iliskisi_7g", 20),
        kap_degeri("KAP_Sermaye_7g", 20),
        kap_degeri("KAP_Pay_Islemi_7g", 20),
        kap_degeri("KAP_Finansal_7g", 20),
        kap_degeri("KAP_Negatif_7g", 20),
        onceki_tavan,
        float(min(tavan_serisi, 5) / 5),
        float(np.clip(hacim_ivmesi, -1, 10) / 10),
        float(np.clip(acilis_boslugu, -0.2, 0.2)),
    ]


def tavan_egitim_verisi(veri: pd.DataFrame) -> dict[str, Any]:
    """Bir hissenin tarihli egitim satirlarini ve en guncel ozelligini uretir."""
    gerekli = {"Close", "High", "Low", "Volume"}
    if veri is None or not gerekli.issubset(veri.columns):
        return {"x": [], "dokunma_y": [], "kapanma_y": [], "tarihler": [], "son_ozellik": None}
    temiz = veri.dropna(subset=list(gerekli)).copy()
    x, dokunma_y, kapanma_y, tarihler, sonraki_getiriler = [], [], [], [], []
    atlanan_kurumsal_aksiyon = 0
    for indeks in range(MIN_TRAIN_SAMPLES, len(temiz) - 1):
        bolunme_var = (
            "Stock Splits" in temiz
            and (
                float(temiz["Stock Splits"].fillna(0).iloc[indeks]) != 0
                or float(temiz["Stock Splits"].fillna(0).iloc[indeks + 1]) != 0
            )
        )
        mevcut_kapanis = float(temiz["Close"].iloc[indeks])
        sonraki_kapanis = float(temiz["Close"].iloc[indeks + 1])
        fiyat_kopuklugu = sonraki_kapanis / mevcut_kapanis < 0.5 or sonraki_kapanis / mevcut_kapanis > 1.5
        if bolunme_var or fiyat_kopuklugu:
            atlanan_kurumsal_aksiyon += 1
            continue
        ozellik = _ozellikler(temiz, indeks)
        if ozellik is None or not np.isfinite(ozellik).all():
            continue
        sonraki_yuksek = float(temiz["High"].iloc[indeks + 1])
        sonraki_acilis = (
            float(temiz["Open"].iloc[indeks + 1])
            if "Open" in temiz and pd.notna(temiz["Open"].iloc[indeks + 1])
            else mevcut_kapanis
        )
        islem_gerceklesti = not tavana_ulasti(mevcut_kapanis, sonraki_acilis)
        x.append(ozellik)
        dokunma_y.append(int(tavana_ulasti(mevcut_kapanis, sonraki_yuksek)))
        kapanma_y.append(int(tavana_ulasti(mevcut_kapanis, sonraki_kapanis)))
        sonraki_getiriler.append(
            float(sonraki_kapanis / sonraki_acilis - 1)
            if islem_gerceklesti and sonraki_acilis > 0 else 0.0
        )
        tarih = temiz.index[indeks]
        tarihler.append(tarih.isoformat() if hasattr(tarih, "isoformat") else str(tarih))
    son_ozellik = _ozellikler(temiz, len(temiz) - 1) if len(temiz) > MIN_TRAIN_SAMPLES else None
    return {
        "x": x,
        "dokunma_y": dokunma_y,
        "kapanma_y": kapanma_y,
        "tarihler": tarihler,
        "sonraki_getiriler": sonraki_getiriler,
        "atlanan_kurumsal_aksiyon": atlanan_kurumsal_aksiyon,
        "son_ozellik": son_ozellik,
    }


def _model_sonucu(x: list[list[float]], y: list[int], son_ozellik: list[float] | None) -> dict[str, Any]:
    if len(x) < MIN_TRAIN_SAMPLES or son_ozellik is None:
        return {"olasilik": None, "ham_olasilik": None, "precision": None, "recall": None, "brier": None}
    if len(set(y)) < 2:
        taban_oran = sum(y) / len(y)
        return {
            "olasilik": round(taban_oran * 100, 1),
            "ham_olasilik": round(taban_oran * 100, 1),
            "precision": None,
            "recall": None,
            "brier": 0.0,
        }
    ayrim = max(MIN_TRAIN_SAMPLES, int(len(x) * 0.8))
    dogrulama_gercek = y[ayrim:]
    dogrulama_tahmin = []
    if dogrulama_gercek and len(set(y[:ayrim])) >= 2:
        dogrulama_modeli = make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=500, random_state=42),
        )
        dogrulama_modeli.fit(x[:ayrim], y[:ayrim])
        dogrulama_tahmin = dogrulama_modeli.predict_proba(x[ayrim:])[:, 1].tolist()

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=500, random_state=42),
    )
    model.fit(x, y)
    ham_olasilik = float(model.predict_proba([son_ozellik])[0, 1])
    taban_oran = sum(y) / len(y)
    benzer = [
        gercek for tahmin, gercek in zip(dogrulama_tahmin, dogrulama_gercek)
        if abs(tahmin - ham_olasilik) <= 0.1
    ]
    olasilik = (sum(benzer) + taban_oran * 10) / (len(benzer) + 10) if benzer else (ham_olasilik + taban_oran * 2) / 3
    siniflar = [int(tahmin >= 0.5) for tahmin in dogrulama_tahmin]
    return {
        "olasilik": round(olasilik * 100, 1),
        "ham_olasilik": round(ham_olasilik * 100, 1),
        "precision": round(precision_score(dogrulama_gercek, siniflar, zero_division=0) * 100, 1) if siniflar else None,
        "recall": round(recall_score(dogrulama_gercek, siniflar, zero_division=0) * 100, 1) if siniflar else None,
        "brier": round(brier_score_loss(dogrulama_gercek, dogrulama_tahmin), 4) if dogrulama_tahmin else None,
    }


def walk_forward_tavan_istatistigi(
    veri: pd.DataFrame,
    egitim: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tek hisse icin zaman sirali cift hedefli model istatistigi uretir."""
    egitim = egitim or tavan_egitim_verisi(veri)
    kapanma = _model_sonucu(egitim["x"], egitim["kapanma_y"], egitim["son_ozellik"])
    dokunma = _model_sonucu(egitim["x"], egitim["dokunma_y"], egitim["son_ozellik"])
    return {
        "olasilik": kapanma["olasilik"],
        "ham_olasilik": kapanma["ham_olasilik"],
        "precision": kapanma["precision"],
        "recall": kapanma["recall"],
        "brier": kapanma["brier"],
        "dokunma_olasiligi": dokunma["olasilik"],
        "dokunma_precision": dokunma["precision"],
        "dokunma_recall": dokunma["recall"],
        "ornek": len(egitim["x"]),
        "pozitif": sum(egitim["kapanma_y"]),
        "dokunma_pozitif": sum(egitim["dokunma_y"]),
        "model_surumu": MODEL_SURUMU,
    }


def global_tavan_tahminleri(veri_setleri: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Tum hisselerin gecmisini tek zaman sirali modelde birlestirip tahmin eder."""
    satirlar = []
    for sembol, egitim in veri_setleri.items():
        getiriler = egitim.get("sonraki_getiriler", [])
        for indeks, (tarih, ozellik, dokunma, kapanma) in enumerate(zip(
            egitim.get("tarihler", []), egitim.get("x", []),
            egitim.get("dokunma_y", []), egitim.get("kapanma_y", []),
        )):
            sonraki_getiri = float(getiriler[indeks]) if indeks < len(getiriler) else 0.0
            satirlar.append((tarih, sembol, ozellik, dokunma, kapanma, sonraki_getiri))
    satirlar.sort(key=lambda satir: (satir[0], satir[1]))
    x = [satir[2] for satir in satirlar]
    dokunma_y = [satir[3] for satir in satirlar]
    kapanma_y = [satir[4] for satir in satirlar]
    sonraki_getiriler = [satir[5] for satir in satirlar]
    son_ozellikler = {
        sembol: egitim.get("son_ozellik")
        for sembol, egitim in veri_setleri.items()
        if egitim.get("son_ozellik") is not None
    }
    if len(x) < MIN_TRAIN_SAMPLES or (len(set(kapanma_y)) < 2 and len(set(dokunma_y)) < 2):
        return {"tahminler": {}, "metrikler": {}, "model_surumu": MODEL_SURUMU}
    if len({satir[0] for satir in satirlar}) < 3:
        return {"tahminler": {}, "metrikler": {}, "model_surumu": MODEL_SURUMU}

    def hedefi_egit(y: list[int]) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
        def taban_sonucu() -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
            taban = sum(y) / len(y)
            tahminler = {sembol: round(taban * 100, 1) for sembol in son_ozellikler}
            return (
                tahminler,
                tahminler.copy(),
                {"precision": None, "recall": None, "brier": 0.0, "ornek": len(y), "pozitif": sum(y)},
            )

        if len(set(y)) < 2:
            return taban_sonucu()
        benzersiz_tarihler = sorted({satir[0] for satir in satirlar})
        kalibrasyon_tarihi = benzersiz_tarihler[max(1, int(len(benzersiz_tarihler) * 0.7))]
        test_tarihi = benzersiz_tarihler[max(2, int(len(benzersiz_tarihler) * 0.85))]
        kalibrasyon_baslangici = next((i for i, satir in enumerate(satirlar) if satir[0] >= kalibrasyon_tarihi), len(x) - 2)
        test_baslangici = next((i for i, satir in enumerate(satirlar) if satir[0] >= test_tarihi), len(x) - 1)
        kalibrasyon_baslangici = max(MIN_TRAIN_SAMPLES, min(kalibrasyon_baslangici, len(x) - 2))
        model_sonu_tarihi = benzersiz_tarihler[max(0, benzersiz_tarihler.index(kalibrasyon_tarihi) - 1)]
        model_sonu = next(
            (i for i, satir in enumerate(satirlar) if satir[0] >= model_sonu_tarihi),
            kalibrasyon_baslangici,
        )
        while kalibrasyon_baslangici < len(x) - 2 and len(set(y[:model_sonu])) < 2:
            kalibrasyon_baslangici += 1
            kalibrasyon_tarihi = satirlar[kalibrasyon_baslangici][0]
            onceki_tarihler = [tarih for tarih in benzersiz_tarihler if tarih < kalibrasyon_tarihi]
            if len(onceki_tarihler) < 2:
                continue
            model_sonu = next(
                (i for i, satir in enumerate(satirlar) if satir[0] >= onceki_tarihler[-1]),
                kalibrasyon_baslangici,
            )
        if len(set(y[:model_sonu])) < 2:
            return taban_sonucu()
        test_baslangici = max(kalibrasyon_baslangici + 1, min(test_baslangici, len(x) - 1))
        test_onceki_tarihler = [tarih for tarih in benzersiz_tarihler if tarih < satirlar[test_baslangici][0]]
        kalibrasyon_sonu = next(
            (i for i, satir in enumerate(satirlar) if satir[0] >= test_onceki_tarihler[-1]),
            test_baslangici,
        ) if test_onceki_tarihler else test_baslangici
        kalibrasyon_y = y[kalibrasyon_baslangici:kalibrasyon_sonu]
        if not kalibrasyon_y:
            return taban_sonucu()
        model_sonuclari = []
        for model_adi, model_uret in _model_adaylari():
            aday_model = model_uret()
            aday_model.fit(x[:model_sonu], y[:model_sonu])
            aday_olasilik = aday_model.predict_proba(x[kalibrasyon_baslangici:kalibrasyon_sonu])[:, 1]
            model_sonuclari.append((
                average_precision_score(kalibrasyon_y, aday_olasilik),
                brier_score_loss(kalibrasyon_y, aday_olasilik),
                model_adi,
                model_uret,
                aday_model,
                aday_olasilik,
            ))
        _, _, secilen_model_adi, secilen_model_uret, model, kalibrasyon_ham = min(
            model_sonuclari, key=lambda sonuc: (-sonuc[0], sonuc[1])
        )
        kalibrator = None
        if len(set(kalibrasyon_y)) >= 2:
            kalibrator = LogisticRegression(max_iter=500, random_state=42)
            kalibrator.fit(kalibrasyon_ham.reshape(-1, 1), kalibrasyon_y)
        test_model_sonu = next(
            (i for i, satir in enumerate(satirlar) if satir[0] >= test_onceki_tarihler[-1]),
            test_baslangici,
        ) if test_onceki_tarihler else test_baslangici
        model = secilen_model_uret()
        model.fit(x[:test_model_sonu], y[:test_model_sonu])
        test_ham = model.predict_proba(x[test_baslangici:])[:, 1]
        test_olasilik = kalibrator.predict_proba(test_ham.reshape(-1, 1))[:, 1] if kalibrator else test_ham
        test_sinif = (test_olasilik >= 0.5).astype(int)
        test_y = y[test_baslangici:]
        gunluk_sonuclar: dict[str, list[tuple[float, int]]] = {}
        for satir, olasilik, gercek in zip(satirlar[test_baslangici:], test_olasilik, test_y):
            gunluk_sonuclar.setdefault(satir[0], []).append((float(olasilik), gercek))
        top5_dogru = top5_tahmin = top5_gercek = 0
        for gun_sonuclari in gunluk_sonuclar.values():
            ilk_bes = sorted(gun_sonuclari, key=lambda sonuc: sonuc[0], reverse=True)[:5]
            top5_dogru += sum(gercek for _, gercek in ilk_bes)
            top5_tahmin += len(ilk_bes)
            top5_gercek += sum(gercek for _, gercek in gun_sonuclari)
        metrikler = {
            "precision": round(precision_score(test_y, test_sinif, zero_division=0) * 100, 1),
            "recall": round(recall_score(test_y, test_sinif, zero_division=0) * 100, 1),
            "brier": round(brier_score_loss(test_y, test_olasilik), 4),
            "ornek": len(y),
            "pozitif": sum(y),
            "taban_oran": round(sum(test_y) / len(test_y) * 100, 2),
            "precision_at_5": round(top5_dogru / top5_tahmin * 100, 1) if top5_tahmin else None,
            "recall_at_5": round(top5_dogru / top5_gercek * 100, 1) if top5_gercek else 0.0,
            "secilen_model": secilen_model_adi,
            "model_karsilastirmasi": {
                model_adi: round(float(brier), 4)
                for _, brier, model_adi, _, _, _ in model_sonuclari
            },
            "model_karsilastirmasi_average_precision": {
                model_adi: round(float(average_precision), 4)
                for average_precision, _, model_adi, _, _, _ in model_sonuclari
            },
            "catboost_kullanilabilir": CatBoostClassifier is not None,
            "purge_gunu": 1,
        }
        model = secilen_model_uret()
        model.fit(x, y)
        ham = {sembol: float(model.predict_proba([ozellik])[0, 1]) for sembol, ozellik in son_ozellikler.items()}
        tahminler = {
            sembol: round(float(kalibrator.predict_proba([[olasilik]])[0, 1] if kalibrator else olasilik) * 100, 1)
            for sembol, olasilik in ham.items()
        }
        ham_tahminler = {sembol: round(olasilik * 100, 1) for sembol, olasilik in ham.items()}
        return tahminler, ham_tahminler, metrikler

    dokunma, dokunma_ham, dokunma_metrikleri = hedefi_egit(dokunma_y)
    kapanma, kapanma_ham, kapanma_metrikleri = hedefi_egit(kapanma_y)
    getiri_modeli = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    risk_modeli = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    sinirli_getiriler = np.clip(sonraki_getiriler, -0.10, 0.10)
    asagi_riskler = np.maximum(-sinirli_getiriler, 0)
    getiri_modeli.fit(x, sinirli_getiriler)
    risk_modeli.fit(x, asagi_riskler)
    beklenen_getiriler = {
        sembol: float(np.clip(getiri_modeli.predict([ozellik])[0], -0.10, 0.10) * 100)
        for sembol, ozellik in son_ozellikler.items()
    }
    dusus_riskleri = {
        sembol: float(np.clip(risk_modeli.predict([ozellik])[0], 0, 0.10) * 100)
        for sembol, ozellik in son_ozellikler.items()
    }
    return {
        "tahminler": {
            sembol: {
                "dokunma": dokunma.get(sembol),
                "dokunma_ham": dokunma_ham.get(sembol),
                "kapanma": kapanma.get(sembol),
                "kapanma_ham": kapanma_ham.get(sembol),
                "beklenen_getiri": round(beklenen_getiriler[sembol], 2),
                "dusus_riski": round(dusus_riskleri[sembol], 2),
                "siralama_skoru": round(
                    (kapanma_ham.get(sembol) or 0) * 0.60
                    + (dokunma_ham.get(sembol) or 0) * 0.40,
                    2,
                ),
            }
            for sembol in son_ozellikler
        },
        "metrikler": {"dokunma": dokunma_metrikleri, "kapanma": kapanma_metrikleri},
        "model_surumu": MODEL_SURUMU,
    }
