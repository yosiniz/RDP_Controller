"""rdpctl kaldırıcı arayüzü (uygulamanın tasarım sistemiyle)."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox

from . import ui
from . import uninstall as un
from .ui import THEME, f, mix

_ICON = {"process": "⏹", "installer": "📦", "firewall": "🛡", "shortcut": "🔗",
         "exe": "🖥", "source": "📁", "config": "🔑"}


class UninstallApp:
    W, H = 700, 660

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("rdpctl — Kaldırıcı")
        ui.apply_base(self.root)
        ui.center(self.root, self.W, self.H)
        self.root.minsize(600, 560)
        self._q: "queue.Queue" = queue.Queue()
        self.items = []
        self.vars = []

        head = tk.Canvas(self.root, height=96, highlightthickness=0, bd=0, bg=THEME.bg)
        head.pack(fill="x")

        def paint(e=None):
            w = head.winfo_width() or self.W
            ui.gradient(head, w, 96, "#7F1D1D", "#1E3A8A")
            head.delete("t")
            head.create_text(28, 38, anchor="w", text="🧹  rdpctl'yi Kaldır",
                             font=f(18, "bold"), fill="#FFFFFF", tags="t")
            head.create_text(30, 68, anchor="w", font=f(10), tags="t",
                             fill=mix("#FFFFFF", "#7F1D1D", 0.2),
                             text="Eski kurulumları, kopyaları ve bıraktığı izleri temizler.")
        head.bind("<Configure>", paint)

        self.body = tk.Frame(self.root, bg=THEME.bg)
        self.body.pack(fill="both", expand=True, padx=24, pady=20)
        self._scan()
        ui.fade_in(self.root)

    # --- yardımcılar ---
    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    @staticmethod
    def _card(parent, **kw):
        return tk.Frame(parent, bg=THEME.surface, padx=18, pady=14,
                        highlightbackground=THEME.border, highlightthickness=1, **kw)

    def _check(self, parent, var, text, bg=THEME.surface, font=None):
        return tk.Checkbutton(parent, variable=var, text=text, bg=bg, fg=THEME.text,
                              activebackground=bg, activeforeground=THEME.text,
                              selectcolor=THEME.surface_2, highlightthickness=0, bd=0,
                              font=font or f(10), anchor="w", justify="left",
                              wraplength=520, cursor="hand2")

    # --- 1) tarama ---
    def _scan(self):
        self._clear()
        box = tk.Frame(self.body, bg=THEME.bg)
        box.place(relx=0.5, rely=0.42, anchor="center")
        sp = ui.Spinner(box, size=46, bg=THEME.bg, width=5)
        sp.pack()
        sp.start()
        tk.Label(box, text="Bilgisayarınız taranıyor…", bg=THEME.bg, fg=THEME.text,
                 font=f(13, "bold")).pack(pady=(16, 4))
        tk.Label(box, text="rdpctl dosyaları, kısayollar ve ayarlar aranıyor",
                 bg=THEME.bg, fg=THEME.text_muted, font=f(10)).pack()

        def work():
            try:
                found = un.discover()
            except Exception as exc:  # tarama asla çökertmesin
                found = []
                self._q.put(("scan_err", str(exc)))
            self._q.put(("scanned", found))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(100, self._poll)

    def _poll(self):
        try:
            while True:
                kind, data = self._q.get_nowait()
                if kind == "scanned":
                    self.items = data
                    self.root.after(500, self._show_list)   # spinner bir an görünsün
                elif kind == "progress":
                    self._on_progress(*data)
                elif kind == "done":
                    self._show_done(*data)
                    return
        except queue.Empty:
            pass
        self.root.after(60, self._poll)

    # --- 2) liste ---
    def _show_list(self):
        self._clear()
        if not self.items:
            self._finale(True, "Temiz!", "Bu bilgisayarda rdpctl bulunamadı.", None, [])
            return

        tk.Label(self.body, text=f"{len(self.items)} öğe bulundu", bg=THEME.bg, fg=THEME.text,
                 font=f(13, "bold")).pack(anchor="w")
        tk.Label(self.body, text="Kaldırılacakları seçin. Kaynak klasörleri varsayılan olarak "
                                 "seçili değildir.", bg=THEME.bg, fg=THEME.text_muted,
                 font=f(9)).pack(anchor="w", pady=(2, 10))

        card = self._card(self.body)
        card.pack(fill="both", expand=True)
        canvas = tk.Canvas(card, bg=THEME.surface, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(card, command=canvas.yview, bg=THEME.surface_2,
                          troughcolor=THEME.surface, bd=0, highlightthickness=0)
        inner = tk.Frame(canvas, bg=THEME.surface)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window(0, 0, anchor="nw", window=inner)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        if len(self.items) > 7:
            sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        self.vars = []
        for it in self.items:
            row = tk.Frame(inner, bg=THEME.surface)
            row.pack(fill="x", pady=4)
            v = tk.BooleanVar(value=it.default)
            self.vars.append(v)
            tk.Label(row, text=_ICON.get(it.kind, "•"), bg=THEME.surface, fg=THEME.text,
                     font=f(12), width=2).pack(side="left")
            self._check(row, v, it.label).pack(side="left", fill="x", expand=True)
            if it.admin:
                tk.Label(row, text="yönetici", bg=mix(THEME.surface, THEME.warning, .18),
                         fg=THEME.warning, font=f(8, "bold"), padx=6).pack(side="right")

        # Günlük yedeği
        self.keep_logs = tk.BooleanVar(value=True)
        opt = tk.Frame(self.body, bg=THEME.bg)
        opt.pack(fill="x", pady=(12, 0))
        self._check(opt, self.keep_logs,
                    "Denetim günlüklerini silmeden önce Masaüstüne yedekle (önerilir)",
                    bg=THEME.bg).pack(anchor="w")

        # Yönetici uyarısı
        if un.IS_WIN and any(it.admin for it in self.items) and not un.is_admin():
            warn = tk.Frame(self.body, bg=mix(THEME.bg, THEME.warning, .12), padx=12, pady=8)
            warn.pack(fill="x", pady=(10, 0))
            tk.Label(warn, text="⚠  Bazı öğeler yönetici izni gerektiriyor.",
                     bg=warn["bg"], fg=THEME.warning, font=f(9, "bold")).pack(side="left")
            ui.RoundedButton(warn, "Yönetici olarak aç", self._elevate, kind="ghost",
                             width=170, height=30, radius=9, bg=warn["bg"],
                             font=f(9, "bold")).pack(side="right")

        btns = tk.Frame(self.body, bg=THEME.bg)
        btns.pack(fill="x", pady=(16, 0))
        ui.RoundedButton(btns, "Seçilenleri Kaldır", self._confirm, kind="danger", icon="🗑",
                         width=210, height=44, bg=THEME.bg).pack(side="right")
        ui.RoundedButton(btns, "Vazgeç", self.root.destroy, kind="ghost",
                         width=120, height=44, bg=THEME.bg).pack(side="right", padx=10)

    def _elevate(self):
        if un.relaunch_as_admin():
            self.root.destroy()

    def _confirm(self):
        chosen = [it for it, v in zip(self.items, self.vars) if v.get()]
        if not chosen:
            ui.Toast.show(self.root, "Kaldırılacak öğe seçilmedi", kind="info")
            return
        note = ("Günlükler önce Masaüstüne yedeklenecek."
                if self.keep_logs.get() else "Günlükler YEDEKLENMEDEN silinecek!")
        if not messagebox.askyesno(
                "Emin misiniz?",
                f"Seçilen {len(chosen)} öğe kalıcı olarak kaldırılacak.\n{note}\n\nDevam edilsin mi?",
                icon="warning", parent=self.root):
            return
        self._run(chosen, self.keep_logs.get())

    # --- 3) ilerleme ---
    def _run(self, chosen, keep_logs):
        self._clear()
        order = sorted(chosen, key=lambda it: un._ORDER.index(it.kind))
        tk.Label(self.body, text="Kaldırılıyor…", bg=THEME.bg, fg=THEME.text,
                 font=f(13, "bold")).pack(anchor="w")
        self._bar = tk.Canvas(self.body, height=8, bg=THEME.surface_2, highlightthickness=0)
        self._bar.pack(fill="x", pady=(10, 14))
        self._frac, self._frac_target = 0.0, 0.0
        self._animate_bar()

        card = self._card(self.body)
        card.pack(fill="both", expand=True)
        self._rows = {}
        for it in order:
            row = tk.Frame(card, bg=THEME.surface)
            row.pack(fill="x", pady=3)
            st = tk.Label(row, text="•", width=2, bg=THEME.surface, fg=THEME.text_muted,
                          font=f(12, "bold"))
            st.pack(side="left")
            tk.Label(row, text=it.label, bg=THEME.surface, fg=THEME.text, font=f(9),
                     anchor="w", justify="left", wraplength=520).pack(side="left", fill="x")
            msg = tk.Label(row, text="", bg=THEME.surface, fg=THEME.text_muted, font=f(8))
            msg.pack(side="right")
            self._rows[id(it)] = (st, msg)
        self._total = len(order)

        def work():
            backup, results = un.uninstall(
                order, keep_logs=keep_logs,
                progress=lambda i, it, ok, m: self._q.put(("progress", (i, it, ok, m))))
            self._q.put(("done", (backup, results)))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(60, self._poll)

    def _animate_bar(self):
        if not self._bar.winfo_exists():
            return
        self._frac += (self._frac_target - self._frac) * 0.2
        w = self._bar.winfo_width() or 600
        self._bar.delete("all")
        self._bar.create_rectangle(0, 0, w * self._frac, 8, fill=THEME.primary, outline="")
        self.root.after(16, self._animate_bar)

    def _on_progress(self, i, it, ok, msg):
        if i < 0:
            ui.Toast.show(self.root, msg, ms=3500, kind="danger")
            return
        st, ml = self._rows.get(id(it), (None, None))
        if st is not None:
            st.configure(text="✓" if ok else "✕", fg=THEME.success if ok else THEME.danger)
            ml.configure(text=msg, fg=THEME.text_muted if ok else THEME.danger)
        self._frac_target = (i + 1) / max(1, self._total)

    # --- 4) bitiş ---
    def _show_done(self, backup, results):
        fails = [(it, m) for it, ok, m in results if not ok]
        self.root.after(450, lambda: (
            self._clear(),
            self._finale(not fails,
                         "rdpctl kaldırıldı" if not fails else "Kısmen kaldırıldı",
                         "Seçilen tüm öğeler temizlendi." if not fails
                         else f"{len(fails)} öğe kaldırılamadı.",
                         backup, fails)))

    def _finale(self, ok, title, sub, backup, fails):
        box = tk.Frame(self.body, bg=THEME.bg)
        box.place(relx=0.5, rely=0.4, anchor="center")
        color = THEME.success if ok else THEME.warning
        c = tk.Canvas(box, width=110, height=110, bg=THEME.bg, highlightthickness=0)
        c.pack()

        def draw(t=0.0):
            c.delete("all")
            c.create_oval(8, 8, 102, 102, outline=mix(THEME.bg, color, .25), width=6)
            c.create_arc(8, 8, 102, 102, start=90, extent=-360 * min(1, t), style="arc",
                         outline=color, width=6)
            if t >= 1:
                if ok:
                    c.create_line(34, 57, 49, 72, 77, 41, fill=color, width=7,
                                  capstyle="round", joinstyle="round")
                else:
                    c.create_text(55, 55, text="!", fill=color, font=f(36, "bold"))
            else:
                c.after(16, lambda: draw(t + 0.05))
        draw()

        tk.Label(box, text=title, bg=THEME.bg, fg=THEME.text, font=f(17, "bold")).pack(pady=(16, 2))
        tk.Label(box, text=sub, bg=THEME.bg, fg=THEME.text_muted, font=f(10)).pack()
        for it, m in fails[:4]:
            tk.Label(box, text=f"✕ {it.label} — {m}", bg=THEME.bg, fg=THEME.danger,
                     font=f(9), wraplength=560, justify="left").pack(anchor="w", pady=(6, 0))
        if backup:
            tk.Label(box, text=f"Günlük yedeği: {backup}", bg=THEME.bg, fg=THEME.text_muted,
                     font=f(9), wraplength=560).pack(pady=(14, 6))
        btns = tk.Frame(box, bg=THEME.bg)
        btns.pack(pady=(14, 0))
        if backup:
            ui.RoundedButton(btns, "Yedeği Aç", lambda: _open_folder(backup), kind="ghost",
                             icon="📂", width=150, height=42, bg=THEME.bg).pack(side="left", padx=6)
        ui.RoundedButton(btns, "Kapat", self.root.destroy, kind="primary",
                         width=150, height=42, bg=THEME.bg).pack(side="left", padx=6)

    def run(self):
        self.root.mainloop()


def _open_folder(path):
    try:
        if un.IS_WIN:
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif un.IS_MAC:
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass
