from kapsamli_backtest import ayrilmis_kabul_testi, tarih_bazli_global_backtest, temsili_sembol_ornekle


def test_temsili_sembol_ornekle_listesinin_tum_araligini_kapsar():
    semboller = [f"S{indeks:03d}" for indeks in range(100)]

    sonuc = temsili_sembol_ornekle(semboller, 5)

    assert sonuc == ["S000", "S024", "S049", "S074", "S099"]


def test_global_backtest_gelecek_tarihleri_egitime_katmadan_metrik_uretir():
    veri_setleri = {}
    for sembol, ofset in (("AAA", 0), ("BBB", 1), ("CCC", 2)):
        veri_setleri[sembol] = {
            "tarihler": [f"2026-{gun // 28 + 1:02d}-{gun % 28 + 1:02d}" for gun in range(75)],
            "x": [[float((gun + ofset) % 5), float(gun % 3)] for gun in range(75)],
            "dokunma_y": [int((gun + ofset) % 7 == 0) for gun in range(75)],
            "kapanma_y": [int((gun + ofset) % 11 == 0) for gun in range(75)],
            "sonraki_getiriler": [0.1 if (gun + ofset) % 11 == 0 else -0.01 for gun in range(75)],
        }

    sonuc = tarih_bazli_global_backtest(
        veri_setleri,
        top_n=2,
        min_egitim_tarihi=60,
        son_test_gunu=10,
        yeniden_egit_araligi=2,
    )

    assert sonuc["ozet"]["test_gunu"] == 10
    assert sonuc["ozet"]["tahmin"] == 20
    assert 0 <= sonuc["ozet"]["precision_at_n"] <= 100
    assert 0 <= sonuc["ozet"]["recall_at_n"] <= 100
    assert 0 <= sonuc["ozet"]["brier"] <= 1
    assert 0 <= sonuc["ozet"]["dokunma_precision_at_n"] <= 100
    assert 0 <= sonuc["ozet"]["dokunma_recall_at_n"] <= 100
    assert sonuc["ozet"]["islem_maliyeti_bps"] == 20
    assert sonuc["ozet"]["gunluk_maruz_kalma"] == 0.25
    assert sonuc["ozet"]["purge_gunu"] == 1
    assert sonuc["ozet"]["maksimum_dusus"] <= 0
    assert sum(sonuc["ozet"]["model_secimleri"].values()) > 0
    assert sonuc["ozet"]["filtre_akisi"]["tum"]["aday"] == 30
    assert sonuc["ozet"]["filtresiz_tahmin"] == 20
    assert 0 <= sonuc["ozet"]["filtresiz_precision_at_n"] <= 100
    assert all("net_getiri" in gun for gun in sonuc["gunler"])
    assert all(len(gun["puanlananlar"]) == 3 for gun in sonuc["gunler"])


def test_ayrilmis_kabul_testi_profili_sadece_eski_gunlerde_secer():
    def gun(tarih, kapanma_dogru, dokunma_dogru):
        return {
            "tarih": tarih,
            "puanlananlar": [
                {
                    "sembol": "KAPANMA",
                    "kapanma_olasiligi": 0.8,
                    "dokunma_olasiligi": 0.1,
                    "beklenen_getiri": 0.01,
                    "dusus_riski": 0.01,
                    "gercek_getiri": 0.10 if kapanma_dogru else -0.05,
                    "tavanda_kapandi": kapanma_dogru,
                },
                {
                    "sembol": "DOKUNMA",
                    "kapanma_olasiligi": 0.2,
                    "dokunma_olasiligi": 0.9,
                    "beklenen_getiri": 0.01,
                    "dusus_riski": 0.01,
                    "gercek_getiri": 0.10 if dokunma_dogru else -0.05,
                    "tavanda_kapandi": dokunma_dogru,
                },
            ],
        }

    profiller = [
        {
            "ad": "kapanma",
            "minimum_kapanma_olasiligi": 0,
            "minimum_dokunma_olasiligi": 0,
            "minimum_beklenen_getiri": 0,
            "maksimum_dusus_riski": 0.1,
            "kapanma_agirligi": 100,
            "dokunma_agirligi": 0,
            "top_n": 1,
        },
        {
            "ad": "dokunma",
            "minimum_kapanma_olasiligi": 0,
            "minimum_dokunma_olasiligi": 0,
            "minimum_beklenen_getiri": 0,
            "maksimum_dusus_riski": 0.1,
            "kapanma_agirligi": 0,
            "dokunma_agirligi": 100,
            "top_n": 1,
        },
    ]
    rapor = {
        "gunler": [
            gun("1", True, False),
            gun("2", True, False),
            gun("3", True, False),
            gun("4", True, False),
            gun("5", False, True),
            gun("6", False, True),
        ],
        "ozet": {"islem_maliyeti_bps": 20},
    }

    sonuc = ayrilmis_kabul_testi(
        rapor,
        kabul_test_gunu=2,
        dogrulama_gunu=0,
        minimum_tahmin=1,
        profiller=profiller,
    )

    assert sonuc["secilen_profil"]["ad"] == "kapanma"
    assert sonuc["kalibrasyon"]["precision"] == 100.0
    assert sonuc["kabul_testi"]["precision"] == 0.0
    assert sonuc["kabul"] is False


