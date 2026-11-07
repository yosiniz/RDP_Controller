# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — rdpctl tek-dosya masaüstü uygulaması.

Her platformda (Windows/macOS/Linux) O platformda çalıştırılır:
    pyinstaller packaging/rdpctl.spec
Çıktı: dist/rdpctl (Linux/macOS) veya dist\\rdpctl.exe (Windows)
"""
import sys

# pynput/mss/watchdog platform-özel arka uçlarını çalışma anında dinamik
# yükler. Bunlar pyinstaller-hooks-contrib tarafından otomatik toplanır;
# ek güvence için platforma göre açık hidden-import listesi veriyoruz.
# (collect_submodules kullanmıyoruz: başsız derleme ortamında pynput'un
#  import anında X sunucusu araması derlemeyi bozabiliyor.)
hiddenimports = [
    'pynput.keyboard._base', 'pynput.mouse._base',
    'watchdog.observers', 'watchdog.observers.polling',
    'mss',
]
if sys.platform.startswith('win'):
    hiddenimports += ['pynput.keyboard._win32', 'pynput.mouse._win32',
                      'mss.windows', 'watchdog.observers.read_directory_changes']
elif sys.platform == 'darwin':
    hiddenimports += ['pynput.keyboard._darwin', 'pynput.mouse._darwin',
                      'mss.darwin', 'watchdog.observers.fsevents']
else:
    hiddenimports += ['pynput.keyboard._xorg', 'pynput.mouse._xorg',
                      'mss.linux', 'watchdog.observers.inotify']

datas = []

block_cipher = None

a = Analysis(
    ['../run_app.py'],
    pathex=['..'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['pytest', 'numpy', 'pandas'],
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
    name='rdpctl',
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

# macOS için .app paketi
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='rdpctl.app',
        icon=None,
        bundle_identifier='com.rdpctl.app',
        info_plist={
            'NSHighResolutionCapable': 'True',
            # macOS izin istemleri için açıklamalar:
            'NSScreenCaptureUsageDescription': 'Uzaktan destek için ekran paylaşımı.',
            'NSAppleEventsUsageDescription': 'Uzaktan fare/klavye kontrolü.',
        },
    )
