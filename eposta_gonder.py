"""Basit SMTP eposta gonderici (Gmail vb. icin). .env icindeki SMTP_EMAIL / SMTP_SIFRE kullanir."""
import os
import smtplib
import ssl
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_SIFRE = os.environ.get("SMTP_SIFRE")


def smtp_yapilandirilmis_mi():
    return bool(SMTP_EMAIL and SMTP_SIFRE)


def sifirlama_maili_gonder(alici_email, sifirlama_linki):
    """Sifre sifirlama linkini eposta ile gonderir. Basarili olursa True doner."""
    if not smtp_yapilandirilmis_mi():
        print("[eposta] SMTP_EMAIL/SMTP_SIFRE tanimli degil, mail gonderilemedi.")
        return False

    govde = (
        "BIST AI hesabiniz icin sifre sifirlama talebi alindi.\n\n"
        f"Sifrenizi sifirlamak icin asagidaki baglantiya tiklayin (30 dakika gecerlidir):\n{sifirlama_linki}\n\n"
        "Bu talebi siz yapmadiysaniz bu epostayi yok sayabilirsiniz."
    )
    mesaj = MIMEText(govde, "plain", "utf-8")
    mesaj["Subject"] = "BIST AI - Sifre Sifirlama"
    mesaj["From"] = SMTP_EMAIL
    mesaj["To"] = alici_email

    try:
        baglam = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as sunucu:
            sunucu.starttls(context=baglam)
            sunucu.login(SMTP_EMAIL, SMTP_SIFRE)
            sunucu.sendmail(SMTP_EMAIL, [alici_email], mesaj.as_string())
        return True
    except Exception as e:
        print(f"[eposta] Gonderim hatasi: {e}")
        return False
