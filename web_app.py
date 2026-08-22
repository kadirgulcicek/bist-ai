"""
BIST AI - Web Uygulaması
Tarayıcıdan portföy takibi
"""

from flask import Flask, render_template_string, request, redirect, url_for
import yfinance as yf
from datetime import datetime
from portfoy import Portfoy

app = Flask(__name__)

# HTML Şablonu (Türkçe, Mobil Uyumlu)
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>BIST AI - Portföy</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #1a1a2e;
            color: white;
            margin: 0;
            padding: 20px;
        }
        .container { max-width: 800px; margin: auto; }
        .header {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #16213e, #0f3460);
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .header h1 { margin: 0; color: #e94560; }
        .stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #16213e;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value { font-size: 24px; font-weight: bold; }
        .positive { color: #4caf50; }
        .negative { color: #f44336; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #0f3460;
        }
        th { background: #0f3460; }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            background: #e94560;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 5px;
        }
        form { margin: 20px 0; }
        input, select {
            padding: 10px;
            margin: 5px;
            border: none;
            border-radius: 5px;
            background: #16213e;
            color: white;
        }
        .form-row { margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💼 BIST AI Portföy</h1>
            <p>{{ tarih }}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div>Toplam Değer</div>
                <div class="stat-value">{{ toplam_deger }} TL</div>
            </div>
            <div class="stat-card">
                <div>Maliyet</div>
                <div class="stat-value">{{ toplam_maliyet }} TL</div>
            </div>
            <div class="stat-card">
                <div>Kâr/Zarar</div>
                <div class="stat-value {{ kar_renk }}">{{ toplam_kar }} TL ({{ toplam_kar_yuzde }}%)</div>
            </div>
            <div class="stat-card">
                <div>Hisse Sayısı</div>
                <div class="stat-value">{{ hisse_sayisi }}</div>
            </div>
        </div>
        
        <h2>📊 Hisseler</h2>
        {% if hisseler %}
        <table>
            <tr>
                <th>Hisse</th>
                <th>Adet</th>
                <th>Alış</th>
                <th>Güncel</th>
                <th>Kâr %</th>
            </tr>
            {% for h in hisseler %}
            <tr>
                <td><b>{{ h.sembol }}</b></td>
                <td>{{ h.adet }}</td>
                <td>{{ h.alis }} TL</td>
                <td>{{ h.guncel }} TL</td>
                <td class="{{ h.renk }}">{{ h.kar_yuzde }}%</td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>Portföy boş. Aşağıdan hisse ekleyin.</p>
        {% endif %}
        
        <h2>➕ Yeni Hisse Ekle</h2>
        <form method="POST" action="/ekle">
            <div class="form-row">
                <input name="sembol" placeholder="Hisse (örn: THYAO)" required>
            </div>
            <div class="form-row">
                <input name="adet" type="number" placeholder="Adet" required>
            </div>
            <div class="form-row">
                <input name="fiyat" type="number" step="0.01" placeholder="Alış Fiyatı" required>
            </div>
            <button class="btn" type="submit">Ekle</button>
        </form>
        
        <p>
            <a class="btn" href="/yenile">🔄 Yenile</a>
            <a class="btn" href="/telegram">📱 Telegram'a Gönder</a>
        </p>
    </div>
</body>
</html>
"""

def verileri_hazirla():
    """Portföy verilerini hazırlar"""
    p = Portfoy()
    
    hisseler = []
    toplam_maliyet = 0
    toplam_deger = 0
    
    for h in p.hisseler:
        try:
            ticker = yf.Ticker(h["sembol"] + ".IS")
            veri = ticker.history(period="5d")
            if len(veri) < 1:
                continue
            
            guncel = float(veri['Close'].iloc[-1])
            maliyet = h["adet"] * h["alis_fiyati"]
            deger = h["adet"] * guncel
            kar = deger - maliyet
            kar_yuzde = (kar / maliyet) * 100 if maliyet > 0 else 0
            
            toplam_maliyet += maliyet
            toplam_deger += deger
            
            hisseler.append({
                "sembol": h["sembol"],
                "adet": h["adet"],
                "alis": f"{h['alis_fiyati']:.2f}",
                "guncel": f"{guncel:.2f}",
                "kar_yuzde": f"{kar_yuzde:+.2f}",
                "renk": "positive" if kar >= 0 else "negative"
            })
        except:
            continue
    
    toplam_kar = toplam_deger - toplam_maliyet
    toplam_kar_yuzde = (toplam_kar / toplam_maliyet * 100) if toplam_maliyet > 0 else 0
    
    return {
        "tarih": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "hisseler": hisseler,
        "toplam_maliyet": f"{toplam_maliyet:,.2f}",
        "toplam_deger": f"{toplam_deger:,.2f}",
        "toplam_kar": f"{toplam_kar:+,.2f}",
        "toplam_kar_yuzde": f"{toplam_kar_yuzde:+.2f}",
        "kar_renk": "positive" if toplam_kar >= 0 else "negative",
        "hisse_sayisi": len(hisseler)
    }


@app.route('/')
def ana_sayfa():
    veri = verileri_hazirla()
    return render_template_string(HTML, **veri)


@app.route('/ekle', methods=['POST'])
def hisse_ekle():
    sembol = request.form['sembol']
    adet = int(request.form['adet'])
    fiyat = float(request.form['fiyat'])
    
    p = Portfoy()
    p.hisse_ekle(sembol, adet, fiyat)
    
    return redirect(url_for('ana_sayfa'))


@app.route('/yenile')
def yenile():
    return redirect(url_for('ana_sayfa'))


@app.route('/telegram')
def telegram_gonder():
    try:
        from gunluk_rapor import telegram_raporu_gonder
        telegram_raporu_gonder()
        return redirect(url_for('ana_sayfa'))
    except Exception as e:
        return f"Hata: {e}"


if __name__ == '__main__':
    print("=" * 50)
    print("WEB UYGULAMASI BASLATILDI")
    print("=" * 50)
    print("Tarayicinizdan acin:")
    print("  http://localhost:5000")
    print("  veya")
    print("  http://BILGISAYAR_IP:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
