"""BIST sahiplik ve hacim analizi.

Yahoo Finance, BIST icin yabanci takas payini dogrudan saglamaz. Bu modul
kurumsal/iciden sahiplik ve hacim alanlarini raporlar; yabanci payi ise
veri kaynagi olmadiginda tahmin edilmez.
"""

import json
import os
from datetime import datetime, timedelta
import re

import requests
import yfinance as yf
from bs4 import BeautifulSoup


HTTP_TIMEOUT = 10
CACHE_DOSYA = "takas_cache.json"
CACHE_SURESI_GUN = 7
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def _onbellek_yukle():
    try:
        with open(CACHE_DOSYA, "r", encoding="utf-8") as dosya:
            veri = json.load(dosya)
            return veri if isinstance(veri, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _onbellek_kaydet(veri):
    with open(CACHE_DOSYA, "w", encoding="utf-8") as dosya:
        json.dump(veri, dosya, ensure_ascii=False, indent=2)


def _onbellek_anahtari(sembol, kullanici):
    return f"{str(kullanici).lower().strip()}:{str(sembol).upper().strip()}"


def yabanci_orani_kaydet(sembol, yabanci_oran, kullanici):
    """Kullanici tarafindan girilen yabanci oranini yedi gun saklar."""
    oran = float(yabanci_oran)
    if not 0 <= oran <= 100:
        raise ValueError("Yabanci orani 0 ile 100 arasynda olmali.")
    onbellek = _onbellek_yukle()
    onbellek[_onbellek_anahtari(sembol, kullanici)] = {
        "yabanci_oran": round(oran, 2),
        "tarih": datetime.now().isoformat(),
        "kaynak": "Manuel giris",
    }
    _onbellek_kaydet(onbellek)


def _onbellekten_yabanci_orani(sembol, kullanici):
    kayit = _onbellek_yukle().get(_onbellek_anahtari(sembol, kullanici))
    if not kayit:
        return None
    try:
        tarih = datetime.fromisoformat(kayit["tarih"])
        if datetime.now() - tarih <= timedelta(days=CACHE_SURESI_GUN):
            return {"yabanci_oran": float(kayit["yabanci_oran"]), "yabanci_kaynak": kayit["kaynak"]}
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _oran_yuzde(deger):
    if deger is None:
        return None
    try:
        return round(float(deger) * 100, 2)
    except (TypeError, ValueError):
        return None


def _sayi(deger):
    try:
        return int(deger) if deger is not None else None
    except (TypeError, ValueError):
        return None


def _ilk_dolu(bilgi, *anahtarlar):
    for anahtar in anahtarlar:
        if bilgi.get(anahtar) is not None:
            return bilgi[anahtar]
    return None


def _yuzdeyi_bul(metin):
    eslesme = re.search(r"%\s*(\d{1,3}(?:[.,]\d+)?)|(\d{1,3}(?:[.,]\d+)?)\s*%", metin or "")
    if not eslesme:
        return None
    try:
        deger = float((eslesme.group(1) or eslesme.group(2)).replace(",", "."))
        return round(deger, 2) if 0 <= deger <= 100 else None
    except ValueError:
        return None


def _yabanci_oranini_tabladan_bul(html):
    """Yalnizca yabanci etiketi bulunan tablo satirindaki yuzdeyi kabul eder."""
    soup = BeautifulSoup(html, "html.parser")
    for satir in soup.find_all("tr"):
        hucreler = satir.find_all(["th", "td"])
        metinler = [hucre.get_text(" ", strip=True) for hucre in hucreler]
        if not any("yabancı" in metin.lower() or "yabanci" in metin.lower() for metin in metinler):
            continue
        for metin in metinler:
            oran = _yuzdeyi_bul(metin)
            if oran is not None:
                return oran
    return None


def isyatirim_takas(sembol):
    """Is Yatirim sirket kartinda acikca etiketlenmis yabanci oranini arar."""
    url = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx"
    try:
        cevap = requests.get(url, params={"hisse": sembol}, headers=HEADERS, timeout=HTTP_TIMEOUT)
        cevap.raise_for_status()
        metin = BeautifulSoup(cevap.text, "html.parser").get_text(" ", strip=True)
        eslesme = re.search(
            r"Yabanc[ıi]\s+Oran[ıi]\s*\(\s*%\s*\)\s*([0-9]+(?:[.,][0-9]+)?)",
            metin,
            flags=re.IGNORECASE,
        )
        oran = _yuzdeyi_bul(eslesme.group(1) + "%") if eslesme else _yabanci_oranini_tabladan_bul(cevap.text)
        return {"yabanci_oran": oran, "yabanci_kaynak": "Is Yatirim"} if oran is not None else None
    except requests.RequestException:
        return None


def foreks_takas(sembol):
    """Foreks hisse sayfasinda acikca etiketlenmis yabanci oranini arar."""
    try:
        cevap = requests.get(
            f"https://www.foreks.com.tr/hisse/{sembol.lower()}/",
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        cevap.raise_for_status()
        oran = _yabanci_oranini_tabladan_bul(cevap.text)
        return {"yabanci_oran": oran, "yabanci_kaynak": "Foreks"} if oran is not None else None
    except requests.RequestException:
        return None


def yfinance_takas(sembol, period="3mo"):
    """Yahoo Finance'den sahiplik ve hacim bilgilerini alir."""
    sembol = str(sembol or "").strip().upper().replace(".IS", "")
    if not sembol:
        return None

    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        tarihce = ticker.history(period=period, auto_adjust=True)
        if tarihce is None or len(tarihce) < 10:
            return None
        bilgi = ticker.info or {}
        return {
            "sembol": sembol,
            "kaynak": "Yahoo Finance",
            "market_cap": _sayi(bilgi.get("marketCap")),
            "toplam_hisse": _sayi(bilgi.get("sharesOutstanding")),
            "free_float": _sayi(bilgi.get("floatShares")),
            "kurumsal_oran": _oran_yuzde(_ilk_dolu(bilgi, "institutionalPercentHeld", "heldPercentInstitutions")),
            "bireysel_oran": _oran_yuzde(_ilk_dolu(bilgi, "insiderPercentHeld", "heldPercentInsiders")),
            "ortalama_hacim_3ay": _sayi(bilgi.get("averageVolume")),
            "ortalama_hacim_10gun": _sayi(bilgi.get("averageVolume10days")),
        }
    except Exception:
        return None


def _kurumsal_yorum(oran):
    if oran is None:
        return "Veri yok"
    if oran >= 30:
        return "Yuksek kurumsal sahiplik"
    if oran >= 10:
        return "Orta kurumsal sahiplik"
    return "Dusuk kurumsal sahiplik"


def takas_analiz(sembol, kullanici=None):
    """Tek hisse icin dogrulanabilir sahiplik ve hacim ozetini uretir."""
    veri = yfinance_takas(sembol)
    if not veri:
        return None

    yabanci_verisi = (
        _onbellekten_yabanci_orani(veri["sembol"], kullanici)
        if kullanici else None
    )
    yabanci_verisi = yabanci_verisi or isyatirim_takas(veri["sembol"]) or foreks_takas(veri["sembol"])

    hacim_3ay = veri["ortalama_hacim_3ay"]
    hacim_10gun = veri["ortalama_hacim_10gun"]
    free_float_oran = None
    if veri["free_float"] and veri["toplam_hisse"]:
        free_float_oran = round(veri["free_float"] / veri["toplam_hisse"] * 100, 2)
    hacim_orani = None
    if hacim_3ay and hacim_10gun:
        hacim_orani = round(hacim_10gun / hacim_3ay, 2)

    if hacim_orani is None:
        hacim_yorum = "Veri yok"
    elif hacim_orani > 1.5:
        hacim_yorum = "Son 10 gunde hacim artti"
    elif hacim_orani > 1.1:
        hacim_yorum = "Son 10 gunde hacim hafif artti"
    elif hacim_orani >= 0.9:
        hacim_yorum = "Hacim stabil"
    else:
        hacim_yorum = "Son 10 gunde hacim azaldi"

    kurumsal_oran = veri["kurumsal_oran"]
    yabanci_oran = yabanci_verisi["yabanci_oran"] if yabanci_verisi else None
    puan = int(kurumsal_oran is not None and kurumsal_oran >= 30)
    puan += int(yabanci_oran is not None and yabanci_oran >= 40)
    puan += int(hacim_orani is not None and hacim_orani > 1.2)
    if puan >= 2:
        degerlendirme = "Kurumsal sahiplik ve hacim olumlu"
    elif puan == 1:
        degerlendirme = "Orta ilgi"
    else:
        degerlendirme = "Dusuk kurumsal ilgi veya eksik veri"

    return {
        **veri,
        "yabanci_oran": yabanci_oran,
        "yabanci_yorum": (
            f"{yabanci_verisi['yabanci_kaynak']} kaynakli yabanci payi"
            if yabanci_verisi else "Acik kaynaklarda dogrulanmis yabanci orani bulunamadi"
        ),
        "kurumsal_yorum": _kurumsal_yorum(kurumsal_oran),
        "hacim_orani": hacim_orani,
        "hacim_yorum": hacim_yorum,
        "free_float_oran": free_float_oran,
        "degerlendirme": degerlendirme,
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def coklu_takas_analizi(hisse_listesi):
    """Hisseleri yabanci, ardindan kurumsal sahiplik oranina gore siralar."""
    sonuclar = [takas_analiz(sembol) for sembol in hisse_listesi]
    sonuclar = [analiz for analiz in sonuclar if analiz]
    return sorted(
        sonuclar,
        key=lambda analiz: (
            analiz["yabanci_oran"] if analiz["yabanci_oran"] is not None else -1,
            analiz["kurumsal_oran"] if analiz["kurumsal_oran"] is not None else -1,
        ),
        reverse=True,
    )


if __name__ == "__main__":
    print("BIST SAHIPLIK VE HACIM ANALIZI")
    print("=" * 50)
    for sonuc in coklu_takas_analizi(["THYAO", "GARAN", "ASELS", "TUPRS"]):
        print(f"\n{sonuc['sembol']}:")
        print(f"  Kurumsal: %{sonuc['kurumsal_oran'] if sonuc['kurumsal_oran'] is not None else 'Veri yok'}")
        print(f"  Yabanci: {sonuc['yabanci_yorum']}")
        print(f"  Hacim: {sonuc['hacim_yorum']}")
        print(f"  Degerlendirme: {sonuc['degerlendirme']}")
