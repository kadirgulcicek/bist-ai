from flask import (
    Flask,
    make_response,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    url_for,
)
import yfinance as yf
from datetime import datetime

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

kullanici_yoneticisi = KullaniciYoneticisi()


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


def portfoy_veri_hazirla_icin(hisseler_listesi):
    hisseler = []
    toplam_maliyet = 0
    toplam_deger = 0

    for hisse in hisseler_listesi:
        try:
            ticker = yf.Ticker(hisse["sembol"] + ".IS")
            veri = ticker.history(period="5d")
            if veri is None or len(veri) < 1:
                continue
            guncel = float(veri["Close"].iloc[-1])
            maliyet = hisse["adet"] * hisse["alis_fiyati"]
            deger = hisse["adet"] * guncel
            kar = deger - maliyet
            kar_yuzde = (kar / maliyet) * 100 if maliyet > 0 else 0
            toplam_maliyet += maliyet
            toplam_deger += deger
            hisseler.append({
                "sembol": hisse["sembol"],
                "adet": hisse["adet"],
                "alis": f"{hisse['alis_fiyati']:.2f}",
                "guncel": f"{guncel:.2f}",
                "kar_yuzde": f"{kar_yuzde:+.2f}",
                "renk": "positive" if kar >= 0 else "negative",
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
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:20px}
.container{max-width:400px;margin:auto;padding-top:50px}
.logo{text-align:center;margin-bottom:30px}
.logo h1{color:#e94560;font-size:32px;margin:0}
.logo p{color:#b0bec5;margin-top:5px}
.form-box{background:#16213e;padding:30px;border-radius:10px}
.form-box h2{margin-top:0;text-align:center}
input{width:100%;padding:12px;margin:8px 0;border:none;border-radius:5px;background:#0f3460;color:white;box-sizing:border-box}
.btn{width:100%;padding:12px;background:#e94560;color:white;border:none;border-radius:5px;cursor:pointer;font-size:16px;margin-top:10px}
.switch{text-align:center;margin-top:15px;color:#b0bec5}
.switch a{color:#e94560;text-decoration:none}
.hata{background:#f44336;padding:10px;border-radius:5px;margin-bottom:15px;text-align:center}
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
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:20px}
.container{max-width:400px;margin:auto;padding-top:50px}
.logo{text-align:center;margin-bottom:30px}
.logo h1{color:#e94560;font-size:32px;margin:0}
.form-box{background:#16213e;padding:30px;border-radius:10px}
.form-box h2{margin-top:0;text-align:center}
input{width:100%;padding:12px;margin:8px 0;border:none;border-radius:5px;background:#0f3460;color:white;box-sizing:border-box}
.btn{width:100%;padding:12px;background:#e94560;color:white;border:none;border-radius:5px;cursor:pointer;font-size:16px;margin-top:10px}
.switch{text-align:center;margin-top:15px;color:#b0bec5}
.switch a{color:#e94560;text-decoration:none}
.hata{background:#f44336;padding:10px;border-radius:5px;margin-bottom:15px;text-align:center}
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
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
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
</style></head>
<body>
<div class="container">
<div class="header"><h1>BIST AI Portfoy</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/" class="active">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
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
<tr><th>Hisse</th><th>Adet</th><th>Alis</th><th>Guncel</th><th>Kar %</th><th>Islem</th></tr>
{% for h in hisseler %}
<tr>
<td><b>{{ h.sembol }}</b></td><td>{{ h.adet }}</td><td>{{ h.alis }}</td><td>{{ h.guncel }}</td>
<td class="{{ h.renk }}">{{ h.kar_yuzde }}%</td>
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
<button class="btn" type="submit">Ekle</button>
</form>
<h2 style="margin-top:30px;color:#f44336">Tehlikeli Bolge</h2>
<a class="btn" href="/temizle" style="background:#f44336" onclick="return confirm('Tum portfoy silinecek! Emin misiniz?')">Portfoyu Temizle</a>
</div></body></html>
"""

HTML_SEKTOR = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Sektor</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
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
<div class="header"><h1>Sektor Analizi</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor" class="active">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
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
</div></body></html>
"""

HTML_RISK = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Risk</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:900px;margin:auto}
.header{text-align:center;padding:22px 18px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:12px;margin-bottom:16px;box-shadow:0 12px 28px rgba(0,0,0,.22)}
.header h1{margin:0;color:#e94560;font-size:24px}
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
<div class="header"><h1>Risk Analizi</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk" class="active">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
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
<div class="puan-sayi" style="color:{{ risk_renk }}">{{ tek_hisse_analizi.ortalama }}/10</div>
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
<h3>Portföy Metrikleri</h3>
<div class="metrik-grid">
<div class="metrik-kutu"><div class="metrik-baslik">Volatilite</div><div class="metrik-deger">%{{ portfoy_volatilite }}</div><div class="metrik-sub">Yıllık oynaklık</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">VaR (95%)</div><div class="metrik-deger">%{{ portfoy_var }}</div><div class="metrik-sub">Günlük maksimum kayıp</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Beta</div><div class="metrik-deger">{{ portfoy_beta }}</div><div class="metrik-sub">Piyasa duyarlılığı</div></div>
</div>
</div>

{% if hisse_verileri %}
<div class="section">
<h3>Hisse Bazlı Risk</h3>
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

HTML_AI = """
<!DOCTYPE html>
<html>
<head><title>BIST AI</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
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
.yarin-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:15px 0}
.yarin-card{background:#16213e;padding:14px;border-radius:8px;border-left:4px solid #4caf50}
.yarin-card .baslik{display:flex;justify-content:space-between;font-weight:bold}
.yarin-card .detay{color:#b0bec5;font-size:12px;margin-top:7px;line-height:1.6}
@media(max-width:600px){.yarin-grid{grid-template-columns:1fr}}
</style></head>
<body>
<div class="container">
<div class="header"><h1>AI Tahmin Sistemi</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai" class="active">AI</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
</div>
<div class="info-box">
<h3>Ensemble AI Model</h3>
<p>Yarının yönünü; momentum, EMA trendi ve RSI ile tahmin eder.</p>
</div>
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
</div></body></html>
"""

HTML_SINYAL = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Sinyaller</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
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
</style></head>
<body>
<div class="container">
<div class="header"><h1>Al-Sat Sinyalleri</h1><p>{{ tarih }} | {{ toplam_sinyal }} aktif</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal" class="active">Sinyal</a>
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
</div>
{% endfor %}
<div class="uyari">NOT: Bu sistem oneri verir. Kendi kararinizi kullanin.</div>
{% else %}
<div class="info-box"><p>Su an aktif sinyal yok.</p></div>
{% endif %}
</div></body></html>
"""

HTML_PANEL = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Panel</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:900px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
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
<div class="header"><h1>BIST AI - Mega Panel</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel" class="active">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
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
</div></body></html>
"""

HTML_CANLI = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Canli</title><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:70px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}.menu a.cikis{background:#f44336}
.canli-card{background:#16213e;padding:15px;margin:10px 0;border-radius:8px;display:flex;justify-content:space-between;align-items:center;border-left:4px solid #4caf50}
.canli-card.negatif{border-left-color:#f44336}
.sembol{font-weight:bold;font-size:18px}
.fiyat{font-size:20px;font-weight:bold;margin-top:5px}
.pozitif{color:#4caf50}.negatif{color:#f44336}
.zaman{font-size:12px;color:#b0bec5}
.alarm{background:#5c1f1f;padding:12px;border-radius:8px;margin:10px 0;border-left:4px solid #f44336}
.info-box{background:#16213e;padding:15px;border-radius:8px;margin:15px 0;text-align:center}
</style></head>
<body>
<div class="container">
<div class="header"><h1>Canli Takip</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
<a href="/canli" class="active">Canli</a><a href="/cikis" class="cikis">Cikis</a>
<a href="/hedef">Hedef</a><a href="/bildirim">Bildirim</a>
</div>
{% for alarm in alarmlar %}
<div class="alarm"><b>ALARM!</b> {{ alarm.sembol }} - {{ alarm.fiyat }} TL - {{ alarm.aciklama }}</div>
{% endfor %}
<h2>Anlik Fiyatlar</h2>
{% for h in fiyatlar %}
<div class="canli-card {{ h.durum }}">
<div><div class="sembol">{{ h.sembol }}</div><div class="zaman">{{ h.zaman }}</div></div>
<div style="text-align:right"><div class="fiyat">{{ h.fiyat }} TL</div><div class="degisim {{ h.renk }}">{{ h.yon }} {{ h.degisim }}%</div></div>
</div>
{% endfor %}
{% if not fiyatlar %}<div class="info-box"><p>Veriler yukleniyor...</p></div>{% endif %}
</div>
<script>setTimeout(function(){location.reload();},30000);</script>
</body></html>
"""

HTML_HEDEF = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Hedef</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
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
</style></head>
<body>
<div class="container">
<div class="header"><h1>Hedef Fiyat Tahmini</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
<a href="/canli">Canli</a><a href="/hedef" class="active">Hedef</a><a href="/bildirim">Bildirim</a>
<a href="/cikis" class="cikis">Cikis</a>
</div>
{% if hedefler %}
{% for h in hedefler %}
<div class="hedef-card">
<div class="baslik"><span class="sembol">{{ h.sembol }}</span><b>{{ h.degisim }}% ({{ h.zaman_gun }} gun)</b></div>
<div class="fiyat-alani">
<div class="fiyat-kutu"><div>Guncel</div><div class="fiyat-deger">{{ h.guncel }} TL</div></div>
<div>-</div>
<div class="fiyat-kutu"><div>Hedef</div><div class="fiyat-deger">{{ h.hedef }} TL</div></div>
</div>
<div class="detay-grid">
<div class="detay-kutu"><div>Volatilite</div><div class="detay-deger">%{{ h.volatilite }}</div></div>
<div class="detay-kutu"><div>Trend</div><div class="detay-deger">{{ h.trend }}</div></div>
</div>
</div>
{% endfor %}
{% else %}<div class="info-box"><p>Tahminler yuklenemedi.</p></div>{% endif %}
</div></body></html>
"""

HTML_BILDIRIM = """
<!DOCTYPE html>
<html>
<head><title>BIST AI - Bildirim</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#1a1a2e;color:white;margin:0;padding:15px}
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
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
<div class="header"><h1>Bildirim Ayarlari</h1><p>{{ tarih }}</p></div>
<div class="menu">
<a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
<a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
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
<span><b>Zaman:</b></span>
<select name="zaman">
<option value="sabah" {% if ayarlar.zaman == 'sabah' %}selected{% endif %}>Sabah</option>
<option value="ogle" {% if ayarlar.zaman == 'ogle' %}selected{% endif %}>Ogle</option>
<option value="aksam" {% if ayarlar.zaman == 'aksam' %}selected{% endif %}>Aksam</option>
<option value="hepsi" {% if ayarlar.zaman == 'hepsi' %}selected{% endif %}>Hepsi</option>
</select>
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
</div></body></html>
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
            response.set_cookie("session_token", sonuc, max_age=30 * 24 * 3600, httponly=True)
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
            response.set_cookie("session_token", sonuc, max_age=30 * 24 * 3600, httponly=True)
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
        portfoy = kullanici_yoneticisi.portfoy_al(kullanici)
        sembol = sembol.upper().replace(".IS", "")
        mevcut = next((h for h in portfoy if h["sembol"] == sembol), None)
        if mevcut:
            toplam_adet = mevcut["adet"] + adet
            mevcut["alis_fiyati"] = round(
                (mevcut["adet"] * mevcut["alis_fiyati"] + adet * fiyat) / toplam_adet, 2)
            mevcut["adet"] = toplam_adet
        else:
            portfoy.append({"sembol": sembol, "adet": adet, "alis_fiyati": fiyat})
        kullanici_yoneticisi.portfoy_kaydet(kullanici, portfoy)
        return redirect(url_for("index"))
    except Exception as e:
        return f"<h1>Hata</h1><p>{e}</p><a href='/'>Geri don</a>"


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


@app.route("/risk")
def risk():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))

        sembol = (request.args.get("sembol", "") or "").upper().replace(".IS", "")
        tek_hisse_analizi = tek_hisse_teknik_risk_hesapla(sembol) if sembol else None
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
            sorgulanan_sembol=sembol,
        )
    except Exception as e:
        return f"Risk analizi yapilamadi. Hata: {str(e)[:80]}"


@app.route("/ai")
def ai_tahmin_sayfasi():
    try:
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
        )
    except Exception as e:
        return render_template_string(
            HTML_AI,
            sonuclar=[], yarin_tahminleri=[], bugun_yukselenler=[]
        )


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
            })

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


@app.route("/canli")
def canli_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        from canli_takip import CanliTakip
        takip = CanliTakip()
        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        takip_semboller = [h["sembol"] for h in portfoy_hisseler] or ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]
        fiyatlar = []
        alarmlar = []
        for sembol in takip_semboller[:10]:
            veri = takip.anlik_fiyat_al(sembol)
            if not veri:
                continue
            degisim = veri["degisim"]
            if degisim > 0.5:
                renk, yon, durum = "pozitif", "YUKARI", ""
            elif degisim < -0.5:
                renk, yon, durum = "negatif", "ASAGI", "negatif"
            else:
                renk, yon, durum = "", "SIFIR", "beklemede"
            fiyatlar.append({
                "sembol": sembol, "fiyat": veri["fiyat"],
                "degisim": degisim, "yon": yon, "renk": renk,
                "durum": durum, "zaman": veri["zaman"],
            })
        return render_template_string(
            HTML_CANLI, fiyatlar=fiyatlar, alarmlar=alarmlar,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        )
    except Exception:
        return render_template_string(
            HTML_CANLI, fiyatlar=[], alarmlar=[],
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        )


@app.route("/hedef")
def hedef_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        from hedef_fiyat import hedef_fiyat_tahmin
        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        semboller = [h["sembol"] for h in portfoy_hisseler] or ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]
        hedefler = []
        for sembol in semboller[:10]:
            tahmin = hedef_fiyat_tahmin(sembol)
            if tahmin:
                hedefler.append(tahmin)
        hedefler.sort(key=lambda x: x["degisim"], reverse=True)
        return render_template_string(
            HTML_HEDEF, hedefler=hedefler,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )
    except Exception:
        return render_template_string(
            HTML_HEDEF, hedefler=[],
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
            "zaman": request.form.get("zaman", "sabah"),
            "tur": request.form.get("tur", "hepsi"),
            "hisseler": mevcut.get("hisseler", []),
            "siklik": request.form.get("siklik", "saatlik"),
            "son_bildirim": mevcut.get("son_bildirim"),
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)