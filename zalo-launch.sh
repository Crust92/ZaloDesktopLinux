#!/bin/bash
ARGS=(--no-sandbox)
[ -n "$WAYLAND_DISPLAY" ] && [ -z "$ZALO_FORCE_WAYLAND" ] && unset WAYLAND_DISPLAY
[ "$ZALO_DISABLE_GPU" = "1" ] && ARGS+=(--disable-gpu --in-process-gpu)
exec /app/electron/electron /app/zalo "${ARGS[@]}" "$@"