def test_ayrilmis_kabul_testi_riskli_kalibrasyon_profilini_secmez():
    profil = {
        "ad": "riskli",
        "minimum_kapanma_olasiligi": 0,
        "minimum_dokunma_olasiligi": 0,
        "minimum_beklenen_getiri": 0,
        "maksimum_dusus_riski": 0.1,
        "kapanma_agirligi": 100,
        "dokunma_agirligi": 0,
        "top_n": 1,
    }
    gunler = [
        {
            "tarih": str(indeks),
            "puanlananlar": [{
                "sembol": "AAA",
                "kapanma_olasiligi": 0.8,
                "dokunma_olasiligi": 0.8,
                "beklenen_getiri": 0.01,
                "dusus_riski": 0.01,
                "gercek_getiri": -0.10,
                "tavanda_kapandi": indeks == 0,
            }],
        }
        for indeks in range(4)
    ]

    sonuc = ayrilmis_kabul_testi(
        {"gunler": gunler, "ozet": {"islem_maliyeti_bps": 20}},
        kabul_test_gunu=1,
        dogrulama_gunu=0,
        minimum_tahmin=1,
        profiller=[profil],
    )

    assert sonuc == {
        "durum": "kalibrasyonda_uygun_profil_yok",
        "kabul": False,
        "degerlendirilen_profil": 1,
    }


def test_ayrilmis_kabul_testi_dogrulama_basarisizsa_finali_kabul_etmez():
    profil = {
        "ad": "sabit",
        "minimum_kapanma_olasiligi": 0,
        "minimum_dokunma_olasiligi": 0,
        "minimum_beklenen_getiri": 0,
        "maksimum_dusus_riski": 0.1,
        "kapanma_agirligi": 100,
        "dokunma_agirligi": 0,
        "top_n": 1,
    }

    def gun(indeks, dogru):
        return {
            "tarih": str(indeks),
            "puanlananlar": [{
                "sembol": "AAA",
                "kapanma_olasiligi": 0.8,
                "dokunma_olasiligi": 0.8,
                "beklenen_getiri": 0.01,
                "dusus_riski": 0.01,
                "gercek_getiri": 0.10 if dogru else -0.05,
                "tavanda_kapandi": dogru,
            }],
        }

    rapor = {
        "gunler": [
            *[gun(indeks, True) for indeks in range(3)],
            *[gun(indeks, False) for indeks in range(3, 6)],
            *[gun(indeks, True) for indeks in range(6, 9)],
        ],
        "ozet": {"islem_maliyeti_bps": 20, "gunluk_maruz_kalma": 0.25},
    }

    sonuc = ayrilmis_kabul_testi(
        rapor,
        kabul_test_gunu=3,
        dogrulama_gunu=3,
        minimum_tahmin=1,
        profiller=[profil],
    )

    assert sonuc["dogrulama_kosullari"]["net_getiri"] is False
    assert sonuc["kabul_kosullari"]["net_getiri"] is True
    assert sonuc["kabul"] is False


def test_ayrilmis_kabul_testi_pozitif_getiriyi_guven_alt_siniri_negatifse_reddeder():
    profil = {
        "ad": "oynak",
        "minimum_kapanma_olasiligi": 0,
        "minimum_dokunma_olasiligi": 0,
        "minimum_beklenen_getiri": 0,
        "maksimum_dusus_riski": 0.1,
        "kapanma_agirligi": 100,
        "dokunma_agirligi": 0,
        "top_n": 1,
    }

    def gun(indeks, getiri):
        return {
            "tarih": str(indeks),
            "puanlananlar": [{
                "sembol": "AAA",
                "kapanma_olasiligi": 0.8,
                "dokunma_olasiligi": 0.8,
                "beklenen_getiri": 0.01,
                "dusus_riski": 0.01,
                "gercek_getiri": getiri,
                "tavanda_kapandi": True,
            }],
        }

    rapor = {
        "gunler": [
            *[gun(i, 0.05) for i in range(20)],
            *[gun(i, 0.20 if i % 2 else -0.10) for i in range(20, 40)],
            *[gun(i, 0.05) for i in range(40, 60)],
        ],
        "ozet": {"islem_maliyeti_bps": 20, "gunluk_maruz_kalma": 1.0},
    }

    sonuc = ayrilmis_kabul_testi(
        rapor,
        kabul_test_gunu=20,
        dogrulama_gunu=20,
        minimum_tahmin=1,
        profiller=[profil],
    )

    assert sonuc["dogrulama"]["bilesik_net_getiri"] > 0
    assert sonuc["dogrulama_kosullari"]["getiri_guven_alt"] is False
    assert sonuc["kabul"] is False