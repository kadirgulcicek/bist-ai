"""OpenAI destekli sinyal ve portfoy yorumlari."""

from __future__ import annotations

import os
import time
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
_CACHE_TTL = 900
_cache: dict[str, tuple[float, str]] = {}


def getir_openai_client():
    """OPENAI_API_KEY ortam degiskeni varsa istemciyi dondurur."""
    if OpenAI is None:
        return None
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key, timeout=15, max_retries=1)
    except Exception:
        return None


def _fallback_yorum(sembol: str, bilgi: dict[str, Any]) -> str:
    karar = bilgi.get("karar", "BEKLE")
    sebepler = [str(s) for s in bilgi.get("sebepler", [])[:5]]
    fiyat = bilgi.get("fiyat", "Veri yok")
    rsi = bilgi.get("rsi", "N/A")
    rsi_yorum = bilgi.get("rsi_yorum", "N/A")
    macd = bilgi.get("macd", "N/A")
    macd_yorum = bilgi.get("macd_yorum", "N/A")
    adx = bilgi.get("adx", "N/A")
    adx_yorum = bilgi.get("adx_yorum", "N/A")
    metin = (
        f"{sembol} TEKNIK ANALIZ RAPORU\n"
        f"KARAR OZETI: {karar} | Oncelik: {bilgi.get('oncelik', 'DUSUK')} | Fiyat: {fiyat} TL\n\n"
        "MOMENTUM VE TREND\n"
        f"RSI(14): {rsi} ({rsi_yorum}). MACD: {macd} ({macd_yorum}); histogram: {bilgi.get('macd_histogram', 'N/A')}. "
        f"ADX: {adx} ({adx_yorum}). Gunluk degisim: %{bilgi.get('degisim_yuzde', 'N/A')}.\n"
        f"Hareketli ortalamalar MA5/MA20/MA50/MA200: {bilgi.get('ma5', 'N/A')} / {bilgi.get('ma20', 'N/A')} / "
        f"{bilgi.get('ma50', 'N/A')} / {bilgi.get('ma200', 'N/A')} TL. {bilgi.get('cross_yorum', 'N/A')}.\n\n"
        "BANT VE OSILATORLER\n"
        f"Bollinger alt/orta/ust: {bilgi.get('bollinger_alt', 'N/A')} / {bilgi.get('bollinger_orta', 'N/A')} / "
        f"{bilgi.get('bollinger_ust', 'N/A')} TL; konum: {bilgi.get('bollinger_pozisyon', 'N/A')} "
        f"({bilgi.get('bollinger_yorum', 'N/A')}). Stochastic: {bilgi.get('stochastic', 'N/A')} "
        f"({bilgi.get('stochastic_yorum', 'N/A')}). Williams %R: {bilgi.get('williams', 'N/A')} "
        f"({bilgi.get('williams_yorum', 'N/A')}). CCI: {bilgi.get('cci', 'N/A')} ({bilgi.get('cci_yorum', 'N/A')}).\n\n"
        "SEVIYELER VE RISK\n"
        f"Destekler: {bilgi.get('destekler', []) or 'Veri yok'} | Direncler: {bilgi.get('direncler', []) or 'Veri yok'}.\n"
        f"20 gunluk yuksek/dusuk: {bilgi.get('yuksek_20', 'N/A')} / {bilgi.get('dusuk_20', 'N/A')} TL. "
        f"Volatilite: %{bilgi.get('volatilite', 'N/A')} | ATR: {bilgi.get('atr', 'N/A')} TL | "
        f"Hacim orani: {bilgi.get('hacim_orani', 'N/A')}x.\n\n"
        f"SINYAL GEREKCELERI: {', '.join(sebepler) if sebepler else 'Ek gerekce tespit edilmedi.'}\n"
        f"FORMASYONLAR: {', '.join(bilgi.get('formasyonlar', [])) or 'Tespit edilmedi.'}\n\n"
        "DEGERLENDIRME: Gosterge verileri birlikte okunmali; tek bir indikatore gore islem yapilmamali. "
        "Fiyat destek altina inerse risk artar, direnç uzerinde kalicilik momentumun guclendigini gosterebilir. "
        "Bu rapor yatirim tavsiyesi degildir; pozisyon boyutu, zarar durdur ve kendi arastirmaniz birlikte degerlendirilmelidir."
    )
    return metin


