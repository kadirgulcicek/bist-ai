import sqlite3

import takas_analiz


def test_son_bir_ay_yabanci_liderleri_gercek_degisim_ve_fiyat_getirisi_uretir(monkeypatch, tmp_path):
    db = tmp_path / "piyasa.db"
    with sqlite3.connect(db) as baglanti:
        baglanti.execute(
            "CREATE TABLE gunluk_fiyat (sembol TEXT, tarih TEXT, kapanis REAL)"
        )
        baglanti.executemany(
            "INSERT INTO gunluk_fiyat VALUES (?, ?, ?)",
            [
                ("AAA", "2026-08-18", 10), ("AAA", "2026-09-18", 12),
                ("BBB", "2026-08-18", 20), ("BBB", "2026-09-18", 18),
            ],
        )

    class SahteCevap:
        def raise_for_status(self):
            return None

        def json(self):
            return {"d": [
                {"HISSE_KODU": "BBB", "YAB_ORAN_START": 5, "YAB_ORAN_END": 8, "DEGISIM": 3},
                {"HISSE_KODU": "AAA", "YAB_ORAN_START": 10, "YAB_ORAN_END": 15, "DEGISIM": 5},
                {"HISSE_KODU": "CCC", "YAB_ORAN_START": 4, "YAB_ORAN_END": 3, "DEGISIM": -1},
            ]}

    istekler = []
    monkeypatch.setattr(
        takas_analiz.requests,
        "post",
        lambda *args, **kwargs: istekler.append(kwargs["json"]) or SahteCevap(),
    )

    sonuc = takas_analiz.son_bir_ay_yabanci_liderleri(adet=2, db=str(db))

    assert istekler[0]["baslangicTarih"] == "18-08-2026"
    assert istekler[0]["bitisTarihi"] == "18-09-2026"
    assert [kayit["sembol"] for kayit in sonuc] == ["AAA", "BBB"]
    assert sonuc[0]["fiyat_getirisi"] == 20.0
    assert sonuc[1]["fiyat_getirisi"] == -10.0


def test_takas_sayfasi_yabanci_artis_liderlerini_gosterir(monkeypatch):
    import web_app

    monkeypatch.setattr(web_app, "aktif_kullanici_al", lambda: "test")
    monkeypatch.setattr(web_app, "takas_analiz", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        web_app,
        "son_bir_ay_yabanci_liderleri",
        lambda: [{
            "sembol": "AAA",
            "yabanci_baslangic": 10.0,
            "yabanci_son": 15.0,
            "yabanci_degisim": 5.0,
            "fiyat_getirisi": 20.0,
        }],
    )

    cevap = web_app.app.test_client().get("/takas")

    assert cevap.status_code == 200
    assert b"Son 1 Ay Yabanci Payi Artis Liderleri" in cevap.data
    assert b"AAA" in cevap.data
    assert b"+5.0 puan" in cevap.data
    assert b"+20.00%" in cevap.data