"""
Coklu Veri Kaynagi Modulu
Yahoo, IsYatirim, BigPara vb. kaynaklardan veri ceker
Hata durumunda alternatif kaynaga gecer
"""

import requests
import csv
from io import StringIO
import os
import sqlite3
from datetime import datetime, timedelta
from xml.etree import ElementTree

import pandas as pd

from tavan_modeli import tavan_fiyati


class VeriKaynaklari:
    def __init__(self):
        self.kaynaklar = ["yahoo", "isyatirim", "twelve_data", "stooq"]

    @staticmethod
    def _ozet(sembol, veri, kaynak):
        if veri is None or len(veri) < 2 or "Close" not in veri:
            return None
        kapanis = veri["Close"].dropna().astype(float)
        if len(kapanis) < 2 or kapanis.iloc[-1] <= 0 or kapanis.iloc[-2] <= 0:
            return None
        hacim = None
        if "Volume" in veri and pd.notna(veri["Volume"].iloc[-1]):
            hacim = float(veri["Volume"].iloc[-1])
        son_zaman = veri.index[-1]
        return {
            "sembol": sembol,
            "fiyat": float(kapanis.iloc[-1]),
            "gunluk": float((kapanis.iloc[-1] / kapanis.iloc[-2] - 1) * 100),
            "hacim": hacim,
            "veri_tarihi": son_zaman.date().isoformat() if hasattr(son_zaman, "date") else str(son_zaman),
            "kaynak": kaynak,
        }
    
    def yahoo_veri(self, sembol):
        """Yahoo Finance'den veri ceker"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(sembol + ".IS")
            veri = ticker.history(period="5d")
            
            if veri is None or len(veri) < 2:
                return None
            
            guncel = float(veri['Close'].iloc[-1])
            dun = float(veri['Close'].iloc[-2])
            
            if guncel != guncel or dun != dun or guncel <= 0:
                return None
            
            return {
                "sembol": sembol,
                "fiyat": guncel,
                "gunluk": ((guncel - dun) / dun) * 100,
                "kaynak": "Yahoo Finance"
            }
        except:
            return None

    @staticmethod
    def _baslangic_tarihi(periyot):
        gunler = {"1mo": 35, "3mo": 100, "6mo": 190, "1y": 370, "2y": 735}
        return datetime.now().date() - timedelta(days=gunler.get(periyot, 370))

    @staticmethod
    def _beklenen_son_islem_gunu():
        gun = datetime.now().date()
        while gun.weekday() >= 5:
            gun -= timedelta(days=1)
        return gun

    def yerel_tarihsel_veri(self, sembol, periyot="1y"):
        """Guncelse kalici SQLite deposundan gunluk OHLCV okur."""
        dosya = os.environ.get("PIYASA_VERI_DB", "data/piyasa_verileri.db")
        if not os.path.exists(dosya):
            return None
        try:
            from gunluk_veri_deposu import GunlukVeriDeposu

            veri = GunlukVeriDeposu(dosya).oku(
                sembol,
                baslangic=self._baslangic_tarihi(periyot).isoformat(),
            )
            if veri.empty or veri.index[-1].date() < self._beklenen_son_islem_gunu():
                return None
            return veri
        except (OSError, sqlite3.Error, ValueError):
            return None

    def yahoo_tarihsel_veri(self, sembol, periyot="1y", auto_adjust=False):
        try:
            import yfinance as yf
            veri = yf.Ticker(f"{sembol.upper().replace('.IS', '')}.IS").history(
                period=periyot,
                auto_adjust=auto_adjust,
            )
            if veri is None or len(veri) < 2 or "Close" not in veri:
                return None
            return veri.sort_index()
        except Exception:
            return None

    def yahoo_intraday_ozeti(self, sembol, aralik="5m"):
        """Ucretsiz bar verisinden intraday teyit uretir; emir defteri verisi uydurmaz."""
        if aralik not in {"5m", "15m"}:
            raise ValueError("Intraday aralik 5m veya 15m olmali")
        try:
            import yfinance as yf

            ticker = yf.Ticker(f"{sembol.upper().replace('.IS', '')}.IS")
            veri = ticker.history(period="5d", interval=aralik, auto_adjust=False)
            gunluk = ticker.history(period="10d", auto_adjust=False)
            gerekli = {"Open", "Close", "Volume"}
            if veri is None or veri.empty or not gerekli.issubset(veri.columns):
                return None
            veri = veri.dropna(subset=["Open", "Close"]).sort_index()
            gunluk = gunluk.dropna(subset=["Close"]).sort_index() if gunluk is not None else None
            if veri.empty or gunluk is None or len(gunluk) < 2:
                return None

            son_tarih = veri.index[-1].date()
            bugun = veri[[zaman.date() == son_tarih for zaman in veri.index]]
            onceki_gunler = [
                grup.iloc[:len(bugun)]
                for tarih, grup in veri.groupby([zaman.date() for zaman in veri.index])
                if tarih < son_tarih and not grup.empty
            ]
            bugun_hacim = float(bugun["Volume"].fillna(0).sum())
            onceki_hacimler = [float(grup["Volume"].fillna(0).sum()) for grup in onceki_gunler]
            ortalama_hacim = float(pd.Series(onceki_hacimler).mean()) if onceki_hacimler else 0.0
            yukari_hacim = float(
                bugun.loc[bugun["Close"] >= bugun["Open"], "Volume"].fillna(0).sum()
            )
            son_fiyat = float(bugun["Close"].iloc[-1])
            onceki_kapanislar = gunluk[gunluk.index.date < son_tarih]["Close"]
            if onceki_kapanislar.empty:
                return None
            baz_fiyat = float(onceki_kapanislar.iloc[-1])
            tavan = tavan_fiyati(baz_fiyat)
            momentum_15dk = (
                float(son_fiyat / bugun["Close"].iloc[-4] - 1) * 100
                if aralik == "5m" and len(bugun) >= 4 else
                float(son_fiyat / bugun["Open"].iloc[-1] - 1) * 100
            )
            return {
                "kaynak": "Yahoo Finance intraday",
                "aralik": aralik,
                "veri_zamani": veri.index[-1].isoformat(),
                "son_fiyat": round(son_fiyat, 4),
                "baz_fiyat": round(baz_fiyat, 4),
                "baz_fiyat_kaynagi": "onceki_kapanis_proxy",
                "tavan_fiyati": tavan,
                "tavana_mesafe": round((tavan / son_fiyat - 1) * 100, 2),
                "momentum_15dk": round(momentum_15dk, 2),
                "hacim_orani": round(bugun_hacim / ortalama_hacim, 2) if ortalama_hacim > 0 else None,
                "yukari_bar_hacim_orani": round(yukari_hacim / bugun_hacim * 100, 1) if bugun_hacim > 0 else None,
                "alis_satis_dengesi": None,
                "tavan_bekleyen_lot": None,
                "emir_defteri_mevcut": False,
            }
        except Exception:
            return None

    def isyatirim_tarihsel_veri(self, sembol, periyot="1y"):
        """Is Yatirim gunluk OHLCV verisini ortak kolon adlariyla dondurur."""
        try:
            bitis = datetime.now().date()
            response = requests.get(
                "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTekil",
                params={
                    "hisse": sembol.upper().replace(".IS", ""),
                    "startdate": self._baslangic_tarihi(periyot).strftime("%d-%m-%Y"),
                    "enddate": bitis.strftime("%d-%m-%Y"),
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=12,
            )
            response.raise_for_status()
            veri = pd.DataFrame(response.json().get("value", []))
            if veri.empty:
                return None
            veri = veri.rename(columns={
                "HGDG_TARIH": "Date",
                "HGDG_MAX": "High",
                "HGDG_MIN": "Low",
                "HGDG_KAPANIS": "Close",
                "HGDG_HACIM": "Volume",
            })
            gerekli = ["Date", "High", "Low", "Close", "Volume"]
            if any(kolon not in veri for kolon in gerekli):
                return None
            veri["Date"] = pd.to_datetime(veri["Date"], format="%d-%m-%Y", errors="coerce")
            for kolon in gerekli[1:]:
                veri[kolon] = pd.to_numeric(veri[kolon], errors="coerce")
            veri = veri.dropna(subset=["Date", "High", "Low", "Close"]).set_index("Date").sort_index()
            return veri[gerekli[1:]] if len(veri) >= 2 else None
        except (KeyError, TypeError, ValueError, requests.RequestException):
            return None

    def tarihsel_veri_al(self, sembol, periyot="1y", auto_adjust=False):
        """Guncel yerel depoyu ana, uzak servisleri yedek olarak kullanir."""
        veri = self.yerel_tarihsel_veri(sembol, periyot)
        if veri is not None:
            if auto_adjust and "Adj Close" in veri and veri["Adj Close"].notna().any():
                oran = veri["Adj Close"] / veri["Close"]
                for kolon in ("Open", "High", "Low", "Close"):
                    veri[kolon] = veri[kolon] * oran
            return veri, {"kaynak": "Yerel SQLite", "yedek_kullanildi": False}
        veri = self.yahoo_tarihsel_veri(sembol, periyot, auto_adjust)
        if veri is not None:
            return veri, {"kaynak": "Yahoo Finance", "yedek_kullanildi": False}
        veri = self.isyatirim_tarihsel_veri(sembol, periyot)
        if veri is not None:
            return veri, {"kaynak": "Is Yatirim", "yedek_kullanildi": True}
        return None, {"kaynak": None, "yedek_kullanildi": False, "uyari": "Gercek OHLCV verisi bulunamadi"}

    @staticmethod
    def kaynak_uyumu(ana_fiyat, teyit_fiyati, tolerans_yuzde=0.5):
        if not ana_fiyat or not teyit_fiyati:
            return {"teyit_edildi": False, "sapma_yuzde": None, "uyari": "Teyit verisi bulunamadi"}
        sapma = abs(float(ana_fiyat) / float(teyit_fiyati) - 1) * 100
        return {
            "teyit_edildi": sapma <= tolerans_yuzde,
            "sapma_yuzde": round(sapma, 3),
            "uyari": None if sapma <= tolerans_yuzde else "Kaynaklar arasi fiyat farki yuksek",
        }

    def isyatirim_veri(self, sembol):
        """Is Yatirim'in halka acik servisinden son gunluk verileri ceker."""
        return self._ozet(sembol, self.isyatirim_tarihsel_veri(sembol, "1mo"), "Is Yatirim")
    
    def mynet_veri(self, sembol):
        """Mynet Finans'tan veri ceker"""
        try:
            url = f"https://finans.mynet.com/borsa/hisse-detay/{sembol.lower()}/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            
            # Basit parsing (gercek implementasyon daha karmasik)
            # Simdilik None dondur
            return None
        except:
            return None

    def stooq_veri(self, sembol):
        """Stooq uzerinden ucretsiz gecikmeli gunluk veri ceker."""
        try:
            url = f"https://stooq.com/q/d/l/?s={sembol.lower()}.tr&i=d"
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            if "csv" not in response.headers.get("Content-Type", "").lower():
                return None
            satirlar = list(csv.DictReader(StringIO(response.text)))
            if len(satirlar) < 2:
                return None
            son = float(satirlar[-1]["Close"])
            onceki = float(satirlar[-2]["Close"])
            if son <= 0 or onceki <= 0:
                return None
            return {"sembol": sembol, "fiyat": son, "gunluk": (son / onceki - 1) * 100, "kaynak": "Stooq"}
        except (KeyError, ValueError, requests.RequestException):
            return None

    def twelve_data_veri(self, sembol):
        """Twelve Data ucretsiz kotasi varsa gunluk veri ceker."""
        api_anahtari = os.environ.get("TWELVE_DATA_API_KEY")
        if not api_anahtari:
            return None
        try:
            response = requests.get(
                "https://api.twelvedata.com/time_series",
                params={"symbol": f"{sembol}:BIST", "interval": "1day", "outputsize": 2, "apikey": api_anahtari},
                timeout=8,
            )
            veriler = response.json().get("values", [])
            if len(veriler) < 2:
                return None
            son, onceki = float(veriler[0]["close"]), float(veriler[1]["close"])
            return {"sembol": sembol, "fiyat": son, "gunluk": (son / onceki - 1) * 100, "kaynak": "Twelve Data"}
        except (KeyError, TypeError, ValueError, requests.RequestException):
            return None
        except:
            return None
    
    def bigpara_veri(self, sembol):
        """BigPara'dan veri ceker"""
        try:
            url = f"https://bigpara.hurriyet.com.tr/borsa/hisse-detay/{sembol}/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            return None  # Simdilik None
        except:
            return None
    
    def guvenli_veri_al(self, sembol):
        """Dogrulanmis kaynaklari sirayla dener; veri yoksa None dondurur."""
        for kaynak in (
            self.yahoo_veri,
            self.isyatirim_veri,
            self.twelve_data_veri,
            self.stooq_veri,
        ):
            veri = kaynak(sembol)
            if veri:
                return veri
        return None


