#!/usr/bin/env bash
# Dung Zalo Desktop chay native tren Linux, dong goi Flatpak.
#
#   ./build.sh                 # dung lai tu stage/ da co (nhanh, hay dung nhat)
#
# Chon ho so ban va bang ZALO_PROFILE=compat|default|full (mac dinh FULL).
#   compat  = chi phan can de chay, gan nhat voi "dong goi nguyen trang"
#   full    = them P8 (khai client type Windows) de mo khoa E2EE/zCloud
#   ./build.sh --from-source   # ghep lai tu dau: can .dmg macOS + .snap
#   ./build.sh --check         # chi kiem tra ban va, khong dung
#
# Bien moi truong khi dung --from-source:
#   ZALO_DMG=/duong/dan/ZaloSetup-universal-<ver>.dmg
#   ZALO_SNAP=/duong/dan/zalo-linux_<ver>.snap
#   ELECTRON_ZIP=/duong/dan/electron-v22.3.27-linux-x64.zip
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPID=ac.d3v.ZaloLinux
STAGE="$HERE/stage"
MODE="${1:-}"
PROFILE="${ZALO_PROFILE:-full}"   # compat | default | full

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31mLoi: %s\033[0m\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "thieu lenh '$1' — cai bang: $2"; }

need python3 'sudo apt install python3'
need flatpak-builder 'sudo apt install flatpak-builder'

# ---------------------------------------------------------------- from-source
if [[ "$MODE" == "--from-source" ]]; then
  need 7z 'sudo apt install p7zip-full'
  need unsquashfs 'sudo apt install squashfs-tools'
  : "${ZALO_DMG:?can dat ZALO_DMG=... (ban macOS, KHONG dung ban Windows)}"
  : "${ZALO_SNAP:?can dat ZALO_SNAP=... (snap zalo-linux, lay 2 native module Linux)}"
  : "${ELECTRON_ZIP:?can dat ELECTRON_ZIP=... (electron v22.3.27 linux-x64)}"

  WORK="$HERE/.work"; rm -rf "$WORK"; mkdir -p "$WORK"

  say "1/5 Giai nen .dmg macOS (nguon app.asar chinh thuc)"
  # Ban Windows KHONG dung duoc: sqlite3 trong do chi co win32-ia32.
  7z x -o"$WORK/dmg" "$ZALO_DMG" >/dev/null
  ASAR="$(find "$WORK/dmg" -name app.asar | head -1)"
  [[ -n "$ASAR" ]] || die 'khong tim thay app.asar trong .dmg'
  python3 "$HERE/patches/unpack-asar.py" "$ASAR" "$STAGE/app"

  say "2/5 Giai nen snap (chi lay phan Linux)"
  unsquashfs -f -d "$WORK/snap" "$ZALO_SNAP" >/dev/null
  SNAPAPP="$(find "$WORK/snap" -maxdepth 6 -type d -name 'app' -path '*resources*' | head -1)"
  [[ -n "$SNAPAPP" ]] || die 'khong tim thay resources/app trong snap'
  # Chi 2 binary native + bootstrap shim + engine goi thoai. KHONG chep de len
  # ma nguon chinh thuc trong pc-dist.
  for p in \
      native/nativelibs/db-cross-v4/prebuilt/linux \
      native/nativelibs/sqlite3/binding/napi-v6-linux-x64 \
      native/qt-call-cap-linux ; do
    if [[ -d "$SNAPAPP/$p" ]]; then
      mkdir -p "$STAGE/app/$(dirname "$p")"
      cp -a "$SNAPAPP/$p" "$STAGE/app/$(dirname "$p")/"
      echo "   + $p"
    fi
  done
  cp -a "$SNAPAPP/bootstrap.js" "$STAGE/app/bootstrap.js"

  say "3/5 Electron 22.3.27 linux-x64"
  rm -rf "$STAGE/electron"; mkdir -p "$STAGE/electron"
  7z x -o"$STAGE/electron" "$ELECTRON_ZIP" >/dev/null
  chmod +x "$STAGE/electron/electron" "$STAGE/electron/chrome-sandbox" 2>/dev/null || true
else
  [[ -d "$STAGE/app/pc-dist" ]] || die "chua co $STAGE/app — chay lai voi --from-source"
fi

# ------------------------------------------------------------------- ban va
say "4/5 Ap ban va Linux"
if [[ "$MODE" == "--check" ]]; then
  python3 "$HERE/patches/apply-patches.py" "$STAGE/app" "--profile=$PROFILE" --check
  exit 0
fi
python3 "$HERE/patches/apply-patches.py" "$STAGE/app" "--profile=$PROFILE"

# ------------------------------------------------------------------- flatpak
say "5/5 Dung va cai Flatpak"
command -v djxl >/dev/null 2>&1 || echo "   (canh bao: khong co djxl tren may — kiem tra $HERE/jxlbin/)"
[[ -x "$HERE/jxlbin/djxl" ]] || die "thieu $HERE/jxlbin/djxl — zjxl se khong giai ma duoc anh .jxl"

flatpak kill "$APPID" 2>/dev/null || true
sleep 2
rm -rf "$HERE/.flatpak-builder/build" "$HERE/build-dir"
flatpak-builder --force-clean --user --install "$HERE/build-dir" "$HERE/$APPID.yml"

say "Xong. Chay: flatpak run $APPID"
echo "   Debug:  flatpak run $APPID --remote-debugging-port=9222"
