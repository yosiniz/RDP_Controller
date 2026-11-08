"""Uygulama icinden guncelleme.

Calisma mantigi:
  - CI, her derlemede GitHub'da 'latest' adli bir surum (release) yayimlar;
    icinde platform ikilisi (rdpctl.exe / rdpctl-macos.zip) ve yapi kimligini
    tutan 'latest.txt' bulunur. Release varliklari HERKESE ACIKTIR (GitHub
    oturumu gerekmez).
  - Guncelleyici latest.txt'yi indirir, kendi build_id'siyle karsilastirir.
    Farkliysa yeni ikiliyi indirir, kendini degistirir ve yeniden baslatir.

Kendini degistirme, calisan surecin disinda kucuk bir yardimci betikle
yapilir (uygulama kapandiktan sonra dosyayi degistirip tekrar acar).
"""
from __future__ import annotations

import os
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from . import version

REPO = "yosiniz/RDP_Controller"
_BASE = f"https://github.com/{REPO}/releases/download/latest"
BUILD_URL = f"{_BASE}/latest.txt"
WIN_URL = f"{_BASE}/rdpctl.exe"


def _mac_url() -> str:
    import platform
    m = platform.machine().lower()
    arch = "apple-silicon" if m in ("arm64", "aarch64") else "intel"
    return f"{_BASE}/rdpctl-{arch}.app.zip"

_UA = {"User-Agent": "rdpctl-updater"}


def is_frozen() -> bool:
    """PyInstaller ile paketlenmis (gercek .exe/.app) olarak mi calisiyor?"""
    return bool(getattr(sys, "frozen", False))


def _http_get(url: str, timeout: float = 20.0) -> bytes:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def remote_build() -> str:
    return _http_get(BUILD_URL).decode("utf-8", "replace").strip()


def check() -> tuple[bool, str]:
    """(guncelleme_var, uzak_build). Ag hatasinda (False, '').

    Yerel/gelistirme derlemesinde (build kimligi bos) guncelleme onerilmez;
    bu surumler 'git pull' ile guncellenir.
    """
    cur = version.build_id()
    if not cur:
        return (False, "")
    try:
        rem = remote_build()
    except Exception:
        return (False, "")
    if rem and rem != cur:
        return (True, rem)
    return (False, rem)


# --- Platforma gore uygula --------------------------------------------------
def apply_update() -> None:
    """Yeni ikiliyi indirir, kendini degistirip yeniden baslatir.

    Basarili olursa bu fonksiyon DONMEZ dememeli; cagiran taraf hemen
    uygulamayi kapatmalidir (yardimci betik dosyayi degistirir).
    Hata olursa Exception firlatir.
    """
    if not is_frozen():
        raise RuntimeError("Guncelleme yalnizca paketlenmis surumde yapilabilir "
                           "(gelistirme modunda 'git pull' kullanin).")
    if sys.platform.startswith("win"):
        _apply_windows()
    elif sys.platform == "darwin":
        _apply_macos()
    else:
        _apply_linux()


def _apply_windows() -> None:
    data = _http_get(WIN_URL, timeout=180)
    tmp = tempfile.mkdtemp(prefix="rdpctl-upd-")
    new_exe = os.path.join(tmp, "rdpctl_new.exe")
    with open(new_exe, "wb") as f:
        f.write(data)
    cur = sys.executable  # calisan rdpctl.exe
    bat = os.path.join(tmp, "update.bat")
    with open(bat, "w", encoding="ascii") as f:
        f.write(
            "@echo off\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'copy /y "{new_exe}" "{cur}" >nul\r\n'
            f'start "" "{cur}"\r\n'
            'del "%~f0"\r\n'
        )
    subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)  # CREATE_NO_WINDOW


def _apply_macos() -> None:
    data = _http_get(_mac_url(), timeout=300)
    tmp = tempfile.mkdtemp(prefix="rdpctl-upd-")
    zpath = os.path.join(tmp, "new.zip")
    with open(zpath, "wb") as f:
        f.write(data)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    # Zip icinde rdpctl.app bekliyoruz
    new_app = os.path.join(tmp, "rdpctl.app")
    if not os.path.isdir(new_app):
        # bazen bir alt klasorde olabilir; ara
        for root, dirs, _ in os.walk(tmp):
            if "rdpctl.app" in dirs:
                new_app = os.path.join(root, "rdpctl.app")
                break
    # Calisan uygulamanin .app paketi: .../rdpctl.app/Contents/MacOS/rdpctl
    bundle = os.path.abspath(os.path.join(sys.executable, "..", "..", ".."))
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", new_app], check=False)
    script = os.path.join(tmp, "update.sh")
    with open(script, "w", encoding="utf-8") as f:
        f.write(
            "#!/bin/bash\n"
            "sleep 2\n"
            f'rm -rf "{bundle}"\n'
            f'mv "{new_app}" "{bundle}"\n'
            f'open "{bundle}"\n'
        )
    os.chmod(script, 0o755)
    subprocess.Popen(["/bin/bash", script])


def _apply_linux() -> None:
    # Linux ikilisi 'latest' surumde yayinlanmiyor; gelistirme/ozel kurulum.
    raise RuntimeError("Linux'ta otomatik guncelleme desteklenmiyor; "
                       "deposundan yeniden derleyin.")
