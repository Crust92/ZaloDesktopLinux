#!/usr/bin/env bash
# Tai ve moi thu can de dung Zalo Linux tu dau.
# Repo khong chua binary — script nay lay chung ve thu muc ./sources/
#
#   ./fetch-sources.sh          # tai tat ca
#   ./fetch-sources.sh jxl      # chi chuan bi jxlbin/
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/sources"
ELECTRON_VER=22.3.27          # phai khop ban Zalo dung, dung tu y nang
UA_MAC='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31mLoi: %s\033[0m\n' "$*" >&2; exit 1; }

mkdir -p "$SRC"

# ------------------------------------------------------------------ 1. jxlbin
prepare_jxl() {
  say "jxlbin: lay djxl/cjxl tu goi he thong libjxl-tools"
  command -v djxl >/dev/null 2>&1 || die "chua co djxl — cai bang: sudo apt install libjxl-tools"
  mkdir -p "$HERE/jxlbin"
  for b in djxl cjxl; do
    cp -f "$(command -v $b)" "$HERE/jxlbin/$b"
    chmod +x "$HERE/jxlbin/$b"
  done
  # runtime cua Flatpak (org.freedesktop.Platform//25.08) thieu hai thu vien nay
  for lib in libjpeg.so.8 libgif.so.7; do
    p="$(ldconfig -p 2>/dev/null | awk -v L="$lib" '$1==L {print $NF; exit}')"
    [ -n "$p" ] && cp -fL "$p" "$HERE/jxlbin/$lib" || echo "   (canh bao: khong tim thay $lib tren he thong)"
  done
  ls -la "$HERE/jxlbin"
}

[ "${1:-}" = "jxl" ] && { prepare_jxl; exit 0; }

# --------------------------------------------------------------------- 2. DMG
say "Zalo macOS (.dmg) — nguon chinh thuc, tu dong theo ban moi nhat"
# zalo.me/download/zalo-pc chuyen huong theo User-Agent; UA macOS -> file .dmg
DMG_URL="$(curl -sIL -o /dev/null -w '%{url_effective}' --max-time 60 \
            -A "$UA_MAC" 'https://zalo.me/download/zalo-pc?utm=90000')"
case "$DMG_URL" in
  *.dmg) ;;
  *) die "khong lay duoc link .dmg (nhan duoc: $DMG_URL)" ;;
esac
DMG_FILE="$SRC/$(basename "$DMG_URL")"
echo "   $DMG_URL"
[ -f "$DMG_FILE" ] || curl -L --progress-bar -A "$UA_MAC" -o "$DMG_FILE" "$DMG_URL"
echo "   -> $DMG_FILE ($(du -h "$DMG_FILE" | cut -f1))"

# Ban Windows KHONG dung duoc: sqlite3 trong do chi co binary win32-ia32 (PE, 32-bit)
# va loader theo quy uoc pre-gyp cu, khong resolve duoc napi-v6-linux-x64.
# Xem README muc "Vi sao phai dung ban macOS".

# ---------------------------------------------------------------- 3. Electron
say "Electron $ELECTRON_VER linux-x64"
EL_FILE="$SRC/electron-v$ELECTRON_VER-linux-x64.zip"
[ -f "$EL_FILE" ] || curl -L --progress-bar -o "$EL_FILE" \
  "https://github.com/electron/electron/releases/download/v$ELECTRON_VER/electron-v$ELECTRON_VER-linux-x64.zip"
echo "   -> $EL_FILE ($(du -h "$EL_FILE" | cut -f1))"

# -------------------------------------------------------------------- 4. snap
say "snap zalo-linux (chi lay 2 native module Linux + bootstrap shim)"
SNAP_FILE="$SRC/zalo-linux.snap"
if [ ! -f "$SNAP_FILE" ]; then
  if command -v snap >/dev/null 2>&1; then
    ( cd "$SRC" && snap download zalo-linux --basename=zalo-linux )
    mv -f "$SRC"/zalo-linux*.snap "$SNAP_FILE" 2>/dev/null || true
  else
    # Khong co snapd: hoi thang Snap Store API
    INFO="$(curl -s --max-time 60 -H 'Snap-Device-Series: 16' \
             'https://api.snapcraft.io/v2/snaps/info/zalo-linux?fields=download&architecture=amd64')"
    URL="$(printf '%s' "$INFO" | grep -o '"url":"[^"]*"' | head -1 | cut -d'"' -f4)"
    [ -n "$URL" ] || die "khong lay duoc link snap. Cai snapd roi chay lai, hoac tai tay tu snapcraft.io/zalo-linux"
    curl -L --progress-bar -o "$SNAP_FILE" "$URL"
  fi
fi
echo "   -> $SNAP_FILE ($(du -h "$SNAP_FILE" | cut -f1))"

prepare_jxl

say "Xong. Dung tiep bang:"
cat <<EOF
  ZALO_DMG="$DMG_FILE" \\
  ZALO_SNAP="$SNAP_FILE" \\
  ELECTRON_ZIP="$EL_FILE" \\
  ./build.sh --from-source
EOF
