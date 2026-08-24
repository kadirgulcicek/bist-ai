import os
import hashlib
import secrets
import json
from datetime import datetime

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
        pass  # Her cagrida yeni baglanti acacagiz
    
    def sifre_hashle(self, sifre):
        return hashlib.sha256(sifre.encode()).hexdigest()
    
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
            c.execute(f"INSERT INTO oturumlar VALUES ({ph}, {ph})", (token, kullanici_adi))
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
            if sonuc[0] != self.sifre_hashle(sifre):
                conn.close()
                return False, "Sifre yanlis"
            
            token = secrets.token_urlsafe(32)
            c.execute(f"INSERT INTO oturumlar VALUES ({ph}, {ph})", (token, kullanici_adi))
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
            c.execute(f"SELECT kullanici_adi FROM oturumlar WHERE token={ph}", (token,))
            sonuc = c.fetchone()
            conn.close()
            return sonuc[0] if sonuc else None
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