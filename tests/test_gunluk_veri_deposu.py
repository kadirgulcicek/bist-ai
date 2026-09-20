import sqlite3

import pandas as pd

from gunluk_veri_deposu import GunlukVeriDeposu


def _ornek_veri(tarihler, kapanislar):
    return pd.DataFrame({
        "Open": [fiyat - 0.2 for fiyat in kapanislar],
        "High": [fiyat + 0.3 for fiyat in kapanislar],
        "Low": [fiyat - 0.4 for fiyat in kapanislar],
        "Close": kapanislar,
        "Volume": [1000 + indeks for indeks in range(len(tarihler))],
    }, index=pd.to_datetime(tarihler))


def test_kaydet_ayni_sembol_tarihini_gunceller_ve_gecmisi_korur(tmp_path):
    depo = GunlukVeriDeposu(tmp_path / "piyasa.db")
    depo.kaydet("AAA", _ornek_veri(["2026-09-14"], [10.0]), "Test")
    depo.kaydet("AAA", _ornek_veri(["2026-09-14", "2026-09-15"], [10.5, 11.0]), "Test")

    veri = depo.oku("AAA")

    assert list(veri.index.strftime("%Y-%m-%d")) == ["2026-09-14", "2026-09-15"]
    assert veri.loc["2026-09-14", "Close"] == 10.5
    assert veri.loc["2026-09-15", "Close"] == 11.0


def test_kaydet_gecersiz_ohlc_satirini_reddeder(tmp_path):
    depo = GunlukVeriDeposu(tmp_path / "piyasa.db")
    veri = _ornek_veri(["2026-09-15"], [10.0])
    veri.loc[:, "High"] = 9.0

    sonuc = depo.kaydet("AAA", veri, "Test")

    assert sonuc == {"alindi": 1, "kaydedildi": 0, "reddedildi": 1}
    assert depo.oku("AAA").empty


def test_guncelle_son_tarihten_itibaren_artimli_veri_ister(tmp_path):
    depo = GunlukVeriDeposu(tmp_path / "piyasa.db")
    depo.kaydet("AAA", _ornek_veri(["2026-09-14"], [10.0]), "Test")
    cagrilar = []

    def indir(sembol, baslangic, bitis):
        cagrilar.append((sembol, baslangic, bitis))
        return _ornek_veri(["2026-09-15"], [11.0])

    sonuc = depo.guncelle(["AAA"], indirici=indir, bitis="2026-09-16")

    assert cagrilar == [("AAA", "2026-09-14", "2026-09-16")]
    assert sonuc["kaydedilen_satir"] == 1
    assert sonuc["basarili_sembol"] == 1


def test_calistirma_ozeti_veritabanina_yazilir(tmp_path):
    dosya = tmp_path / "piyasa.db"
    depo = GunlukVeriDeposu(dosya)

    depo.guncelle(
        ["AAA"],
        indirici=lambda sembol, baslangic, bitis: _ornek_veri(["2026-09-15"], [10.0]),
        bitis="2026-09-16",
    )

    with sqlite3.connect(dosya) as baglanti:
        durum, toplam = baglanti.execute(
            "SELECT durum, kaydedilen_satir FROM veri_akisi_calisma ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert durum == "TAMAMLANDI"
    assert toplam == 1


def test_sonraki_islem_tarihi_takvim_boslugunu_atlar(tmp_path):
    depo = GunlukVeriDeposu(tmp_path / "piyasa.db")
    depo.kaydet(
        "AAA",
        _ornek_veri(["2026-09-18", "2026-09-21"], [10.0, 10.5]),
        "Test",
    )

    assert depo.sonraki_islem_tarihi("2026-09-18") == "2026-09-21"