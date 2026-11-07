# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — rdpctl kaldırıcı (rdpctl-kaldir).

Her platformda (Windows/macOS/Linux) O platformda çalıştırılır:
    pyinstaller packaging/rdpctl-kaldir.spec
Çıktı: dist/rdpctl-kaldir(.exe)
"""
import sys

# Kaldırıcı yalnızca standart kütüphane + tkinter kullanır; ekran/girdi
# kütüphanelerini pakete almayarak dosyayı küçük tutuyoruz.
hiddenimports = ['winreg'] if sys.platform.startswith('win') else []

datas = []

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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='rdpctl-kaldir',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI uygulaması: konsol penceresi açma
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

