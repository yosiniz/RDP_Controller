#!/usr/bin/env bash
# Linux için tek-dosya çalıştırılabilir üretir -> dist/rdpctl
set -e
cd "$(dirname "$0")/.."
python3 -m pip install --upgrade pyinstaller -r requirements.txt
pyinstaller --noconfirm packaging/rdpctl.spec
pyinstaller --noconfirm packaging/rdpctl-kaldir.spec
echo "Tamam -> dist/rdpctl ve dist/rdpctl-kaldir"
