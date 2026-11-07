"""Merkezi yapılandırma — relay (buluşma) sunucusu adresi.

Relay modu, iki bilgisayarın AYNI AĞDA olmadan ve HİÇBİR PORT AÇMADAN,
yalnızca oturum koduyla buluşmasını sağlar. Her iki taraf da relay'e
DIŞARI doğru bağlanır (giden bağlantı), relay onları kodla eşleştirir ve
aralarında ham baytları aktarır. Uçtan uca TLS host ile controller
arasında kurulduğundan relay trafiği GÖREMEZ (zero-trust aktarıcı).

Relay adresi derleme zamanında ortam değişkeniyle gömülebilir
(RDPCTL_RELAY_HOST) ya da çalışma anında okunur. Boşsa uygulama eski
davranışa (doğrudan IP ile yerel ağ bağlantısı) düşer.
"""
from __future__ import annotations

import os

# Geliştirici, uygulamayı derlerken RDPCTL_RELAY_HOST ortam değişkenini
# kendi relay sunucusunun genel adresine ayarlar (ör. "relay.ornek.com").
# PyInstaller bu değeri çalıştırılabilir dosyanın içine gömmez; bunun yerine
# değer, aşağıdaki _EMBEDDED sabitine derleme betiği tarafından yazılabilir
# veya son kullanıcı ortamında da okunur. Pratikte GitHub Actions, bu değeri
# ortam değişkeni olarak verir ve biz derleme anında _EMBEDDED'e gömeriz.
_EMBEDDED_RELAY_HOST = ""   # derleme betiği doldurabilir; boş = gömülü değer yok
_EMBEDDED_RELAY_PORT = ""   # aynı şekilde


def _first_nonempty(*vals: str) -> str:
    for v in vals:
        if v:
            return v.strip()
    return ""


DEFAULT_RELAY_HOST = _first_nonempty(
    os.environ.get("RDPCTL_RELAY_HOST", ""),
    _EMBEDDED_RELAY_HOST,
)

try:
    DEFAULT_RELAY_PORT = int(
        _first_nonempty(os.environ.get("RDPCTL_RELAY_PORT", ""),
                        _EMBEDDED_RELAY_PORT) or "7444"
    )
except ValueError:
    DEFAULT_RELAY_PORT = 7444


def relay_configured() -> bool:
    """Relay modu etkin mi? (adres tanımlıysa evet)"""
    return bool(DEFAULT_RELAY_HOST)


def relay_target() -> tuple[str, int]:
    return DEFAULT_RELAY_HOST, DEFAULT_RELAY_PORT
