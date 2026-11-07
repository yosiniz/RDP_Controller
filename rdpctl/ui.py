"""rdpctl tasarım sistemi.

Tkinter üzerinde modern, güven veren bir görünüm için küçük bir bileşen
kütüphanesi: tema renkleri, degrade başlık, yuvarlatılmış animasyonlu
butonlar, nabız atan durum göstergesi, dönen spinner ve yumuşak açılış.

Saf Tkinter (ek bağımlılık yok) — her platformda çalışır. Alfa (saydamlık)
animasyonları Linux'ta pencere yöneticisine bağlı olarak atlanabilir; kod
bu durumda sessizce zarif biçimde devam eder.
"""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass


# --- Tema ------------------------------------------------------------------
@dataclass(frozen=True)
class Theme:
    bg: str = "#0B1220"          # koyu lacivert zemin (premium his)
    surface: str = "#131C2E"     # kart yüzeyi
    surface_2: str = "#1B2740"   # ikincil yüzey / girdi
    border: str = "#263249"
    primary: str = "#3B82F6"     # güven mavisi
    primary_hover: str = "#60A5FA"
    primary_press: str = "#2563EB"
    success: str = "#22C55E"     # güvenli / aktif
    success_soft: str = "#16311F"
    danger: str = "#EF4444"
    danger_hover: str = "#F87171"
    warning: str = "#F59E0B"
    text: str = "#E6EDF7"
    text_muted: str = "#8A9ABA"
    on_primary: str = "#FFFFFF"
    header_a: str = "#1E3A8A"    # degrade başlık üst
    header_b: str = "#0EA5A3"    # degrade başlık alt (teal)


THEME = Theme()


def font_family() -> str:
    if sys.platform.startswith("win"):
        return "Segoe UI"
    if sys.platform == "darwin":
        return "SF Pro Text"
    return "DejaVu Sans"


def f(size: int, weight: str = "normal") -> tuple:
    return (font_family(), size, weight)


# --- Renk yardımcıları -----------------------------------------------------
def _hex2rgb(c: str):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _rgb2hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def mix(c1: str, c2: str, t: float) -> str:
    """c1 ve c2 arasında t oranında (0..1) karışım."""
    a, b = _hex2rgb(c1), _hex2rgb(c2)
    return _rgb2hex([a[i] + (b[i] - a[i]) * t for i in range(3)])


# --- Temel stil ------------------------------------------------------------
def apply_base(root: tk.Misc) -> None:
    """Kök pencereye tema zeminini uygular ve ttk stillerini ayarlar."""
    from tkinter import ttk

    try:
        root.configure(bg=THEME.bg)
    except tk.TclError:
        pass
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=THEME.bg, foreground=THEME.text,
                    fieldbackground=THEME.surface_2, bordercolor=THEME.border,
                    font=f(10))
    style.configure("TFrame", background=THEME.bg)
    style.configure("Card.TFrame", background=THEME.surface)
    style.configure("TLabel", background=THEME.bg, foreground=THEME.text)
    style.configure("Card.TLabel", background=THEME.surface, foreground=THEME.text)
    style.configure("Muted.TLabel", background=THEME.bg, foreground=THEME.text_muted)
    style.configure("CardMuted.TLabel", background=THEME.surface, foreground=THEME.text_muted)
    style.configure("H1.TLabel", background=THEME.bg, foreground=THEME.text, font=f(24, "bold"))
    style.configure("H2.TLabel", background=THEME.surface, foreground=THEME.text, font=f(14, "bold"))
    style.configure("Code.TLabel", background=THEME.surface, foreground="#7DD3FC",
                    font=(("Consolas" if sys.platform.startswith("win") else "monospace"), 30, "bold"))
    # Girdi alanları
    style.configure("TEntry", fieldbackground=THEME.surface_2, foreground=THEME.text,
                    bordercolor=THEME.border, insertcolor=THEME.text, padding=6)
    style.map("TEntry", bordercolor=[("focus", THEME.primary)])
    style.configure("Vertical.TScrollbar", background=THEME.surface_2,
                    troughcolor=THEME.bg, bordercolor=THEME.bg, arrowcolor=THEME.text_muted)


