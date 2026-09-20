import veri_kaynaklari
import sektor_analiz
import numpy as np
import pandas as pd


def test_guvenli_veri_al_gercek_kaynak_sirasini_kullanir(monkeypatch):
    kaynaklar = veri_kaynaklari.VeriKaynaklari()
    cagrilar = []

    monkeypatch.setattr(kaynaklar, "yahoo_veri", lambda sembol: cagrilar.append("yahoo"))
    monkeypatch.setattr(
        kaynaklar,
        "isyatirim_veri",
        lambda sembol: cagrilar.append("isyatirim") or {"sembol": sembol, "fiyat": 10, "gunluk": 1, "kaynak": "Is Yatirim"},
    )
    monkeypatch.setattr(kaynaklar, "twelve_data_veri", lambda sembol: cagrilar.append("twelve"))
    monkeypatch.setattr(kaynaklar, "stooq_veri", lambda sembol: cagrilar.append("stooq"))

    sonuc = kaynaklar.guvenli_veri_al("THYAO")

    assert sonuc["kaynak"] == "Is Yatirim"
    assert cagrilar == ["yahoo", "isyatirim"]


def test_guvenli_veri_al_sahte_veri_uretmez(monkeypatch):
    kaynaklar = veri_kaynaklari.VeriKaynaklari()
    for kaynak in kaynaklar.kaynaklar:
        monkeypatch.setattr(kaynaklar, f"{kaynak}_veri", lambda sembol: None)

    assert kaynaklar.guvenli_veri_al("YOK") is None


def test_stooq_html_yanitini_veri_saymaz(monkeypatch):
    class Cevap:
        text = "<html>JavaScript gerekli</html>"
        headers = {"Content-Type": "text/html"}

        def raise_for_status(self):
            return None

    monkeypatch.setattr(veri_kaynaklari.requests, "get", lambda *args, **kwargs: Cevap())

    assert veri_kaynaklari.VeriKaynaklari().stooq_veri("THYAO") is None


def test_tarihsel_veri_yahoo_yokken_isyatirima_gecer(monkeypatch):
    kaynaklar = veri_kaynaklari.VeriKaynaklari()
    beklenen = object()
    monkeypatch.setattr(kaynaklar, "yerel_tarihsel_veri", lambda *args: None)
    monkeypatch.setattr(kaynaklar, "yahoo_tarihsel_veri", lambda *args: None)
    monkeypatch.setattr(kaynaklar, "isyatirim_tarihsel_veri", lambda *args: beklenen)

    veri, kalite = kaynaklar.tarihsel_veri_al("THYAO")

    assert veri is beklenen
    assert kalite == {"kaynak": "Is Yatirim", "yedek_kullanildi": True}


def test_tarihsel_veri_guncel_yerel_depoyu_kullanir(monkeypatch):
    kaynaklar = veri_kaynaklari.VeriKaynaklari()
    beklenen = pd.DataFrame({"Close": [10.0, 11.0]})
    monkeypatch.setattr(kaynaklar, "yerel_tarihsel_veri", lambda *args: beklenen)
    monkeypatch.setattr(
        kaynaklar,
        "yahoo_tarihsel_veri",
        lambda *args: (_ for _ in ()).throw(AssertionError("Yahoo cagrilmamali")),
    )

    veri, kalite = kaynaklar.tarihsel_veri_al("THYAO")

    assert veri is beklenen
    assert kalite == {"kaynak": "Yerel SQLite", "yedek_kullanildi": False}


def test_kaynak_fiyat_farki_uyari_uretir():
    uyum = veri_kaynaklari.VeriKaynaklari.kaynak_uyumu(100, 98, tolerans_yuzde=0.5)

    assert uyum["teyit_edildi"] is False
    assert uyum["uyari"]


def test_ozet_fiyatla_birlikte_hacim_ve_tarih_dondurur():
    veri = pd.DataFrame(
        {"Close": [10.0, 11.0], "Volume": [1000, 2500]},
        index=pd.to_datetime(["2026-09-10", "2026-09-11"]),
    )

    sonuc = veri_kaynaklari.VeriKaynaklari._ozet("AAA", veri, "Test")

    assert sonuc["hacim"] == 2500
    assert sonuc["veri_tarihi"] == "2026-09-11"


def test_intraday_ozeti_tavan_mesafesi_ve_hacim_ivmesi_uretir(monkeypatch):
    intraday_index = pd.to_datetime([
        "2026-09-10 10:00", "2026-09-10 10:05",
        "2026-09-11 10:00", "2026-09-11 10:05",
    ])
    intraday = pd.DataFrame({
        "Open": [10, 10.1, 10.5, 10.8],
        "Close": [10.1, 10.2, 10.8, 10.9],
        "Volume": [100, 100, 200, 300],
    }, index=intraday_index)
    gunluk = pd.DataFrame(
        {"Close": [10.0, 10.9]},
        index=pd.to_datetime(["2026-09-10", "2026-09-11"]),
    )

    class SahteTicker:
        def history(self, period, interval=None, auto_adjust=False):
            return intraday if interval else gunluk

    monkeypatch.setattr("yfinance.Ticker", lambda sembol: SahteTicker())

    sonuc = veri_kaynaklari.VeriKaynaklari().yahoo_intraday_ozeti("AAA")

    assert sonuc["tavan_fiyati"] == 11
    assert sonuc["tavana_mesafe"] == 0.92
    assert sonuc["hacim_orani"] == 2.5
    assert sonuc["yukari_bar_hacim_orani"] == 100
    assert sonuc["alis_satis_dengesi"] is None
    assert sonuc["emir_defteri_mevcut"] is False


def test_sektor_analizi_veri_yokken_sahte_deger_uretmez(monkeypatch):
    monkeypatch.setattr(sektor_analiz, "hisse_veri_al", lambda sembol: None)

    assert sektor_analiz.guvenli_veri_al("THYAO") is None