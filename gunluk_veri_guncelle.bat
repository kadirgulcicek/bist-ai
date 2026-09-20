@echo off
cd /d %~dp0
if not exist logs mkdir logs
echo [%date% %time%] Gunluk veri akisi basladi. >> logs\gunluk_veri.log
py -3 gunluk_veri_deposu.py --semboller bist_sembol_cache.json --db data\piyasa_verileri.db >> logs\gunluk_veri.log 2>&1
set CIKIS=%ERRORLEVEL%
if %CIKIS% EQU 0 (
	py -3 kap_veri_deposu.py --db data\piyasa_verileri.db >> logs\gunluk_veri.log 2>&1
	set CIKIS=%ERRORLEVEL%
)
echo [%date% %time%] Gunluk veri akisi bitti. Kod: %CIKIS% >> logs\gunluk_veri.log
exit /b %CIKIS%