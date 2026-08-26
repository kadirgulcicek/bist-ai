"""KAP ve ucretsiz RSS kaynaklarindan halka arz takip modulu."""

import json
import os
import re
import calendar
import time
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from datetime import datetime, timedelta

import requests
import yfinance as yf

DOSYA = "halka_arz_takip.json"
MANUEL_DOSYA = "manual_ekle.json"
HTTP_TIMEOUT = 8
HALKARZ_URL = "https://halkarz.com/"
HALKARZ_CACHE_TTL = 900
_halkarz_onbellek = {"zaman": 0, "kayitlar": []}
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


def _manuel_verileri_uygula(veriler):
    try:
        with open(MANUEL_DOSYA, "r", encoding="utf-8") as dosya:
            manuel = json.load(dosya)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    for kayit in manuel if isinstance(manuel, list) else []:
        sembol = _sembol_temizle(kayit.get("sembol"))
        if not sembol:
            continue
        for veri in veriler.values():
            if _sembol_temizle(veri.get("sembol")) == sembol:
                for alan in ("sirket", "arz_fiyati", "iskonto", "link"):
                    deger = kayit.get(alan)
                    if deger not in (None, "", "Belirtilmedi"):
                        veri[alan] = deger
                break


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


def _metni_temizle(metin):
    metin = unescape(str(metin or ""))
    metin = re.sub(r"<[^>]+>", " ", metin)
    return re.sub(r"\s+", " ", metin).strip()


def _alan_bul(metin, desenler):
    for desen in desenler:
        eslesme = re.search(desen, metin, re.IGNORECASE)
        if eslesme:
            return eslesme.group(1).strip(" \t\r\n.,;:")
    return "Belirtilmedi"


def _fiyat_bul(metin):
    desenler = (
        r"(?:halka arz|arz|satış|satis|pay başına|birim pay)[^.;]{0,80}?(?:fiyatı|fiyati|bedeli)?\s*[:=-]?\s*(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:TL|lira)\b",
        r"(?:arz|satış|satis) fiyat(?:ı|i)?\s*[:=-]?\s*(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:TL|lira)?\b",
        r"(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:TL|lira)\s*(?:fiyatından|fiyatla|ile)\s*(?:halka arz|satış|satis)",
    )
    return _alan_bul(metin, desenler)


def _iskonto_bul(metin):
    desenler = (
        r"(?:iskonto|indirim)(?: oranı| orani)?\s*[:=-]?\s*%?\s*(\d+(?:[.,]\d+)?)\s*%?",
        r"%\s*(\d+(?:[.,]\d+)?)\s*(?:oranında\s+)?(?:iskonto|indirim)",
        r"(\d+(?:[.,]\d+)?)\s*%\s*(?:iskontolu|indirimli)",
        r"yüzde\s+(\d+(?:[.,]\d+)?)\s*(?:oranında\s+)?(?:iskonto|indirim)",
    )
    sonuc = _alan_bul(metin, desenler)
    return f"%{sonuc}" if sonuc != "Belirtilmedi" else sonuc


def _haber_detayi_al(link):
    if not link:
        return ""
    try:
        cevap = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
        if cevap.ok:
            return _metni_temizle(cevap.text)
    except requests.RequestException:
        pass
    return ""


