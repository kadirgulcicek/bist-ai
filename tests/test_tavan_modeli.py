import numpy as np
import pandas as pd
import sqlite3

import tavan_modeli
from kap_ozellikleri import kap_ozelliklerini_ekle
from tavan_modeli import erken_tavan_adayi_mi, global_tavan_tahminleri, tavan_egitim_verisi, tavan_fiyati, tavana_ulasti, walk_forward_tavan_istatistigi


def test_kap_ozellikleri_sonraki_seans_acilisinda_bilinen_veriyi_kullanir(tmp_path):
    db = tmp_path / "kap.db"
    with sqlite3.connect(db) as baglanti:
        baglanti.executescript("""
            CREATE TABLE kap_bildirim (
                bildirim_id INTEGER PRIMARY KEY,
                yayin_zamani TEXT NOT NULL,
                gecikmeli INTEGER NOT NULL DEFAULT 0,
                konu TEXT NOT NULL DEFAULT '',
                ham_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE kap_bildirim_sembol (
                bildirim_id INTEGER NOT NULL,
                sembol TEXT NOT NULL
            );
        """)
        baglanti.executemany(
            "INSERT INTO kap_bildirim VALUES (?, ?, ?, ?, ?)",
            [
                (1, "2026-09-18T20:00:00+03:00", 0, "Yeni İş İlişkisi", '{"summary":"Yeni siparis"}'),
                (2, "2026-09-21T09:00:00+03:00", 1, "Olağan Dışı Fiyat ve Miktar Hareketleri", '{}'),
                (3, "2026-09-22T10:00:00+03:00", 0, "Finansal Rapor", '{}'),
            ],
        )
        baglanti.executemany(
            "INSERT INTO kap_bildirim_sembol VALUES (?, 'AAA')",
            [(1,), (2,), (3,)],
        )
    veri = pd.DataFrame(
        {"Close": [10.0, 10.2]},
        index=pd.to_datetime(["2026-09-18", "2026-09-21"]),
    )

    sonuc = kap_ozelliklerini_ekle(veri, "AAA", db)

    assert sonuc["KAP_Bildirim_24s"].tolist() == [1.0, 0.0]
    assert sonuc["KAP_Bildirim_7g"].tolist() == [2.0, 2.0]
    assert sonuc["KAP_Gecikmeli_30g"].tolist() == [1.0, 1.0]
    assert sonuc["KAP_Piyasa_Olayi_24s"].tolist() == [1.0, 0.0]
    assert sonuc["KAP_Is_Iliskisi_7g"].tolist() == [1.0, 1.0]
    assert sonuc["KAP_Finansal_7g"].tolist() == [0.0, 0.0]


def test_tavan_fiyati_fiyat_adimina_gore_asagi_yuvarlanir():
    assert tavan_fiyati(10) == 11
    assert tavan_fiyati(20) == 22
    assert tavan_fiyati(100) == 110
    assert tavan_fiyati(4260) == 4685
    assert tavana_ulasti(20, 21.90) is False
    assert tavana_ulasti(20, 21.99) is False
    assert tavana_ulasti(20, 22.00) is True


def test_tavan_fiyati_veri_kaynagi_kayan_nokta_hatasini_tolere_eder():
    assert tavan_fiyati(4.619999885559082) == 5.08
    assert tavana_ulasti(4.619999885559082, 5.079999923706055) is True


def test_wilder_rsi_kayipsiz_yukseliste_100_ve_yataysada_50_doner():
    yukselen = pd.Series(np.arange(1.0, 31.0))
    yatay = pd.Series(np.full(30, 10.0))

    assert tavan_modeli.wilder_rsi(yukselen, 14).iloc[-1] == 100
    assert tavan_modeli.wilder_rsi(yatay, 14).iloc[-1] == 50


def test_wilder_atr_true_range_degerini_korur():
    kapanis = pd.Series(np.full(30, 10.0))
    yuksek = pd.Series(np.full(30, 11.0))
    dusuk = pd.Series(np.full(30, 9.0))

    assert tavan_modeli.wilder_atr(yuksek, dusuk, kapanis, 14).iloc[-1] == 2


