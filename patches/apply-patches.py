#!/usr/bin/env python3
"""
Áp toàn bộ bản vá Linux lên cây app Zalo (bản macOS đã ghép native module Linux).

Dùng:  ./apply-patches.py <duong-dan-app>       # vd: ~/zalo-pkg/stage/app
       ./apply-patches.py <duong-dan-app> --check   # chi kiem tra, khong ghi

Moi ban va deu IDEMPOTENT: chay lai nhieu lan van an toan. Neu mot ban va
khong tim thay diem neo (Zalo doi cau truc bundle) thi script BAO LOI va thoat
khac 0 — dung de im lang bo qua, vi moi ban va o day deu la bat buoc.

Ban va dung regex thay vi offset co dinh vi ten bien rut gon va hash ten file
thay doi theo tung ban Zalo.
"""
import os
import re
import sys
import glob

APP = os.path.abspath(os.path.expanduser(sys.argv[1])) if len(sys.argv) > 1 else None
CHECK_ONLY = '--check' in sys.argv

if not APP or not os.path.isdir(APP):
    sys.exit('Loi: can duong dan thu muc app. Vd: ./apply-patches.py ~/zalo-pkg/stage/app')

PC = os.path.join(APP, 'pc-dist')
if not os.path.isdir(PC):
    sys.exit('Loi: khong thay %s — day khong phai cay app Zalo.' % PC)


def bundles():
    return sorted(glob.glob(os.path.join(PC, '*.js')) + glob.glob(os.path.join(PC, 'lazy', '*.js')))


def rel(p):
    return os.path.relpath(p, APP)


results = []


def record(name, applied, already, detail=''):
    results.append((name, applied, already, detail))
    tag = 'VA' if applied else ('SAN' if already else 'HONG')
    print('  [%-4s] %-46s %s' % (tag, name, detail))


# ---------------------------------------------------------------- P1 bootstrap
def p1_bootstrap():
    """Cua so co khung + an thanh menu tren Linux."""
    path = os.path.join(APP, 'bootstrap.js')
    if not os.path.isfile(path):
        record('P1 bootstrap: khung cua so + an menu', False, False, 'KHONG thay bootstrap.js')
        return
    s = open(path, encoding='utf8', errors='ignore').read()
    orig = s
    have_frame = 'ZALO_KEEP_FRAMELESS' in s
    have_menu = 'setMenuBarVisibility' in s

    if not have_menu:
        head = (
            "(function(){\n"
            "  try {\n"
            "    if (process.platform === 'linux') {\n"
            "      const { app, Menu } = require('electron');\n"
            "      const hide = () => { try { Menu.setApplicationMenu(null); } catch(_){} };\n"
            "      hide();\n"
            "      app.on('ready', hide);\n"
            "      app.on('browser-window-created', (_e, w) => {\n"
            "        try { w.setMenuBarVisibility(false); w.setAutoHideMenuBar(true); } catch(_){}\n"
            "      });\n"
            "    }\n"
            "  } catch(_){}\n"
            "})();\n\n"
        )
        s = head + s

    if not have_frame:
        # Chen ngay dau ham dung options cua BrowserWindow.
        rx = re.compile(r'(function patchBrowserWindowOptions\(options, preloadWrapper\) \{\n)')
        ins = (
            "    if (process.platform === 'linux' && options && options.frame === false"
            " && process.env.ZALO_KEEP_FRAMELESS !== '1') {\n"
            "        options = Object.assign({}, options, { frame: true, autoHideMenuBar: true });\n"
            "        delete options.titleBarStyle; delete options.titleBarOverlay;\n"
            "    }\n"
        )
        s2, n = rx.subn(lambda m: m.group(1) + ins, s, count=1)
        if n == 0:
            record('P1 bootstrap: khung cua so + an menu', False, False,
                   'KHONG neo duoc patchBrowserWindowOptions')
            return
        s = s2

    if s == orig:
        record('P1 bootstrap: khung cua so + an menu', False, True, 'da co san')
        return
    if not CHECK_ONLY:
        open(path, 'w', encoding='utf8').write(s)
    record('P1 bootstrap: khung cua so + an menu', True, False, 'bootstrap.js')


