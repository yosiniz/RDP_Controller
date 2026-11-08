"""CI yardimcisi: RDPCTL_RELAY_HOST/PORT ortam degiskenlerini config.py'ye gomer.

Derleme sirasinda cagrilir. Degisken bossa hicbir sey yapmaz (relay kapali =
uygulama dogrudan-IP moduna duser). Deger, deponun sahibi tarafindan
'repository variable' olarak verilir; guvenilir kabul edilir.

Not: Mesajlar yalnizca ASCII; Windows konsolu (cp1252) Turkce karakterleri
basamayip UnicodeEncodeError ile derlemeyi bozabiliyor. Yine de guvenlik
icin cikti UTF-8'e ayarlanir.
"""
import os
import pathlib
import sys

try:  # Windows'ta cp1252 konsolda bile guvenli olsun
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

host = (os.environ.get("RDPCTL_RELAY_HOST") or "").strip()
port = (os.environ.get("RDPCTL_RELAY_PORT") or "").strip()

if not host:
    print("RDPCTL_RELAY_HOST bos - relay gomulmedi (dogrudan mod).")
    raise SystemExit(0)

# Basit guvenlik: gomulen degerler tirnak/yeni satir icermemeli.
if any(c in host + port for c in '"\n\r\\'):
    raise SystemExit("Gecersiz relay degeri (tirnak/yeni satir iceremez).")

p = pathlib.Path("rdpctl/config.py")
s = p.read_text(encoding="utf-8")
s = s.replace('_EMBEDDED_RELAY_HOST = ""', f'_EMBEDDED_RELAY_HOST = "{host}"', 1)
if port:
    s = s.replace('_EMBEDDED_RELAY_PORT = ""', f'_EMBEDDED_RELAY_PORT = "{port}"', 1)
p.write_text(s, encoding="utf-8")
print(f"Relay gomuldu: {host}:{port or '7444'}")
