import web_app


def test_gecikmeli_tavan_karsilastirmasi_fiyat_adimini_ve_gecikmeyi_raporlar(monkeypatch):
    import piyasa_tarama

    class SahteCevap:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [
                {"d": ["AAA", "BIST", 11.0, 10.0, 11.0, "delayed_streaming_900"]},
                {"d": ["BBB", "BIST", 10.5, 5.0, 11.0, "delayed_streaming_900"]},
            ]}

    monkeypatch.setattr(piyasa_tarama.requests, "post", lambda *args, **kwargs: SahteCevap())

    sonuc = piyasa_tarama.gecikmeli_tavan_karsilastirmasi(["BBB"])

    assert sonuc["durum"] == "SEANS_ICI_ON_SONUC"
    assert sonuc["gecikme_dakika"] == 15
    assert [veri["sembol"] for veri in sonuc["tavandaki_hisseler"]] == ["AAA"]
    assert sonuc["aday_sonuclari"][0]["sembol"] == "BBB"
    assert sonuc["aday_sonuclari"][0]["tavana_dokundu"] is True


def test_kapsamli_analiz_route_renders_score_table(monkeypatch):
    monkeypatch.setattr(web_app, "aktif_kullanici_al", lambda: "test")

    import kapsamli_analiz
    import piyasa_tarama

    monkeypatch.setattr(piyasa_tarama, "sembolleri_al", lambda: ["AAA"])
    monkeypatch.setattr(
        piyasa_tarama,
        "gecikmeli_tavan_karsilastirmasi",
        lambda adaylar: {
            "durum": "SEANS_ICI_ON_SONUC",
            "kaynak": "TradingView",
            "veri_zamani": "2026-09-17T10:30:00",
            "gecikme_dakika": 15,
            "tavandaki_hisseler": [{"sembol": "BBB", "degisim": 10}],
            "aday_sonuclari": [],
            "uyari": "Kesin sonuc kapanistan sonra hesaplanir.",
        },
    )
    monkeypatch.setattr(
        kapsamli_analiz,
        "kapsamli_tarama",
        lambda semboller, force=False, kullanici=None: {
            "analizler": [{
                "sembol": "AAA", "skor": 72.5, "durum": "GUCLU ADAY",
                "skorlar": {"teknik": 80, "temel": 70, "risk": 65, "takas": 60, "hedef": 75, "trade": 78},
                "risk_seviyesi": "ORTA", "veri_guveni": 100,
                "trade": {"karar": "TRADE ADAYI"},
            }],
            "sembol_sayisi": 1, "analiz_sayisi": 1, "son_guncelleme": "test",
            "backtest_kabul": {"kabul": False, "durum": "kalibrasyonda_uygun_profil_yok"},
        },
    )

    response = web_app.app.test_client().get("/kapsamli-analiz")

    assert response.status_code == 200
    assert b"Kapsamli BIST AI Analizi" in response.data
    assert b"AAA" in response.data
    assert b"TRADE ADAYI" in response.data
    assert b"Bugunku tavanlarla seans ici karsilastirma" in response.data
    assert b"15 dakika gecikmeli" in response.data
    assert b"BBB" in response.data
    assert b"CANLI TAVAN SINYALI KAPALI" in response.data


def test_kapsamli_analiz_yenile_eski_sonucu_temizleyip_temiz_urle_yonlendirir(monkeypatch):
    monkeypatch.setattr(web_app, "aktif_kullanici_al", lambda: "test")

    import piyasa_tarama

    monkeypatch.setattr(piyasa_tarama, "sembolleri_al", lambda: [f"S{i}" for i in range(21)])
    baslatilanlar = []

    class SahteThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            baslatilanlar.append(self.target)

    monkeypatch.setattr(web_app.threading, "Thread", SahteThread)
    monkeypatch.setitem(web_app._KAPSAMLI_ANALIZ_DURUMU, "test", {
        "calisiyor": False, "sonuc": {"eski": True}, "taranan": 20, "toplam": 20,
    })

    response = web_app.app.test_client().get("/kapsamli-analiz?yenile=1")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/kapsamli-analiz")
    assert web_app._KAPSAMLI_ANALIZ_DURUMU["test"]["sonuc"] is None
    assert web_app._KAPSAMLI_ANALIZ_DURUMU["test"]["taranan"] == 0
    assert web_app._KAPSAMLI_ANALIZ_DURUMU["test"]["toplam"] == 21
    assert len(baslatilanlar) == 1