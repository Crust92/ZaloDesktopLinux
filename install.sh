#!/usr/bin/env bash
# Cai Zalo Desktop for Linux tu GitHub Release.
#
#   curl -fsSL https://raw.githubusercontent.com/Crust92/ZaloDesktopLinux/main/install.sh | bash
#
# Tuy chon:
#   --method flatpak|appimage|snap|auto   (mac dinh: auto)
#   --version v26.8.10                    (mac dinh: ban moi nhat)
#   --uninstall                           go cai dat
#   --yes                                 khong hoi
set -euo pipefail

REPO="Crust92/ZaloDesktopLinux"
APPID="ac.d3v.ZaloLinux"
SNAPNAME="zalo-desktop"
BINDIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
APPDIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONDIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"

METHOD=auto
VERSION=""
ASSUME_YES=0
UNINSTALL=0

c_ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m%s\033[0m\n' "$*"; }
c_err()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
say()    { printf '\033[1m==> %s\033[0m\n' "$*"; }
die()    { c_err "Loi: $*"; exit 1; }
have()   { command -v "$1" >/dev/null 2>&1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --method) METHOD="${2:-}"; shift 2 ;;
    --method=*) METHOD="${1#*=}"; shift ;;
    --version) VERSION="${2:-}"; shift 2 ;;
    --version=*) VERSION="${1#*=}"; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    -h|--help)
      # KHONG doc tu "$0": khi chay qua `curl | bash` thi $0 la "bash", khong phai file.
      cat <<'HELP'
Cai Zalo Desktop for Linux tu GitHub Release.

  curl -fsSL https://raw.githubusercontent.com/Crust92/ZaloDesktopLinux/main/install.sh | bash

Tuy chon:
  --method flatpak|appimage|snap|auto   (mac dinh: auto)
  --version v26.8.10-8                  (mac dinh: ban moi nhat)
  --uninstall                           go cai dat
  --yes                                 khong hoi
HELP
      exit 0 ;;
    *) die "tham so la: $1 (dung --help)" ;;
  esac
done

# Khi chay qua `curl | bash`, stdin la ONG chu khong phai terminal. Flatpak/snap
# van hoi terminal vi tri con tro (ESC[6n) roi cho tra loi tren stdin — khong ai
# doc nen chuoi tra loi bi in ra man hinh dang "^[[28;1R". Cho stdin tro ve
# terminal that (neu co) va tat giao dien tien trinh loe loet cua flatpak.
run_tty() {
  # `[ -e /dev/tty ]` KHONG du: file luon ton tai nhung MO duoc hay khong con tuy
  # co terminal dieu khien hay khong (cron, CI, tien trinh nen deu khong co).
  # Phai thu mo that.
  if : </dev/tty 2>/dev/null; then
    FLATPAK_FANCY_OUTPUT=0 "$@" </dev/tty
  else
    FLATPAK_FANCY_OUTPUT=0 "$@" </dev/null
  fi
}

# ----------------------------------------------------------------- go cai dat
if [ "$UNINSTALL" = 1 ]; then
  say "Go cai dat"
  have flatpak && run_tty flatpak uninstall --user -y "$APPID" 2>/dev/null && c_ok "  da go ban Flatpak" || true
  have snap && sudo snap remove "$SNAPNAME" 2>/dev/null && c_ok "  da go ban Snap" || true
  rm -f "$BINDIR/zalo-desktop" "$APPDIR/zalo-desktop.desktop" "$ICONDIR/zalo-desktop.png" 2>/dev/null || true
  c_ok "Xong."
  exit 0
fi

# --------------------------------------------------------------- kiem tra may
[ "$(uname -m)" = "x86_64" ] || die "hien chi co ban x86_64 (may nay: $(uname -m))"
have curl || die "can curl"

# ------------------------------------------------------------- chon phuong an
if [ "$METHOD" = auto ]; then
  if have flatpak; then METHOD=flatpak
  elif have snap;  then METHOD=snap
  else                  METHOD=appimage
  fi
fi
case "$METHOD" in flatpak|appimage|snap) ;; *) die "--method phai la flatpak|appimage|snap|auto" ;; esac

# --------------------------------------------------------------- lay ban phat hanh
api="https://api.github.com/repos/$REPO/releases/latest"
[ -n "$VERSION" ] && api="https://api.github.com/repos/$REPO/releases/tags/$VERSION"
say "Tim ban phat hanh"
meta="$(curl -fsSL "$api")" || die "khong lay duoc thong tin release tu GitHub"
tag="$(printf '%s' "$meta" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
[ -n "$tag" ] || die "khong doc duoc tag"
echo "   $tag"

pick_url() { # $1 = duoi file
  printf '%s' "$meta" \
    | tr ',' '\n' | grep '"browser_download_url"' \
    | sed -n 's/.*"browser_download_url": *"\([^"]*\)".*/\1/p' \
    | grep -i -- "$1" | head -1 || true
}

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

