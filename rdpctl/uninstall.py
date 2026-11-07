"""rdpctl kaldırıcı (rdpctl-kaldir.exe).

Bilgisayardaki eski/mevcut rdpctl kurulumlarını ve bıraktığı izleri bulur,
kullanıcıya listeler ve onaylananları kaldırır:

  • çalışan rdpctl süreçleri (önce kapatılır)
  • kurulum sihirbazıyla kurulmuş sürüm (kayıt defterindeki kaldırıcısı)
  • rdpctl.exe kopyaları (Masaüstü, İndirilenler, Belgeler, Program Files…)
  • kısayollar ve Windows Güvenlik Duvarı kuralı
  • ~/.rdpctl yapılandırma klasörü (TLS anahtarı, sertifika, günlükler)
  • (isteğe bağlı) zip'ten çıkarılmış kaynak klasörleri

Denetim günlükleri güvenlik kaydıdır: varsayılan olarak silinmeden önce
Masaüstü'ne yedeklenir.

Komut satırı:
  rdpctl-kaldir --list          bulunanları listele, hiçbir şey silme
  rdpctl-kaldir --silent        varsayılan seçimlerle sessizce kaldır
  rdpctl-kaldir --no-backup     günlükleri yedekleme (önerilmez)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

APP = "rdpctl"
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
FIREWALL_RULE = "rdpctl"
_NO_WINDOW = 0x08000000 if IS_WIN else 0


# --- Bulunan öğe -----------------------------------------------------------
@dataclass
class Item:
    kind: str                 # process|installer|firewall|shortcut|exe|source|config
    label: str
    path: str = ""
    default: bool = True
    admin: bool = False       # yönetici izni gerektirir mi
    data: dict = field(default_factory=dict)


# --- Yardımcılar -----------------------------------------------------------
def _run(cmd: List[str], timeout: int = 60) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=_NO_WINDOW)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def is_admin() -> bool:
    if IS_WIN:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def relaunch_as_admin() -> bool:
    """Windows'ta kaldırıcıyı yönetici olarak yeniden başlatır."""
    if not IS_WIN:
        return False
    import ctypes
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe = sys.executable
        params = " ".join(f'"{a}"' for a in [os.path.abspath(sys.argv[0])] + sys.argv[1:])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


def _self_paths() -> set:
    """Kaldırıcının kendi dosyası (kendini silmeye çalışmasın)."""
    out = set()
    for p in (sys.executable, sys.argv[0] if sys.argv else ""):
        if p:
            try:
                out.add(os.path.normcase(os.path.realpath(p)))
            except OSError:
                pass
    return out


def _home() -> Path:
    return Path(os.environ.get("RDPCTL_HOME_OVERRIDE") or Path.home())


def _desktop() -> Path:
    h = _home()
    for cand in (h / "Desktop", h / "OneDrive" / "Desktop", h / "Masaüstü"):
        if cand.is_dir():
            return cand
    return h


def _search_roots() -> List[Tuple[Path, bool]]:
    """(klasör, yönetici-gerekir) çiftleri."""
    h = _home()
    roots = [(h / n, False) for n in
             ("Desktop", "Masaüstü", "Downloads", "İndirilenler", "Documents", "Belgeler",
              os.path.join("OneDrive", "Desktop"), os.path.join("OneDrive", "Documents"))]
    roots.append((h, False))  # yalnızca üst düzey (derinlik sınırı aşağıda)
    if IS_WIN:
        la = os.environ.get("LOCALAPPDATA")
        if la:
            roots.append((Path(la) / "Programs" / APP, False))
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            pf = os.environ.get(env)
            if pf:
                roots.append((Path(pf) / APP, True))
    elif IS_MAC:
        roots.append((Path("/Applications"), True))
        roots.append((h / "Applications", False))
    else:
        roots += [(h / ".local" / "bin", False), (Path("/opt") / APP, True),
                  (Path("/usr/local/bin"), True)]
    return roots


def _is_app_binary(p: Path) -> bool:
    name = p.name.lower()
    if IS_WIN:
        return name == "rdpctl.exe" and p.is_file()
    if IS_MAC and name == "rdpctl.app" and p.is_dir():
        return True
    if name == "rdpctl" and p.is_file():
        try:
            return bool(p.stat().st_mode & stat.S_IXUSR)
        except OSError:
            return False
    return False


def _is_source_dir(p: Path) -> bool:
    return (p / "run_app.py").is_file() and (p / "rdpctl" / "host.py").is_file()


_SKIP = {"node_modules", "AppData", "Library", "$Recycle.Bin", "site-packages",
         "__pycache__", ".git", "venv", ".venv"}


def _walk(root: Path, max_depth: int, on_entry: Callable[[Path], bool]) -> None:
    """Sınırlı derinlikte dolaşır. on_entry True dönerse o dizine inilmez."""
    budget = [4000]

    def rec(d: Path, depth: int):
        if budget[0] <= 0:
            return
        budget[0] -= 1
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        for e in entries:
            p = Path(e.path)
            if e.name.startswith(".") or e.name in _SKIP:
                continue
            if on_entry(p):
                continue
            try:
                is_dir = e.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if is_dir and depth < max_depth:
                rec(p, depth + 1)

    if root.is_dir():
        rec(root, 1)


# --- Keşif -----------------------------------------------------------------
def discover() -> List[Item]:
    items: List[Item] = []
    me = _self_paths()

    # 1) Çalışan süreçler
    procs = _running_processes()
    if procs:
        items.append(Item("process", f"Çalışan rdpctl uygulaması ({procs} adet) kapatılacak",
                          data={"count": procs}))

    # 2) Kurulum sihirbazıyla kurulmuş sürüm
    for name, cmd, admin in _registry_installs():
        items.append(Item("installer", f"Kurulu program: {name}", path=cmd, admin=admin))

    # 3) Güvenlik duvarı kuralı
    if IS_WIN and _firewall_rule_exists():
        items.append(Item("firewall", f"Güvenlik Duvarı kuralı: “{FIREWALL_RULE}”", admin=True))

    # 4) Kısayollar
    for sc in _shortcuts():
        items.append(Item("shortcut", f"Kısayol: {sc}", path=str(sc)))

    # 5) Uygulama kopyaları ve kaynak klasörleri
    seen = set()
    for root, admin in _search_roots():
        depth = 1 if root == _home() else 4

        def visit(p: Path, admin=admin) -> bool:
            key = os.path.normcase(str(p))
            if key in seen:
                return True
            if _is_app_binary(p):
                seen.add(key)
                if os.path.normcase(os.path.realpath(p)) not in me:
                    items.append(Item("exe", f"Uygulama dosyası: {p}", path=str(p), admin=admin))
                return True
            if p.is_dir() and _is_source_dir(p):
                seen.add(key)
                items.append(Item("source", f"Kaynak klasörü: {p}", path=str(p),
                                  default=False, admin=admin))
                return False  # içindeki dist\rdpctl.exe de ayrıca bulunsun
            return False

        _walk(root, depth, visit)

    # 6) Yapılandırma / anahtarlar / günlükler
    cfg = _home() / ".rdpctl"
    if cfg.is_dir():
        logs = sorted(cfg.glob("*.log"))
        extra = f" — {len(logs)} günlük dosyası içeriyor" if logs else ""
        items.append(Item("config", f"Ayarlar ve anahtarlar: {cfg}{extra}", path=str(cfg),
                          data={"logs": [str(x) for x in logs]}))
    return items


def _running_processes() -> int:
    if IS_WIN:
        rc, out = _run(["tasklist", "/FI", "IMAGENAME eq rdpctl.exe", "/FO", "CSV", "/NH"])
        return sum(1 for line in out.splitlines() if line.lower().startswith('"rdpctl.exe"'))
    rc, out = _run(["pgrep", "-x", APP])
    return len([x for x in out.split() if x.strip().isdigit()]) if rc == 0 else 0


def _registry_installs():
    if not IS_WIN:
        return []
    try:
        import winreg
    except ImportError:
        return []
    found = []
    roots = [(winreg.HKEY_CURRENT_USER, False), (winreg.HKEY_LOCAL_MACHINE, True)]
    sub = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    for hive, admin in roots:
        for view in (0, getattr(winreg, "KEY_WOW64_32KEY", 0)):
            try:
                k = winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    sk = winreg.OpenKey(k, name)
                    disp = winreg.QueryValueEx(sk, "DisplayName")[0]
                    if APP.lower() in str(disp).lower():
                        cmd = winreg.QueryValueEx(sk, "UninstallString")[0]
                        if (disp, cmd) not in [(d, c) for d, c, _ in found]:
                            found.append((disp, cmd, admin))
                except OSError:
                    continue
    return found


def _firewall_rule_exists() -> bool:
    rc, out = _run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={FIREWALL_RULE}"])
    return rc == 0 and FIREWALL_RULE.lower() in out.lower()


