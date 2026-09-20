import json
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

import kapsamli_analiz


@pytest.fixture(autouse=True)
def sinyal_gecmisini_izole_et(monkeypatch, tmp_path):
    monkeypatch.setattr(
        kapsamli_analiz,
        "TAVAN_SINYAL_GECMISI",
        str(tmp_path / "tavan_sinyal_gecmisi.json"),
    )


def test_hisse_analizi_missing_sections_keeps_score_and_confidence(monkeypatch):
    monkeypatch.setattr(
        kapsamli_analiz,
        "_teknik_ve_trade",
        lambda sembol: (
            {"puan": 80, "fiyat": 100, "volatilite": 20, "sebepler": []},
            {"puan": 70, "karar": "TRADE ADAYI", "sebepler": []},
        ),
    )
    monkeypatch.setattr(kapsamli_analiz, "temel_analiz", lambda sembol: None)
    monkeypatch.setattr(kapsamli_analiz, "hedef_fiyat_tahmin", lambda sembol, gun_hedef=5: None)
    monkeypatch.setattr(kapsamli_analiz, "takas_analiz", lambda sembol, kullanici=None: None)

    sonuc = kapsamli_analiz.hisse_analiz_et("THYAO")

    assert sonuc["skor"] > 0
    assert sonuc["veri_guveni"] < 100
    assert sonuc["skorlar"]["teknik"] == 80
    assert sonuc["trade"]["karar"] == "TRADE ADAYI"


def test_gunluk_veri_istanbul_seans_kapanisindan_sonra_tamamlanir():
    saat_dilimi = ZoneInfo("Europe/Istanbul")

    assert kapsamli_analiz._gunluk_veri_tamamlandi_mi(
        "2026-09-18", datetime(2026, 9, 18, 17, 59, tzinfo=saat_dilimi)
    ) is False
    assert kapsamli_analiz._gunluk_veri_tamamlandi_mi(
        "2026-09-18", datetime(2026, 9, 18, 18, 10, tzinfo=saat_dilimi)
    ) is True
    assert kapsamli_analiz._gunluk_veri_tamamlandi_mi(
        "2026-09-17", datetime(2026, 9, 18, 10, 0, tzinfo=saat_dilimi)
    ) is True


def test_kapsamli_tarama_sorts_and_deduplicates(monkeypatch, tmp_path):
    monkeypatch.setattr(kapsamli_analiz, "ANALIZ_CACHE", str(tmp_path / "cache.json"))
    monkeypatch.setattr(
        kapsamli_analiz,
        "hisse_analiz_et",
        lambda sembol, kullanici=None: {
            "sembol": sembol,
            "skor": 90 if sembol == "AAA" else 40,
            "veri_guveni": 100,
        },
    )

    sonuc = kapsamli_analiz.kapsamli_tarama(["BBB", "AAA", "AAA"], force=True)

    assert sonuc["sembol_sayisi"] == 2
    assert [item["sembol"] for item in sonuc["analizler"]] == ["AAA", "BBB"]


def test_kapsamli_tarama_scans_full_universe_and_returns_top_20(monkeypatch, tmp_path):
    monkeypatch.setattr(kapsamli_analiz, "ANALIZ_CACHE", str(tmp_path / "cache.json"))
    monkeypatch.setattr(kapsamli_analiz, "KAPSAMLI_ANALIZ_MAX_SEMBOL", 0)
    monkeypatch.setattr(kapsamli_analiz, "KAPSAMLI_ANALIZ_TOP_N", 20)

    calisanlar = []

    def fake_hisse_analiz_et(sembol, kullanici=None):
        calisanlar.append(sembol)
        idx = int(sembol[1:])
        return {"sembol": sembol, "skor": 100 - idx, "veri_guveni": 100}

    monkeypatch.setattr(kapsamli_analiz, "hisse_analiz_et", fake_hisse_analiz_et)

    semboller = [f"S{i:03d}" for i in range(25)]
    sonuc = kapsamli_analiz.kapsamli_tarama(semboller, force=True)

    assert sonuc["sembol_sayisi"] == 25
    assert len(calisanlar) == 25
    assert len(sonuc["analizler"]) == 20
    assert [item["sembol"] for item in sonuc["analizler"][:5]] == ["S000", "S001", "S002", "S003", "S004"]


