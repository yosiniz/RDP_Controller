#!/usr/bin/env bash
# =====================================================================
#  rdpctl - macOS surukle-birak kurulum imaji (.dmg) uretici
# ---------------------------------------------------------------------
#  dist/rdpctl.app'ten, icinde rdpctl.app ve /Applications kisayolu
#  bulunan sikistirilmis bir rdpctl.dmg olusturur. Son kullanici .dmg'yi
#  acip rdpctl'i Applications klasorune suruker.
#
#  YALNIZCA macOS'ta calisir (hdiutil/ditto Apple araclaridir). Linux'ta
#  calismaz. Once .app'i uretmek icin:  bash packaging/build_macos.sh
#
#  Cikti:  macosx/rdpctl.dmg
# =====================================================================
set -euo pipefail

# Betigin bulundugu klasorun ustu = depo koku
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

APP="$ROOT/dist/rdpctl.app"
VOLNAME="rdpctl"
OUT="$HERE/rdpctl.dmg"

# --- Ortam kontrolleri ----------------------------------------------
if [ "$(uname -s)" != "Darwin" ]; then
  echo "[HATA] Bu betik yalnizca macOS'ta calisir (hdiutil/ditto gerekir)." >&2
  echo "       Once bir Mac'te 'bash packaging/build_macos.sh' calistirin." >&2
  exit 1
fi

if [ ! -d "$APP" ]; then
  echo "[HATA] Uygulama bulunamadi: $APP" >&2
  echo "       Once uygulamayi uretin:" >&2
  echo "           bash packaging/build_macos.sh" >&2
  echo "       (bu komut dist/rdpctl.app olusturur), sonra bu betigi tekrar calistirin." >&2
  exit 1
fi

for tool in hdiutil ditto ln; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "[HATA] Gerekli arac bulunamadi: $tool" >&2
    exit 1
  fi
done

# --- Gecici hazirlik klasoru ----------------------------------------
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/rdpctl-dmg.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "rdpctl.app hazirlik klasorune kopyalaniyor..."
# ditto .app imza/izinlerini bozmadan kopyalar
ditto "$APP" "$STAGE/rdpctl.app"

echo "/Applications kisayolu ekleniyor (surukle-birak icin)..."
ln -s /Applications "$STAGE/Applications"

# --- Eski cikti varsa sil -------------------------------------------
rm -f "$OUT"

echo ".dmg olusturuluyor (sikistirilmis)..."
hdiutil create \
  -volname "$VOLNAME" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$OUT"

echo
echo "============================================================"
echo "  TAMAM! Kurulum imajiniz hazir:"
echo "    $OUT"
echo "============================================================"
echo "Son kullanici: .dmg'yi cift tiklar, rdpctl'i Applications'a suruker."
echo "Ilk acilista Gatekeeper icin: rdpctl.app'e SAG TIK -> 'Ac'."
echo
echo "SHA-256:"
shasum -a 256 "$OUT" 2>/dev/null || true
