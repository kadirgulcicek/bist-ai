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
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'oturumlar' AND column_name = 'son_kullanma'
                """)
                if cursor.fetchone() is None:
                    cursor.execute("ALTER TABLE oturumlar ADD COLUMN son_kullanma TEXT")
                cursor.execute(
                    "UPDATE oturumlar SET son_kullanma = %s WHERE son_kullanma IS NULL",
                    ((datetime.now() + timedelta(days=30)).isoformat(),),
                )
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
                cursor.execute("PRAGMA table_info(oturumlar)")
                if not any(row[1] == "son_kullanma" for row in cursor.fetchall()):
                    cursor.execute("ALTER TABLE oturumlar ADD COLUMN son_kullanma TEXT")
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