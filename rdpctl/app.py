"""Birleşik masaüstü başlatıcı.

Aynı uygulama her iki bilgisayara da kurulur. Açılışta kullanıcı rolünü
seçer:

  • "Bu bilgisayarı paylaş (Host)"  -> kontrol EDİLEN makine
  • "Başka bilgisayara bağlan"      -> kontrol EDEN makine (Controller)

Böylece tek bir yürütülebilir dosya iki rolü de karşılar.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

_HOST_DEFAULTS = dict(
    listen="0.0.0.0", port=7443, fps=8, max_width=1280, quality=60,
    watch=None, audit=None,
)
_CTRL_DEFAULTS = dict(host=None, port=7443, first_name=None, last_name=None)


def _choose_role() -> str | None:
    """Rol seçim penceresini gösterir; 'host', 'controller' veya None döner."""
    choice: dict = {"role": None}
    root = tk.Tk()
    root.title("rdpctl — Uzaktan Kontrol")
    root.geometry("460x340")
    root.resizable(False, False)

    try:
        style = ttk.Style()
        style.theme_use(style.theme_names()[0])
    except tk.TclError:
        pass

    ttk.Label(root, text="rdpctl", font=("", 26, "bold")).pack(pady=(26, 0))
    ttk.Label(root, text="Güvenli, onay tabanlı uzaktan kontrol",
              foreground="#555").pack(pady=(0, 20))

    def pick(role: str):
        choice["role"] = role
        root.destroy()

    host_btn = ttk.Button(
        root, text="🖥  Bu bilgisayarı paylaş\n(Host — kontrol edilecek)",
        command=lambda: pick("host"))
    host_btn.pack(fill="x", padx=40, pady=8, ipady=10)

    ctrl_btn = ttk.Button(
        root, text="🔌  Başka bilgisayara bağlan\n(Controller — kontrol eden)",
        command=lambda: pick("controller"))
    ctrl_btn.pack(fill="x", padx=40, pady=8, ipady=10)

    ttk.Label(
        root,
        text="Not: Bağlantı yalnızca karşı taraf onayladığında başlar\n"
             "ve tüm işlemler kaydedilir.",
        foreground="#777", justify="center").pack(side="bottom", pady=16)

    root.mainloop()
    return choice["role"]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    # İsteğe bağlı kısayollar: doğrudan rol komutuyla da başlatılabilir.
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
    else:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
