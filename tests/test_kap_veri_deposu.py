from datetime import date
import sqlite3

from kap_veri_deposu import KAP_SAYFA_SINIRI, KapVeriDeposu


def _kayit(bildirim_id, tarih="18.09.2026 20:00:00", kodlar="AAA, BBB"):
    return {
        "disclosureIndex": bildirim_id,
        "publishDate": tarih,
        "kapTitle": "Sirket",
        "subject": "Ozel durum aciklamasi",
        "isLate": False,
        "stockCodes": kodlar,
        "relatedStocks": None,
    }


def test_kap_deposu_ayni_bildirimi_idempotent_kaydeder(tmp_path):
    db = tmp_path / "veri.db"
    depo = KapVeriDeposu(db)

    depo.kaydet([_kayit(10)])
    depo.kaydet([_kayit(10)])

    with sqlite3.connect(db) as baglanti:
        assert baglanti.execute("SELECT COUNT(*) FROM kap_bildirim").fetchone()[0] == 1
        assert baglanti.execute("SELECT COUNT(*) FROM kap_bildirim_sembol").fetchone()[0] == 2


def test_kap_indir_api_sinirinda_tarih_araligini_boler(tmp_path):
    class Cevap:
        def __init__(self, veri):
            self.veri = veri

        def raise_for_status(self):
            return None

        def json(self):
            return self.veri

    class Oturum:
        def __init__(self):
            self.araliklar = []

        def post(self, url, json, headers, timeout):
            self.araliklar.append((json["fromDate"], json["toDate"]))
            veri = [_kayit(i) for i in range(KAP_SAYFA_SINIRI)] if len(self.araliklar) == 1 else [_kayit(len(self.araliklar))]
            return Cevap(veri)

    oturum = Oturum()
    sonuc = KapVeriDeposu(tmp_path / "veri.db").indir(
        date(2026, 9, 1), date(2026, 9, 4), oturum,
    )

    assert len(sonuc) == 2
    assert oturum.araliklar == [
        ("2026-09-01", "2026-09-04"),
        ("2026-09-01", "2026-09-02"),
        ("2026-09-03", "2026-09-04"),
    ]