def test_kapsamli_tarama_ignores_small_stale_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(kapsamli_analiz, "ANALIZ_CACHE", str(tmp_path / "cache.json"))
    monkeypatch.setattr(kapsamli_analiz, "ANALIZ_CACHE_TTL", 999999)
    monkeypatch.setattr(kapsamli_analiz, "KAPSAMLI_ANALIZ_TOP_N", 20)
    monkeypatch.setattr(kapsamli_analiz, "KAPSAMLI_ANALIZ_MAX_SEMBOL", 1000)

    with open(kapsamli_analiz.ANALIZ_CACHE, "w", encoding="utf-8") as dosya:
        json.dump({"zaman": 0, "sonuc": {"analizler": [{"sembol": "OLD", "skor": 1, "veri_guveni": 100}] }}, dosya)

    def fake_hisse_analiz_et(sembol, kullanici=None):
        return {"sembol": sembol, "skor": 99, "veri_guveni": 100}

    monkeypatch.setattr(kapsamli_analiz, "hisse_analiz_et", fake_hisse_analiz_et)

    sonuc = kapsamli_analiz.kapsamli_tarama(["AAA", "BBB"], force=False)

    assert len(sonuc["analizler"]) == 2
    assert [item["sembol"] for item in sonuc["analizler"]] == ["AAA", "BBB"]


def test_kapsamli_tarama_baska_kullanicinin_cache_sonucunu_kullanmaz(monkeypatch, tmp_path):
    monkeypatch.setattr(kapsamli_analiz, "ANALIZ_CACHE", str(tmp_path / "cache.json"))
    monkeypatch.setattr(kapsamli_analiz, "KAPSAMLI_ANALIZ_TOP_N", 1)
    with open(kapsamli_analiz.ANALIZ_CACHE, "w", encoding="utf-8") as dosya:
        json.dump({
            "zaman": time.time(),
            "kullanici": "alice",
            "sonuc": {
                "analizler": [{"sembol": "ALICE"}],
                "tavan_gecmis_ozeti": {},
                "tavan_izleme_listesi": [],
            },
        }, dosya)
    monkeypatch.setattr(
        kapsamli_analiz,
        "hisse_analiz_et",
        lambda sembol, kullanici=None: {"sembol": sembol, "skor": 50, "veri_guveni": 100},
    )

    sonuc = kapsamli_analiz.kapsamli_tarama(["BOB"], kullanici="bob")

    assert sonuc["analizler"][0]["sembol"] == "BOB"


def test_kapsamli_tarama_reports_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(kapsamli_analiz, "ANALIZ_CACHE", str(tmp_path / "cache.json"))

    monkeypatch.setattr(
        kapsamli_analiz,
        "hisse_analiz_et",
        lambda sembol, kullanici=None: {"sembol": sembol, "skor": 50, "veri_guveni": 100},
    )
    ilerlemeler = []

    kapsamli_analiz.kapsamli_tarama(
        ["AAA", "BBB", "CCC"],
        force=True,
        progress_callback=lambda taranan, toplam: ilerlemeler.append((taranan, toplam)),
    )

    assert ilerlemeler[0] == (0, 3)
    assert ilerlemeler[-1] == (3, 3)


def test_hisse_analizleri_takas_cagrilarini_paralel_yurutur(monkeypatch, tmp_path):
    monkeypatch.setattr(kapsamli_analiz, "ANALIZ_CACHE", str(tmp_path / "cache.json"))
    durum = {"aktif": 0, "en_yuksek": 0}
    kilit = threading.Lock()
    baslangic = threading.Barrier(2)

    def fake_takas(sembol, kullanici=None):
        with kilit:
            durum["aktif"] += 1
            durum["en_yuksek"] = max(durum["en_yuksek"], durum["aktif"])
        try:
            baslangic.wait(timeout=1)
            time.sleep(0.01)
            return None
        finally:
            with kilit:
                durum["aktif"] -= 1

    monkeypatch.setattr(kapsamli_analiz, "_teknik_ve_trade", lambda sembol: (None, None))
    monkeypatch.setattr(kapsamli_analiz, "temel_analiz", lambda sembol: None)
    monkeypatch.setattr(kapsamli_analiz, "hedef_fiyat_tahmin", lambda sembol, gun_hedef=5: None)
    monkeypatch.setattr(kapsamli_analiz, "takas_analiz", fake_takas)

    kapsamli_analiz.kapsamli_tarama(["AAA", "BBB"], force=True)

    assert durum["en_yuksek"] == 2


