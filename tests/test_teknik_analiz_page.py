import web_app


def test_teknik_analiz_route_renders_local_analyzer_result(monkeypatch):
    monkeypatch.setattr(web_app, "aktif_kullanici_al", lambda: "test")
    monkeypatch.setattr(
        web_app,
        "hisse_teknik_analiz",
        lambda sembol: {
            "Sembol": "THYAO",
            "Fiyat": 100.0,
            "RSI": 55.0,
            "MACD": 1.2,
            "SMA 20": 99.0,
            "SMA 50": 95.0,
            "Destek": 90.0,
            "Direnç": 110.0,
            "Skor": 3,
            "Karar": "AL",
            "Sinyaller": ["Test sinyali"],
        },
    )

    response = web_app.app.test_client().get("/teknik?sembol=THYAO")

    assert response.status_code == 200
    assert b"Teknik Analiz" in response.data
    assert b"Test sinyali" in response.data