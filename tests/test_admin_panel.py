import web_app


def test_admin_panel_route_requires_admin_access(monkeypatch):
    monkeypatch.setattr(web_app, "aktif_kullanici_al", lambda: "adminuser")
    monkeypatch.setattr(web_app.kullanici_yoneticisi, "admin_mi", lambda username: True)
    monkeypatch.setattr(web_app.kullanici_yoneticisi, "admin_listele", lambda: [])

    response = web_app.app.test_client().get("/admin")

    assert response.status_code == 200
    assert b"Admin Panel" in response.data