# ------------------------------------------------- P2 cross_setting.isEnable
def p2_sync_isenable():
    """Dong bo tin nhan: may chu tra cross_setting.enable=false -> ep true.

    Truoc:  isEnable(){const e=...offFeature,t=...enable;return!e&&t}
    Sau:    isEnable(){const e=...;const t=...;return true}
    """
    rx = re.compile(
        r'(isEnable\(\)\{const [\w$]+=this\.config\.get\("cross_setting\.offFeature"\),'
        r'[\w$]+=this\.config\.get\("cross_setting\.enable"\);return )(![\w$]+&&[\w$]+)(\})'
    )
    applied = already = 0
    files = []
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        if 'cross_setting.offFeature' not in s:
            continue
        if re.search(r'cross_setting\.enable"\);return true\}', s):
            already += 1
            continue
        ns, n = rx.subn(lambda m: m.group(1) + 'true' + m.group(3), s)
        if n:
            if not CHECK_ONLY:
                open(f, 'w', encoding='utf8').write(ns)
            applied += n
            files.append(rel(f))
    if applied:
        record('P2 sync: cross_setting.isEnable -> true', True, False,
               '%d cho (%s)' % (applied, ', '.join(files)))
    elif already:
        record('P2 sync: cross_setting.isEnable -> true', False, True, 'da co san')
    else:
        record('P2 sync: cross_setting.isEnable -> true', False, False, 'KHONG khop')


# ---------------------------------------------- P3 isEnableLoadMedia -> true
def p3_load_media_enable():
    """return!!X.default.load_media.enable  ->  return!0"""
    rx = re.compile(r'return\s*!!([\w$]+)\.default\.load_media\.enable')
    applied = 0
    files = []
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        if 'load_media.enable' not in s:
            continue
        ns, n = rx.subn('return!0', s)
        if n:
            if not CHECK_ONLY:
                open(f, 'w', encoding='utf8').write(ns)
            applied += n
            files.append('%s:%d' % (rel(f), n))
    if applied:
        record('P3 isEnableLoadMedia -> true', True, False, '%d cho' % applied)
    else:
        record('P3 isEnableLoadMedia -> true', False, True,
               'da co san (khong con cho doc truc tiep)')


# ------------------------------------------------- P4 load_media force config
def p4_load_media_config():
    """BAT BUOC cho phan Anh/File/Link trong "Thong tin hoi thoai".

    May chu Zalo tra ve load_media={enable:0,optimize_mode:0} cho client nay.
    Trong repository media, `getMediasOfConv` dat TOAN BO truy van trong
        if (load_media.optimize_mode && (n = await ...))
    va KHONG co nhanh else -> co tat thi ham tra [] ngay lap tuc, khong cham DB.
    Ep lai gia tri mac dinh cua chinh Zalo (ca hai deu = 1 trong bundle goc).
    """
    rx = re.compile(
        r'([\w$]+)\.load_media=Object\(([\w$]+)\.a\)\(Object\(\2\.a\)\(\{\},\1\.load_media\),'
        r'\1\.settings\.features\.load_media\)'
    )
    applied = already = 0
    files = []
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        if 'settings.features.load_media' not in s:
            continue
        if '{enable:1,optimize_mode:1}' in s:
            already += 1
            continue

        def rep(m):
            a, b = m.group(1), m.group(2)
            return ('%s.load_media=Object.assign(Object(%s.a)(Object(%s.a)({},%s.load_media),'
                    '%s.settings.features.load_media),{enable:1,optimize_mode:1})'
                    % (a, b, b, a, a))

        ns, n = rx.subn(rep, s)
        if n:
            if not CHECK_ONLY:
                open(f, 'w', encoding='utf8').write(ns)
            applied += n
            files.append(rel(f))
    if applied:
        record('P4 load_media: ep enable+optimize_mode=1', True, False,
               '%d file' % applied)
    elif already:
        record('P4 load_media: ep enable+optimize_mode=1', False, True, 'da co san')
    else:
        record('P4 load_media: ep enable+optimize_mode=1', False, False, 'KHONG khop')


