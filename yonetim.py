"""
Sistem Yönetim Paneli
- Sistemi başlat/durdur
- Durumu kontrol et
- Manuel rapor gönder
"""

import subprocess
import os
import sys
from datetime import datetime


def sistem_durumu():
    """Çalışan Python süreçlerini gösterir"""
    print("=" * 50)
    print("📊 SİSTEM DURUMU")
    print("=" * 50)
    
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
            capture_output=True, text=True
        )
        print(result.stdout)
        
        if 'python.exe' in result.stdout:
            print("✅ Sistem çalışıyor!")
        else:
            print("⚠️ Sistem çalışmıyor.")
            
    except Exception as e:
        print(f"❌ Hata: {e}")


def manuel_rapor():
    """Şimdi rapor gönder"""
    print("\n  Manuel rapor gönderiliyor...")
    
    # Buraya kendi dosya yolunuzu yazın
    dosya_yolu = os.path.dirname(os.path.abspath(__file__))
    
    try:
        # gunluk_bildirim.py'den sadece rapor kısmını çalıştır
        from gunluk_bildirim import GunlukBildirim
        from telegram_bot import BISTTelegramBot
        
        # Aynı token ve chat ID (kendi bilgilerinizi yazın)
        TOKEN = "BURAYA_TOKEN"
        CHAT_ID = "BURAYA_CHAT_ID"
        
        bildirim = GunlukBildirim(TOKEN, CHAT_ID)
        bildirim.sabah_raporu()
        print("✅ Rapor gönderildi!")
        
    except Exception as e:
        print(f"❌ Hata: {e}")


def log_goster():
    """Log dosyasını göster"""
    print("\n📄 Log dosyası gösteriliyor...")
    
    if os.path.exists("log.txt"):
        with open("log.txt", "r", encoding="utf-8", errors="ignore") as f:
            satirlar = f.readlines()
        
        print(f"📊 Toplam {len(satirlar)} satır")
        print("\nSon 20 satır:\n")
        for s in satirlar[-20:]:
            print(s.rstrip())
    else:
        print("⚠️ Henüz log oluşmamış.")


def sistemi_durdur():
    """Çalışan Python süreçlerini sonlandır"""
    print("\n🛑 Sistem durduruluyor...")
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
        print("✅ Durduruldu!")
    except Exception as e:
        print(f"❌ Hata: {e}")


def menu():
    """Ana menü"""
    while True:
        print("\n" + "=" * 50)
        print("🎯 BIST AI YÖNETİM PANELİ")
        print("=" * 50)
        print("1. 📊 Sistem durumunu göster")
        print("2. 📤 Şimdi rapor gönder")
        print("3. 📄 Logları göster")
        print("4. 🛑 Sistemi durdur")
        print("5. 🚪 Çıkış")
        print()
        
        secim = input("Seçiminiz (1-5): ").strip()
        
        if secim == "1":
            sistem_durumu()
        elif secim == "2":
            manuel_rapor()
        elif secim == "3":
            log_goster()
        elif secim == "4":
            sistemi_durdur()
        elif secim == "5":
            print("👋 Görüşürüz!")
            break
        else:
            print("⚠️ Geçersiz seçim")
        
        input("\nDevam etmek için Enter'a basın...")


if __name__ == "__main__":
    menu()
