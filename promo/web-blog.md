# Bài quảng cáo Web / Blog

> Giọng: cộng đồng mã nguồn mở, có chiều sâu kỹ thuật. Ảnh bìa: `branding/social-preview.png`.

---

## Zalo Desktop cho Linux: app native, mã nguồn mở, cài một dòng lệnh

Nếu bạn dùng Linux, bạn biết cảm giác này: mọi thứ đều có, trừ Zalo. Bao năm nay lựa chọn chỉ quanh quẩn ở mấy cách chắp vá — mở Zalo Web trong trình duyệt, gói lại bằng Electron sơ sài, hay chạy bản Windows qua Wine rồi cầu nguyện nó đừng treo.

**Zalo Desktop for Linux** ra đời để chấm dứt chuyện đó: app Zalo **gốc**, được đóng gói và vá để chạy đúng như một ứng dụng Linux thật sự — và **toàn bộ mã nguồn công khai** để bất kỳ ai cũng kiểm chứng, tự build, và đóng góp.

### Vì sao khác với các bản "Zalo Linux" khác?

Đây không phải bản web nhét vào khung cửa sổ. Nhân là app Zalo desktop thật, ghép thêm phần nền tảng mà Zalo không phát hành cho Linux, cộng **13 bản vá** để mọi tính năng chạy trơn:

| Tính năng | Trạng thái |
|---|---|
| Tin nhắn mã hoá đầu-cuối (E2EE) | ✅ |
| Đồng bộ zCloud, đồng bộ tin nhắn nhiều thiết bị | ✅ |
| Xem lại ảnh/video/file cũ (tới tận 2019) | ✅ |
| Thu nhỏ xuống khay hệ thống (system tray) | ✅ |
| Đóng cửa sổ / thoát đúng chuẩn Linux | ✅ |
| Thumbnail video, cửa sổ xem media có nút đóng | ✅ |
| Khung cửa sổ, ẩn thanh menu, icon gọn gàng | ✅ |

Thứ duy nhất chưa có là **gọi thoại/video** — engine gọi của Zalo chỉ có bản biên dịch cho macOS/Windows, chưa có cách nào đưa lên Linux mà không viết lại từ đầu. Mọi thứ còn lại: chạy mượt.

### Cài đặt

**Flatpak** (khuyên dùng, mọi distro):
```bash
flatpak install ac.d3v.ZaloLinux
```

**AppImage** (tải về chạy luôn, không cần cài):
```bash
chmod +x ZaloDesktop-*.AppImage
./ZaloDesktop-*.AppImage
```

**Snap** (Ubuntu):
```bash
sudo snap install zalo-desktop
```

### Minh bạch vì mã nguồn mở

Điểm mình tự hào nhất không phải danh sách tính năng, mà là **mọi bản vá đều công khai và giải thích rõ**. Bạn thấy chính xác đã đổi gì, vì sao đổi — từ chuyện bật lại các mặc định mà máy chủ tắt riêng cho Linux, tới việc khai báo client type để mở khoá E2EE. Không có hộp đen. Bạn tự build được từ mã nguồn, tự kiểm tra được từng dòng.

Dự án theo giấy phép **MIT**. Mọi issue, pull request, góp ý đều được chào đón — đây là dự án của cộng đồng Linux Việt Nam, và nó tốt lên nhờ chính người dùng.

👉 **Mã nguồn:** [github.com/Crust92/ZaloDesktopLinux](https://github.com/Crust92/ZaloDesktopLinux)

Nếu thấy hữu ích, một ⭐ trên GitHub và một lần chia sẻ là cách ủng hộ thiết thực nhất.

---

*Zalo Desktop for Linux là dự án cộng đồng phi lợi nhuận, **không liên kết với VNG hay Zalo**. "Zalo" là thương hiệu của VNG. Dự án chỉ đóng gói lại phần mềm để dùng trên Linux, dành cho mục đích cá nhân; bạn tự chịu trách nhiệm khi sử dụng.*