# ------------------------------------------------- P6 file.enable_cloud
def p6_file_enable_cloud():
    """Media cu (qua han 14 ngay tren CDN) phai lay lai tu zCloud.

    May chu tra ve `file.enable_cloud = 0` cho client nay (mac dinh trong bundle
    la `true`). Selector quyet dinh "file co duoc luu tren cloud khong" la
        W = (file.enable_indicator && file.enable_indicator_ver===1
             || cloud_send2me.enable) && file.enable_cloud && file.enable_cloud_ver===1
    Co tat -> W=false -> app khong coi media la co ban sao tren cloud, nen khi URL
    CDN het han (404) thi khong con duong nao lay anh cu ve.
    """
    # May chu nhet `enable_cloud:0` vao khoi `file_indicator`, KHONG phai `file`
    # (khoi `file` thuong khong duoc gui). Ca hai deu merge vao cung `config.file`
    # nen phai boc ca hai. 'setttings' 3 chu t la loi chinh ta trong ma Zalo.
    rx = re.compile(
        r'([\w$]+)\.default\.file=Object\(([\w$]+)\.a\)\(Object\(\2\.a\)\(\{\},\1\.default\.file\),'
        r'([\w$]+)\.setttings\.features\.(file_indicator|file)\)'
    )
    applied = already = 0
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        if 'setttings.features.file' not in s:
            continue

        def rep(m):
            a, b, d, key = m.group(1), m.group(2), m.group(3), m.group(4)
            return ('%s.default.file=Object.assign(Object(%s.a)(Object(%s.a)({},%s.default.file),'
                    '%s.setttings.features.%s),{enable_cloud:1,enable_cloud_ver:1})'
                    % (a, b, b, a, d, key))

        # Cho da va, bieu thuc goc khong con khop -> chay lai an toan.
        ns, n = rx.subn(rep, s)
        if not n and '{enable_cloud:1,enable_cloud_ver:1}' in s:
            already += 1
            continue
        if n:
            if not CHECK_ONLY:
                open(f, 'w', encoding='utf8').write(ns)
            applied += n
    if applied:
        record('P6 file.enable_cloud = 1 (khoi phuc zCloud)', True, False, '%d file' % applied)
    elif already:
        record('P6 file.enable_cloud = 1 (khoi phuc zCloud)', False, True, 'da co san')
    else:
        record('P6 file.enable_cloud = 1 (khoi phuc zCloud)', False, False, 'KHONG khop')


# ------------------------------------------------- P7 never_expire 1-1 + nhom
def p7_never_expire():
    """App tu ket luan anh/file cu la "da mat" nen khong them thu tai ve.

    Cong thuc het han (module bUXd, ap cho ca `image` va `file`):
        het_han = !never_expire_<loai> && cu_hon(min_shelf_life_<loai> ngay)
    Mac dinh cua Zalo: never_expire_send2me=1 (My Cloud vinh vien),
    con 1-1 va nhom = 0 voi min_shelf_life = 7 ngay.

    Day KHONG phai co may chu tat rieng cho Linux — mac dinh trong bundle giong
    het gia tri luc chay. Vi vay may Windows xem duoc anh cu la nho file DA nam
    san tren dia may do, chu khong phai tai moi.

    Ep never_expire=1 cho 1-1 va nhom -> app se THU tai/khoi phuc thay vi bao
    "khong con ton tai". Neu may chu that su khong con file thi anh do van hong,
    nhung khong te hon truoc.
    """
    rx = re.compile(r'never_expire_11:0,never_expire_group:0,never_expire_send2me:([01])')
    applied = already = 0
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        if 'never_expire_send2me' not in s:
            continue
        ns, n = rx.subn(
            lambda m: 'never_expire_11:1,never_expire_group:1,never_expire_send2me:' + m.group(1), s)
        if n:
            if not CHECK_ONLY:
                open(f, 'w', encoding='utf8').write(ns)
            applied += n
        elif 'never_expire_11:1,never_expire_group:1' in s:
            already += 1
    if applied:
        record('P7 never_expire cho 1-1 + nhom', True, False, '%d khoi' % applied)
    elif already:
        record('P7 never_expire cho 1-1 + nhom', False, True, 'da co san')
    else:
        record('P7 never_expire cho 1-1 + nhom', False, False, 'KHONG khop')


