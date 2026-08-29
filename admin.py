"""
BIST AI Admin Paneli
Kullanici, sistem ve veri yonetimi
"""

import os
import json
import hashlib
from datetime import datetime, timedelta


class AdminYoneticisi:
    """Admin islemleri - Sadece admin kullanicilar erisebilir"""

    def __init__(self):
        self.admin_dosya = "admin_data.json"
        self.veriler = self._yukle()

    def _yukle(self):
        """Admin verilerini yukle"""
        try:
            if os.path.exists(self.admin_dosya):
                with open(self.admin_dosya, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return self._varsayilan()

    def _varsayilan(self):
        """Varsayilan admin verileri"""
        return {
            "admin_kullanicilar": [],
            "sistem_ayarlari": {
                "bakim_modu": False,
                "kayit_acik": True,
                "api_limitleri": {},
                "son_guncelleme": datetime.now().isoformat(),
            },
            "aktivite_log": [],
            "hata_log": [],
            "sistem_metrikleri": {
                "toplam_kullanici": 0,
                "aktif_kullanici": 0,
                "toplam_portfoy": 0,
                "toplam_sorgu": 0,
                "api_cagrilari": 0,
            },
            "engellenen_ip": [],
        }

    def _kaydet(self):
        """Verileri kaydet"""
        try:
            self.veriler["sistem_ayarlari"]["son_guncelleme"] = datetime.now().isoformat()
            with open(self.admin_dosya, "w", encoding="utf-8") as f:
                json.dump(self.veriler, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def admin_ekle(self, kullanici_adi, sifre, email, rol="admin"):
        """Yeni admin ekle"""
        sifre_hash = hashlib.sha256(sifre.encode()).hexdigest()
        admin = {
            "kullanici_adi": kullanici_adi,
            "sifre_hash": sifre_hash,
            "email": email,
            "rol": rol,
            "eklenme_tarihi": datetime.now().isoformat(),
            "son_giris": None,
            "aktif": True,
        }
        for mevcut in self.veriler["admin_kullanicilar"]:
            if mevcut["kullanici_adi"] == kullanici_adi:
                return False, "Kullanici zaten var"

        self.veriler["admin_kullanicilar"].append(admin)
        self._kaydet()
        return True, "Admin eklendi"

    def admin_sil(self, kullanici_adi):
        """Admin sil"""
        for i, admin in enumerate(self.veriler["admin_kullanicilar"]):
            if admin["kullanici_adi"] == kullanici_adi:
                del self.veriler["admin_kullanicilar"][i]
                self._kaydet()
                return True
        return False

    def admin_listele(self):
        """Tum adminleri listele"""
        return self.veriler["admin_kullanicilar"]

    def log_ekle(self, kullanici, islem, detay=""):
        """Aktivite logu ekle"""
        log = {
            "tarih": datetime.now().isoformat(),
            "kullanici": kullanici,
            "islem": islem,
            "detay": detay,
            "ip": "",
        }
        self.veriler["aktivite_log"].append(log)
        self.veriler["aktivite_log"] = self.veriler["aktivite_log"][-1000:]
        self._kaydet()

    def loglari_getir(self, son_n=50, filtre=None):
        """Loglari getir"""
        loglar = self.veriler["aktivite_log"][-son_n:]
        loglar.reverse()
        if filtre:
            loglar = [l for l in loglar if filtre.lower() in str(l).lower()]
        return loglar

    def hata_logla(self, hata, modul=""):
        """Hata logla"""
        log = {
            "tarih": datetime.now().isoformat(),
            "hata": str(hata),
            "modul": modul,
        }
        self.veriler["hata_log"].append(log)
        self.veriler["hata_log"] = self.veriler["hata_log"][-500:]
        self._kaydet()

    def hatalari_getir(self, son_n=50):
        """Hatalari getir"""
        hatalar = self.veriler["hata_log"][-son_n:]
        hatalar.reverse()
        return hatalar

    def metrik_guncelle(self, kullanici=None, portfoy=None, sorgu=None, api=None):
        """Sistem metriklerini guncelle"""
        if kullanici:
            self.veriler["sistem_metrikleri"]["toplam_kullanici"] = kullanici
        if portfoy is not None:
            self.veriler["sistem_metrikleri"]["toplam_portfoy"] = portfoy
        if sorgu is not None:
            self.veriler["sistem_metrikleri"]["toplam_sorgu"] += sorgu
        if api is not None:
            self.veriler["sistem_metrikleri"]["api_cagrilari"] += api
        self._kaydet()

    def metrikleri_getir(self):
        """Metrikleri getir"""
        return self.veriler["sistem_metrikleri"]

    def ayar_al(self, anahtar, varsayilan=None):
        """Ayar degeri al"""
        return self.veriler["sistem_ayarlari"].get(anahtar, varsayilan)

    def ayar_kaydet(self, anahtar, deger):
        """Ayar kaydet"""
        self.veriler["sistem_ayarlari"][anahtar] = deger
        self._kaydet()
        return True

    def bakim_modu(self, aktif=None):
        """Bakim modunu ac/kapat"""
        if aktif is None:
            return self.veriler["sistem_ayarlari"]["bakim_modu"]
        self.veriler["sistem_ayarlari"]["bakim_modu"] = aktif
        self._kaydet()
        return aktif

    def kayit_acik(self, aktif=None):
        """Kayit acar/kapatir"""
        if aktif is None:
            return self.veriler["sistem_ayarlari"]["kayit_acik"]
        self.veriler["sistem_ayarlari"]["kayit_acik"] = aktif
        self._kaydet()
        return aktif

    def ip_engelle(self, ip, sebep=""):
        """IP adresini engelle"""
        self.veriler["engellenen_ip"].append({
            "ip": ip,
            "tarih": datetime.now().isoformat(),
            "sebep": sebep,
        })
        self._kaydet()

    def ip_engelli_mi(self, ip):
        """IP engelli mi kontrol"""
        for kayit in self.veriler["engellenen_ip"]:
            if kayit["ip"] == ip:
                return True
        return False

    def ip_engel_kaldir(self, ip):
        """IP engelini kaldir"""
        for i, kayit in enumerate(self.veriler["engellenen_ip"]):
            if kayit["ip"] == ip:
                del self.veriler["engellenen_ip"][i]
                self._kaydet()
                return True
        return False

    def genel_istatistikler(self):
        """Genel istatistikler"""
        toplam_log = len(self.veriler["aktivite_log"])
        hata_log = len(self.veriler["hata_log"])
        aktif_admin = sum(1 for a in self.veriler["admin_kullanicilar"] if a.get("aktif", True))
        engelli_ip = len(self.veriler["engellenen_ip"])

        son_24 = sum(
            1
            for l in self.veriler["aktivite_log"]
            if datetime.fromisoformat(l["tarih"]) > datetime.now() - timedelta(hours=24)
        )

        return {
            "toplam_admin": len(self.veriler["admin_kullanicilar"]),
            "aktif_admin": aktif_admin,
            "toplam_aktivite": toplam_log,
            "son_24_saat_aktivite": son_24,
            "toplam_hata": hata_log,
            "engelli_ip_sayisi": engelli_ip,
            "metrikler": self.veriler["sistem_metrikleri"],
        }
