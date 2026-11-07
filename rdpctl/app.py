"""Birleşik masaüstü başlatıcı.

Aynı uygulama her iki bilgisayara da kurulur. Açılışta kullanıcı rolünü
seçer:

  • "Bu bilgisayarı paylaş (Host)"  -> kontrol EDİLEN makine
  • "Başka bilgisayara bağlan"      -> kontrol EDEN makine (Controller)
"""
from __future__ import annotations

import sys
import tkinter as tk
from types import SimpleNamespace

from . import ui
from .ui import THEME, f, mix

_HOST_DEFAULTS = dict(
    listen="0.0.0.0", port=7443, fps=8, max_width=1280, quality=60,
    watch=None, audit=None,
)
_CTRL_DEFAULTS = dict(host=None, port=7443, first_name=None, last_name=None)


class RoleCard(tk.Canvas):
    """Hover'da kenarlığı parlayan, hafifçe yükselen tıklanabilir kart."""

    W, H, R = 262, 200, 18

    def __init__(self, parent, icon, title, subtitle, accent, command):
        super().__init__(parent, width=self.W, height=self.H + 6, bg=THEME.bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._icon, self._title, self._sub = icon, title, subtitle
        self._accent = accent
        self._cmd = command
        self._t = 0.0          # hover ilerlemesi 0..1
        self._target = 0.0
        self._anim = None
        self.bind("<Enter>", lambda e: self._go(1.0))
        self.bind("<Leave>", lambda e: self._go(0.0))
        self.bind("<ButtonRelease-1>", self._click)
        self._draw()

    def _go(self, target):
        self._target = target
        if self._anim is None:
            self._step()

    def _step(self):
        self._t += (self._target - self._t) * 0.25
        self._draw()
        if abs(self._target - self._t) > 0.01:
            self._anim = self.after(16, self._step)
        else:
            self._t = self._target
            self._draw()
            self._anim = None

    def _rr(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self):
        self.delete("all")
        lift = 6 * (1 - self._t)       # hover'da yukarı kalkar
        y0 = lift
        y1 = y0 + self.H - 2
        border = mix(THEME.border, self._accent, self._t)
        fill = mix(THEME.surface, mix(THEME.surface, self._accent, 0.12), self._t)
        # gölge
        self._rr(4, y0 + 6, self.W - 2, y1 + 4, self.R,
                 fill=mix(THEME.bg, "#000000", 0.35 + 0.2 * self._t), outline="")
        self._rr(2, y0 + 1, self.W - 3, y1, self.R, fill=fill, outline=border, width=2)
        # ikon dairesi
        cx, cy = self.W / 2, y0 + 56
        r = 30
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         fill=mix(THEME.surface, self._accent, 0.22 + 0.15 * self._t), outline="")
        self.create_text(cx, cy, text=self._icon, font=f(24), fill=THEME.text)
        self.create_text(cx, y0 + 110, text=self._title, font=f(12, "bold"), fill=THEME.text)
        self.create_text(cx, y0 + 134, text=self._sub, font=f(9), fill=THEME.text_muted,
                         justify="center", width=self.W - 40, anchor="n")

    def _click(self, e):
        if 0 <= e.x <= self.W and 0 <= e.y <= self.H + 6 and self._cmd:
            self._cmd()


def _choose_role() -> str | None:
    choice: dict = {"role": None}
    root = tk.Tk()
    root.title("rdpctl — Güvenli Uzaktan Destek")
    ui.apply_base(root)
    W, H = 620, 580
    ui.center(root, W, H)
    root.resizable(False, False)

    # --- Degrade başlık ---
    header = tk.Canvas(root, width=W, height=170, highlightthickness=0, bd=0, bg=THEME.bg)
    header.pack(fill="x")
    ui.gradient(header, W, 170, THEME.header_a, THEME.header_b)
    # kalkan logosu
    cx = W / 2
    header.create_oval(cx - 30, 26, cx + 30, 86, fill=mix(THEME.header_a, "#FFFFFF", 0.15),
                       outline=mix(THEME.header_b, "#FFFFFF", 0.4), width=2)
    header.create_text(cx, 56, text="🛡", font=f(26), fill="#FFFFFF")
    header.create_text(cx, 112, text="rdpctl", font=f(24, "bold"), fill="#FFFFFF")
    header.create_text(cx, 142, text="Güvenli • Şeffaf • Onay tabanlı uzaktan destek",
                       font=f(10), fill=mix("#FFFFFF", THEME.header_b, 0.15))

    tk.Label(root, text="Ne yapmak istiyorsunuz?", bg=THEME.bg, fg=THEME.text,
             font=f(13, "bold")).pack(pady=(22, 14))

    cards = tk.Frame(root, bg=THEME.bg)
    cards.pack()

    def pick(role):
        choice["role"] = role
        # kısa kapanış solması
        def out(i=10):
            try:
                root.attributes("-alpha", i / 10)
            except tk.TclError:
                root.destroy(); return
            if i > 0:
                root.after(14, lambda: out(i - 1))
            else:
                root.destroy()
        out()

    RoleCard(cards, "🖥", "Bilgisayarımı Paylaş",
             "Destek alacağım. Karşı taraf, benim onayımla ekranımı kontrol edebilir.",
             THEME.success, lambda: pick("host")).pack(side="left", padx=10)
    RoleCard(cards, "🔌", "Uzak Bilgisayara Bağlan",
             "Destek vereceğim. Oturum kodu ile başka bir bilgisayara bağlanırım.",
             THEME.primary, lambda: pick("controller")).pack(side="left", padx=10)

    # --- Güven rozetleri ---
    badges = tk.Frame(root, bg=THEME.bg)
    badges.pack(side="bottom", pady=(0, 22))
    for icon, text in (("🔒", "TLS ile şifreli"), ("✋", "Onaysız bağlanılamaz"),
                       ("📜", "Her işlem kayıt altında")):
        b = tk.Frame(badges, bg=THEME.surface, padx=10, pady=6,
                     highlightbackground=THEME.border, highlightthickness=1)
        b.pack(side="left", padx=5)
        tk.Label(b, text=f"{icon}  {text}", bg=THEME.surface, fg=THEME.text_muted,
                 font=f(9)).pack()

    ui.fade_in(root)
    root.mainloop()
    return choice["role"]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("host", "controller"):
        role, rest = argv[0], argv[1:]
    else:
        role, rest = _choose_role(), []

    if role == "host":
        from .host import HostApp, build_parser
        args = build_parser().parse_args(rest) if rest else SimpleNamespace(**_HOST_DEFAULTS)
        HostApp(args).start()
    elif role == "controller":
        from .controller import ControllerApp, build_parser
        args = build_parser().parse_args(rest) if rest else SimpleNamespace(**_CTRL_DEFAULTS)
        ControllerApp(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