# ------------------------------------------------------ P8 client type 25 -> 24
def p8_client_type():
    """MO KHOA E2EE + zCloud. Doc ky phan danh doi truoc khi dung.

    `getClientType()` tra ve 23 (macOS) / 24 (Windows) / 25 (Linux) va duoc gui
    len may chu trong URL app (`index.html?type=NN`).

    May chu Zalo **khong phuc vu dang ky E2EE cho client type 25**. Hau qua day
    chuyen, do duoc tung buoc:
        khong dang ky Signal -> khong nhan duoc khoa rieng zCloud
        -> `pcloudKey` rong -> `checkUpgraded()` false
        -> `updateExtMediaInfo` thoat ngay -> `cloudInfo` null tren toan bo muc
        -> khong xin duoc link tai -> anh/file cu khong xem duoc
    Doi 25 -> 24: ngay lan khoi dong dau tien, `E2ee.db` sinh ban ghi
    `e2ee_registration` va `e2ee_metadata` (truoc do la 0), va anh cu xem duoc.

    DANH DOI: may se hien la thiet bi **Windows** trong danh sach dang nhap cua
    tai khoan. Day la ban va DUY NHAT trong bo nay khong thuoc dang "bat lai gia
    tri mac dinh cua chinh Zalo" — no khai bao sai nen tang voi may chu.
    Muon lui lai: doi `24` ve `25` roi dung lai, khong mat du lieu.

    Luu y: cac nhanh xu ly CUC BO (registry, chu cai o dia, duong dan, updater)
    deu re theo `process.platform`, KHONG theo client type — nen doi so nay
    khong lam app chay nhu Windows tren may Linux.
    """
    rx = re.compile(r'(case"LINUX":return )25')
    applied = already = 0
    for name in ('main.js', 'compact-app.js'):
        path = os.path.join(APP, 'main-dist', name)
        if not os.path.isfile(path):
            continue
        s = open(path, encoding='utf8', errors='ignore').read()
        ns, n = rx.subn(lambda m: m.group(1) + '24', s)
        if n:
            if not CHECK_ONLY:
                open(path, 'w', encoding='utf8').write(ns)
            applied += n
        elif 'case"LINUX":return 24' in s:
            already += 1
    if applied:
        record('P8 client type 25 -> 24 (mo khoa E2EE)', True, False, '%d file' % applied)
    elif already:
        record('P8 client type 25 -> 24 (mo khoa E2EE)', False, True, 'da co san')
    else:
        record('P8 client type 25 -> 24 (mo khoa E2EE)', False, False, 'KHONG khop')


# ------------------------------------------------------ P5 shim native Linux
def p5_linux_shims():
    """Chep cac index-linux.js thay the .node ma Zalo khong phat hanh cho Linux."""
    src_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'linux-native')
    src_root = os.path.normpath(src_root)
    mods = ['zwalker', 'file-utilities', 'zfile', 'zjxl']
    copied = missing = []
    copied, missing = [], []
    for m in mods:
        src = os.path.join(src_root, m, 'index-linux.js')
        dst = os.path.join(APP, 'native', 'nativelibs', m, 'index-linux.js')
        if not os.path.isfile(src):
            missing.append(m)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = open(src, encoding='utf8').read()
        if os.path.isfile(dst) and open(dst, encoding='utf8', errors='ignore').read() == data:
            continue
        if not CHECK_ONLY:
            open(dst, 'w', encoding='utf8').write(data)
        copied.append(m)
    if missing:
        record('P5 shim native Linux', False, False, 'THIEU nguon: ' + ','.join(missing))
    elif copied:
        record('P5 shim native Linux', True, False, 'chep: ' + ','.join(copied))
    else:
        record('P5 shim native Linux', False, True, 'da khop')


print('Ap ban va len: %s%s' % (APP, '  [CHI KIEM TRA]' if CHECK_ONLY else ''))
p1_bootstrap()
p2_sync_isenable()
p3_load_media_enable()
p4_load_media_config()
p6_file_enable_cloud()
p7_never_expire()
p8_client_type()
p5_linux_shims()

failed = [r[0] for r in results if not r[1] and not r[2]]
print()
if failed:
    print('THAT BAI %d/%d ban va:' % (len(failed), len(results)))
    for f in failed:
        print('   - ' + f)
    print('Nhieu kha nang Zalo doi cau truc bundle. Xem README.md muc "Khi ban va truot".')
    sys.exit(1)
print('OK — tat ca %d ban va da co hieu luc.' % len(results))
