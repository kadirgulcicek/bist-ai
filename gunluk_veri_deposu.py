"""BIST gunluk OHLCV verisini artimli olarak SQLite'ta saklar."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable

import pandas as pd
import yfinance as yf


VARSAYILAN_DB = os.environ.get("PIYASA_VERI_DB", "data/piyasa_verileri.db")
VARSAYILAN_BASLANGIC = "2015-01-01"
OHLCV_KOLONLARI = ("Open", "High", "Low", "Close", "Volume")


class GunlukVeriDeposu:
    def __init__(self, dosya: str | Path = VARSAYILAN_DB):
        self.dosya = Path(dosya)
        self.dosya.parent.mkdir(parents=True, exist_ok=True)
        self._sema_olustur()

    def _baglan(self) -> sqlite3.Connection:
        baglanti = sqlite3.connect(self.dosya, timeout=30)
        baglanti.execute("PRAGMA journal_mode=WAL")
        baglanti.execute("PRAGMA foreign_keys=ON")
        return baglanti

    def _sema_olustur(self) -> None:
        with self._baglan() as baglanti:
            baglanti.executescript("""
                CREATE TABLE IF NOT EXISTS gunluk_fiyat (
                    sembol TEXT NOT NULL,
                    tarih TEXT NOT NULL,
                    acilis REAL NOT NULL,
                    yuksek REAL NOT NULL,
                    dusuk REAL NOT NULL,
                    kapanis REAL NOT NULL,
                    duzeltilmis_kapanis REAL,
                    hacim INTEGER NOT NULL DEFAULT 0,
                    temettu REAL NOT NULL DEFAULT 0,
                    bolunme REAL NOT NULL DEFAULT 0,
                    kaynak TEXT NOT NULL,
                    guncelleme_zamani TEXT NOT NULL,
                    PRIMARY KEY (sembol, tarih)
                );
                CREATE INDEX IF NOT EXISTS idx_gunluk_fiyat_tarih
                    ON gunluk_fiyat (tarih);
                CREATE TABLE IF NOT EXISTS veri_akisi_calisma (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    baslama_zamani TEXT NOT NULL,
                    bitis_zamani TEXT,
                    durum TEXT NOT NULL,
                    sembol_sayisi INTEGER NOT NULL,
                    basarili_sembol INTEGER NOT NULL DEFAULT 0,
                    basarisiz_sembol INTEGER NOT NULL DEFAULT 0,
                    kaydedilen_satir INTEGER NOT NULL DEFAULT 0,
                    hata_ozeti TEXT
                );
            """)

    @staticmethod
    def _sembol(sembol: str) -> str:
        return str(sembol or "").strip().upper().replace(".IS", "")

    @staticmethod
    def _tarih(zaman: Any) -> str | None:
        try:
            damga = pd.Timestamp(zaman)
            if pd.isna(damga):
                return None
            return damga.date().isoformat()
        except (TypeError, ValueError):
            return None

    def son_tarih(self, sembol: str) -> str | None:
        with self._baglan() as baglanti:
            satir = baglanti.execute(
                "SELECT MAX(tarih) FROM gunluk_fiyat WHERE sembol = ?",
                (self._sembol(sembol),),
            ).fetchone()
        return satir[0] if satir and satir[0] else None

    def sonraki_islem_tarihi(self, tarih: str) -> str | None:
        with self._baglan() as baglanti:
            satir = baglanti.execute(
                "SELECT MIN(tarih) FROM gunluk_fiyat WHERE tarih > ?",
                (str(tarih),),
            ).fetchone()
        return satir[0] if satir and satir[0] else None

    def kaydet(self, sembol: str, veri: pd.DataFrame, kaynak: str) -> dict[str, int]:
        sembol = self._sembol(sembol)
        alindi = 0 if veri is None else len(veri)
        if not sembol or veri is None or veri.empty:
            return {"alindi": alindi, "kaydedildi": 0, "reddedildi": alindi}
        if any(kolon not in veri.columns for kolon in OHLCV_KOLONLARI):
            return {"alindi": alindi, "kaydedildi": 0, "reddedildi": alindi}

        simdi = datetime.now().isoformat(timespec="seconds")
        satirlar = []
        for zaman, satir in veri.sort_index().iterrows():
            tarih = self._tarih(zaman)
            try:
                acilis = float(satir["Open"])
                yuksek = float(satir["High"])
                dusuk = float(satir["Low"])
                kapanis = float(satir["Close"])
                hacim = max(0, int(float(satir["Volume"]))) if pd.notna(satir["Volume"]) else 0
            except (TypeError, ValueError, OverflowError):
                continue
            fiyatlar = (acilis, yuksek, dusuk, kapanis)
            if not tarih or any(not pd.notna(fiyat) or fiyat <= 0 for fiyat in fiyatlar):
                continue
            if yuksek < max(acilis, dusuk, kapanis) or dusuk > min(acilis, yuksek, kapanis):
                continue
            duzeltilmis = satir.get("Adj Close")
            duzeltilmis = float(duzeltilmis) if pd.notna(duzeltilmis) else None
            temettu = satir.get("Dividends", 0)
            bolunme = satir.get("Stock Splits", 0)
            satirlar.append((
                sembol, tarih, acilis, yuksek, dusuk, kapanis, duzeltilmis, hacim,
                float(temettu) if pd.notna(temettu) else 0.0,
                float(bolunme) if pd.notna(bolunme) else 0.0,
                kaynak, simdi,
            ))

        if satirlar:
            with self._baglan() as baglanti:
                baglanti.executemany("""
                    INSERT INTO gunluk_fiyat (
                        sembol, tarih, acilis, yuksek, dusuk, kapanis,
                        duzeltilmis_kapanis, hacim, temettu, bolunme, kaynak, guncelleme_zamani
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sembol, tarih) DO UPDATE SET
                        acilis=excluded.acilis,
                        yuksek=excluded.yuksek,
                        dusuk=excluded.dusuk,
                        kapanis=excluded.kapanis,
                        duzeltilmis_kapanis=excluded.duzeltilmis_kapanis,
                        hacim=excluded.hacim,
                        temettu=excluded.temettu,
                        bolunme=excluded.bolunme,
                        kaynak=excluded.kaynak,
                        guncelleme_zamani=excluded.guncelleme_zamani
                """, satirlar)
        return {
            "alindi": alindi,
            "kaydedildi": len(satirlar),
            "reddedildi": alindi - len(satirlar),
        }

    def oku(self, sembol: str, baslangic: str | None = None, bitis: str | None = None) -> pd.DataFrame:
        sorgu = """
            SELECT tarih, acilis, yuksek, dusuk, kapanis, duzeltilmis_kapanis,
                   hacim, temettu, bolunme
            FROM gunluk_fiyat WHERE sembol = ?
        """
        parametreler: list[Any] = [self._sembol(sembol)]
        if baslangic:
            sorgu += " AND tarih >= ?"
            parametreler.append(str(baslangic))
        if bitis:
            sorgu += " AND tarih <= ?"
            parametreler.append(str(bitis))
        sorgu += " ORDER BY tarih"
        with self._baglan() as baglanti:
            veri = pd.read_sql_query(sorgu, baglanti, params=parametreler)
        if veri.empty:
            return pd.DataFrame(columns=[*OHLCV_KOLONLARI, "Adj Close", "Dividends", "Stock Splits"])
        veri = veri.rename(columns={
            "tarih": "Date", "acilis": "Open", "yuksek": "High", "dusuk": "Low",
            "kapanis": "Close", "duzeltilmis_kapanis": "Adj Close", "hacim": "Volume",
            "temettu": "Dividends", "bolunme": "Stock Splits",
        })
        veri["Date"] = pd.to_datetime(veri["Date"])
        return veri.set_index("Date")

    @staticmethod
    def yahoo_indir(sembol: str, baslangic: str, bitis: str) -> pd.DataFrame:
        return yf.Ticker(f"{sembol}.IS").history(
            start=baslangic,
            end=bitis,
            auto_adjust=False,
            actions=True,
        )

    def guncelle(
        self,
        semboller: Iterable[str],
        baslangic: str = VARSAYILAN_BASLANGIC,
        bitis: str | None = None,
        indirici: Callable[[str, str, str], pd.DataFrame] | None = None,
        max_calisan: int = 6,
    ) -> dict[str, Any]:
        temiz = sorted({self._sembol(sembol) for sembol in semboller if self._sembol(sembol)})
        bitis = bitis or (date.today() + timedelta(days=1)).isoformat()
        indirici = indirici or self.yahoo_indir
        baslama_zamani = datetime.now().isoformat(timespec="seconds")
        with self._baglan() as baglanti:
            calisma_id = baglanti.execute("""
                INSERT INTO veri_akisi_calisma (baslama_zamani, durum, sembol_sayisi)
                VALUES (?, 'CALISIYOR', ?)
            """, (baslama_zamani, len(temiz))).lastrowid

        def al(sembol: str) -> tuple[str, pd.DataFrame]:
            son = self.son_tarih(sembol)
            return sembol, indirici(sembol, son or baslangic, bitis)

        indirilenler: dict[str, pd.DataFrame] = {}
        hatalar: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=max(1, min(max_calisan, len(temiz) or 1))) as havuz:
            gorevler = {havuz.submit(al, sembol): sembol for sembol in temiz}
            for gorev in as_completed(gorevler):
                sembol = gorevler[gorev]
                try:
                    _, veri = gorev.result()
                    if veri is None or veri.empty:
                        hatalar[sembol] = "Veri bulunamadi"
                    else:
                        indirilenler[sembol] = veri
                except Exception as hata:
                    hatalar[sembol] = str(hata)[:300]

        kaydedilen = 0
        basarili = 0
        for sembol, veri in indirilenler.items():
            sonuc = self.kaydet(sembol, veri, "Yahoo Finance")
            if sonuc["kaydedildi"]:
                basarili += 1
                kaydedilen += sonuc["kaydedildi"]
            else:
                hatalar[sembol] = "Gecerli OHLCV satiri bulunamadi"

        bitis_zamani = datetime.now().isoformat(timespec="seconds")
        durum = "TAMAMLANDI" if not hatalar else "KISMI" if basarili else "BASARISIZ"
        with self._baglan() as baglanti:
            baglanti.execute("""
                UPDATE veri_akisi_calisma SET bitis_zamani=?, durum=?, basarili_sembol=?,
                    basarisiz_sembol=?, kaydedilen_satir=?, hata_ozeti=? WHERE id=?
            """, (
                bitis_zamani, durum, basarili, len(hatalar), kaydedilen,
                json.dumps(hatalar, ensure_ascii=False) if hatalar else None, calisma_id,
            ))
        return {
            "durum": durum,
            "sembol_sayisi": len(temiz),
            "basarili_sembol": basarili,
            "basarisiz_sembol": len(hatalar),
            "kaydedilen_satir": kaydedilen,
            "hatalar": hatalar,
            "veritabani": str(self.dosya),
        }


def sembolleri_yukle(dosya: str | Path) -> list[str]:
    veri = json.loads(Path(dosya).read_text(encoding="utf-8"))
    if not isinstance(veri, list):
        raise ValueError("Sembol dosyasi JSON listesi olmali")
    return [str(sembol).upper().replace(".IS", "") for sembol in veri if sembol]


def main() -> None:
    parser = argparse.ArgumentParser(description="BIST gunluk OHLCV veri deposunu guncelle")
    parser.add_argument("--db", default=VARSAYILAN_DB)
    parser.add_argument("--semboller", default="bist_sembol_cache.json")
    parser.add_argument("--baslangic", default=VARSAYILAN_BASLANGIC)
    parser.add_argument("--bitis", default=None, help="Yahoo icin haric bitis tarihi (YYYY-AA-GG)")
    parser.add_argument("--max-calisan", type=int, default=6)
    args = parser.parse_args()
    depo = GunlukVeriDeposu(args.db)
    sonuc = depo.guncelle(
        sembolleri_yukle(args.semboller),
        baslangic=args.baslangic,
        bitis=args.bitis,
        max_calisan=args.max_calisan,
    )
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    if sonuc["durum"] == "BASARISIZ":
        raise SystemExit(1)


if __name__ == "__main__":
    main()