def test_stokastik_high_low_araligini_kullanir():
    kapanis = pd.Series(np.full(20, 50.0))
    yuksek = pd.Series(np.full(20, 100.0))
    dusuk = pd.Series(np.zeros(20))

    assert tavan_modeli.stokastik_k(yuksek, dusuk, kapanis, 14).iloc[-1] == 50


def test_tavan_modeli_veri_yetersizken_guvenli_sonuc_dondurur():
    veri = pd.DataFrame({
        "Close": np.linspace(10, 20, 40),
        "High": np.linspace(10.2, 20.2, 40),
        "Low": np.linspace(9.8, 19.8, 40),
        "Volume": np.full(40, 1000),
    })

    sonuc = walk_forward_tavan_istatistigi(veri)

    assert sonuc["olasilik"] is None
    assert sonuc["precision"] is None
    assert sonuc["ornek"] == 0


def test_tavan_modeli_yeterli_gecmiste_olasilik_ve_ornek_raporlar():
    rng = np.random.default_rng(42)
    kapanis = [20.0]
    for indeks in range(180):
        hareket = 0.012 if indeks % 17 == 0 else rng.normal(0, 0.012)
        kapanis.append(kapanis[-1] * (1 + hareket))
    kapanis = np.asarray(kapanis)
    veri = pd.DataFrame({
        "Close": kapanis,
        "High": kapanis * 1.002,
        "Low": kapanis * 0.998,
        "Volume": np.where(np.arange(len(kapanis)) % 17 == 0, 5000, 1000),
    })

    sonuc = walk_forward_tavan_istatistigi(veri)

    assert sonuc["ornek"] >= 60
    assert sonuc["pozitif"] >= 0
    assert 0 <= sonuc["olasilik"] <= 100
    assert sonuc["precision"] is None or 0 <= sonuc["precision"] <= 100


def test_tavan_modeli_ertesi_gun_icin_son_satirin_ozelliklerini_kullanir(monkeypatch):
    satir_sayisi = 122
    kapanis = np.full(satir_sayisi, 10.0)
    yuksek = kapanis.copy()
    yuksek[61::2] = 11.0
    kapanis[61::2] = 11.0
    veri = pd.DataFrame({
        "Close": kapanis,
        "High": yuksek,
        "Low": np.full(satir_sayisi, 9.5),
        "Volume": np.full(satir_sayisi, 1000),
    })
    tahmin_girdileri = []

    class SahteModel:
        def fit(self, egitim_x, egitim_y):
            return self

        def predict_proba(self, girdiler):
            tahmin_girdileri.append(girdiler[0])
            return np.array([[0.25, 0.75]])

    monkeypatch.setattr(tavan_modeli, "_ozellikler", lambda veri, indeks: [float(indeks)])
    monkeypatch.setattr(tavan_modeli, "make_pipeline", lambda *args: SahteModel())

    walk_forward_tavan_istatistigi(veri)

    assert tahmin_girdileri[-1] == [float(satir_sayisi - 1)]


def test_tavan_modeli_dokunma_ve_kapanmayi_ayri_etiketler():
    kapanis = np.full(125, 10.0)
    yuksek = kapanis.copy()
    yuksek[70] = 11.0
    veri = pd.DataFrame({
        "Close": kapanis,
        "High": yuksek,
        "Low": np.full(125, 9.8),
        "Volume": np.full(125, 1000),
    })

    egitim = tavan_egitim_verisi(veri)

    assert sum(egitim["dokunma_y"]) == 1
    assert sum(egitim["kapanma_y"]) == 0


def test_tavan_modeli_getiriyi_ertesi_gun_acilistan_hesaplar():
    kapanis = np.full(125, 10.0)
    acilis = kapanis.copy()
    acilis[70] = 10.5
    kapanis[70] = 10.8
    veri = pd.DataFrame({
        "Open": acilis,
        "Close": kapanis,
        "High": np.maximum(acilis, kapanis),
        "Low": np.minimum(acilis, kapanis) * 0.99,
        "Volume": np.full(125, 1000),
    })

    egitim = tavan_egitim_verisi(veri)

    assert egitim["sonraki_getiriler"][9] == (10.8 / 10.5 - 1)


