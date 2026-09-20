from types import SimpleNamespace

import sosyal_medya


def test_kap_aday_ozeti_tek_istekle_sembolleri_eslestirir(monkeypatch):
    class SahteYanit:
        content = b"rss"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(sosyal_medya.requests, "get", lambda *args, **kwargs: SahteYanit())
    monkeypatch.setattr(
        sosyal_medya.feedparser,
        "parse",
        lambda content: SimpleNamespace(entries=[
            {"title": "ASELS yeni anlasma ile buyume bekliyor"},
            {"title": "THY zarar acikladi"},
        ]),
    )

    sonuc = sosyal_medya.kap_aday_ozeti(["ASELS", "THYAO"])

    assert sonuc["ASELS"]["adet"] == 1
    assert sonuc["ASELS"]["net_sinyal"] > 0
    assert sonuc["THYAO"]["adet"] == 1
    assert sonuc["THYAO"]["net_sinyal"] < 0
    assert sonuc["ASELS"]["olaylar"][0]["tur"] == "SOZLESME_IHALE"
    assert sonuc["ASELS"]["olaylar"][0]["etki"] > 0