confirm() {
  [ "$ASSUME_YES" = 1 ] && return 0
  [ -t 0 ] || return 0   # chay qua ong dan (curl | bash) thi khong hoi
  printf 'Tiep tuc? [Y/n] '; read -r a </dev/tty || return 0
  case "$a" in n|N|no|khong) exit 1 ;; esac
}


download() { # $1=url $2=dich
  say "Tai $(basename "$2")"
  curl -fL --progress-bar -o "$2" "$1" || die "tai that bai"
  verify_sum "$1" "$2"
}

# Doi chieu SHA256SUMS cua release. Script nay thuong chay qua `curl | bash` nen
# xac minh tinh toan ven la bat buoc khi release co file sum.
verify_sum() { # $1=url goc $2=file da tai
  sums_url="$(pick_url 'SHA256SUMS')"
  [ -n "$sums_url" ] || { c_warn "   (release nay chua co SHA256SUMS — bo qua kiem tra)"; return 0; }
  curl -fsSL -o "$tmp/SHA256SUMS" "$sums_url" || { c_warn "   (khong tai duoc SHA256SUMS)"; return 0; }
  name="$(basename "$1")"
  want="$(grep -F "  $name" "$tmp/SHA256SUMS" 2>/dev/null | awk '{print $1}' | head -1 || true)"
  [ -n "$want" ] || { c_warn "   (khong co dong sum cho $name)"; return 0; }
  got="$(sha256sum "$2" | awk '{print $1}')"
  [ "$want" = "$got" ] || die "SHA256 KHONG khop cho $name — dung cai dat.
   mong doi: $want
   thuc te : $got"
  c_ok "   SHA256 khop"
}

# ------------------------------------------------------------------- Flatpak
install_flatpak() {
  have flatpak || die "chua co flatpak. Fedora: sudo dnf install flatpak | Ubuntu: sudo apt install flatpak"
  url="$(pick_url '.flatpak')"; [ -n "$url" ] || die "release khong co goi .flatpak"
  # runtime nam o Flathub; them remote neu chua co
  if ! flatpak remotes --columns=name 2>/dev/null | grep -qx flathub; then
    say "Them remote Flathub (de lay runtime)"
    run_tty flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
  fi
  download "$url" "$tmp/zalo.flatpak"
  say "Cai (Flatpak, che do --user)"
  run_tty flatpak install --user -y "$tmp/zalo.flatpak"
  c_ok "Xong. Chay bang:  flatpak run $APPID"
}

# ------------------------------------------------------------------ AppImage
install_appimage() {
  url="$(pick_url '.AppImage')"; [ -n "$url" ] || die "release khong co goi .AppImage"
  mkdir -p "$BINDIR" "$APPDIR" "$ICONDIR"
  download "$url" "$BINDIR/zalo-desktop"
  chmod +x "$BINDIR/zalo-desktop"
  # icon + muc menu de hien trong danh sach ung dung
  curl -fsSL -o "$ICONDIR/zalo-desktop.png" \
    "https://raw.githubusercontent.com/$REPO/main/icon.png" 2>/dev/null || true
  cat > "$APPDIR/zalo-desktop.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Zalo Desktop
Comment=Zalo cho Linux
Exec=$BINDIR/zalo-desktop %U
Icon=zalo-desktop
Terminal=false
Categories=Network;InstantMessaging;
StartupWMClass=Zalo
EOF
  have update-desktop-database && update-desktop-database "$APPDIR" 2>/dev/null || true
  c_ok "Xong. Chay bang:  zalo-desktop   (hoac tim 'Zalo Desktop' trong menu)"
  case ":$PATH:" in
    *":$BINDIR:"*) ;;
    *) c_warn "Luu y: $BINDIR chua nam trong PATH. Them vao ~/.bashrc:"
       echo "         export PATH=\"\$PATH:$BINDIR\"" ;;
  esac
}

# ---------------------------------------------------------------------- Snap
install_snap() {
  have snap || die "chua co snapd. Fedora: sudo dnf install snapd && sudo ln -s /var/lib/snapd/snap /snap"
  say "Cai tu Snap Store (kenh edge)"
  run_tty sudo snap install --edge "$SNAPNAME"
  c_ok "Xong. Chay bang:  $SNAPNAME"
}

say "Se cai Zalo Desktop $tag bang phuong an: $METHOD"
confirm
case "$METHOD" in
  flatpak)  install_flatpak ;;
  appimage) install_appimage ;;
  snap)     install_snap ;;
esac

cat <<EOF

Du an cong dong, KHONG lien ket voi VNG/Zalo.
Ma nguon: https://github.com/$REPO
Go cai dat: curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash -s -- --uninstall
EOF
