# Zalo Desktop chạy native trên Linux (Flatpak)

Ghép **app.asar chính thức của Zalo (bản macOS)** với **phần native Linux** rồi
đóng gói Flatpak. Không phải bản mô phỏng, không dùng Wine — vẫn là mã Zalo gốc,
chỉ thay những mảnh mà Zalo chưa phát hành cho Linux.

App-id: `io.github.zalolinux.Zalo` · Electron 22.3.27 · runtime `org.freedesktop.Platform//25.08`

---

## Dựng

```bash
./build.sh
```

Dựng lại từ `stage/` đã có (nhanh). Dựng từ đầu — repo **không chứa binary**, tải nguồn trước:

```bash
./fetch-sources.sh
```

Script tự lấy bản `.dmg` macOS mới nhất (theo chuyển hướng của `zalo.me/download/zalo-pc`),
Electron 22.3.27 linux-x64, snap `zalo-linux`, và chuẩn bị `jxlbin/` từ gói `libjxl-tools`.
Rồi:

```bash
ZALO_DMG=sources/ZaloSetup-universal-26.8.10.dmg \
ZALO_SNAP=sources/zalo-linux.snap \
ELECTRON_ZIP=sources/electron-v22.3.27-linux-x64.zip \
./build.sh --from-source
```

Chỉ kiểm tra bản vá, không dựng:

```bash
./build.sh --check
```

## Vì sao phải tự ghép

Zalo **không phát hành native module Linux** ở bất kỳ bản chính thức nào. Wine
cũng thất bại: Chromium trong Wine không dò được trạng thái mạng
(`WSALookupServiceBegin failed`) nên tưởng máy offline và kẹt ở màn splash.

Phải dùng **bản macOS**, không dùng bản Windows: `sqlite3` trong bản Windows chỉ
có binary `win32-ia32`.

Mượn từ snap `zalo-linux` (tác giả nnluc073) **chỉ phần Linux**: hai binary
`db-cross-v4` + `sqlite3`, `bootstrap.js` (shim Linux ~30 hàm, trong đó có cầu
nối `$zFeatures.zwalker.*`), và thư mục `qt-call-cap-linux` (engine gọi thoại).
Toàn bộ `pc-dist/` giữ nguyên bản chính thức.

## Các bản vá (`patches/apply-patches.py`)

Đều **bắt buộc**, đều idempotent, và dùng regex thay vì offset cố định vì tên
biến rút gọn và hash tên file đổi theo từng bản Zalo.

| | Nội dung | Mất thì hỏng gì |
|---|---|---|
| **P1** | `bootstrap.js`: ép `frame:true` cho cửa sổ Linux, ẩn thanh menu | Cửa sổ không có nút thu nhỏ/phóng to/đóng |
| **P2** | `isEnable()` của `cross_setting` → `return true` | Nút "Đồng bộ tin nhắn" bấm không phản ứng |
| **P3** | `return!!X.load_media.enable` → `return!0` | Không nạp media |
| **P4** | Ép `load_media = {enable:1, optimize_mode:1}` sau khi hợp nhất cấu hình máy chủ | **Ảnh/File/Link trong "Thông tin hội thoại" rỗng hoàn toàn** |
| **P5** | Chép `linux-native/*/index-linux.js` (zwalker, file-utilities, zfile, zjxl) | Tính dung lượng sai, **"Quản lý dữ liệu → Tin nhắn media" quay vòng mãi**, ảnh `.jxl` không mở được |
| **P6** | Ép `file.enable_cloud = 1` sau khi hợp nhất cấu hình máy chủ | **Không khôi phục được ảnh/file cũ từ zCloud** (CDN chỉ giữ 14 ngày) |
| **P7** | Ép `never_expire_11 = never_expire_group = 1` (khối `image` và `file`) | App tự kết luận ảnh cũ hơn 7 ngày ở chat 1-1/nhóm là "không còn tồn tại" và **không thử tải** |
| **P8** | `getClientType()` trả `24` (Windows) thay vì `25` (Linux) | **Không đăng ký được E2EE → không nhận được khoá zCloud → toàn bộ ảnh/file cũ không xem được.** Đọc phần đánh đổi bên dưới |

### Vì sao P8 tồn tại — và đánh đổi

Máy chủ Zalo **không phục vụ đăng ký E2EE cho client type 25 (Linux)**. Hậu quả dây chuyền, đo được từng bước:

```
không đăng ký Signal → không nhận được khoá riêng zCloud
  → pcloudKey rỗng → checkUpgraded() = false
    → updateExtMediaInfo() thoát ngay → cloudInfo = null trên toàn bộ mục
      → không xin được link tải → ảnh/file cũ không xem được
```

Đo thực tế trên một tài khoản có **54.784 mục zCloud trải từ 2019**: `cloudInfo` khác null = **0**,
`verified` khác null = **0**. Tỉ lệ 0/54.784 không thể là mất dữ liệu — luôn là một công tắc.

Đổi `25 → 24`: ngay lần khởi động đầu tiên, `E2ee.db` sinh bản ghi `e2ee_registration` và
`e2ee_metadata` (trước đó cả hai đều 0 dòng), và ảnh cũ xem lại được.

**Đánh đổi:** máy sẽ hiện là thiết bị **Windows** trong danh sách đăng nhập của tài khoản.
Đây là bản vá **duy nhất** trong bộ này không thuộc dạng "bật lại giá trị mặc định của chính
Zalo" — nó khai báo sai nền tảng với máy chủ. Muốn lùi: đổi `24` về `25` rồi dựng lại, không
mất dữ liệu.

Yên tâm ở một điểm: mọi nhánh xử lý **cục bộ** (registry, chữ cái ổ đĩa, đường dẫn, updater)
đều rẽ theo `process.platform`, **không** theo client type — nên đổi số này không làm app cư
xử như đang chạy trên Windows.

### Vì sao P4 tồn tại

Máy chủ Zalo trả về `load_media = {enable:0, optimize_mode:0}` cho client này
(mặc định trong chính bundle của Zalo là `1`). Trong repository media,
`getMediasOfConv` đặt **toàn bộ** truy vấn bên trong

```js
if (load_media.optimize_mode && (n = await ...))
```

và **không có nhánh `else`** — cờ tắt thì hàm trả `[]` ngay lập tức (0 ms) mà
không hề chạm cơ sở dữ liệu. P4 khôi phục lại đúng giá trị mặc định của Zalo.

Cùng họ lỗi với P2 (`cross_setting.enable`) và P3.

### Vì sao P6 tồn tại

CDN `zdn.vn` chỉ giữ file media **14 ngày** (đã đo: ranh giới 200/404 rơi đúng
mốc hôm nay trừ 14). Quá hạn thì phải khôi phục từ **zCloud**. Cổng quyết định
app có coi media là "có bản sao trên cloud" hay không:

```js
K = (file.enable_indicator && file.enable_indicator_ver === 1) || cloud_send2me.enable
W = K && file.enable_cloud && file.enable_cloud_ver === 1
```

Máy chủ trả `enable_cloud = 0` (mặc định trong bundle là `true`) → `W = false`
→ không còn đường lấy ảnh cũ về.

**Bẫy**: máy chủ nhét `enable_cloud` vào khối `settings.features.**file_indicator**`
chứ không phải `settings.features.file` (khối `file` thường không được gửi).
Cả hai đều merge vào cùng `config.file`, nên bản vá phải bọc **cả hai** chỗ.
Và lưu ý `setttings` trong mã Zalo viết **ba chữ t** — không phải lỗi gõ ở đây.

### Hợp đồng ẩn của `file-utilities` (thuộc P5)

```js
getDirectorySizeAsync(dir, { deep: { maxDepth: 3 } })
//  -> { totalSize, fileCount, tree: [ { relativePath, totalSize, fileCount }, ... ] }
```

Trường **`tree` là bắt buộc** khi có `deep`. Bên gọi làm thẳng `a.tree.length`
không kiểm tra `null`, nên thiếu nó thì ném `TypeError`, tác vụ quét từng hội
thoại không bao giờ giải quyết (`resolve`) và màn hình quay vòng vĩnh viễn.

`relativePath` là đường dẫn tương đối so với thư mục truyền vào; bên tiêu thụ
(`calculateConvDataForResMntV2`) chỉ ánh xạ tên cấp 1:
`video → videosSize`, `picture → imagesSize`, `file`/`fileNoise → filesSize`,
`folder → foldersSize`, `fileThumb`/`voice`/`richThumb → othersSize`.

Bố cục thư mục thật (path structure V2):
`ZaloData/media/<uid>/ZaloDownloads/resource/<convId>/{video,picture,file,Cache,…}`