def sinyal_yorumla(sembol: str, sinyal_bilgileri: dict[str, Any]) -> str:
    """Bir sinyali teknik gostergelerle zenginlestirip Turkce aciklar."""
    try:
        from teknik_gostergeler import tum_gostergeleri_al
        zengin_veri = tum_gostergeleri_al(sembol)
        if zengin_veri:
            sinyal_bilgileri = {**sinyal_bilgileri, **zengin_veri}
    except Exception:
        pass
    client = getir_openai_client()
    if client is None:
        return _fallback_yorum(sembol, sinyal_bilgileri)

    veri = {
        "sembol": sembol,
        "karar": sinyal_bilgileri.get("karar", "BELIRSIZ"),
        "oncelik": sinyal_bilgileri.get("oncelik", "DUSUK"),
        "fiyat": sinyal_bilgileri.get("fiyat", 0),
        "rsi": sinyal_bilgileri.get("rsi", "N/A"),
        "macd": sinyal_bilgileri.get("macd", "N/A"),
        "adx": sinyal_bilgileri.get("adx", "N/A"),
        "stoch": sinyal_bilgileri.get("stoch", "N/A"),
        "cci": sinyal_bilgileri.get("cci", "N/A"),
        "williams": sinyal_bilgileri.get("williams", "N/A"),
        "bb_pos": sinyal_bilgileri.get("bb_pos", "N/A"),
        "al_puan": sinyal_bilgileri.get("al_puan", "N/A"),
        "sat_puan": sinyal_bilgileri.get("sat_puan", "N/A"),
        "formasyonlar": sinyal_bilgileri.get("formasyonlar", []),
        "sebepler": sinyal_bilgileri.get("sebepler", []),
        "rsi_yorum": sinyal_bilgileri.get("rsi_yorum", "N/A"),
        "macd_histogram": sinyal_bilgileri.get("macd_histogram", "N/A"),
        "macd_yorum": sinyal_bilgileri.get("macd_yorum", "N/A"),
        "bollinger": {
            "alt": sinyal_bilgileri.get("bollinger_alt", "N/A"),
            "orta": sinyal_bilgileri.get("bollinger_orta", "N/A"),
            "ust": sinyal_bilgileri.get("bollinger_ust", "N/A"),
            "pozisyon": sinyal_bilgileri.get("bollinger_pozisyon", "N/A"),
            "yorum": sinyal_bilgileri.get("bollinger_yorum", "N/A"),
        },
        "stochastic_yorum": sinyal_bilgileri.get("stochastic_yorum", "N/A"),
        "cci": sinyal_bilgileri.get("cci", "N/A"),
        "cci_yorum": sinyal_bilgileri.get("cci_yorum", "N/A"),
        "williams_yorum": sinyal_bilgileri.get("williams_yorum", "N/A"),
        "adx_yorum": sinyal_bilgileri.get("adx_yorum", "N/A"),
        "degisim_yuzde": sinyal_bilgileri.get("degisim_yuzde", "N/A"),
        "ma5": sinyal_bilgileri.get("ma5", "N/A"),
        "ma20": sinyal_bilgileri.get("ma20", "N/A"),
        "ma50": sinyal_bilgileri.get("ma50", "N/A"),
        "ma200": sinyal_bilgileri.get("ma200", "N/A"),
        "cross_yorum": sinyal_bilgileri.get("cross_yorum", "N/A"),
        "destekler": sinyal_bilgileri.get("destekler", []),
        "direncler": sinyal_bilgileri.get("direncler", []),
        "volatilite": sinyal_bilgileri.get("volatilite", "N/A"),
        "atr": sinyal_bilgileri.get("atr", "N/A"),
        "hacim_orani": sinyal_bilgileri.get("hacim_orani", "N/A"),
        "formasyonlar": sinyal_bilgileri.get("formasyonlar", []),
    }
    anahtar = repr(sorted(veri.items()))
    kayit = _cache.get(anahtar)
    if kayit and time.time() - kayit[0] < _CACHE_TTL:
        return kayit[1]

    prompt = (
        "BIST sinyalini Turkce, detayli ama anlasilir bir mini rapor olarak acikla. "
        "Tam olarak su basliklari kullan ve her baslik altinda 1-2 cümle yaz:\n"
        "KARAR OZETI:\nTEKNIK GEREKCELER:\nRISKLER:\nIZLENECEK SEVIYELER:\nSONUC:\n"
        "RSI, MACD histogrami, Bollinger bantlari, Stochastic, Williams %R, ADX, hareketli ortalamalar, "
        "destek/direnc, ATR, volatilite, hacim ve formasyonlari "
        "veri varsa yorumla. Fiyat hedefi veya kesin kazanc vaadi verme; bunun yatirim tavsiyesi olmadigini belirt. Veriler: " + repr(veri)
    )
    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "Kisa, tarafsiz ve Turkce finansal aciklama yaz."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        yorum = (response.choices[0].message.content or "").strip()
        if yorum:
            _cache[anahtar] = (time.time(), yorum)
            return yorum
    except Exception:
        pass
    return _fallback_yorum(sembol, sinyal_bilgileri)


