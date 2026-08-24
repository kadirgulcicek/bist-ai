"""
Kullanici Kimlik Dogrulama - PostgreSQL ile Kalici Veri
"""

import os
import hashlib
import secrets
import json
from datetime import datetime

# Veritabani URL - Railway otomatik olarak ayarlar
DATABASE_URL = os.environ.get('DATABASE_URL')

# Railway'de bazen postgres:// gelir, psycopg2 icin postgresql:// lazim
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)


def veritabani_baglanti():
    """PostgreSQL baglantisi olustur"""
    if not DATABASE_URL:
        import sqlite3
        conn = sqlite3.connect('users.db')
        return conn, 'sqlite'
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        return conn, 'postgres'
    except Exception as e:
        print(f"PostgreSQL baglanti hatasi: {e}")
        import sqlite3
        conn = sqlite3.connect('users.db')
        return conn, 'sqlite'


def tablo_olustur(conn, db_tipi):
    """Tablolari olustur"""
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS kullanicilar
                 (kullanici_adi TEXT PRIMARY KEY,
                  sifre_hash TEXT,
                  email TEXT,
                  kayit_tarihi TEXT,
                  portfoy TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS oturumlar
                 (token TEXT PRIMARY KEY,
                  kullanici_adi TEXT)''')
    conn.commit()


class KullaniciYoneticisi:
    def __init__(self):
        self.conn, self.db_tipi = veritabani_baglanti()
        tablo_olustur(self.conn, self.db_tipi)
        self.conn.commit()
    
    def sifre_hashle(self, sifre):
        return hashlib.sha256(sifre.encode()).hexdigest()
    
    def placeholder(self):
        """PostgreSQL %s, SQLite ?"""
        return "%s" if self.db_tipi == 'postgres' else "?"
    
    def kayit_ol(self, kullanici_adi, sifre, email):
        kullanici_adi = kullanici_adi.lower().strip()
        if len(kullanici_adi) < 3:
            return False, "Kullanici adi en az 3 karakter"
        if len(sifre) < 4:
            return False, "Sifre en az 4 karakter"
        if "@" not in email:
            return False, "Gecerli email girin"
        
        c = self.conn.cursor()
        ph = self.placeholder()
        c.execute(f"SELECT kullanici_adi FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
        if c.fetchone():
            return False, "Bu kullanici adi zaten alinmis"
        
        c.execute(f"INSERT INTO kullanicilar VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                  (kullanici_adi, self.sifre_hashle(sifre), email,
                   datetime.now().strftime("%Y-%m-%d"), "[]"))
        self.conn.commit()
        
        token = secrets.token_urlsafe(32)
        c.execute(f"INSERT INTO oturumlar VALUES ({ph}, {ph})", (token, kullanici_adi))
        self.conn.commit()
        return True, token
    
    def giris_yap(self, kullanici_adi, sifre):
        kullanici_adi = kullanici_adi.lower().strip()
        c = self.conn.cursor()
        ph = self.placeholder()
        c.execute(f"SELECT sifre_hash FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
        sonuc = c.fetchone()
        if not sonuc:
            return False, "Kullanici bulunamadi"
        if sonuc[0] != self.sifre_hashle(sifre):
            return False, "Sifre yanlis"
        
        token = secrets.token_urlsafe(32)
        c.execute(f"INSERT INTO oturumlar VALUES ({ph}, {ph})", (token, kullanici_adi))
        self.conn.commit()
        return True, token
    
    def cikis_yap(self, token):
        c = self.conn.cursor()
        ph = self.placeholder()
        c.execute(f"DELETE FROM oturumlar WHERE token={ph}", (token,))
        self.conn.commit()
        return True
    
    def token_dogrula(self, token):
        c = self.conn.cursor()
        ph = self.placeholder()
        c.execute(f"SELECT kullanici_adi FROM oturumlar WHERE token={ph}", (token,))
        sonuc = c.fetchone()
        return sonuc[0] if sonuc else None
    
    def portfoy_al(self, kullanici_adi):
        kullanici_adi = kullanici_adi.lower().strip()
        c = self.conn.cursor()
        ph = self.placeholder()
        c.execute(f"SELECT portfoy FROM kullanicilar WHERE kullanici_adi={ph}", (kullanici_adi,))
        sonuc = c.fetchone()
        if sonuc and sonuc[0]:
            return json.loads(sonuc[0])
        return []
    
    def portfoy_kaydet(self, kullanici_adi, portfoy):
        kullanici_adi = kullanici_adi.lower().strip()
        c = self.conn.cursor()
        ph = self.placeholder()
        c.execute(f"UPDATE kullanicilar SET portfoy={ph} WHERE kullanici_adi={ph}",
                  (json.dumps(portfoy), kullanici_adi))
        self.conn.commit()
        return True
