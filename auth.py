"""
Kullanici Kimlik Dogrulama Sistemi
Kayit, giris, sifre yonetimi
Guvenli sifre hashleme
"""

import json
import os
import hashlib
import secrets
from datetime import datetime


class KullaniciYoneticisi:
    def __init__(self):
        self.db_dosya = "users_db.json"
        self.veriler = self.yukle()
    
    def yukle(self):
        """Kullanici veritabanini yukler"""
        if os.path.exists(self.db_dosya):
            with open(self.db_dosya, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"kullanicilar": {}, "oturumlar": {}}
    
    def kaydet(self):
        """Veritabanini kaydeder"""
        with open(self.db_dosya, "w", encoding="utf-8") as f:
            json.dump(self.veriler, f, indent=2, ensure_ascii=False)
    
    def sifre_hashle(self, sifre):
        """Sifreyi guvenli sekilde hashler"""
        return hashlib.sha256(sifre.encode()).hexdigest()
    
    def token_olustur(self):
        """Rastgele oturum tokeni"""
        return secrets.token_urlsafe(32)
    
    def kayit_ol(self, kullanici_adi, sifre, email):
        """Yeni kullanici kaydi"""
        kullanici_adi = kullanici_adi.lower().strip()
        
        # Kontroller
        if len(kullanici_adi) < 3:
            return False, "Kullanici adi en az 3 karakter olmali"
        if len(sifre) < 4:
            return False, "Sifre en az 4 karakter olmali"
        if "@" not in email:
            return False, "Gecerli bir email girin"
        if kullanici_adi in self.veriler["kullanicilar"]:
            return False, "Bu kullanici adi zaten alinmis"
        
        # Kaydet
        self.veriler["kullanicilar"][kullanici_adi] = {
            "sifre_hash": self.sifre_hashle(sifre),
            "email": email,
            "kayit_tarihi": datetime.now().strftime("%Y-%m-%d"),
            "portfoy": []
        }
        self.kaydet()
        
        # Otomatik giris yap
        token = self.token_olustur()
        self.veriler["oturumlar"][token] = kullanici_adi
        self.kaydet()
        
        return True, token
    
    def giris_yap(self, kullanici_adi, sifre):
        """Giris yapma"""
        kullanici_adi = kullanici_adi.lower().strip()
        
        if kullanici_adi not in self.veriler["kullanicilar"]:
            return False, "Kullanici bulunamadi"
        
        kullanici = self.veriler["kullanicilar"][kullanici_adi]
        if kullanici["sifre_hash"] != self.sifre_hashle(sifre):
            return False, "Sifre yanlis"
        
        # Oturum tokeni olustur
        token = self.token_olustur()
        self.veriler["oturumlar"][token] = kullanici_adi
        self.kaydet()
        
        return True, token
    
    def cikis_yap(self, token):
        """Oturumu sonlandir"""
        if token in self.veriler["oturumlar"]:
            del self.veriler["oturumlar"][token]
            self.kaydet()
            return True
        return False
    
    def token_dogrula(self, token):
        """Token ile kullanici bul"""
        if token in self.veriler["oturumlar"]:
            return self.veriler["oturumlar"][token]
        return None
    
    def portfoy_al(self, kullanici_adi):
        """Kullanicinin portfoyunu getir"""
        kullanici_adi = kullanici_adi.lower().strip()
        if kullanici_adi in self.veriler["kullanicilar"]:
            kullanici = self.veriler["kullanicilar"][kullanici_adi]
            return kullanici.get("portfoy", kullanici.get(" portfoy", []))
        return []
    
    def portfoy_kaydet(self, kullanici_adi, portfoy):
        """Kullanicinin portfoyunu kaydet"""
        kullanici_adi = kullanici_adi.lower().strip()
        if kullanici_adi in self.veriler["kullanicilar"]:
            self.veriler["kullanicilar"][kullanici_adi]["portfoy"] = portfoy
            self.kaydet()
            return True
        return False
