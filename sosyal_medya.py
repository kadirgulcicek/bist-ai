"""BIST icin acik kaynak haber ve piyasa duyarliligi analizi."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import unescape
import re

import feedparser
import requests
import yfinance as yf


SIRKET_ADLARI = {
    "THYAO": ("THY", "Turk Hava Yollari", "Turkish Airlines"),
    "GARAN": ("Garanti Bankasi", "Garanti"),
    "ASELS": ("Aselsan",),
    "TUPRS": ("Tupras",),
    "EREGL": ("Erdemir", "Eregli Demir Celik"),
    "KCHOL": ("Koc Holding",),
    "PETKM": ("Petkim",),
    "BIMAS": ("BIM",),
    "AKBNK": ("Akbank",),
    "ISCTR": ("Is Bankasi",),
}
POZITIF = ("artis", "yukselis", "rekor", "buyume", "kar", "temettu", "anlasma", "olumlu", "guclu")
NEGATIF = ("dusus", "gerileme", "zarar", "satis", "borc", "sorusturma", "olumsuz", "risk", "ceza")
KAP_OLAY_TURLERI = (
    ("SOZLESME_IHALE", ("sozlesme", "ihale", "siparis", "anlasma"), 3),
    ("FINANSAL_SONUCLAR", ("finansal rapor", "bilanco", "gelir tablosu", "kar", "zarar"), 2),
    ("TEMETTU", ("temettu", "kar payi"), 2),
    ("PAY_GERI_ALIM", ("pay geri alim", "geri alim"), 2),
    ("SERMAYE", ("sermaye artirimi", "bedelli", "bedelsiz"), 1),
    ("YAPTIRIM_RISK", ("ceza", "sorusturma", "tedbir", "dava"), -3),
)


def _normalize(metin):
    return (
        unescape(str(metin or ""))
        .lower()
        .translate(str.maketrans("çğıöşü", "cgiosu"))
    )


def anahtar_kelime_uret(sembol):
    """Sembol ve bilinen sirket adlariyla arama ifadesi uretir."""
    sembol = str(sembol or "").upper().replace(".IS", "").strip()
    if not sembol:
        return []
    return [sembol, *SIRKET_ADLARI.get(sembol, ())]


def sentiment_hesapla(metin):
    """Baslik metninden basit ve denetlenebilir duyarlilik skoru uretir."""
    temiz = _normalize(metin)
    pozitif = sum(kelime in temiz for kelime in POZITIF)
    negatif = sum(kelime in temiz for kelime in NEGATIF)
    if pozitif > negatif:
        return "POZITIF", pozitif - negatif
    if negatif > pozitif:
        return "NEGATIF", negatif - pozitif
    return "NOTR", 0


def kap_olayini_siniflandir(baslik):
    temiz = _normalize(baslik)
    sentiment, sentiment_skoru = sentiment_hesapla(baslik)
    for olay_turu, anahtarlar, taban_etki in KAP_OLAY_TURLERI:
        if any(anahtar in temiz for anahtar in anahtarlar):
            yon = -1 if sentiment == "NEGATIF" else 1
            return olay_turu, max(-5, min(5, taban_etki * yon + sentiment_skoru * yon))
    return "DIGER", sentiment_skoru if sentiment == "POZITIF" else -sentiment_skoru


def _rss_haberleri_al(kaynak, url, anahtarlar, limit=10):
    feed = feedparser.parse(url)
    haberler = []
    gorulen = set()
    for kayit in feed.entries[:50]:
        baslik = re.sub(r"<[^>]+>", "", kayit.get("title", "")).strip()
        if not baslik or baslik in gorulen:
            continue
        baslik_norm = _normalize(baslik)
        if not any(_normalize(anahtar) in baslik_norm for anahtar in anahtarlar):
            continue
        gorulen.add(baslik)
        sentiment, skor = sentiment_hesapla(baslik)
        haberler.append({
            "baslik": baslik,
            "link": kayit.get("link", ""),
            "kaynak": kaynak,
            "sentiment": sentiment,
            "skor": skor,
        })
        if len(haberler) == limit:
            break
    return haberler


def google_news_rss(sembol, anahtarlar):
    sorgu = f"{sembol} Borsa Istanbul"
    url = f"https://news.google.com/rss/search?q={sorgu.replace(' ', '%20')}&hl=tr&gl=TR&ceid=TR:tr"
    return _rss_haberleri_al("Google News", url, anahtarlar)


def kap_rss(sembol, anahtarlar):
    return _rss_haberleri_al("KAP", "https://www.kap.org.tr/tr/rss/bildirim", anahtarlar)


def kap_aday_ozeti(semboller, timeout=8):
    """KAP akisini tek istekte alip verilen sembollerle eslestirir."""
    temiz_semboller = [str(sembol).upper().replace(".IS", "").strip() for sembol in semboller]
    sonuc = {
        sembol: {"adet": 0, "net_sinyal": 0, "basliklar": [], "olaylar": []}
        for sembol in temiz_semboller
    }
    try:
        yanit = requests.get("https://www.kap.org.tr/tr/rss/bildirim", timeout=timeout)
        yanit.raise_for_status()
        akis = feedparser.parse(yanit.content)
    except Exception:
        return sonuc
    for kayit in akis.entries[:100]:
        baslik = re.sub(r"<[^>]+>", "", kayit.get("title", "")).strip()
        baslik_norm = _normalize(baslik)
        for sembol in temiz_semboller:
            if not any(_normalize(anahtar) in baslik_norm for anahtar in anahtar_kelime_uret(sembol)):
                continue
            sentiment, skor = sentiment_hesapla(baslik)
            isaretli_skor = skor if sentiment == "POZITIF" else -skor if sentiment == "NEGATIF" else 0
            olay_turu, olay_etkisi = kap_olayini_siniflandir(baslik)
            sonuc[sembol]["adet"] += 1
            sonuc[sembol]["net_sinyal"] += olay_etkisi if olay_turu != "DIGER" else isaretli_skor
            sonuc[sembol]["basliklar"].append(baslik)
            sonuc[sembol]["olaylar"].append({
                "tur": olay_turu,
                "etki": olay_etkisi,
                "baslik": baslik,
                "yayin_zamani": kayit.get("published") or kayit.get("updated"),
            })
    return sonuc


def yahoo_piyasa_ozeti(sembol):
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        fiyatlar = ticker.history(period="5d", auto_adjust=True)
        if fiyatlar is None or len(fiyatlar) < 2:
            return {}
        onceki = float(fiyatlar["Close"].iloc[-2])
        son = float(fiyatlar["Close"].iloc[-1])
        return {
            "fiyat": round(son, 2),
            "gunluk_degisim": round((son / onceki - 1) * 100, 2) if onceki else None,
            "hacim": int(fiyatlar["Volume"].iloc[-1]) if "Volume" in fiyatlar else None,
        }
    except Exception:
        return {}


def sosyal_medya_analiz(sembol):
    """Google News RSS, KAP ve Yahoo verilerinden duyarlilik ozeti uretir."""
    sembol = str(sembol or "").upper().replace(".IS", "").strip()
    anahtarlar = anahtar_kelime_uret(sembol)
    if not anahtarlar:
        return None

    kaynaklar = (google_news_rss, kap_rss)
    haberler = []
    with ThreadPoolExecutor(max_workers=len(kaynaklar)) as havuz:
        gelecekler = [havuz.submit(kaynak, sembol, anahtarlar) for kaynak in kaynaklar]
        for gelecek in as_completed(gelecekler):
            try:
                haberler.extend(gelecek.result())
            except Exception:
                continue

    gorulen = set()
    haberler = [haber for haber in haberler if not (haber["baslik"] in gorulen or gorulen.add(haber["baslik"]))][:15]
    pozitif = sum(haber["sentiment"] == "POZITIF" for haber in haberler)
    negatif = sum(haber["sentiment"] == "NEGATIF" for haber in haberler)
    net_skor = sum(haber["skor"] if haber["sentiment"] == "POZITIF" else -haber["skor"] for haber in haberler)
    durum = "POZITIF" if net_skor > 0 else "NEGATIF" if net_skor < 0 else "NOTR"

    return {
        "sembol": sembol,
        "haberler": haberler,
        "toplam_haber": len(haberler),
        "pozitif": pozitif,
        "negatif": negatif,
        "notr": len(haberler) - pozitif - negatif,
        "sentiment": durum if haberler else "VERI YOK",
        "sentiment_skoru": net_skor,
        "piyasa": yahoo_piyasa_ozeti(sembol),
        "kaynaklar": ["Google News RSS", "KAP", "Yahoo Finance"],
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


if __name__ == "__main__":
    sembol = input("Hisse kodu (varsayilan THYAO): ").strip().upper() or "THYAO"
    sonuc = sosyal_medya_analiz(sembol)
    print(f"{sonuc['sembol']} | {sonuc['sentiment']} | Skor: {sonuc['sentiment_skoru']}")
    print(f"Haber: {sonuc['toplam_haber']} | Pozitif: {sonuc['pozitif']} | Negatif: {sonuc['negatif']}")
    for haber in sonuc["haberler"][:5]:
        print(f"- [{haber['kaynak']}] {haber['baslik']}")
