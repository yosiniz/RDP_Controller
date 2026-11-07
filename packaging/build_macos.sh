#!/usr/bin/env bash
# macOS için rdpctl.app ve rdpctl-kaldir.app üretir.
#
# ÖNEMLİ: Python 3.10+ gerekir. macOS'un/Xcode'un kendi Python 3.9'u ile
# pynput'un gerektirdiği pyobjc derlenemiyor (yeni clang hatası). Bu betik
# uygun bir Python 3.10+ bulur ve izole bir sanal ortamda derler.
set -e
cd "$(dirname "$0")/.."

echo "============================================================"
echo "  rdpctl — macOS uygulaması derleniyor"
echo "============================================================"

# 1) Uygun Python 3.10+ bul (pyobjc'nin hazır paketleri bu sürümlerde var)
PY=""
for c in python3.13 python3.12 python3.11 python3.10; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ] && command -v python3 >/dev/null 2>&1; then
  v=$(python3 -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null || echo 0)
  if [ "$v" -ge 310 ]; then PY="python3"; fi
fi

if [ -z "$PY" ]; then
  echo
  echo "[HATA] Python 3.10+ bulunamadı. Mevcut python3 muhtemelen 3.9 (çok eski)."
  echo
  echo "Çözüm — şunlardan BİRİNİ yapın, sonra bu betiği tekrar çalıştırın:"
  echo "  A) python.org'dan Python 3.12 kurun (macOS 64-bit universal2 installer):"
  echo "       https://www.python.org/downloads/macos/"
  echo "  B) Homebrew varsa:   brew install python@3.12"
  echo
  exit 1
fi
echo "Kullanılan Python: $($PY --version 2>&1)  ($PY)"

# 1.5) tkinter (Tk) var mı? Homebrew Python'u Tk'yi ayrı paketler; yoksa
#      derlenen .app arayüzsüz kalır ve açılmaz. Eksikse kurmayı dene.
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
  PYVER=$("$PY" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  echo "tkinter (Tk) eksik — kurulmaya çalışılıyor (python-tk@$PYVER)…"
  if command -v brew >/dev/null 2>&1; then
    brew install "python-tk@$PYVER" || brew install python-tk || true
  fi
  if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
    echo
    echo "[HATA] tkinter hâlâ yok. Şunu çalıştırıp betiği tekrar deneyin:"
    echo "    brew install python-tk@$PYVER"
    exit 1
  fi
  echo "tkinter kuruldu."
fi

# 2) İzole sanal ortam (sistem/Xcode Python'ını kirletmeden)
VENV=".build-venv"
rm -rf "$VENV"
"$PY" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "Pip güncelleniyor ve bağımlılıklar kuruluyor (birkaç dakika sürebilir)…"
python -m pip install --upgrade pip wheel >/dev/null
python -m pip install --upgrade pyinstaller
python -m pip install -r requirements.txt

# 3) Paketle
echo "Paketleniyor…"
pyinstaller --noconfirm packaging/rdpctl.spec
pyinstaller --noconfirm packaging/rdpctl-kaldir.spec
deactivate

echo
echo "============================================================"
echo "  TAMAM! Uygulamalarınız hazır:"
echo "    dist/rdpctl.app          (uygulama)"
echo "    dist/rdpctl-kaldir.app   (kaldırıcı)"
echo "============================================================"
echo "İlk açılış: rdpctl.app'e SAĞ TIK -> 'Aç' -> tekrar 'Aç'"
echo "İzinler   : Sistem Ayarları > Gizlilik ve Güvenlik >"
echo "            Ekran Kaydı ve Erişilebilirlik altında rdpctl'i işaretleyin."
echo
echo "SHA-256:"
shasum -a 256 dist/rdpctl.app/Contents/MacOS/rdpctl 2>/dev/null || true
