"""Host = kontrol EDİLEN bilgisayarda çalışan ajan.

Güvenlik/şeffaflık ilkeleri (bu uygulamayı meşru kılan şeyler):
  1. Oturum kodu olmadan kimse el sıkışamaz.
  2. Kod doğru olsa bile, host'un başındaki kişi ONAY penceresinde
     bağlanan kişinin AD-SOYAD'ını görüp "Kabul Et" demeden kontrol
     BAŞLAMAZ.
  3. Kontrol süresince ekranda kalıcı, kapatılamayan bir uyarı bandı durur.
  4. Her girdi ve dosya değişikliği denetim günlüğüne yazılır; host kişi
     istediği an "Bağlantıyı Kes" ile oturumu sonlandırabilir.
"""
from __future__ import annotations

import argparse
import io
import os
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

from . import protocol as proto
from .audit import AuditLog
from .auth import Identity, RateLimiter, code_matches, generate_session_code, valid_name
from .fswatch import FileChangeWatcher


# --- Ekran yakalama / girdi enjeksiyonu (tembel içe aktarma) ---------------
def _screen_grabber():
    import mss
    from PIL import Image

    sct = mss.mss()
    monitor = sct.monitors[0]  # tüm ekranlar birleşik

    def grab(max_width: int, quality: int):
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.rgb)
        w, h = img.size
        if w > max_width:
            img = img.resize((max_width, int(h * max_width / w)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue(), w, h

    return grab, monitor["width"], monitor["height"]


class _InputInjector:
    def __init__(self):
        from pynput.keyboard import Controller as KBD
        from pynput.mouse import Button, Controller as Mouse

        self._mouse = Mouse()
        self._kbd = KBD()
        self._Button = Button
        self._buttons = {"left": Button.left, "right": Button.right, "middle": Button.middle}

    def apply(self, ev: dict, scale_x: float, scale_y: float) -> str:
        from pynput.keyboard import Key, KeyCode

        t = ev.get("t")
        if t == "move":
            x, y = int(ev["x"] * scale_x), int(ev["y"] * scale_y)
            self._mouse.position = (x, y)
            return f"fare -> ({x},{y})"
        if t == "click":
            x, y = int(ev["x"] * scale_x), int(ev["y"] * scale_y)
            self._mouse.position = (x, y)
            btn = self._buttons.get(ev.get("button", "left"), self._Button.left)
            if ev.get("pressed"):
                self._mouse.press(btn)
                return f"tıklama-bas {ev.get('button')} ({x},{y})"
            self._mouse.release(btn)
            return f"tıklama-bırak {ev.get('button')} ({x},{y})"
        if t == "scroll":
            self._mouse.scroll(int(ev.get("dx", 0)), int(ev.get("dy", 0)))
            return f"kaydırma ({ev.get('dx')},{ev.get('dy')})"
        if t in ("keydown", "keyup"):
            key = ev.get("key", "")
            try:
                k = getattr(Key, key) if hasattr(Key, key) else KeyCode.from_char(key)
            except Exception:
                return f"tuş (geçersiz: {key!r})"
            if t == "keydown":
                self._kbd.press(k)
                return f"tuş-bas {key!r}"
            self._kbd.release(k)
            return f"tuş-bırak {key!r}"
        return f"bilinmeyen girdi: {t!r}"


class _Session:
    """Tek bir aktif kontrol oturumu."""

    def __init__(self, host: "HostApp", conn: socket.socket, identity: Identity, ip: str):
        self.host = host
        self.conn = conn
        self.identity = identity
        self.ip = ip
        self.active = threading.Event()
        self.active.set()
        self._fps = host.fps
        self._injector: Optional[_InputInjector] = None
        self._grab = None
        self._src_w = host._screen_w
        self._src_h = host._screen_h

    def stop(self, reason: str = "normal") -> None:
        if self.active.is_set():
            self.active.clear()
            try:
                proto.send_msg(self.conn, {"type": proto.MSG_BYE, "reason": reason})
            except OSError:
                pass
            try:
                self.conn.close()
            except OSError:
                pass
            self.host.audit.session_end(self.identity.full_name, self.ip, reason)
            self.host._on_session_ended(self)

    def run(self) -> None:
        self.host.audit.session_start(self.identity.full_name, self.ip)
        try:
            self._injector = _InputInjector()
        except Exception as exc:  # girdi enjeksiyonu yoksa yalnızca görüntüleme
            self.host.audit.log("input_unavailable", detail=str(exc))
        self._grab, _, _ = _screen_grabber()

        sender = threading.Thread(target=self._send_frames, daemon=True)
        sender.start()
        try:
            while self.active.is_set():
                msg = proto.recv_msg(self.conn)
                if msg.get("type") == proto.MSG_INPUT:
                    self._handle_input(msg.get("event", {}))
                elif msg.get("type") == proto.MSG_BYE:
                    break
        except (OSError, ConnectionError, ValueError):
            pass
        finally:
            self.stop()

    def _handle_input(self, ev: dict) -> None:
        if not self._injector:
            return
        frame_w = ev.get("fw") or self._src_w
        frame_h = ev.get("fh") or self._src_h
        sx = self._src_w / frame_w if frame_w else 1.0
        sy = self._src_h / frame_h if frame_h else 1.0
        try:
            summary = self._injector.apply(ev, sx, sy)
        except Exception as exc:
            summary = f"girdi hatası: {exc}"
        # Gürültüyü azaltmak için sürekli fare hareketlerini seyrek logla.
        if ev.get("t") == "move":
            now = time.monotonic()
            if now - getattr(self, "_last_move_log", 0) < 1.0:
                return
            self._last_move_log = now
        self.host.audit.input_event(self.identity.full_name, summary)

    def _send_frames(self) -> None:
        interval = 1.0 / max(1, self._fps)
        while self.active.is_set():
            start = time.monotonic()
            try:
                import base64

                data, w, h = self._grab(self.host.max_width, self.host.quality)
                proto.send_msg(
                    self.conn,
                    {
                        "type": proto.MSG_FRAME,
                        "w": w,
                        "h": h,
                        "jpeg": base64.b64encode(data).decode("ascii"),
                    },
                )
            except (OSError, ConnectionError, ValueError):
                break
            except Exception as exc:
                self.host.audit.log("frame_error", detail=str(exc))
                break
            elapsed = time.monotonic() - start
            time.sleep(max(0.0, interval - elapsed))


class HostApp:
    def __init__(self, args):
        self.listen_host = args.listen
        self.listen_port = args.port
        self.fps = args.fps
        self.max_width = args.max_width
        self.quality = args.quality
        self.watch_paths = args.watch or [os.path.expanduser("~")]

        self.session_code = generate_session_code()
        self.rate = RateLimiter()
        self._gui_queue: "queue.Queue" = queue.Queue()
        self._current: Optional[_Session] = None
        self._watcher: Optional[FileChangeWatcher] = None
        self._server_sock: Optional[socket.socket] = None
        self._stopping = threading.Event()

        # TLS sertifikası
        cfgdir = os.path.join(os.path.expanduser("~"), ".rdpctl")
        os.makedirs(cfgdir, exist_ok=True)
        self.cert_path = os.path.join(cfgdir, "host_cert.pem")
        self.key_path = os.path.join(cfgdir, "host_key.pem")
        self.fingerprint = proto.generate_self_signed_cert(self.cert_path, self.key_path)

        audit_path = args.audit or os.path.join(cfgdir, "audit.log")
        self.audit = AuditLog(audit_path, on_event=self._audit_to_gui)
        self.audit_path = audit_path

        # Ekran boyutu (ölçekleme için)
        try:
            _, self._screen_w, self._screen_h = _screen_grabber()
        except Exception:
            self._screen_w, self._screen_h = 1920, 1080

        self._build_gui()

    # --- GUI ---------------------------------------------------------------
    def _build_gui(self) -> None:
        self.root = tk.Tk()
        self.root.title("rdpctl — Host (Kontrol Edilen Makine)")
        self.root.geometry("760x560")

        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Oturum Kodu", font=("", 10)).grid(row=0, column=0, sticky="w")
        ttk.Label(top, text=self.session_code, font=("", 22, "bold"),
                  foreground="#0a60c0").grid(row=1, column=0, sticky="w")
        ttk.Label(top, text="Bu kodu yalnızca GÜVENDİĞİNİZ kişiyle paylaşın.",
                  foreground="#a00").grid(row=2, column=0, sticky="w", pady=(0, 8))

        info = ttk.LabelFrame(self.root, text="Bağlantı Bilgileri", padding=10)
        info.pack(fill="x", padx=12)
        ttk.Label(info, text=f"Dinlenen adres : {self.listen_host}:{self.listen_port}").pack(anchor="w")
        ttk.Label(info, text=f"Sertifika parmak izi (SHA-256):").pack(anchor="w")
        fp = ttk.Entry(info, width=90)
        fp.insert(0, self.fingerprint)
        fp.configure(state="readonly")
        fp.pack(anchor="w", pady=(0, 4))
        ttk.Label(info, text=f"Denetim günlüğü : {self.audit_path}").pack(anchor="w")

        self.status_var = tk.StringVar(value="Durum: bağlantı bekleniyor…")
        ttk.Label(self.root, textvariable=self.status_var, font=("", 11, "bold")).pack(
            anchor="w", padx=12, pady=(8, 2))

        self.disconnect_btn = ttk.Button(self.root, text="Bağlantıyı Kes",
                                         command=self._force_disconnect, state="disabled")
        self.disconnect_btn.pack(anchor="w", padx=12)

        logframe = ttk.LabelFrame(self.root, text="Canlı Denetim Günlüğü", padding=6)
        logframe.pack(fill="both", expand=True, padx=12, pady=10)
        self.log_text = tk.Text(logframe, height=12, wrap="none", state="disabled")
        self.log_text.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(logframe, command=self.log_text.yview)
        sb.pack(fill="y", side="right")
        self.log_text.configure(yscrollcommand=sb.set)

        self._banner: Optional[tk.Toplevel] = None
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._pump_gui_queue)

    def _audit_to_gui(self, record: dict) -> None:
        self._gui_queue.put(("log", record))

    def _pump_gui_queue(self) -> None:
        try:
            while True:
                kind, payload = self._gui_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "consent":
                    self._show_consent(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "session_end":
                    self._clear_banner()
                    self.disconnect_btn.configure(state="disabled")
                    self.status_var.set("Durum: bağlantı bekleniyor…")
        except queue.Empty:
            pass
        self.root.after(100, self._pump_gui_queue)

    def _append_log(self, record: dict) -> None:
        line = f"[{record.get('ts','')}] {record.get('event','')}: " + ", ".join(
            f"{k}={v}" for k, v in record.items() if k not in ("ts", "event", "prev"))
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _show_consent(self, ctx: dict) -> None:
        ident: Identity = ctx["identity"]
        ip: str = ctx["ip"]
        result_q: "queue.Queue" = ctx["result"]

        dlg = tk.Toplevel(self.root)
        dlg.title("Bağlantı İzni")
        dlg.grab_set()
        dlg.attributes("-topmost", True)
        ttk.Label(dlg, text="Uzaktan kontrol isteği", font=("", 14, "bold"),
                  padding=12).pack()
        ttk.Label(dlg, padding=(12, 0),
                  text=f"Kişi : {ident.full_name}\nKaynak IP : {ip}\n\n"
                       "Bu kişinin ekranınızı görmesine ve\n"
                       "fare/klavyenizi kontrol etmesine izin veriyor musunuz?").pack()
        btns = ttk.Frame(dlg, padding=12)
        btns.pack()

        def done(granted: bool):
            result_q.put(granted)
            dlg.destroy()

        ttk.Button(btns, text="Kabul Et", command=lambda: done(True)).pack(side="left", padx=6)
        ttk.Button(btns, text="Reddet", command=lambda: done(False)).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", lambda: done(False))
        # 60 sn içinde yanıt yoksa reddet.
        dlg.after(60000, lambda: (done(False) if dlg.winfo_exists() else None))

    def _show_banner(self, name: str) -> None:
        self._clear_banner()
        b = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.attributes("-topmost", True)
        try:
            b.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        sw = b.winfo_screenwidth()
        b.geometry(f"{sw}x34+0+0")
        lbl = tk.Label(b, bg="#b00020", fg="white", font=("", 11, "bold"),
                       text=f"● UZAKTAN KONTROL AKTİF — {name} bu bilgisayarı kontrol ediyor")
        lbl.pack(fill="both", expand=True)
        self._banner = b

    def _clear_banner(self) -> None:
        if self._banner is not None:
            try:
                self._banner.destroy()
            except tk.TclError:
                pass
            self._banner = None

    # --- Sunucu ------------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._serve, daemon=True).start()
        self.root.mainloop()

    def _serve(self) -> None:
        ctx = proto.server_tls_context(self.cert_path, self.key_path)
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        raw.bind((self.listen_host, self.listen_port))
        raw.listen(5)
        self._server_sock = raw
        while not self._stopping.is_set():
            try:
                client, addr = raw.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(ctx, client, addr),
                             daemon=True).start()

    def _handle_client(self, ctx, client, addr) -> None:
        ip = addr[0]
        try:
            conn = ctx.wrap_socket(client, server_side=True)
        except ssl_error():
            client.close()
            return
        try:
            if self.rate.is_locked(ip):
                proto.send_msg(conn, {"type": proto.MSG_AUTH_FAIL, "reason": "too_many_attempts"})
                conn.close()
                return
            msg = proto.recv_msg(conn)
            if msg.get("type") != proto.MSG_HELLO:
                conn.close()
                return
            first = (msg.get("first_name") or "").strip()
            last = (msg.get("last_name") or "").strip()
            code = msg.get("code") or ""
            if not (valid_name(first) and valid_name(last)):
                proto.send_msg(conn, {"type": proto.MSG_AUTH_FAIL, "reason": "bad_name"})
                conn.close()
                return
            if not code_matches(self.session_code, code):
                self.rate.record_failure(ip)
                self.audit.log("auth_fail", who=f"{first} {last}", ip=ip, reason="bad_code")
                proto.send_msg(conn, {"type": proto.MSG_AUTH_FAIL, "reason": "bad_code"})
                conn.close()
                return
            self.rate.record_success(ip)
            identity = Identity(first, last)

            if self._current is not None and self._current.active.is_set():
                proto.send_msg(conn, {"type": proto.MSG_AUTH_FAIL, "reason": "busy"})
                conn.close()
                return

            # Onay iste (GUI thread'inde)
            proto.send_msg(conn, {"type": proto.MSG_CONSENT_PENDING})
            result_q: "queue.Queue" = queue.Queue()
            self._gui_queue.put(("consent", {"identity": identity, "ip": ip, "result": result_q}))
            try:
                granted = result_q.get(timeout=75)
            except queue.Empty:
                granted = False
            self.audit.consent(identity.full_name, ip, granted)
            if not granted:
                proto.send_msg(conn, {"type": proto.MSG_CONSENT_DENIED})
                conn.close()
                return

            proto.send_msg(conn, {"type": proto.MSG_CONSENT_GRANTED,
                                   "w": self._screen_w, "h": self._screen_h})
            self._begin_session(conn, identity, ip)
        except (OSError, ConnectionError, ValueError):
            try:
                conn.close()
            except OSError:
                pass

    def _begin_session(self, conn, identity: Identity, ip: str) -> None:
        session = _Session(self, conn, identity, ip)
        self._current = session
        # Dosya izleyiciyi başlat
        self._watcher = FileChangeWatcher(
            self.watch_paths,
            sink=lambda kind, path: self.audit.file_change(identity.full_name, kind, path),
        )
        self._watcher.start()
        self._gui_queue.put(("status", f"Durum: AKTİF — {identity.full_name} ({ip})"))
        self.root.after(0, lambda: self.disconnect_btn.configure(state="normal"))
        self.root.after(0, lambda: self._show_banner(identity.full_name))
        session.run()

    def _on_session_ended(self, session: "_Session") -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        if self._current is session:
            self._current = None
        self._gui_queue.put(("session_end", None))

    def _force_disconnect(self) -> None:
        if self._current is not None:
            self._current.stop(reason="host_disconnected")

    def _on_close(self) -> None:
        self._stopping.set()
        if self._current is not None:
            self._current.stop(reason="host_shutdown")
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
        self.root.destroy()


def ssl_error():
    import ssl
    return ssl.SSLError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="rdpctl host — kontrol edilen makine ajanı")
    p.add_argument("--listen", default="0.0.0.0", help="dinlenecek arayüz (vars. 0.0.0.0)")
    p.add_argument("--port", type=int, default=7443)
    p.add_argument("--fps", type=int, default=8, help="ekran kare hızı")
    p.add_argument("--max-width", type=int, default=1280, help="gönderilen kare genişliği üst sınırı")
    p.add_argument("--quality", type=int, default=60, help="JPEG kalitesi 1-95")
    p.add_argument("--watch", action="append", help="izlenecek klasör (çoklu verilebilir)")
    p.add_argument("--audit", help="denetim günlüğü yolu")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    app = HostApp(args)
    app.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
