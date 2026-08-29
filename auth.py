import os
import hashlib
import secrets
import json
from datetime import datetime, timedelta
import bcrypt

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)


def _yeni_baglanti(self):
    """Her cagrida yeni baglanti"""
    try:
        if DATABASE_URL:
            import psycopg2
            return psycopg2.connect(DATABASE_URL), 'postgres'
    except:
        pass
    
    import sqlite3
    return sqlite3.connect('users.db'), 'sqlite'


class KullaniciYoneticisi:
    def __init__(self):
        self._tablolari_hazirla()

    def _tablolari_hazirla(self):
        """Yeni kurulumlarda kullanici tablolarini otomatik olusturur."""
        conn, db_tipi = _yeni_baglanti(None)
        try:
            if db_tipi == 'postgres':
                conn.autocommit = True
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS kullanicilar (
                        kullanici_adi VARCHAR(100) PRIMARY KEY,
                        sifre_hash TEXT NOT NULL,
                        email TEXT NOT NULL,
                        kayit_tarihi TEXT NOT NULL,
                        portfoy TEXT NOT NULL DEFAULT '[]'
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS oturumlar (
                        token TEXT PRIMARY KEY,
                        kullanici_adi TEXT NOT NULL,
                        son_kullanma TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS islemler (
                        id SERIAL PRIMARY KEY,
                        kullanici_adi TEXT NOT NULL,
                        sembol TEXT NOT NULL,
                        islem TEXT NOT NULL,
                        adet INTEGER NOT NULL,
                        fiyat DOUBLE PRECISION NOT NULL,
                        tarih TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sifre_sifirlama (
                        token TEXT PRIMARY KEY,
                        kullanici_adi TEXT NOT NULL,
                        son_kullanma TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'oturumlar' AND column_name = 'son_kullanma'
                """)
                if cursor.fetchone() is None:
                    cursor.execute("ALTER TABLE oturumlar ADD COLUMN son_kullanma TEXT")
                cursor.execute(
                    "UPDATE oturumlar SET son_kullanma = %s WHERE son_kullanma IS NULL",
                    ((datetime.now() + timedelta(days=30)).isoformat(),),
                )
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'kullanicilar' AND column_name = 'telefon'
                """)
                if cursor.fetchone() is None:
                    cursor.execute("ALTER TABLE kullanicilar ADD COLUMN telefon TEXT")
            else:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS kullanicilar (
                        kullanici_adi TEXT PRIMARY KEY,
                        sifre_hash TEXT NOT NULL,
                        email TEXT NOT NULL,
                        kayit_tarihi TEXT NOT NULL,
                        portfoy TEXT NOT NULL DEFAULT '[]'
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS oturumlar (
                        token TEXT PRIMARY KEY,
                        kullanici_adi TEXT NOT NULL,
                        son_kullanma TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS islemler (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        kullanici_adi TEXT NOT NULL,
                        sembol TEXT NOT NULL,
                        islem TEXT NOT NULL,
                        adet INTEGER NOT NULL,
                        fiyat REAL NOT NULL,
                        tarih TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sifre_sifirlama (
                        token TEXT PRIMARY KEY,
                        kullanici_adi TEXT NOT NULL,
                        son_kullanma TEXT NOT NULL
                    )
                """)
                cursor.execute("PRAGMA table_info(oturumlar)")
                if not any(row[1] == "son_kullanma" for row in cursor.fetchall()):
                    cursor.execute("ALTER TABLE oturumlar ADD COLUMN son_kullanma TEXT")
                cursor.execute("PRAGMA table_info(kullanicilar)")
                if not any(row[1] == "telefon" for row in cursor.fetchall()):
                    cursor.execute("ALTER TABLE kullanicilar ADD COLUMN telefon TEXT")
                conn.commit()
        finally:
            conn.close()
    
    def sifre_hashle(self, sifre):
        return bcrypt.hashpw(sifre.encode(), bcrypt.gensalt()).decode()

    def sifre_dogrula(self, sifre, kayitli_hash):
        try:
            if kayitli_hash.startswith("$2"):
                return bcrypt.checkpw(sifre.encode(), kayitli_hash.encode())
            # Eski hesaplar ilk basarili giriste bcrypt'e tasinir.
            return hashlib.sha256(sifre.encode()).hexdigest() == kayitli_hash
        except (ValueError, TypeError):
            return False
    
    def _placeholder(self):
        return "%s" if DATABASE_URL else "?"
    
    def kayit_ol(self, kullanici_adi, sifre, email):
        kullanici_adi = kullanici_adi.lower().strip()
        if len(kullanici_adi) < 3:
            return False, "Kullanici adi en az 3 karakter"
        if len(sifre) < 4:
            return False, "Sifre en az 4 karakter"
        if "@" not in email:
            return False, "Gecerli email girin"
        
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT kullanici_adi FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
            if c.fetchone():
                conn.close()
                return False, "Bu kullanici adi zaten alinmis"
            
            c.execute(f"INSERT INTO kullanicilar VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                      (kullanici_adi, self.sifre_hashle(sifre), email,
                       datetime.now().strftime("%Y-%m-%d"), "[]"))
            conn.commit()
            conn.close()
            
            token = secrets.token_urlsafe(32)
            conn, _ = _yeni_baglanti(None)
            c = conn.cursor()
            son_kullanma = (datetime.now() + timedelta(days=30)).isoformat()
            c.execute(f"INSERT INTO oturumlar (token, kullanici_adi, son_kullanma) VALUES ({ph}, {ph}, {ph})", (token, kullanici_adi, son_kullanma))
            conn.commit()
            conn.close()
            return True, token
        except Exception as e:
            conn.close()
            return False, f"Hata: {str(e)[:50]}"
    
    def giris_yap(self, kullanici_adi, sifre):
        kullanici_adi = kullanici_adi.lower().strip()
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT sifre_hash FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
            sonuc = c.fetchone()
            if not sonuc:
                conn.close()
                return False, "Kullanici bulunamadi"
            if not self.sifre_dogrula(sifre, sonuc[0]):
                conn.close()
                return False, "Sifre yanlis"
            if not sonuc[0].startswith("$2"):
                c.execute(f"UPDATE kullanicilar SET sifre_hash={ph} WHERE kullanici_adi={ph}", (self.sifre_hashle(sifre), kullanici_adi))
            
            token = secrets.token_urlsafe(32)
            son_kullanma = (datetime.now() + timedelta(days=30)).isoformat()
            c.execute(f"INSERT INTO oturumlar (token, kullanici_adi, son_kullanma) VALUES ({ph}, {ph}, {ph})", (token, kullanici_adi, son_kullanma))
            conn.commit()
            conn.close()
            return True, token
        except Exception as e:
            conn.close()
            return False, f"Hata: {str(e)[:50]}"
    
    def cikis_yap(self, token):
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"DELETE FROM oturumlar WHERE token={ph}", (token,))
            conn.commit()
            conn.close()
            return True
        except:
            conn.close()
            return False
    
    def token_dogrula(self, token):
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT kullanici_adi, son_kullanma FROM oturumlar WHERE token={ph}", (token,))
            sonuc = c.fetchone()
            conn.close()
            if not sonuc:
                return None
            if sonuc[1] and datetime.fromisoformat(sonuc[1]) < datetime.now():
                self.cikis_yap(token)
                return None
            return sonuc[0]
        except:
            conn.close()
            return None
    
    def portfoy_al(self, kullanici_adi):
        kullanici_adi = kullanici_adi.lower().strip()
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT portfoy FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
            sonuc = c.fetchone()
            conn.close()
            if sonuc and sonuc[0]:
                return json.loads(sonuc[0])
            return []
        except:
            conn.close()
            return []
    
    def portfoy_kaydet(self, kullanici_adi, portfoy):
        kullanici_adi = kullanici_adi.lower().strip()
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"UPDATE kullanicilar SET portfoy={ph} WHERE kullanici_adi={ph}",
                      (json.dumps(portfoy), kullanici_adi))
            conn.commit()
            conn.close()
            return True
        except:
            conn.close()
            return False
    
    def hisse_sil(self, kullanici_adi, sembol):
        kullanici_adi = kullanici_adi.lower().strip()
        sembol = sembol.upper().strip()
        portfoy = self.portfoy_al(kullanici_adi)
        yeni = [h for h in portfoy if h["sembol"].upper() != sembol]
        if len(yeni) == len(portfoy):
            return False
        return self.portfoy_kaydet(kullanici_adi, yeni)

    def hisse_sat(self, kullanici_adi, sembol, adet, fiyat):
        """Portfoyden kismen veya tamamen satis yapar."""
        portfoy = self.portfoy_al(kullanici_adi)
        for hisse in portfoy:
            if hisse.get("sembol", "").upper() != sembol.upper():
                continue
            mevcut_adet = int(hisse.get("adet", 0))
            if adet <= 0 or adet > mevcut_adet:
                return False
            hisse["adet"] = mevcut_adet - adet
            yeni = [h for h in portfoy if h.get("adet", 0) > 0]
            if not self.portfoy_kaydet(kullanici_adi, yeni):
                return False
            return self.islem_kaydet(kullanici_adi, sembol, "SATIS", adet, fiyat)
        return False

    def islem_kaydet(self, kullanici_adi, sembol, islem, adet, fiyat):
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"INSERT INTO islemler (kullanici_adi, sembol, islem, adet, fiyat, tarih) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})", (kullanici_adi.lower().strip(), sembol.upper(), islem, adet, fiyat, datetime.now().isoformat()))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def islemleri_al(self, kullanici_adi):
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT sembol, islem, adet, fiyat, tarih FROM islemler WHERE kullanici_adi={ph} ORDER BY id DESC", (kullanici_adi.lower().strip(),))
            return c.fetchall()
        finally:
            conn.close()

    def kullanicilari_al(self):
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            c.execute("SELECT kullanici_adi, email, kayit_tarihi FROM kullanicilar ORDER BY kullanici_adi")
            return c.fetchall()
        finally:
            conn.close()

    def admin_mi(self, kullanici_adi):
        """Kullanici admin mi kontrol et"""
        kullanici_adi = (kullanici_adi or "").strip()
        if not kullanici_adi:
            return False
        try:
            conn, db_tipi = _yeni_baglanti(None)
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT email FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi.lower(),))
            sonuc = c.fetchone()
            conn.close()
            if sonuc and sonuc[0]:
                email = str(sonuc[0]).lower()
                if email.endswith("@admin.bistai") or "admin" in email:
                    return True
        except Exception:
            pass

        try:
            import os
            if os.path.exists("admin_data.json"):
                with open("admin_data.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                for admin in data.get("admin_kullanicilar", []):
                    if str(admin.get("kullanici_adi", "")).lower() == kullanici_adi.lower():
                        return True
        except Exception:
            pass
        return False

    def admin_listele(self):
        """Tum kullanicilari listele (sadece admin)"""
        try:
            conn, db_tipi = _yeni_baglanti(None)
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT kullanici_adi, email, kayit_tarihi FROM kullanicilar")
            kullanicilar = c.fetchall()
            conn.close()
            sonuc = [
                {"kullanici_adi": k[0], "email": k[1], "kayit_tarihi": k[2]}
                for k in kullanicilar
            ]
            try:
                import os
                if os.path.exists("admin_data.json"):
                    with open("admin_data.json", "r", encoding="utf-8") as f:
                        data = json.load(f)
                    adminlar = {str(ad.get("kullanici_adi", "")).lower() for ad in data.get("admin_kullanicilar", [])}
                    for item in sonuc:
                        if item["kullanici_adi"].lower() in adminlar:
                            item["admin"] = True
            except Exception:
                pass
            return sonuc
        except Exception:
            return []

    def kullanici_bilgisi_al(self, kullanici_adi):
        """Profil sayfasi icin kullanicinin email/telefon/kayit tarihini getirir."""
        kullanici_adi = (kullanici_adi or "").lower().strip()
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT email, kayit_tarihi, telefon FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
            sonuc = c.fetchone()
            if not sonuc:
                return None
            return {"kullanici_adi": kullanici_adi, "email": sonuc[0], "kayit_tarihi": sonuc[1], "telefon": sonuc[2]}
        finally:
            conn.close()

    def email_guncelle(self, kullanici_adi, yeni_email):
        """Kullanicinin email adresini gunceller."""
        kullanici_adi = (kullanici_adi or "").lower().strip()
        yeni_email = (yeni_email or "").strip()
        if "@" not in yeni_email or "." not in yeni_email.split("@")[-1]:
            return False, "Gecerli bir email girin"
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"UPDATE kullanicilar SET email={ph} WHERE kullanici_adi={ph}", (yeni_email, kullanici_adi))
            conn.commit()
            return True, "Email guncellendi"
        except Exception as e:
            return False, f"Hata: {str(e)[:50]}"
        finally:
            conn.close()

    def sifre_degistir(self, kullanici_adi, eski_sifre, yeni_sifre):
        """Mevcut sifreyi dogrulayip yenisiyle degistirir."""
        kullanici_adi = (kullanici_adi or "").lower().strip()
        if len(yeni_sifre or "") < 4:
            return False, "Yeni sifre en az 4 karakter olmali"
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT sifre_hash FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
            sonuc = c.fetchone()
            if not sonuc:
                return False, "Kullanici bulunamadi"
            if not self.sifre_dogrula(eski_sifre or "", sonuc[0]):
                return False, "Mevcut sifre yanlis"
            c.execute(f"UPDATE kullanicilar SET sifre_hash={ph} WHERE kullanici_adi={ph}", (self.sifre_hashle(yeni_sifre), kullanici_adi))
            conn.commit()
            return True, "Sifre guncellendi"
        except Exception as e:
            return False, f"Hata: {str(e)[:50]}"
        finally:
            conn.close()

    def telefon_guncelle(self, kullanici_adi, yeni_telefon):
        """Kullanicinin telefon numarasini gunceller."""
        kullanici_adi = (kullanici_adi or "").lower().strip()
        yeni_telefon = (yeni_telefon or "").strip()
        rakamlar = "".join(ch for ch in yeni_telefon if ch.isdigit() or ch == "+")
        if yeni_telefon and (len(rakamlar) < 10 or len(rakamlar) > 15):
            return False, "Gecerli bir telefon numarasi girin"
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"UPDATE kullanicilar SET telefon={ph} WHERE kullanici_adi={ph}", (yeni_telefon, kullanici_adi))
            conn.commit()
            return True, "Telefon numarasi guncellendi"
        except Exception as e:
            return False, f"Hata: {str(e)[:50]}"
        finally:
            conn.close()

    def sifirlama_tokeni_olustur(self, kullanici_adi_veya_email):
        """Kullanici adi veya email ile eslesen hesap icin sifre sifirlama tokeni uretir."""
        deger = (kullanici_adi_veya_email or "").strip().lower()
        if not deger:
            return None, None
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(
                f"SELECT kullanici_adi FROM kullanicilar WHERE kullanici_adi={ph} OR LOWER(email)={ph}",
                (deger, deger),
            )
            sonuc = c.fetchone()
            if not sonuc:
                return None, None
            kullanici_adi = sonuc[0]
            token = secrets.token_urlsafe(32)
            son_kullanma = (datetime.now() + timedelta(minutes=30)).isoformat()
            c.execute(
                f"INSERT INTO sifre_sifirlama (token, kullanici_adi, son_kullanma) VALUES ({ph}, {ph}, {ph})",
                (token, kullanici_adi, son_kullanma),
            )
            conn.commit()
            return kullanici_adi, token
        except Exception:
            return None, None
        finally:
            conn.close()

    def sifirlama_tokeni_dogrula(self, token):
        """Token gecerliyse kullanici adini, degilse None doner."""
        if not token:
            return None
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"SELECT kullanici_adi, son_kullanma FROM sifre_sifirlama WHERE token={ph}", (token,))
            sonuc = c.fetchone()
            if not sonuc:
                return None
            if datetime.fromisoformat(sonuc[1]) < datetime.now():
                c.execute(f"DELETE FROM sifre_sifirlama WHERE token={ph}", (token,))
                conn.commit()
                return None
            return sonuc[0]
        except Exception:
            return None
        finally:
            conn.close()

    def sifre_sifirla(self, token, yeni_sifre):
        """Gecerli bir token ile sifreyi sifirlar ve tokeni tuketir."""
        kullanici_adi = self.sifirlama_tokeni_dogrula(token)
        if not kullanici_adi:
            return False, "Baglanti gecersiz veya suresi dolmus"
        if len(yeni_sifre or "") < 4:
            return False, "Yeni sifre en az 4 karakter olmali"
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"UPDATE kullanicilar SET sifre_hash={ph} WHERE kullanici_adi={ph}", (self.sifre_hashle(yeni_sifre), kullanici_adi))
            c.execute(f"DELETE FROM sifre_sifirlama WHERE token={ph}", (token,))
            conn.commit()
            return True, "Sifre basariyla sifirlandi"
        except Exception as e:
            return False, f"Hata: {str(e)[:50]}"
        finally:
            conn.close()

    def kullanici_sil(self, kullanici_adi):
        conn, db_tipi = _yeni_baglanti(None)
        try:
            c = conn.cursor()
            ph = "%s" if db_tipi == 'postgres' else "?"
            c.execute(f"DELETE FROM oturumlar WHERE kullanici_adi={ph}", (kullanici_adi.lower().strip(),))
            c.execute(f"DELETE FROM islemler WHERE kullanici_adi={ph}", (kullanici_adi.lower().strip(),))
            c.execute(f"DELETE FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi.lower().strip(),))
            conn.commit()
            return c.rowcount > 0
        finally:
            conn.close()