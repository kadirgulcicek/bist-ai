import web_app
from web_app import app


def test_temel_analiz_route_exists_and_returns_html(monkeypatch):
    monkeypatch.setattr(web_app, "aktif_kullanici_al", lambda: "test")

    client = app.test_client()
    response = client.get('/temel?sembol=THYAO')
    assert response.status_code == 200
    assert b'Temel Analiz' in response.data
