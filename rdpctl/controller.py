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
from tkinter import messagebox
from typing import Optional

from . import config
from . import protocol as proto
from . import ui
from .ui import THEME, f, mix
from .auth import Identity


class ControllerApp:
    def __init__(self, args):
        self.args = args
        relay_host = getattr(args, "relay_host", None)
        if relay_host is None:
            relay_host = config.DEFAULT_RELAY_HOST
        self.relay_host = relay_host
        self.relay_port = getattr(args, "relay_port", None) or config.DEFAULT_RELAY_PORT
        self.relay_mode = bool(relay_host) and not getattr(args, "no_relay", False)
        self._peer_label = ""
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
        self.root.title("rdpctl — Uzak Bilgisayara Bağlan")
        self._build_login()

    # --- Giriş ekranı ------------------------------------------------------
    def _build_login(self) -> None:
        ui.apply_base(self.root)
        ui.center(self.root, 920, 600)
        self.root.minsize(820, 560)
        self._login = tk.Frame(self.root, bg=THEME.bg)
        self._login.pack(fill="both", expand=True)

        # Sol: marka paneli (degrade)
        side = tk.Canvas(self._login, width=340, highlightthickness=0, bd=0, bg=THEME.bg)
        side.pack(side="left", fill="y")

        def paint_side(e=None):
            h = side.winfo_height() or 600
            ui.gradient(side, 340, h, THEME.header_a, THEME.header_b)
            side.delete("txt")
            side.create_text(36, 70, anchor="w", text="🛡", font=f(34), fill="#FFFFFF", tags="txt")
            side.create_text(36, 130, anchor="w", text="Güvenli bağlantı", font=f(20, "bold"),
                             fill="#FFFFFF", tags="txt")
            side.create_text(36, 162, anchor="w", font=f(10), tags="txt",
                             fill=mix("#FFFFFF", THEME.header_b, 0.2),
                             text="Karşı taraf onaylamadan hiçbir\nbağlantı başlamaz.")
            y = 240
            for icon, t1, t2 in (("🔒", "Uçtan uca TLS", "Tüm trafik şifrelenir"),
                                 ("✋", "Açık onay", "Ekran sahibi izin verir"),
                                 ("👤", "Kimlik zorunlu", "Ad-soyadınız görünür"),
                                 ("📜", "Tam kayıt", "Her işlem günlüğe yazılır")):
                side.create_oval(36, y - 18, 72, y + 18, tags="txt",
                                 fill=mix(THEME.header_a, "#FFFFFF", 0.15), outline="")
                side.create_text(54, y, text=icon, font=f(13), tags="txt", fill="#FFFFFF")
                side.create_text(88, y - 8, anchor="w", text=t1, font=f(11, "bold"),
                                 fill="#FFFFFF", tags="txt")
                side.create_text(88, y + 10, anchor="w", text=t2, font=f(9), tags="txt",
                                 fill=mix("#FFFFFF", THEME.header_b, 0.25))
                y += 62
        side.bind("<Configure>", paint_side)

        # Sağ: form kartı
        right = tk.Frame(self._login, bg=THEME.bg)
        right.pack(side="left", fill="both", expand=True)
        card = tk.Frame(right, bg=THEME.surface, padx=36, pady=30,
                        highlightbackground=THEME.border, highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.88)
        card.columnconfigure(0, weight=1, uniform="c")
        card.columnconfigure(1, weight=1, uniform="c")

        tk.Label(card, text="Uzak bilgisayara bağlan", bg=THEME.surface, fg=THEME.text,
                 font=f(17, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(card, text="Karşı taraftan aldığınız bilgileri girin.", bg=THEME.surface,
                 fg=THEME.text_muted, font=f(10)).grid(row=1, column=0, columnspan=2,
                                                      sticky="w", pady=(2, 18))

        self.vars = {
            "first": tk.StringVar(value=self.args.first_name or ""),
            "last": tk.StringVar(value=self.args.last_name or ""),
            "host": tk.StringVar(value=self.args.host or ""),
            "port": tk.StringVar(value=str(self.args.port)),
            "code": tk.StringVar(value=""),
        }
        first = self._field(card, "Ad", "first", 2, 0)
        self._field(card, "Soyad", "last", 2, 1)
        if self.relay_mode:
            # IP/port GEREKMEZ — sadece oturum kodu.
            code_e = self._field(card, "Oturum kodu", "code", 4, 0, colspan=2, big=True,
                                 placeholder="123-456-789")
        else:
            self._field(card, "Bilgisayar adresi (IP)", "host", 4, 0,
                        placeholder="192.168.1.50")
            self._field(card, "Port", "port", 4, 1, width=8)
            code_e = self._field(card, "Oturum kodu", "code", 6, 0, colspan=2, big=True,
                                 placeholder="123-456-789")
        code_e.bind("<Return>", lambda e: self._do_connect())

        self.connect_btn = ui.RoundedButton(card, "Güvenli Bağlan", self._do_connect,
                                            kind="primary", icon="🔒", width=360, height=46,
                                            bg=THEME.surface)
        self.connect_btn.grid(row=8, column=0, columnspan=2, pady=(22, 0))

        st = tk.Frame(card, bg=THEME.surface)
        st.grid(row=9, column=0, columnspan=2, pady=(14, 0))
        self._spinner = ui.Spinner(st, size=20, bg=THEME.surface, width=3)
        self._spinner.pack(side="left", padx=(0, 8))
        self.login_status = tk.Label(st, text="", bg=THEME.surface, fg=THEME.text_muted,
                                     font=f(10), wraplength=340, justify="left")
        self.login_status.pack(side="left")

        first.focus_set()
        ui.fade_in(self.root)

    def _field(self, parent, label, key, row, col, colspan=1, width=None, big=False,
               placeholder=""):
        tk.Label(parent, text=label, bg=THEME.surface, fg=THEME.text_muted,
                 font=f(9, "bold")).grid(row=row, column=col, columnspan=colspan,
                                         sticky="w", padx=(0 if col == 0 else 10, 0))
        holder = tk.Frame(parent, bg=THEME.border, padx=1, pady=1)
        holder.grid(row=row + 1, column=col, columnspan=colspan, sticky="ew",
                    padx=(0 if col == 0 else 10, 0), pady=(4, 12))
        e = tk.Entry(holder, textvariable=self.vars[key], bg=THEME.surface_2, fg=THEME.text,
                     insertbackground=THEME.text, relief="flat", bd=0, highlightthickness=0,
                     font=f(15 if big else 11, "bold" if big else "normal"),
                     width=width or 6)
        e.pack(fill="x", ipady=9 if big else 7, ipadx=10)
        # odakta kenarlık rengi yumuşakça maviye döner
        e.bind("<FocusIn>", lambda ev: self._glow(holder, THEME.primary))
        e.bind("<FocusOut>", lambda ev: self._glow(holder, THEME.border))
        if placeholder and not self.vars[key].get():
            self._placeholder(e, key, placeholder)
        return e

    def _placeholder(self, e, key, text):
        var = self.vars[key]
        state = {"on": True}

        def show():
            state["on"] = True
            e.configure(fg=THEME.text_muted)
            var.set(text)

        def hide(_=None):
            if state["on"]:
                state["on"] = False
                var.set("")
                e.configure(fg=THEME.text)

        def maybe_show(_=None):
            if not var.get():
                show()

        show()
        e.bind("<FocusIn>", hide, add="+")
        e.bind("<FocusOut>", maybe_show, add="+")
        self._placeholders = getattr(self, "_placeholders", {})
        self._placeholders[key] = state

    def _value(self, key) -> str:
        st = getattr(self, "_placeholders", {}).get(key)
        if st and st["on"]:
            return ""
        return self.vars[key].get()

    def _glow(self, widget, target, i=0):
        cur = widget.cget("bg")
        nxt = mix(cur, target, 0.4)
        widget.configure(bg=nxt)
        if i < 6:
            widget.after(16, lambda: self._glow(widget, target, i + 1))
        else:
            widget.configure(bg=target)

    def _do_connect(self) -> None:
        try:
            identity = Identity(self._value("first"), self._value("last"))
            identity.validate()
        except ValueError as exc:
            self._login_fail(str(exc))
            return
        if self.relay_mode:
            host, port = None, None
            self._peer_label = "İnternet (kod ile)"
        else:
            host = self._value("host").strip()
            if not proto.is_valid_host(host):
                self._login_fail("Geçerli bir bilgisayar adresi girin.")
                return
            try:
                port = int(self.vars["port"].get())
                assert 1 <= port <= 65535
            except (ValueError, AssertionError):
                self._login_fail("Geçersiz port.")
                return
            self._peer_label = host
        self.identity = identity
        self.connect_btn.configure(state="disabled")
        self.login_status.configure(text="Güvenli bağlantı kuruluyor…", fg=THEME.text_muted)
        self._spinner.start()
        threading.Thread(target=self._connect_worker,
                         args=(host, port, self._value("code")), daemon=True).start()

    def _connect_worker(self, host, port, code: str) -> None:
        try:
            if self.relay_mode:
                self._login_status_async("Buluşma sunucusuna bağlanılıyor…")
                raw = proto.connect_via_relay(
                    self.relay_host, self.relay_port, "controller", code, timeout=25)
            else:
                raw = socket.create_connection((host, port), timeout=15)
            ctx = proto.client_tls_context()
            conn = ctx.wrap_socket(raw, server_hostname="rdpctl-host")
            import ssl as _ssl
            der = conn.getpeercert(binary_form=True)
            self._server_fp = (
                proto.cert_fingerprint(_ssl.DER_cert_to_PEM_cert(der).encode())
                if der else ""
            )
        except proto.RelayError as exc:
            msg = {
                "not_found": "Karşı taraf henüz paylaşımı başlatmadı ya da kod yanlış.",
                "relay_unreachable": "Buluşma sunucusuna ulaşılamadı. İnternetinizi kontrol edin.",
                "timeout": "Eşleşme zaman aşımına uğradı. Tekrar deneyin.",
                "code_in_use": "Bu kod şu an kullanılıyor.",
            }.get(exc.reason, f"Bağlantı kurulamadı ({exc.reason}).")
            self._login_fail(msg)
            return
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
            self._login_status_async("Karşı tarafın onayı bekleniyor…")
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
            self._spinner.stop()
            self.login_status.configure(text="✕  " + text, fg=THEME.danger)
            self.connect_btn.configure(state="normal")
            self._shake(self.connect_btn)
        self.root.after(0, go)

    def _shake(self, widget, i=0):
        """Hata durumunda kısa yatay sallanma animasyonu."""
        offsets = [0, -8, 8, -6, 6, -3, 3, 0]
        if i < len(offsets):
            widget.grid_configure(padx=(max(0, 0 + offsets[i]), max(0, -offsets[i])))
            widget.after(30, lambda: self._shake(widget, i + 1))

    def _login_status_async(self, text: str) -> None:
        self.root.after(0, lambda: self.login_status.configure(text=text, fg=THEME.text_muted))

    # --- Görüntüleyici -----------------------------------------------------
    def _build_viewer(self) -> None:
        self._spinner.stop()
        self._login.destroy()
        peer = self._peer_label or "uzak bilgisayar"
        self.root.title(f"rdpctl — {peer} bağlı")
        try:
            self.root.geometry("1200x780")
        except tk.TclError:
            pass

        bar = tk.Frame(self.root, bg=THEME.surface, padx=16, pady=8,
                       highlightbackground=THEME.border, highlightthickness=1)
        bar.pack(fill="x")
        ui.PulseDot(bar, color=THEME.success, size=16, bg=THEME.surface).pack(side="left")
        tk.Label(bar, text=f"  Bağlı: {self._peer_label or 'uzak bilgisayar'}",
                 bg=THEME.surface, fg=THEME.text, font=f(11, "bold")).pack(side="left")
        tk.Label(bar, text=f"   {self._remote_w}×{self._remote_h}   •   {self.identity.full_name}",
                 bg=THEME.surface, fg=THEME.text_muted, font=f(9)).pack(side="left")
        chip = tk.Label(bar, text="🔒 Şifreli bağlantı", bg=THEME.success_soft, fg=THEME.success,
                        font=f(9, "bold"), padx=10, pady=3)
        chip.pack(side="left", padx=14)
        ui.RoundedButton(bar, "Bağlantıyı Kes", self._disconnect, kind="danger", icon="⏻",
                         width=160, height=36, bg=THEME.surface).pack(side="right")

        self.canvas = tk.Canvas(self.root, bg=THEME.bg, highlightthickness=0,
                                width=1000, height=640)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.focus_set()
        self.canvas.create_text(500, 320, text="Ekran görüntüsü bekleniyor…",
                                fill=THEME.text_muted, font=f(12), tags="wait")

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
        ui.Toast.show(self.root, "✓ Bağlantı onaylandı — şifreli oturum başladı")

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
            self.canvas.delete("all")  # bekleme yazısı dahil
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
    p.add_argument("--host", help="host adresi (relay kapalıysa)")
    p.add_argument("--port", type=int, default=7443)
    p.add_argument("--first-name", help="ad (giriş formunu ön-doldurur)")
    p.add_argument("--last-name", help="soyad")
    p.add_argument("--relay-host", default=None,
                   help="buluşma sunucusu adresi (boş = config/ortam değişkeni)")
    p.add_argument("--relay-port", type=int, default=None, help="buluşma sunucusu portu")
    p.add_argument("--no-relay", action="store_true",
                   help="relay yapılandırılmış olsa bile doğrudan IP ile bağlan")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    ControllerApp(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