def _shortcuts() -> List[Path]:
    out = []
    names = ["rdpctl.lnk", "rdpctl.desktop"]
    places = [_desktop()]
    if IS_WIN:
        ad = os.environ.get("APPDATA")
        if ad:
            places.append(Path(ad) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    else:
        places.append(_home() / ".local" / "share" / "applications")
    for d in places:
        for n in names:
            if (d / n).exists():
                out.append(d / n)
        if (d / APP).is_dir() and IS_WIN:
            out.append(d / APP)
    return out


# --- Kaldırma --------------------------------------------------------------
def backup_logs(items: List[Item]) -> Optional[Path]:
    logs = [l for it in items if it.kind == "config" for l in it.data.get("logs", [])]
    if not logs:
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    dest = _desktop() / f"rdpctl-gunluk-yedegi-{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    for l in logs:
        shutil.copy2(l, dest / Path(l).name)
    return dest


def _rm(path: str) -> None:
    def onerr(func, p, exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            raise
    p = Path(path)
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p, onerror=onerr)
    elif p.exists() or p.is_symlink():
        try:
            p.unlink()
        except PermissionError:
            os.chmod(p, stat.S_IWRITE)
            p.unlink()


def remove(item: Item) -> Tuple[bool, str]:
    try:
        if item.kind == "process":
            if IS_WIN:
                _run(["taskkill", "/F", "/T", "/IM", "rdpctl.exe"])
            else:
                _run(["pkill", "-x", APP])
            import time
            time.sleep(0.8)
            left = _running_processes()
            return (left == 0, "Kapatıldı" if left == 0 else f"{left} süreç kapatılamadı")

        if item.kind == "installer":
            cmd = item.path.strip()
            exe = cmd.split('"')[1] if cmd.startswith('"') else cmd.split(" ")[0]
            rc, out = _run([exe, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=300)
            return (rc == 0, "Kaldırıldı" if rc == 0 else f"Hata ({rc})")

        if item.kind == "firewall":
            rc, out = _run(["netsh", "advfirewall", "firewall", "delete", "rule",
                            f"name={FIREWALL_RULE}"])
            return (rc == 0, "Silindi" if rc == 0 else "Yönetici izni gerekiyor")

        if item.kind in ("shortcut", "exe", "source", "config"):
            if not Path(item.path).exists():
                return True, "Zaten yok"
            _rm(item.path)
            # Boş kalan 'dist' / program klasörlerini de temizle
            parent = Path(item.path).parent
            if item.kind == "exe" and parent.name.lower() in ("dist", APP):
                try:
                    if not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass
            return True, "Silindi"
    except PermissionError:
        return False, "Erişim reddedildi (yönetici olarak deneyin)"
    except OSError as exc:
        return False, f"Silinemedi: {exc.strerror or exc}"
    return False, "Bilinmeyen öğe"


_ORDER = ["process", "installer", "firewall", "shortcut", "exe", "source", "config"]


def uninstall(items: List[Item], keep_logs: bool = True,
              progress: Optional[Callable[[int, Item, bool, str], None]] = None):
    """Seçili öğeleri güvenli sırada kaldırır. (yedek_klasörü, sonuçlar) döner."""
    items = sorted(items, key=lambda it: _ORDER.index(it.kind))
    backup = None
    if keep_logs:
        try:
            backup = backup_logs(items)
        except OSError as exc:
            # Yedek alınamadıysa günlükleri SİLME.
            items = [it for it in items if it.kind != "config"]
            if progress:
                progress(-1, Item("config", "Günlük yedeği"), False,
                         f"Yedeklenemedi, ayarlar klasörü korunuyor: {exc}")
    results = []
    for i, it in enumerate(items):
        ok, msg = remove(it)
        results.append((it, ok, msg))
        if progress:
            progress(i, it, ok, msg)
    return backup, results


# --- Komut satırı ----------------------------------------------------------
def cli(args) -> int:
    items = discover()
    if not items:
        print("Bu bilgisayarda rdpctl bulunamadı.")
        return 0
    print("Bulunanlar:")
    for it in items:
        mark = "x" if it.default else " "
        print(f"  [{mark}] {it.label}" + ("  (yönetici)" if it.admin else ""))
    if args.list:
        return 0
    chosen = [it for it in items if it.default]
    backup, results = uninstall(chosen, keep_logs=not args.no_backup)
    if backup:
        print(f"\nGünlükler yedeklendi: {backup}")
    fails = 0
    for it, ok, msg in results:
        print(f"  {'✓' if ok else '✕'} {it.label} — {msg}")
        fails += not ok
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="rdpctl kaldırıcı")
    ap.add_argument("--list", action="store_true", help="yalnızca listele")
    ap.add_argument("--silent", action="store_true", help="arayüzsüz kaldır")
    ap.add_argument("--no-backup", action="store_true", help="günlükleri yedekleme")
    args = ap.parse_args(argv)
    if args.list or args.silent:
        return cli(args)
    from .uninstall_gui import UninstallApp
    UninstallApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
