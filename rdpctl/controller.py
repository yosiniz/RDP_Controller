"""Controller = kontrol EDEN taraf.

Giriş ekranında AD ve SOYAD girmek ZORUNLUDUR (host tarafında onay
penceresinde ve denetim günlüğünde bu isim görünür). Ardından host'un
oturum kodu ve adresi girilir. Bağlantı TLS ile şifrelenir.
"""
from __future__ import annotations

import argparse
import base64
import io
import queue
import socket
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from . import protocol as proto
from .auth import Identity


class ControllerApp:
    def __init__(self, args):
        self.args = args
        self.sock: Optional[socket.socket] = None
        self.identity: Optional[Identity] = None
        self._frame_q: "queue.Queue" = queue.Queue(maxsize=2)
        self._connected = threading.Event()
        self._remote_w = 0
        self._remote_h = 0
        self._photo = None  # referansı korumak için
        self._disp_w = 0
        self._disp_h = 0

        self.root = tk.Tk()
        self.root.title("rdpctl — Controller (Kontrol Eden)")
        self._build_login()

    # --- Giriş ekranı ------------------------------------------------------
    def _build_login(self) -> None:
        self._login = ttk.Frame(self.root, padding=20)
        self._login.pack(fill="both", expand=True)
        ttk.Label(self._login, text="Uzak Bağlantı Girişi",
                  font=("", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 12))

        self.vars = {
            "first": tk.StringVar(value=self.args.first_name or ""),
            "last": tk.StringVar(value=self.args.last_name or ""),
            "host": tk.StringVar(value=self.args.host or ""),
            "port": tk.StringVar(value=str(self.args.port)),
            "code": tk.StringVar(value=""),
        }
        rows = [
            ("Ad *", "first"),
            ("Soyad *", "last"),
            ("Host adresi", "host"),
            ("Port", "port"),
            ("Oturum kodu", "code"),
        ]
        for i, (label, key) in enumerate(rows, start=1):
            ttk.Label(self._login, text=label).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(self._login, textvariable=self.vars[key], width=34).grid(
                row=i, column=1, pady=3)

        self.login_status = ttk.Label(self._login, text="", foreground="#a00")
        self.login_status.grid(row=7, column=0, columnspan=2, pady=(6, 0))
        self.connect_btn = ttk.Button(self._login, text="Bağlan", command=self._do_connect)
        self.connect_btn.grid(row=8, column=0, columnspan=2, pady=12)

    def _do_connect(self) -> None:
        try:
            identity = Identity(self.vars["first"].get(), self.vars["last"].get())
            identity.validate()
        except ValueError as exc:
            self.login_status.configure(text=str(exc))
            return
        host = self.vars["host"].get().strip()
        if not proto.is_valid_host(host):
            self.login_status.configure(text="Geçerli bir host adresi girin.")
            return
        try:
            port = int(self.vars["port"].get())
            assert 1 <= port <= 65535
        except (ValueError, AssertionError):
            self.login_status.configure(text="Geçersiz port.")
            return
        self.identity = identity
        self.connect_btn.configure(state="disabled")
        self.login_status.configure(text="Bağlanılıyor…", foreground="#333")
        threading.Thread(target=self._connect_worker,
                         args=(host, port, self.vars["code"].get()), daemon=True).start()

    def _connect_worker(self, host: str, port: int, code: str) -> None:
        try:
            raw = socket.create_connection((host, port), timeout=15)
            ctx = proto.client_tls_context()
            conn = ctx.wrap_socket(raw, server_hostname="rdpctl-host")
            import ssl as _ssl
            der = conn.getpeercert(binary_form=True)
            self._server_fp = (
                proto.cert_fingerprint(_ssl.DER_cert_to_PEM_cert(der).encode())
                if der else ""
            )
        except Exception as exc:
            self._login_fail(f"Bağlantı kurulamadı: {exc}")
            return
        try:
            proto.send_msg(conn, {
                "type": proto.MSG_HELLO,
                "first_name": self.identity.first_name,
                "last_name": self.identity.last_name,
                "code": code,
            })
            reply = proto.recv_msg(conn)
            if reply.get("type") == proto.MSG_AUTH_FAIL:
                reason = {
                    "bad_code": "Oturum kodu hatalı.",
                    "bad_name": "Ad/soyad reddedildi.",
                    "too_many_attempts": "Çok fazla hatalı deneme. Daha sonra tekrar deneyin.",
                    "busy": "Host şu anda başka bir oturumla meşgul.",
                }.get(reply.get("reason"), "Kimlik doğrulama başarısız.")
                self._login_fail(reason)
                conn.close()
                return
            # Onay bekle
            self._login_status_async("Host onayı bekleniyor…")
            if reply.get("type") == proto.MSG_CONSENT_PENDING:
                reply = proto.recv_msg(conn)
            if reply.get("type") == proto.MSG_CONSENT_DENIED:
                self._login_fail("Host bağlantıyı reddetti.")
                conn.close()
                return
            if reply.get("type") != proto.MSG_CONSENT_GRANTED:
                self._login_fail("Beklenmeyen yanıt.")
                conn.close()
                return
            self._remote_w = reply.get("w", 0)
            self._remote_h = reply.get("h", 0)
            self.sock = conn
            self._connected.set()
            self.root.after(0, self._build_viewer)
            threading.Thread(target=self._recv_loop, daemon=True).start()
        except Exception as exc:
            self._login_fail(f"Hata: {exc}")
            try:
                conn.close()
            except OSError:
                pass

    def _login_fail(self, text: str) -> None:
        def go():
            self.login_status.configure(text=text, foreground="#a00")
            self.connect_btn.configure(state="normal")
        self.root.after(0, go)

    def _login_status_async(self, text: str) -> None:
        self.root.after(0, lambda: self.login_status.configure(text=text, foreground="#333"))

    # --- Görüntüleyici -----------------------------------------------------
    def _build_viewer(self) -> None:
        self._login.destroy()
        bar = ttk.Frame(self.root, padding=4)
        bar.pack(fill="x")
        ttk.Label(bar, text=f"Bağlı: {self.identity.full_name}  "
                            f"→  {self.vars['host'].get()}  "
                            f"({self._remote_w}×{self._remote_h})").pack(side="left")
        ttk.Button(bar, text="Bağlantıyı Kes", command=self._disconnect).pack(side="right")

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0,
                                width=1000, height=640)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.focus_set()

        self.canvas.bind("<Motion>", self._on_move)
        self.canvas.bind("<ButtonPress>", lambda e: self._on_click(e, True))
        self.canvas.bind("<ButtonRelease>", lambda e: self._on_click(e, False))
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._send_scroll(0, 1))
        self.canvas.bind("<Button-5>", lambda e: self._send_scroll(0, -1))
        self.canvas.bind("<KeyPress>", lambda e: self._on_key(e, True))
        self.canvas.bind("<KeyRelease>", lambda e: self._on_key(e, False))

        self.root.protocol("WM_DELETE_WINDOW", self._disconnect)
        self.root.after(30, self._render_loop)

    def _recv_loop(self) -> None:
        try:
            while self._connected.is_set():
                msg = proto.recv_msg(self.sock)
                t = msg.get("type")
                if t == proto.MSG_FRAME:
                    data = base64.b64decode(msg["jpeg"])
                    try:
                        self._frame_q.put_nowait((data, msg.get("w"), msg.get("h")))
                    except queue.Full:
                        try:
                            self._frame_q.get_nowait()
                            self._frame_q.put_nowait((data, msg.get("w"), msg.get("h")))
                        except queue.Empty:
                            pass
                elif t == proto.MSG_BYE:
                    self._remote_closed(msg.get("reason", "normal"))
                    return
        except (OSError, ConnectionError, ValueError):
            self._remote_closed("connection_lost")

    def _render_loop(self) -> None:
        if not self._connected.is_set():
            return
        try:
            from PIL import Image, ImageTk

            data, w, h = self._frame_q.get_nowait()
            img = Image.open(io.BytesIO(data))
            cw = max(1, self.canvas.winfo_width())
            ch = max(1, self.canvas.winfo_height())
            scale = min(cw / img.width, ch / img.height)
            dw, dh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
            if (dw, dh) != (img.width, img.height):
                img = img.resize((dw, dh))
            self._disp_w, self._disp_h = dw, dh
            self._frame_w, self._frame_h = w, h
            self._photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self._offx = (cw - dw) // 2
            self._offy = (ch - dh) // 2
            self.canvas.create_image(self._offx, self._offy, anchor="nw", image=self._photo)
        except queue.Empty:
            pass
        self.root.after(30, self._render_loop)

    # --- Girdi gönderimi (uzak ekran koordinatlarına ölçeklenir) ----------
    def _map(self, e) -> Optional[tuple]:
        if not self._disp_w or not getattr(self, "_frame_w", 0):
            return None
        x = e.x - getattr(self, "_offx", 0)
        y = e.y - getattr(self, "_offy", 0)
        if x < 0 or y < 0 or x > self._disp_w or y > self._disp_h:
            return None
        rx = x * self._frame_w / self._disp_w
        ry = y * self._frame_h / self._disp_h
        return rx, ry

    def _send(self, event: dict) -> None:
        if not self._connected.is_set() or self.sock is None:
            return
        event["fw"] = getattr(self, "_frame_w", self._remote_w)
        event["fh"] = getattr(self, "_frame_h", self._remote_h)
        try:
            proto.send_msg(self.sock, {"type": proto.MSG_INPUT, "event": event})
        except OSError:
            self._remote_closed("connection_lost")

    def _on_move(self, e):
        m = self._map(e)
        if m:
            self._send({"t": "move", "x": m[0], "y": m[1]})

    def _on_click(self, e, pressed):
        self.canvas.focus_set()
        m = self._map(e)
        if not m:
            return
        button = {1: "left", 2: "middle", 3: "right"}.get(e.num, "left")
        self._send({"t": "click", "x": m[0], "y": m[1], "button": button, "pressed": pressed})

    def _on_wheel(self, e):
        self._send_scroll(0, 1 if e.delta > 0 else -1)

    def _send_scroll(self, dx, dy):
        self._send({"t": "scroll", "dx": dx, "dy": dy})

    def _on_key(self, e, pressed):
        key = self._translate_key(e)
        if key is None:
            return
        self._send({"t": "keydown" if pressed else "keyup", "key": key})

    @staticmethod
    def _translate_key(e):
        special = {
            "Return": "enter", "BackSpace": "backspace", "Tab": "tab", "Escape": "esc",
            "space": "space", "Up": "up", "Down": "down", "Left": "left", "Right": "right",
            "Shift_L": "shift", "Shift_R": "shift_r", "Control_L": "ctrl", "Control_R": "ctrl_r",
            "Alt_L": "alt", "Alt_R": "alt_r", "Caps_Lock": "caps_lock", "Delete": "delete",
            "Home": "home", "End": "end", "Prior": "page_up", "Next": "page_down",
            "Super_L": "cmd", "Super_R": "cmd_r",
        }
        if e.keysym in special:
            return special[e.keysym]
        if len(e.char) == 1 and e.char.isprintable():
            return e.char
        if len(e.keysym) == 1:
            return e.keysym
        if e.keysym.startswith("F") and e.keysym[1:].isdigit():
            return e.keysym.lower()
        return None

    # --- Kapanış -----------------------------------------------------------
    def _disconnect(self) -> None:
        if self.sock is not None and self._connected.is_set():
            try:
                proto.send_msg(self.sock, {"type": proto.MSG_BYE, "reason": "controller_closed"})
            except OSError:
                pass
        self._connected.clear()
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.root.destroy()

    def _remote_closed(self, reason: str) -> None:
        self._connected.clear()
        def go():
            messagebox.showinfo("Bağlantı kapandı", f"Oturum sona erdi: {reason}")
            self.root.destroy()
        try:
            self.root.after(0, go)
        except RuntimeError:
            pass

    def run(self) -> None:
        self.root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="rdpctl controller — kontrol eden istemci")
    p.add_argument("--host", help="host adresi")
    p.add_argument("--port", type=int, default=7443)
    p.add_argument("--first-name", help="ad (giriş formunu ön-doldurur)")
    p.add_argument("--last-name", help="soyad")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    ControllerApp(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
