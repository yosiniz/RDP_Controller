#!/usr/bin/env bash
# macOS için .app paketi üretir -> dist/rdpctl.app
set -e
cd "$(dirname "$0")/.."
python3 -m pip install --upgrade pyinstaller -r requirements.txt
pyinstaller --noconfirm packaging/rdpctl.spec
pyinstaller --noconfirm packaging/rdpctl-kaldir.spec
echo "Tamam -> dist/rdpctl.app ve dist/rdpctl-kaldir"
echo "Not: Sistem Ayarları > Gizlilik ve Güvenlik bölümünden"
echo "     'Ekran Kaydı' ve 'Erişilebilirlik' izinlerini verin."