Hội thoại chỉ có `Cache`/`fileThumb` sẽ bị loại khỏi danh sách vì
`validateCalculateResult` đòi `videosSize + imagesSize + filesSize ≥ 1`.

## Hai kho media — đừng nhầm

| | Đường dẫn | Index | Tình trạng |
|---|---|---|---|
| Kho **mới** (đang dùng) | `Database/_production/<uid>/Media.db` | `convId_sendDttm_cliMsgId` | đầy dữ liệu |
| Kho **cũ** (bỏ) | `Database/_production/<uid>/Core/Index.db` | `userId_sendDttm_msgId` | rỗng hoàn toàn |

Cờ chọn kho là `change_media_db.should_use_new_media_db_flow` (= 1, đúng, không
cần vá). Nếu debug mà thấy bảng `image` rỗng thì hãy kiểm tra xem đang mở đúng
file chưa.

Chuỗi gọi khi mở tab Ảnh/Video:
`panel → _getChatMedia → getChatMedia → getMediaFromConversation → getValidMediasOfConv → repo.getMediasOfConv`

## Khi bản vá trượt

`apply-patches.py` thoát khác 0 và in rõ bản vá nào không neo được — nghĩa là
Zalo đã đổi cấu trúc bundle. Cách dò lại:

```bash
flatpak run io.github.zalolinux.Zalo --remote-debugging-port=9222
```

rồi dùng Chrome DevTools Protocol. Mẹo lấy `__webpack_require__` từ ngoài:

```js
window.webpackJsonp.push([['probe'], {probe: (m,e,r) => { window.__wr = r }}, [['probe']]])
```

Sau đó `window.__wr('NDmK').default` là toàn bộ cấu hình đã hợp nhất — so nó với
giá trị mặc định trong bundle để tìm cờ nào bị máy chủ tắt.

## Chạy

```bash
flatpak run io.github.zalolinux.Zalo
```

Launcher tự `unset WAYLAND_DISPLAY` để ép X11 — Electron 22 trên Wayland không vẽ
được cửa sổ. Dữ liệu phiên nằm ở
`~/.var/app/io.github.zalolinux.Zalo/config/ZaloData`.

Nếu app thoát ngay không log: `rm -f ~/.config/ZaloData/Singleton*`.

Gọi thoại/video dùng engine của tác giả snap, bật bằng `ZALO_ENABLE_LINUX_CALL=1`
— **chưa kiểm thử**.

## Hiệu năng — đã đo, không đoán

| hạng mục | trước | sau | ghi chú |
|---|---|---|---|
| `zjxl.jxlToJpeg` (ảnh 1280×881) | 95,8 ms | **43,0 ms** | bỏ file tạm, chạy qua ống stdin→stdout |
| `zjxl.getJxlInfo` | 0 ms | 0 ms | đọc header thuần JS, không gọi tiến trình |
| Kết xuất | raster CPU | **raster GPU** | `--ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy` |

Vì sao **không** viết addon N-API cho JXL: đo tách bạch cho thấy `djxl` giải mã
thuần mất ~42 ms và fork chỉ 3 ms. Sau khi bỏ file tạm, shim đã ở mức 43 ms —
tức đã chạm sàn. Addon C++ chỉ tiết kiệm thêm ~3 ms nhưng kéo cả toolchain C++
vào Flatpak. Không đáng.

Vì sao **không** viết `zimage`/libvips: app có nhà máy resizer nhiều backend
(`LIBJXL_WASM`, `WEB_WORKER`, `MAIN`, libvips) và cấu hình gốc của Zalo là
`enable_libvips_macos: false` — bản macOS cũng không dùng libvips mà đi đường
OffscreenCanvas thuần Chromium. Linux vào đúng nhánh đó, không thiếu gì.

Vì sao **không** viết `mp4thumb`: app có sẵn đường lui no-op
(`generateThumbnail → Promise.resolve("")`), và ảnh đại diện video vốn lấy từ
`thumbUrl` của máy chủ. Viết nó phải gánh thêm ffmpeg cho lợi ích rất mỏng.

## Còn dang dở

- `zimage` (libvips) và `mp4thumb` (ffmpeg) chưa có bản thay thế native.
- Màn "Quản lý dữ liệu → Tin nhắn media" chưa ra danh sách hội thoại.
