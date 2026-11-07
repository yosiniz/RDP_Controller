"""Mesaj çerçeveleme (framing) ve TLS yardımcıları.

Tel üzerindeki her mesaj:  [4 bayt uzunluk big-endian][JSON gövde]
İkili veri (ekran kareleri) base64 ile JSON içinde taşınır — basit ve
güvenli tutmak için. Taşıma katmanı TLS olduğundan gövde zaten şifrelidir.
"""
from __future__ import annotations

import datetime as _dt
import ipaddress
import json
import os
import socket
import ssl
import struct
from typing import Any, Dict

# --- Mesaj tipleri ---------------------------------------------------------
MSG_HELLO = "hello"            # controller -> host: kimlik + oturum kodu
MSG_AUTH_OK = "auth_ok"        # host -> controller: onay bekleniyor
MSG_AUTH_FAIL = "auth_fail"    # host -> controller: kod/kimlik reddedildi
MSG_CONSENT_PENDING = "consent_pending"
MSG_CONSENT_GRANTED = "consent_granted"
MSG_CONSENT_DENIED = "consent_denied"
MSG_FRAME = "frame"            # host -> controller: ekran karesi (jpeg b64)
MSG_INPUT = "input"            # controller -> host: fare/klavye olayı
MSG_BYE = "bye"

_MAX_MSG = 32 * 1024 * 1024  # 32 MiB üst sınır (DoS'a karşı)


def send_msg(sock: socket.socket, obj: Dict[str, Any]) -> None:
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    if len(data) > _MAX_MSG:
        raise ValueError("mesaj çok büyük")
    sock.sendall(struct.pack(">I", len(data)) + data)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("bağlantı kapandı")
        buf.extend(chunk)
    return bytes(buf)


def recv_msg(sock: socket.socket) -> Dict[str, Any]:
    (length,) = struct.unpack(">I", _recv_exact(sock, 4))
    if length > _MAX_MSG:
        raise ValueError("gelen mesaj boyut sınırını aşıyor")
    return json.loads(_recv_exact(sock, length).decode("utf-8"))


# --- Relay (buluşma) istemcisi --------------------------------------------
class RelayError(Exception):
    """Relay eşleştirme hatası. `reason` alanı makine-okunur sebebi taşır."""

    def __init__(self, reason: str, message: str = ""):
        self.reason = reason
        super().__init__(message or reason)


def connect_via_relay(relay_host: str, relay_port: int, role: str, code: str,
                      timeout: float = 20.0) -> socket.socket:
    """Relay'e bağlanıp eşleşmeyi bekler; eşleşince ÇIPLAK TCP soketi döner.

    Dönen soket SONRADAN TLS ile sarılır (host: server_side, controller:
    client). Böylece uçtan uca şifreleme relay'den bağımsız kurulur.

    role: "host" | "controller". Eşleşme olmazsa RelayError(reason) fırlatır:
      - not_found   : (controller) o kodla bekleyen host yok
      - code_in_use : (host) aynı kod zaten kullanılıyor
      - timeout     : eşleşme süresi doldu
    """
    if role not in ("host", "controller"):
        raise ValueError("role 'host' veya 'controller' olmalı")
    raw = socket.create_connection((relay_host, relay_port), timeout=timeout)
    try:
        send_msg(raw, {"type": "register", "role": role, "code": code})
        # host, controller gelene kadar bekleyebilir; makul bir üst sınır ver.
        raw.settimeout(None if role == "host" else timeout)
        reply = recv_msg(raw)
    except (OSError, ConnectionError, ValueError) as exc:
        try:
            raw.close()
        except OSError:
            pass
        raise RelayError("relay_unreachable", f"relay'e ulaşılamadı: {exc}")
    t = reply.get("type")
    if t == "paired":
        raw.settimeout(None)
        return raw
    try:
        raw.close()
    except OSError:
        pass
    if t == "error":
        raise RelayError(reply.get("reason", "unknown"))
    raise RelayError("unexpected", f"beklenmeyen relay yanıtı: {reply!r}")


# --- TLS -------------------------------------------------------------------

def generate_self_signed_cert(cert_path: str, key_path: str) -> str:
    """Host için kendinden imzalı sertifika üretir. Parmak izini döndürür.

    Parmak izi, host ekranında gösterilir; controller'a bağlanmadan önce
    MITM'e karşı doğrulatmak için kullanılabilir.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "rdpctl-host")])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(minutes=1))
        .not_valid_after(now + _dt.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("rdpctl-host")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    os.chmod(key_path, 0o600)
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    fp = cert.fingerprint(hashes.SHA256())
    return ":".join(f"{b:02X}" for b in fp)


def cert_fingerprint(cert_pem: bytes) -> str:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    cert = x509.load_pem_x509_certificate(cert_pem)
    fp = cert.fingerprint(hashes.SHA256())
    return ":".join(f"{b:02X}" for b in fp)


def server_tls_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return ctx


def client_tls_context(expected_fingerprint: str | None = None) -> ssl.SSLContext:
    """İstemci TLS bağlamı.

    Kendinden imzalı sertifika kullanıldığından CA doğrulaması kapalıdır;
    bunun yerine (varsa) host'ta gösterilen parmak izi el sıkışmadan sonra
    doğrulanır. Böylece MITM'e karşı koruma kullanıcı onayına dayanır.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def is_valid_host(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        pass
    if len(value) > 253:
        return False
    return all(part and len(part) <= 63 for part in value.split("."))
