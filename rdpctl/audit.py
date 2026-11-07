"""Denetim (audit) günlüğü.

Kontrol edilen bilgisayarda OLAN her şeyi kaydeder:
- oturum başlangıç/bitiş, kimin (ad-soyad) bağlandığı, kaynak IP
- uzaktan gelen her girdi olayı (fare tıklaması, tuş, kaydırma) — özet
- bağlı kişinin yaptığı DOSYA DEĞİŞİKLİKLERİ (oluşturma/değiştirme/silme)

Günlük hem satır-satır JSON dosyasına (makine-okur, değiştirilmesi zor)
hem de isteğe bağlı bir GUI geri-çağırmasına (canlı görüntüleme) yazılır.
Her kayıt, önceki kaydın hash'ini içerir -> kurcalamaya karşı zincir.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import threading
from typing import Any, Callable, Dict, List, Optional


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


class AuditLog:
    def __init__(self, path: str, on_event: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.path = path
        self._on_event = on_event
        self._lock = threading.Lock()
        self._prev_hash = "0" * 64
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        # Varsa mevcut zincirin son hash'ini sürdür.
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    last = None
                    for line in f:
                        line = line.strip()
                        if line:
                            last = line
                    if last:
                        self._prev_hash = hashlib.sha256(last.encode("utf-8")).hexdigest()
            except OSError:
                pass

    def log(self, event: str, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            record = {
                "ts": _now_iso(),
                "event": event,
                "prev": self._prev_hash,
            }
            record.update(fields)
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._prev_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
        if self._on_event:
            try:
                self._on_event(record)
            except Exception:
                pass
        return record

    # Kolaylık yardımcıları ------------------------------------------------
    def session_start(self, name: str, ip: str) -> None:
        self.log("session_start", who=name, ip=ip)

    def session_end(self, name: str, ip: str, reason: str = "normal") -> None:
        self.log("session_end", who=name, ip=ip, reason=reason)

    def consent(self, name: str, ip: str, granted: bool) -> None:
        self.log("consent", who=name, ip=ip, granted=granted)

    def input_event(self, who: str, summary: str) -> None:
        self.log("input", who=who, detail=summary)

    def file_change(self, who: str, kind: str, path: str) -> None:
        self.log("file_change", who=who, kind=kind, path=path)


def verify_chain(path: str) -> bool:
    """Günlük zincirini doğrular; kurcalanmışsa False döner."""
    prev = "0" * 64
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                return False
            if rec.get("prev") != prev:
                return False
            prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
    return True


def read_all(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out
