"""Kimlik ve oturum kodu doğrulama.

- Controller giriş yaparken AD ve SOYAD girmek zorundadır (boş olamaz).
- Host, başlangıçta rastgele bir oturum kodu üretir; controller bunu
  bilmek zorundadır. Kod sabit-zamanlı (constant-time) karşılaştırma ile
  doğrulanır, böylece zamanlama saldırıları önlenir.
- Çok sayıda hatalı deneme IP bazında geçici olarak kilitlenir.
"""
from __future__ import annotations

import hmac
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict

_NAME_RE = re.compile(r"^[\wÀ-ɏЀ-ӿ' .-]{1,40}$", re.UNICODE)


def generate_session_code(groups: int = 3, group_len: int = 3) -> str:
    """Örn. '428-170-935' biçiminde okunabilir rastgele oturum kodu."""
    digits = "".join(secrets.choice("0123456789") for _ in range(groups * group_len))
    return "-".join(digits[i : i + group_len] for i in range(0, len(digits), group_len))


def normalize_code(code: str) -> str:
    return re.sub(r"[^0-9]", "", code or "")


def code_matches(expected: str, supplied: str) -> bool:
    a = normalize_code(expected).encode()
    b = normalize_code(supplied).encode()
    return hmac.compare_digest(a, b)


def valid_name(value: str) -> bool:
    return bool(value) and bool(_NAME_RE.match(value.strip()))


@dataclass
class Identity:
    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def validate(self) -> None:
        if not valid_name(self.first_name):
            raise ValueError("Geçerli bir ad girilmelidir.")
        if not valid_name(self.last_name):
            raise ValueError("Geçerli bir soyad girilmelidir.")


@dataclass
class RateLimiter:
    """IP başına basit brute-force koruması."""

    max_attempts: int = 5
    window_seconds: int = 300
    lockout_seconds: int = 300
    _fails: Dict[str, list] = field(default_factory=dict)
    _locked: Dict[str, float] = field(default_factory=dict)

    def is_locked(self, ip: str) -> bool:
        until = self._locked.get(ip, 0)
        if until and until > time.monotonic():
            return True
        if until:
            self._locked.pop(ip, None)
        return False

    def record_failure(self, ip: str) -> None:
        now = time.monotonic()
        window = [t for t in self._fails.get(ip, []) if now - t < self.window_seconds]
        window.append(now)
        self._fails[ip] = window
        if len(window) >= self.max_attempts:
            self._locked[ip] = now + self.lockout_seconds
            self._fails[ip] = []

    def record_success(self, ip: str) -> None:
        self._fails.pop(ip, None)
        self._locked.pop(ip, None)
