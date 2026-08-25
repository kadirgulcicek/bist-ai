"""Tek hisse icin coklu kaynakli piyasa istihbarati analizi."""

import os
import re
from datetime import datetime

import feedparser
import numpy as np
import requests
import yfinance as yf


class PiyasaIstihbarati:
    """Teknik, hacim, haber ve opsiyonel kurum verisini birlestirir."""

    def __init__(self, sembol):
        self.sembol = str(sembol).upper().replace(".IS", "").strip()
        self.ticker = yf.Ticker(f"{self.sembol}.IS")

    def _fiyat_verisi(self):
        try:
            veri = self.ticker.history(period="1y", auto_adjust=True)
            if veri is None or len(veri) < 30 or "Close" not in veri.columns:
                return None
            return veri.dropna(subset=["Close"])
        except Exception:
            return None

    def teknik_analiz(self, veri):
        fiyat = veri["Close"].astype(float)
        son = float(fiyat.iloc[-1])
        ema21 = float(fiyat.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50 = float(fiyat.ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(fiyat.ewm(span=min(200, len(fiyat)), adjust=False).mean().iloc[-1])
        macd = fiyat.ewm(span=12, adjust=False).mean() - fiyat.ewm(span=26, adjust=False).mean()
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        delta = fiyat.diff()
        kazanc = delta.clip(lower=0).rolling(14).mean()
        kayip = -delta.clip(upper=0).rolling(14).mean()
        rsi = (100 - 100 / (1 + kazanc / kayip.replace(0, np.nan))).fillna(50)
        getiriler = fiyat.pct_change().dropna()
        hacim_orani = None
        if "Volume" in veri.columns:
            hacim = veri["Volume"].astype(float)
            ortalama_hacim = float(hacim.tail(20).mean())
            if ortalama_hacim > 0:
                hacim_orani = float(hacim.iloc[-1] / ortalama_hacim)

        skorlar = {
            "trend": 8 if son > ema21 > ema50 else 6 if son > ema50 else 3,
            "macd": 8 if macd.iloc[-1] > macd_signal.iloc[-1] else 3,
            "rsi": 8 if 30 <= rsi.iloc[-1] <= 70 else 5 if rsi.iloc[-1] < 30 else 2,
            "hacim": 8 if hacim_orani is not None and hacim_orani >= 1.2 else 6 if hacim_orani is not None else None,
        }
        mevcut_skorlar = [deger for deger in skorlar.values() if deger is not None]
        return {
            "fiyat": round(son, 2),
            "ema21": round(ema21, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "macd": round(float(macd.iloc[-1]), 3),
            "macd_sinyal": round(float(macd_signal.iloc[-1]), 3),
            "rsi": round(float(rsi.iloc[-1]), 2),
            "hacim_orani": round(hacim_orani, 2) if hacim_orani is not None else None,
            "volatilite": round(float(getiriler.tail(60).std() * np.sqrt(252) * 100), 2),
            "skor": round(sum(mevcut_skorlar) / len(mevcut_skorlar), 1) if mevcut_skorlar else None,
            "skorlar": skorlar,
            "veri_gun": len(veri),
            "kaynak": "Yahoo Finance",
        }

    def haber_analizi(self):
        """KAP ve Google News RSS basliklarindan acik duyarlilik sinyali cikarir."""
        kaynaklar = [
            "https://www.kap.org.tr/tr/rss/bildirim",
            f"https://news.google.com/rss/search?q={self.sembol}%20Borsa&hl=tr&gl=TR&ceid=TR:tr",
        ]
        yukselis = ("artış", "yükseliş", "rekor", "temettü", "kar", "anlaşma", "büyüme")
        dusus = ("düşüş", "gerileme", "zarar", "satış", "borç", "soruşturma")
        basliklar = []
        for kaynak in kaynaklar:
            try:
                akıs = feedparser.parse(kaynak)
                for kayit in akıs.entries[:10]:
                    baslik = re.sub(r"<[^>]+>", "", kayit.get("title", "")).strip()
                    if self.sembol.lower() in baslik.lower() or "borsa" in baslik.lower():
                        basliklar.append(baslik)
            except Exception:
                continue
        puan = 0
        for baslik in basliklar:
            metin = baslik.lower()
            puan += sum(metin.count(kelime) for kelime in yukselis)
            puan -= sum(metin.count(kelime) for kelime in dusus)
        return {
            "adet": len(basliklar),
            "net_sinyal": puan,
            "skor": round(max(0, min(10, 5 + puan)), 1) if basliklar else None,
            "basliklar": basliklar[:8],
            "kaynak": "KAP + Google News RSS",
        }

    def kurum_analizi(self):
        """Yahoo'nun acik kurumsal sahiplik alanini kullanir; takas degildir."""
        try:
            info = self.ticker.info
            sahiplik = info.get("institutionalPercentHeld")
            if sahiplik is None:
                return {"durum": "VERI YOK", "skor": None, "kaynak": "Yahoo Finance"}
            oran = float(sahiplik) * 100
            return {"durum": f"Kurumsal sahiplik %{oran:.2f}", "oran": round(oran, 2), "skor": 7 if oran >= 30 else 5, "kaynak": "Yahoo Finance"}
        except Exception:
            return {"durum": "VERI YOK", "skor": None, "kaynak": "Yahoo Finance"}

    def analiz_et(self):
        veri = self._fiyat_verisi()
        if veri is None:
            return {"sembol": self.sembol, "durum": "YETERLI VERI YOK", "veri_guveni": 0}
        teknik = self.teknik_analiz(veri)
        haber = self.haber_analizi()
        kurum = self.kurum_analizi()
        skorlar = [teknik["skor"]]
        if haber["skor"] is not None:
            skorlar.append(haber["skor"])
        if kurum["skor"] is not None:
            skorlar.append(kurum["skor"])
        agirlikli_skor = round(sum(skorlar) / len(skorlar), 1)
        return {
            "sembol": self.sembol,
            "durum": "POZITIF" if agirlikli_skor >= 6.5 else "NEGATIF" if agirlikli_skor <= 4 else "KARARSIZ",
            "skor": agirlikli_skor,
            "veri_guveni": round(len(skorlar) / 3 * 100),
            "teknik": teknik,
            "haber": haber,
            "kurum": kurum,
            "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "uyari": "Takas ve kademe verisi lisansli/API kaynagi olmadan gerceklesmez; bu alanlar tahmine katilmadi.",
        }


def hisse_istihbarat_analizi(sembol):
    return PiyasaIstihbarati(sembol).analiz_et()
