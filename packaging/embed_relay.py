"""CI yardımcı: RDPCTL_RELAY_HOST/PORT ortam değişkenlerini config.py'ye gömer.

Derleme sırasında çağrılır. Değişken boşsa hiçbir şey yapmaz (relay kapalı =
uygulama doğrudan-IP moduna düşer). Değer, deponun sahibi tarafından
'repository variable' olarak verilir; güvenilir kabul edilir.
"""
import os
import pathlib

host = (os.environ.get("RDPCTL_RELAY_HOST") or "").strip()
port = (os.environ.get("RDPCTL_RELAY_PORT") or "").strip()

if not host:
    print("RDPCTL_RELAY_HOST boş — relay gömülmedi (doğrudan mod).")
    raise SystemExit(0)

# Basit güvenlik: gömülen değerler tırnak/yeni satır içermemeli.
if any(c in host + port for c in '"\n\r\\'):
    raise SystemExit("Geçersiz relay değeri (tırnak/yeni satır içeremez).")

p = pathlib.Path("rdpctl/config.py")
s = p.read_text(encoding="utf-8")
s = s.replace('_EMBEDDED_RELAY_HOST = ""', f'_EMBEDDED_RELAY_HOST = "{host}"', 1)
if port:
    s = s.replace('_EMBEDDED_RELAY_PORT = ""', f'_EMBEDDED_RELAY_PORT = "{port}"', 1)
p.write_text(s, encoding="utf-8")
print(f"Relay gömüldü: {host}:{port or '7444'}")