def portfoy_analiz_et(portfoy_hisseler: list[dict[str, Any]]) -> str:
    """Portfoy icin OpenAI yorumu veya anahtarsiz fallback dondurur."""
    if not portfoy_hisseler:
        return "Portfoyde henuz hisse bulunmuyor."
    client = getir_openai_client()
    if client is None:
        return f"Portfoyunuzde {len(portfoy_hisseler)} hisse var. Cesitlendirme, risk limiti ve pozisyon buyuklugunu birlikte takip edin."
    detaylar = []
    for hisse in portfoy_hisseler:
        try:
            from teknik_gostergeler import tum_gostergeleri_al
            gosterge = tum_gostergeleri_al(hisse.get("sembol", "")) or {}
        except Exception:
            gosterge = {}
        detaylar.append({
            "sembol": hisse.get("sembol", ""),
            "adet": hisse.get("adet", 0),
            "alis": hisse.get("alis_fiyati", 0),
            "fiyat": gosterge.get("fiyat", "N/A"),
            "rsi": gosterge.get("rsi", "N/A"),
            "macd": gosterge.get("macd_yorum", "N/A"),
            "adx": gosterge.get("adx", "N/A"),
            "volatilite": gosterge.get("volatilite", "N/A"),
        })
    ozet = repr(detaylar)
    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": "Turkce, tarafsiz ve kisa portfoy risk yorumu yaz."},
                {"role": "user", "content": f"Portfoyu; her hissenin teknik durumu, toplam risk, cesitlendirme ve izlenecek riskleriyle 4-5 kisa paragrafta degerlendir. Kesin yatirim tavsiyesi verme: {ozet}"},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip() or "Portfoy yorumu uretilemedi."
    except Exception:
        return f"Portfoyunuzde {len(portfoy_hisseler)} hisse var. Cesitlendirme ve risk limitlerini kontrol edin."


def hedef_fiyat_yorumla(sembol: str, mevcut: float, hedef: float, zaman_gun: int) -> str | None:
    """Hedef fiyati teknik seviyelerle tarafsiz yorumlar."""
    client = getir_openai_client()
    if client is None:
        return None
    try:
        from teknik_gostergeler import tum_gostergeleri_al
        gosterge = tum_gostergeleri_al(sembol)
        if not gosterge or not mevcut:
            return None
        degisim = (hedef - mevcut) / mevcut * 100
        prompt = (
            f"BIST hedef fiyatini Turkce 4 kisa maddede analiz et: {sembol}, mevcut {mevcut} TL, "
            f"hedef {hedef} TL, sure {zaman_gun} gun, hedef degisimi %{degisim:.1f}. "
            f"RSI {gosterge['rsi']} ({gosterge['rsi_yorum']}), MACD {gosterge['macd_yorum']}, "
            f"ADX {gosterge['adx']} ({gosterge['adx_yorum']}), destekler {gosterge['destekler']}, "
            f"direncler {gosterge['direncler']}. Ulasilabilirlik, engeller, risk ve izlenecek stop seviyesini yaz; "
            "kesin kazanc veya yatirim tavsiyesi verme."
        )
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "system", "content": "Tarafsiz ve profesyonel Turkce BIST analisti."}, {"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip() or None
    except Exception:
        return None
