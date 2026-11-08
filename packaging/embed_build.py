"""CI yardimcisi: yapi (build) kimligini version.py'ye gomer.

RDPCTL_BUILD_ID ortam degiskenini (CI'da git commit SHA) version.py icine
yazar. Bossa hicbir sey yapmaz. Mesajlar ASCII (Windows cp1252 konsol icin).
"""
import os
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

bid = (os.environ.get("RDPCTL_BUILD_ID") or "").strip()
if not bid:
    print("RDPCTL_BUILD_ID bos - build kimligi gomulmedi.")
    raise SystemExit(0)

if any(c in bid for c in '"\n\r\\'):
    raise SystemExit("Gecersiz build kimligi.")

p = pathlib.Path("rdpctl/version.py")
s = p.read_text(encoding="utf-8")
s = s.replace('_EMBEDDED_BUILD = ""', f'_EMBEDDED_BUILD = "{bid}"', 1)
p.write_text(s, encoding="utf-8")
print(f"Build kimligi gomuldu: {bid}")
