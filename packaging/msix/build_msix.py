"""MSIX paket klasörünü hazırlar (makeappx ile paketlenmeye hazır).

Girdi : dist/rdpctl/          (PyInstaller onedir çıktısı: rdpctl.exe + _internal)
Çıktı : build/msix_stage/     (AppxManifest.xml + Assets + uygulama dosyaları)

Ortam değişkenleri (Partner Center > Ürün kimliği sayfasından):
  MSIX_IDENTITY_NAME            ör. 12345YusufSubasi.rdpctl
  MSIX_PUBLISHER                ör. CN=1A2B3C4D-....
  MSIX_PUBLISHER_DISPLAY_NAME   ör. Yusuf Subaşı
  MSIX_DISPLAY_NAME             Store'da ayrılan uygulama adı (vars. rdpctl)
  MSIX_VERSION                  Major.Minor.Build.0 (Store'da son hane 0 olmalı)

Değerler verilmezse yer tutucularla (test amaçlı) paket hazırlanır; o paket
Store'a gönderilemez.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import sys
from xml.sax.saxutils import escape

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "dist" / "rdpctl"
STAGE = ROOT / "build" / "msix_stage"


def env(name: str, default: str) -> str:
    return (os.environ.get(name) or "").strip() or default


def main() -> int:
    vals = {
        "IDENTITY_NAME": env("MSIX_IDENTITY_NAME", "rdpctl.dev"),
        "PUBLISHER": env("MSIX_PUBLISHER", "CN=rdpctl-dev"),
        "PUBLISHER_DISPLAY_NAME": env("MSIX_PUBLISHER_DISPLAY_NAME", "rdpctl"),
        "DISPLAY_NAME": env("MSIX_DISPLAY_NAME", "rdpctl"),
        "VERSION": env("MSIX_VERSION", "1.0.0.0"),
    }

    errors = []
    if not re.fullmatch(r"[A-Za-z0-9.\-]{3,50}", vals["IDENTITY_NAME"]):
        errors.append("MSIX_IDENTITY_NAME gecersiz (3-50 karakter: harf, rakam, nokta, tire).")
    if not vals["PUBLISHER"].startswith("CN="):
        errors.append("MSIX_PUBLISHER 'CN=' ile baslamali.")
    if not re.fullmatch(r"\d{1,5}\.\d{1,5}\.\d{1,5}\.0", vals["VERSION"]):
        errors.append("MSIX_VERSION Major.Minor.Build.0 biciminde olmali (son hane 0).")
    if errors:
        for e in errors:
            print("HATA:", e)
        return 1
    if not (SRC / "rdpctl.exe").is_file():
        print(f"HATA: {SRC / 'rdpctl.exe'} yok. Once onedir derleyin (RDPCTL_ONEDIR=1).")
        return 1

    if STAGE.exists():
        shutil.rmtree(STAGE)
    shutil.copytree(SRC, STAGE)
    shutil.copytree(HERE / "Assets", STAGE / "Assets",
                    ignore=shutil.ignore_patterns("StoreListing*.png"))

    tpl = (HERE / "AppxManifest.template.xml").read_text(encoding="utf-8")
    for k, v in vals.items():
        tpl = tpl.replace("{{" + k + "}}", escape(v, {'"': "&quot;"}))
    if "{{" in tpl:
        print("HATA: manifestte doldurulmamis alan kaldi.")
        return 1
    (STAGE / "AppxManifest.xml").write_text(tpl, encoding="utf-8")

    placeholder = vals["PUBLISHER"] == "CN=rdpctl-dev"
    print("MSIX klasoru hazir:", STAGE)
    print("  Kimlik  :", vals["IDENTITY_NAME"])
    print("  Yayinci :", vals["PUBLISHER"])
    print("  Surum   :", vals["VERSION"])
    if placeholder:
        print("UYARI: Partner Center kimlik degerleri verilmedi; bu paket yalnizca "
              "test icindir, Store'a GONDERILEMEZ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
