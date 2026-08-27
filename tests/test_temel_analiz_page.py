from web_app import app


def test_temel_analiz_route_exists_and_returns_html():
    client = app.test_client()
    response = client.get('/temel?sembol=THYAO')
    assert response.status_code == 200
    assert b'Temel Analiz' in response.data
