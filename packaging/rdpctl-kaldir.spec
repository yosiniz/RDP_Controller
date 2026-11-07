# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — rdpctl kaldırıcı (rdpctl-kaldir).

Her platformda (Windows/macOS/Linux) O platformda çalıştırılır:
    pyinstaller packaging/rdpctl-kaldir.spec
Çıktı: dist/rdpctl-kaldir(.exe)
"""
import os
import sys

# Kaldırıcı yalnızca standart kütüphane + tkinter kullanır; ekran/girdi
# kütüphanelerini pakete almayarak dosyayı küçük tutuyoruz.
hiddenimports = ['winreg'] if sys.platform.startswith('win') else []

datas = []

# --- Yanlış-pozitif azaltma ayarları -------------------------------------
# UPX sıkıştırması bir antivirüs "yanlış pozitif" tetikleyicisidir; kapatıyoruz.
USE_UPX = False
# RDPCTL_ONEDIR=1 ise tek .exe yerine KLASÖR dağıtımı üretilir (daha az
# yanlış pozitif; çalışırken kendini geçici klasöre açmaz).
ONEDIR = os.environ.get("RDPCTL_ONEDIR") == "1"
# Windows'ta sürüm/üretici bilgisi ekle (imzasız dosyalarda güveni artırır).
VERSION_FILE = os.path.join(SPECPATH, "version_uninstall.txt") if sys.platform.startswith("win") else None


block_cipher = None

a = Analysis(
    ['../run_uninstall.py'],
    pathex=['..'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['pytest', 'numpy', 'pandas', 'pynput', 'mss', 'PIL', 'watchdog', 'cryptography'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

MAC = sys.platform == 'darwin'
# macOS'ta .app HER ZAMAN onedir olmalı (onefile .app macOS güvenliğiyle çakışır).
ONEDIR_MODE = ONEDIR or MAC

exe = EXE(
    pyz,
    a.scripts,
    [] if ONEDIR_MODE else a.binaries,
    [] if ONEDIR_MODE else a.zipfiles,
    [] if ONEDIR_MODE else a.datas,
    [],
    exclude_binaries=ONEDIR_MODE,
    name='rdpctl-kaldir',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=USE_UPX,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version=VERSION_FILE,
)

if ONEDIR_MODE:
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False, upx=USE_UPX, upx_exclude=[], name='rdpctl-kaldir',
    )

if MAC:
    app = BUNDLE(
        coll,
        name='rdpctl-kaldir.app',
        icon=None,
        bundle_identifier='com.rdpctl.uninstall',
        info_plist={
            'NSHighResolutionCapable': 'True',
        },
    )
