import auth


def test_kayit_ol_telefon_sutunu_olan_veritabanina_kullanici_ekler(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(auth, "DATABASE_URL", None)
    yonetici = auth.KullaniciYoneticisi()

    basarili, token = yonetici.kayit_ol("test_user", "test1234", "test@example.com")

    assert basarili is True
    assert yonetici.token_dogrula(token) == "test_user"