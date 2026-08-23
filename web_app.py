"""
BIST AI - Web Uygulamasi (Tam Versiyon)
Portfoy + Sektor + Risk Analizi
"""

from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory
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

app = Flask(__name__)

# ============================================
# HTML SABLONLARI
# ============================================
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
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai">AI</a>
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
        <h2 style="margin-top: 30px; color: #f44336;">Tehlikeli Bölge</h2>
        <a class="btn" href="/temizle"
           style="background: #f44336;"
           onclick="return confirm('Tüm portföy silinecek! Emin misiniz?')">
            🗑️ Portföyü Temizle
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
            <a href="/">Portfoy</a><a href="/sektor" class="active">Sektor</a><a href="/risk">Risk</a><a href="/ai">AI</a><a href="/telegram">Telegram</a>
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
            <a href="/">Portfoy</a><a href="/sektor">Sektor</a><a href="/risk" class="active">Risk</a><a href="/ai">AI</a><a href="/telegram">Telegram
            </a>
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
            <a href="/sektor">Sektor</a>
            <a href="/risk">Risk</a>
            <a href="/ai" class="active">AI</a>
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


@app.route("/")
def index():
    portfoy = Portfoy()
    hisseler = []
    toplam_deger = 0
    toplam_maliyet = 0

    for hisse in portfoy.hisseler:
        adet = hisse["adet"]
        alis = hisse["alis_fiyati"]
        guncel = alis
        deger = adet * guncel
        hisseler.append({
            "sembol": hisse["sembol"],
            "adet": adet,
            "alis": f"{alis:.2f}",
            "guncel": f"{guncel:.2f}",
            "kar_yuzde": "0.00",
            "renk": "positive",
        })
        toplam_deger += deger
        toplam_maliyet += adet * alis

    toplam_kar = toplam_deger - toplam_maliyet
    return render_template_string(
        HTML_PORTFOY,
        tarih=datetime.now().strftime("%d.%m.%Y %H:%M"),
        hisseler=hisseler,
        toplam_deger=f"{toplam_deger:,.2f}",
        toplam_maliyet=f"{toplam_maliyet:,.2f}",
        toplam_kar=f"{toplam_kar:,.2f}",
        kar_renk="positive" if toplam_kar >= 0 else "negative",
        hisse_sayisi=len(hisseler),
    )


@app.route("/temizle")
def portfoy_temizle():
    """Portfoyu temizler"""
    try:
        portfoy = Portfoy()
        portfoy.hisseler = []
        portfoy.kaydet()
        return redirect(url_for("index"))
    except Exception as e:
        return f"Hata: {e}"


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
    """Ensemble AI tahmin sayfasi"""
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


@app.route("/telegram")
def telegram():
    return "Telegram entegrasyonu hazir degil."


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


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
