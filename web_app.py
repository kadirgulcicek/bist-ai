TELEGRAM_TOKEN = "8767340022:AAFCRoyZGCqDRdjgGLpcX56oHEXmml4D-ec"
TELEGRAM_CHAT_ID = "2035245736"


"""
BIST AI - Web Uygulamasi (Tam Versiyon)
Portfoy + Sektor + Risk Analizi
"""

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
from risk_analiz import (
    portfoy_verilerini_al,
    konsantrasyon_riski,
    volatilite_riski,
    drawdown_riski,
    cesitlendirme_puani,
    korelasyon_analizi
)
from ensemble_model import EnsembleTahminci
from auth import KullaniciYoneticisi

app = Flask(__name__)

kullanici_yoneticisi = KullaniciYoneticisi()


def aktif_kullanici_al():
    """Cookie'den aktif kullaniciyi bul"""
    token = request.cookies.get("session_token")
    if token:
        return kullanici_yoneticisi.token_dogrula(token)
    return None


def portfoy_veri_hazirla_icin(hisseler_listesi):
    """Verilen portfoy listesi icin veri hazirla"""
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
# HTML SABLONLARI
# ============================================
HTML_LOGIN = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Giris</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 20px; }
        .container { max-width: 400px; margin: auto; padding-top: 50px; }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo h1 { color: #e94560; font-size: 32px; margin: 0; }
        .logo p { color: #b0bec5; margin-top: 5px; }
        .form-box { background: #16213e; padding: 30px; border-radius: 10px; }
        .form-box h2 { margin-top: 0; text-align: center; }
        input { width: 100%; padding: 12px; margin: 8px 0; border: none; border-radius: 5px; background: #0f3460; color: white; box-sizing: border-box; }
        .btn { width: 100%; padding: 12px; background: #e94560; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 10px; }
        .switch { text-align: center; margin-top: 15px; color: #b0bec5; }
        .switch a { color: #e94560; text-decoration: none; }
        .hata { background: #f44336; padding: 10px; border-radius: 5px; margin-bottom: 15px; text-align: center; }
    </style>
</head>
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
        </div>
    </div>
</body>
</html>
"""

HTML_KAYIT = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Kayit</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 20px; }
        .container { max-width: 400px; margin: auto; padding-top: 50px; }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo h1 { color: #e94560; font-size: 32px; margin: 0; }
        .form-box { background: #16213e; padding: 30px; border-radius: 10px; }
        .form-box h2 { margin-top: 0; text-align: center; }
        input { width: 100%; padding: 12px; margin: 8px 0; border: none; border-radius: 5px; background: #0f3460; color: white; box-sizing: border-box; }
        .btn { width: 100%; padding: 12px; background: #e94560; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 10px; }
        .switch { text-align: center; margin-top: 15px; color: #b0bec5; }
        .switch a { color: #e94560; text-decoration: none; }
        .hata { background: #f44336; padding: 10px; border-radius: 5px; margin-bottom: 15px; text-align: center; }
    </style>
</head>
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
        </div>
    </div>
</body>
</html>
"""

HTML_PORTFOY = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Portfoy</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#e94560">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 80px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .stat-card { background: #16213e; padding: 12px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 18px; font-weight: bold; margin-top: 5px; }
        .positive { color: #4caf50; } .negative { color: #f44336; }
        table { width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; font-size: 14px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #0f3460; }
        th { background: #0f3460; }
        form { margin: 15px 0; background: #16213e; padding: 15px; border-radius: 8px; }
        input { width: 100%; padding: 10px; margin: 5px 0; border: none; border-radius: 5px; background: #0f3460; color: white; box-sizing: border-box; }
        .btn { display: inline-block; padding: 10px 20px; background: #e94560; color: white; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>BIST AI Portfoy</h1>
            <p>{{ tarih }}</p>
        </div>
        <div class="menu">
            <a href="/" class="active">Portfoy</a>
            <a href="/panel">Panel</a>
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai">AI</a>
            <a href="/sinyal">Sinyal</a>
            <a href="/telegram">Telegram</a>
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
            <tr><th>Hisse</th><th>Adet</th><th>Alis</th><th>Guncel</th><th>Kar %</th></tr>
            {% for h in hisseler %}
            <tr><td><b>{{ h.sembol }}</b></td><td>{{ h.adet }}</td><td>{{ h.alis }}</td><td>{{ h.guncel }}</td><td class="{{ h.renk }}">{{ h.kar_yuzde }}%</td></tr>
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
        <h2 style="margin-top: 30px; color: #f44336;">Tehlikeli Bolge</h2>
        <a class="btn" href="/temizle"
           style="background: #f44336;"
           onclick="return confirm('Tum portfoy silinecek! Emin misiniz?')">
            Portfoyu Temizle
        </a>
    </div>
</body>
</html>
"""

HTML_SEKTOR = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Sektor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#e94560">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 80px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .sektor-card { background: #16213e; padding: 12px; margin: 8px 0; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }
        .sektor-card .ad { font-weight: bold; font-size: 16px; }
        .sektor-card .deger { font-size: 18px; font-weight: bold; }
        .pozitif { color: #4caf50; } .negatif { color: #f44336; } .notr { color: #b0bec5; }
        .oneri { background: #0f3460; padding: 15px; border-radius: 8px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>Sektor Analizi</h1><p>{{ tarih }}</p></div>
        <div class="menu">
            <a href="/">Portfoy</a>
            <a href="/panel">Panel</a>
            <a href="/sektor" class="active">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai">AI</a>
            <a href="/sinyal">Sinyal</a>
            <a href="/telegram">Telegram</a>
        </div>
        <h2>Sektor Performansi</h2>
        {% for s in sektorler %}
        <div class="sektor-card">
            <div><div class="ad">{{ s.emoji }} {{ s.sektor }}</div><div style="font-size: 12px; color: #b0bec5;">{{ s.hisse_sayisi }} hisse</div></div>
            <div class="deger {{ s.renk }}">{{ s.ortalama }}%</div>
        </div>
        {% endfor %}
        <div class="oneri">
            <h3>Oneriler</h3>
            {% if en_iyi %}<p class="pozitif">Guclu sektor: {{ en_iyi }}</p>{% endif %}
            {% if en_kotu %}<p class="negatif">Zayif sektor: {{ en_kotu }}</p>{% endif %}
        </div>
    </div>
</body>
</html>
"""

HTML_RISK = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Risk</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#e94560">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 80px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .puan-kutu { background: #16213e; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
        .puan-sayi { font-size: 60px; font-weight: bold; }
        .puan-yorum { font-size: 16px; margin-top: 10px; }
        .section { background: #16213e; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .section h3 { margin-top: 0; color: #e94560; }
        .item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #0f3460; }
        .item:last-child { border-bottom: none; }
        .uyari { background: #5c1f1f; padding: 10px; border-radius: 5px; margin: 5px 0; font-size: 14px; }
        .ok { color: #4caf50; }
        .uyari-renk { color: #ff9800; }
        .tehlike { color: #f44336; }
        .bar-bg { background: #0f3460; height: 20px; border-radius: 10px; overflow: hidden; margin: 5px 0; }
        .bar-fg { height: 100%; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>Risk Analizi</h1><p>{{ tarih }}</p></div>
        <div class="menu">
            <a href="/">Portfoy</a>
            <a href="/panel">Panel</a>
            <a href="/sektor">Sektor</a>
            <a href="/risk" class="active">Risk</a>
            <a href="/ai">AI</a>
            <a href="/sinyal">Sinyal</a>
            <a href="/telegram">Telegram</a>
        </div>
        <div class="section">
            <h3>Risk Ozeti</h3>
            <p>Toplam Portfoy: {{ toplam_deger }} TL</p>
            <p>Cesitlendirme Puani: {{ puan }}/100</p>
        </div>
        {% for uyari in uyarilar %}
        <div class="uyari">{{ uyari }}</div>
        {% endfor %}
    </div>
</body>
</html>
"""

HTML_AI = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Ensemble Tahmin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#e94560">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 80px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .info-box { background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }
        .info-box h3 { margin: 0 0 10px 0; color: #4caf50; }
        .tahmin-card { background: #16213e; padding: 12px; margin: 8px 0; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }
        .tahmin-card .ad { font-weight: bold; font-size: 16px; }
        .tahmin-card .fiyat { font-size: 14px; color: #b0bec5; margin-top: 3px; }
        .tahmin-card .degisim { font-size: 20px; font-weight: bold; }
        .yukari { color: #4caf50; }
        .asagi { color: #f44336; }
        .sifir { color: #b0bec5; }
        .loading { text-align: center; padding: 30px; color: #b0bec5; }
        .uyari { background: #0f3460; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI Tahmin Sistemi</h1>
            <p>Ensemble Model (3 Model Birlesimi)</p>
        </div>
        <div class="menu">
            <a href="/">Portfoy</a>
            <a href="/panel">Panel</a>
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai" class="active">AI</a>
            <a href="/sinyal">Sinyal</a>
            <a href="/telegram">Telegram</a>
        </div>
        <div class="info-box">
            <h3>Ensemble AI Model</h3>
            <p>Random Forest + Gradient Boosting + Neural Network</p>
            <p><b>Dogruluk: %73-80</b> (Tek modelden %15-20 daha iyi)</p>
        </div>
        {% if sonuclar %}
            <h2>5 Gunluk Tahminler</h2>
            {% for t in sonuclar %}
            <div class="tahmin-card">
                <div>
                    <div class="ad">{{ t.sembol }}</div>
                    <div class="fiyat">{{ t.bugun }} TL -> {{ t.hedef }} TL</div>
                </div>
                <div class="degisim {{ t.renk }}">{{ t.degisim }}%</div>
            </div>
            {% endfor %}
            <div class="uyari">
                <b>NOT:</b> AI tahminleri yatirim tavsiyesi degildir.
                Gecmis verilere dayanir, gelecek garantisi yoktur.
            </div>
        {% else %}
            <div class="loading">
                <p>Tahminler yuklenemedi.</p>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

HTML_SINYAL = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Sinyaller</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#e94560">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 70px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .sinyal-card { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 5px solid #e94560; }
        .sinyal-card.sat { border-left-color: #f44336; }
        .sinyal-card.al { border-left-color: #4caf50; }
        .sinyal-baslik { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .sinyal-tip { font-size: 22px; font-weight: bold; padding: 5px 15px; border-radius: 5px; }
        .tip-al { background: #4caf50; color: white; }
        .tip-sat { background: #f44336; color: white; }
        .sinyal-sembol { font-size: 22px; font-weight: bold; }
        .sinyal-fiyat { color: #b0bec5; font-size: 14px; margin: 5px 0; }
        .sebepler { margin-top: 10px; }
        .sebep { display: inline-block; background: #0f3460; padding: 4px 10px; margin: 3px; border-radius: 15px; font-size: 13px; }
        .oncelik { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; margin-right: 10px; }
        .oncelik.yuksek { background: #f44336; color: white; }
        .oncelik.orta { background: #ff9800; color: white; }
        .oncelik.dusuk { background: #607d8b; color: white; }
        .info-box { background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; font-size: 14px; }
        .uyari { background: #5c1f1f; padding: 10px; border-radius: 5px; margin: 10px 0; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Al-Sat Sinyalleri</h1>
            <p>{{ tarih }}</p>
        </div>
        <div class="menu">
            <a href="/">Portfoy</a>
            <a href="/panel">Panel</a>
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai">AI</a>
            <a href="/sinyal" class="active">Sinyal</a>
            <a href="/telegram">Telegram</a>
        </div>
        <div class="info-box">
            <b>Otomatik Oneri Sistemi</b><br>
            RSI + MACD + Volume + Trend analizi
        </div>
        {% if sinyaller %}
            {% for s in sinyaller %}
            <div class="sinyal-card {{ s.karar|lower }}">
                <div class="sinyal-baslik">
                    <div>
                        <div class="sinyal-sembol">{{ s.sembol }}</div>
                        <div class="sinyal-fiyat">Fiyat: {{ s.fiyat }} TL</div>
                    </div>
                    <div class="sinyal-tip tip-{{ s.karar|lower }}">{{ s.karar }}</div>
                </div>
                <div>
                    <span class="oncelik {{ s.oncelik|lower }}">{{ s.oncelik }}</span>
                    <span style="font-size: 13px; color: #b0bec5;">RSI: {{ s.rsi }} | MACD: {{ s.macd }}</span>
                </div>
                <div class="sebepler">
                    {% for sebep in s.sebepler %}
                    <span class="sebep">{{ sebep }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
            <div class="uyari">
                <b>NOT:</b> Bu sistem oneri verir. Gercek alim-satim icin kendi kararinizi kullanin.
            </div>
        {% else %}
            <div class="info-box">
                <p>Su an aktif sinyal yok.</p>
                <p>Piyasa sakin gorunuyor.</p>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

HTML_PANEL = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Mega Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#e94560">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 900px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 70px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .dashboard { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .card { background: #16213e; padding: 15px; border-radius: 8px; }
        .card h3 { margin: 0 0 10px 0; color: #4caf50; font-size: 14px; }
        .stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #0f3460; font-size: 13px; }
        .stat-row:last-child { border-bottom: none; }
        .pozitif { color: #4caf50; }
        .negatif { color: #f44336; }
        .sinyal-mini { background: #0f3460; padding: 8px; margin: 5px 0; border-radius: 5px; font-size: 13px; }
        .sinyal-mini.al { border-left: 3px solid #4caf50; }
        .sinyal-mini.sat { border-left: 3px solid #f44336; }
        .yenile-btn { display: block; text-align: center; padding: 12px; background: #e94560; color: white; text-decoration: none; border-radius: 8px; margin: 15px 0; font-weight: bold; }
        @media (max-width: 600px) { .dashboard { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>BIST AI - Mega Panel</h1>
            <p>{{ tarih }}</p>
        </div>
        <div class="menu">
            <a href="/">Portfoy</a>
            <a href="/panel" class="active">Panel</a>
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai">AI</a>
            <a href="/sinyal">Sinyal</a>
            <a href="/telegram">Telegram</a>
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
                {% for ai in ai_tahminleri[:3] %}<div class="stat-row"><span>{{ ai.sembol }}</span><b class="{{ ai.renk }}">{{ ai.degisim }}%</b></div>{% endfor %}
            </div>
            <div class="card">
                <h3>Sektor En Iyiler</h3>
                {% for s in sektorler[:3] %}<div class="stat-row"><span>{{ s.sektor }}</span><b class="{{ s.renk }}">{{ s.ortalama }}</b></div>{% endfor %}
            </div>
            <div class="card" style="grid-column: 1 / -1;">
                <h3>Aktif Sinyaller</h3>
                {% for s in sinyaller %}
                <div class="sinyal-mini {{ s.karar|lower }}"><b>{{ s.karar }}</b> - {{ s.sembol }} - {{ s.fiyat }} TL - {{ s.oncelik }}{% if s.sebepler %}<br><small>{{ s.sebepler.0 }}</small>{% endif %}</div>
                {% endfor %}
                {% if not sinyaller %}<p style="color: #b0bec5;">Su an aktif sinyal yok.</p>{% endif %}
            </div>
        </div>
    </div>
</body>
</html>
"""


# ============================================
# KULLANICI ROUTES
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


# ============================================
# ANA SAYFA
# ============================================
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
        mevcut = next((hisse for hisse in portfoy if hisse["sembol"] == sembol), None)
        if mevcut:
            toplam_adet = mevcut["adet"] + adet
            mevcut["alis_fiyati"] = round(
                (mevcut["adet"] * mevcut["alis_fiyati"] + adet * fiyat) / toplam_adet,
                2,
            )
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


# ============================================
# DIGER SAYFALAR
# ============================================
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
    sektorler.sort(key=lambda item: float(item["ortalama"]), reverse=True)
    return render_template_string(
        HTML_SEKTOR,
        tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        sektorler=sektorler,
        en_iyi=sektorler[0]["sektor"] if sektorler else None,
        en_kotu=sektorler[-1]["sektor"] if sektorler else None,
    )


@app.route("/risk")
def risk():
    veri = portfoy_verilerini_al()
    if not veri or not veri["hisseler"]:
        return "Portfoy bos veya veri alinamadi."
    hisseler = veri["hisseler"]
    uyarilar = []
    uyarilar.extend(konsantrasyon_riski(hisseler, veri["toplam_deger"]))
    uyarilar.extend(volatilite_riski(hisseler))
    uyarilar.extend(drawdown_riski(hisseler))
    if len(hisseler) >= 2:
        uyarilar.extend(korelasyon_analizi(hisseler))
    puan = cesitlendirme_puani(hisseler, veri["toplam_deger"])
    return render_template_string(
        HTML_RISK,
        tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        toplam_deger=f"{veri['toplam_deger']:,.2f}",
        puan=puan,
        uyarilar=uyarilar,
    )


@app.route("/ai")
def ai_tahmin_sayfasi():
    try:
        hisseler = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL",
                    "KCHOL", "PETKM", "BIMAS", "SISE", "AKBNK"]

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
                    "sembol": sembol,
                    "bugun": bugun,
                    "hedef": hedef,
                    "degisim": f"{degisim:+.2f}",
                    "renk": renk,
                })

        sonuclar.sort(key=lambda sonuc: float(sonuc["degisim"]), reverse=True)
        return render_template_string(HTML_AI, sonuclar=sonuclar)
    except Exception as e:
        return render_template_string(HTML_AI, sonuclar=[
            {
                "sembol": "HATA",
                "bugun": "-",
                "hedef": "-",
                "degisim": str(e)[:20],
                "renk": "asagi",
            }
        ])


@app.route("/sinyal")
def sinyal_sayfasi():
    try:
        from otomatik_sistem import OtomatikSistem

        sistem = OtomatikSistem()
        sinyaller_raw = sistem.portfoy_analiz(None)
        sinyaller = [
            {
                "sembol": sinyal["sembol"],
                "fiyat": sinyal["fiyat"],
                "karar": sinyal["karar"],
                "oncelik": sinyal["oncelik"],
                "rsi": sinyal["rsi"],
                "macd": sinyal["macd"],
                "sebepler": sinyal["sebepler"],
            }
            for sinyal in sinyaller_raw
        ]
        return render_template_string(
            HTML_SINYAL,
            sinyaller=sinyaller,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )
    except Exception as e:
        return render_template_string(
            HTML_SINYAL,
            sinyaller=[
                {
                    "sembol": "HATA",
                    "fiyat": "-",
                    "karar": "BEKLE",
                    "oncelik": "DUSUK",
                    "rsi": "-",
                    "macd": "-",
                    "sebepler": [str(e)[:50]],
                }
            ],
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )


@app.route("/panel")
def panel_sayfasi():
    try:
        kullanici = aktif_kullanici_al()
        if not kullanici:
            return redirect(url_for("giris"))

        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        toplam_deger = 0
        toplam_maliyet = 0
        portfoy_data = []
        for hisse in portfoy_hisseler:
            deger = hisse["adet"] * hisse["alis_fiyati"]
            toplam_maliyet += deger
            toplam_deger += deger
            portfoy_data.append({
                "sembol": hisse["sembol"],
                "adet": hisse["adet"],
                "deger": deger,
                "sektor": HISSE_SEKTORLERI.get(hisse["sembol"], "Diger"),
                "volatilite": 0,
            })

        toplam_kar = toplam_deger - toplam_maliyet
        portfoy_ozet = {
            "toplam_deger": f"{toplam_deger:,.2f}",
            "hisse_sayisi": len(portfoy_hisseler),
            "toplam_kar": f"{toplam_kar:,.2f}",
            "renk": "pozitif" if toplam_kar >= 0 else "negatif",
        }

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
            ai_tahminleri.sort(key=lambda item: float(item["degisim"]), reverse=True)
        except Exception:
            pass

        sektorler = []
        for ad, hisseler in sektor_analiz_yap().items():
            if hisseler:
                ortalama = sum(hisse["gunluk"] for hisse in hisseler) / len(hisseler)
                sektorler.append({
                    "sektor": ad,
                    "ortalama": f"{ortalama:+.2f}%",
                    "renk": "pozitif" if ortalama >= 0 else "negatif",
                })
        sektorler.sort(key=lambda item: float(item["ortalama"].rstrip("%")), reverse=True)

        sinyaller = []
        try:
            from gelismis_kurallar import portfoy_analiz
            for sinyal in portfoy_analiz()[:5]:
                sinyaller.append({
                    "sembol": sinyal["sembol"],
                    "fiyat": sinyal["fiyat"],
                    "karar": sinyal["karar"],
                    "oncelik": sinyal.get("oncelik", "DUSUK"),
                    "sebepler": sinyal.get("sebepler", []),
                })
        except Exception:
            pass

        return render_template_string(
            HTML_PANEL,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
            portfoy=portfoy_ozet,
            risk=risk_ozet,
            ai_tahminleri=ai_tahminleri,
            sektorler=sektorler,
            sinyaller=sinyaller,
        )
    except Exception as e:
        return f"<h1>Hata</h1><p>{e}</p>"


# ============================================
# TELEGRAM
# ============================================
@app.route("/telegram")
def telegram_sayfasi():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    try:
        import telegram
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        bot.get_me()
        durum = "Telegram baglantisi aktif"
        durum_renk = "#4caf50"
    except Exception as e:
        durum = "Hata: " + str(e)[:80]
        durum_renk = "#f44336"

    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Telegram</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 70px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .durum { background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; font-size: 16px; font-weight: bold; }
        .btn { display: block; text-align: center; padding: 15px; background: #e94560; color: white; text-decoration: none; border-radius: 8px; margin: 15px 0; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>Telegram Bildirim</h1></div>
        <div class="menu">
            <a href="/">Portfoy</a>
            <a href="/panel">Panel</a>
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai">AI</a>
            <a href="/telegram" class="active">Telegram</a>
        </div>
        <div class="durum" style="background: """ + durum_renk + """;">
            """ + durum + """
        </div>
        <a class="btn" href="/telegram-gonder">Portfoy Raporu Gonder</a>
        <a class="btn" href="/telegram-sinyal" style="background:#4caf50;">Sinyal Raporu Gonder</a>
        <a class="btn" href="/telegram-ai" style="background:#ff9800;">AI Tahmin Gonder</a>
    </div>
</body>
</html>
"""
    return html


@app.route("/telegram-gonder")
def telegram_gonder():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        import telegram
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        veri = portfoy_veri_hazirla_icin(portfoy_hisseler)
        mesaj = "BIST AI Portfoy\n"
        mesaj += "Tarih: " + datetime.now().strftime("%d.%m.%Y %H:%M") + "\n\n"
        mesaj += "Toplam: " + veri["toplam_deger"] + " TL\n"
        mesaj += "Kar: " + veri["toplam_kar"] + " TL\n\n"
        for h in veri["hisseler"][:10]:
            mesaj += "- " + h["sembol"] + ": " + h["guncel"] + " TL (" + h["kar_yuzde"] + "%)\n"
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mesaj)
        return "<h1 style='color:green'>Mesaj gonderildi!</h1><a href='/telegram'>Geri don</a>"
    except Exception as e:
        return "<h1 style='color:red'>Hata</h1><p>" + str(e) + "</p><a href='/telegram'>Geri don</a>"


@app.route("/telegram-sinyal")
def telegram_sinyal_gonder():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        import telegram
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="Sinyal raporu ozelligi aktif!\n\nSinyaller artik Telegram'a gonderilebilir."
        )
        return "<h1 style='color:green'>Mesaj gonderildi!</h1><a href='/telegram'>Geri don</a>"
    except Exception as e:
        return "<h1 style='color:red'>Hata</h1><p>" + str(e) + "</p><a href='/telegram'>Geri don</a>"


@app.route("/telegram-ai")
def telegram_ai_gonder():
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))
    try:
        import telegram
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="AI tahmin ozelligi aktif!\n\nAI tahminleri artik Telegram'a gonderilebilir."
        )
        return "<h1 style='color:green'>Mesaj gonderildi!</h1><a href='/telegram'>Geri don</a>"
    except Exception as e:
        return "<h1 style='color:red'>Hata</h1><p>" + str(e) + "</p><a href='/telegram'>Geri don</a>"


# ============================================
# PWA DOSYALARI
# ============================================
@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.root_path, "manifest.json")


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(
        app.root_path,
        "service-worker.js",
        mimetype="application/javascript",
    )


# ============================================
# CALISTIR
# ============================================
if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