def test_tavandan_acilista_islem_gerceklesmis_sayilmaz():
    kapanis = np.full(125, 10.0)
    acilis = kapanis.copy()
    acilis[70] = 11.0
    kapanis[70] = 11.0
    veri = pd.DataFrame({
        "Open": acilis,
        "Close": kapanis,
        "High": np.maximum(acilis, kapanis),
        "Low": np.minimum(acilis, kapanis),
        "Volume": np.full(125, 1000),
    })

    egitim = tavan_egitim_verisi(veri)

    assert egitim["sonraki_getiriler"][9] == 0.0


def test_tavan_modeli_tavan_sonrasi_ozelliklerini_gecmisten_uretir():
    kapanis = np.full(70, 10.0)
    kapanis[-2] = 11.0
    kapanis[-1] = 12.1
    veri = pd.DataFrame({
        "Open": kapanis.copy(),
        "Close": kapanis,
        "High": kapanis,
        "Low": kapanis * 0.98,
        "Volume": np.append(np.full(69, 1000), 3000),
    })

    ozellikler = tavan_modeli._ozellikler(veri, len(veri) - 1)

    assert ozellikler[-4] == 1.0
    assert ozellikler[-3] == 0.4
    assert ozellikler[-2] == 0.2


def test_tavan_modeli_kap_ozelliklerini_vektorun_son_dort_alani_oncesine_ekler():
    kapanis = np.linspace(10.0, 12.0, 70)
    veri = pd.DataFrame({
        "Open": kapanis,
        "Close": kapanis,
        "High": kapanis * 1.01,
        "Low": kapanis * 0.99,
        "Volume": np.full(70, 1000),
        "KAP_Bildirim_24s": np.append(np.zeros(69), 3),
        "KAP_Bildirim_7g": np.append(np.zeros(69), 8),
        "KAP_Gecikmeli_30g": np.append(np.zeros(69), 1),
        "KAP_Piyasa_Olayi_24s": np.append(np.zeros(69), 1),
        "KAP_Is_Iliskisi_7g": np.append(np.zeros(69), 2),
        "KAP_Sermaye_7g": np.append(np.zeros(69), 1),
        "KAP_Pay_Islemi_7g": np.zeros(70),
        "KAP_Finansal_7g": np.append(np.zeros(69), 1),
        "KAP_Negatif_7g": np.zeros(70),
    })

    ozellikler = tavan_modeli._ozellikler(veri, len(veri) - 1)

    assert len(ozellikler) == 29
    assert ozellikler[tavan_modeli.OZELLIK_KAP_24S] > 0
    assert ozellikler[tavan_modeli.OZELLIK_KAP_7G] > ozellikler[tavan_modeli.OZELLIK_KAP_24S]
    assert ozellikler[tavan_modeli.OZELLIK_KAP_GECIKMELI_30G] > 0


def test_erken_tavan_filtresi_asiri_hareketi_ve_ust_fitili_eler():
    normal = [0.65, 0.01, 0.10, 0.15, 1.0, 0.8, -0.01, 0.02, 0.03, 0.01, 0.02, -0.01, 0.2, 0.03, 0.1, 0.2, 0.0, 0.0, 0.1, 0.0]
    asiri_gunluk = normal.copy()
    asiri_gunluk[13] = 0.09
    uzun_ust_fitil = normal.copy()
    uzun_ust_fitil[14] = 0.75
    onceki_tavan = normal.copy()
    onceki_tavan[-4] = 1.0

    assert erken_tavan_adayi_mi(normal) is True
    assert erken_tavan_adayi_mi(asiri_gunluk) is False
    assert erken_tavan_adayi_mi(uzun_ust_fitil) is False
    assert erken_tavan_adayi_mi(onceki_tavan) is False