# Kolay kullanım fonksiyonu
def hisse_veri_al(sembol):
    """Tek bir hisseden veri almak icin kisa fonksiyon"""
    vk = VeriKaynaklari()
    return vk.guvenli_veri_al(sembol)


_TCMB_CACHE = {"tarih": None, "veri": None}


def tcmb_piyasa_rejimi():
    """TCMB resmi XML kaynagindan USD/EUR seviyelerini gunde bir kez alir."""
    bugun = datetime.now().date().isoformat()
    if _TCMB_CACHE["tarih"] == bugun:
        return _TCMB_CACHE["veri"]
    try:
        response = requests.get("https://www.tcmb.gov.tr/kurlar/today.xml", timeout=8)
        response.raise_for_status()
        kok = ElementTree.fromstring(response.content)
        kurlar = {}
        for kod in ("USD", "EUR"):
            dugum = kok.find(f".//Currency[@CurrencyCode='{kod}']")
            alis = dugum.findtext("ForexBuying") if dugum is not None else None
            if alis:
                kurlar[kod] = float(alis)
        sonuc = {
            "tarih": kok.attrib.get("Tarih"),
            "usd_try": kurlar.get("USD"),
            "eur_try": kurlar.get("EUR"),
            "kaynak": "TCMB",
        } if len(kurlar) == 2 else None
    except (ElementTree.ParseError, TypeError, ValueError, requests.RequestException):
        sonuc = None
    _TCMB_CACHE.update({"tarih": bugun, "veri": sonuc})
    return sonuc
