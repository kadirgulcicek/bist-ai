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
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

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
            <a href="/canli">Canli</a>
            <a href="/hedef">Hedef</a>
            <a href="/bildirim">Bildirim</a>
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
            <tr>
                <th>Hisse</th>
                <th>Adet</th>
                <th>Alis</th>
                <th>Guncel</th>
                <th>Kar %</th>
                <th style="width: 60px;">Islem</th>
            </tr>
            {% for h in hisseler %}
            <tr>
                <td><b>{{ h.sembol }}</b></td>
                <td>{{ h.adet }}</td>
                <td>{{ h.alis }}</td>
                <td>{{ h.guncel }}</td>
                <td class="{{ h.renk }}">{{ h.kar_yuzde }}%</td>
                <td style="text-align: center;">
                    <a href="/hisse-sil/{{ h.sembol }}"
                       style="background: #f44336; color: white; padding: 5px 12px; border-radius: 4px; text-decoration: none; font-weight: bold;"
                       onclick="return confirm('{{ h.sembol }} hissesini portfoyden silmek istediginize emin misiniz?')">
                        X
                    </a>
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
            <a href="/canli">Canli</a>
            <a href="/hedef">Hedef</a>
            <a href="/bildirim">Bildirim</a>
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
            <a href="/canli">Canli</a>
            <a href="/hedef">Hedef</a>
            <a href="/bildirim">Bildirim</a>
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
            <a href="/canli">Canli</a>
            <a href="/hedef">Hedef</a>
            <a href="/bildirim">Bildirim</a>
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
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
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
        .filtre { background: #16213e; padding: 12px; margin-bottom: 15px; border-radius: 8px; display: flex; gap: 8px; }
        .filtre-btn { flex: 1; padding: 8px; background: #0f3460; color: white; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; text-align: center; font-size: 13px; }
        .filtre-btn.aktif { background: #e94560; }
        .sinyal-card { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 5px solid #e94560; position: relative; }
        .sinyal-card.sat { border-left-color: #f44336; }
        .sinyal-card.al { border-left-color: #4caf50; }
        .sinyal-baslik { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .sinyal-sol { flex: 1; }
        .sinyal-tip { font-size: 22px; font-weight: bold; padding: 5px 15px; border-radius: 5px; display: inline-block; }
        .tip-al { background: #4caf50; color: white; }
        .tip-sat { background: #f44336; color: white; }
        .sinyal-sembol { font-size: 22px; font-weight: bold; }
        .sinyal-fiyat { color: #b0bec5; font-size: 14px; margin-top: 3px; }
        .sinyal-hedef { font-size: 13px; margin-top: 3px; }
        .hedef-yukari { color: #4caf50; }
        .hedef-asagi { color: #f44336; }
        .sinyal-sag { text-align: right; }
        .guven { margin-top: 5px; font-size: 14px; padding: 4px 10px; background: #0f3460; border-radius: 12px; display: inline-block; }
        .guven-bar { background: #0f3460; height: 8px; border-radius: 4px; margin: 8px 0; overflow: hidden; }
        .guven-bar-fill { height: 100%; background: linear-gradient(90deg, #f44336 0%, #ff9800 50%, #4caf50 100%); border-radius: 4px; }
        .sebepler { margin-top: 10px; }
        .sebep { display: inline-block; background: #0f3460; padding: 4px 10px; margin: 3px; border-radius: 15px; font-size: 13px; }
        .oncelik { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; margin-right: 10px; font-weight: bold; }
        .oncelik.yuksek { background: #f44336; color: white; }
        .oncelik.orta { background: #ff9800; color: white; }
        .info-box { background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }
        .yenile-btn { display: block; text-align: center; padding: 10px; background: #e94560; color: white; text-decoration: none; border-radius: 8px; margin: 15px 0; font-weight: bold; }
        .sinyal-detay { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-top: 10px; padding: 10px; background: #0f3460; border-radius: 5px; font-size: 12px; }
        .detay-item { text-align: center; }
        .detay-deger { font-size: 16px; font-weight: bold; margin-top: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Al-Sat Sinyalleri</h1>
            <p>{{ tarih }} | {{ toplam_sinyal }} aktif sinyal</p>
        </div>
        <div class="menu">
            <a href="/">Portfoy</a>
            <a href="/panel">Panel</a>
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai">AI</a>
            <a href="/sinyal" class="active">Sinyal</a>
            <a href="/canli">Canli</a>
            <a href="/hedef">Hedef</a>
            <a href="/bildirim">Bildirim</a>
        </div>
        <a href="/sinyal" class="yenile-btn">Yenile</a>
        <div class="filtre">
            <a href="/sinyal" class="filtre-btn {{ filtre_hepsi }}">Hepsi</a>
            <a href="/sinyal?tip=AL" class="filtre-btn {{ filtre_al }}">AL</a>
            <a href="/sinyal?tip=SAT" class="filtre-btn {{ filtre_sat }}">SAT</a>
            <a href="/sinyal?tip=PORTFOY" class="filtre-btn {{ filtre_portfoy }}">Portfoyum</a>
        </div>
        {% if sinyaller %}
            {% for s in sinyaller %}
            <div class="sinyal-card {{ s.karar|lower }}">
                <div class="sinyal-baslik">
                    <div class="sinyal-sol">
                        <div class="sinyal-sembol">{{ s.sembol }}</div>
                        <div class="sinyal-fiyat">{{ s.fiyat }} TL</div>
                        {% if s.hedef %}
                        <div class="sinyal-hedef">Hedef: <span class="{{ s.hedef_renk }}">{{ s.hedef }} TL ({{ s.hedef_degisim }})</span></div>
                        {% endif %}
                    </div>
                    <div class="sinyal-sag">
                        <div class="sinyal-tip tip-{{ s.karar|lower }}">{{ s.karar }}</div>
                        <div class="guven">Guven: {{ s.guven }}%</div>
                    </div>
                </div>
                <div class="guven-bar"><div class="guven-bar-fill" style="width: {{ s.guven }}%;"></div></div>
                <div>
                    <span class="oncelik {{ s.oncelik|lower }}">{{ s.oncelik }}</span>
                </div>
                <div class="sebepler">
                    {% for sebep in s.sebepler %}
                    <span class="sebep">{{ sebep }}</span>
                    {% endfor %}
                </div>
                {% if s.rsi or s.macd or s.trend %}
                <div class="sinyal-detay">
                    <div class="detay-item"><div>RSI</div><div class="detay-deger {{ s.rsi_renk }}">{{ s.rsi }}</div></div>
                    <div class="detay-item"><div>MACD</div><div class="detay-deger {{ s.macd_renk }}">{{ s.macd }}</div></div>
                    <div class="detay-item"><div>Trend</div><div class="detay-deger {{ s.trend_renk }}">{{ s.trend }}</div></div>
                </div>
                {% endif %}
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
            <a href="/canli">Canli</a>
            <a href="/hedef">Hedef</a>
            <a href="/bildirim">Bildirim</a>
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


HTML_CANLI = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Canli Takip</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 70px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .menu a.cikis { background: #f44336; }
        .canli-card { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #4caf50; }
        .canli-card.negatif { border-left-color: #f44336; }
        .canli-card.beklemede { border-left-color: #607d8b; opacity: 0.7; }
        .sembol { font-weight: bold; font-size: 18px; }
        .fiyat { font-size: 20px; font-weight: bold; margin-top: 5px; }
        .degisim { font-size: 14px; margin-top: 3px; }
        .pozitif { color: #4caf50; } .negatif { color: #f44336; }
        .zaman { font-size: 12px; color: #b0bec5; }
        .alarm { background: #5c1f1f; padding: 12px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #f44336; animation: blink 2s infinite; }
        @keyframes blink { 50% { opacity: 0.7; } }
        .info-box { background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }
        .otomatik-bilgi { font-size: 12px; color: #b0bec5; margin-top: 15px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>Canli Takip</h1><p>{{ tarih }}</p></div>
        <div class="menu">
            <a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a><a href="/ai">AI</a><a href="/sinyal">Sinyal</a>
            <a href="/canli" class="active">Canli</a><a href="/cikis" class="cikis">Cikis</a>
            <a href="/hedef">Hedef</a>
            <a href="/bildirim">Bildirim</a>
        </div>
        {% for alarm in alarmlar %}
        <div class="alarm"><b>ALARM!</b> {{ alarm.sembol }} - {{ alarm.fiyat }} TL - {{ alarm.aciklama }}</div>
        {% endfor %}
        <h2>Anlik Fiyatlar</h2>
        {% for h in fiyatlar %}
        <div class="canli-card {{ h.durum }}">
            <div><div class="sembol">{{ h.sembol }}</div><div class="zaman">{{ h.zaman }}</div></div>
            <div style="text-align: right;"><div class="fiyat">{{ h.fiyat }} TL</div><div class="degisim {{ h.renk }}">{{ h.yon }} {{ h.degisim }}%</div></div>
        </div>
        {% endfor %}
        {% if not fiyatlar %}<div class="info-box"><p>Veriler yukleniyor...</p><p style="font-size: 12px;">Sayfa her 30 saniyede otomatik guncellenir.</p></div>{% endif %}
        <div class="info-box" style="margin-top: 20px;"><b>Canli Takip Ozellikleri</b><br>- Her 30 saniyede otomatik fiyat guncelleme<br>- Buyuk hareketlerde otomatik alarm<br>- Piyasa kapaliysa son kapanis fiyati gosterilir</div>
        <div class="otomatik-bilgi">Bu sayfa her 30 saniyede otomatik guncellenir.</div>
    </div>
    <script>setTimeout(function() { location.reload(); }, 30000);</script>
</body>
</html>
"""


HTML_HEDEF = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Hedef Fiyat</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 70px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; }
        .menu a.cikis { background: #f44336; }
        .hedef-card { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #4caf50; }
        .hedef-card.orta { border-left-color: #ff9800; } .hedef-card.yuksek { border-left-color: #f44336; }
        .baslik { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .sembol { font-weight: bold; font-size: 18px; } .trend-badge { font-size: 12px; padding: 3px 8px; border-radius: 4px; }
        .trend-yukari { background: #4caf50; } .trend-asagi { background: #f44336; } .trend-yatay { background: #607d8b; }
        .fiyat-alani { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: center; margin: 15px 0; padding: 15px; background: #0f3460; border-radius: 8px; }
        .fiyat-kutu { text-align: center; } .fiyat-baslik { font-size: 11px; color: #b0bec5; text-transform: uppercase; }
        .fiyat-deger { font-size: 22px; font-weight: bold; margin-top: 5px; } .ok { font-size: 24px; color: #e94560; }
        .detay-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
        .detay-kutu { background: #0f3460; padding: 10px; border-radius: 5px; } .detay-baslik { font-size: 11px; color: #b0bec5; }
        .detay-deger { font-size: 14px; font-weight: bold; margin-top: 3px; } .risk-dusuk { color: #4caf50; }
        .risk-orta { color: #ff9800; } .risk-yuksek { color: #f44336; }
        .info-box { background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }
        .guven-bar { background: #0f3460; height: 12px; border-radius: 6px; margin: 10px 0; overflow: hidden; position: relative; }
        .guven-bar-fill { height: 100%; width: 50%; background: linear-gradient(90deg, #4caf50 0%, #ff9800 50%, #f44336 100%); }
        .guven-bar-text { position: absolute; top: 0; left: 50%; transform: translateX(-50%); font-size: 10px; line-height: 12px; }
    </style>
</head>
<body><div class="container">
    <div class="header"><h1>Hedef Fiyat Tahmini</h1><p>{{ tarih }}</p></div>
    <div class="menu">
        <a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a><a href="/risk">Risk</a>
        <a href="/ai">AI</a><a href="/sinyal">Sinyal</a><a href="/canli">Canli</a><a href="/hedef" class="active">Hedef</a><a href="/bildirim">Bildirim</a><a href="/cikis" class="cikis">Cikis</a>
    </div>
    {% if hedefler %}{% for h in hedefler %}
    <div class="hedef-card {{ h.risk|lower }}">
        <div class="baslik"><div><span class="sembol">{{ h.sembol }}</span> <span class="trend-badge trend-{{ h.trend|lower }}">{{ h.trend }}</span></div><span class="risk-{{ h.risk|lower }}" style="font-weight: bold;">{{ h.risk }} RISK</span></div>
        <div class="fiyat-alani"><div class="fiyat-kutu"><div class="fiyat-baslik">Guncel</div><div class="fiyat-deger">{{ h.guncel }} TL</div></div><div class="ok">-</div><div class="fiyat-kutu"><div class="fiyat-baslik">Hedef ({{ h.zaman_gun }} gun)</div><div class="fiyat-deger">{{ h.hedef }} TL</div></div></div>
        <div style="text-align: center; margin: 10px 0;"><span class="risk-{{ h.risk|lower }}" style="font-size: 16px; font-weight: bold;">{{ h.degisim }}% ({{ h.zaman_gun }} gun)</span></div>
        <div class="guven-bar"><div class="guven-bar-fill"></div><div class="guven-bar-text">Guven araligi: {{ h.guven_alt }} - {{ h.guven_ust }} TL</div></div>
        <div class="detay-grid"><div class="detay-kutu"><div class="detay-baslik">Volatilite</div><div class="detay-deger">%{{ h.volatilite }}</div></div><div class="detay-kutu"><div class="detay-baslik">MA5 / MA20</div><div class="detay-deger">{{ h.ma_5 }} / {{ h.ma_20 }}</div></div></div>
    </div>
    {% endfor %}{% else %}<div class="info-box"><p>Tahminler yuklenemedi.</p></div>{% endif %}
    <div class="info-box" style="margin-top: 20px; font-size: 12px;"><b>NOT:</b> Tahminler gecmis verilere dayanir, garanti vermez. Yatirim tavsiyesi degildir.</div>
</div></body>
</html>
"""


HTML_BILDIRIM = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Bildirimler</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; margin: 0; padding: 15px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; padding: 20px; background: linear-gradient(135deg, #16213e, #0f3460); border-radius: 10px; margin-bottom: 15px; }
        .header h1 { margin: 0; color: #e94560; font-size: 22px; }
        .menu { display: flex; gap: 8px; margin: 15px 0; flex-wrap: wrap; }
        .menu a { flex: 1; min-width: 70px; padding: 8px; background: #0f3460; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 13px; }
        .menu a.active { background: #e94560; } .menu a.cikis { background: #f44336; }
        .ayar-kutu { background: #16213e; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .ayar-kutu h3 { margin-top: 0; color: #4caf50; }
        .ayar-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #0f3460; }
        .ayar-row:last-child { border-bottom: none; }
        .switch { position: relative; display: inline-block; width: 50px; height: 24px; }
        .switch input { display: none; } .slider { position: absolute; cursor: pointer; inset: 0; background: #607d8b; border-radius: 24px; transition: .3s; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: .3s; }
        input:checked + .slider { background: #4caf50; } input:checked + .slider:before { transform: translateX(26px); }
        select { background: #0f3460; color: white; border: none; padding: 8px 12px; border-radius: 5px; font-size: 14px; }
        .btn { padding: 10px 20px; background: #e94560; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        .bildirim { background: #16213e; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #e94560; }
        .bildirim-zaman { font-size: 11px; color: #b0bec5; margin-bottom: 5px; }
        .info-box { background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }
        .basarili { background: #4caf50; padding: 10px; border-radius: 5px; margin-bottom: 15px; text-align: center; }
    </style>
</head>
<body><div class="container">
    <div class="header"><h1>Bildirim Ayarlari</h1><p>{{ tarih }}</p></div>
    <div class="menu">
        <a href="/">Portfoy</a><a href="/panel">Panel</a><a href="/sektor">Sektor</a><a href="/risk">Risk</a>
        <a href="/ai">AI</a><a href="/sinyal">Sinyal</a><a href="/canli">Canli</a><a href="/hedef">Hedef</a>
        <a href="/bildirim" class="active">Bildirim</a><a href="/cikis" class="cikis">Cikis</a>
    </div>
    {% if mesaj %}<div class="{{ sinif }}">{{ mesaj }}</div>{% endif %}
    <div class="ayar-kutu"><h3>Bildirim Tercihleri</h3><form method="POST">
        <div class="ayar-row"><span><b>Bildirim Aktif:</b></span><label class="switch"><input type="checkbox" name="aktif" {% if ayarlar.aktif %}checked{% endif %}><span class="slider"></span></label></div>
        <div class="ayar-row"><span><b>Zaman:</b></span><select name="zaman">
            <option value="sabah" {% if ayarlar.zaman == 'sabah' %}selected{% endif %}>Sabah (09:00)</option><option value="ogle" {% if ayarlar.zaman == 'ogle' %}selected{% endif %}>Ogle (13:00)</option><option value="aksam" {% if ayarlar.zaman == 'aksam' %}selected{% endif %}>Aksam (18:00)</option><option value="hepsi" {% if ayarlar.zaman == 'hepsi' %}selected{% endif %}>Hepsi</option>
        </select></div>
        <div class="ayar-row"><span><b>Tur:</b></span><select name="tur"><option value="hepsi" {% if ayarlar.tur == 'hepsi' %}selected{% endif %}>Hepsi (AL + SAT)</option><option value="AL" {% if ayarlar.tur == 'AL' %}selected{% endif %}>Sadece AL</option><option value="SAT" {% if ayarlar.tur == 'SAT' %}selected{% endif %}>Sadece SAT</option></select></div>
        <div class="ayar-row"><span><b>Siklik:</b></span><select name="siklik"><option value="saatlik" {% if ayarlar.siklik == 'saatlik' %}selected{% endif %}>Her saat</option><option value="gunluk" {% if ayarlar.siklik == 'gunluk' %}selected{% endif %}>Gunde 1</option><option value="haftalik" {% if ayarlar.siklik == 'haftalik' %}selected{% endif %}>Haftada 1</option></select></div>
        <div style="text-align: center; margin-top: 20px;"><button class="btn" type="submit">Ayarlari Kaydet</button></div>
    </form></div>
    <div class="ayar-kutu"><h3>Son Bildirimler</h3>{% if bildirimler %}{% for b in bildirimler %}<div class="bildirim"><div class="bildirim-zaman">{{ b.tarih }}</div><div>{{ b.mesaj }}</div></div>{% endfor %}{% else %}<p style="color: #b0bec5;">Henuz bildirim yok.</p>{% endif %}</div>
    <div class="info-box"><p style="font-size: 12px;">Bu sayfayi ziyaret ederek bildirim ayarlarinizi yonetin.</p><p style="font-size: 12px; color: #b0bec5;">Son bildirim: {{ ayarlar.son_bildirim|default('Henuz yok') }}</p></div>
</div></body>
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


@app.route("/hisse-sil/<sembol>")
def hisse_sil(sembol):
    """Tek bir hisseyi portfoyden sil"""
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    basarili = kullanici_yoneticisi.hisse_sil(kullanici, sembol)
    if basarili:
        return redirect(url_for("index"))
    return f"<h1>Hata</h1><p>{sembol} portfoyde bulunamadi.</p><a href='/'>Geri don</a>"


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
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    try:
        from sinyal_gelismis import portfoy_sinyalleri_al

        sinyaller_raw = portfoy_sinyalleri_al(kullanici)
        filtre = request.args.get("tip", "HEPSI").upper()
        if filtre == "AL":
            sinyaller_raw = [s for s in sinyaller_raw if s["karar"] == "AL"]
        elif filtre == "SAT":
            sinyaller_raw = [s for s in sinyaller_raw if s["karar"] == "SAT"]
        elif filtre == "PORTFOY":
            try:
                portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
                portfoy_semboller = [h["sembol"] for h in portfoy_hisseler]
                sinyaller_raw = [s for s in sinyaller_raw if s["sembol"] in portfoy_semboller]
            except Exception:
                pass

        sinyaller = []
        for s in sinyaller_raw:
            rsi = s.get("rsi", "-")
            macd = s.get("macd", "-")
            sinyal = {
                "sembol": s.get("sembol", ""),
                "fiyat": s.get("fiyat", 0),
                "karar": s.get("karar", "BEKLE"),
                "oncelik": s.get("oncelik", "DUSUK"),
                "sebepler": s.get("sebepler", []),
                "rsi": rsi,
                "macd": macd,
                "trend": "-",
                "rsi_renk": "",
                "macd_renk": "",
                "trend_renk": "",
                "guven": 50,
                "hedef": None,
                "hedef_renk": "",
                "hedef_degisim": "",
            }

            try:
                rsi_val = float(rsi)
                if rsi_val < 35:
                    sinyal["rsi_renk"] = "hedef-yukari"
                elif rsi_val > 70:
                    sinyal["rsi_renk"] = "hedef-asagi"
            except (TypeError, ValueError):
                pass

            try:
                macd_val = float(macd)
                sinyal["macd_renk"] = "hedef-yukari" if macd_val > 0 else "hedef-asagi"
            except (TypeError, ValueError):
                pass

            sebepler = s.get("sebepler", [])
            if any("Trend" in str(sep) for sep in sebepler):
                sinyal["trend"] = "YUKARI"
                sinyal["trend_renk"] = "hedef-yukari"

            try:
                if s.get("karar") == "AL":
                    sinyal["hedef"] = round(s["fiyat"] * 1.10, 2)
                    sinyal["hedef_renk"] = "hedef-yukari"
                    sinyal["hedef_degisim"] = "+10%"
                elif s.get("karar") == "SAT":
                    alis = None
                    try:
                        for h in kullanici_yoneticisi.portfoy_al(kullanici):
                            if h["sembol"] == s.get("sembol"):
                                alis = h["alis_fiyati"]
                                break
                    except Exception:
                        pass
                    if alis:
                        sinyal["hedef"] = round(alis * 1.15, 2)
                        sinyal["hedef_renk"] = "hedef-yukari"
                        sinyal["hedef_degisim"] = "+15%"
                    else:
                        sinyal["hedef"] = round(s.get("fiyat", 0) * 0.95, 2)
                        sinyal["hedef_renk"] = "hedef-asagi"
                        sinyal["hedef_degisim"] = "-5%"
            except Exception:
                pass
            sinyaller.append(sinyal)

        return render_template_string(
            HTML_SINYAL,
            sinyaller=sinyaller,
            toplam_sinyal=len(sinyaller),
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
            filtre_hepsi="aktif" if filtre == "HEPSI" else "",
            filtre_al="aktif" if filtre == "AL" else "",
            filtre_sat="aktif" if filtre == "SAT" else "",
            filtre_portfoy="aktif" if filtre == "PORTFOY" else "",
        )
    except Exception as e:
        return render_template_string(
            HTML_SINYAL,
            sinyaller=[],
            toplam_sinyal=0,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
            filtre_hepsi="",
            filtre_al="",
            filtre_sat="",
            filtre_portfoy="",
        )


@app.route("/canli")
def canli_sayfasi():
    """Canli fiyat takibi"""
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    try:
        from canli_takip import CanliTakip

        takip = CanliTakip()
        portfoy_hisseler = kullanici_yoneticisi.portfoy_al(kullanici)
        takip_semboller = [h["sembol"] for h in portfoy_hisseler]
        populer = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]
        if not takip_semboller:
            takip_semboller = populer
        else:
            for sembol in populer:
                if sembol not in takip_semboller:
                    takip_semboller.append(sembol)
                if len(takip_semboller) >= 10:
                    break

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
                "sembol": sembol,
                "fiyat": veri["fiyat"],
                "degisim": veri["degisim"],
                "yon": yon,
                "renk": renk,
                "durum": durum,
                "zaman": veri["zaman"],
            })
            if abs(degisim) >= 3.0:
                alarmlar.append({
                    "sembol": sembol,
                    "fiyat": veri["fiyat"],
                    "aciklama": f"%{degisim:+.2f} hareket!",
                })

        return render_template_string(
            HTML_CANLI,
            fiyatlar=fiyatlar,
            alarmlar=alarmlar,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        )
    except Exception:
        return render_template_string(
            HTML_CANLI,
            fiyatlar=[],
            alarmlar=[],
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
        takip_semboller = [h["sembol"] for h in portfoy_hisseler]
        populer = ["THYAO", "GARAN", "ASELS", "TUPRS", "EREGL"]
        if not takip_semboller:
            takip_semboller = populer
        else:
            for sembol in populer:
                if sembol not in takip_semboller:
                    takip_semboller.append(sembol)
                if len(takip_semboller) >= 10:
                    break

        hedefler = []
        for sembol in takip_semboller[:10]:
            tahmin = hedef_fiyat_tahmin(sembol)
            if tahmin:
                hedefler.append(tahmin)
        hedefler.sort(key=lambda item: item["degisim"], reverse=True)

        return render_template_string(
            HTML_HEDEF,
            hedefler=hedefler,
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )
    except Exception:
        return render_template_string(
            HTML_HEDEF,
            hedefler=[],
            tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )


@app.route("/bildirim", methods=["GET", "POST"])
def bildirim_sayfasi():
    """Kisisel bildirim ayarlari"""
    kullanici = aktif_kullanici_al()
    if not kullanici:
        return redirect(url_for("giris"))

    from bildirim_sistemi import kullanici_ayarlari_al, kullanici_ayarlari_guncelle

    mesaj = None
    sinif = "basarili"
    if request.method == "POST":
        mevcut_ayarlar = kullanici_ayarlari_al(kullanici)
        yeni_ayarlar = {
            "aktif": request.form.get("aktif") == "on",
            "zaman": request.form.get("zaman", "sabah"),
            "tur": request.form.get("tur", "hepsi"),
            "hisseler": mevcut_ayarlar.get("hisseler", []),
            "siklik": request.form.get("siklik", "saatlik"),
            "son_bildirim": mevcut_ayarlar.get("son_bildirim"),
            "gecmis": mevcut_ayarlar.get("gecmis", []),
        }
        kullanici_ayarlari_guncelle(kullanici, yeni_ayarlar)
        mesaj = "Ayarlar kaydedildi!"

    ayarlar = kullanici_ayarlari_al(kullanici)
    bildirimler = ayarlar.get("gecmis", [])[-10:]
    bildirimler.reverse()
    return render_template_string(
        HTML_BILDIRIM,
        tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        ayarlar=ayarlar,
        bildirimler=bildirimler,
        mesaj=mesaj,
        sinif=sinif,
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
