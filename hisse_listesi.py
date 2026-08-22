"""
BIST - Tüm Hisselerin Listesi
BIST 100 ve BIST 30 hisseleri
"""

# BIST 30 Hisseler (Büyük şirketler)
BIST_30 = [
    "AKBNK.IS", "ARCLK.IS", "ASELS.IS", "BIMAS.IS", "EKGYO.IS",
    "EREGL.IS", "FROTO.IS", "GARAN.IS", "HEKTS.IS", "ISCTR.IS",
    "KCHOL.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "PETKM.IS",
    "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TAVHL.IS",
    "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TUPRS.IS",
    "VESTL.IS", "YKBNK.IS", "PETKM.IS", "ENKAI.IS", "GESAN.IS"
]

# BIST 100'e Genişletilmiş Liste
BIST_100_EK = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKSA.IS", "ALARK.IS",
    "ALFAS.IS", "ANSGR.IS", "ASUZU.IS", "AYDEM.IS", "BAGFS.IS",
    "BERA.IS", "BIOEN.IS", "BRYAT.IS", "BUCIM.IS", "CCOLA.IS",
    "CEMTS.IS", "CIMSA.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS",
    "ECZYT.IS", "EGEEN.IS", "ENJSA.IS", "ERBOS.IS", "FENER.IS",
    "GENIL.IS", "GLMTR.IS", "GOLTS.IS", "GUBRF.IS", "HALKB.IS",
    "IEYHO.IS", "INDES.IS", "IPEKE.IS", "ISDMR.IS", "ISFIN.IS",
    "ISGYO.IS", "ISMEN.IS", "JANTS.IS", "KAPLM.IS", "KARSN.IS",
    "KAYSE.IS", "KLGYO.IS", "KMPUR.IS", "KONTR.IS", "KORDS.IS",
    "KONYA.IS", "LOGO.IS", "MAVI.IS", "MGROS.IS", "NTHOL.IS",
    "NUGYO.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PENTA.IS",
    "QUAGR.IS", "RYSAS.IS", "SARKY.IS", "SDTTR.IS", "SKBNK.IS",
    "SOKM.IS", "TAKS.IS", "TARKM.IS", "TCMB.IS", "TMSN.IS",
    "TUKAS.IS", "TURSG.IS", "ULKER.IS", "VAKBN.IS", "VKGYO.IS",
    "YATAS.IS", "YEOTK.IS", "YKSLN.IS", "ZOREN.IS"
]

# Tüm listeyi birleştir ve tekrarları sil
TUM_HISSELER = sorted(list(set(BIST_30 + BIST_100_EK)))

def hisse_listesi_getir():
    """Tüm hisselerin listesini döndürür"""
    return TUM_HISSELER

if __name__ == "__main__":
    liste = hisse_listesi_getir()
    print(f"📊 Toplam {len(liste)} hisse takip edilecek:")
    print(", ".join(liste[:10]) + "...")