def test_teknik_gosterge_skorlari_tum_gostergeleri_ve_agirliklari_icerir():
    kapanis = pd.Series(np.linspace(100, 140, 120))
    yuksek = kapanis + 2
    dusuk = kapanis - 2
    ema21 = kapanis.ewm(span=21, adjust=False).mean()
    ema50 = kapanis.ewm(span=50, adjust=False).mean()
    macd = kapanis.ewm(span=12, adjust=False).mean() - kapanis.ewm(span=26, adjust=False).mean()
    sinyal = macd.ewm(span=9, adjust=False).mean()
    delta = kapanis.diff()
    rsi = (100 - 100 / (1 + delta.clip(lower=0).rolling(14).mean() / -delta.clip(upper=0).rolling(14).mean())).fillna(50)
    orta = kapanis.rolling(20).mean()
    sapma = kapanis.rolling(20).std()

    skorlar = kapsamli_analiz._teknik_gosterge_skorlari(
        float(kapanis.iloc[-1]), kapanis, yuksek, dusuk, ema21, ema50,
        macd, sinyal, rsi, orta, orta + 2 * sapma, orta - 2 * sapma,
    )

    assert set(skorlar) == set(kapsamli_analiz.TEKNIK_GOSTERGE_AGIRLIKLARI)
    assert all(0 <= puan <= 100 for puan in skorlar.values())
    assert sum(kapsamli_analiz.TEKNIK_GOSTERGE_AGIRLIKLARI.values()) == 100
    assert sum(kapsamli_analiz.ANALIZ_AGIRLIKLARI.values()) == 100


def test_tavan_adaylari_model_olasiligina_gore_ilk_besi_secer():
    analizler = [
        {
            "sembol": f"S{i}",
            "fiyat": 10,
            "teknik": {
                "tavan_modeli_olasiligi": float(i),
                "tavana_dokunma_olasiligi": float(i * 2),
                "tavan_modeli_precision": 50,
                "veri_bayat": False,
                "gunluk_getiri": 1,
                "getiri_5g": 2,
                "hacim_orani": 1.2,
            },
        }
        for i in range(7)
    ]

    adaylar = kapsamli_analiz._tavan_adaylarini_sec(analizler)

    assert len(adaylar) == 2
    assert [aday["sembol"] for aday in adaylar] == ["S6", "S5"]


def test_tavan_adaylari_kapanma_ve_dokunma_esiklerini_birlikte_arar():
    analizler = [
        {
            "sembol": "SADECE_KAPANMA",
            "teknik": {
                "tavan_modeli_olasiligi": 12,
                "tavana_dokunma_olasiligi": 7,
                "gunluk_getiri": 2,
                "getiri_5g": 3,
                "hacim_orani": 2,
            },
        },
        {
            "sembol": "IKI_TEYIT",
            "teknik": {
                "tavan_modeli_olasiligi": 12,
                "tavana_dokunma_olasiligi": 18,
                "gunluk_getiri": 2,
                "getiri_5g": 3,
                "hacim_orani": 2,
            },
        },
    ]

    adaylar = kapsamli_analiz._tavan_adaylarini_sec(analizler)

    assert [aday["sembol"] for aday in adaylar] == ["IKI_TEYIT"]


def test_tavan_adaylari_asiri_yukselmis_zayif_hisseleri_eler_ama_guclu_tavan_devamini_korur():
    analizler = [
        {
            "sembol": "ZAYIF_GUNLUK_TAVAN",
            "teknik": {
                "onceki_kapanis": 10,
                "fiyat": 11,
                "tavan_modeli_olasiligi": 10,
                "tavana_dokunma_olasiligi": 15,
                "gunluk_getiri": 9.8,
                "getiri_5g": 12,
                "hacim_orani": 3,
                "rsi": 72,
            },
        },
        {
            "sembol": "GUCLU_TAVAN_DEVAMI",
            "teknik": {
                "onceki_kapanis": 10,
                "fiyat": 11,
                "tavan_modeli_olasiligi": 18.9,
                "tavana_dokunma_olasiligi": 23.9,
                "gunluk_getiri": 10,
                "getiri_5g": -3.2,
                "hacim_orani": 4.2,
                "rsi": 72,
            },
        },
        {
            "sembol": "BES_GUN_SISME",
            "teknik": {
                "tavan_modeli_olasiligi": 30,
                "tavana_dokunma_olasiligi": 40,
                "gunluk_getiri": 4,
                "getiri_5g": 30,
                "hacim_orani": 3,
                "rsi": 72,
            },
        },
        {
            "sembol": "ERKEN_KIRILIM",
            "teknik": {
                "tavan_modeli_olasiligi": 12,
                "tavana_dokunma_olasiligi": 18,
                "gunluk_getiri": 4,
                "getiri_5g": 12,
                "hacim_orani": 2,
                "rsi": 65,
            },
        },
    ]

    adaylar = kapsamli_analiz._tavan_adaylarini_sec(analizler)

    assert [aday["sembol"] for aday in adaylar] == ["GUCLU_TAVAN_DEVAMI", "ERKEN_KIRILIM"]


def test_tavan_adaylari_temel_esikleri_gecen_tavan_devamini_negatif_5g_nedeniyle_elemez():
    aday = {
        "sembol": "AZTEK",
        "teknik": {
            "onceki_kapanis": 3.15,
            "fiyat": 3.46,
            "tavan_modeli_olasiligi": 13.2,
            "tavana_dokunma_olasiligi": 17.7,
            "gunluk_getiri": 9.84,
            "getiri_5g": -6.49,
            "hacim_orani": 1.57,
            "rsi": 65,
        },
    }

    assert kapsamli_analiz._tavan_adaylarini_sec([aday]) == [aday]


