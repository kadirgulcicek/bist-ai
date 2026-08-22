"""
Log dosyasını kontrol eder
Çalışıp çalışmadığını, hataları gösterir
"""

import os
from datetime import datetime

log_dosyasi = "log.txt"

if not os.path.exists(log_dosyasi):
    print("❌ log.txt bulunamadı. Sistem henüz çalışmamış olabilir.")
else:
    print("=" * 50)
    print(f"📄 LOG DOSYASI İÇERİĞİ")
    print("=" * 50)
    
    with open(log_dosyasi, 'r', encoding='utf-8', errors='ignore') as f:
        satirlar = f.readlines()
    
    # Son 30 satırı göster
    print(f"\n📊 Toplam {len(satirlar)} satır log")
    print(f"📅 Son güncelleme: {datetime.fromtimestamp(os.path.getmtime(log_dosyasi))}")
    print("\n📋 Son 30 satır:\n")
    
    for satir in satirlar[-30:]:
        print(satir.rstrip())