def _halkarz_detaylarini_oku():
    if time.time() - _halkarz_onbellek["zaman"] < HALKARZ_CACHE_TTL:
        return [dict(kayit) for kayit in _halkarz_onbellek["kayitlar"]]
    try:
        cevap = requests.get(HALKARZ_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=(3, 5))
        cevap.raise_for_status()
    except requests.RequestException:
        return []

    adresler = []
    for adres in re.findall(r'href=["\'](https://halkarz\.com/[^"\']+/)["\']', cevap.text):
        if re.search(r"-a-s/$", adres) and adres not in adresler:
            adresler.append(adres)
    def detay_oku(adres):
        try:
            detay_cevap = requests.get(adres, headers={"User-Agent": "Mozilla/5.0"}, timeout=(3, 5))
            detay_cevap.raise_for_status()
        except requests.RequestException:
            return None
        html = unescape(detay_cevap.text)
        metin = _metni_temizle(html)
        sembol = _alan_bul(metin, (r"Bist Kodu\s*:\s*([A-Z]{3,6})\b",))
        if not _sembol_temizle(sembol):
            return None
        sirket = _alan_bul(html, (r"<h1[^>]*>\s*(.*?)\s*</h1>",))
        sirket = _metni_temizle(sirket)
        if sirket == "Belirtilmedi":
            sirket = _alan_bul(metin, (r"(?:Halka Arz Bilgileri|Halka Arz)\s*:?\s*([^|]+)",))
        fiyat = _alan_bul(metin, (
            r"Halka Arz Fiyatı/Aralığı\s*:\s*([0-9.,]+\s*TL)",
            r"Halka Arz Fiyatı\s*:\s*([0-9.,]+\s*TL)",
        ))
        iskonto = _alan_bul(metin, (r"Halka Arz İskontosu\s*-\s*(%\s*[0-9.,]+)",))
        ilk_islem = _alan_bul(metin, (r"Bist İlk İşlem Tarihi\s*:\s*([^|]+?20\d{2})",))
        talep_tarihi = _alan_bul(metin, (r"Halka Arz Tarihi\s*:\s*([^|]+?20\d{2})",))
        arz_tarihi = _tarih_bul(talep_tarihi)
        return {
            "id": adres,
            "sirket": _metni_temizle(sirket),
            "sembol": sembol,
            "baslik": f"{_metni_temizle(sirket)} halka arz",
            "link": adres,
            "kaynak": "HalkArz.com",
            "arz_fiyati": fiyat,
            "iskonto": iskonto,
            "talep_tarihi": talep_tarihi or "Belirtilmedi",
            "borsa_baslangic": ilk_islem,
            "duyuru_tarihi": arz_tarihi.isoformat() if arz_tarihi else datetime.now().date().isoformat(),
            "takip_baslangic": None,
            "takip_bitis": None,
            "durum": "DUYURU",
        }

    with ThreadPoolExecutor(max_workers=8) as havuz:
        kayitlar = [kayit for kayit in havuz.map(detay_oku, adresler[:8]) if kayit]
    _halkarz_onbellek["zaman"] = time.time()
    _halkarz_onbellek["kayitlar"] = kayitlar
    return [dict(kayit) for kayit in kayitlar]


def _kayit_olustur(baslik, ozet, link, kaynak):
    baslik = _metni_temizle(baslik)
    ozet = _metni_temizle(ozet)
    metin = f"{baslik} {ozet}"
    if not any(anahtar in metin.lower() for anahtar in ANAHTARLAR):
        return None
    sembol = _alan_bul(metin, (
        r"(?:kod|borsa kodu|sembol|ticker)\s*[:=-]?\s*([A-Z]{3,6})\b",
        r"\b([A-Z]{3,6})\.E\b",
        r"\(([A-Z]{3,6})\)",
        r"\*{2,}\s*([A-Z]{3,6})(?:,[A-Z]{3,6})*\s*\*{2,}",
        r"\b([A-Z]{3,6})\s+(?:halka arz|borsada işlem|ne zaman borsada)",
    ))
    sirket = _alan_bul(metin, (
        r"(?:şirket|firma)\s*[:=-]\s*([^,.;]+)",
        r"^(.+?)\s+halka arz(?:ı|i)?\b",
    ))
    if sirket == "Belirtilmedi":
        baslik_sirket = re.split(r"\s+halka arz", baslik, maxsplit=1, flags=re.IGNORECASE)[0]
        kap = re.match(r"^KAP\s+\*{2,}\s*(.*?)\s+\*{2,}\s+[A-Z,]+\s+\*{2,}", baslik_sirket, flags=re.IGNORECASE)
        sirket = kap.group(1) if kap else re.sub(r"^KAP\s+\*{2,}.*?\*{2,}\s*", "", baslik_sirket, flags=re.IGNORECASE).strip(" -:") or "Belirtilmedi"
    sirket = re.sub(r"\s*\*{2,}.*$", "", sirket).strip(" -:") or "Belirtilmedi"
    arz_tarihi = _tarih_bul(metin)
    arz_fiyati = _fiyat_bul(metin)
    iskonto = _iskonto_bul(metin)
    if _sembol_temizle(sembol) and (arz_fiyati == "Belirtilmedi" or iskonto == "Belirtilmedi"):
        detay = _haber_detayi_al(link)
        metin = f"{metin} {detay}"
        arz_fiyati = arz_fiyati if arz_fiyati != "Belirtilmedi" else _fiyat_bul(metin)
        iskonto = iskonto if iskonto != "Belirtilmedi" else _iskonto_bul(metin)
    return {
        "id": link or baslik,
        "sirket": sirket,
        "sembol": sembol,
        "baslik": baslik,
        "link": link,
        "kaynak": kaynak,
        "arz_fiyati": arz_fiyati,
        "iskonto": iskonto,
        "talep_tarihi": _alan_bul(metin, (r"(?:talep toplama|arz tarihi)[: ]*([^.;]+)",)),
        "borsa_baslangic": _alan_bul(metin, (r"(?:işlem görmeye|borsada işlem)[: ]*([^.;]+)",)),
        "duyuru_tarihi": arz_tarihi.isoformat() if arz_tarihi else datetime.now().date().isoformat(),
        "takip_baslangic": None,
        "takip_bitis": None,
        "durum": "DUYURU",
    }