def test_tek_gunluk_gecmis_tavan_devami_sayilmaz(monkeypatch):
    indeks = pd.to_datetime(["2026-09-17"]).tz_localize("Europe/Istanbul")
    veri = pd.DataFrame({
        "Open": [28.06],
        "High": [28.06],
        "Low": [28.06],
        "Close": [28.06],
        "Volume": [2_138_427],
    }, index=indeks)
    monkeypatch.setattr(
        kapsamli_analiz.VeriKaynaklari,
        "tarihsel_veri_al",
        lambda *args, **kwargs: (veri, {"kaynak": "Yahoo Finance", "yedek_kullanildi": False}),
    )

    teknik, trade = kapsamli_analiz._teknik_ve_trade("NETGL")

    assert trade is None
    assert teknik is None


def test_kisa_gecmisli_taban_hisse_tavan_devami_sayilmaz(monkeypatch):
    indeks = pd.to_datetime(["2026-09-17", "2026-09-18"]).tz_localize("Europe/Istanbul")
    veri = pd.DataFrame({
        "Open": [10.0, 9.0],
        "High": [10.0, 9.0],
        "Low": [10.0, 9.0],
        "Close": [10.0, 9.0],
        "Volume": [1_000_000, 1_500_000],
    }, index=indeks)
    monkeypatch.setattr(
        kapsamli_analiz.VeriKaynaklari,
        "tarihsel_veri_al",
        lambda *args, **kwargs: (veri, {"kaynak": "Yahoo Finance", "yedek_kullanildi": False}),
    )

    teknik, trade = kapsamli_analiz._teknik_ve_trade("TABAN")

    assert teknik is None
    assert trade is None


def test_yuksek_guvenli_tavan_adayi_coklu_teyit_ister():
    teknik = {
        "tavan_modeli_kapsami": "GLOBAL",
        "tavan_modeli_olasiligi": 18,
        "tavana_dokunma_olasiligi": 24,
        "tavan_modeli_ham_olasiligi": 85,
        "tavana_dokunma_ham_olasiligi": 88,
        "beklenen_getiri": 0.8,
        "dusus_riski": 2.0,
        "gunluk_getiri": 4,
        "getiri_5g": 10,
        "hacim_orani": 2,
        "rsi": 68,
        "gunluk_veri_tamamlandi": True,
        "fiyat_teyidi": {"guvenilir": True},
        "intraday": {"momentum_15dk": 0.5, "hacim_orani": 1.5},
    }
    aday = {"sembol": "TEYITLI", "teknik": teknik, "kap_teyidi": {"net_sinyal": 0}}

    assert kapsamli_analiz._yuksek_guvenli_tavan_adayi_mi(aday) is True

    aday["teknik"]["intraday"]["momentum_15dk"] = -0.1
    assert kapsamli_analiz._yuksek_guvenli_tavan_adayi_mi(aday) is False

    aday["teknik"]["intraday"]["momentum_15dk"] = 0.5
    aday["teknik"]["tavan_modeli_kapsami"] = None
    aday["teknik"]["yeni_halka_arz_tavan_devami"] = True
    assert kapsamli_analiz._yuksek_guvenli_tavan_adayi_mi(aday) is False


def test_reddedilen_backtest_yuksek_guven_sinyalini_izlemeye_dusurur():
    aday = {
        "sembol": "TEYITLI",
        "teknik": {
            "tavan_modeli_kapsami": "GLOBAL",
            "tavan_modeli_olasiligi": 18,
            "tavana_dokunma_olasiligi": 24,
            "tavan_modeli_ham_olasiligi": 85,
            "tavana_dokunma_ham_olasiligi": 88,
            "beklenen_getiri": 0.8,
            "dusus_riski": 2.0,
            "gunluk_getiri": 4,
            "getiri_5g": 10,
            "hacim_orani": 2,
            "rsi": 68,
            "gunluk_veri_tamamlandi": True,
            "fiyat_teyidi": {"guvenilir": True},
            "intraday": {"momentum_15dk": 0.5, "hacim_orani": 1.5},
        },
        "kap_teyidi": {"net_sinyal": 0},
    }

    yuksek_guven, izleme = kapsamli_analiz._tavan_listelerini_siniflandir(
        [aday], model_kabul=False,
    )

    assert yuksek_guven == []
    assert izleme == [aday]
    assert aday["teknik"]["tavan_guven_eksikleri"][0] == "Ayrilmis backtest kabul edilmedi"


