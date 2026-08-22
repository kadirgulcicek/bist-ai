"""
Sektör Veritabanı - Her hissenin sektörü tanımlı
"""

# BIST Hisseleri ve Sektörleri
HISSE_SEKTORLERI = {
    # Bankacılık
    "AKBNK": "Bankacılık", "GARAN": "Bankacılık", "ISCTR": "Bankacılık",
    "YKBNK": "Bankacılık", "HALKB": "Bankacılık", "VAKBN": "Bankacılık",
    "SKBNK": "Bankacılık", "ALBRK": "Bankacılık",
    
    # Havacılık
    "THYAO": "Havacılık", "PGSUS": "Havacılık", "TAVHL": "Havacılık",
    
    # Otomotiv
    "FROTO": "Otomotiv", "TOASO": "Otomotiv", "DOAS": "Otomotiv",
    "KARSN": "Otomotiv",
    
    # Sanayi / Endüstri
    "ASELS": "Savunma", "TUKAS": "Gıda", "BIMAS": "Perakende",
    "MGROS": "Perakende", "SOKM": "Perakende",
    
    # Enerji
    "TUPRS": "Enerji", "PETKM": "Enerji", "AYDEM": "Enerji",
    "AKSA": "Enerji", "SISE": "Enerji",
    
    # Demir-Çelik
    "EREGL": "Demir-Çelik", "KRDMD": "Demir-Çelik", "ISDMR": "Demir-Çelik",
    
    # Teknoloji
    "LOGO": "Teknoloji", "KONTR": "Teknoloji", "PAPIL": "Teknoloji",
    "ARCLK": "Teknoloji", "NETAS": "Teknoloji",
    
    # İnşaat / Gayrimenkul
    "EKGYO": "Gayrimenkul", "KLGYO": "Gayrimenkul",
    "NTHOL": "İnşaat", "ENKAI": "İnşaat",
    
    # Holding
    "KCHOL": "Holding", "SAHOL": "Holding", "AGHOL": "Holding",
    "TUPRS": "Holding",
    
    # Gıda
    "ULKER": "Gıda", "CCOLA": "Gıda", "AEFES": "Gıda",
    
    # Tekstil
    "KORDS": "Tekstil", "MAVI": "Tekstil",
    
    # Kimya
    "GOLTS": "Kimya", "BAGFS": "Kimya", "SASA": "Kimya",
    
    # Madencilik
    "KOZAA": "Madencilik", "KOZAL": "Madencilik",
    
    # Diğer
    "VESTL": "Elektronik", "GESAN": "Elektronik"
}


def hisse_sektor(sembol):
    """Bir hissenin sektörünü döndürür"""
    sembol = sembol.upper().replace(".IS", "")
    return HISSE_SEKTORLERI.get(sembol, "Diğer")


def tum_sektorler():
    """Tüm sektörleri listeler"""
    sektorler = set(HISSE_SEKTORLERI.values())
    return sorted(sektorler)


def sektordeki_hisseler(sektor):
    """Bir sektördeki tüm hisseleri listeler"""
    return [h for h, s in HISSE_SEKTORLERI.items() if s == sektor]
