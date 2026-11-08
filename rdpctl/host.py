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
import sys
import threading
import time
import tkinter as tk
from typing import Optional

from . import config
from . import protocol as proto
from . import ui
from .ui import THEME, f, mix
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
        # NOT: Ekran yakalayıcı (mss) BURADA değil, _send_frames thread'inin
        # İÇİNDE oluşturulur. macOS'ta mss bir thread'de oluşturulup başka bir
        # thread'de kullanılırsa native çökme (segfault) olur.
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
        # Ekran yakalayıcıyı BU thread içinde oluştur (macOS native çökmesini
        # önler). Başlatılamazsa (ör. ekran kaydı izni yok) çökmek yerine
        # oturumu düzgünce sonlandır.
        try:
            grab, _, _ = _screen_grabber()
        except Exception as exc:
            self.host.audit.log("frame_error", detail=f"ekran yakalama başlatılamadı: {exc}")
            self.stop(reason="capture_unavailable")
            return
        while self.active.is_set():
            start = time.monotonic()
            try:
                import base64

                data, w, h = grab(self.host.max_width, self.host.quality)
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
        self._relay_sock: Optional[socket.socket] = None
        self._stopping = threading.Event()

        # Relay (buluşma) modu: IP/port gerekmeden, sadece kodla bağlantı.
        relay_host = getattr(args, "relay_host", None)
        if relay_host is None:
            relay_host = config.DEFAULT_RELAY_HOST
        self.relay_host = relay_host
        self.relay_port = getattr(args, "relay_port", None) or config.DEFAULT_RELAY_PORT
        self.relay_mode = bool(relay_host) and not getattr(args, "no_relay", False)

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
        self.root.title("rdpctl — Bilgisayarımı Paylaş")
        ui.apply_base(self.root)
        W, H = 820, 680
        ui.center(self.root, W, H)
        self.root.minsize(720, 600)

        # Degrade başlık + durum rozeti
        head = tk.Canvas(self.root, height=86, highlightthickness=0, bd=0, bg=THEME.bg)
        head.pack(fill="x")

        def paint_head(e=None):
            w = head.winfo_width() or W
            ui.gradient(head, w, 86, THEME.header_a, THEME.header_b)
            head.delete("txt")
            head.create_text(28, 32, anchor="w", text="🛡  Bilgisayarımı Paylaş",
                             font=f(17, "bold"), fill="#FFFFFF", tags="txt")
            head.create_text(30, 60, anchor="w", font=f(10), tags="txt",
                             fill=mix("#FFFFFF", THEME.header_b, 0.2),
                             text="Bağlantı yalnızca sizin onayınızla başlar.")
            head.tag_raise("txt")
        head.bind("<Configure>", paint_head)

        body = tk.Frame(self.root, bg=THEME.bg)
        body.pack(fill="both", expand=True, padx=22, pady=18)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        # --- Kod kartı ---
        code_card = self._card(body)
        code_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Label(code_card, text="OTURUM KODUNUZ", bg=THEME.surface, fg=THEME.text_muted,
                 font=f(9, "bold")).pack(anchor="w")
        self._code_lbl = tk.Label(code_card, text="", bg=THEME.surface, fg="#7DD3FC",
                                  font=(("Consolas" if sys.platform.startswith("win") else "monospace"),
                                        32, "bold"))
        self._code_lbl.pack(anchor="w", pady=(4, 10))
        self._reveal_code()
        row = tk.Frame(code_card, bg=THEME.surface)
        row.pack(anchor="w")
        ui.RoundedButton(row, "Kodu Kopyala", self._copy_code, kind="primary", icon="📋",
                         width=160, height=40, bg=THEME.surface).pack(side="left")
        tk.Label(code_card, text="⚠  Bu kodu yalnızca güvendiğiniz kişiyle paylaşın.",
                 bg=THEME.surface, fg=THEME.warning, font=f(9)).pack(anchor="w", pady=(12, 0))

        # --- Bağlantı bilgileri kartı ---
        info = self._card(body)
        info.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        if self.relay_mode:
            tk.Label(info, text="NASIL BAĞLANILIR", bg=THEME.surface, fg=THEME.text_muted,
                     font=f(9, "bold")).pack(anchor="w")
            tk.Label(info, text="🌐 İnternet üzerinden hazır", bg=THEME.surface,
                     fg=THEME.success, font=f(13, "bold")).pack(anchor="w", pady=(4, 2))
            tk.Label(info, bg=THEME.surface, fg=THEME.text_muted, font=f(9),
                     justify="left", wraplength=240,
                     text="IP veya port GEREKMEZ. Karşı tarafa sadece\n"
                          "oturum kodunu verin; aynı ağda olmanıza\n"
                          "gerek yok.").pack(anchor="w", pady=(0, 12))
        else:
            tk.Label(info, text="BAĞLANTI ADRESİ", bg=THEME.surface, fg=THEME.text_muted,
                     font=f(9, "bold")).pack(anchor="w")
            for ip in _local_ips():
                tk.Label(info, text=f"{ip}", bg=THEME.surface, fg=THEME.text,
                         font=f(15, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(info, text=f"Port: {self.listen_port}", bg=THEME.surface,
                     fg=THEME.text_muted, font=f(10)).pack(anchor="w", pady=(2, 12))
        tk.Label(info, text="🔒 TLS parmak izi", bg=THEME.surface, fg=THEME.text_muted,
                 font=f(9, "bold")).pack(anchor="w")
        short_fp = " ".join(self.fingerprint.split(":")[:8]) + " …"
        tk.Label(info, text=short_fp, bg=THEME.surface, fg=THEME.text,
                 font=f(9)).pack(anchor="w")

        # --- Durum satırı ---
        status = self._card(body, pady=12)
        status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        self.status_var = tk.StringVar(value="")
        self._dot = ui.PulseDot(status, color=THEME.warning, size=18, bg=THEME.surface)
        self._dot.pack(side="left", padx=(0, 10))
        tk.Label(status, textvariable=self.status_var, bg=THEME.surface, fg=THEME.text,
                 font=f(11, "bold")).pack(side="left")
        self.disconnect_btn = ui.RoundedButton(status, "Bağlantıyı Kes", self._force_disconnect,
                                               kind="danger", icon="⏻", width=170, height=38,
                                               bg=THEME.surface)
        self.disconnect_btn.pack(side="right")
        self.disconnect_btn.set_enabled(False)
        self._set_status("Bağlantı bekleniyor…", "waiting")

        # --- Etkinlik günlüğü ---
        logc = self._card(body, pady=12)
        logc.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(18, 0))
        body.rowconfigure(2, weight=1)
        top = tk.Frame(logc, bg=THEME.surface)
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="📜  Canlı Etkinlik Günlüğü", bg=THEME.surface, fg=THEME.text,
                 font=f(11, "bold")).pack(side="left")
        tk.Label(top, text="kurcalamaya karşı korumalı", bg=THEME.surface,
                 fg=THEME.text_muted, font=f(9)).pack(side="right")
        wrap = tk.Frame(logc, bg=THEME.surface_2)
        wrap.pack(fill="both", expand=True)
        self.log_text = tk.Text(wrap, height=10, wrap="word", state="disabled",
                                bg=THEME.surface_2, fg=THEME.text, bd=0, padx=12, pady=10,
                                insertbackground=THEME.text, font=f(9),
                                highlightthickness=0, relief="flat")
        self.log_text.pack(fill="both", expand=True, side="left")
        sb = tk.Scrollbar(wrap, command=self.log_text.yview, bg=THEME.surface_2,
                          troughcolor=THEME.surface_2, bd=0, highlightthickness=0)
        sb.pack(fill="y", side="right")
        self.log_text.configure(yscrollcommand=sb.set)
        for tag, color in (("ok", THEME.success), ("bad", THEME.danger),
                           ("file", THEME.warning), ("input", THEME.text_muted),
                           ("time", mix(THEME.text_muted, THEME.surface_2, 0.3))):
            self.log_text.tag_configure(tag, foreground=color)

        self._banner: Optional[tk.Toplevel] = None
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._pump_gui_queue)
        ui.fade_in(self.root)

    @staticmethod
    def _card(parent, pady=18) -> tk.Frame:
        return tk.Frame(parent, bg=THEME.surface, padx=20, pady=pady,
                        highlightbackground=THEME.border, highlightthickness=1)

    def _reveal_code(self, i: int = 0) -> None:
        """Oturum kodunu karakter karakter beliren bir animasyonla gösterir."""
        import random
        code = self.session_code
        shown = "".join(
            ch if (k < i or ch == "-") else random.choice("0123456789")
            for k, ch in enumerate(code))
        self._code_lbl.configure(text=shown)
        if i <= len(code):
            self.root.after(45, lambda: self._reveal_code(i + 1))

    def _copy_code(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.session_code)
        ui.Toast.show(self.root, "✓ Oturum kodu kopyalandı")

    def _set_status(self, text: str, state: str) -> None:
        self.status_var.set(text)
        color = {"waiting": THEME.warning, "active": THEME.success,
                 "pending": THEME.primary}.get(state, THEME.text_muted)
        self._dot.set_color(color)

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
                    self._set_status(*payload)
                elif kind == "session_end":
                    self._clear_banner()
                    self.disconnect_btn.set_enabled(False)
                    self._set_status("Bağlantı bekleniyor…", "waiting")
        except queue.Empty:
            pass
        self.root.after(100, self._pump_gui_queue)

    _EVENT_TEXT = {
        "session_start": ("ok", "Oturum başladı"),
        "session_end": ("bad", "Oturum sona erdi"),
        "auth_fail": ("bad", "Hatalı giriş denemesi"),
        "file_change": ("file", "Dosya değişikliği"),
        "input": ("input", "Girdi"),
        "input_unavailable": ("bad", "Girdi denetimi kullanılamıyor"),
        "frame_error": ("bad", "Ekran yakalama hatası"),
    }
    _FILE_KIND = {"created": "oluşturuldu", "deleted": "silindi",
                  "modified": "değiştirildi", "moved": "taşındı"}

    def _append_log(self, record: dict) -> None:
        ev = record.get("event", "")
        tag, title = self._EVENT_TEXT.get(ev, ("input", ev))
        if ev == "consent":
            tag, title = ("ok", "Erişim onaylandı") if record.get("granted") else ("bad", "Erişim reddedildi")
        who = record.get("who", "")
        if ev == "file_change":
            detail = f"{self._FILE_KIND.get(record.get('kind'), record.get('kind'))}: {record.get('path')}"
        elif ev == "input":
            detail = record.get("detail", "")
        else:
            detail = " ".join(str(record[k]) for k in ("ip", "reason", "detail") if record.get(k))
        ts = (record.get("ts", "")[11:19])
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{ts}  ", "time")
        self.log_text.insert("end", f"● {title}", tag)
        if who:
            self.log_text.insert("end", f"  —  {who}")
        if detail:
            self.log_text.insert("end", f"\n          {detail}", "input")
        self.log_text.insert("end", "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _show_consent(self, ctx: dict) -> None:
        ident: Identity = ctx["identity"]
        ip: str = ctx["ip"]
        result_q: "queue.Queue" = ctx["result"]
        TIMEOUT = 60

        dlg = tk.Toplevel(self.root)
        dlg.title("Bağlantı İzni")
        dlg.configure(bg=THEME.surface)
        dlg.resizable(False, False)
        ui.center(dlg, 440, 400)
        dlg.attributes("-topmost", True)
        dlg.grab_set()
        try:
            dlg.bell()
        except tk.TclError:
            pass

        tk.Label(dlg, text="Uzaktan erişim isteği", bg=THEME.surface, fg=THEME.text_muted,
                 font=f(10, "bold")).pack(pady=(24, 10))
        # avatar (baş harfler)
        av = tk.Canvas(dlg, width=76, height=76, bg=THEME.surface, highlightthickness=0)
        av.pack()
        av.create_oval(2, 2, 74, 74, fill=THEME.primary, outline=mix(THEME.primary, "#FFFFFF", .4), width=2)
        initials = (ident.first_name[:1] + ident.last_name[:1]).upper()
        av.create_text(38, 38, text=initials, fill="#FFFFFF", font=f(22, "bold"))
        tk.Label(dlg, text=ident.full_name, bg=THEME.surface, fg=THEME.text,
                 font=f(16, "bold")).pack(pady=(10, 0))
        tk.Label(dlg, text=f"Kaynak adres: {ip}", bg=THEME.surface, fg=THEME.text_muted,
                 font=f(9)).pack()
        tk.Label(dlg, bg=THEME.surface, fg=THEME.text, font=f(10), justify="center",
                 text="bu bilgisayarın ekranını görmek ve\nfare/klavyesini kontrol etmek istiyor."
                 ).pack(pady=(12, 10))

        # geri sayım çubuğu
        bar = tk.Canvas(dlg, width=360, height=6, bg=THEME.surface_2, highlightthickness=0)
        bar.pack()
        left_lbl = tk.Label(dlg, text="", bg=THEME.surface, fg=THEME.text_muted, font=f(8))
        left_lbl.pack(pady=(4, 0))

        btns = tk.Frame(dlg, bg=THEME.surface)
        btns.pack(pady=16)
        state = {"done": False}

        def done(granted: bool):
            if state["done"]:
                return
            state["done"] = True
            result_q.put(granted)
            try:
                dlg.grab_release()
                dlg.destroy()
            except tk.TclError:
                pass

        ui.RoundedButton(btns, "Reddet", lambda: done(False), kind="ghost",
                         width=150, height=42, bg=THEME.surface).pack(side="left", padx=6)
        ui.RoundedButton(btns, "İzin Ver", lambda: done(True), kind="success", icon="✓",
                         width=150, height=42, bg=THEME.surface).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", lambda: done(False))

        import time as _t
        start = _t.monotonic()

        def tick():
            if state["done"]:
                return
            remaining = TIMEOUT - (_t.monotonic() - start)
            if remaining <= 0:
                done(False)
                return
            frac = remaining / TIMEOUT
            bar.delete("all")
            col = THEME.primary if frac > 0.3 else THEME.warning
            bar.create_rectangle(0, 0, 360 * frac, 6, fill=col, outline="")
            left_lbl.configure(text=f"Yanıt verilmezse {int(remaining) + 1} sn içinde reddedilecek")
            dlg.after(50, tick)

        tick()
        ui.fade_in(dlg)

    def _show_banner(self, name: str) -> None:
        self._clear_banner()
        b = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.attributes("-topmost", True)
        b.configure(bg=THEME.danger)
        sw = b.winfo_screenwidth()
        bw = min(680, sw - 40)
        b.geometry(f"{bw}x42+{(sw - bw) // 2}+8")
        inner = tk.Frame(b, bg=THEME.danger, padx=14)
        inner.pack(fill="both", expand=True)
        ui.PulseDot(inner, color="#FFFFFF", size=14, bg=THEME.danger).pack(side="left", padx=(0, 10))
        tk.Label(inner, text=f"Uzaktan kontrol aktif — {name}", bg=THEME.danger, fg="#FFFFFF",
                 font=f(10, "bold")).pack(side="left")
        ui.RoundedButton(inner, "Sonlandır", self._force_disconnect, kind="ghost",
                         width=110, height=30, radius=10, bg=THEME.danger,
                         font=f(9, "bold")).pack(side="right", pady=6)
        ui.fade_in(b)
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
        if self.relay_mode:
            threading.Thread(target=self._serve_relay, daemon=True).start()
        else:
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
            threading.Thread(target=self._handle_client, args=(ctx, client, addr[0]),
                             daemon=True).start()

    def _serve_relay(self) -> None:
        """Relay modu: host, buluşma sunucusuna DIŞARI bağlanır ve kodla
        eşleşmeyi bekler. Eşleşince gelen baytları TLS SUNUCU olarak sarıp
        normal oturum akışını işler. Oturum bitince yeniden kaydolur."""
        ctx = proto.server_tls_context(self.cert_path, self.key_path)
        backoff = 2
        while not self._stopping.is_set():
            self._gui_queue.put(("status",
                                 ("İnternet üzerinden bağlantı bekleniyor…", "waiting")))
            try:
                raw = proto.connect_via_relay(
                    self.relay_host, self.relay_port, "host",
                    self.session_code, timeout=20)
            except proto.RelayError as exc:
                if exc.reason == "timeout":
                    continue  # kimse gelmedi; hemen yeniden kaydol
                if exc.reason == "code_in_use":
                    self._gui_queue.put(("status",
                                         ("Bu kod başka bir oturumda kullanılıyor",
                                          "waiting")))
                    self.audit.log("relay_error", reason="code_in_use")
                # relay_unreachable / diğer: üstel geri çekilmeyle yeniden dene
                if self._stopping.wait(backoff):
                    break
                backoff = min(backoff * 2, 30)
                continue
            except Exception as exc:
                self.audit.log("relay_error", detail=str(exc))
                if self._stopping.wait(backoff):
                    break
                backoff = min(backoff * 2, 30)
                continue
            backoff = 2
            self._relay_sock = raw
            # Eşleşti: TLS sunucu el sıkışması + oturum akışı (ip gizli -> "internet")
            self._handle_client(ctx, raw, "internet")
            self._relay_sock = None

    def _handle_client(self, ctx, client, ip) -> None:
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
        self._gui_queue.put(("status", (f"Aktif — {identity.full_name} bağlı ({ip})", "active")))
        self.root.after(0, lambda: self.disconnect_btn.set_enabled(True))
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
        for sock in (self._server_sock, self._relay_sock):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        self.root.destroy()


def _local_ips():
    """Bu bilgisayarın yerel ağ IP adres(ler)i."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # paket gönderilmez; yalnızca rota seçilir
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips[:3] or ["127.0.0.1"]


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
    p.add_argument("--relay-host", default=None,
                   help="buluşma sunucusu adresi (boş = config/ortam değişkeni)")
    p.add_argument("--relay-port", type=int, default=None, help="buluşma sunucusu portu")
    p.add_argument("--no-relay", action="store_true",
                   help="relay yapılandırılmış olsa bile yerel port dinle")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    app = HostApp(args)
    app.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