# --- Degrade başlık --------------------------------------------------------
def gradient(canvas: tk.Canvas, w: int, h: int, c1: str, c2: str, tag: str = "grad") -> None:
    """Canvas üzerine dikey degrade çizer."""
    canvas.delete(tag)
    steps = max(1, h)
    for i in range(steps):
        canvas.create_line(0, i, w, i, fill=mix(c1, c2, i / steps), tags=tag)


# --- Yuvarlatılmış animasyonlu buton --------------------------------------
class RoundedButton(tk.Canvas):
    """Canvas tabanlı, hover/press animasyonlu yuvarlatılmış buton."""

    def __init__(self, parent, text="", command=None, kind="primary",
                 width=200, height=44, radius=12, icon="", bg=None, font=None):
        base_bg = bg if bg is not None else _parent_bg(parent)
        super().__init__(parent, width=width, height=height, bg=base_bg,
                         highlightthickness=0, bd=0)
        self._text = text
        self._icon = icon
        self._command = command
        self._kind = kind
        self._bw, self._bh, self._r = width, height, radius
        self._font = font or f(11, "bold")
        self._enabled = True
        self._fill = self._base_fill()
        self._target = self._fill
        self._anim = None
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    # renk setleri
    def _palette(self):
        return {
            "primary": (THEME.primary, THEME.primary_hover, THEME.primary_press, THEME.on_primary),
            "success": (THEME.success, mix(THEME.success, "#FFFFFF", .2),
                        mix(THEME.success, "#000000", .15), "#06230F"),
            "danger": (THEME.danger, THEME.danger_hover, mix(THEME.danger, "#000000", .15), "#FFFFFF"),
            "ghost": (THEME.surface_2, mix(THEME.surface_2, "#FFFFFF", .08),
                      mix(THEME.surface_2, "#000000", .1), THEME.text),
        }[self._kind]

    def _base_fill(self):
        return self._palette()[0]

    def _fg(self):
        return self._palette()[3]

    def _round_points(self):
        w, h, r = self._bw - 2, self._bh - 2, self._r
        x0, y0, x1, y1 = 1, 1, w, h
        return [
            x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
            x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
        ]

    def _draw(self):
        self.delete("all")
        fill = self._fill if self._enabled else mix(self._base_fill(), THEME.bg, .55)
        self.create_polygon(self._round_points(), smooth=True, fill=fill, outline=fill)
        label = (self._icon + "  " if self._icon else "") + self._text
        fg = self._fg() if self._enabled else THEME.text_muted
        self.create_text(self._bw / 2, self._bh / 2, text=label, fill=fg,
                         font=self._font, justify="center")

    # yumuşak renk animasyonu
    def _animate_to(self, target):
        self._target = target
        if self._anim is None:
            self._step()

    def _step(self):
        cur = _hex2rgb(self._fill)
        tgt = _hex2rgb(self._target)
        nxt = [cur[i] + (tgt[i] - cur[i]) * 0.35 for i in range(3)]
        self._fill = _rgb2hex(nxt)
        self._draw()
        if sum(abs(nxt[i] - tgt[i]) for i in range(3)) > 3:
            self._anim = self.after(16, self._step)
        else:
            self._fill = self._target
            self._draw()
            self._anim = None

    def _on_enter(self, _):
        if self._enabled:
            self.configure(cursor="hand2")
            self._animate_to(self._palette()[1])

    def _on_leave(self, _):
        if self._enabled:
            self._animate_to(self._base_fill())

    def _on_press(self, _):
        if self._enabled:
            self._animate_to(self._palette()[2])

    def _on_release(self, e):
        if not self._enabled:
            return
        self._animate_to(self._palette()[1])
        if 0 <= e.x <= self._bw and 0 <= e.y <= self._bh and self._command:
            self._command()

    # ttk benzeri arayüz
    def configure(self, **kw):  # type: ignore[override]
        if "state" in kw:
            self.set_enabled(kw.pop("state") != "disabled")
        if "text" in kw:
            self._text = kw.pop("text")
            self._draw()
        if kw:
            super().configure(**kw)
    config = configure

    def set_enabled(self, value: bool):
        self._enabled = value
        self.configure(cursor="hand2" if value else "arrow")
        self._fill = self._base_fill()
        self._draw()


def _parent_bg(parent) -> str:
    try:
        return parent.cget("background")
    except tk.TclError:
        return THEME.bg


