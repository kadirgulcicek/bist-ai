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
    if _portfoy_risk_analiz is None:
        return None
    return _portfoy_risk_analiz(portfoy_hisseler)

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

kullanici_yoneticisi = KullaniciYoneticisi()


def aktif_kullanici_al():
    token = request.cookies.get("session_token")
    if token:
        return kullanici_yoneticisi.token_dogrula(token)
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
<div class="stat-card"><div>Hisse</div><div class="stat-value">{{ hisse_sayisi }}</div></div>
</div>
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
.container{max-width:800px;margin:auto}
.header{text-align:center;padding:20px;background:linear-gradient(135deg,#16213e,#0f3460);border-radius:10px;margin-bottom:15px}
.header h1{margin:0;color:#e94560;font-size:22px}
.menu{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}
.menu a{flex:1;min-width:80px;padding:8px;background:#0f3460;color:white;text-decoration:none;border-radius:5px;text-align:center;font-size:13px}
.menu a.active{background:#e94560}.menu a.cikis{background:#f44336}
.puan-kutu{background:#16213e;padding:30px;border-radius:10px;text-align:center;margin-bottom:20px}
.puan-sayi{font-size:60px;font-weight:bold}
.puan-yorum{font-size:16px;margin-top:10px}
.section{background:#16213e;padding:15px;border-radius:8px;margin-bottom:15px}
.section h3{margin-top:0;color:#e94560}
.metrik-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px}
.metrik-kutu{background:#16213e;padding:12px;border-radius:8px;text-align:center;border:1px solid #0f3460}
.metrik-baslik{font-size:11px;color:#b0bec5;text-transform:uppercase}
.metrik-deger{font-size:18px;font-weight:bold;margin-top:5px}
.uyari{background:#5c1f1f;padding:10px;border-radius:5px;margin:5px 0;font-size:14px}
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

<div class="puan-kutu">
<div class="puan-sayi" style="color:{{ risk_renk }}">{{ genel_risk }}/100</div>
<div class="puan-yorum">{{ risk_seviye }} RISK</div>
</div>

<h2>Portfoy Metrikleri</h2>
<div class="metrik-grid">
<div class="metrik-kutu"><div class="metrik-baslik">Toplam Deger</div><div class="metrik-deger">{{ toplam_deger }} TL</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Kar/Zarar</div><div class="metrik-deger">{{ toplam_kar_yuzde }}%</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Sharpe Ratio</div><div class="metrik-deger">{{ portfoy_sharpe }}</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Volatilite</div><div class="metrik-deger">%{{ portfoy_volatilite }}</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">VaR (95%)</div><div class="metrik-deger">%{{ portfoy_var }}</div></div>
<div class="metrik-kutu"><div class="metrik-baslik">Beta</div><div class="metrik-deger">{{ portfoy_beta }}</div></div>
</div>

<div class="section">
<h3>Cesitlendirme Puani: {{ cesitlendirme }}/100</h3>
<p>{{ puan_yorum }}</p>
</div>

{% if hisse_verileri %}
<div class="section">
<h3>Hisse Bazli Risk Detayi</h3>
{% for h in hisse_verileri %}
<div class="uyari">
<b>{{ h.sembol }} ({{ h.agirlik }}%)</b> - Risk: {{ h.risk_skor }}/10<br>
<small>Sharpe: {{ h.sharpe }} | Max DD: %{{ h.max_drawdown }} | Vol: %{{ h.volatilite }} | Beta: {{ h.beta }}</small><br>
<small>Kar/Zarar: {{ h.kar_yuzde }}% ({{ h.kar }} TL)</small>
</div>
{% endfor %}
</div>
{% endif %}

{% if korelasyonlar %}
<div class="section">
<h3>Yuksek Korelasyonlu Hisseler</h3>
{% for k in korelasyonlar %}
<div class="uyari">{{ k.hisse1 }} - {{ k.hisse2 }}: {{ k.korelasyon }} ({{ k.tip }})</div>
{% endfor %}
</div>
{% endif %}

<div class="section">
<h3>Oneriler</h3>
{% for o in oneriler %}
<div class="uyari">{{ o }}</div>
{% endfor %}
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
<p>Random Forest + Gradient Boosting + Neural Network</p>
</div>
{% if sonuclar %}
<h2>5 Gunluk Tahminler</h2>
{% for t in sonuclar %}
<div class="tahmin-card">
<div><div class="ad">{{ t.sembol }}</div><div class="fiyat">{{ t.bugun }} TL -> {{ t.hedef }} TL</div></div>
<div class="degisim {{ t.renk }}">{{ t.degisim }}%</div>
</div>
{% endfor %}
<div class="uyari">NOT: AI tahminleri yatirim tavsiyesi degildir.</div>
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
    return render_template_string(HTML_PORTFOY, **veri, kullanici=kullanici)


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
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
    if not portfoy_hisseler:
        return render_template_string(
            HTML_RISK,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
            toplam_deger="0", toplam_maliyet="0",
            toplam_kar="0", toplam_kar_yuzde="0",
            portfoy_sharpe="0", portfoy_volatilite="0",
            portfoy_var="0", portfoy_beta="0",
            cesitlendirme="0", genel_risk="0",
            risk_seviye="VERI YOK", risk_renk="#607d8b",
            puan_yorum="Portfoye hisse ekleyin.",
            hisse_verileri=[], korelasyonlar=[], oneriler=[]
        )

    try:
        sonuc = portfoy_risk_hesapla(portfoy_hisseler)
        if sonuc is None:
            return "Risk analizi yapilamadi."

        if not sonuc:
            return "Risk analizi yapilamadi."

        puan = sonuc["cesitlendirme"]
        if puan >= 80:
            puan_yorum = "Mukemmel! Portfoy cok iyi cesitlendirilmis."
        elif puan >= 60:
            puan_yorum = "Iyi. Cesitlendirme yeterli."
        elif puan >= 40:
            puan_yorum = "Orta. Cesitlendirme artirilabilir."
        elif puan >= 20:
            puan_yorum = "Zayif. Risk var!"
        else:
            puan_yorum = "Cok tehlikeli!"

        return render_template_string(
            HTML_RISK,
            **sonuc,
            puan=puan,
            puan_yorum=puan_yorum,
        )
    except Exception as e:
        return f"Risk analizi yapilamadi. Hata: {str(e)[:80]}"


@app.route("/ai")
def ai_tahmin_sayfasi():
    try:
        hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]
        ensemble = EnsembleTahminci(look_back=30)
        ensemble.model_egit(hisseler[0])
        sonuclar = []
        for sembol in hisseler:
            tahminler = ensemble.gelecek_tahmin(sembol, gun_sayisi=5)
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
        return render_template_string(HTML_AI, sonuclar=sonuclar)
    except Exception as e:
        return render_template_string(HTML_AI, sonuclar=[])


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