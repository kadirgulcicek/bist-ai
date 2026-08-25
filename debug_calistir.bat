@echo off
cd /d %~dp0
echo ==========================================
echo DEBUG MODU - %date% %time%
echo ==========================================
echo.
py -3.14 web_app.py
echo.
echo ==========================================
echo PROGRAM BITTI - Yukaridaki ciktiyi kontrol edin
echo ==========================================
pause
