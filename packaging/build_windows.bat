@echo off
chcp 65001 >nul
setlocal
title rdpctl - Windows exe olusturucu
cd /d "%~dp0.."

echo ============================================================
echo   rdpctl icin Windows uygulamasi (rdpctl.exe) olusturuluyor
echo ============================================================
echo.

REM --- Python'u bul (once 'py' launcher, sonra 'python') ---
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [HATA] Python bulunamadi.
    echo.
    echo Lutfen once Python 3.10+ kurun:
    echo   https://www.python.org/downloads/
    echo   ^(Kurulum ekraninda "Add python.exe to PATH" kutusunu ISARETLEYIN^)
    echo.
    echo Python'u kurduktan sonra bu dosyayi tekrar calistirin.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python bulundu: %PY%
%PY% --version
echo.
echo Gerekli paketler kuruluyor ^(internet gerekir, birkac dakika surebilir^)...
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install --upgrade pyinstaller -r requirements.txt
if errorlevel 1 (
    echo.
    echo [HATA] Paket kurulumu basarisiz oldu. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

echo.
echo Uygulama paketleniyor...
%PY% -m PyInstaller --noconfirm packaging\rdpctl.spec
if errorlevel 1 (
    echo.
    echo [HATA] Paketleme basarisiz oldu.
    pause
    exit /b 1
)

echo.
echo Kaldirici paketleniyor ^(rdpctl-kaldir.exe^)...
%PY% -m PyInstaller --noconfirm packaging\rdpctl-kaldir.spec
if errorlevel 1 (
    echo.
    echo [HATA] Kaldirici paketlenemedi.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TAMAM!  Dosyalariniz hazir:
echo   %cd%\dist\rdpctl.exe          ^(uygulama^)
echo   %cd%\dist\rdpctl-kaldir.exe   ^(kaldirici^)
echo ============================================================
echo.
echo SHA-256 ozetleri ^(karsi tarafla paylasip dogrulatabilirsiniz^):
for %%F in ("dist\rdpctl.exe" "dist\rdpctl-kaldir.exe") do (
    if exist %%F certutil -hashfile %%F SHA256 | findstr /v ":"
)
echo.
echo NOT: Windows "bilinmeyen yayimci/virus" uyarisi verebilir. Bu bir
echo      YANLIS POZITIF'tir. Kalici cozum kod imzalamadir; ayrintilar:
echo      VIRUS_UYARISI_COZUM.md
echo.
echo rdpctl.exe tek dosyadir; istediginiz bilgisayara kopyalayip
echo cift tiklayarak calistirabilirsiniz ^(Python gerekmez^).
echo.
REM dist klasorunu Gezgin'de ac
start "" "%cd%\dist"
pause
endlocal