def test_tavan_modeli_bolunme_gununu_egitimden_cikarir():
    kapanis = np.full(125, 10.0)
    kapanis[70] = 5.0
    bolunmeler = np.zeros(125)
    bolunmeler[70] = 2.0
    veri = pd.DataFrame({
        "Close": kapanis,
        "High": kapanis,
        "Low": kapanis,
        "Volume": np.full(125, 1000),
        "Stock Splits": bolunmeler,
    })

    egitim = tavan_egitim_verisi(veri)

    assert egitim["atlanan_kurumsal_aksiyon"] >= 1
    assert sum(egitim["dokunma_y"]) == 0


def test_global_tavan_modeli_hisseleri_ortak_veriyle_tahminler():
    veri_setleri = {
        "AAA": {
            "x": [[float(i % 7), float(i % 3)] for i in range(80)],
            "dokunma_y": [int(i % 9 == 0) for i in range(80)],
            "kapanma_y": [int(i % 13 == 0) for i in range(80)],
            "tarihler": [f"2026-01-{i + 1:03d}" for i in range(80)],
            "son_ozellik": [1.0, 2.0],
        },
        "BBB": {
            "x": [[float(i % 5), float(i % 4)] for i in range(80)],
            "dokunma_y": [int(i % 8 == 0) for i in range(80)],
            "kapanma_y": [int(i % 11 == 0) for i in range(80)],
            "tarihler": [f"2026-01-{i + 1:03d}" for i in range(80)],
            "son_ozellik": [2.0, 1.0],
        },
    }

    sonuc = global_tavan_tahminleri(veri_setleri)

    assert set(sonuc["tahminler"]) == {"AAA", "BBB"}
    assert 0 <= sonuc["tahminler"]["AAA"]["dokunma"] <= 100
    assert 0 <= sonuc["tahminler"]["AAA"]["kapanma"] <= 100
    assert 0 <= sonuc["tahminler"]["AAA"]["dokunma_ham"] <= 100
    assert 0 <= sonuc["tahminler"]["AAA"]["kapanma_ham"] <= 100
    assert sonuc["metrikler"]["kapanma"]["ornek"] == 160
    assert sonuc["metrikler"]["kapanma"]["secilen_model"] in {"logistic_regression", "catboost"}
    assert sonuc["metrikler"]["kapanma"]["purge_gunu"] == 1
    assert "logistic_regression" in sonuc["metrikler"]["kapanma"]["model_karsilastirmasi"]
    assert "logistic_regression" in sonuc["metrikler"]["kapanma"]["model_karsilastirmasi_average_precision"]
    assert -10 <= sonuc["tahminler"]["AAA"]["beklenen_getiri"] <= 10
    assert 0 <= sonuc["tahminler"]["AAA"]["dusus_riski"] <= 10
    assert sonuc["tahminler"]["AAA"]["siralama_skoru"] is not None


def test_global_tavan_modeli_ilk_egitim_dilimi_tek_sinifsa_cokmez():
    ornek_sayisi = 100
    hedef = [0] * 75 + [1, 0] * 12 + [1]
    veri_setleri = {
        "AAA": {
            "x": [[float(i % 7), float(i % 3)] for i in range(ornek_sayisi)],
            "dokunma_y": hedef,
            "kapanma_y": hedef,
            "tarihler": [f"2026-{i // 28 + 1:02d}-{i % 28 + 1:02d}" for i in range(ornek_sayisi)],
            "sonraki_getiriler": [0.1 if deger else -0.01 for deger in hedef],
            "son_ozellik": [1.0, 2.0],
        },
    }

    sonuc = global_tavan_tahminleri(veri_setleri)

    assert set(sonuc["tahminler"]) == {"AAA"}
    assert 0 <= sonuc["tahminler"]["AAA"]["kapanma"] <= 100


def test_global_tavan_modeli_yeterli_satir_ama_az_tarih_varken_guvenli_doner():
    veri_setleri = {
        f"S{indeks}": {
            "x": [[float(indeks), 1.0], [float(indeks), 2.0]],
            "dokunma_y": [0, 1],
            "kapanma_y": [0, 1],
            "tarihler": ["2026-01-01", "2026-01-02"],
            "son_ozellik": [float(indeks), 3.0],
        }
        for indeks in range(40)
    }

    sonuc = global_tavan_tahminleri(veri_setleri)

    assert sonuc["tahminler"] == {}
    assert sonuc["metrikler"] == {}
