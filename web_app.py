from flask import (
    Flask,
    make_response,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    url_for,
)
import csv
import io
import os
import re
import time
import yfinance as yf
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from portfoy import Portfoy
from sektor_analiz import sektor_analiz_yap, HISSE_SEKTORLERI

try:
    from risk_gelismis import portfoy_risk_analiz as _portfoy_risk_analiz
    risk_modulu_yuklu = True
except ImportError:
    try:
        from risk_analiz import portfoy_risk_analizi as _portfoy_risk_analiz
        risk_modulu_yuklu = True
    except ImportError:
        _portfoy_risk_analiz = None
        risk_modulu_yuklu = False

from ensemble_model import EnsembleTahminci
from auth import KullaniciYoneticisi
from piyasa_istihbarati import hisse_istihbarat_analizi
from halka_arz import halka_arz_ozeti
from temel_analiz import temel_analiz
from teknik_analiz import hisse_teknik_analiz


def portfoy_risk_hesapla(portfoy_hisseler):
    """Web arayuzunde tek risk akisi."""
    if _portfoy_risk_analiz is not None:
        try:
            sonuc = _portfoy_risk_analiz(portfoy_hisseler)
            if sonuc:
                return sonuc
        except Exception:
            pass

    maliyet = sum(
        float(h.get("adet", 0)) * float(h.get("alis_fiyati", 0))
        for h in portfoy_hisseler
    )
    hisse_verileri = []
    for hisse in portfoy_hisseler:
        adet = int(hisse.get("adet", 0))
        fiyat = float(hisse.get("alis_fiyati", 0))
        hisse_verileri.append({
            "sembol": str(hisse.get("sembol", "")).upper(),
            "adet": adet,
            "maliyet": fiyat,
            "guncel": fiyat,
            "deger": adet * fiyat,
            "kar_yuzde": 0.0,
            "agirlik": round((adet * fiyat / maliyet) * 100, 2) if maliyet else 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "volatilite": 0.0,
            "beta": 1.0,
            "risk_skor": 5,
        })
    cesitlendirme = min(100, len(hisse_verileri) * 20)
    return {
        "hisse_verileri": hisse_verileri,
        "korelasyonlar": [],
        "toplam_deger": round(maliyet, 2),
        "toplam_maliyet": round(maliyet, 2),
        "toplam_kar": 0.0,
        "toplam_kar_yuzde": 0.0,
        "portfoy_sharpe": 0.0,
        "portfoy_volatilite": 0.0,
        "portfoy_var": 0.0,
        "portfoy_beta": 1.0,
        "cesitlendirme": cesitlendirme,
        "genel_risk": 50,
        "risk_seviye": "VERI YOK",
        "risk_renk": "#607d8b",
        "oneriler": ["Piyasa verisi alınamadı; temel portföy özeti gösteriliyor."],
        "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE', '0') == '1'
_istek_sayaci = {}
_veri_cache = {}


@app.after_request
def hamburger_menu_ekle(response):
    """Tum HTML sayfalarina ortak hamburger navigasyonu ekler."""
    if not response.content_type or "text/html" not in response.content_type:
        return response
    html = response.get_data(as_text=True)
    html = re.sub(
        r'<a\b[^>]*\bhref\s*=\s*["\']https?://(?:www\.)?halkarz\.com/[^"\']*["\'][^>]*>.*?</a>',
        '',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    menu_eslesmesi = re.search(r'<div class="menu">(.*?)</div>', html, flags=re.DOTALL)
    if menu_eslesmesi:
        aktif_yol = request.path
        menu_linkleri = (
            ("/", "Portfoy"), ("/panel", "Panel"), ("/sektor", "Sektor"),
            ("/risk", "Risk"), ("/teknik", "Teknik Analiz"), ("/temel", "Temel Analiz"), ("/ai", "Yapay Zeka"),
            ("/istihbarat", "Istihbarat"), ("/sinyal", "Sinyal"),
            ("/tarama", "Tarama"), ("/halka-arz", "Halka Arz"),
            ("/hedef", "Hedef"), ("/bildirim", "Bildirim"), ("/cikis", "Cikis"),
        )
        menu = "".join(
            f'<a href="{yol}"{(" class=\"active\"" if aktif_yol == yol else "")}>{etiket}</a>'
            for yol, etiket in menu_linkleri
        )
        html = html[:menu_eslesmesi.start(1)] + menu + html[menu_eslesmesi.end(1):]
    if '<div class="menu">' not in html:
        response.set_data(html)
        return response
    def header_saatini_canli_yap(eslesme):
        aktif_sayaci = eslesme.group(2) or ""
        return f'{eslesme.group(1)}<p class="canli-saat" aria-live="polite"></p>{aktif_sayaci}</div>'

    html = re.sub(
        r'(<div class="header">.*?</div>)<p>[^<]*?(\s*\|\s*\d+\s+aktif)?</p></div>',
        header_saatini_canli_yap,
        html,
        flags=re.DOTALL,
    )
    stil = """
<style>
:root{
  --bg: #07111f;
  --bg-soft: #0f1d2c;
  --panel: rgba(17, 24, 39, 0.96);
  --panel-2: rgba(15, 30, 46, 0.96);
  --card: #101d2d;
  --card-strong: #13273e;
  --line: rgba(148, 163, 184, 0.18);
  --primary: #e94560;
  --primary-2: #ff6b7f;
  --accent: #4ade80;
    --accent-warm: #f4c95d;
  --warning: #fbbf24;
  --text: #eef6ff;
  --muted: #9bb0c7;
  --shadow: 0 16px 40px rgba(2, 6, 23, 0.42);
}
html{min-height:100%;background:#07111f}
html,body{background:linear-gradient(135deg,#07111f 0%,#0c1b2b 52%,#182232 100%);color:var(--text);font-family:"Trebuchet MS","Segoe UI",sans-serif}
body{min-height:100vh;margin:0;padding:24px;line-height:1.5;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:36px 36px}
*{box-sizing:border-box}
a{transition:color .2s ease,background .2s ease,border-color .2s ease,transform .2s ease}
button,.btn,a{touch-action:manipulation}
.container{max-width:1180px;margin:0 auto;animation:page-enter .45s ease both}
.header{padding:18px 22px 18px 72px;box-sizing:border-box;background:linear-gradient(135deg,rgba(22,33,62,.97),rgba(15,52,96,.9));border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);backdrop-filter:blur(14px)}
.header h1{color:#f4f7fb;font-size:22px;font-weight:800;letter-spacing:.04em}
.header small{color:var(--muted);letter-spacing:.12em}
.menu-toggle{position:fixed;top:18px;left:18px;z-index:40;width:44px;height:42px;background:linear-gradient(135deg,var(--primary),var(--primary-2));color:white;border:0;border-radius:9px;font-size:22px;line-height:1;cursor:pointer;box-shadow:0 8px 18px rgba(233,69,96,.35);transition:transform .2s ease,box-shadow .2s ease}
.menu-toggle:hover{transform:translateY(-2px);box-shadow:0 12px 24px rgba(233,69,96,.42)}
.menu{display:flex;position:fixed;top:70px;left:14px;z-index:30;width:min(270px,calc(100vw - 28px));max-height:calc(100vh - 88px);overflow-y:auto;padding:12px;background:rgba(12,24,40,.98);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);flex-direction:column;gap:5px;margin:0;opacity:0;visibility:hidden;pointer-events:none;transform:translateX(-18px);transition:opacity .2s ease,transform .2s ease,visibility .2s ease}
.menu::before{content:'BIST AI  |  NAVIGASYON';padding:4px 8px 10px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.1em;border-bottom:1px solid var(--line);margin-bottom:4px}.menu.acik{opacity:1;visibility:visible;pointer-events:auto;transform:translateX(0)}.menu a{width:100%;box-sizing:border-box;flex:none;text-align:left;padding:11px 12px;border-radius:7px;color:var(--text);text-decoration:none;background:rgba(255,255,255,.02);border:1px solid transparent;font-weight:600}
.menu a:hover,.menu a.active{background:linear-gradient(135deg,rgba(233,69,96,.18),rgba(17,103,171,.18));border-color:rgba(233,69,96,.35)}
.menu-backdrop{display:none;position:fixed;inset:0;z-index:15;background:rgba(2,6,23,.45)}.menu-backdrop.acik{display:block}
.card,.section,.stat-card,.summary-card,.metric-box,.panel,.form-box,.hero{background:linear-gradient(180deg,rgba(19,31,47,.98),rgba(18,24,35,.96));border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
input,select,textarea{background:rgba(13,29,46,.92);border:1px solid rgba(148,163,184,.2);color:var(--text);border-radius:10px;padding:11px 12px;transition:border-color .2s ease,box-shadow .2s ease,background .2s ease}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent-warm);box-shadow:0 0 0 3px rgba(244,201,93,.16);background:#10243a}
button,.btn{background:linear-gradient(135deg,var(--primary),var(--primary-2));border:0;color:white;border-radius:10px;padding:11px 16px;font-weight:700;cursor:pointer;box-shadow:0 10px 20px rgba(233,69,96,.28);transition:transform .2s ease,filter .2s ease,box-shadow .2s ease}
button:hover,.btn:hover{filter:brightness(1.06);transform:translateY(-1px);box-shadow:0 13px 24px rgba(233,69,96,.34)}
table{border:1px solid var(--line);box-shadow:var(--shadow)}
th{letter-spacing:.04em}
tr{transition:background .18s ease}
tr:hover{background:rgba(244,201,93,.06)}
@keyframes page-enter{from{opacity:0}to{opacity:1}}
@media (min-width: 900px){body{padding:22px 28px 22px 294px}.container{max-width:1280px;margin:0}.menu-toggle,.menu-backdrop{display:none!important}.menu{top:18px;left:18px;bottom:18px;width:248px;max-height:none;padding:16px;opacity:1;visibility:visible;pointer-events:auto;transform:none;border-radius:12px}.menu::before{padding:4px 6px 14px;font-size:12px}.menu a{padding:12px}.header{padding-left:22px}.header h1{font-size:24px}}
@media (max-width: 640px){body{padding:14px}.header{padding:16px 16px 16px 60px}.header p{font-size:11px}.card,.section,.stat-card,.summary-card,.metric-box,.panel,.form-box,.hero{border-radius:10px}table{display:block;overflow-x:auto;white-space:nowrap}}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
</style>
"""
    script = """
<script>
(function(){
    function menuKur(){
        var menu=document.querySelector('.menu');
        var toggle=document.querySelector('.menu-toggle');
        var backdrop=document.querySelector('.menu-backdrop');
        if(!menu || !toggle || !backdrop || toggle.dataset.menuHazir) return;
        toggle.dataset.menuHazir='1';
        document.body.appendChild(menu);
        menu.id='ana-navigasyon';
        toggle.setAttribute('aria-controls','ana-navigasyon');
        function kapat(){menu.classList.remove('acik');backdrop.classList.remove('acik');toggle.setAttribute('aria-label','Menüyü aç');toggle.setAttribute('aria-expanded','false');}
        toggle.addEventListener('click',function(){var acik=!menu.classList.contains('acik');menu.classList.toggle('acik',acik);backdrop.classList.toggle('acik',acik);toggle.setAttribute('aria-label',acik?'Menüyü kapat':'Menüyü aç');toggle.setAttribute('aria-expanded',String(acik));});
        backdrop.addEventListener('click',kapat);
        menu.querySelectorAll('a').forEach(function(link){link.addEventListener('click',kapat);});
        document.addEventListener('keydown',function(event){if(event.key==='Escape') kapat();});
    }
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',menuKur); else menuKur();
})();
(function(){
    function guncelle(){
        var simdi=new Date();
        var metin=simdi.toLocaleDateString('tr-TR',{day:'2-digit',month:'2-digit',year:'numeric'})+' '+simdi.toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
        document.querySelectorAll('.canli-saat,#canli-saat').forEach(function(alan){alan.textContent=metin;});
    }
    guncelle(); setInterval(guncelle,1000);
})();
</script>
"""
    html = html.replace('</head>', stil + '</head>', 1)
    html = re.sub(
        r'(<body\b[^>]*>)',
        r'\1<button class="menu-toggle" type="button" aria-label="Menüyü aç" aria-expanded="false">☰</button><div class="menu-backdrop"></div>',
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    html = html.replace('<div class="menu">', '<div class="menu">', 1)
    html = html.replace('</body>', script + '</body>', 1)
    response.set_data(html)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.before_request
def basit_rate_limit():
    """Tek prosesli kurulumlarda temel istek siniri uygular."""
    ip = request.remote_addr or "unknown"
    simdi = time.time()
    pencere_baslangici, sayi = _istek_sayaci.get(ip, (simdi, 0))
    if simdi - pencere_baslangici >= 60:
        pencere_baslangici, sayi = simdi, 0
    sayi += 1
    _istek_sayaci[ip] = (pencere_baslangici, sayi)
    if sayi > 120:
        return "Çok fazla istek gönderildi. Lütfen biraz sonra tekrar deneyin.", 429


def cacheli_gecmis(ticker, period="1y", auto_adjust=False):
    """Piyasa verisini 60 saniye bellekte tutar."""
    anahtar = (ticker, period, auto_adjust)
    simdi = time.time()
    kayit = _veri_cache.get(anahtar)
    if kayit and simdi - kayit[0] < 60:
        return kayit[1]
    veri = yf.Ticker(ticker).history(period=period, auto_adjust=auto_adjust)
    _veri_cache[anahtar] = (simdi, veri)
    return veri


def normalize_bist_sembol(sembol):
    """Kullanici kaydini Yahoo icin tek bir BIST sembol formatina cevirir."""
    return str(sembol or "").strip().upper().replace(".IS", "")

kullanici_yoneticisi = KullaniciYoneticisi()


@app.route("/health")
def health():
    return {"status": "ok"}, 200


def aktif_kullanici_al():
    token = request.cookies.get("session_token")
    if token:
        return kullanici_yoneticisi.token_dogrula(token)
    return None


def risk_renk_hesapla(puan):
    """Risk puanina gore otomatik renk skalasi."""
    if puan < 30:
        return "#4caf50"
    elif puan < 60:
        return "#ff9800"
    return "#f44336"


def risk_seviyesi_hesapla(puan):
    """Risk puanina gore etiket."""
    if puan < 30:
        return "DUSUK"
    elif puan < 60:
        return "ORTA"
    return "YUKSEK"


def teknik_skor_renk_hesapla(puan):
    """10 uzerinden teknik skoru yesil-sari-kirmizi renklendirir."""
    if puan >= 7:
        return "#4caf50"
    if puan >= 4:
        return "#ff9800"
    return "#f44336"


def risk_yorum_uret(puan):
    """Risk puani icin kullanici odakli yorum."""
    if puan >= 80:
        return "Mukemmel! Portfoy cok iyi cesitlendirilmis."
    elif puan >= 60:
        return "Iyi. Cesitlendirme yeterli."
    elif puan >= 40:
        return "Orta. Cesitlendirme artirilabilir."
    elif puan >= 20:
        return "Zayif. Risk var!"
    return "Cok tehlikeli!"


def cesitlendirme_puani(portfoy_data, toplam_deger):
    """Portfoy yogunlasmasina gore 0-100 cesitlendirme puani verir."""
    if not portfoy_data or toplam_deger <= 0:
        return 0

    agirliklar = [hisse["deger"] / toplam_deger for hisse in portfoy_data]
    yogunlasma = max(agirliklar)
    hisse_puani = min(50, len(agirliklar) * 10)
    yogunlasma_puani = max(0, 50 - yogunlasma * 50)
    sektor_sayisi = len({hisse["sektor"] for hisse in portfoy_data})
    sektor_puani = min(20, sektor_sayisi * 5)
    return round(min(100, hisse_puani + yogunlasma_puani + sektor_puani))


def tek_hisse_teknik_risk_hesapla(sembol):
    """Tek hisseyi dort teknik baslikla 10 uzerinden puanlar."""
    try:
        ticker = yf.Ticker(f"{sembol}.IS")
        veri = ticker.history(period="1y", auto_adjust=False)
        if veri is None or veri.empty or "Close" not in veri.columns:
            return None

        fiyatlar = veri["Close"].dropna().astype(float)
        if len(fiyatlar) < 60:
            return None

        fiyat = float(fiyatlar.iloc[-1])
        ema21 = float(fiyatlar.ewm(span=21, adjust=False).mean().iloc[-1])
        ema50 = float(fiyatlar.ewm(span=50, adjust=False).mean().iloc[-1])
        macd_serisi = fiyatlar.ewm(span=12, adjust=False).mean() - fiyatlar.ewm(span=26, adjust=False).mean()
        macd = float(macd_serisi.iloc[-1])
        macd_sinyal = float(macd_serisi.ewm(span=9, adjust=False).mean().iloc[-1])

        degisim = fiyatlar.diff()
        kazanc = degisim.clip(lower=0).rolling(14).mean()
        kayip = -degisim.clip(upper=0).rolling(14).mean()
        rs = kazanc / kayip.replace(0, np.nan)
        rsi_serisi = (100 - (100 / (1 + rs))).fillna(100)
        rsi = float(rsi_serisi.iloc[-1])

        orta = fiyatlar.rolling(20).mean()
        standart_sapma = fiyatlar.rolling(20).std()
        ust_bant = float((orta + 2 * standart_sapma).iloc[-1])
        alt_bant = float((orta - 2 * standart_sapma).iloc[-1])
        orta_deger = float(orta.iloc[-1])

        rsi14 = rsi_serisi.dropna()
        rsi_min = rsi14.rolling(14).min()
        rsi_max = rsi14.rolling(14).max()
        stoch_rsi = ((rsi14 - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan) * 100).fillna(50)
        stoch = float(stoch_rsi.iloc[-1])

        momentum_puan = 8 if macd > macd_sinyal and macd > 0 else 6 if macd > macd_sinyal else 3
        rsi_puan = 9 if 30 <= rsi <= 70 else 5 if rsi < 30 else 2
        trend_puan = 10 if fiyat > ema21 > ema50 else 8 if fiyat > ema50 else 3
        bant_puan = 8 if alt_bant <= fiyat <= orta_deger else 6 if fiyat < alt_bant else 3
        destek_puan = round((trend_puan + bant_puan) / 2, 1)
        donus_puan = 9 if stoch < 20 else 8 if stoch > 80 else 6
        puanlar = [momentum_puan, rsi_puan, destek_puan, donus_puan]

        return {
            "sembol": sembol,
            "fiyat": round(fiyat, 2),
            "macd": round(momentum_puan, 1),
            "macd_deger": round(macd, 3),
            "rsi": round(rsi_puan, 1),
            "rsi_deger": round(rsi, 2),
            "destek_direnc": round(destek_puan, 1),
            "ema21": round(ema21, 2),
            "ema50": round(ema50, 2),
            "stochastic": round(donus_puan, 1),
            "stochastic_deger": round(stoch, 2),
            "ortalama": round(sum(puanlar) / len(puanlar), 1),
            "bollinger_alt": round(alt_bant, 2),
            "bollinger_ust": round(ust_bant, 2),
        }
    except Exception:
        return None


def basit_ai_tahmini(sembol, gun_sayisi=5):
    """Model verisi yoksa son fiyat trendiyle tahmin üretir."""
    try:
        veri = yf.Ticker(f"{sembol}.IS").history(period="3mo", auto_adjust=False)
        fiyatlar = veri["Close"].dropna().astype(float) if veri is not None and "Close" in veri else None
        if fiyatlar is None or len(fiyatlar) < 5:
            return None
        son_fiyat = float(fiyatlar.iloc[-1])
        gunluk_getiri = float(fiyatlar.pct_change().dropna().tail(20).mean())
        gunluk_getiri = max(-0.05, min(0.05, gunluk_getiri))
        return [son_fiyat * ((1 + gunluk_getiri) ** gun) for gun in range(gun_sayisi)]
    except Exception:
        return None


def yarin_hisse_tahmini(sembol):
    """Son fiyat hareketlerinden yarinin yon tahminini uretir."""
    try:
        veri = yf.Ticker(f"{sembol}.IS").history(period="6mo", auto_adjust=False)
        if veri is None or "Close" not in veri.columns:
            return None
        fiyatlar = veri["Close"].dropna().astype(float)
        if len(fiyatlar) < 30:
            return None

        getiriler = fiyatlar.pct_change().dropna()
        son_fiyat = float(fiyatlar.iloc[-1])
        bugun_getiri = float(getiriler.iloc[-1]) * 100
        momentum_5 = float(getiriler.tail(5).mean())
        momentum_20 = float(getiriler.tail(20).mean())
        ema5 = float(fiyatlar.ewm(span=5, adjust=False).mean().iloc[-1])
        ema20 = float(fiyatlar.ewm(span=20, adjust=False).mean().iloc[-1])
        delta = fiyatlar.diff()
        kazanc = delta.clip(lower=0).rolling(14).mean()
        kayip = -delta.clip(upper=0).rolling(14).mean()
        rs = kazanc / kayip.replace(0, np.nan)
        rsi = float((100 - (100 / (1 + rs))).fillna(50).iloc[-1])

        trend = (ema5 / ema20 - 1) * 100
        beklenen_getiri = (momentum_5 * 0.45 + momentum_20 * 0.35 + trend / 100 * 0.20) * 100
        if rsi > 70:
            beklenen_getiri -= 0.8
        elif rsi < 30:
            beklenen_getiri += 0.8
        beklenen_getiri = max(-5.0, min(5.0, beklenen_getiri))
        puan = max(0.0, min(100.0, 50 + beklenen_getiri * 8 + trend * 4))
        yarin_fiyat = son_fiyat * (1 + beklenen_getiri / 100)

        return {
            "sembol": sembol,
            "bugun": round(son_fiyat, 2),
            "bugun_getiri": round(bugun_getiri, 2),
            "yarin": round(yarin_fiyat, 2),
            "beklenen_getiri": round(beklenen_getiri, 2),
            "puan": round(puan, 1),
            "rsi": round(rsi, 1),
            "trend": round(trend, 2),
            "bugun_yukseliyor": bugun_getiri > 0,
        }
    except Exception:
        return None


def uzun_vade_hisse_tahmini(sembol):
    """Hissenin ilk mevcut islem gununden bugune uzun vadeli analizini yapar."""
    try:
        veri = cacheli_gecmis(f"{sembol}.IS", period="max", auto_adjust=True)
        if veri is None or "Close" not in veri.columns:
            return None
        fiyatlar = veri["Close"].dropna().astype(float)
        if len(fiyatlar) < 30:
            return None

        son_fiyat = float(fiyatlar.iloc[-1])
        getiriler = fiyatlar.pct_change().dropna()
        gun_sayisi = max(1, (fiyatlar.index[-1] - fiyatlar.index[0]).days)
        yillik_getiri = (son_fiyat / float(fiyatlar.iloc[0])) ** (365 / gun_sayisi) - 1
        son_1y = fiyatlar.tail(min(252, len(fiyatlar)))
        son_1y_getiri = (float(son_1y.iloc[-1]) / float(son_1y.iloc[0])) ** (252 / max(1, len(son_1y))) - 1
        yillik_ortalama = max(-0.50, min(1.00, yillik_getiri * 0.55 + son_1y_getiri * 0.45))
        # Uzun tarihcedeki bolunme kaynakli tek gunluk sivramalari kirp.
        temiz_getiriler = getiriler.clip(lower=-0.20, upper=0.20)
        volatilite = float(temiz_getiriler.std() * np.sqrt(252) * 100)
        trend = "YUKARI" if yillik_ortalama > 0.03 else "ASAGI" if yillik_ortalama < -0.03 else "YATAY"
        ema50 = float(fiyatlar.ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(fiyatlar.ewm(span=min(200, len(fiyatlar)), adjust=False).mean().iloc[-1])
        destek = float(fiyatlar.tail(min(252, len(fiyatlar))).min())
        direnc = float(fiyatlar.tail(min(252, len(fiyatlar))).max())

        hedefler = {}
        for ay, gun in ((3, 63), (6, 126), (9, 189)):
            hedef = son_fiyat * ((1 + yillik_ortalama) ** (gun / 252))
            hedefler[ay] = {
                "fiyat": round(hedef, 2),
                "degisim": round((hedef / son_fiyat - 1) * 100, 2),
            }

        def grafik_olustur(gun):
            grafik_fiyatlari = fiyatlar.tail(min(gun, len(fiyatlar))).iloc[::max(1, gun // 30)]
            if grafik_fiyatlari.iloc[-1] != fiyatlar.iloc[-1]:
                grafik_degerleri = np.concatenate((grafik_fiyatlari.to_numpy(), [float(fiyatlar.iloc[-1])]))
            else:
                grafik_degerleri = grafik_fiyatlari.to_numpy()
            normalize = grafik_degerleri / float(grafik_degerleri[0]) * 100
            en_dusuk = float(normalize.min())
            aralik = max(0.01, float(normalize.max()) - en_dusuk)
            return " ".join(
                f"{round(index * 100 / max(1, len(normalize) - 1), 1)},{round(100 - (float(fiyat) - en_dusuk) * 90 / aralik, 1)}"
                for index, fiyat in enumerate(normalize)
            )

        def indikatör_grafigi(seri, gun, alt=0, ust=100):
            secilen = seri.tail(min(gun, len(seri))).iloc[::max(1, gun // 30)]
            degerler = secilen.to_numpy(dtype=float)
            if len(degerler) < 2:
                return "0,50 100,50"
            minimum, maksimum = float(np.nanmin(degerler)), float(np.nanmax(degerler))
            aralik = max(0.0001, maksimum - minimum)
            return " ".join(
                f"{round(i * 100 / (len(degerler) - 1), 1)},{round(100 - (deger - minimum) * 90 / aralik, 1)}"
                for i, deger in enumerate(degerler)
            )

        ema50_serisi = fiyatlar.ewm(span=50, adjust=False).mean()
        ema200_serisi = fiyatlar.ewm(span=min(200, len(fiyatlar)), adjust=False).mean()
        macd_serisi = fiyatlar.ewm(span=12, adjust=False).mean() - fiyatlar.ewm(span=26, adjust=False).mean()
        delta = fiyatlar.diff()
        kazanc = delta.clip(lower=0).rolling(14).mean()
        kayip = -delta.clip(upper=0).rolling(14).mean()
        rsi_serisi = (100 - (100 / (1 + kazanc / kayip.replace(0, np.nan)))).fillna(50)

        def indikatör_seti(gun):
            return {
                "ema50": indikatör_grafigi(ema50_serisi, gun),
                "ema200": indikatör_grafigi(ema200_serisi, gun),
                "macd": indikatör_grafigi(macd_serisi, gun),
                "rsi": indikatör_grafigi(rsi_serisi, gun),
            }
        return {
            "sembol": sembol,
            "guncel": round(son_fiyat, 2),
            "trend": trend,
            "volatilite": round(volatilite, 2),
            "degisim": hedefler[3]["degisim"],
            "gecmis_yil": round(gun_sayisi / 365, 1),
            "gecmis_getiri": round(yillik_getiri * 100, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "destek": round(destek, 2),
            "direnc": round(direnc, 2),
            "hedefler": hedefler,
            "grafik_noktalar": grafik_olustur(63),
            "grafik_3_ay": grafik_olustur(63),
            "grafik_6_ay": grafik_olustur(126),
            "grafik_9_ay": grafik_olustur(189),
            "indikator_3_ay": indikatör_seti(63),
            "indikator_6_ay": indikatör_seti(126),
            "indikator_9_ay": indikatör_seti(189),
        }
    except Exception:
        return None


def uzun_vade_fallback_tahmini(sembol):
    """Kisa veri donerse bile uzun vadeli hedef karti uretir."""
    try:
        tahminler = basit_ai_tahmini(sembol, gun_sayisi=5)
        if not tahminler or len(tahminler) < 2 or tahminler[0] <= 0:
            return None
        guncel = float(tahminler[0])
        gunluk_trend = (float(tahminler[-1]) / guncel) ** 0.25 - 1
        hedefler = {}
        for ay, gun in ((3, 63), (6, 126), (9, 189)):
            hedef = guncel * ((1 + gunluk_trend) ** gun)
            hedefler[ay] = {"fiyat": round(hedef, 2), "degisim": round((hedef / guncel - 1) * 100, 2)}
        return {
            "sembol": sembol, "guncel": round(guncel, 2),
            "trend": "YUKARI" if gunluk_trend > 0 else "ASAGI" if gunluk_trend < 0 else "YATAY",
            "volatilite": 0.0, "degisim": hedefler[3]["degisim"],
            "gecmis_yil": 0.0, "gecmis_getiri": 0.0, "ema50": guncel,
            "ema200": guncel, "destek": guncel, "direnc": guncel,
            "hedefler": hedefler,
            "grafik_noktalar": "0,70 25,55 50,60 75,40 100,30",
            "grafik_3_ay": "0,70 25,55 50,60 75,40 100,30",
            "grafik_6_ay": "0,75 25,60 50,50 75,45 100,30",
            "grafik_9_ay": "0,80 25,65 50,55 75,40 100,25",
            "indikator_3_ay": {"ema50": "0,50 100,50", "ema200": "0,50 100,50", "macd": "0,50 100,50", "rsi": "0,50 100,50"},
            "indikator_6_ay": {"ema50": "0,50 100,50", "ema200": "0,50 100,50", "macd": "0,50 100,50", "rsi": "0,50 100,50"},
            "indikator_9_ay": {"ema50": "0,50 100,50", "ema200": "0,50 100,50", "macd": "0,50 100,50", "rsi": "0,50 100,50"},
        }
    except Exception:
        return None


def portfoy_veri_hazirla_icin(hisseler_listesi):
    hisseler = []
    toplam_maliyet = 0
    toplam_deger = 0

    for hisse in hisseler_listesi:
        try:
            sembol = normalize_bist_sembol(hisse.get("sembol"))
            alis_fiyati = float(hisse.get("alis_fiyati", 0) or 0)
            adet = int(hisse.get("adet", 0) or 0)
            if not sembol or adet <= 0 or alis_fiyati <= 0:
                continue

            guncel = alis_fiyati
            try:
                ticker = yf.Ticker(sembol + ".IS")
                veri = ticker.history(period="5d")
                if veri is not None and len(veri) >= 1:
                    son_fiyat = float(veri["Close"].iloc[-1])
                    if son_fiyat > 0:
                        guncel = son_fiyat
            except Exception:
                guncel = alis_fiyati

            maliyet = adet * alis_fiyati
            deger = adet * guncel
            kar = deger - maliyet
            kar_yuzde = (kar / maliyet) * 100 if maliyet > 0 else 0
            stop_loss = float(hisse.get("stop_loss", 0) or 0)
            kar_hedef = float(hisse.get("kar_hedef", 0) or 0)
            if stop_loss and guncel <= stop_loss:
                hedef_durumu = "STOP-LOSS"
            elif kar_hedef and guncel >= kar_hedef:
                hedef_durumu = "KAR HEDEFI"
            elif guncel == alis_fiyati:
                hedef_durumu = "BEKLENIYOR"
            else:
                hedef_durumu = "Normal"
            toplam_maliyet += maliyet
            toplam_deger += deger
            hisseler.append({
                "sembol": sembol,
                "adet": adet,
                "alis": f"{alis_fiyati:.2f}",
                "guncel": f"{guncel:.2f}",
                "kar_yuzde": f"{kar_yuzde:+.2f}",
                "renk": "positive" if kar >= 0 else "negative",
                "hedef_durumu": hedef_durumu,
            })
        except Exception:
            continue

    toplam_kar = toplam_deger - toplam_maliyet
    return {
        "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "hisseler": hisseler,
        "toplam_maliyet": f"{toplam_maliyet:,.2f}",
        "toplam_deger": f"{toplam_deger:,.2f}",
        "toplam_kar": f"{toplam_kar:+,.2f}",
        "kar_renk": "positive" if toplam_kar >= 0 else "negative",
        "hisse_sayisi": len(hisseler),
    }


# ============================================
# HTML SABLONLARI (DUZELTILMIS)
# ============================================
HTML_LOGIN = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Giris</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#07111f;--panel:#111b2c;--panel-2:#0d1b2a;--primary:#e94560;--primary-2:#ff6b7f;--line:rgba(148,163,184,.18);--text:#eef6ff;--muted:#9bb0c7}
body{font-family:Segoe UI, Arial, sans-serif;background:radial-gradient(circle at top, #112339 0%, #081522 42%, #050d18 100%);color:var(--text);margin:0;padding:20px}
.container{max-width:420px;margin:80px auto 0}
.logo{text-align:center;margin-bottom:26px}
.logo h1{margin:0;color:#f7f9fc;font-size:36px;letter-spacing:.08em;font-weight:800}
.logo p{margin:8px 0 0;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-size:12px}
.form-box{background:linear-gradient(180deg,rgba(17,27,44,.96),rgba(10,18,28,.96));padding:30px;border-radius:18px;border:1px solid var(--line);box-shadow:0 18px 42px rgba(2,6,23,.45)}
.form-box h2{margin:0 0 20px;text-align:center;font-size:28px}
input{width:100%;padding:14px 12px;margin:8px 0;border:1px solid rgba(148,163,184,.2);border-radius:10px;background:#0d1b2a;color:var(--text);box-sizing:border-box;font-size:15px}
.btn{width:100%;padding:14px 12px;border:none;border-radius:10px;background:linear-gradient(135deg,var(--primary),var(--primary-2));color:white;cursor:pointer;font-size:16px;font-weight:700;margin-top:12px;box-shadow:0 12px 24px rgba(233,69,96,.22)}
.switch{text-align:center;margin-top:16px;color:var(--muted);font-size:14px}
.switch a{color:#ffd1db;text-decoration:none;font-weight:700}
.hata{background:rgba(220,38,38,.18);border:1px solid rgba(248,113,113,.35);padding:10px;border-radius:10px;margin-bottom:15px;text-align:center;color:#ffe4e6;font-weight:600}
</style></head>
<body>
<div class="container">
<div class="logo"><h1>BIST AI</h1><p>Borsa Yatirim Asistani</p></div>
<div class="form-box">
<h2>Giris Yap</h2>
{% if hata %}<div class="hata">{{ hata }}</div>{% endif %}
<form method="POST" action="/giris">
<input type="text" name="kullanici_adi" placeholder="Kullanici Adi" required>
<input type="password" name="sifre" placeholder="Sifre" required>
<button class="btn" type="submit">Giris Yap</button>
</form>
<div class="switch">Hesabin yok mu? <a href="/kayit">Kayit Ol</a></div>
</div></div>
</body></html>
"""

HTML_KAYIT = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Kayit</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#07111f;--panel:#111b2c;--line:rgba(148,163,184,.18);--primary:#e94560;--primary-2:#ff6b7f;--text:#eef6ff;--muted:#9bb0c7}
body{font-family:Segoe UI, Arial, sans-serif;background:radial-gradient(circle at top, #112339 0%, #081522 42%, #050d18 100%);color:var(--text);margin:0;padding:20px}
.container{max-width:420px;margin:80px auto 0}
.logo{text-align:center;margin-bottom:26px}
.logo h1{margin:0;color:#f7f9fc;font-size:36px;letter-spacing:.08em;font-weight:800}
.logo p{margin:8px 0 0;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-size:12px}
.form-box{background:linear-gradient(180deg,rgba(17,27,44,.96),rgba(10,18,28,.96));padding:30px;border-radius:18px;border:1px solid var(--line);box-shadow:0 18px 42px rgba(2,6,23,.45)}
.form-box h2{margin:0 0 20px;text-align:center;font-size:28px}
input{width:100%;padding:14px 12px;margin:8px 0;border:1px solid rgba(148,163,184,.2);border-radius:10px;background:#0d1b2a;color:var(--text);box-sizing:border-box;font-size:15px}
.btn{width:100%;padding:14px 12px;border:none;border-radius:10px;background:linear-gradient(135deg,var(--primary),var(--primary-2));color:white;cursor:pointer;font-size:16px;font-weight:700;margin-top:12px;box-shadow:0 12px 24px rgba(233,69,96,.22)}
.switch{text-align:center;margin-top:16px;color:var(--muted);font-size:14px}
.switch a{color:#ffd1db;text-decoration:none;font-weight:700}
.hata{background:rgba(220,38,38,.18);border:1px solid rgba(248,113,113,.35);padding:10px;border-radius:10px;margin-bottom:15px;text-align:center;color:#ffe4e6;font-weight:600}
</style></head>
<body>
<div class="container">
<div class="logo"><h1>BIST AI</h1><p>Yeni Hesap Olustur</p></div>
<div class="form-box">
<h2>Kayit Ol</h2>
{% if hata %}<div class="hata">{{ hata }}</div>{% endif %}
<form method="POST" action="/kayit">
<input type="text" name="kullanici_adi" placeholder="Kullanici Adi" required>
<input type="email" name="email" placeholder="Email" required>
<input type="password" name="sifre" placeholder="Sifre (min 4 karakter)" required>
<button class="btn" type="submit">Kayit Ol</button>
</form>
<div class="switch">Hesabin var mi? <a href="/giris">Giris Yap</a></div>
</div></div>
</body></html>
"""

HTML_PORTFOY = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Portfoy</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BIST AI">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:80px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:15px}
.stat-card{background:#16213e;padding:12px;border-radius:8px;text-align:center}
.stat-value{font-size:18px;font-weight:bold;margin-top:5px}
.positive{color:#4caf50}.negative{color:#f44336}
table{width:100%;border-collapse:collapse;background:#16213e;border-radius:8px;overflow:hidden;font-size:14px}
th,td{padding:10px;text-align:left;border-bottom:1px solid #0f3460}
th{background:#0f3460}
form{margin:15px 0;background:#16213e;padding:15px;border-radius:8px}
input{width:100%;padding:10px;margin:5px 0;border:none;border-radius:5px;background:#0f3460;color:white;box-sizing:border-box}
.btn{display:inline-block;padding:10px 20px;background:#e94560;color:white;border:none;border-radius:5px;cursor:pointer;text-decoration:none}
.portfolio-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:24px}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/" class="active">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
</div>
<div class="stats">
<div class="stat-card"><div>Deger</div><div class="stat-value">{{ toplam_deger }} TL</div></div>
<div class="stat-card"><div>Maliyet</div><div class="stat-value">{{ toplam_maliyet }} TL</div></div>
<div class="stat-card"><div>Kar/Zarar</div><div class="stat-value {{ kar_renk }}">{{ toplam_kar }} TL</div></div>
<div class="stat-card"><div>Risk</div><div class="stat-value" style="color:{% if risk_ozeti %}{{ risk_ozeti.risk_renk }}{% else %}#b0bec5{% endif %}">{% if risk_ozeti %}{{ risk_ozeti.genel_risk }}{% else %}0{% endif %}/100</div></div>
</div>

{% if risk_ozeti %}
<div style="background:#16213e;padding:16px;border-radius:10px;margin:15px 0;border-left:4px solid {{ risk_ozeti.risk_renk }};">
<b style="color:{{ risk_ozeti.risk_renk }}">{{ risk_ozeti.risk_seviye }} RISK</b>
<div style="margin-top:8px;font-size:14px;color:#dfeaff">Cesitlendirme: {{ risk_ozeti.cesitlendirme }}/100</div>
<div style="margin-top:6px;font-size:13px;color:#b0bec5">{{ risk_ozeti.puan_yorum }}</div>
</div>
{% endif %}

<h2>Hisseler</h2>
{% if hisseler %}
<table>
<tr><th>Hisse</th><th>Adet</th><th>Alis</th><th>Guncel</th><th>Kar %</th><th>Hedef Durumu</th><th>Islem</th></tr>
{% for h in hisseler %}
<tr>
<td><b>{{ h.sembol }}</b></td><td>{{ h.adet }}</td><td>{{ h.alis }}</td><td>{{ h.guncel }}</td>
<td class="{{ h.renk }}">{{ h.kar_yuzde }}%</td>
<td>{{ h.hedef_durumu }}</td>
<td style="text-align:center">
<a href="/hisse-sil/{{ h.sembol }}" style="background:#f44336;color:white;padding:5px 12px;border-radius:4px;text-decoration:none;font-weight:bold" onclick="return confirm('{{ h.sembol }} hissesini portfoyden silmek istediginize emin misiniz?')">X</a>
</td>
</tr>
{% endfor %}
</table>
{% else %}<p>Portfoy bos.</p>{% endif %}
<h2>Yeni Hisse Ekle</h2>
<form method="POST" action="/ekle">
<input name="sembol" placeholder="Hisse (orn: THYAO)" required>
<input name="adet" type="number" placeholder="Adet" required>
<input name="fiyat" type="number" step="0.01" placeholder="Alis Fiyati" required>
<input name="stop_loss" type="number" step="0.01" min="0" placeholder="Stop-loss (opsiyonel)">
<input name="kar_hedef" type="number" step="0.01" min="0" placeholder="Kar hedefi (opsiyonel)">
<button class="btn" type="submit">Ekle</button>
</form>
<h2>Hisse Sat</h2>
<form method="POST" action="/sat">
<input name="sembol" placeholder="Hisse (orn: THYAO)" required>
<input name="adet" type="number" min="1" placeholder="Adet" required>
<input name="fiyat" type="number" step="0.01" min="0.01" placeholder="Satis Fiyati" required>
<button class="btn" type="submit">Sat</button>
</form>
<div class="portfolio-actions">
<a class="btn" href="/islemler">İşlem Geçmişi</a>
<a class="btn" href="/portfoy.csv">CSV İndir</a>
<a class="btn" href="/portfoy.xlsx">Excel İndir</a>
<a class="btn" href="/performans">Performans</a>
<a class="btn" href="/temizle" style="background:#f44336" onclick="return confirm('Tum portfoy silinecek! Emin misiniz?')">Portfoyu Temizle</a>
</div>
</div>
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service-worker.js').catch(function (error) {
      console.log('Service worker kaydi basarisiz:', error);
    });
  });
}
</script>
</body></html>
"""

HTML_SEKTOR = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Sektor</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BIST AI">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:80px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}
.sektor-card{background:#16213e;padding:12px;margin:8px 0;border-radius:8px;display:flex;justify-content:space-between;align-items:center}
.sektor-card .ad{font-weight:bold;font-size:16px}
.sektor-card .deger{font-size:18px;font-weight:bold}
.pozitif{color:#4caf50}.negatif{color:#f44336}.notr{color:#b0bec5}
.oneri{background:#0f3460;padding:15px;border-radius:8px;margin:10px 0}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor" class="active">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
</div>
<h2>Sektor Performansi</h2>
{% for s in sektorler %}
<div class="sektor-card">
<div><div class="ad">{{ s.emoji }} {{ s.sektor }}</div><div style="font-size:12px;color:#b0bec5">{{ s.hisse_sayisi }} hisse</div></div>
<div class="deger {{ s.renk }}">{{ s.ortalama }}%</div>
</div>
{% endfor %}
<div class="oneri">
<h3>Oneriler</h3>
{% if en_iyi %}<p class="pozitif">Guclu sektor: {{ en_iyi }}</p>{% endif %}
{% if en_kotu %}<p class="negatif">Zayif sektor: {{ en_kotu }}</p>{% endif %}
</div>
</div>
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service-worker.js').catch(function (error) {
      console.log('Service worker kaydi basarisiz:', error);
    });
  });
}
</script>
</body></html>
"""

HTML_RISK = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Risk</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BIST AI">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:900px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#cfe2ff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.header p{margin:8px 0 0;color:#cfe2ff;font-size:13px}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:80px;padding:9px;background:#0f3460;color:white;text-decoration:none;border-radius:7px;text-align:center;font-size:12px;font-weight:600}
.menu a.active{background:#e94560}.menu a.cikis{background:#f44336}
.risk-hero{background:linear-gradient(135deg,#0f3460,#1a2749);padding:24px;border-radius:14px;margin-bottom:18px;border:1px solid rgba(255,255,255,.06);box-shadow:0 12px 28px rgba(0,0,0,.22)}
.risk-header-row{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.badge{padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.08);font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#dfeaff}
.puan-sayi{font-size:56px;font-weight:800;line-height:1;color:#ffffff;margin-top:10px}
.puan-yorum{font-size:16px;font-weight:700;color:#dfeaff;margin-top:12px}
.summary-grid{display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:12px;margin:18px 0}
.summary-card{background:#16213e;border:1px solid rgba(233,69,96,.22);border-radius:12px;padding:16px;min-height:110px}
.summary-card .label{font-size:11px;color:#b0bec5;text-transform:uppercase;letter-spacing:.08em}
.summary-card .value{margin-top:8px;font-size:22px;font-weight:800;line-height:1.2}
.summary-card .sub{margin-top:8px;font-size:12px;color:#cfe2ff}
.section{background:#16213e;padding:18px;border-radius:12px;margin-bottom:18px;border:1px solid rgba(255,255,255,.06)}
.section h3{margin:0 0 12px;color:#e94560;font-size:18px}
.metrik-grid{display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:12px;margin-top:14px}
.metrik-kutu{background:#0f3460;padding:16px;border-radius:10px;border:1px solid rgba(255,255,255,.06)}
.metrik-baslik{font-size:11px;color:#b0bec5;text-transform:uppercase;letter-spacing:.08em}
.metrik-deger{font-size:20px;font-weight:800;margin-top:8px}
.metrik-sub{font-size:12px;color:#dfeaff;margin-top:4px}
.alert{padding:14px 16px;border-radius:10px;margin:10px 0;border-left:4px solid #e94560;background:rgba(233,69,96,.1);font-size:14px;line-height:1.5}
.alert.success{border-left-color:#4caf50;background:rgba(76,175,80,.12)}
.alert.warning{border-left-color:#ff9800;background:rgba(255,152,0,.12)}
.alert.danger{border-left-color:#f44336;background:rgba(244,67,54,.12)}
.hisse-list{display:grid;gap:10px}
.hisse-item{background:#0f3460;padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,.06)}
.hisse-top{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:6px}
.hisse-simge{font-weight:800;font-size:16px}
.hisse-risk{padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.08);font-size:12px;font-weight:700}
.hisse-meta{font-size:12px;color:#cfe2ff;line-height:1.6}
.korelasyon-list{display:grid;gap:10px}
.korelasyon-item{background:#0f3460;padding:12px;border-radius:10px;border-left:4px solid #ff9800}
.korelasyon-item strong{color:#fff}
.oneri-panel{display:grid;gap:10px}
.oneri-item{padding:14px 16px;border-radius:10px;background:rgba(15,52,96,.8);border-left:4px solid #e94560;font-size:14px;line-height:1.5}
.oneri-item:nth-child(odd){border-left-color:#4caf50}
.oneri-item:nth-child(even){border-left-color:#ff9800}
.query-form{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end}
.query-form label{display:block;color:#b0bec5;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}
.query-form input{width:100%;padding:11px;border:1px solid rgba(255,255,255,.1);border-radius:7px;background:#0f3460;color:white;box-sizing:border-box}
.query-form .btn{padding:11px 18px;background:#e94560;color:white;border:0;border-radius:7px;cursor:pointer;font-weight:700;white-space:nowrap}
@media (max-width: 700px){.summary-grid,.metrik-grid{grid-template-columns:1fr 1fr}.}
@media (max-width: 700px){.query-form{grid-template-columns:1fr 1fr}.query-form .btn{width:100%}}
@media (max-width: 520px){.summary-grid,.metrik-grid{grid-template-columns:1fr}. .menu a{min-width:calc(50% - 8px)} .query-form{grid-template-columns:1fr}}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk" class="active">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
<a href="/cikis" class="cikis">Cikis</a>
</div>

<div class="section">
<h3>Tek Hisse Risk Sorgula</h3>
<form method="POST" action="/risk-sorgula" class="query-form">
<div><label for="risk-sembol">Hisse</label><input id="risk-sembol" name="sembol" placeholder="THYAO" required></div>
<button class="btn" type="submit">Risk Sorgula</button>
</form>
</div>

{% if tek_hisse_analizi %}
<div class="section">
<h3>{{ tek_hisse_analizi.sembol }} Teknik Risk Skoru</h3>
<div class="puan-sayi" style="color:{{ tek_hisse_renk }}">{{ tek_hisse_analizi.ortalama }}/10</div>
<div class="metrik-grid">
<div class="metrik-kutu"><div class="metrik-baslik">Momentum & Trend: MACD (12, 26, 9)</div><div class="metrik-deger">{{ tek_hisse_analizi.macd }}/10</div><div class="metrik-sub">Trendin yönünü ve gücünü gösterir. MACD: {{ tek_hisse_analizi.macd_deger }}</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Göreceli Güç: RSI (14)</div><div class="metrik-deger">{{ tek_hisse_analizi.rsi }}/10</div><div class="metrik-sub">70+ aşırı alım, 30- aşırı satım. RSI: {{ tek_hisse_analizi.rsi_deger }}</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Dinamik Destek/Direnç</div><div class="metrik-deger">{{ tek_hisse_analizi.destek_direnc }}/10</div><div class="metrik-sub">EMA 21: {{ tek_hisse_analizi.ema21 }} | EMA 50: {{ tek_hisse_analizi.ema50 }}<br>Bant: {{ tek_hisse_analizi.bollinger_alt }} - {{ tek_hisse_analizi.bollinger_ust }}</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Volatiliteli Hızlı Dönüşler</div><div class="metrik-deger">{{ tek_hisse_analizi.stochastic }}/10</div><div class="metrik-sub">Stochastic RSI: {{ tek_hisse_analizi.stochastic_deger }}</div></div>
</div>
</div>
{% endif %}
{% if sorgulanan_sembol and not tek_hisse_analizi %}
<div class="alert warning">{{ sorgulanan_sembol }} için yeterli piyasa verisi alınamadı. Sembolü kontrol edip tekrar deneyin.</div>
{% endif %}

<div class="risk-hero">
<div class="risk-header-row">
<div class="badge">Portfoy Risk</div>
<div class="badge" style="color:{{ risk_renk }};border:1px solid {{ risk_renk }};background:rgba(255,255,255,.04)">{{ risk_seviye }}</div>
</div>
<div class="puan-sayi" style="color:{{ risk_renk }}">{{ genel_risk }}/100</div>
<div class="puan-yorum">{{ puan_yorum }}</div>
</div>

<div class="summary-grid">
<div class="summary-card"><div class="label">Toplam Değer</div><div class="value">{{ toplam_deger }} TL</div><div class="sub">Maliyet: {{ toplam_maliyet }} TL</div></div>
<div class="summary-card"><div class="label">Kar/Zarar</div><div class="value">{{ toplam_kar_yuzde }}%</div><div class="sub">{{ toplam_kar }} TL</div></div>
<div class="summary-card"><div class="label">Cesitlendirme</div><div class="value">{{ cesitlendirme }}/100</div><div class="sub">Dengeli dağılım</div></div>
<div class="summary-card"><div class="label">Sharpe</div><div class="value">{{ portfoy_sharpe }}</div><div class="sub">Risk/getiri oranı</div></div>
</div>

<div class="section">
<h3>Portföy Risk Metrikleri</h3>
<div class="metrik-grid">
<div class="metrik-kutu"><div class="metrik-baslik">Volatilite</div><div class="metrik-deger">%{{ portfoy_volatilite }}</div><div class="metrik-sub">Yıllık oynaklık</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">VaR (95%)</div><div class="metrik-deger">%{{ portfoy_var }}</div><div class="metrik-sub">Günlük maksimum kayıp</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Beta</div><div class="metrik-deger">{{ portfoy_beta }}</div><div class="metrik-sub">Piyasa duyarlılığı</div></div>
</div>
</div>

{% if hisse_verileri %}
<div class="section">
<h3>Portföyde Hisse Bazlı Risk</h3>
<div class="hisse-list">
{% for h in hisse_verileri %}
<div class="hisse-item">
<div class="hisse-top">
<div class="hisse-simge">{{ h.sembol }}</div>
<div class="hisse-risk" style="color:{% if h.risk_skor >= 7 %}#ffb3b3{% elif h.risk_skor >= 4 %}#ffd666{% else %}#b9f2c5{% endif %}">{{ h.risk_skor }}/10</div>
</div>
<div class="hisse-meta">
Ağırlık: {{ h.agirlik }}% | Kar/Zarar: {{ h.kar_yuzde }}% | Fiyat: {{ h.guncel }} TL<br>
Sharpe: {{ h.sharpe }} | Max DD: %{{ h.max_drawdown }} | Vol: %{{ h.volatilite }} | Beta: {{ h.beta }}
</div>
</div>
{% endfor %}
</div>
</div>
{% endif %}

{% if korelasyonlar %}
<div class="section">
<h3>Yüksek Korelasyon</h3>
<div class="korelasyon-list">
{% for k in korelasyonlar %}
<div class="korelasyon-item"><strong>{{ k.hisse1 }}</strong> - <strong>{{ k.hisse2 }}</strong><br><span>{{ k.korelasyon }} korelasyon ({{ k.tip }})</span></div>
{% endfor %}
</div>
</div>
{% endif %}

<div class="section">
<h3>Öneriler</h3>
<div class="oneri-panel">
{% for o in oneriler %}
<div class="oneri-item">{{ o }}</div>
{% endfor %}
</div>
</div>
</div></body></html>
"""

HTML_ISTIHBARAT = """
<!DOCTYPE html>
<html><head><title>BIST AI - Hisse Istihbarati</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}.container{max-width:900px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}.header h1{margin:0;color:#e94560;font-size:20px}.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}.menu a{flex:1;min-width:80px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}.menu a.active{background:#e94560}
.form{display:grid;grid-template-columns:1fr auto;gap:10px;background:#16213e;padding:15px;border-radius:8px}.form input{padding:11px;border:0;border-radius:5px;background:#0f3460;color:white}.btn{padding:11px 18px;background:#e94560;color:white;border:0;border-radius:5px;cursor:pointer;font-weight:bold}.hero,.card{background:#16213e;padding:18px;border-radius:8px;margin:15px 0}.hero{border-left:5px solid #4caf50}.score{font-size:48px;font-weight:bold;color:#4caf50}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{background:#0f3460;padding:12px;border-radius:6px}.metric b{display:block;font-size:20px;margin-top:5px}.muted{color:#b0bec5;font-size:12px}.news{margin:6px 0;padding:8px;background:#0f3460;border-radius:4px;font-size:13px}@media(max-width:600px){.form,.grid{grid-template-columns:1fr}}
</style></head><body><div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu"><a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a><a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat" class="active">Istihbarat</a><a href="/hedef">Hedef</a><a href="/cikis">Cikis</a></div>
<form class="form" method="GET"><input name="sembol" value="{{ sorgu }}" placeholder="Hisse sembolü (örn: THYAO)" required><button class="btn" type="submit">Analiz Et</button></form>
{% if analiz %}{% if analiz.durum == 'YETERLI VERI YOK' %}<div class="card">{{ analiz.sembol }} için yeterli fiyat verisi alınamadı.</div>{% else %}
<div class="hero"><div class="muted">{{ analiz.sembol }} Birleşik Analiz</div><div class="score">{{ analiz.skor }}/10</div><b>{{ analiz.durum }}</b><div class="muted">Veri güveni: %{{ analiz.veri_guveni }} | {{ analiz.tarih }}</div></div>
<div class="grid"><div class="metric"><span>Fiyat</span><b>{{ analiz.teknik.fiyat }} TL</b><small class="muted">EMA21: {{ analiz.teknik.ema21 }}</small></div><div class="metric"><span>RSI (14)</span><b>{{ analiz.teknik.rsi }}</b><small class="muted">MACD: {{ analiz.teknik.macd }}</small></div><div class="metric"><span>Hacim</span><b>{% if analiz.teknik.hacim_orani %}{{ analiz.teknik.hacim_orani }}x{% else %}VERI YOK{% endif %}</b><small class="muted">Yıllık volatilite: %{{ analiz.teknik.volatilite }}</small></div></div>
<div class="card"><h3>Haber ve KAP</h3><p class="muted">{{ analiz.haber.kaynak }} | {{ analiz.haber.adet }} başlık | Net sinyal: {{ analiz.haber.net_sinyal }}</p>{% for baslik in analiz.haber.basliklar %}<div class="news">{{ baslik }}</div>{% else %}<p class="muted">Haber bulunamadı.</p>{% endfor %}</div>
<div class="card"><h3>Kurum Verisi</h3><p>{{ analiz.kurum.durum }}</p><p class="muted">{{ analiz.kurum.kaynak }}</p><p class="muted">Takas ve kademe verisi lisanslı/API kaynağı olmadan hesaba katılmadı.</p></div>
{% endif %}{% else %}<div class="card">Analiz için bir hisse sembolü girin.</div>{% endif %}
</div></body></html>
"""


HTML_HALKA_ARZ = """
<!DOCTYPE html><html><head><title>BIST AI - Halka Arz</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}.container{max-width:1000px;margin:auto}.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}.header h1{margin:0;color:#e94560;font-size:20px}.header p{margin:0;color:#dfeaff;font-size:12px}.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}.menu a{flex:1;min-width:80px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}.menu a.active{background:#e94560}.card{background:#16213e;padding:16px;border-radius:8px;margin:12px 0;border-left:4px solid #ff9800}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.metric{background:#0f3460;padding:12px;border-radius:6px}.metric span{color:#b0bec5;font-size:12px}.metric b{display:block;margin-top:5px;font-size:18px}.muted{color:#b0bec5;font-size:12px}.news{margin-top:10px}.news a{color:#cfe2ff}.takip{border-left-color:#4caf50}.bekliyor{border-left-color:#64b5f6}@media(max-width:650px){.grid{grid-template-columns:1fr 1fr}}
</style></head><body><div class="container"><div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p id="canli-saat" aria-live="polite"></p></div>
<div class="menu"><a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a><a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/halka-arz" class="active">Halka Arz</a><a href="/hedef">Hedef</a></div>
<div class="card"><h2>Halka Arz Takibi</h2><p class="muted">Son 6 halka arz. Piyasa başlangıcından itibaren 14 gün takip edilir.</p><p><b>{{ veri_sayisi }}</b> kayıt | <b>{{ fiyatli_veri_sayisi }}</b> son fiyat mevcut</p><a href="/halka-arz?yenile=1" style="display:inline-block;background:#e94560;color:white;text-decoration:none;padding:9px 14px;border-radius:5px;font-weight:bold">Veriyi şimdi yenile</a><p class="muted">Son kontrol: {{ son_guncelleme }}</p></div>
{% for h in son_alti %}<div class="card {% if h.durum == '14 GUN TAKIP' %}takip{% elif h.durum == 'BEKLENIYOR' %}bekliyor{% endif %}"><h3>{{ h.sembol }} | {{ h.sirket }}</h3><div class="grid"><div class="metric"><span>Halka arz tarihi</span><b>{{ h.talep_tarihi }}</b></div><div class="metric"><span>Arz fiyatı</span><b>{{ h.arz_fiyati }}</b></div><div class="metric"><span>İskonto</span><b>{{ h.iskonto }}</b></div><div class="metric"><span>İlk işlem tarihi</span><b>{{ h.borsa_baslangic }}</b></div><div class="metric"><span>Fiyat değişimi</span><b>{% if h.fiyat_degisim != 'Veri yok' %}{{ h.fiyat_degisim }}%{% else %}Veri yok{% endif %}</b></div></div><p class="muted">İlk işlem fiyatı: {{ h.ilk_islem_fiyati }} | Güncel fiyat: {{ h.guncel_fiyat }} | Durum: {{ h.durum }}{% if h.takip_bitis %} | Takip bitişi: {{ h.takip_bitis }}{% endif %}</p></div>{% else %}<div class="card"><p>Güncel halka arz duyurusu bulunamadı.</p></div>{% endfor %}
</div></body></html>
<script>
function cihazinSaatiniGoster() {
    var simdi = new Date();
    var tarih = simdi.toLocaleDateString('tr-TR', {
        day: '2-digit', month: '2-digit', year: 'numeric'
    });
    var saat = simdi.toLocaleTimeString('tr-TR', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    document.getElementById('canli-saat').textContent = tarih + ' ' + saat;
}
cihazinSaatiniGoster();
setInterval(cihazinSaatiniGoster, 1000);
</script>
"""


HTML_TARAMA = """
<!DOCTYPE html><html><head><title>BIST AI - Piyasa Tarama</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}.container{max-width:1100px;margin:auto}.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px}.header h1{margin:0;color:#e94560;font-size:20px}.header p{margin:0;color:#dfeaff;font-size:12px}.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}.menu a{flex:1;min-width:80px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}.menu a.active{background:#e94560}.ozet{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:15px 0}.kutu{background:#16213e;padding:15px;border-radius:8px;border-left:4px solid #4caf50}.kutu b{display:block;font-size:24px;margin-top:5px}.muted{color:#b0bec5;font-size:12px}.yenile{display:inline-block;background:#e94560;color:white;text-decoration:none;padding:9px 14px;border-radius:5px;font-weight:bold}.tablo{width:100%;border-collapse:collapse;background:#16213e;border-radius:8px;overflow:hidden}.tablo th,.tablo td{text-align:left;padding:11px 10px;border-bottom:1px solid #243659;font-size:13px}.tablo th{color:#b0bec5;font-size:11px;text-transform:uppercase}.tablo tr:hover{background:#193d70}.puan{font-weight:bold}.yuksek{color:#4caf50}.orta{color:#ffca28}.izle{color:#b0bec5}.ai{color:#cfe2ff;text-decoration:none}.ai:hover{text-decoration:underline}@media(max-width:700px){.ozet{grid-template-columns:1fr 1fr}.tablo{font-size:12px}.tablo th,.tablo td{padding:9px 6px}.tablo th:nth-child(4),.tablo td:nth-child(4){display:none}}
</style></head><body><div class="container"><div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarama.son_guncelleme }}</p></div>
<div class="menu"><a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a><a href="/tarama" class="active">Piyasa Tarama</a><a href="/halka-arz">Halka Arz</a></div>
<div class="ozet"><div class="kutu"><span class="muted">Sembol havuzu</span><b>{{ tarama.sembol_sayisi }}</b></div><div class="kutu"><span class="muted">Verisi gelen</span><b>{{ tarama.veri_sayisi }}</b></div><div class="kutu"><span class="muted">Güçlü aday</span><b>{{ tarama.adaylar|length }}</b></div><div class="kutu"><span class="muted">Son tarama</span><b>{{ tarama.son_guncelleme[11:] }}</b></div></div>
<p class="muted">Bu liste tavan garantisi vermez. Momentum, hacim ve trend birlikteliğine göre yüksek hareket adayı olarak sıralanır.</p><a class="yenile" href="/tarama?yenile=1">Piyasayı yeniden tara</a>
{% if tarama.adaylar %}<h2>En Güçlü Yükseliş Adayları</h2><table class="tablo"><thead><tr><th>Sembol</th><th>Fiyat</th><th>1 Gün</th><th>5 Gün</th><th>20 Gün</th><th>Hacim</th><th>Puan</th><th>Risk</th><th>AI</th></tr></thead><tbody>{% for h in tarama.adaylar %}<tr><td><b>{{ h.sembol }}</b></td><td>{{ h.fiyat }} TL</td><td class="{% if h.gunluk >= 0 %}yuksek{% else %}izle{% endif %}">{{ '%+.2f'|format(h.gunluk) }}%</td><td>{{ '%+.2f'|format(h.getiri_5g) }}%</td><td>{{ '%+.2f'|format(h.getiri_20g) }}%</td><td>{{ h.hacim_orani }}x</td><td class="puan {{ h.aday_seviyesi|lower }}">{{ h.aday_puani }}/100</td><td class="{{ 'izle' if h.risk_uyarisi != 'Normal' else 'yuksek' }}">{{ h.risk_uyarisi }}</td><td><a class="ai" href="/ai?sembol={{ h.sembol }}">Yorumla</a></td></tr>{% endfor %}</tbody></table>{% else %}<div class="kutu"><p>Henüz aday verisi alınamadı. Yenile düğmesini tekrar deneyin.</p></div>{% endif %}
</div></body></html>
"""


HTML_AI = """
<!DOCTYPE html>
<html>
<head><title>BIST AI</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:80px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}
.info-box{background:#16213e;padding:15px;border-radius:8px;margin:15px 0;text-align:center}
.tahmin-card{background:#16213e;padding:12px;margin:8px 0;border-radius:8px;display:flex;justify-content:space-between;align-items:center}
.tahmin-card .ad{font-weight:bold;font-size:16px}
.tahmin-card .fiyat{font-size:14px;color:#b0bec5;margin-top:3px}
.tahmin-card .degisim{font-size:20px;font-weight:bold}
.yukari{color:#4caf50}.asagi{color:#f44336}
.uyari{background:#0f3460;padding:10px;border-radius:5px;margin:10px 0;font-size:13px}
.ai-sorgu{display:grid;grid-template-columns:1fr auto;gap:10px;background:#16213e;padding:15px;border-radius:8px;margin:15px 0}
.ai-sorgu input{width:100%;padding:11px;border:1px solid rgba(255,255,255,.1);border-radius:5px;background:#0f3460;color:white;box-sizing:border-box;text-transform:uppercase}
.ai-sorgu button{padding:11px 18px;background:#e94560;color:white;border:0;border-radius:5px;cursor:pointer;font-weight:bold}
.geri-btn{display:inline-block;margin:0 0 15px;padding:10px 16px;background:#0f3460;color:#fff;text-decoration:none;border:1px solid #4f78ad;border-radius:5px;font-weight:bold}
.geri-btn:hover{background:#193d70}
.yorum-card{background:#16213e;padding:15px;border-radius:8px;margin:15px 0;border-left:4px solid #ff9800}
.yorum-card .yorum-meta{color:#b0bec5;font-size:13px;line-height:1.7}
.yorum-card p{white-space:pre-line;line-height:1.7}
.yarin-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:15px 0}
.yarin-card{background:#16213e;padding:14px;border-radius:8px;border-left:4px solid #4caf50}
.yarin-card .baslik{display:flex;justify-content:space-between;font-weight:bold}
.yarin-card .detay{color:#b0bec5;font-size:12px;margin-top:7px;line-height:1.6}
@media(max-width:600px){.yarin-grid{grid-template-columns:1fr}}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai" class="active">AI</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
</div>
<div class="info-box">
<h3>Ensemble AI Model</h3>
<p>Yarının yönünü; momentum, EMA trendi ve RSI ile tahmin eder.</p>
</div>
<form method="GET" action="/ai" class="ai-sorgu">
<input name="sembol" value="{{ sorgulanan_sembol or '' }}" placeholder="Hisse sembolü (örn. THYAO)" maxlength="6" pattern="[A-Za-z]{3,6}">
<button type="submit">Hisseyi yorumla</button>
</form>
<a class="geri-btn" href="/tarama">&lt; Tarama sayfasına dön</a>
{% if sorgulanan_sembol %}
{% if sorgu_sinyali %}
<div class="yorum-card"><h2>{{ sorgu_sinyali.sembol }} AI Yorumu</h2><p class="yorum-meta">Karar: <b>{{ sorgu_sinyali.karar }}</b> | Öncelik: <b>{{ sorgu_sinyali.oncelik }}</b> | Fiyat: <b>{{ sorgu_sinyali.fiyat }} TL</b><br>RSI: {{ sorgu_sinyali.rsi }} | MACD: {{ sorgu_sinyali.macd }}</p><p>{{ sorgu_yorumu }}</p></div>
{% else %}<div class="uyari">{{ sorgulanan_sembol }} için teknik sinyal üretilemedi. Sembolü kontrol edip tekrar deneyin.</div>{% endif %}
{% endif %}
{% if yarin_tahminleri %}
<h2>Yarın Yükselme İhtimali En Yüksek Hisseler</h2>
<div class="yarin-grid">
{% for t in yarin_tahminleri %}
<div class="yarin-card">
<div class="baslik"><span>{{ t.sembol }}</span><span class="{{ t.renk }}">{{ t.beklenen_yazi }}%</span></div>
<div class="detay">Bugün: {{ t.bugun }} TL → Yarın: {{ t.yarin }} TL<br>Olasılık skoru: {{ t.puan }}/100 | RSI: {{ t.rsi }} | Trend: {{ t.trend }}%</div>
</div>
{% endfor %}
</div>
{% endif %}
{% if bugun_yukselenler %}
<h2>Bugün Yükselen Hisselerin Yarın Tahmini</h2>
<div class="yarin-grid">
{% for t in bugun_yukselenler %}
<div class="yarin-card"><div class="baslik"><span>{{ t.sembol }}</span><span class="{{ t.renk }}">{{ t.beklenen_yazi }}%</span></div><div class="detay">Bugünkü değişim: +{{ t.bugun_getiri }}%<br>Yarın beklenen fiyat: {{ t.yarin }} TL</div></div>
{% endfor %}
</div>
{% endif %}
{% if sonuclar %}
<h2>5 Gunluk Tahminler</h2>
{% for t in sonuclar %}
<div class="tahmin-card">
<div><div class="ad">{{ t.sembol }}</div><div class="fiyat">{{ t.bugun }} TL -> {{ t.hedef }} TL</div></div>
<div class="degisim {{ t.renk }}">{{ t.degisim }}%</div>
</div>
{% endfor %}
<div class="uyari">NOT: AI tahminleri yatirim tavsiyesi degildir.</div>
{% else %}
<div class="uyari">Tahmin üretilemedi. Piyasa verisi bağlantısını ve sembol listesini kontrol edin.</div>
{% endif %}
</div>
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service-worker.js').catch(function (error) {
      console.log('Service worker kaydi basarisiz:', error);
    });
  });
}
</script>
</body></html>
"""

HTML_SINYAL = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Sinyaller</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BIST AI">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:70px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}
.sinyal-card{background:#16213e;padding:15px;margin:10px 0;border-radius:8px;border-left:5px solid #e94560}
.sinyal-card.sat{border-left-color:#f44336}
.sinyal-card.al{border-left-color:#4caf50}
.sinyal-baslik{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.sinyal-tip{font-size:22px;font-weight:bold;padding:5px 15px;border-radius:5px}
.tip-al{background:#4caf50;color:white}
.tip-sat{background:#f44336;color:white}
.sinyal-sembol{font-size:22px;font-weight:bold}
.sebep{display:inline-block;background:#0f3460;padding:4px 10px;margin:3px;border-radius:15px;font-size:13px}
.oncelik{display:inline-block;padding:3px 8px;border-radius:4px;font-size:12px;margin-right:10px;font-weight:bold}
.oncelik.yuksek{background:#f44336;color:white}
.info-box{background:#16213e;padding:15px;border-radius:8px;margin:15px 0;text-align:center}
.uyari{background:#5c1f1f;padding:10px;border-radius:5px;margin:10px 0;font-size:13px}
.ai-yorum{margin-top:12px;padding:11px 13px;background:#193d70;border-left:3px solid #ff9800;border-radius:5px;color:#e8f1ff;font-size:13px;line-height:1.6;white-space:pre-line}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }} | {{ toplam_sinyal }} aktif</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/sinyal" class="active">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
</div>
{% if sinyaller %}
{% for s in sinyaller %}
<div class="sinyal-card {{ s.karar|lower }}">
<div class="sinyal-baslik">
<div><span class="sinyal-sembol">{{ s.sembol }}</span><br><small style="color:#b0bec5">{{ s.fiyat }} TL</small></div>
<div class="sinyal-tip tip-{{ s.karar|lower }}">{{ s.karar }}</div>
</div>
<div>
<span class="oncelik {{ s.oncelik|lower }}">{{ s.oncelik }}</span>
</div>
<div>
{% for sebep in s.sebepler %}
<span class="sebep">{{ sebep }}</span>
{% endfor %}
</div>
<div class="ai-yorum"><b>AI yorumu:</b> {{ s.ai_yorum }}</div>
</div>
{% endfor %}
<div class="uyari">NOT: Bu sistem oneri verir. Kendi kararinizi kullanin.</div>
{% else %}
<div class="info-box"><p>Su an aktif sinyal yok.</p></div>
{% endif %}
</div>
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service-worker.js').catch(function (error) {
      console.log('Service worker kaydi basarisiz:', error);
    });
  });
}
</script>
</body></html>
"""

HTML_PANEL = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Panel</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BIST AI">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:900px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:70px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}
.dashboard{display:grid;grid-template-columns:1fr 1fr;gap:15px}
.card{background:#16213e;padding:15px;border-radius:8px}
.card h3{margin:0 0 10px 0;color:#4caf50;font-size:14px}
.stat-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #0f3460;font-size:13px}
.stat-row:last-child{border-bottom:none}
.pozitif{color:#4caf50}.negatif{color:#f44336}
.sinyal-mini{background:#0f3460;padding:8px;margin:5px 0;border-radius:5px;font-size:13px}
.sinyal-mini.al{border-left:3px solid #4caf50}
.sinyal-mini.sat{border-left:3px solid #f44336}
.yenile-btn{display:block;text-align:center;padding:12px;background:#e94560;color:white;text-decoration:none;border-radius:8px;margin:15px 0;font-weight:bold}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel" class="active">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
</div>
<a href="/panel" class="yenile-btn">Yenile</a>
<div class="dashboard">
<div class="card">
<h3>Portfoy Durumu</h3>
<div class="stat-row"><span>Toplam Deger:</span><b>{{ portfoy.toplam_deger }} TL</b></div>
<div class="stat-row"><span>Hisse Sayisi:</span><b>{{ portfoy.hisse_sayisi }}</b></div>
<div class="stat-row"><span>Toplam Kar:</span><b class="{{ portfoy.renk }}">{{ portfoy.toplam_kar }} TL</b></div>
</div>
<div class="card">
<h3>Risk Puani</h3>
<div class="stat-row"><span>Cesitlendirme:</span><b>{{ risk.puan }}/100</b></div>
<div class="stat-row"><span>Durum:</span><b>{{ risk.durum }}</b></div>
</div>
<div class="card">
<h3>AI En Iyi 3 (5 gun)</h3>
{% for ai in ai_tahminleri[:3] %}
<div class="stat-row"><span>{{ ai.sembol }}</span><b class="{{ ai.renk }}">{{ ai.degisim }}%</b></div>
{% endfor %}
</div>
<div class="card">
<h3>Sektor En Iyiler</h3>
{% for s in sektorler[:3] %}
<div class="stat-row"><span>{{ s.sektor }}</span><b class="{{ s.renk }}">{{ s.ortalama }}</b></div>
{% endfor %}
</div>
<div class="card" style="grid-column:1 / -1">
<h3>Aktif Sinyaller</h3>
{% for s in sinyaller %}
<div class="sinyal-mini {{ s.karar|lower }}"><b>{{ s.karar }}</b> - {{ s.sembol }} - {{ s.fiyat }} TL - {{ s.oncelik }}</div>
{% endfor %}
{% if not sinyaller %}<p style="color:#b0bec5">Su an aktif sinyal yok.</p>{% endif %}
</div>
</div>
</div>
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service-worker.js').catch(function (error) {
      console.log('Service worker kaydi basarisiz:', error);
    });
  });
}
</script>
</body></html>
"""

HTML_HEDEF = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Hedef</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:70px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}.menu a.cikis{background:#f44336}
.hedef-card{background:#16213e;padding:15px;margin:10px 0;border-radius:8px;border-left:4px solid #4caf50}
.baslik{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.sembol{font-weight:bold;font-size:18px}
.fiyat-alani{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;margin:15px 0;padding:15px;background:#0f3460;border-radius:8px}
.fiyat-kutu{text-align:center}
.fiyat-deger{font-size:20px;font-weight:bold;margin-top:5px}
.detay-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.detay-kutu{background:#0f3460;padding:10px;border-radius:5px}
.detay-deger{font-size:14px;font-weight:bold;margin-top:3px}
.info-box{background:#16213e;padding:15px;border-radius:8px;margin:15px 0;text-align:center}
.sorgu-form{display:grid;grid-template-columns:1fr auto;gap:10px;background:#16213e;padding:15px;border-radius:8px;margin:15px 0}
.sorgu-form input{width:100%;padding:11px;border:0;border-radius:5px;background:#0f3460;color:white;box-sizing:border-box}
.sorgu-form button{padding:11px 18px;background:#e94560;color:white;border:0;border-radius:5px;cursor:pointer;font-weight:bold}
.uzun-vade-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:15px}
.uzun-vade-kutu{background:#0f3460;padding:12px;border-radius:6px;text-align:center}
.uzun-vade-kutu b{display:block;font-size:18px;margin-top:5px}
.uzun-vade-kutu{border:1px solid transparent;color:white;cursor:pointer;width:100%}
.uzun-vade-kutu.aktif{border-color:#e94560;background:#193d70}
.trend-grafik{width:100%;height:150px;background:#0f3460;border-radius:6px;margin-top:15px}
.donem-butonu{padding:10px 14px;background:#0f3460;color:white;border:1px solid rgba(255,255,255,.12);border-radius:6px;cursor:pointer;font-weight:bold}
.donem-butonu.aktif{background:#e94560;border-color:#e94560}
.grafik-baslik{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:16px}
.donem-butonlari{display:flex;gap:8px;flex-wrap:wrap}
@media(max-width:600px){.sorgu-form{grid-template-columns:1fr}.uzun-vade-grid{grid-template-columns:1fr}}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef" class="active">Hedef</a><a href="/bildirim">Bildirim</a>
<a href="/cikis" class="cikis">Cikis</a>
</div>
<form method="GET" action="/hedef" class="sorgu-form">
<input name="sembol" placeholder="Sadece hisse adı yazın (örn: THYAO)" value="{{ sorgulanan_sembol or '' }}" required>
<button type="submit">Hisseyi Kontrol Et</button>
</form>
{% if sorgulanan_sembol and not hedefler %}
<div class="info-box"><p>{{ sorgulanan_sembol }} için yeterli piyasa verisi bulunamadı.</p></div>
{% endif %}
{% if hedefler %}
{% for h in hedefler %}
<div class="hedef-card">
<div class="baslik"><span class="sembol">{{ h.sembol }}</span><b>Trend: {{ h.trend }}</b></div>
<div class="fiyat-kutu"><div>Güncel fiyat</div><div class="fiyat-deger">{{ h.guncel }} TL</div></div>
<div class="uzun-vade-grid">
<button class="uzun-vade-kutu aktif" type="button" onclick="donemGrafikGoster(this, '{{ h.grafik_3_ay }}', 'Son 3 Ay', '{{ h.indikator_3_ay.ema50 }}', '{{ h.indikator_3_ay.ema200 }}', '{{ h.indikator_3_ay.macd }}', '{{ h.indikator_3_ay.rsi }}')"><span>3 Ay</span><b>{{ h.hedefler[3].fiyat }} TL</b><span>{{ h.hedefler[3].degisim }}%</span></button>
<button class="uzun-vade-kutu" type="button" onclick="donemGrafikGoster(this, '{{ h.grafik_6_ay }}', 'Son 6 Ay', '{{ h.indikator_6_ay.ema50 }}', '{{ h.indikator_6_ay.ema200 }}', '{{ h.indikator_6_ay.macd }}', '{{ h.indikator_6_ay.rsi }}')"><span>6 Ay</span><b>{{ h.hedefler[6].fiyat }} TL</b><span>{{ h.hedefler[6].degisim }}%</span></button>
<button class="uzun-vade-kutu" type="button" onclick="donemGrafikGoster(this, '{{ h.grafik_9_ay }}', 'Son 9 Ay', '{{ h.indikator_9_ay.ema50 }}', '{{ h.indikator_9_ay.ema200 }}', '{{ h.indikator_9_ay.macd }}', '{{ h.indikator_9_ay.rsi }}')"><span>9 Ay</span><b>{{ h.hedefler[9].fiyat }} TL</b><span>{{ h.hedefler[9].degisim }}%</span></button>
</div>
<div class="grafik-baslik"><b>Trend Grafiği</b></div>
<svg id="trend-grafik-{{ h.sembol }}" class="trend-grafik" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="{{ h.sembol }} son 3 ay trend grafiği"><polyline points="{{ h.grafik_3_ay }}" fill="none" stroke="#4caf50" stroke-width="1.5" vector-effect="non-scaling-stroke" /></svg>
<div class="grafik-baslik"><b>İndikatörler: EMA 50 / EMA 200 / MACD / RSI</b></div>
<svg class="trend-grafik" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="EMA indikatör grafiği"><polyline class="ema50" points="{{ h.indikator_3_ay.ema50 }}" fill="none" stroke="#ff9800" stroke-width="1.2" vector-effect="non-scaling-stroke" /><polyline class="ema200" points="{{ h.indikator_3_ay.ema200 }}" fill="none" stroke="#e94560" stroke-width="1.2" vector-effect="non-scaling-stroke" /></svg>
<svg class="trend-grafik" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="MACD indikatör grafiği"><polyline class="macd" points="{{ h.indikator_3_ay.macd }}" fill="none" stroke="#4caf50" stroke-width="1.2" vector-effect="non-scaling-stroke" /></svg>
<svg class="trend-grafik" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="RSI indikatör grafiği"><polyline class="rsi" points="{{ h.indikator_3_ay.rsi }}" fill="none" stroke="#64b5f6" stroke-width="1.2" vector-effect="non-scaling-stroke" /></svg>
<div class="detay-grid"><div class="detay-kutu"><div>Yıllık volatilite</div><div class="detay-deger">%{{ h.volatilite }}</div></div><div class="detay-kutu"><div>Analiz dönemi</div><div class="detay-deger">İlk günden bugüne ({{ h.gecmis_yil }} yıl)</div></div><div class="detay-kutu"><div>EMA 50 / EMA 200</div><div class="detay-deger">{{ h.ema50 }} / {{ h.ema200 }} TL</div></div><div class="detay-kutu"><div>Destek / Direnç</div><div class="detay-deger">{{ h.destek }} / {{ h.direnc }} TL</div></div></div>
</div>
{% endfor %}
{% elif not sorgulanan_sembol %}<div class="info-box"><p>3, 6 ve 9 aylık hedefleri görmek için bir hisse adı yazın.</p></div>{% endif %}
</div></body></html>
<script>
function donemGrafikGoster(buton, noktalar, donem, ema50, ema200, macd, rsi) {
    var kart = buton.closest('.hedef-card');
    var grafik = kart.querySelector('.trend-grafik');
    grafik.querySelector('polyline').setAttribute('points', noktalar);
    var grafikler = kart.querySelectorAll('.trend-grafik');
    grafikler[1].querySelector('.ema50').setAttribute('points', ema50);
    grafikler[1].querySelector('.ema200').setAttribute('points', ema200);
    grafikler[2].querySelector('.macd').setAttribute('points', macd);
    grafikler[3].querySelector('.rsi').setAttribute('points', rsi);
    grafik.setAttribute('aria-label', donem + ' trend grafiği');
    buton.closest('.uzun-vade-grid').querySelectorAll('.uzun-vade-kutu').forEach(function (item) { item.classList.remove('aktif'); });
    buton.classList.add('aktif');
}
</script>
"""

HTML_BILDIRIM = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Bildirim</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BIST AI">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
.header h1{margin:0;color:#e94560;font-size:20px}
.header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
.header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:70px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}.menu a.cikis{background:#f44336}
.ayar-kutu{background:#16213e;padding:20px;border-radius:8px;margin-bottom:20px}
.ayar-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #0f3460}
.switch{position:relative;display:inline-block;width:50px;height:24px}
.switch input{display:none}
.slider{position:absolute;cursor:pointer;inset:0;background:#607d8b;border-radius:24px;transition:.3s}
.slider:before{position:absolute;content:"";height:18px;width:18px;left:3px;bottom:3px;background:white;border-radius:50%;transition:.3s}
input:checked + .slider{background:#4caf50}
input:checked + .slider:before{transform:translateX(26px)}
select{background:#0f3460;color:white;border:none;padding:8px 12px;border-radius:5px;font-size:14px}
.btn{padding:10px 20px;background:#e94560;color:white;border:none;border-radius:5px;cursor:pointer;font-size:14px}
.bildirim{background:#16213e;padding:12px;margin:8px 0;border-radius:8px;border-left:4px solid #e94560}
.basarili{background:#4caf50;padding:10px;border-radius:5px;margin-bottom:15px;text-align:center}
</style></head>
<body>
<div class="container">
<div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/istihbarat">Istihbarat</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a>
<a href="/bildirim" class="active">Bildirim</a><a href="/cikis" class="cikis">Cikis</a>
</div>
{% if mesaj %}<div class="{{ sinif }}">{{ mesaj }}</div>{% endif %}
<div class="ayar-kutu">
<h3>Bildirim Tercihleri</h3>
<form method="POST">
<div class="ayar-row">
<span><b>Aktif:</b></span>
<label class="switch">
<input type="checkbox" name="aktif" {% if ayarlar.aktif %}checked{% endif %}>
<span class="slider"></span>
</label>
</div>
<div class="ayar-row">
<span><b>Bildirim saati:</b></span>
<input type="time" name="saat" value="{{ ayarlar.saat or '09:00' }}" required>
</div>
<div class="ayar-row">
<span><b>Tur:</b></span>
<select name="tur">
<option value="hepsi" {% if ayarlar.tur == 'hepsi' %}selected{% endif %}>Hepsi</option>
<option value="AL" {% if ayarlar.tur == 'AL' %}selected{% endif %}>Sadece AL</option>
<option value="SAT" {% if ayarlar.tur == 'SAT' %}selected{% endif %}>Sadece SAT</option>
</select>
</div>
<div style="text-align:center;margin-top:20px">
<button class="btn" type="submit">Ayarlari Kaydet</button>
</div>
</form>
</div>
</div>
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/service-worker.js').catch(function (error) {
      console.log('Service worker kaydi basarisiz:', error);
    });
  });
}
</script>
</body></html>
"""


# ============================================
# ROUTES
# ============================================
@app.route("/giris", methods=["GET", "POST"])
def giris():
    if request.method == "POST":
        basarili, sonuc = kullanici_yoneticisi.giris_yap(
            request.form.get("kullanici_adi", ""),
            request.form.get("sifre", ""),
        )
        if basarili:
            response = make_response(redirect(url_for("index")))
            response.set_cookie("session_token", sonuc, max_age=30 * 24 * 3600, httponly=True, samesite="Lax", secure=app.config['SESSION_COOKIE_SECURE'])
            return response
        return render_template_string(HTML_LOGIN, hata=sonuc)
    return render_template_string(HTML_LOGIN, hata=None)


@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    if request.method == "POST":
        basarili, sonuc = kullanici_yoneticisi.kayit_ol(
            request.form.get("kullanici_adi", ""),
            request.form.get("sifre", ""),
            request.form.get("email", ""),
        )
        if basarili:
            response = make_response(redirect(url_for("index")))
            response.set_cookie("session_token", sonuc, max_age=30 * 24 * 3600, httponly=True, samesite="Lax", secure=app.config['SESSION_COOKIE_SECURE'])
            return response
        return render_template_string(HTML_KAYIT, hata=sonuc)
    return render_template_string(HTML_KAYIT, hata=None)


@app.route("/cikis")
def cikis():
    token = request.cookies.get("session_token")
    if token:
        kullanici_yoneticisi.cikis_yap(token)
    response = make_response(redirect(url_for("giris")))
    response.delete_cookie("session_token")
    return response


@app.route("/")
def index():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
    veri = portfoy_veri_hazirla_icin(portfoy_hisseler)
    risk_ozeti = portfoy_risk_hesapla(portfoy_hisseler) if portfoy_hisseler else None
    if risk_ozeti:
        risk_ozeti["risk_renk"] = risk_renk_hesapla(risk_ozeti.get("genel_risk", 0))
        risk_ozeti["risk_seviye"] = risk_seviyesi_hesapla(risk_ozeti.get("genel_risk", 0))
        risk_ozeti["puan_yorum"] = risk_yorum_uret(risk_ozeti.get("cesitlendirme", 0))
    return render_template_string(HTML_PORTFOY, **veri, kullanici=kullanici, risk_ozeti=risk_ozeti)


@app.route("/ekle", methods=["POST"])
def hisse_ekle():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))
        sembol = request.form["sembol"]
        adet = int(request.form["adet"])
        fiyat = float(request.form["fiyat"])
        stop_loss = float(request.form.get("stop_loss", 0) or 0)
        kar_hedef = float(request.form.get("kar_hedef", 0) or 0)
        portfoy = kullanici_yoneticisi.portfoy_al(kullanici)
        sembol = sembol.upper().replace(".IS", "")
        mevcut = next((h for h in portfoy if h["sembol"] == sembol), None)
        if mevcut:
            toplam_adet = mevcut["adet"] + adet
            mevcut["alis_fiyati"] = round(
                (mevcut["adet"] * mevcut["alis_fiyati"] + adet * fiyat) / toplam_adet, 2)
            mevcut["adet"] = toplam_adet
            mevcut["stop_loss"] = stop_loss or mevcut.get("stop_loss", 0)
            mevcut["kar_hedef"] = kar_hedef or mevcut.get("kar_hedef", 0)
        else:
            portfoy.append({"sembol": sembol, "adet": adet, "alis_fiyati": fiyat, "stop_loss": stop_loss, "kar_hedef": kar_hedef})
        kullanici_yoneticisi.portfoy_kaydet(kullanici, portfoy)
        kullanici_yoneticisi.islem_kaydet(kullanici, sembol, "ALIS", adet, fiyat)
        return redirect(url_for("index"))
    except Exception as e:
        return f"<h1>Hata</h1><p>{e}</p><a href='/'>Geri don</a>"


@app.route("/sat", methods=["POST"])
def hisse_sat():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))
        sembol = (request.form.get("sembol", "") or "").upper().replace(".IS", "")
        adet = int(request.form.get("adet", 0) or 0)
        fiyat = float(request.form.get("fiyat", 0) or 0)
        if not sembol or adet <= 0 or fiyat <= 0:
            return "Geçerli sembol, adet ve fiyat girin.", 400
        if not kullanici_yoneticisi.hisse_sat(kullanici, sembol, adet, fiyat):
            return "Satış yapılamadı: hisse bulunamadı veya adet yetersiz.", 400
        return redirect(url_for("index"))
    except (TypeError, ValueError):
        return "Adet ve fiyat sayısal olmalıdır.", 400


@app.route("/islemler")
def islemler():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    islemler = kullanici_yoneticisi.islemleri_al(kullanici)
    satirlar = "".join(f"<tr><td>{s}</td><td>{i}</td><td>{a}</td><td>{f:.2f}</td><td>{t}</td></tr>" for s, i, a, f, t in islemler)
    return f"<h1>İşlem Geçmişi</h1><table><tr><th>Hisse</th><th>İşlem</th><th>Adet</th><th>Fiyat</th><th>Tarih</th></tr>{satirlar}</table>"


@app.route("/portfoy.csv")
def portfoy_csv():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    cikti = io.StringIO()
    yazici = csv.writer(cikti)
    yazici.writerow(["Sembol", "Adet", "Alis Fiyati"])
    for hisse in kullanici_yoneticisi.portfoy_al(kullanici):
        yazici.writerow([hisse.get("sembol", ""), hisse.get("adet", 0), hisse.get("alis_fiyati", 0)])
    response = make_response(cikti.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=portfoy.csv"
    return response


@app.route("/portfoy.xlsx")
def portfoy_xlsx():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        import xlsxwriter
        cikti = io.BytesIO()
        kitap = xlsxwriter.Workbook(cikti, {"in_memory": True})
        sayfa = kitap.add_worksheet("Portfoy")
        sayfa.write_row(0, 0, ["Sembol", "Adet", "Alis Fiyati", "Stop Loss", "Kar Hedefi"])
        for satir, hisse in enumerate(kullanici_yoneticisi.portfoy_al(kullanici), 1):
            sayfa.write_row(satir, 0, [hisse.get("sembol", ""), hisse.get("adet", 0), hisse.get("alis_fiyati", 0), hisse.get("stop_loss", 0), hisse.get("kar_hedef", 0)])
        kitap.close()
        response = make_response(cikti.getvalue())
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response.headers["Content-Disposition"] = "attachment; filename=portfoy.xlsx"
        return response
    except ImportError:
        return "Excel aktarımı için xlsxwriter kurulmalı.", 503


@app.route("/performans")
def performans():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    portfoy = kullanici_yoneticisi.portfoy_al(kullanici)
    donem = request.args.get("donem", "3mo")
    if donem not in {"1mo", "3mo", "6mo", "1y"}:
        donem = "3mo"
    toplam = sum(float(h.get("adet", 0)) * float(h.get("alis_fiyati", 0)) for h in portfoy)
    seri_listesi = []
    for hisse in portfoy:
        try:
            sembol = normalize_bist_sembol(hisse.get("sembol"))
            fiyatlar = cacheli_gecmis(f"{sembol}.IS", period=donem, auto_adjust=True)["Close"].dropna().astype(float)
            if len(fiyatlar) > 1 and float(fiyatlar.iloc[0]) > 0:
                agirlik = (float(hisse.get("adet", 0)) * float(hisse.get("alis_fiyati", 0))) / toplam if toplam else 0
                seri_listesi.append((fiyatlar / float(fiyatlar.iloc[0]) * agirlik, fiyatlar))
        except Exception:
            continue
    if seri_listesi:
        uzunluk = min(len(seri) for seri, _ in seri_listesi)
        performans_serisi = sum((seri.tail(uzunluk).reset_index(drop=True) for seri, _ in seri_listesi))
        performans_serisi = performans_serisi / float(performans_serisi.iloc[0]) * 100
        minimum, maksimum = float(performans_serisi.min()), float(performans_serisi.max())
        aralik = max(0.01, maksimum - minimum)
        noktalar = " ".join(f"{round(i * 100 / max(1, len(performans_serisi) - 1), 1)},{round(100 - (float(deger) - minimum) * 90 / aralik, 1)}" for i, deger in enumerate(performans_serisi))
        son_performans = round(float(performans_serisi.iloc[-1]) - 100, 2)
    else:
        noktalar, son_performans = "0,50 100,50", 0.0
    mevcut_deger = round(sum(float(h.get("adet", 0)) * float(h.get("alis_fiyati", 0)) for h in portfoy), 2)
    grafik_durumu = "Aktif fiyat verisi bulunamadı; sembolü ve işlem kaydını kontrol edin." if not seri_listesi else ""
    return render_template_string("""
    <h1>Portföy Performansı</h1><p>Başlangıç maliyeti: {{ toplam|round(2) }} TL | Dönem getirisi: {{ son_performans }}%</p>
    <p><a href="/performans?donem=1mo">1 Ay</a> | <a href="/performans?donem=3mo">3 Ay</a> | <a href="/performans?donem=6mo">6 Ay</a> | <a href="/performans?donem=1y">1 Yıl</a></p>
    <svg viewBox="0 0 100 100" width="100%" height="240" style="background:#16213e"><polyline points="{{ noktalar }}" fill="none" stroke="#4caf50" stroke-width="2" /></svg>
    <p>Grafik, seçilen dönemdeki portföy hisselerinin ağırlıklı normalize getirisini gösterir.</p>
    {% if grafik_durumu %}<p style="color:#ff9800">{{ grafik_durumu }}</p>{% endif %}
    <a href="/">Portföye dön</a>
    """, toplam=toplam, noktalar=noktalar, son_performans=son_performans, mevcut_deger=mevcut_deger, grafik_durumu=grafik_durumu)


@app.route("/admin")
def admin():
    kullanici = aktif_kullanici_al()
    admin_adi = os.environ.get("ADMIN_USERNAME", "admin").lower()
    if not kullanici or kullanici.lower() != admin_adi:
        return "Yetkisiz erişim", 403
    kullanicilar = kullanici_yoneticisi.kullanicilari_al()
    satirlar = "".join(
        f"<tr><td>{ad}</td><td>{email}</td><td>{tarih}</td>"
        f"<td><form method='POST' action='/admin/kullanici-sil/{ad}'><button>Sil</button></form></td></tr>"
        for ad, email, tarih in kullanicilar
    )
    return f"<h1>Yönetici Paneli</h1><table><tr><th>Kullanıcı</th><th>Email</th><th>Kayıt</th><th>İşlem</th></tr>{satirlar}</table>"


@app.route("/admin/kullanici-sil/<kullanici_adi>", methods=["POST"])
def admin_kullanici_sil(kullanici_adi):
    kullanici = aktif_kullanici_al()
    admin_adi = os.environ.get("ADMIN_USERNAME", "admin").lower()
    if not kullanici or kullanici.lower() != admin_adi:
        return "Yetkisiz erişim", 403
    if kullanici_adi.lower() == admin_adi:
        return "Yönetici hesabı silinemez", 400
    kullanici_yoneticisi.kullanici_sil(kullanici_adi)
    return redirect(url_for("admin"))


@app.route("/risk-sorgula", methods=["POST"])
def risk_sorgula():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))

        sembol = (request.form.get("sembol", "") or "").upper().replace(".IS", "")
        if not sembol:
            return redirect(url_for("risk"))
        return redirect(url_for("risk", sembol=sembol))
    except Exception as e:
        return f"<h1>Hata</h1><p>{e}</p><a href='/'>Geri don</a>"


@app.route("/temizle")
def portfoy_temizle():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))
        kullanici_yoneticisi.portfoy_kaydet(kullanici, [])
        return redirect(url_for("index"))
    except Exception as e:
        return f"Hata: {e}"


@app.route("/hisse-sil/<sembol>")
def hisse_sil(sembol):
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    basarili = kullanici_yoneticisi.hisse_sil(kullanici, sembol)
    if basarili:
        return redirect(url_for("index"))
    return f"<h1>Hata</h1><p>{sembol} portfoyde bulunamadi.</p><a href='/'>Geri don</a>"


@app.route("/sektor")
def sektor():
    veriler = sektor_analiz_yap()
    sektorler = []
    for ad, hisseler in veriler.items():
        ortalama = sum(h["gunluk"] for h in hisseler) / len(hisseler)
        sektorler.append({
            "sektor": ad,
            "hisse_sayisi": len(hisseler),
            "ortalama": f"{ortalama:+.2f}",
            "renk": "pozitif" if ortalama >= 0 else "negatif",
            "emoji": "YUKARI" if ortalama >= 0 else "ASAGI",
        })
    sektorler.sort(key=lambda x: float(x["ortalama"]), reverse=True)
    return render_template_string(
        HTML_SEKTOR,
        tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        sektorler=sektorler,
        en_iyi=sektorler[0]["sektor"] if sektorler else None,
        en_kotu=sektorler[-1]["sektor"] if sektorler else None,
    )


@app.route("/manifest.json")
def manifest():
    from flask import send_from_directory
    return send_from_directory(".", "manifest.json", mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    from flask import send_from_directory
    response = send_from_directory(".", "service-worker.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/risk")
def risk():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))

        sembol = (request.args.get("sembol", "") or "").upper().replace(".IS", "")
        tek_hisse_analizi = tek_hisse_teknik_risk_hesapla(sembol) if sembol else None
        tek_hisse_renk = teknik_skor_renk_hesapla(tek_hisse_analizi["ortalama"]) if tek_hisse_analizi else "#607d8b"
        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        if not portfoy_hisseler:
            return render_template_string(
                HTML_RISK,
                tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
                toplam_deger="0", toplam_maliyet="0",
                toplam_kar="0", toplam_kar_yuzde=0,
                portfoy_sharpe="0", portfoy_volatilite="0",
                portfoy_var="0", portfoy_beta="0",
                cesitlendirme="0", genel_risk="0",
                risk_seviye="VERI YOK", risk_renk="#607d8b",
                puan_yorum="Portfoye hisse ekleyin.",
                hisse_verileri=[], korelasyonlar=[], oneriler=[],
                tek_hisse_analizi=tek_hisse_analizi,
                tek_hisse_renk=tek_hisse_renk,
                sorgulanan_sembol=sembol
            )
    except Exception:
        app.logger.exception("Risk sayfasi kullanici verisi yuklenemedi")
        return redirect(url_for("giris"))

    try:
        sonuc = portfoy_risk_hesapla(portfoy_hisseler)
        if sonuc is None:
            return "Risk analizi yapilamadi."

        if not sonuc:
            return "Risk analizi yapilamadi."

        puan = sonuc["cesitlendirme"]
        puan_yorum = risk_yorum_uret(puan)
        if "risk_renk" not in sonuc:
            sonuc["risk_renk"] = risk_renk_hesapla(sonuc.get("genel_risk", 0))
        if "risk_seviye" not in sonuc:
            sonuc["risk_seviye"] = risk_seviyesi_hesapla(sonuc.get("genel_risk", 0))

        return render_template_string(
            HTML_RISK,
            **sonuc,
            puan=puan,
            puan_yorum=puan_yorum,
            tek_hisse_analizi=tek_hisse_analizi,
            tek_hisse_renk=tek_hisse_renk,
            sorgulanan_sembol=sembol,
        )
    except Exception as e:
        return f"Risk analizi yapilamadi. Hata: {str(e)[:80]}"


@app.route("/teknik")
def teknik_analiz_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    sembol = normalize_bist_sembol(request.args.get("sembol", "") or "THYAO")
    try:
        analiz = hisse_teknik_analiz(f"{sembol}.IS")
    except Exception:
        app.logger.exception("Teknik analiz verisi alinamadi: %s", sembol)
        analiz = None

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Teknik Analiz - {{ sembol }}</title><style>
    body{font-family:Arial;background:#1a1a2e;color:#fff;margin:0;padding:15px}.container{max-width:1050px;margin:auto}.header,.card{background:#16213e;border-radius:8px;padding:18px;margin-bottom:15px}.header h1{margin:0;color:#e94560;font-size:22px}.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}.menu a{flex:1;min-width:90px;padding:8px;background:#0f3460;color:#fff;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}.menu a.active{background:#e94560}form{display:flex;gap:8px}input,button{padding:10px;border-radius:6px;border:0}input{flex:1;background:#0f3460;color:#fff;border:1px solid #35506d}button{background:#e94560;color:#fff;font-weight:bold;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}.metric{background:#1e293b;padding:14px;border-radius:6px}.metric small{color:#b0bec5;display:block}.metric strong{font-size:21px;display:block;margin-top:6px}.signal{padding:9px;background:#1e293b;border-left:3px solid #e94560;margin:7px 0;border-radius:4px}.error{color:#ffb4b4}
    </style></head><body><div class="container"><div class="header"><h1>Teknik Analiz</h1><p>{{ sembol }} icin guncel gostergeler</p></div><div class="menu"></div>
    <div class="card"><form method="get"><input name="sembol" value="{{ sembol }}" placeholder="Ornek: THYAO"><button type="submit">Analiz Et</button></form></div>
    {% if analiz %}<div class="card"><h2>{{ analiz.Sembol }}: {{ analiz.Karar }}</h2><div class="grid">
    {% for etiket, deger in [("Fiyat", analiz.Fiyat ~ " TL"), ("RSI", analiz.RSI), ("MACD", analiz.MACD), ("SMA 20", analiz["SMA 20"]), ("SMA 50", analiz["SMA 50"]), ("Destek", analiz.Destek), ("Direnc", analiz["Direnç"]), ("Skor", analiz.Skor)] %}<div class="metric"><small>{{ etiket }}</small><strong>{{ deger }}</strong></div>{% endfor %}
    </div></div><div class="card"><h2>Sinyaller</h2>{% for sinyal in analiz.Sinyaller %}<div class="signal">{{ sinyal }}</div>{% endfor %}</div>
    {% else %}<div class="card error">{{ sembol }} icin yeterli piyasa verisi alinamadi. Lutfen daha sonra tekrar deneyin.</div>{% endif %}
    </div></body></html>
    """, sembol=sembol, analiz=analiz)


@app.route("/temel")
def temel_analiz_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    sembol = normalize_bist_sembol(request.args.get("sembol", "") or "")
    if not sembol:
        sembol = "THYAO"

    analiz = temel_analiz(sembol) or {
        "sembol": sembol,
        "fiyat": 0,
        "degisim": 0,
        "fk": None,
        "pddd": None,
        "temettu_verimi": None,
        "market_cap_milyar": 0,
        "gelir_buyumesi": None,
        "kar_buyumesi": None,
        "kar_marji": None,
        "roe": None,
        "sektor": "Bilinmiyor",
        "endustri": "Bilinmiyor",
        "genel_degerlendirme": "Veri bulunamadi",
        "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    def deger_ve_aciklama(etiket, deger, aciklama, birim=""):
        if deger is None:
            deger_yazi = "Veri yok"
        elif birim:
            deger_yazi = f"{deger}{birim}"
        else:
            deger_yazi = str(deger)
        return {"etiket": etiket, "deger": deger_yazi, "aciklama": aciklama}

    metrikler = [
        deger_ve_aciklama(
            "F/K",
            analiz.get("fk"),
            "Hisse fiyatının net karına göre ne kadar pahalı/ucuz olduğunu gösterir. Düşükse genelde daha uygun fiyatlanmış olabilir.",
            ""
        ),
        deger_ve_aciklama(
            "F/K (Forward)",
            analiz.get("fk_forward"),
            "Gelecek yıldaki kar beklentisine göre fiyatın oranı. Gelecek büyüme güçlü ise bu oran daha yüksek olabilir.",
            ""
        ),
        deger_ve_aciklama(
            "P/B",
            analiz.get("pddd"),
            "Fiyatın defter değerine oranıdır. 1'in altı çok güçlü değerlenme, 3 civarı normal/olumlu olabilir.",
            ""
        ),
        deger_ve_aciklama(
            "FD/FAVÖK",
            analiz.get("fd_favok"),
            "Şirketin değerinin operasyonel karına oranı. Düşükse şirket daha ucuza alınıyor olabilir.",
            ""
        ),
        deger_ve_aciklama(
            "Temettü verimi",
            analiz.get("temettu_verimi"),
            "Şirketin kârından hissedaraya dağıtılan temettü oranı. Yüksek temettü, gelir odaklı yatırım için önemlidir.",
            "%"
        ),
        deger_ve_aciklama(
            "ROE",
            analiz.get("roe"),
            "Öz kaynak kârlılığı. Yüksek ROE, şirketin sermayeyi verimli kullandığını gösterir.",
            "%"
        ),
        deger_ve_aciklama(
            "Kar marjı",
            analiz.get("kar_marji"),
            "Satıştan ne kadar kâr kaldığını gösterir. Yüksek marj, rekabet gücü ve verimlilik demektir.",
            "%"
        ),
        deger_ve_aciklama(
            "Borç / Öz kaynak",
            analiz.get("borc_ozkaynak"),
            "Şirketin borcunun öz kaynak içindeki ağırlığı. Düşük değer daha güvenli kabul edilir.",
            ""
        ),
        deger_ve_aciklama(
            "Gelir büyümesi",
            analiz.get("gelir_buyumesi"),
            "Şirketin gelirinin yıllık olarak ne kadar büyüdüğünü gösterir. Güçlü büyüme, uzun vadeli değeri artırabilir.",
            "%"
        ),
        deger_ve_aciklama(
            "Kar büyümesi",
            analiz.get("kar_buyumesi"),
            "Şirketin kârının büyüme hızı. Gelir büyümesi kadar önemli bir göstergedir; veri yoksa bu alanda net bilgi bulunamadı.",
            "%"
        ),
        deger_ve_aciklama(
            "52 haftalık yüksek",
            analiz.get("hafta_52_yuksek"),
            "Son 52 haftadaki en yüksek fiyat. Hisse bu seviyeye yakınsa güçlü görünüm olabilir.",
            ""
        ),
        deger_ve_aciklama(
            "52 haftalık düşük",
            analiz.get("hafta_52_dusuk"),
            "Son 52 haftadaki en düşük fiyat. Bu seviyelere yakınsa belirli bir değerleme olabilir.",
            ""
        ),
    ]

    if analiz.get("fk") is not None and analiz.get("pddd") is not None and analiz.get("roe") is not None:
        kisa_degerlendirme = (
            "Bu hisse için temel görünüm şu: "
            f"F/K {analiz.get('fk')}, P/B {analiz.get('pddd')} ve ROE %{analiz.get('roe')} ile "
            "şirketin değerleme ve kârlılık profilini birlikte değerlendiriyoruz."
        )
    else:
        kisa_degerlendirme = "Bu hisse için bazı temel veriler eksik; değeri ve kârlılığı tüm veriler birlikte değerlendirmek daha doğru olur."

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Temel Analiz - {{ analiz.sembol }}</title>
        <link rel="manifest" href="/manifest.json">
        <meta name="theme-color" content="#e94560">
        <style>
            body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
            .container{max-width:1100px;margin:auto}
            .header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:8px;margin-bottom:15px;position:sticky;top:10px;z-index:10}
            .header h1{margin:0;color:#e94560;font-size:20px}
            .header p{margin:0;color:#dfeaff;font-size:12px;text-align:right;white-space:nowrap}
            .header small{display:block;color:#b0bec5;font-size:10px;margin-top:3px;letter-spacing:.08em}
            .menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
            .menu a{flex:1;min-width:90px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
            .menu a.active{background:#e94560}
            .card{background:#16213e;border:1px solid rgba(255,255,255,.05);border-radius:12px;padding:18px;margin-bottom:18px}
            .topbar{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
            .metric{background:#1e293b;border-radius:10px;padding:12px}
            .metric .label{color:#94a3b8;font-size:12px;text-transform:uppercase}
            .metric .value{font-size:24px;font-weight:700;margin-top:8px}
            .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:12px}
            .metric-box{background:#1e293b;border-radius:10px;padding:12px}
            .metric-box .label{font-size:12px;text-transform:uppercase;color:#94a3b8;margin-bottom:8px}
            .metric-box .value{font-size:24px;font-weight:700;margin-bottom:8px}
            .metric-box .desc{font-size:12px;line-height:1.5;color:#dbeafe}
            form{display:flex;gap:10px;flex-wrap:wrap}
            input{flex:1;min-width:180px;border:1px solid rgba(148,163,184,.3);background:#0f3460;color:white;padding:10px 12px;border-radius:8px}
            button{background:#e94560;color:white;border:0;border-radius:8px;padding:10px 20px;cursor:pointer;font-weight:700}
            .pill{display:inline-block;padding:6px 12px;border-radius:999px;background:rgba(34,197,94,.15);color:#bbf7d0;font-size:12px;font-weight:700}
            .muted{color:#b0bec5}
            .top-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
            a.inline-link{color:#7dd3fc;text-decoration:none}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><div><h1>BIST AI</h1><small>SİZİN İÇİN ÇALIŞIYORUZ</small></div><p>{{ tarih }}</p></div>
            <div class="menu">
                <a href="/">Portfoy</a>
                <a href="/panel">Panel</a>
                <a href="/sektor">Sektor</a>
                <a href="/risk">Risk</a>
                <a href="/temel" class="active">Temel Analiz</a>
                <a href="/ai">AI</a>
                <a href="/istihbarat">Istihbarat</a>
                <a href="/sinyal">Sinyal</a>
                <a href="/canli">Canli</a>
                <a href="/hedef">Hedef</a>
                <a href="/bildirim">Bildirim</a>
            </div>

            <div class="card">
                <form method="GET" action="/temel">
                    <input type="text" name="sembol" value="{{ analiz.sembol }}" placeholder="Hisse sembolü (örn: THYAO)">
                    <button type="submit">Sorgula</button>
                </form>
            </div>

            <div class="card">
                <div class="topbar">
                    <div class="metric"><div class="label">Sembol</div><div class="value">{{ analiz.sembol }}</div></div>
                    <div class="metric"><div class="label">Fiyat</div><div class="value">{{ '%.2f' % analiz.fiyat }} ₺</div></div>
                    <div class="metric"><div class="label">Günlük değişim</div><div class="value">{{ '%.2f' % analiz.degisim }}%</div></div>
                    <div class="metric"><div class="label">Piyasa değeri</div><div class="value">{{ '%.2f' % analiz.market_cap_milyar }} B</div></div>
                </div>
            </div>

            <div class="card">
                <div class="pill">{{ analiz.genel_degerlendirme }}</div>
                <p><strong>Hızlı yorum:</strong> {{ kisa_degerlendirme }}</p>
                <p class="muted">Son güncelleme: {{ analiz.tarih }}</p>
                <div class="grid">
                    {% for metrik in metrikler %}
                    <div class="metric-box">
                        <div class="label">{{ metrik.etiket }}</div>
                        <div class="value">{{ metrik.deger }}</div>
                        <div class="desc">{{ metrik.aciklama }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </body>
    </html>
    """, analiz=analiz, sembol=sembol, tarih=datetime.now().strftime("%d.%m.%Y %H:%M"), metrikler=metrikler, kisa_degerlendirme=kisa_degerlendirme)


@app.route("/ai")
def ai_tahmin_sayfasi():
    try:
        sorgulanan_sembol = re.sub(r"[^A-Z]", "", request.args.get("sembol", "").upper())[:6]
        sorgu_sinyali = None
        sorgu_yorumu = None
        if sorgulanan_sembol:
            from sinyal_pro import sinyal_analiz
            sorgu_sinyali = sinyal_analiz(sorgulanan_sembol)
            if sorgu_sinyali and sorgu_sinyali.get("karar") != "HATA":
                from ai_yorumlama import sinyal_yorumla
                sorgu_yorumu = sinyal_yorumla(sorgulanan_sembol, sorgu_sinyali)
        hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]
        yarin_tahminleri = []
        for sembol in hisseler:
            tahmin = yarin_hisse_tahmini(sembol)
            if tahmin:
                tahmin["renk"] = "yukari" if tahmin["beklenen_getiri"] >= 0 else "asagi"
                tahmin["beklenen_yazi"] = f"{tahmin['beklenen_getiri']:+.2f}"
                yarin_tahminleri.append(tahmin)
        yarin_tahminleri.sort(key=lambda x: x["puan"], reverse=True)
        bugun_yukselenler = [t for t in yarin_tahminleri if t["bugun_yukseliyor"]]

        ensemble = EnsembleTahminci(look_back=30)
        model_hazir = ensemble.model_egit(hisseler[0]) is not None
        sonuclar = []
        for sembol in hisseler:
            tahminler = ensemble.gelecek_tahmin(sembol, gun_sayisi=5) if model_hazir else None
            tahminler = tahminler or basit_ai_tahmini(sembol, gun_sayisi=5)
            if tahminler and len(tahminler) >= 2:
                bugun = round(tahminler[0], 2)
                hedef = round(tahminler[-1], 2)
                degisim = round(((hedef - bugun) / bugun) * 100, 2)
                renk = "yukari" if degisim > 0 else "asagi" if degisim < 0 else "sifir"
                sonuclar.append({
                    "sembol": sembol, "bugun": bugun, "hedef": hedef,
                    "degisim": f"{degisim:+.2f}", "renk": renk,
                })
        sonuclar.sort(key=lambda x: float(x["degisim"]), reverse=True)
        return render_template_string(
            HTML_AI,
            sonuclar=sonuclar,
            yarin_tahminleri=yarin_tahminleri,
            bugun_yukselenler=bugun_yukselenler,
            sorgulanan_sembol=sorgulanan_sembol,
            sorgu_sinyali=sorgu_sinyali,
            sorgu_yorumu=sorgu_yorumu,
        )
    except Exception as e:
        return render_template_string(
            HTML_AI,
            sonuclar=[], yarin_tahminleri=[], bugun_yukselenler=[],
            sorgulanan_sembol=request.args.get("sembol", "").upper(),
            sorgu_sinyali=None, sorgu_yorumu=None,
        )


@app.route("/tarama")
def piyasa_tarama_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        from piyasa_tarama import piyasa_taramasi
        tarama = piyasa_taramasi(force=request.args.get("yenile") == "1")
    except Exception:
        tarama = {"sonuclar": [], "adaylar": [], "sembol_sayisi": 0, "veri_sayisi": 0, "son_guncelleme": "Veri yok"}
    return render_template_string(HTML_TARAMA, tarama=tarama)


@app.route("/istihbarat")
def istihbarat_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    sorgu = (request.args.get("sembol", "") or "").upper().replace(".IS", "")
    analiz = hisse_istihbarat_analizi(sorgu) if sorgu else None
    return render_template_string(
        HTML_ISTIHBARAT,
        analiz=analiz,
        sorgu=sorgu,
        tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
    )


@app.route("/halka-arz")
def halka_arz_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        sonuc = halka_arz_ozeti(zorla=request.args.get("yenile") == "1")
    except Exception:
        sonuc = {"tum": [], "son_alti": [], "takip": [], "beklenen": [], "son_guncelleme": datetime.now().strftime("%d.%m.%Y %H:%M")}
    response = make_response(render_template_string(HTML_HALKA_ARZ, **sonuc))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.route("/sinyal")
def sinyal_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        from sinyal_pro import portfoy_sinyalleri_al
        sinyaller_raw = portfoy_sinyalleri_al(kullanici)
        filtre = request.args.get("tip", "HEPSI").upper()
        if filtre == "AL":
            sinyaller_raw = [s for s in sinyaller_raw if s["karar"] == "AL"]
        elif filtre == "SAT":
            sinyaller_raw = [s for s in sinyaller_raw if s["karar"] == "SAT"]

        sinyaller = []
        for s in sinyaller_raw:
            sinyaller.append({
                "sembol": s.get("sembol", ""),
                "fiyat": s.get("fiyat", 0),
                "karar": s.get("karar", "BEKLE"),
                "oncelik": s.get("oncelik", "DUSUK"),
                "sebepler": s.get("sebepler", []),
                "rsi": s.get("rsi", "N/A"),
                "macd": s.get("macd", "N/A"),
                "adx": s.get("adx", "N/A"),
                "stoch": s.get("stoch", "N/A"),
                "cci": s.get("cci", "N/A"),
                "williams": s.get("williams", "N/A"),
                "bb_pos": s.get("bb_pos", "N/A"),
                "al_puan": s.get("al_puan", "N/A"),
                "sat_puan": s.get("sat_puan", "N/A"),
                "formasyonlar": s.get("formasyonlar", []),
            })
        try:
            from ai_yorumlama import sinyal_yorumla
            for sira, sinyal in enumerate(sinyaller):
                if sira < 10:
                    sinyal["ai_yorum"] = sinyal_yorumla(sinyal["sembol"], sinyal)
                else:
                    sinyal["ai_yorum"] = "Bu aday teknik puanlamada bulundu. Detayli AI analizi en guclu 10 aday icin uretilir."
        except Exception:
            for sinyal in sinyaller:
                sinyal["ai_yorum"] = "AI yorumu su anda kullanilamiyor."
        try:
            from bildirim_sistemi import bildirim_gonder
            for sinyal in sinyaller:
                bildirim_gonder(kullanici, sinyal)
        except Exception:
            pass

        return render_template_string(
            HTML_SINYAL,
            sinyaller=sinyaller,
            toplam_sinyal=len(sinyaller),
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )
    except Exception as e:
        return render_template_string(
            HTML_SINYAL, sinyaller=[], toplam_sinyal=0,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )


@app.route("/hedef")
def hedef_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        sorgulanan_sembol = (request.args.get("sembol", "") or "").upper().replace(".IS", "")
        semboller = [sorgulanan_sembol] if sorgulanan_sembol else ([h["sembol"] for h in portfoy_hisseler] or ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"])
        hedefler = []
        for sembol in semboller[:10]:
            tahmin = uzun_vade_hisse_tahmini(sembol)
            if not tahmin:
                tahmin = uzun_vade_fallback_tahmini(sembol)
            if tahmin:
                hedefler.append(tahmin)
        hedefler.sort(key=lambda x: x["degisim"], reverse=True)
        return render_template_string(
            HTML_HEDEF, hedefler=hedefler,
            sorgulanan_sembol=sorgulanan_sembol,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )
    except Exception:
        return render_template_string(
            HTML_HEDEF, hedefler=[],
            sorgulanan_sembol=request.args.get("sembol", ""),
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )


@app.route("/bildirim", methods=["GET", "POST"])
def bildirim_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    from bildirim_sistemi import kullanici_ayarlari_al, kullanici_ayarlari_guncelle

    mesaj = None
    sinif = "basarili"
    if request.method == "POST":
        mevcut = kullanici_ayarlari_al(kullanici)
        yeni = {
            "aktif": request.form.get("aktif") == "on",
            "saat": request.form.get("saat", "09:00"),
            "tur": request.form.get("tur", "hepsi"),
            "hisseler": mevcut.get("hisseler", []),
            "siklik": request.form.get("siklik", "saatlik"),
            "son_bildirim": mevcut.get("son_bildirim"),
            "gecmis": mevcut.get("gecmis", []),
        }
        kullanici_ayarlari_guncelle(kullanici, yeni)
        mesaj = "Ayarlar kaydedildi!"

    ayarlar = kullanici_ayarlari_al(kullanici)
    return render_template_string(
        HTML_BILDIRIM,
        tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        ayarlar=ayarlar, mesaj=mesaj, sinif=sinif,
    )


@app.route("/panel")
def panel_sayfasi():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))

        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        toplam_deger = sum(h["adet"] * h["alis_fiyati"] for h in portfoy_hisseler)
        toplam_maliyet = toplam_deger
        portfoy_ozet = {
            "toplam_deger": f"{toplam_deger:,.2f}",
            "hisse_sayisi": len(portfoy_hisseler),
            "toplam_kar": "0.00",
            "renk": "notr",
        }

        portfoy_data = [{
            "sembol": h["sembol"], "adet": h["adet"],
            "deger": h["adet"] * h["alis_fiyati"],
            "sektor": HISSE_SEKTORLERI.get(h["sembol"], "Diger"),
            "volatilite": 0,
        } for h in portfoy_hisseler]

        if portfoy_data and toplam_deger:
            puan = cesitlendirme_puani(portfoy_data, toplam_deger)
        else:
            puan = 0
        risk_ozet = {
            "puan": puan,
            "durum": "Iyi" if puan >= 70 else "Orta" if puan >= 40 else "Dikkat",
        }

        ai_tahminleri = []
        try:
            from ensemble_model import basit_tahmin
            for sembol in ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]:
                tahminler = basit_tahmin(sembol, 5)
                if tahminler and len(tahminler) >= 2 and tahminler[0] > 0:
                    degisim = ((tahminler[-1] - tahminler[0]) / tahminler[0]) * 100
                    ai_tahminleri.append({
                        "sembol": sembol,
                        "degisim": f"{degisim:+.2f}",
                        "renk": "pozitif" if degisim > 0 else "negatif",
                    })
            ai_tahminleri.sort(key=lambda x: float(x["degisim"]), reverse=True)
        except Exception:
            pass

        sektorler = []
        for ad, hisseler in sektor_analiz_yap().items():
            if hisseler:
                ortalama = sum(h["gunluk"] for h in hisseler) / len(hisseler)
                sektorler.append({
                    "sektor": ad,
                    "ortalama": f"{ortalama:+.2f}%",
                    "renk": "pozitif" if ortalama >= 0 else "negatif",
                })
        sektorler.sort(key=lambda x: float(x["ortalama"].rstrip("%")), reverse=True)

        sinyaller = []
        try:
            from gelismis_kurallar import portfoy_analiz
            for sinyal in portfoy_analiz()[:5]:
                sinyaller.append({
                    "sembol": sinyal["sembol"],
                    "fiyat": sinyal["fiyat"],
                    "karar": sinyal["karar"],
                    "oncelik": sinyal.get("oncelik", "DUSUK"),
                })
        except Exception:
            pass

        return render_template_string(
            HTML_PANEL,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
            portfoy=portfoy_ozet, risk=risk_ozet,
            ai_tahminleri=ai_tahminleri, sektorler=sektorler,
            sinyaller=sinyaller,
        )
    except Exception as e:
        return f"<h1>Hata</h1><p>{e}</p>"


# ============================================
# CALISTIR
# ============================================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)