"""KAP bildirimlerini resmi sorgu API'sinden alip SQLite'ta saklar."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
from zoneinfo import ZoneInfo

import requests

from gunluk_veri_deposu import VARSAYILAN_DB


KAP_API = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
KAP_SAYFA_SINIRI = 2000
HTTP_TIMEOUT = (5, 30)


def _istek_govdesi(baslangic: date, bitis: date) -> dict[str, Any]:
    return {
        "fromDate": baslangic.isoformat(), "toDate": bitis.isoformat(),
        "memberType": "IGS", "mkkMemberOidList": [], "inactiveMkkMemberOidList": [],
        "disclosureClass": "", "subjectList": [], "isLate": "", "mainSector": "",
        "sector": "", "subSector": "", "marketOid": "", "index": "",
        "bdkReview": "", "bdkMemberOidList": [], "year": "", "term": "",
        "ruleType": "", "period": "", "fromSrc": False, "srcCategory": "",
        "disclosureIndexList": [],
    }


def _semboller(kayit: dict[str, Any]) -> list[str]:
    metin = " ".join(str(kayit.get(alan) or "") for alan in ("stockCodes", "relatedStocks"))
    return sorted(set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", metin.upper())))


class KapVeriDeposu:
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
                CREATE TABLE IF NOT EXISTS kap_bildirim (
                    bildirim_id INTEGER PRIMARY KEY,
                    yayin_zamani TEXT NOT NULL,
                    alinma_zamani TEXT NOT NULL,
                    baslik TEXT NOT NULL,
                    konu TEXT NOT NULL,
                    gecikmeli INTEGER NOT NULL DEFAULT 0,
                    kaynak TEXT NOT NULL,
                    ham_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kap_bildirim_sembol (
                    bildirim_id INTEGER NOT NULL,
                    sembol TEXT NOT NULL,
                    PRIMARY KEY (bildirim_id, sembol),
                    FOREIGN KEY (bildirim_id) REFERENCES kap_bildirim (bildirim_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_kap_bildirim_yayin
                    ON kap_bildirim (yayin_zamani);
                CREATE INDEX IF NOT EXISTS idx_kap_sembol
                    ON kap_bildirim_sembol (sembol, bildirim_id);
            """)

    @staticmethod
    def _yayin_zamani(kayit: dict[str, Any]) -> str:
        zaman = datetime.strptime(str(kayit["publishDate"]), "%d.%m.%Y %H:%M:%S")
        return zaman.replace(tzinfo=ZoneInfo("Europe/Istanbul")).isoformat()

    def kaydet(self, kayitlar: list[dict[str, Any]]) -> dict[str, int]:
        alinma = datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(timespec="seconds")
        bildirimler = []
        semboller = []
        reddedilen = 0
        for kayit in kayitlar:
            try:
                bildirim_id = int(kayit["disclosureIndex"])
                bildirimler.append((
                    bildirim_id, self._yayin_zamani(kayit), alinma,
                    str(kayit.get("kapTitle") or ""), str(kayit.get("subject") or ""),
                    int(bool(kayit.get("isLate"))), "KAP",
                    json.dumps(kayit, ensure_ascii=False, sort_keys=True),
                ))
                semboller.extend((bildirim_id, sembol) for sembol in _semboller(kayit))
            except (KeyError, TypeError, ValueError):
                reddedilen += 1
        with self._baglan() as baglanti:
            baglanti.executemany("""
                INSERT INTO kap_bildirim (
                    bildirim_id, yayin_zamani, alinma_zamani, baslik, konu,
                    gecikmeli, kaynak, ham_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bildirim_id) DO UPDATE SET
                    yayin_zamani=excluded.yayin_zamani,
                    alinma_zamani=excluded.alinma_zamani,
                    baslik=excluded.baslik,
                    konu=excluded.konu,
                    gecikmeli=excluded.gecikmeli,
                    ham_json=excluded.ham_json
            """, bildirimler)
            baglanti.executemany(
                "INSERT OR IGNORE INTO kap_bildirim_sembol (bildirim_id, sembol) VALUES (?, ?)",
                semboller,
            )
        return {"bildirim": len(bildirimler), "sembol_eslesmesi": len(semboller), "reddedilen": reddedilen}

    def son_tarih(self) -> date | None:
        with self._baglan() as baglanti:
            satir = baglanti.execute("SELECT MAX(yayin_zamani) FROM kap_bildirim").fetchone()
        return date.fromisoformat(satir[0][:10]) if satir and satir[0] else None

    def indir(self, baslangic: date, bitis: date, oturum: Any = requests) -> list[dict[str, Any]]:
        cevap = oturum.post(
            KAP_API,
            json=_istek_govdesi(baslangic, bitis),
            headers={"Accept-Language": "tr", "User-Agent": "Mozilla/5.0"},
            timeout=HTTP_TIMEOUT,
        )
        cevap.raise_for_status()
        kayitlar = cevap.json()
        if not isinstance(kayitlar, list):
            raise ValueError("KAP API liste dondurmedi")
        if len(kayitlar) >= KAP_SAYFA_SINIRI and baslangic < bitis:
            orta = baslangic + timedelta(days=(bitis - baslangic).days // 2)
            return self.indir(baslangic, orta, oturum) + self.indir(orta + timedelta(days=1), bitis, oturum)
        if len(kayitlar) >= KAP_SAYFA_SINIRI:
            raise RuntimeError(f"KAP tek gun kaydi API sinirina ulasti: {baslangic}")
        return kayitlar

    def guncelle(self, baslangic: date | None = None, bitis: date | None = None) -> dict[str, int]:
        bitis = bitis or date.today()
        baslangic = baslangic or self.son_tarih() or (bitis - timedelta(days=7))
        if baslangic > bitis:
            return {"bildirim": 0, "sembol_eslesmesi": 0, "reddedilen": 0}
        return self.kaydet(self.indir(baslangic, bitis))


def main() -> None:
    parser = argparse.ArgumentParser(description="KAP bildirimlerini yerel SQLite deposuna aktarir")
    parser.add_argument("--db", default=VARSAYILAN_DB)
    parser.add_argument("--baslangic")
    parser.add_argument("--bitis")
    args = parser.parse_args()
    baslangic = date.fromisoformat(args.baslangic) if args.baslangic else None
    bitis = date.fromisoformat(args.bitis) if args.bitis else None
    print(json.dumps(KapVeriDeposu(args.db).guncelle(baslangic, bitis), ensure_ascii=False))


if __name__ == "__main__":
    main()