"""rdpctl relay (buluşma/aktarma) sunucusu — SADECE Python stdlib.

AnyDesk/TeamViewer tarzı çalışır: iki bilgisayarın da AYNI AĞDA olmasına
ya da PORT AÇMASINA gerek yoktur. Host ve controller, relay'e DIŞARI doğru
(giden) bağlanır; relay onları oturum koduyla eşleştirir ve aralarında ham
baytları iki yönlü aktarır.

GÜVENLİK (zero-trust): Relay yalnızca baytları pipe'lar. Host ile controller
kendi uçtan uca TLS el sıkışmalarını bu pipe üzerinden yürütür; relay
içeriği (ekran, girdi, kimlik) GÖREMEZ ve çözemez. Oturum kodu da relay'de
yalnızca eşleştirme anahtarıdır; TLS ve onay akışı relay'den bağımsızdır.

Kayıt el sıkışması (protocol çerçevelemesiyle, [4B uzunluk][JSON]):
  istemci -> relay : {"type":"register","role":"host"|"controller","code":"..."}
  relay -> istemci : {"type":"paired"}                       (eşleşince)
                     {"type":"error","reason":"not_found"}   (controller, host yok)
                     {"type":"error","reason":"code_in_use"} (host, kod dolu)
                     {"type":"error","reason":"timeout"}     (eşleşme beklerken)
Eşleşmeden sonra her iki yönde ham bayt aktarımı başlar.
"""
from __future__ import annotations

import argparse
import logging
import re
import selectors
import socket
import threading
import time
from typing import Dict, Optional

from . import protocol as proto

log = logging.getLogger("rdpctl.relay")

PAIR_TIMEOUT = 60.0        # host, eşleşme için en fazla bu kadar bekler (sn)
_MAX_CONN_PER_IP = 30      # IP başına eşzamanlı açık bağlantı sınırı
_PIPE_BUF = 65536


def _normalize_code(code: str) -> str:
    return re.sub(r"[^0-9]", "", code or "")


class _Waiting:
    """Eşleşme bekleyen bir host kaydı."""

    def __init__(self, sock: socket.socket, ip: str):
        self.sock = sock
        self.ip = ip
        self.ts = time.monotonic()


class RelayServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 7444):
        self.host = host
        self.port = port
        self._waiting: Dict[str, _Waiting] = {}   # kod -> bekleyen host
        self._lock = threading.Lock()
        self._conns_per_ip: Dict[str, int] = {}
        self._stopping = threading.Event()
        self._srv: Optional[socket.socket] = None

    # --- IP bağlantı sayacı ---
    def _ip_inc(self, ip: str) -> bool:
        with self._lock:
            n = self._conns_per_ip.get(ip, 0)
            if n >= _MAX_CONN_PER_IP:
                return False
            self._conns_per_ip[ip] = n + 1
            return True

    def _ip_dec(self, ip: str) -> None:
        with self._lock:
            n = self._conns_per_ip.get(ip, 0) - 1
            if n <= 0:
                self._conns_per_ip.pop(ip, None)
            else:
                self._conns_per_ip[ip] = n

    # --- Sunucu döngüsü ---
    def serve_forever(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(128)
        srv.settimeout(1.0)
        self._srv = srv
        log.info("relay dinliyor: %s:%d", self.host, self.port)
        threading.Thread(target=self._reaper, daemon=True).start()
        try:
            while not self._stopping.is_set():
                try:
                    client, addr = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(target=self._handle, args=(client, addr[0]),
                                 daemon=True).start()
        finally:
            try:
                srv.close()
            except OSError:
                pass

    def stop(self) -> None:
        self._stopping.set()
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass

    # --- Süresi geçen host kayıtlarını temizle ---
    def _reaper(self) -> None:
        while not self._stopping.is_set():
            time.sleep(2.0)
            now = time.monotonic()
            expired = []
            with self._lock:
                for code, w in list(self._waiting.items()):
                    if now - w.ts > PAIR_TIMEOUT:
                        expired.append((code, w))
                        self._waiting.pop(code, None)
            for code, w in expired:
                log.info("kod %s: eşleşme zaman aşımı, host düşürüldü", code)
                try:
                    proto.send_msg(w.sock, {"type": "error", "reason": "timeout"})
                except OSError:
                    pass
                self._safe_close(w.sock)
                self._ip_dec(w.ip)

    # --- Tek bir istemci ---
    def _handle(self, client: socket.socket, ip: str) -> None:
        if not self._ip_inc(ip):
            self._safe_close(client)
            return
        counted = True
        try:
            client.settimeout(30.0)
            try:
                msg = proto.recv_msg(client)
            except (OSError, ConnectionError, ValueError):
                return
            if msg.get("type") != "register":
                self._safe_close(client)
                return
            role = msg.get("role")
            code = _normalize_code(msg.get("code", ""))
            if role not in ("host", "controller") or not code:
                try:
                    proto.send_msg(client, {"type": "error", "reason": "bad_request"})
                except OSError:
                    pass
                self._safe_close(client)
                return

            if role == "host":
                self._register_host(client, ip, code)
                counted = False  # eşleşme/pipe sahipliği _pair'e geçti ya da reaper temizler
                return
            else:  # controller
                self._pair_controller(client, ip, code)
                counted = False
                return
        finally:
            if counted:
                self._ip_dec(ip)
                self._safe_close(client)

    def _register_host(self, sock: socket.socket, ip: str, code: str) -> None:
        with self._lock:
            if code in self._waiting:
                dup = True
            else:
                self._waiting[code] = _Waiting(sock, ip)
                dup = False
        if dup:
            log.info("kod %s: zaten kullanımda, yeni host reddedildi", code)
            try:
                proto.send_msg(sock, {"type": "error", "reason": "code_in_use"})
            except OSError:
                pass
            self._safe_close(sock)
            self._ip_dec(ip)
            return
        # Host artık havuzda bekliyor; eşleşme controller geldiğinde olur,
        # zaman aşımı olursa reaper temizler. (soket/ip sahipliği onlarda)
        log.info("kod %s: host bekliyor", code)

    def _pair_controller(self, csock: socket.socket, cip: str, code: str) -> None:
        with self._lock:
            w = self._waiting.pop(code, None)
        if w is None:
            log.info("kod %s: host yok, controller reddedildi", code)
            try:
                proto.send_msg(csock, {"type": "error", "reason": "not_found"})
            except OSError:
                pass
            self._safe_close(csock)
            self._ip_dec(cip)
            return

        # Her iki tarafa da "paired" gönder, sonra ham aktarım başlat.
        ok = True
        for s in (w.sock, csock):
            try:
                proto.send_msg(s, {"type": "paired"})
            except OSError:
                ok = False
        if not ok:
            self._safe_close(w.sock)
            self._safe_close(csock)
            self._ip_dec(w.ip)
            self._ip_dec(cip)
            return

        log.info("kod %s: eşleşti (host<->controller), aktarım başlıyor", code)
        try:
            self._pipe(w.sock, csock)
        finally:
            self._safe_close(w.sock)
            self._safe_close(csock)
            self._ip_dec(w.ip)
            self._ip_dec(cip)
            log.info("kod %s: oturum kapandı", code)

    # --- İki soket arasında çift yönlü ham bayt aktarımı ---
    def _pipe(self, a: socket.socket, b: socket.socket) -> None:
        for s in (a, b):
            s.settimeout(None)
            s.setblocking(False)
        sel = selectors.DefaultSelector()
        sel.register(a, selectors.EVENT_READ, b)
        sel.register(b, selectors.EVENT_READ, a)
        try:
            while not self._stopping.is_set():
                events = sel.select(timeout=1.0)
                if not events:
                    continue
                for key, _ in events:
                    src = key.fileobj
                    dst = key.data
                    try:
                        chunk = src.recv(_PIPE_BUF)
                    except (BlockingIOError, InterruptedError):
                        continue
                    except OSError:
                        return
                    if not chunk:
                        return
                    try:
                        dst.sendall(chunk)
                    except OSError:
                        return
        finally:
            sel.close()

    @staticmethod
    def _safe_close(sock: socket.socket) -> None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="rdpctl relay (buluşma/aktarma) sunucusu")
    p.add_argument("--host", default="0.0.0.0", help="dinlenecek arayüz (vars. 0.0.0.0)")
    p.add_argument("--port", type=int, default=7444, help="dinlenecek port (vars. 7444)")
    p.add_argument("--quiet", action="store_true", help="yalnızca uyarı/hata logla")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    server = RelayServer(args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
