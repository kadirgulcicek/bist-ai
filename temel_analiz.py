"""
Temel Analiz - BIST hisseleri icin mali veri analizi
F/K, PD/DD, Temettu, Buyume oranlari
"""

from datetime import datetime

import yfinance as yf


def guvenli_bilgi(sembol):
    """YFinance'den hisse bilgilerini guvenli al"""
    try:
        ticker = yf.Ticker(sembol + ".IS")
        return ticker.info or {}
    except Exception:
        return {}


def temel_analiz(sembol):
    """
    Bir hisse icin temel analiz bilgileri

    Returns: dict veya None
    """
    try:
        simb = str(sembol or "").strip().upper().replace(".IS", "")
        if not simb:
            return None

        info = guvenli_bilgi(simb)
        if not info:
            return None

        fiyat = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        onceki_kapanis = info.get("previousClose") or 0

        degisim = 0.0
        if fiyat and onceki_kapanis and onceki_kapanis > 0:
            degisim = ((fiyat - onceki_kapanis) / onceki_kapanis) * 100

        market_cap = info.get("marketCap") or 0
        market_cap_milyar = market_cap / 1_000_000_000 if market_cap else 0

        fk = info.get("trailingPE")
        fk_forward = info.get("forwardPE")
        pddd = info.get("priceToBook")
        fd_favok = info.get("enterpriseToEbitda")

        temettu_verimi = info.get("dividendYield")
        if temettu_verimi:
            temettu_verimi = temettu_verimi * 100

        hafta_52_yuksek = info.get("fiftyTwoWeekHigh") or 0
        hafta_52_dusuk = info.get("fiftyTwoWeekLow") or 0

        pozisyon_52 = 0.0
        if hafta_52_yuksek and hafta_52_dusuk and hafta_52_yuksek > hafta_52_dusuk:
            pozisyon_52 = ((fiyat - hafta_52_dusuk) / (hafta_52_yuksek - hafta_52_dusuk)) * 100

        hacim = info.get("volume") or 0
        ort_hacim_3ay = info.get("averageDailyVolume3Month") or 0
        hacim_orani = (hacim / ort_hacim_3ay) if ort_hacim_3ay and ort_hacim_3ay > 0 else 1.0

        gelir_buyumesi = info.get("revenueGrowth")
        if gelir_buyumesi is not None:
            gelir_buyumesi = gelir_buyumesi * 100

        kar_buyumesi = info.get("earningsGrowth")
        if kar_buyumesi is not None:
            kar_buyumesi = kar_buyumesi * 100

        kar_marji = info.get("profitMargins")
        if kar_marji is not None:
            kar_marji = kar_marji * 100

        borc_ozkaynak = info.get("debtToEquity")

        roe = info.get("returnOnEquity")
        if roe is not None:
            roe = roe * 100

        sonuc = {
            "sembol": simb,
            "fiyat": round(float(fiyat), 2) if fiyat else 0,
            "onceki_kapanis": round(float(onceki_kapanis), 2) if onceki_kapanis else 0,
            "degisim": round(float(degisim), 2),
            "fk": round(float(fk), 2) if fk else None,
            "fk_forward": round(float(fk_forward), 2) if fk_forward else None,
            "pddd": round(float(pddd), 2) if pddd else None,
            "fd_favok": round(float(fd_favok), 2) if fd_favok else None,
            "temettu_verimi": round(float(temettu_verimi), 2) if temettu_verimi else None,
            "hacim": int(hacim) if hacim else 0,
            "ort_hacim_3ay": int(ort_hacim_3ay) if ort_hacim_3ay else 0,
            "hacim_orani": round(float(hacim_orani), 2),
            "hafta_52_yuksek": float(hafta_52_yuksek) if hafta_52_yuksek else 0,
            "hafta_52_dusuk": float(hafta_52_dusuk) if hafta_52_dusuk else 0,
            "pozisyon_52": round(float(pozisyon_52), 1),
            "gelir_buyumesi": round(float(gelir_buyumesi), 1) if gelir_buyumesi is not None else None,
            "kar_buyumesi": round(float(kar_buyumesi), 1) if kar_buyumesi is not None else None,
            "kar_marji": round(float(kar_marji), 1) if kar_marji is not None else None,
            "borc_ozkaynak": round(float(borc_ozkaynak), 2) if borc_ozkaynak is not None else None,
            "roe": round(float(roe), 1) if roe is not None else None,
            "market_cap_milyar": round(float(market_cap_milyar), 2),
            "sektor": info.get("sector") or "Bilinmiyor",
            "endustri": info.get("industry") or "Bilinmiyor",
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        if fk is not None:
            if fk < 10:
                sonuc["fk_yorum"] = "Cok ucuz (F/K < 10)"
            elif fk < 15:
                sonuc["fk_yorum"] = "Ucuz"
            elif fk < 25:
                sonuc["fk_yorum"] = "Normal"
            else:
                sonuc["fk_yorum"] = "Pahali"
        else:
            sonuc["fk_yorum"] = "Veri yok"

        if pddd is not None:
            if pddd < 1:
                sonuc["pddd_yorum"] = "Ucuz (< 1)"
            elif pddd < 3:
                sonuc["pddd_yorum"] = "Normal"
            else:
                sonuc["pddd_yorum"] = "Pahali"
        else:
            sonuc["pddd_yorum"] = "Veri yok"

        if pozisyon_52 > 80:
            sonuc["pozisyon_52_yorum"] = "52 hafta tepede"
        elif pozisyon_52 < 20:
            sonuc["pozisyon_52_yorum"] = "52 hafta dibinde"
        else:
            sonuc["pozisyon_52_yorum"] = "52 hafta ortasinda"

        puanlar = []

        if fk is not None and fk < 15:
            puanlar.append(1)
        if pddd is not None and pddd < 2:
            puanlar.append(1)
        if temettu_verimi is not None and temettu_verimi > 3:
            puanlar.append(1)
        if roe is not None and roe > 15:
            puanlar.append(1)
        if gelir_buyumesi is not None and gelir_buyumesi > 10:
            puanlar.append(1)

        if len(puanlar) >= 4:
            sonuc["genel_degerlendirme"] = "COK IYI - Uzun vadeli yatirim icin uygun"
        elif len(puanlar) >= 3:
            sonuc["genel_degerlendirme"] = "IYI - Takip edilebilir"
        elif len(puanlar) >= 2:
            sonuc["genel_degerlendirme"] = "ORTA - Daha fazla analiz lazim"
        else:
            sonuc["genel_degerlendirme"] = "ZAYIF - Dikkatli olunmali"

        return sonuc

    except Exception as e:
        print(f"Temel analiz hatasi ({sembol}): {e}")
        return None


def portfoy_temel_analiz(portfoy_hisseler):
    """Tum portfoy icin temel analiz"""
    sonuclar = []
    for h in portfoy_hisseler:
        analiz = temel_analiz(h.get("sembol"))
        if analiz:
            analiz["adet"] = h.get("adet", 0)
            analiz["alis_fiyati"] = h.get("alis_fiyati", 0)
            sonuclar.append(analiz)
    return sonuclar
