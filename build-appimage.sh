#!/usr/bin/env bash
# Dong goi Zalo Desktop thanh AppImage — mot file chay duoc ngay, khong can
# Flatpak hay snapd tren may nguoi dung.
#
#   ./build-appimage.sh
#
# Can `stage/` da san sang (chay ./build.sh hoac ZALO_STAGE_ONLY=1 ./build.sh truoc).
# Chon ho so ban va bang ZALO_PROFILE nhu build.sh.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAGE="$HERE/stage"
DIST="$HERE/dist"
APPDIR="$HERE/.appdir"
PROFILE="${ZALO_PROFILE:-full}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31mLoi: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -d "$STAGE/app/pc-dist" ]] || die "chua co $STAGE/app — chay ZALO_STAGE_ONLY=1 ./build.sh --from-source truoc"
[[ -d "$STAGE/electron" ]]    || die "chua co $STAGE/electron"

say "1/4 Ap ban va (ho so: $PROFILE)"
python3 "$HERE/patches/apply-patches.py" "$STAGE/app" "--profile=$PROFILE"

say "2/4 Dung AppDir"
rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib"
cp -a "$STAGE/app"      "$APPDIR/usr/zalo"
cp -a "$STAGE/electron" "$APPDIR/usr/electron"
chmod +x "$APPDIR/usr/electron/electron" 2>/dev/null || true
# chrome-sandbox can setuid root, ma AppImage khong lam duoc -> bo di va chay
# voi --no-sandbox. Day la han che that su cua dinh dang AppImage.
rm -f "$APPDIR/usr/electron/chrome-sandbox"

# djxl/cjxl: uu tien ban trong jxlbin/, khong co thi lay tu he thong
for b in djxl cjxl; do
  if [[ -x "$HERE/jxlbin/$b" ]]; then cp -f "$HERE/jxlbin/$b" "$APPDIR/usr/bin/$b"
  elif command -v "$b" >/dev/null 2>&1; then cp -f "$(command -v $b)" "$APPDIR/usr/bin/$b"
  else echo "   (canh bao: khong co $b — anh .jxl se khong giai ma duoc)"; fi
done
for lib in libjpeg.so.8 libgif.so.7; do
  [[ -f "$HERE/jxlbin/$lib" ]] && cp -f "$HERE/jxlbin/$lib" "$APPDIR/usr/lib/$lib"
done

cp -f "$HERE/icon.png" "$APPDIR/zalo.png"
cat > "$APPDIR/zalo.desktop" <<'EOF'
[Desktop Entry]
Name=Zalo Desktop
GenericName=Nhan tin
Comment=Zalo Desktop cho Linux
Exec=AppRun %U
Icon=zalo
Terminal=false
Type=Application
Categories=Network;InstantMessaging;Chat;
StartupWMClass=zalo
EOF

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/lib:${LD_LIBRARY_PATH:-}"

# AppImage khong the cai setuid cho chrome-sandbox nen buoc phai --no-sandbox.
ARGS=(--no-sandbox)

[ -n "$WAYLAND_DISPLAY" ] && [ -z "$ZALO_FORCE_WAYLAND" ] && unset WAYLAND_DISPLAY

gpu_tuning() {
    [ "$ZALO_NO_GPU_TUNING" = "1" ] && return 1
    [ "$LIBGL_ALWAYS_SOFTWARE" = "1" ] && return 1
    compgen -G "/dev/dri/renderD*" >/dev/null 2>&1 || return 1
    return 0
}
if [ "$ZALO_DISABLE_GPU" = "1" ]; then
    ARGS+=(--disable-gpu --in-process-gpu)
elif gpu_tuning; then
    ARGS+=(--enable-gpu-rasterization --enable-zero-copy)
    [ "$ZALO_FORCE_GPU" = "1" ] && ARGS+=(--ignore-gpu-blocklist)
fi

exec "$HERE/usr/electron/electron" "$HERE/usr/zalo" "${ARGS[@]}" "$@"
EOF
chmod +x "$APPDIR/AppRun"

say "3/4 Lay appimagetool"
TOOL="$HERE/.appimagetool"
if [[ ! -x "$TOOL" ]]; then
  curl -L --progress-bar -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi

say "4/4 Dong goi"
mkdir -p "$DIST"
VER="$(python3 -c "import json;print(json.load(open('$STAGE/app/package.json'))['version'])")"
OUT="$DIST/ZaloDesktop-${VER}-x86_64.AppImage"
# appimagetool can FUSE; --appimage-extract-and-run tranh phu thuoc do
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT" 2>&1 | tail -3

rm -rf "$APPDIR"
say "Xong: $OUT ($(du -h "$OUT" | cut -f1))"
echo "  chmod +x '$OUT' && '$OUT'"
