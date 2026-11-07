@echo off
REM Windows icin tek-dosya rdpctl.exe uretir -> dist\rdpctl.exe
cd /d "%~dp0.."
python -m pip install --upgrade pyinstaller -r requirements.txt
pyinstaller --noconfirm packaging\rdpctl.spec
echo Tamam -> dist\rdpctl.exe
pause
