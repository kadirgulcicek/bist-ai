"""
Kisisel Bildirim Sistemi
Her kullanici kendi bildirim tercihlerini belirler
"""

import os
import json
from datetime import datetime


BILDIRIM_DOSYA = "bildirim_ayarlari.json"


def varsayilan_ayarlar():
    """Yeni kullanici icin varsayilan ayarlar"""
    return {
        "aktif": True,
        "saat": "09:00",
        "zaman": "sabah",  # sabah, ogle, aksam, hepsi
        "tur": "hepsi",  # al, sat, hepsi
        "hisseler": [],  # Bos = tum hisseler
        "siklik": "saatlik",  # saatlik, gunluk, haftalik
        "son_bildirim": None
    }


def yukle():
    """Tum kullanicilarin ayarlarini yukle"""
    if os.path.exists(BILDIRIM_DOSYA):
        with open(BILDIRIM_DOSYA, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def kaydet(ayarlar):
    """Ayarlari kaydet"""
    with open(BILDIRIM_DOSYA, "w", encoding="utf-8") as f:
        json.dump(ayarlar, f, indent=2, ensure_ascii=False)


def kullanici_ayarlari_al(kullanici_adi):
    """Kullanicinin ayarlarini getir"""
    ayarlar = yukle()
    if kullanici_adi not in ayarlar:
        ayarlar[kullanici_adi] = varsayilan_ayarlar()
        kaydet(ayarlar)
    return ayarlar[kullanici_adi]


def kullanici_ayarlari_guncelle(kullanici_adi, yeni_ayarlar):
    """Kullanicinin ayarlarini guncelle"""
    ayarlar = yukle()
    ayarlar[kullanici_adi] = yeni_ayarlar
    kaydet(ayarlar)


def bildirim_kaydet(kullanici_adi, mesaj):
    """Kullanici icin bildirim kaydet"""
    kullanici_ayarlari = kullanici_ayarlari_al(kullanici_adi)
    kullanici_ayarlari["son_bildirim"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Bildirim gecmisi
    if "gecmis" not in kullanici_ayarlari:
        kullanici_ayarlari["gecmis"] = []
    
    kullanici_ayarlari["gecmis"].append({
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mesaj": mesaj
    })
    
    # Son 50 bildirim
    kullanici_ayarlari["gecmis"] = kullanici_ayarlari["gecmis"][-50:]
    
    kullanici_ayarlari_guncelle(kullanici_adi, kullanici_ayarlari)


def bildirim_gonder(kullanici_adi, sinyal):
    """Kullanici ayarlarina gore bildirim gonder"""
    ayarlar = kullanici_ayarlari_al(kullanici_adi)
    
    if not ayarlar.get("aktif", True):
        return False

    tercih_saati = str(ayarlar.get("saat", "09:00"))
    try:
        saat, dakika = (int(deger) for deger in tercih_saati.split(":", 1))
        if not 0 <= saat <= 23 or not 0 <= dakika <= 59:
            raise ValueError
        if datetime.now().time().replace(second=0, microsecond=0) < datetime.now().replace(
            hour=saat, minute=dakika, second=0, microsecond=0
        ).time():
            return False
    except (TypeError, ValueError):
        tercih_saati = "09:00"
    
    # Tur filtresi
    tur = ayarlar.get("tur", "hepsi")
    if tur != "hepsi" and sinyal.get("karar") != tur:
        return False
    
    # Hisse filtresi
    hisseler = ayarlar.get("hisseler", [])
    if hisseler and sinyal.get("sembol") not in hisseler:
        return False
    
    # Mesaj olustur
    mesaj = f"{sinyal.get('sembol', '')} - {sinyal.get('karar', '')} - {sinyal.get('sebepler', ['Yeni sinyal'])[0]}"
    bugun = datetime.now().strftime("%Y-%m-%d")
    if any(
        kayit.get("tarih", "").startswith(bugun) and kayit.get("mesaj") == mesaj
        for kayit in ayarlar.get("gecmis", [])
    ):
        return False
    
    # Kaydet (gercek bildirim gonderimi icin webhook entegrasyonu gerekir)
    bildirim_kaydet(kullanici_adi, mesaj)
    
    return True


if __name__ == "__main__":
    # Test
    print("Kisisel Bildirim Sistemi - Test")
    
    ayarlar = kullanici_ayarlari_al("test_user")
    print(f"Varsayilan ayarlar: {ayarlar}")
    
    # Guncelle
    ayarlar["zaman"] = "sabah"
    ayarlar["tur"] = "AL"
    kullanici_ayarlari_guncelle("test_user", ayarlar)
    
    print(f"Guncellenmis: {kullanici_ayarlari_al('test_user')}")
