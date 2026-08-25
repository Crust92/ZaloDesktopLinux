#!/usr/bin/env python3
"""
Áp toàn bộ bản vá Linux lên cây app Zalo (bản macOS đã ghép native module Linux).

Dung:  ./apply-patches.py <duong-dan-app> [--profile=compat|default|full] [--check]

       --profile=compat   chi phan CAN DE CHAY (gan nhat voi 'dong goi nguyen trang')
       --profile=default  + bat lai mac dinh cua chinh Zalo bi may chu tat (mac dinh)
       --profile=full     + khai client type Windows de mo khoa E2EE/zCloud

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

APP = None
for _a in sys.argv[1:]:
    if not _a.startswith('-'):
        APP = os.path.abspath(os.path.expanduser(_a))
        break
CHECK_ONLY = '--check' in sys.argv

# ---------------------------------------------------------------- ho so ban va
# Ba muc, chon bang --profile=<ten>. Mac dinh `default`.
#
#   compat   Chi nhung gi CAN DE CHAY DUOC tren Linux. Day la muc gan nhat voi
#            "dong goi nguyen trang": khong doi hanh vi nao cua app, chi bu vao
#            phan nen tang ma Zalo khong phat hanh cho Linux.
#            Danh cho ban dua len store.
#            Danh doi: Anh/File/Link trong "Thong tin hoi thoai" RONG, nut
#            "Dong bo tin nhan" khong phan ung, khong xem duoc media cu.
#
#   default  compat + cac ban va BAT LAI GIA TRI MAC DINH CUA CHINH ZALO ma may
#            chu tat rieng cho client Linux (P2,P3,P4,P6,P7). Khong khai sai
#            danh tinh thiet bi.
#
#   full     default + P8 (khai client type 24/Windows). Mo khoa E2EE + zCloud,
#            nhung khai sai nen tang voi may chu. Xem README muc "Vi sao P8".
PROFILES = {
    'compat':  ['P1', 'P5'],
    'default': ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P9', 'P10', 'P11', 'P12', 'P13', 'P14', 'P15', 'P16', 'P17'],
    'full':    ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8', 'P9', 'P10', 'P11', 'P12', 'P13', 'P14', 'P15', 'P16', 'P17'],
}
PROFILE = 'default'
for _a in sys.argv[1:]:
    if _a.startswith('--profile='):
        PROFILE = _a.split('=', 1)[1]
if PROFILE not in PROFILES:
    sys.exit('Loi: --profile phai la mot trong: %s' % ', '.join(PROFILES))
ACTIVE = set(PROFILES[PROFILE])


def enabled(tag):
    return tag in ACTIVE

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
    # Ban 26.8.10 minify thanh `;return!e&&t}` — KHONG co dau cach sau `return`.
    # Dung `\s*` de chiu ca hai dang, va luon xuat lai `return true` (co dau cach)
    # cho khoi sinh `returntrue`.
    rx = re.compile(
        r'(isEnable\(\)\{const [\w$]+=this\.config\.get\("cross_setting\.offFeature"\),'
        r'[\w$]+=this\.config\.get\("cross_setting\.enable"\);return)\s*(![\w$]+&&[\w$]+)(\})'
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
        ns, n = rx.subn(lambda m: m.group(1) + ' true' + m.group(3), s)
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


# ------------------------------------------------------ P9 nut goi thoai/video
def p9_enable_call():
    """Hien nut goi thoai va goi video.

    Mac dinh trong bundle la tat:  enableCall:!1, enableVideoCall:!1
    Sau do app doc tu may chu:
        try{ let e = 1 == t.settings.chat.enable_call;       X.enableCall = e } catch(e){}
        try{ let e = 1 == t.settings.chat.enable_video_call; X.enableVideoCall = e } catch(e){}

    May chu KHONG gui khoi `settings.chat` cho client nay -> truy cap
    `.enable_call` cua undefined nem loi -> try/catch nuot im -> hai co giu
    nguyen mac dinh false -> nut goi khong bao gio hien.

    Va o day chi mo NUT. Goi co ket noi duoc hay khong lai la chuyen khac:
    `zcall` la module macOS chua ai port; engine thay the `qt-call-cap-linux`
    cua tac gia snap co trong goi nhung CHUA KIEM THU (bat bang
    ZALO_ENABLE_LINUX_CALL=1).
    """
    applied = already = 0
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        if 'enableCall' not in s:
            continue
        orig = s
        # 1) lat gia tri mac dinh trong object cau hinh
        s = s.replace('enableCall:!1,', 'enableCall:!0,')
        s = s.replace('enableVideoCall:!1,', 'enableVideoCall:!0,')
        # 2) ep ket qua gan tu may chu (phong khi sau nay co settings.chat voi gia tri 0)
        s = re.sub(r'(\.enableCall=)\w+(\}catch)', r'\g<1>!0\g<2>', s)
        s = re.sub(r'(\.enableVideoCall=)\w+(\}catch)', r'\g<1>!0\g<2>', s)
        if s != orig:
            if not CHECK_ONLY:
                open(f, 'w', encoding='utf8').write(s)
            applied += 1
        elif 'enableCall:!0,' in s:
            already += 1
    if applied:
        record('P9 hien nut goi thoai/video', True, False, '%d file' % applied)
    elif already:
        record('P9 hien nut goi thoai/video', False, True, 'da co san')
    else:
        record('P9 hien nut goi thoai/video', False, False, 'KHONG khop')


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


# ------------------------------------------------------ P11 icon tray (png thay ico)
def p11_tray_icon():
    """Tray tao bang nativeImage.createFromPath('favicon.ico'). Linux Electron KHONG
    ve duoc .ico da do phan giai -> o vuong den. Thay bang favicon.png."""
    pc = os.path.join(APP, 'pc-dist')
    mainjs = os.path.join(APP, 'main-dist', 'main.js')
    src_png = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            '..', 'linux-native', 'tray', 'favicon.png'))
    if not os.path.isfile(mainjs):
        record('P11 icon tray png', False, False, 'thieu main.js'); return
    s = open(mainjs, encoding='utf8', errors='surrogateescape').read()
    png_dst = os.path.join(pc, 'favicon.png')
    have_png = os.path.isfile(png_dst)
    patched = '"favicon.png"' in s
    if patched and have_png:
        record('P11 icon tray png', False, True, 'da khop'); return
    if '"favicon.ico"' not in s and not patched:
        record('P11 icon tray png', False, False, 'KHONG khop main.js'); return
    if not CHECK_ONLY:
        if not have_png:
            # uu tien nguon linux-native, khong co thi lay favicon-128 san trong pc-dist
            import shutil as _sh
            if os.path.isfile(src_png):
                _sh.copyfile(src_png, png_dst)
            elif os.path.isfile(os.path.join(pc, 'favicon-128x128.png')):
                _sh.copyfile(os.path.join(pc, 'favicon-128x128.png'), png_dst)
        if not patched:
            open(mainjs, 'w', encoding='utf8', errors='surrogateescape').write(
                s.replace('"favicon.ico"', '"favicon.png"', 1))
    record('P11 icon tray png', True, False, 'favicon.png')


# ------------------------------------------------------ P12 thoat that tren Linux
def p12_linux_quit():
    """requestQuitApp() tren Linux gui IPC hoi renderer xac nhan thoat roi CHO —
    hop thoai do khong hien tren Linux nen app khong bao gio thoat, va co
    appIsRequestQuiting ket lam moi lan Thoat sau bi tu choi. Vá: Linux thoat thang."""
    mainjs = os.path.join(APP, 'main-dist', 'main.js')
    if not os.path.isfile(mainjs):
        record('P12 thoat that Linux', False, False, 'thieu main.js'); return
    s = open(mainjs, encoding='utf8', errors='surrogateescape').read()
    if '"linux"===process.platform||this.currentPage===' in s:
        record('P12 thoat that Linux', False, True, 'da khop'); return
    rx = re.compile(r'(this\.currentPage===\w+\.APP_PAGE\.LOGIN\|\|this\.mainWindow\.webContents&&this\.mainWindow\.webContents\.isCrashed\(\)\|\|!\w+\.\w+\.isMainAppStarted\(\))')
    ns, n = rx.subn(lambda m: '"linux"===process.platform||' + m.group(1), s, count=1)
    if n == 0:
        record('P12 thoat that Linux', False, False, 'KHONG khop requestQuitApp'); return
    if not CHECK_ONLY:
        open(mainjs, 'w', encoding='utf8', errors='surrogateescape').write(ns)
    record('P12 thoat that Linux', True, False, 'requestQuitApp -> quit thang')


# ------------------------------------------------------ P13 cua so xem anh/video co nut X
def p13_viewer_frame():
    """Cua so "Zalo Photo" (xem anh/video) dat titleBarStyle:"hidden" -> tren Linux
    (Electron 22) an ca thanh tieu de lan nut dieu khien => KHONG co nut X. Ngoai ra
    mot bien the dat frame theo getClientType()!==WIN, ma P8 gia client=Windows nen
    frame=false. Va: tren Linux ep frame:true + bo titleBarStyle cho 3 cua so viewer."""
    mainjs = os.path.join(APP, 'main-dist', 'main.js')
    if not os.path.isfile(mainjs):
        record('P13 viewer co nut X', False, False, 'thieu main.js'); return
    s = open(mainjs, encoding='utf8', errors='surrogateescape').read()
    if 'titleBarStyle:"linux"===process.platform?"default":"hidden"' in s:
        record('P13 viewer co nut X', False, True, 'da khop'); return
    a = s.count('frame:h()!==p')
    b = s.count('frame:Object(l.getClientType)()!==l.WIN_CLIENT_TYPE')
    c = s.count('titleBarStyle:"hidden",show:!1,resizable:!0,backgroundColor:"#1f1f1f"')
    if not (a and c):
        record('P13 viewer co nut X', False, False, f'KHONG khop (hp={a} ct={b} tb={c})'); return
    s = s.replace('frame:h()!==p', 'frame:"darwin"!==process.platform')
    s = s.replace('frame:Object(l.getClientType)()!==l.WIN_CLIENT_TYPE',
                  'frame:"linux"===process.platform||Object(l.getClientType)()!==l.WIN_CLIENT_TYPE')
    s = s.replace('titleBarStyle:"hidden",show:!1,resizable:!0,backgroundColor:"#1f1f1f"',
                  'titleBarStyle:"linux"===process.platform?"default":"hidden",show:!1,resizable:!0,backgroundColor:"#1f1f1f"')
    if not CHECK_ONLY:
        open(mainjs, 'w', encoding='utf8', errors='surrogateescape').write(s)
    record('P13 viewer co nut X', True, False, f'frame×{a+b}, titlebar×{c}')


# ------------------------------------------------ P14 db-cross-v4 binding cho Linux
def p14_dbcross_binding():
    """binding.js cua db-cross-v4 chi biet darwin va Windows:

        if (process.platform === 'darwin') { ...darwin/electron/<arch>... }
        else { ...prebuilt/window/electron_x86_64... }

    Linux roi vao nhanh else -> doi file Windows KHONG co, du goi da co ban Linux
    o prebuilt/linux/electron/x64 (lay tu snap zalo-linux).

    Hau qua day chuyen (da do bang CDP tren may that):
        preload-shared-worker.js -> nativelibs/index.js -> binding.js NEM LOI
        -> shared-worker khong dang ky duoc TaskHandler nao
        -> "Task type is not supported" cho GENERATE_IK_KEY_PAIR / GET_BACKUP_STATUS
        -> LOAD_IK_FAILED -> popup "Dong bo khong thanh cong".
    Tuc la TAT CA tinh nang dong bo tin nhan / sao luu / khoi phuc deu hong.
    """
    p = os.path.join(APP, 'native', 'nativelibs', 'db-cross-v4', 'dist', 'binding.js')
    if not os.path.isfile(p):
        record('P14 db-cross-v4 binding Linux', False, False, 'thieu binding.js'); return
    s = open(p, encoding='utf8').read()
    if "process.platform === 'linux'" in s:
        record('P14 db-cross-v4 binding Linux', False, True, 'da khop'); return
    anchor = "if (process.platform === 'darwin') {"
    if anchor not in s:
        record('P14 db-cross-v4 binding Linux', False, False, 'KHONG khop binding.js'); return
    new = ("if (process.platform === 'linux') {\n"
           "    addon = require('../prebuilt/linux/electron/x64/db-cross-v4-native.node');\n"
           "}\n"
           "else if (process.platform === 'darwin') {")
    if not CHECK_ONLY:
        open(p, 'w', encoding='utf8').write(s.replace(anchor, new, 1))
    record('P14 db-cross-v4 binding Linux', True, False, 'them nhanh linux')


# ------------------------------------------- P15 noi shim Linux vao loader NAPI-RS
def p15_wire_shims():
    """P5 chi CHEP index-linux.js vao module, KHONG he noi vao — khong file nao
    trong app require no. Loader NAPI-RS goc (index.js) tren Linux tim
    ./<mod>.linux-x64-gnu.node, khong thay thi require goi npm cung ten, roi

        if (!nativeBinding) { if (loadError) throw loadError; throw new Error(...) }

    => require('./zwalker/index.js') NEM LOI. Ham nativelibs.zwalker() vi vay
    khong bao gio tra ve duoc gi, moi thong ke thu muc = 0 => man "Quan ly du
    lieu" bao 0 B va ket "Dang tinh toan..." (do tren may that: ZaloData 2,1 GB).

    Va: dat mot nhanh o DAU index.js de Linux dung thang shim JS.
    (`return` o cap module la hop le trong CommonJS.)
    """
    head = ("// Linux: dung shim JS thay .node (Zalo khong phat hanh ban Linux).\n"
            "if (process.platform === 'linux') {\n"
            "  module.exports = require('./index-linux.js');\n"
            "  return;\n"
            "}\n")
    wired, missing = [], []
    for m in ('zwalker', 'file-utilities', 'zfile', 'zjxl'):
        idx = os.path.join(APP, 'native', 'nativelibs', m, 'index.js')
        shim = os.path.join(APP, 'native', 'nativelibs', m, 'index-linux.js')
        if not os.path.isfile(idx) or not os.path.isfile(shim):
            missing.append(m)
            continue
        s = open(idx, encoding='utf8', errors='surrogateescape').read()
        if "require('./index-linux.js')" in s:
            continue
        if not CHECK_ONLY:
            open(idx, 'w', encoding='utf8', errors='surrogateescape').write(head + s)
        wired.append(m)
    if missing:
        record('P15 noi shim Linux vao loader', False, False, 'THIEU: ' + ','.join(missing))
    elif wired:
        record('P15 noi shim Linux vao loader', True, False, 'noi: ' + ','.join(wired))
    else:
        record('P15 noi shim Linux vao loader', False, True, 'da khop')


# ------------------------------------------- P16 bam thong bao phai MO cua so
def p16_noti_click_show():
    """Bam vao thong bao he thong khong mo duoc app.

    Da do bang CDP tren may that: su kien click TOI DUOC renderer (bat duoc ca
    'show' lan 'click'). Loi nam o buoc sau — handler chi goi:

        m.onclick = () => { ...; a(); window.focus(); this._closeNotifyV2(i) }

    `window.focus()` la API cua trang web: no chi lam viec khi cua so DANG hien.
    Tren Linux cua so bi thu xuong khay (close-to-tray goi win.hide()) nen khong
    the focus mot cua so dang an — phai win.show() truoc. Tren Wayland con them
    co che chong cuop focus khien focus() don thuan khong keo cua so len.

    Va: goi $zwindow.show() truoc roi moi window.focus().
    """
    old = 'window.focus(),this._closeNotifyV2(i)'
    new = ('(()=>{try{$zwindow&&$zwindow.show&&$zwindow.show()}catch(_){}})(),'
           'window.focus(),this._closeNotifyV2(i)')
    applied = already = 0
    files = []
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        if old not in s:
            continue
        if new in s:
            already += 1
            continue
        if not CHECK_ONLY:
            open(f, 'w', encoding='utf8').write(s.replace(old, new, 1))
        applied += 1
        files.append(rel(f))
    if applied:
        record('P16 bam thong bao mo cua so', True, False, ', '.join(files))
    elif already:
        record('P16 bam thong bao mo cua so', False, True, 'da khop')
    else:
        record('P16 bam thong bao mo cua so', False, False, 'KHONG khop')


# ------------------------------------------- P17 dan anh vao khung chat
def p17_paste_image():
    """Dan anh vao khung chat khong gui duoc (khong hien gi).

    Da truy bang CDP tren may that:
      - su kien paste TOI DUOC app, clipboardData co File image/png dung dung luong
      - nhung khong ham nao trong luong anh (_sendExcel/_uploadDragPhoto/
        handleDragPhoto/addImageToPreview) duoc goi
      - goi TRUC TIEP chatController._uploadDragPhoto(file) thi CHAY (DOM +24 phan tu)

    Nguyen nhan: nhanh xu ly anh goi ham z(), ma z() chi goi uploadPhoto BEN TRONG
    .then() cua `$zscreencap.getClipboard(...)`:

        z=(t,n,a)=>{G||(G=!0,$zscreencap.getClipboard(uid).then(...uploadPhoto...))}

    Do bang CDP: $zscreencap.getClipboard() KHONG BAO GIO resolve tren Linux (cho
    12s van treo). Vi vay uploadPhoto khong bao gio duoc goi. Te hon: co khoa G
    duoc bat truoc khi cho, va chi duoc go trong .then() — nen dan lan dau treo la
    MOI lan dan sau deu bi bo qua im lang.

    Va: goi thang uploadPhoto, giu nguyen duong cu lam du phong.
    """
    # Hai nhanh anh, CA HAI deu cho $zscreencap.getClipboard():
    #   z(t,n,a)   — dan ANH THO (chup man hinh)
    #   W(t,n="")  — dan FILE ANH (chep tu trinh quan ly tep)
    # Nguoi dung bao: dan file .jpg khong nhan, file khac thi nhan — dung vi file
    # thuong di duong uploadFileForMac (khong qua zscreencap), con anh thi qua W.
    subs = [
        ('z=(t,n,a)=>{G||(G=!0,$zscreencap.getClipboard(',
         'z=(t,n,a)=>{try{if(e.uploadPhoto&&a){a.name||(a.name="clipboard.png");'
         'e.uploadPhoto([a],e.currentUserId);return}}catch(_){}'
         'G||(G=!0,$zscreencap.getClipboard('),
        ('W=(t,n="")=>{G||(G=!0,$zscreencap.getClipboard(',
         'W=(t,n="")=>{try{if(e.uploadPhoto&&Array.isArray(t)&&t.length>0){'
         'e.uploadPhoto(t,e.currentUserId);return}}catch(_){}'
         'G||(G=!0,$zscreencap.getClipboard('),
    ]
    applied = already = 0
    files = []
    for f in bundles():
        s = open(f, encoding='utf8', errors='ignore').read()
        orig = s
        hit = 0
        for old, new in subs:
            if new in s:
                hit += 1
                continue
            if old in s:
                s = s.replace(old, new, 1)
        if s != orig:
            if not CHECK_ONLY:
                open(f, 'w', encoding='utf8').write(s)
            applied += 1
            files.append(rel(f))
        elif hit:
            already += 1
    if applied:
        record('P17 dan anh vao khung chat', True, False, '%d file' % applied)
    elif already:
        record('P17 dan anh vao khung chat', False, True, 'da khop')
    else:
        record('P17 dan anh vao khung chat', False, False, 'KHONG khop')


# ------------------------------------------------------ P10 thumbnail video (ffmpeg)
def p10_mp4thumb_ffmpeg():
    """mp4thumb khong co ban Linux -> throw 'not available'. Thay bang backend
    ffmpeg (giu nguyen hop dong), va noi vao index.js o nhanh else."""
    src_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'linux-native')
    src = os.path.normpath(os.path.join(src_root, 'mp4thumb', 'linux-ffmpeg.js'))
    moddir = os.path.join(APP, 'native', 'nativelibs', 'mp4thumb')
    idx = os.path.join(moddir, 'index.js')
    if not os.path.isfile(src) or not os.path.isfile(idx):
        record('P10 thumbnail video ffmpeg', False, False, 'THIEU nguon/dich')
        return
    data = open(src, encoding='utf8').read()
    dst = os.path.join(moddir, 'linux-ffmpeg.js')
    s = open(idx, encoding='utf8').read()
    # Ban 26.8.10 bo `createUnsupportedModule()`; cau truc gio la
    #     if(process.platform === 'win32') { ... }
    #     else { if(process.arch === 'arm64'){...} else {...} }
    # Neo vao cuoi nhanh win32 va chen mot nhanh `else if linux` ngay sau — ben
    # hon chuoi cung vi chiu duoc thay doi khoang trang/dinh dang.
    rx = re.compile(
        r"(require\(`\./win32/\$\{process\.arch\}/mp4thumb\.node`\);\s*\n\s*\})"
        r"(\s*\n\s*else\s*\{)"
    )
    already = os.path.isfile(dst) and open(dst, encoding='utf8', errors='ignore').read() == data
    patched = "require('./linux-ffmpeg.js')" in s
    if already and patched:
        record('P10 thumbnail video ffmpeg', False, True, 'da khop')
        return
    if not patched and not rx.search(s):
        record('P10 thumbnail video ffmpeg', False, False, 'KHONG khop index.js')
        return
    if not CHECK_ONLY:
        open(dst, 'w', encoding='utf8').write(data)
        if not patched:
            ins = ("\\1\n        else if(process.platform === 'linux') {\n"
                   "            thumbModule = require('./linux-ffmpeg.js');\n"
                   "        }\\2")
            open(idx, 'w', encoding='utf8').write(rx.sub(ins, s, count=1))
    record('P10 thumbnail video ffmpeg', True, False, 'ffmpeg backend')


print('Ap ban va len: %s%s' % (APP, '  [CHI KIEM TRA]' if CHECK_ONLY else ''))
print('Ho so: %s  (%s)' % (PROFILE, ', '.join(sorted(ACTIVE))))
for _tag, _fn in (('P1', p1_bootstrap), ('P2', p2_sync_isenable), ('P3', p3_load_media_enable),
                  ('P4', p4_load_media_config), ('P6', p6_file_enable_cloud),
                  ('P7', p7_never_expire), ('P8', p8_client_type), ('P9', p9_enable_call),
                  ('P10', p10_mp4thumb_ffmpeg), ('P11', p11_tray_icon), ('P12', p12_linux_quit), ('P13', p13_viewer_frame), ('P14', p14_dbcross_binding), ('P5', p5_linux_shims), ('P15', p15_wire_shims), ('P16', p16_noti_click_show), ('P17', p17_paste_image)):
    if enabled(_tag):
        _fn()
    else:
        print('  [BO  ] %-46s khong thuoc ho so %s' % (_tag, PROFILE))

failed = [r[0] for r in results if not r[1] and not r[2]]
print()
if failed:
    print('THAT BAI %d/%d ban va:' % (len(failed), len(results)))
    for f in failed:
        print('   - ' + f)
    print('Nhieu kha nang Zalo doi cau truc bundle. Xem README.md muc "Khi ban va truot".')
    sys.exit(1)
print('OK — tat ca %d ban va da co hieu luc.' % len(results))
