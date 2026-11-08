"""Surum bilgisi ve yapi (build) kimligi.

VERSION insan-okunur surum. _EMBEDDED_BUILD, CI tarafindan her derlemede
doldurulan benzersiz yapi kimligidir (git commit SHA). Guncelleyici,
kendi BUILD'ini uzaktaki 'latest' surumun BUILD'iyle karsilastirir; farkli
ise guncelleme vardir.
"""
from __future__ import annotations

import os

VERSION = "1.0.0"

# CI (embed_build.py) doldurur; bos = gelistirme/derlenmemis.
_EMBEDDED_BUILD = ""


def build_id() -> str:
    return (os.environ.get("RDPCTL_BUILD_ID") or _EMBEDDED_BUILD or "").strip()


def short_build() -> str:
    b = build_id()
    return b[:7] if b else "dev"


def version_string() -> str:
    """Kullaniciya gosterilen kisa surum, orn. 'v1.0.0 · a1b2c3d'."""
    return f"v{VERSION} · {short_build()}"
