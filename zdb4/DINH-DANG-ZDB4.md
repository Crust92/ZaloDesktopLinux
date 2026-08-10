# Định dạng sao lưu ZDB4.0 của Zalo — dựng lại từ native module

Nguồn: `native/nativelibs/db-cross-v4/prebuilt/linux/electron/x64/db-cross-v4-native.node`
(có sẵn bản Linux — không phải đoán, mà đọc trực tiếp symbol + chuỗi + luồng gọi JS).

## Toàn cảnh chuỗi biến đổi

    file .zl.zip  ─(AES-256-CBC, KHÔNG padding)─►  khối ZDB4.0
                  ─(kiểm magic "ZDB4.0")─►  header + bảng file
                  ─(LZMA / xz, liblzma)─►  "SQLite format 3\0…"  (DB tin nhắn)

## Tầng mã hoá (đã chắc chắn)

- Thuật toán: **AES-256-CBC**, `EVP_aes_256_cbc` (OpenSSL 3).
- **Không padding**: `EVP_CIPHER_CTX_set_padding(ctx, 0)`; hàm nội bộ tên
  `aes256cbc_decrypt_nopad`. Vì vậy độ dài ciphertext phải chia hết cho 16 —
  đúng với file thật (14.740.822.544 = 921.301.409 × 16).
- **Không có KDF**: không PBKDF2 / HKDF / scrypt / BytesToKey / SHA trong symbol.
  ⇒ Khoá được dùng **thẳng**. Phía JS gọi `privateKey.toUpperCase()` trước khi
  đưa vào, nên khoá là chuỗi **hex 64 ký tự → 32 byte** AES-256.
- IV: không có chuỗi salt/nonce; nhiều khả năng IV = 0 hoặc hằng cố định (đang xác
  minh khi có khoá thật).
- Toàn bộ file là ciphertext, không có header rõ ở đầu (byte đầu đã ngẫu nhiên).
  Magic "ZDB4.0" chỉ xuất hiện **sau khi giải mã**.

## Tầng nén

- `lzma_stream_decoder` + `lzma_code` + `lzma_end` (liblzma / XZ 5.0).
- Chuỗi lỗi: `Failed to init liblzma decoder`, `LZMA decode did not finish cleanly`.

## Hàm N-API xuất ra

- `DecompressAndDecryptDb(info)`        → format 0 (cũ)
- `DecompressAndDecryptDb_V2(info)`     → format 1 (mới, có callback tiến độ)
- `ParseBinNet(info)`                    → không liên quan sao lưu

Chữ ký JS:
    dbUtils().decompressAndDecryptDb_V2(inputPath, outputPath,
                                        privateKey.toUpperCase(), onProgress)
    // trả { result, inner_error, error_message }; result===0 là thành công.

## Mã lỗi quan sát được
    "Invalid ZDB4.0 Magic Header"   — sai khoá, hoặc không phải ZDB4.0
    "Ciphertext length not AES block" — độ dài không bội số 16
    "Truncated file"                — thiếu byte / hỏng
    "file table names"              — hỏng bảng thư mục file bên trong

## KHOÁ lấy ở đâu (điểm quyết định)

Khoá KHÔNG lưu cục bộ trên máy (đã soát `SecureLocalstorage.db` của cả bản cũ lẫn
bản Flatpak — không có `pcloudKey`/`_privateKey`). Với bản sao lưu, Zalo lấy khoá
qua tài khoản/zCloud lúc khôi phục. Hai đường khả thi:

1. **Dùng chính chức năng khôi phục của app** (đáng tin nhất) — app tự lấy khoá,
   tự gọi đúng native module này, giải mã và trộn tin nhắn cũ vào DB sống ⇒ khôi
   phục luôn `cliMsgId` cho media cũ. Cần: đang đăng nhập + đã mở E2EE (P8 đã làm).

2. **Bắt khoá bằng shim** (`zdb4-key-capture.js`): chèn một lớp bọc quanh
   `db-cross-v4` để khi app gọi `DecompressAndDecryptDb_V2`, ghi lại `privateKey`
   + đường dẫn. Có khoá rồi thì `decode-zdb4.js` chạy độc lập, tái lập chính xác
   thuật toán trên mà không cần app.