def _sembol_temizle(sembol):
    sembol = str(sembol or "").upper().replace(".E", "")
    yasakli = {"HALKA", "TALEP", "BORSA", "BIST", "YENI", "HISSE", "GYO", "SANAYI", "BANK", "GIDA", "ENERJI", "PIYASA", "DAHA", "NEDIR", "SAAT", "NIN", "BETON", "YAPI", "DEVI", "TURIZM", "LIK", "HABER", "ZAMAN", "SON", "BUGUN", "YARIN", "NE", "KADAR", "OLUR", "BELLİ", "ACIKLANDI", "BEKLENIYOR", "ISLEM", "GORECEK"}
    return sembol if re.fullmatch(r"[A-Z]{3,6}", sembol) and sembol not in yasakli else ""


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
        fiyatlar = yf.Ticker(f"{sembol}.IS").history(
            period="max", auto_adjust=True, timeout=HTTP_TIMEOUT
        )["Close"].dropna()
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
            cevap = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=HTTP_TIMEOUT,
            )
            cevap.raise_for_status()
            akis = feedparser.parse(cevap.content)
            for kayit in akis.entries[:50]:
                haber = _kayit_olustur(kayit.get("title", ""), kayit.get("summary", ""), kayit.get("link", ""), kaynak)
                if haber:
                    yayin_tarihi = kayit.get("published_parsed") or kayit.get("updated_parsed")
                    if yayin_tarihi:
                        haber["duyuru_tarihi"] = datetime.fromtimestamp(calendar.timegm(yayin_tarihi)).date().isoformat()
                    haberler.append(haber)
        except (requests.RequestException, ValueError):
            continue
    return haberler


def halka_arzlari_guncelle():
    veriler = _yukle()
    eski_veriler = veriler
    halkarz_kayitlari = _halkarz_detaylarini_oku()
    if not halkarz_kayitlari:
        halkarz_kayitlari = [v for v in veriler.values() if v.get("kaynak") == "HalkArz.com"]
    veriler = {}
    for yeni in halkarz_kayitlari:
        eski = next((v for v in eski_veriler.values() if _sembol_temizle(v.get("sembol")) == yeni["sembol"]), {})
        for alan in ("takip_baslangic", "takip_bitis", "durum", "ilk_islem_fiyati", "guncel_fiyat", "fiyat_degisim"):
            if eski.get(alan) is not None:
                yeni[alan] = eski[alan]
        veriler[yeni["id"]] = yeni
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
    with ThreadPoolExecutor(max_workers=6) as havuz:
        list(havuz.map(_fiyat_degisimini_ekle, veriler.values()))
    _kaydet(veriler)
    return sorted(veriler.values(), key=lambda veri: veri.get("duyuru_tarihi", ""), reverse=True)


def halka_arz_ozeti():
    veriler = halka_arzlari_guncelle()
    guncel_semboller = {
        _sembol_temizle(veri.get("sembol"))
        for veri in _halkarz_detaylarini_oku()
    }
    son_alti = []
    gorulen_semboller = set()
    for veri in veriler:
        if veri.get("kaynak") != "HalkArz.com" or _sembol_temizle(veri.get("sembol")) not in guncel_semboller:
            continue
        sembol = _sembol_temizle(veri.get("sembol"))
        if not sembol or sembol in gorulen_semboller:
            continue
        gorulen_semboller.add(sembol)
        son_alti.append(veri)
        if len(son_alti) == 6:
            break
    return {
        "tum": son_alti,
        "son_alti": son_alti,
        "takip": [veri for veri in son_alti if veri.get("durum") == "14 GUN TAKIP"],
        "beklenen": [veri for veri in son_alti if veri.get("durum") == "BEKLENIYOR"],
        "son_guncelleme": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }


if __name__ == "__main__":
    ozet = halka_arz_ozeti()
    for veri in ozet["son_alti"]:
        print(
            f"{veri.get('sirket', 'Belirtilmedi')} | "
            f"{veri.get('sembol', 'Belirtilmedi')} | "
            f"Arz: {veri.get('arz_fiyati', 'Belirtilmedi')} | "
            f"İskonto: {veri.get('iskonto', 'Belirtilmedi')} | "
            f"Güncel: {veri.get('guncel_fiyat', 'Veri yok')} TL"
        )
