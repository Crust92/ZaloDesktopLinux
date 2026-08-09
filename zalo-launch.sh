#!/bin/bash
# Launcher Zalo cho Flatpak.
#
# Bien moi truong:
#   ZALO_FORCE_WAYLAND=1   giu Wayland (mac dinh ep X11 — xem ghi chu duoi)
#   ZALO_DISABLE_GPU=1     tat tang toc GPU (dung khi driver tro chung)
#   ZALO_NO_GPU_TUNING=1   giu GPU nhung bo cac co tang toc bo sung
#   ZALO_ENABLE_LINUX_CALL=1  bat engine goi thoai cua tac gia snap (chua kiem thu)

ARGS=(--no-sandbox)

# Electron 22 (Chrome 108) tren Wayland khong ve duoc cua so — ep X11.
[ -n "$WAYLAND_DISPLAY" ] && [ -z "$ZALO_FORCE_WAYLAND" ] && unset WAYLAND_DISPLAY

if [ "$ZALO_DISABLE_GPU" = "1" ]; then
    ARGS+=(--disable-gpu --in-process-gpu)
elif [ "$ZALO_NO_GPU_TUNING" != "1" ]; then
    # Chrome 108 dua nhieu driver Linux vao danh sach chan nen mac dinh chi
    # raster bang CPU. Ba co duoi tra viec do lai cho GPU:
    #   ignore-gpu-blocklist    : bo qua danh sach chan driver
    #   enable-gpu-rasterization: raster tren GPU thay vi CPU
    #   enable-zero-copy        : khong copy texture qua RAM
    ARGS+=(--ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy)
fi

exec /app/electron/electron /app/zalo "${ARGS[@]}" "$@"