# --- Nabız atan durum göstergesi ------------------------------------------
class PulseDot(tk.Canvas):
    """Yumuşak nabız animasyonlu durum noktası (ör. 'AKTİF')."""

    def __init__(self, parent, color=THEME.success, size=16, bg=None, running=True):
        bg = bg if bg is not None else _parent_bg(parent)
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self._c = color
        self._s = size
        self._t = 0.0
        self._bg = bg
        self._running = running
        self._tick()

    def set_color(self, color):
        self._c = color

    def set_running(self, running: bool):
        self._running = running
        self._draw(1.0 if not running else None)

    def _tick(self):
        import math
        if self._running:
            self._t += 0.08
            scale = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(self._t))
            self._draw(scale)
        self.after(40, self._tick)

    def _draw(self, scale):
        self.delete("all")
        c, s = self._s / 2, self._s / 2
        if scale is None:
            scale = 1.0
        # dış hale
        r_out = s * scale
        self.create_oval(c - r_out, c - r_out, c + r_out, c + r_out,
                         fill=mix(self._bg, self._c, 0.35), outline="")
        # çekirdek
        r_in = s * 0.45
        self.create_oval(c - r_in, c - r_in, c + r_in, c + r_in, fill=self._c, outline="")


# --- Dönen spinner ---------------------------------------------------------
class Spinner(tk.Canvas):
    """Bağlanırken gösterilen dönen yay."""

    def __init__(self, parent, size=28, color=THEME.primary, bg=None, width=4):
        bg = bg if bg is not None else _parent_bg(parent)
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self._s = size
        self._c = color
        self._lw = width
        self._bg = bg
        self._angle = 0
        self._on = False

    def start(self):
        if not self._on:
            self._on = True
            self._spin()

    def stop(self):
        self._on = False
        self.delete("all")

    def _spin(self):
        if not self._on:
            return
        self.delete("all")
        pad = self._lw
        box = (pad, pad, self._s - pad, self._s - pad)
        self.create_oval(*box, outline=mix(self._bg, self._c, 0.25), width=self._lw)
        self.create_arc(*box, start=self._angle, extent=100, style="arc",
                        outline=self._c, width=self._lw)
        self._angle = (self._angle - 12) % 360
        self.after(28, self._spin)


# --- Yardımcılar -----------------------------------------------------------
def fade_in(win: tk.Misc, duration_ms: int = 220) -> None:
    """Pencereyi 0->1 saydamlıkta yumuşak açar (desteklenmiyorsa atlar)."""
    try:
        win.attributes("-alpha", 0.0)
    except tk.TclError:
        return
    steps = max(1, duration_ms // 16)

    def step(i=0):
        try:
            win.attributes("-alpha", min(1.0, i / steps))
        except tk.TclError:
            return
        if i < steps:
            win.after(16, lambda: step(i + 1))

    step()


def center(win: tk.Misc, w: int, h: int) -> None:
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")


class Toast:
    """Kısa süreli, köşede beliren bildirim (ör. 'Kod kopyalandı')."""

    @staticmethod
    def show(root: tk.Misc, text: str, ms: int = 1600, kind="success"):
        color = {"success": THEME.success, "danger": THEME.danger,
                 "info": THEME.primary}.get(kind, THEME.primary)
        t = tk.Toplevel(root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        try:
            t.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        frame = tk.Frame(t, bg=color, padx=16, pady=10)
        frame.pack()
        tk.Label(frame, text=text, bg=color, fg="#06230F" if kind == "success" else "#FFFFFF",
                 font=f(10, "bold")).pack()
        root.update_idletasks()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw = root.winfo_width()
        t.update_idletasks()
        tw = t.winfo_width()
        t.geometry(f"+{rx + rw - tw - 24}+{ry + 24}")

        def fade(i=0, closing=False):
            try:
                if not closing:
                    t.attributes("-alpha", min(0.96, i / 10))
                    if i < 10:
                        t.after(16, lambda: fade(i + 1))
                    else:
                        t.after(ms, lambda: fade(10, True))
                else:
                    t.attributes("-alpha", max(0.0, i / 10))
                    if i > 0:
                        t.after(16, lambda: fade(i - 1, True))
                    else:
                        t.destroy()
            except tk.TclError:
                try:
                    t.destroy()
                except tk.TclError:
                    pass
        fade()
