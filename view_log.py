#!/usr/bin/env python3
"""Denetim günlüğünü görüntüleme ve bütünlük (kurcalama) doğrulama aracı.

Kullanım:
  python3 view_log.py ~/.rdpctl/audit.log            # tüm kayıtları göster
  python3 view_log.py ~/.rdpctl/audit.log --changes  # yalnız dosya değişiklikleri
  python3 view_log.py ~/.rdpctl/audit.log --verify    # zincir bütünlüğünü doğrula
"""
import argparse

from rdpctl.audit import read_all, verify_chain


def main() -> int:
    ap = argparse.ArgumentParser(description="rdpctl denetim günlüğü görüntüleyici")
    ap.add_argument("path", help="audit.log yolu")
    ap.add_argument("--changes", action="store_true", help="yalnız dosya değişiklikleri")
    ap.add_argument("--verify", action="store_true", help="kurcalama kontrolü")
    args = ap.parse_args()

    if args.verify:
        ok = verify_chain(args.path)
        print("Günlük bütünlüğü:", "SAĞLAM ✓" if ok else "KURCALANMIŞ ✗")
        return 0 if ok else 1

    for rec in read_all(args.path):
        if args.changes and rec.get("event") != "file_change":
            continue
        extra = ", ".join(f"{k}={v}" for k, v in rec.items()
                          if k not in ("ts", "event", "prev"))
        print(f"[{rec.get('ts','')}] {rec.get('event',''):<14} {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