def test_backtest_kabul_durumu_rapor_yokken_guvenli_kapali(monkeypatch, tmp_path):
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_BACKTEST_RAPORU", str(tmp_path / "yok.json"))

    sonuc = kapsamli_analiz._backtest_kabul_durumu()

    assert sonuc["kabul"] is False
    assert sonuc["durum"] == "rapor_yok"


def test_backtest_kabul_durumu_ayrilmis_test_sonucunu_okur(monkeypatch, tmp_path):
    rapor = tmp_path / "rapor.json"
    rapor.write_text(
        json.dumps({
            "metadata": {
                    "rapor_sema_surumu": 3,
                "model_surumu": kapsamli_analiz.MODEL_SURUMU,
                "uretim_zamani": datetime.now(ZoneInfo("UTC")).isoformat(),
            },
            "veri_kapsami": {"kapsam_yuzde": 95, "kullanilan_sembol": 500},
            "ozet": {"test_gunu": 120},
            "ayrilmis_kabul_testi": {"durum": "tamamlandi", "kabul": True},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_BACKTEST_RAPORU", str(rapor))

    sonuc = kapsamli_analiz._backtest_kabul_durumu()

    assert sonuc["kabul"] is True
    assert sonuc["durum"] == "tamamlandi"


def test_yuksek_guvenli_tavan_adayi_tamamlanmamis_mum_ve_teyitsiz_fiyati_reddeder():
    aday = {
        "sembol": "AAA",
        "teknik": {
            "tavan_modeli_kapsami": "GLOBAL",
            "tavan_modeli_olasiligi": 18,
            "tavana_dokunma_olasiligi": 24,
            "tavan_modeli_ham_olasiligi": 85,
            "tavana_dokunma_ham_olasiligi": 88,
            "beklenen_getiri": 0.8,
            "dusus_riski": 2,
            "gunluk_getiri": 4,
            "getiri_5g": 10,
            "hacim_orani": 2,
            "rsi": 68,
            "gunluk_veri_tamamlandi": False,
            "fiyat_teyidi": {"guvenilir": False},
            "intraday": {"momentum_15dk": 0.5, "hacim_orani": 1.5},
        },
        "kap_teyidi": {"net_sinyal": 0},
    }

    eksikler = kapsamli_analiz._tavan_guven_eksikleri(aday)

    assert "Gunluk mum henuz kapanmadi" in eksikler
    assert "Fiyat ikinci kaynaktan dogrulanmadi" in eksikler


def test_kisa_gecmisli_tavan_devami_yuksek_riskli_izlemeye_kaydedilir(monkeypatch, tmp_path):
    indeks = pd.to_datetime(["2026-09-17", "2026-09-18"]).tz_localize("Europe/Istanbul")
    veri = pd.DataFrame({
        "Open": [10.0, 11.0],
        "High": [10.0, 11.0],
        "Low": [10.0, 11.0],
        "Close": [10.0, 11.0],
        "Volume": [1_000_000, 2_000_000],
    }, index=indeks)
    monkeypatch.setattr(
        kapsamli_analiz.VeriKaynaklari,
        "tarihsel_veri_al",
        lambda *args, **kwargs: (veri, {"kaynak": "Yahoo Finance", "yedek_kullanildi": False}),
    )

    teknik, trade = kapsamli_analiz._teknik_ve_trade("YENI")

    assert trade is None
    assert teknik["yeni_halka_arz_tavan_devami"] is True
    aday = {"sembol": "YENI", "fiyat": 11, "teknik": teknik}
    assert kapsamli_analiz._tavan_adaylarini_sec([aday]) == [aday]
    assert kapsamli_analiz._yuksek_guvenli_tavan_adayi_mi(aday) is False
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    kapsamli_analiz._tavan_sinyalini_kaydet([aday], [aday])

    kayit = json.loads(gecmis_dosyasi.read_text(encoding="utf-8"))[0]
    assert kayit["adaylar"][0]["yeni_halka_arz_tavan_devami"] is True


def test_global_tavan_adaylari_ham_guven_ve_beklenen_getiri_esigini_uygular():
    def aday(sembol, kapanma_ham, dokunma_ham, beklenen_getiri):
        return {
            "sembol": sembol,
            "teknik": {
                "tavan_modeli_kapsami": "GLOBAL",
                "tavan_modeli_olasiligi": 12,
                "tavana_dokunma_olasiligi": 18,
                "tavan_modeli_ham_olasiligi": kapanma_ham,
                "tavana_dokunma_ham_olasiligi": dokunma_ham,
                "beklenen_getiri": beklenen_getiri,
                "gunluk_getiri": 3,
                "getiri_5g": 8,
                "hacim_orani": 2,
                "rsi": 65,
            },
        }

    analizler = [
        aday("GUCLU", 65, 70, 1.2),
        aday("ZAYIF_KAPANMA", 55, 70, 1.2),
        aday("ZAYIF_DOKUNMA", 65, 55, 1.2),
        aday("NEGATIF_GETIRI", 65, 70, -0.1),
    ]

    secilenler = kapsamli_analiz._tavan_adaylarini_sec(analizler)

    assert [veri["sembol"] for veri in secilenler] == ["GUCLU"]


def test_tavan_adayi_skoru_asiri_hareketi_ve_rsi_degerini_cezalandirir():
    taban = pd.Series(np.linspace(90, 100, 30))
    yuksek = taban + 1
    dusuk = taban - 1
    hacim = pd.Series([1000.0] * 29 + [2500.0])
    macd = pd.Series([1.0] * 30)
    sinyal = pd.Series([0.5] * 30)
    normal_rsi = pd.Series([65.0] * 30)
    asiri_kapanis = taban.copy()
    asiri_kapanis.iloc[-1] = taban.iloc[-2] * 1.09
    asiri_yuksek = yuksek.copy()
    asiri_dusuk = dusuk.copy()
    asiri_yuksek.iloc[-1] = asiri_kapanis.iloc[-1]
    asiri_dusuk.iloc[-1] = taban.iloc[-2]

    normal_skor, _ = kapsamli_analiz._yarin_tavan_adayi_skoru(
        taban, yuksek, dusuk, hacim, macd, sinyal, normal_rsi, {"adx": 70},
    )
    asiri_skor, sebepler = kapsamli_analiz._yarin_tavan_adayi_skoru(
        asiri_kapanis, asiri_yuksek, asiri_dusuk, hacim, macd, sinyal,
        pd.Series([82.0] * 30), {"adx": 70},
    )

    assert asiri_skor < normal_skor
    assert "Asiri gunluk hareket" in sebepler
    assert "Asiri RSI" in sebepler


def test_global_uygulama_piyasa_ve_sektor_rejimini_ekler(monkeypatch):
    monkeypatch.setattr(kapsamli_analiz, "global_tavan_tahminleri", lambda veri: {
        "tahminler": {}, "metrikler": {}, "model_surumu": "test",
    })
    analizler = [
        {"sembol": "AAA", "teknik": {"getiri_5g": 4, "volatilite": 20}},
        {"sembol": "BBB", "teknik": {"getiri_5g": 2, "volatilite": 30}},
    ]

    sonuc = kapsamli_analiz._global_modeli_ve_goreceli_gucu_uygula(analizler)

    assert sonuc["piyasa_rejimi"]["durum"] == "GUCLU"
    assert sonuc["piyasa_rejimi"]["getiri_5g_medyan"] == 3
    assert all(veri["teknik"]["piyasa_rejimi"] == "GUCLU" for veri in analizler)


def test_fiyat_teyidi_adayin_teknik_bilgisine_eklenir(monkeypatch):
    class SahteKaynaklar:
        def isyatirim_veri(self, sembol):
            return {"fiyat": 100.2}

        def kaynak_uyumu(self, ana_fiyat, teyit_fiyati):
            return {"teyit_edildi": True, "sapma_yuzde": 0.2, "uyari": None}

    monkeypatch.setattr(kapsamli_analiz, "VeriKaynaklari", SahteKaynaklar)
    adaylar = [{"sembol": "THYAO", "fiyat": 100, "teknik": {"fiyat": 100}}]

    kapsamli_analiz._fiyat_teyidini_ekle(adaylar)

    assert adaylar[0]["teknik"]["fiyat_teyidi"]["teyit_edildi"] is True


def test_intraday_teyidi_hacim_ve_tavan_mesafesiyle_skoru_artirir(monkeypatch):
    class SahteKaynaklar:
        def yahoo_intraday_ozeti(self, sembol):
            return {
                "hacim_orani": 2.5,
                "yukari_bar_hacim_orani": 70,
                "momentum_15dk": 1,
                "tavana_mesafe": 2,
            }

    monkeypatch.setattr(kapsamli_analiz, "VeriKaynaklari", SahteKaynaklar)
    adaylar = [{"sembol": "AAA", "teknik": {"tavan_siralama_skoru": 20}}]

    kapsamli_analiz._intraday_teyidini_ekle(adaylar)

    assert adaylar[0]["teknik"]["intraday_teyit_skoru"] == 22
    assert adaylar[0]["teknik"]["tavan_nihai_skoru"] == 42


def test_tavan_sinyali_ayni_gunu_tekrar_kaydetmez(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    adaylar = [{"sembol": "AAA", "fiyat": 10, "teknik": {"tavan_modeli_olasiligi": 20, "tavan_modeli_precision": 25}}]

    kapsamli_analiz._tavan_sinyalini_kaydet(adaylar)
    kapsamli_analiz._tavan_sinyalini_kaydet(adaylar)

    with open(gecmis_dosyasi, "r", encoding="utf-8") as dosya:
        assert len(json.load(dosya)) == 1


def test_tavan_sinyali_ayni_gundeki_bekleyen_kaydi_gunceller(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    ilk_aday = [{
        "sembol": "AAA",
        "fiyat": 10,
        "teknik": {"son_islem_tarihi": "2026-09-14", "tavan_modeli_olasiligi": 20},
    }]
    son_aday = [{
        "sembol": "BBB",
        "fiyat": 20,
        "teknik": {"son_islem_tarihi": "2026-09-14", "tavan_modeli_olasiligi": 30},
    }]

    kapsamli_analiz._tavan_sinyalini_kaydet(ilk_aday)
    kapsamli_analiz._tavan_sinyalini_kaydet(son_aday)

    with open(gecmis_dosyasi, "r", encoding="utf-8") as dosya:
        gecmis = json.load(dosya)
    assert len(gecmis) == 1
    assert gecmis[0]["adaylar"][0]["sembol"] == "BBB"


def test_tavan_sinyali_ayni_gundeki_tamamlanmis_kaydi_korur(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    gecmis_dosyasi.write_text(json.dumps([{
        "sema_surumu": 2,
        "tarih": "2026-09-14",
        "adaylar": [{"sembol": "AAA", "olasilik": 20}],
        "sonuc": {"durum": "TAMAMLANDI", "precision": 50},
    }]), encoding="utf-8")
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    yeni_aday = [{
        "sembol": "BBB",
        "fiyat": 20,
        "teknik": {"son_islem_tarihi": "2026-09-14", "tavan_modeli_olasiligi": 30},
    }]

    kapsamli_analiz._tavan_sinyalini_kaydet(yeni_aday)

    with open(gecmis_dosyasi, "r", encoding="utf-8") as dosya:
        gecmis = json.load(dosya)
    assert len(gecmis) == 1
    assert gecmis[0]["adaylar"][0]["sembol"] == "AAA"
    assert gecmis[0]["sonuc"]["durum"] == "TAMAMLANDI"


def test_tavan_sinyali_ayni_gundeki_gecersiz_ornek_kaydi_degistirir(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    gecmis_dosyasi.write_text(json.dumps([
        {
            "tarih": "2026-09-10",
            "adaylar": [{"sembol": "BBB", "olasilik": None}],
        },
        {
            "tarih": "2026-09-11",
            "adaylar": [{"sembol": "AAA", "olasilik": None}],
        },
    ]), encoding="utf-8")
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    adaylar = [{
        "sembol": "THYAO",
        "fiyat": 350,
        "teknik": {
            "son_islem_tarihi": "2026-09-11",
            "tavan_modeli_olasiligi": 20,
            "tavan_modeli_precision": 25,
        },
    }]

    kapsamli_analiz._tavan_sinyalini_kaydet(adaylar)

    with open(gecmis_dosyasi, "r", encoding="utf-8") as dosya:
        gecmis = json.load(dosya)
    assert len(gecmis) == 1
    assert gecmis[0]["sema_surumu"] == 3
    assert gecmis[0]["adaylar"][0]["sembol"] == "THYAO"
    assert gecmis[0]["adaylar"][0]["olasilik"] == 20


def test_tavan_sinyali_dokunma_olasiligi_olan_adayi_gecerli_sayar(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    adaylar = [{
        "sembol": "THYAO",
        "fiyat": 350,
        "teknik": {
            "son_islem_tarihi": "2026-09-10",
            "tavan_modeli_olasiligi": None,
            "tavana_dokunma_olasiligi": 15,
        },
    }]
    kapsamli_analiz._tavan_sinyalini_kaydet(adaylar)

    analizler = [{
        "sembol": "THYAO",
        "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": 9.8},
    }]
    sonuc = kapsamli_analiz._tavan_sinyallerini_degerlendir(analizler)

    assert sonuc["dogru_tahminler"] == ["THYAO"]
    assert sonuc["precision"] == 100


def test_tavan_sinyali_sonraki_islem_gununde_precision_ve_recall_hesaplar(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    gecmis_dosyasi.write_text(json.dumps([{
        "tarih": "2026-09-10",
        "adaylar": [
            {"sembol": "AAA", "olasilik": 60},
            {"sembol": "BBB", "olasilik": 55},
        ],
    }]), encoding="utf-8")
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    analizler = [
        {"sembol": "AAA", "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": 9.8}},
        {"sembol": "BBB", "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": -1}},
        {"sembol": "CCC", "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": 10}},
    ]

    sonuc = kapsamli_analiz._tavan_sinyallerini_degerlendir(analizler)

    assert sonuc["dogru_tahminler"] == ["AAA"]
    assert sonuc["yanlis_pozitifler"] == ["BBB"]
    assert sonuc["kacirilan_tavanlar"] == ["CCC"]
    assert sonuc["precision"] == 50
    assert sonuc["recall"] == 50


def test_tavan_sinyali_bir_sonraki_islem_gunu_atlandiysa_puanlanmaz(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    gecmis_dosyasi.write_text(json.dumps([{
        "tarih": "2026-09-10",
        "adaylar": [{"sembol": "AAA", "olasilik": 60}],
    }]), encoding="utf-8")

    class SahteDepo:
        def sonraki_islem_tarihi(self, tarih):
            return "2026-09-11"

    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    monkeypatch.setattr(kapsamli_analiz, "GunlukVeriDeposu", SahteDepo)

    sonuc = kapsamli_analiz._tavan_sinyallerini_degerlendir([{
        "sembol": "AAA",
        "teknik": {"son_islem_tarihi": "2026-09-14", "gunluk_getiri": 10},
    }])

    assert sonuc["durum"] == "DEGERLENDIRILEMEDI"
    assert sonuc["beklenen_tarih"] == "2026-09-11"


def test_tavan_sinyali_yanlis_pozitif_nedenlerini_aciklar(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    gecmis_dosyasi.write_text(json.dumps([{
        "tarih": "2026-09-10",
        "adaylar": [{
            "sembol": "AAA",
            "olasilik": 6,
            "dokunma_olasiligi": 8,
            "precision": 0,
            "hacim_orani": 4,
        }],
    }]), encoding="utf-8")
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))

    sonuc = kapsamli_analiz._tavan_sinyallerini_degerlendir([{
        "sembol": "AAA",
        "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": -2},
    }])

    nedenler = sonuc["yanlis_pozitif_nedenleri"]["AAA"]
    assert "Kapanma olasiligi yuksek guven esigi %15 altinda" in nedenler
    assert "Dokunma olasiligi secim esigi %10 altinda" in nedenler
    assert "Tarihsel precision tahmini desteklemiyor" in nedenler
    assert "Hacim artisi tavan hareketine donusmedi" in nedenler
    assert "Ertesi gun momentum tersine dondu" in nedenler


def test_tavan_sinyali_eksik_evrenle_performans_yazmaz(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    gecmis_dosyasi.write_text(json.dumps([{
        "sema_surumu": 2,
        "tarih": "2026-09-10",
        "evren_sayisi": 3,
        "evren": [{"sembol": sembol} for sembol in ("AAA", "BBB", "CCC")],
        "adaylar": [{"sembol": "AAA", "olasilik": 60}],
    }]), encoding="utf-8")
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    analizler = [{
        "sembol": "AAA",
        "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": 9.8},
    }]

    sonuc = kapsamli_analiz._tavan_sinyallerini_degerlendir(analizler)

    assert sonuc["durum"] == "YETERSIZ_KAPSAM"
    assert sonuc["evren_kapsami"] == 33.3
    assert "sonuc" not in json.loads(gecmis_dosyasi.read_text(encoding="utf-8"))[0]


def test_tavan_sinyali_kacirilan_hissenin_tahmin_gunu_nedenini_saklar(monkeypatch, tmp_path):
    gecmis_dosyasi = tmp_path / "sinyaller.json"
    monkeypatch.setattr(kapsamli_analiz, "TAVAN_SINYAL_GECMISI", str(gecmis_dosyasi))
    ortak = {
        "son_islem_tarihi": "2026-09-10",
        "tavan_modeli_olasiligi": 20,
        "tavana_dokunma_olasiligi": 25,
        "gunluk_getiri": 2,
        "getiri_5g": 3,
    }
    aday = {"sembol": "AAA", "fiyat": 10, "teknik": {**ortak, "hacim_orani": 1.5}}
    elenen = {"sembol": "CCC", "fiyat": 20, "teknik": {**ortak, "hacim_orani": 0.8}}

    kapsamli_analiz._tavan_sinyalini_kaydet([aday], [aday, elenen])
    sonuc = kapsamli_analiz._tavan_sinyallerini_degerlendir([
        {"sembol": "AAA", "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": 1}},
        {"sembol": "CCC", "teknik": {"son_islem_tarihi": "2026-09-11", "gunluk_getiri": 10}},
    ])

    assert sonuc["evren_kapsami"] == 100
    assert sonuc["kacirilan_nedenleri"] == {"CCC": ["Hacim teyidi 1.1 altinda"]}
    assert sonuc["tahmin_sonuclari"] == [{
        "sembol": "AAA",
        "gercek_getiri": 1,
        "tavan_oldu": False,
    }]