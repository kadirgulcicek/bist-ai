"""KAP ve ucretsiz RSS kaynaklarindan halka arz takip modulu."""

import json
import os
import re
import calendar
from datetime import datetime, timedelta

import feedparser
import yfinance as yf

DOSYA = "halka_arz_takip.json"
KAYNAKLAR = {
    "KAP": "https://www.kap.org.tr/tr/rss/bildirim",
    "Google News - Halka Arz": "https://news.google.com/rss/search?q=halka%20arz%20BIST&hl=tr&gl=TR&ceid=TR:tr",
    "Google News - Talep Toplama": "https://news.google.com/rss/search?q=talep%20toplama%20Borsa%20Istanbul&hl=tr&gl=TR&ceid=TR:tr",
    "Google News - Yeni Hisse": "https://news.google.com/rss/search?q=yeni%20hisse%20borsada%20islem%20gorecek&hl=tr&gl=TR&ceid=TR:tr",
}
ANAHTARLAR = ("halka arz", "halka arzı", "talep toplama", "talep toplama tarih", "borsada işlem", "işlem görmeye", "ilk işlem", "işlem görmeye başlayacak")


def _yukle():
    try:
        with open(DOSYA, "r", encoding="utf-8") as dosya:
            return json.load(dosya)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _kaydet(veriler):
    with open(DOSYA, "w", encoding="utf-8") as dosya:
        json.dump(veriler, dosya, ensure_ascii=False, indent=2)


def _tarih_bul(metin):
    aylar = {"ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6, "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12}
    turkce = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(20\d{2})", metin.lower())
    if turkce and turkce.group(2) in aylar:
        try:
            return datetime(int(turkce.group(3)), aylar[turkce.group(2)], int(turkce.group(1))).date()
        except ValueError:
            return None
    eslesme = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})|(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](20\d{2})", metin)
    if not eslesme:
        return None
    try:
        if eslesme.group(1):
            return datetime(int(eslesme.group(1)), int(eslesme.group(2)), int(eslesme.group(3))).date()
        return datetime(int(eslesme.group(6)), int(eslesme.group(5)), int(eslesme.group(4))).date()
    except ValueError:
        return None


def _alan_bul(metin, desenler):
    for desen in desenler:
        eslesme = re.search(desen, metin, re.IGNORECASE)
        if eslesme:
            return eslesme.group(1).strip()
    return "Belirtilmedi"


def _kayit_olustur(baslik, ozet, link, kaynak):
    metin = f"{baslik} {ozet}"
    if not any(anahtar in metin.lower() for anahtar in ANAHTARLAR):
        return None
    sembol = _alan_bul(metin, (r"(?:kod|borsa kodu)[: ]+([A-Z]{3,6})\b", r"\b([A-Z]{3,6})\.E\b", r"\(([A-Z]{3,6})\)\s+halka arz", r"\b([A-Z]{3,6})\s+halka arz"))
    arz_tarihi = _tarih_bul(metin)
    return {
        "id": link or baslik,
        "sirket": _alan_bul(metin, (r"(?:şirket|firma)[: ]+([^,.;]+)",)),
        "sembol": sembol,
        "baslik": baslik,
        "link": link,
        "kaynak": kaynak,
        "arz_fiyati": _alan_bul(metin, (r"(?:arz fiyat.{0,2}|satış fiyat.{0,2})\s*[:=-]?\s*([0-9]+(?:[.,][0-9]+)?)\s*TL?", r"(?:arz fiyat.{0,2}|satış fiyat.{0,2})\s*[:=-]?\s*([0-9]+(?:[.,][0-9]+)?)")),
        "iskonto": _alan_bul(metin, (r"(?:iskonto|indirim)[: ]*%?([0-9]+(?:[.,][0-9]+)?)",)),
        "talep_tarihi": _alan_bul(metin, (r"(?:talep toplama|arz tarihi)[: ]*([^.;]+)",)),
        "borsa_baslangic": _alan_bul(metin, (r"(?:işlem görmeye|borsada işlem)[: ]*([^.;]+)",)),
        "duyuru_tarihi": arz_tarihi.isoformat() if arz_tarihi else datetime.now().date().isoformat(),
        "takip_baslangic": None,
        "takip_bitis": None,
        "durum": "DUYURU",
    }


