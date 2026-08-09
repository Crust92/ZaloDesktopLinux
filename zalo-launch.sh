#!/bin/bash
# Launcher Zalo cho Flatpak.
#
# Bien moi truong:
#   ZALO_FORCE_WAYLAND=1   giu Wayland (mac dinh ep X11 — xem ghi chu duoi)
#   ZALO_DISABLE_GPU=1     tat han tang toc GPU
#   ZALO_FORCE_GPU=1       ep bat GPU ke ca khi driver nam trong danh sach chan
#   ZALO_NO_GPU_TUNING=1   giu GPU nhung bo cac co tang toc bo sung
#   ZALO_NO_SANDBOX=1      chay khong qua zypak (chi de go roi)

# --- Di tru du lieu tu app-id cu -------------------------------------------
# Ban truoc dung id io.github.zalolinux.Zalo. Neu nguoi dung nang cap, chep
# du lieu sang mot lan roi thoi. Chi chay khi thu muc moi con trong.
OLD="$HOME/.var/app/io.github.zalolinux.Zalo/config/ZaloData"
NEW="${XDG_CONFIG_HOME:-$HOME/.config}/ZaloData"
if [ -d "$OLD" ] && [ ! -e "$NEW" ]; then
    echo "Zalo: chep du lieu tu ban cai cu, co the mat vai phut..." >&2
    mkdir -p "$(dirname "$NEW")"
    cp -a "$OLD" "$NEW" 2>/dev/null && echo "Zalo: chep xong." >&2 \
        || echo "Zalo: chep khong tron ven, se dang nhap lai tu dau." >&2
fi

ARGS=()

# Electron 22 (Chrome 108) tren Wayland khong ve duoc cua so — ep X11.
[ -n "$WAYLAND_DISPLAY" ] && [ -z "$ZALO_FORCE_WAYLAND" ] && unset WAYLAND_DISPLAY

# --- Tang toc ket xuat: TU DO theo may dich -------------------------------
# May khong co GPU (may ao, server, container) hoac dang ep render phan mem
# thi khong them co gi — de Chromium tu chon SwiftShader. Chi khi thay node
# render that su moi bat raster GPU.
gpu_tuning() {
    [ "$ZALO_NO_GPU_TUNING" = "1" ] && return 1
    [ "$LIBGL_ALWAYS_SOFTWARE" = "1" ] && return 1
    # /dev/dri/renderD* chi ton tai khi co GPU dung duoc (can --device=dri)
    compgen -G "/dev/dri/renderD*" >/dev/null 2>&1 || return 1
    return 0
}

if [ "$ZALO_DISABLE_GPU" = "1" ]; then
    ARGS+=(--disable-gpu --in-process-gpu)
elif gpu_tuning; then
    # Hai co nay an toan tren driver lanh: raster tren GPU thay vi CPU, va
    # khong copy texture qua RAM.
    ARGS+=(--enable-gpu-rasterization --enable-zero-copy)
    # Bo qua danh sach chan driver la viec RUI RO — danh sach do ton tai vi
    # nhung driver trong do tung gay treo. Chi bat khi nguoi dung tu yeu cau.
    [ "$ZALO_FORCE_GPU" = "1" ] && ARGS+=(--ignore-gpu-blocklist)
fi

# --- Sandbox --------------------------------------------------------------
# zypak cho phep sandbox cua Chromium chay ben trong Flatpak. Khong co no thi
# phai dung --no-sandbox, tuc bo mot lop bao ve.
if [ "$ZALO_NO_SANDBOX" = "1" ] || ! command -v zypak-wrapper >/dev/null 2>&1; then
    exec /app/electron/electron /app/zalo --no-sandbox "${ARGS[@]}" "$@"
fi
exec zypak-wrapper /app/electron/electron /app/zalo "${ARGS[@]}" "$@"
