@echo off
cd /d %~dp0
echo [%date% %time%] Sistem baslatiliyor... >> log.txt
py -3.14 gunluk_bildirim.py >> log.txt 2>&1
echo [%date% %time%] Sistem durdu. >> log.txt
pause