def _sembol_temizle(sembol):
    sembol = str(sembol or "").upper().replace(".E", "")
    return sembol if re.fullmatch(r"[A-Z]{3,6}", sembol) and sembol not in {"HALKA", "TALEP", "BORSA"} else ""


def _fiyat_degisimini_ekle(veri):
    sembol = _sembol_temizle(veri.get("sembol"))
    veri["sembol"] = sembol or "Belirtilmedi"
    veri["piyasa_baslangic"] = veri.get("borsa_baslangic") or veri.get("duyuru_tarihi", "Belirtilmedi")
    veri["ilk_islem_fiyati"] = "Veri yok"
    veri["guncel_fiyat"] = "Veri yok"
    veri["fiyat_degisim"] = "Veri yok"
    if not sembol:
        return veri
    try:
        fiyatlar = yf.Ticker(f"{sembol}.IS").history(period="max", auto_adjust=True)["Close"].dropna()
        if fiyatlar.empty:
            return veri
        baslangic = _tarih_bul(str(veri.get("borsa_baslangic", "")))
        if baslangic:
            uygun = fiyatlar[fiyatlar.index.date >= baslangic]
            if not uygun.empty:
                fiyatlar = uygun
        ilk, guncel = float(fiyatlar.iloc[0]), float(fiyatlar.iloc[-1])
        veri["ilk_islem_fiyati"] = round(ilk, 2)
        veri["guncel_fiyat"] = round(guncel, 2)
        veri["fiyat_degisim"] = round((guncel / ilk - 1) * 100, 2)
    except Exception:
        pass
    return veri


def _kaynaklari_oku():
    haberler = []
    for kaynak, url in KAYNAKLAR.items():
        try:
            akis = feedparser.parse(url)
            for kayit in akis.entries[:50]:
                haber = _kayit_olustur(kayit.get("title", ""), kayit.get("summary", ""), kayit.get("link", ""), kaynak)
                if haber:
                    yayin_tarihi = kayit.get("published_parsed") or kayit.get("updated_parsed")
                    if yayin_tarihi:
                        haber["duyuru_tarihi"] = datetime.fromtimestamp(calendar.timegm(yayin_tarihi)).date().isoformat()
                    haberler.append(haber)
        except Exception:
            continue
    return haberler


def halka_arzlari_guncelle():
    veriler = _yukle()
    for yeni in _kaynaklari_oku():
        eslesme_id = yeni["id"]
        if yeni.get("sembol") and yeni["sembol"] != "Belirtilmedi":
            for mevcut_id, mevcut in veriler.items():
                if mevcut.get("sembol") == yeni["sembol"]:
                    eslesme_id = mevcut_id
                    break
        eski = veriler.get(eslesme_id, {})
        yeni.update({k: eski.get(k) for k in ("takip_baslangic", "takip_bitis", "durum") if eski.get(k)})
        veriler[eslesme_id] = yeni
    bugun = datetime.now().date()
    for veri in veriler.values():
        tarih = _tarih_bul(f"{veri.get('talep_tarihi', '')} {veri.get('duyuru_tarihi', '')}")
        if veri.get("takip_baslangic"):
            bitis = datetime.fromisoformat(veri["takip_baslangic"]).date() + timedelta(days=14)
            veri["takip_bitis"] = bitis.isoformat()
            veri["durum"] = "14 GUN TAKIP" if bugun <= bitis else "TAKIP TAMAMLANDI"
        elif tarih and tarih <= bugun and (bugun - tarih).days <= 14:
            veri["takip_baslangic"] = tarih.isoformat()
            veri["takip_bitis"] = (tarih + timedelta(days=14)).isoformat()
            veri["durum"] = "14 GUN TAKIP"
        elif tarih and tarih > bugun:
            veri["durum"] = "BEKLENIYOR"
        _fiyat_degisimini_ekle(veri)
    _kaydet(veriler)
    return sorted(veriler.values(), key=lambda veri: veri.get("duyuru_tarihi", ""), reverse=True)


def halka_arz_ozeti():
    veriler = halka_arzlari_guncelle()
    son_alti = veriler[:6]
    return {
        "tum": son_alti,
        "son_alti": son_alti,
        "takip": [veri for veri in son_alti if veri.get("durum") == "14 GUN TAKIP"],
        "beklenen": [veri for veri in son_alti if veri.get("durum") == "BEKLENIYOR"],
        "son_guncelleme": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
