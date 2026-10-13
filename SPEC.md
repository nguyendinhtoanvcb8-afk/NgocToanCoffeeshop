# SPEC – Công cụ quản lý quán CoffeeShop

Trạng thái: **bản đặc tả, chưa có code**. Nguồn: `data/Quyet_dinh_chu_quan.md`, các file CSV trong `data/`, `Kich_ban_kiem_thu.md` và buổi phỏng vấn ngày 2026-10-13.

## 1. Mục tiêu và phạm vi

Tool web nhỏ cho một quán: gọi món, xử lý đơn, quản lý thực đơn, xem báo cáo doanh thu. Có sẵn dữ liệu bán hàng 01/07–30/09/2026 để có báo cáo ngay khi chạy.

**Ngoài phạm vi:** kho/nguyên liệu, nhân viên và chấm công, khuyến mãi/giảm giá/VAT, phí giao hàng, địa chỉ khách, in hóa đơn, theo dõi bàn trống/đang dùng, sửa nội dung đơn sau khi tạo.

## 2. Công nghệ và triển khai

| Mục | Quyết định |
|---|---|
| Nền tảng | Python Flask + SQLite (một file DB) |
| Nạp dữ liệu | Script khởi tạo đọc CSV, **không sửa file CSV gốc** |
| Local | Chạy một lệnh; bật hiển thị ảnh và mô tả |
| Render (Internet) | Gắn persistent disk để giữ file SQLite; không nạp mô tả và đường dẫn ảnh; không đưa thư mục `images/` lên |
| Cờ cấu hình | `SHOW_MEDIA` (bật ở local, tắt ở Render) |
| Biến môi trường | `APP_PASSWORD` (mật khẩu đăng nhập, quyền quản lý), `CASHIER_PASSWORD` (tùy chọn, thêm vai trò thu ngân), `SECRET_KEY`, `RENDER` (do Render đặt) |
| Chạy trên máy | Không đặt `APP_PASSWORD` thì không có đăng nhập, toàn quyền |
| Chạy trên Render | Thiếu `APP_PASSWORD` hoặc `SECRET_KEY` thì dừng với lỗi rõ ràng; `SHOW_MEDIA` luôn tắt; gói Free không có disk nên DB nạp lại từ CSV mỗi lần khởi động |

Script nạp phải chạy lặp lại được: chỉ nạp khi DB trống, không nhân đôi dữ liệu.

## 3. Người dùng và quyền

Đăng nhập bằng mật khẩu; mật khẩu quyết định vai trò (`APP_PASSWORD` = quản lý, `CASHIER_PASSWORD` nếu có = thu ngân). Chưa đăng nhập thì mọi trang và API đều chuyển về trang đăng nhập. **Ngoại lệ:** chạy trên máy mà không đặt `APP_PASSWORD` thì không có đăng nhập và mọi người dùng có quyền quản lý.

| Chức năng | Thu ngân | Quản lý |
|---|---|---|
| Gọi món (tạo đơn) | Có | Có |
| Xem đơn, tra cứu lịch sử | Có | Có |
| Chuyển trạng thái đơn, hủy đơn Mới/Đang pha chế | Có | Có |
| Tổng quan (báo cáo) | Có | Có |
| Xem thực đơn | Có | Có |
| Thêm, sửa, tạm ngưng/bật bán lại, xóa món | Không | Có |

Quyền kiểm tra ở **server**, không chỉ ẩn nút.

## 4. Các trang

### 4.1 Đăng nhập
Một ô mật khẩu. Sai thì báo lỗi, không nói rõ là mật khẩu của vai trò nào. Có nút đăng xuất.

### 4.2 Gọi món
- Chọn loại phục vụ: **Tại quán**, **Mang đi**, **Giao hàng**.
- Tại quán: bắt buộc chọn **số bàn 1–12**. Loại khác: không có số bàn.
- Danh sách món nhóm theo danh mục, **chỉ món `dang_ban = 1`**. Thêm món vào giỏ, chỉnh số lượng, bỏ món.
- Mỗi dòng món có **ghi chú** tự do (tối đa 100 ký tự) và nút gợi ý: *ít đá, ít ngọt, không đá, thêm sữa*.
- Chọn phương thức thanh toán: **Tiền mặt, Chuyển khoản QR, Ví điện tử**.
- Hiển thị tổng tiền tạm tính theo giá hiện tại. Bấm "Tạo đơn" → đơn trạng thái **Mới**.
- Loại Giao hàng không thu thêm thông tin nào.
- Local có ảnh và mô tả; nếu `SHOW_MEDIA` tắt thì chỉ hiện tên và giá.

### 4.3 Đơn hàng
- Mặc định hiện **đơn hôm nay**; đơn Mới và Đang pha chế xếp lên đầu.
- Bộ lọc: khoảng ngày, trạng thái, loại phục vụ, tìm theo mã đơn. Phân trang 50 đơn/trang.
- Bấm đơn để xem chi tiết: từng món, số lượng, đơn giá tại thời điểm bán, ghi chú, thành tiền, tổng.
- Nút chuyển trạng thái (xem 6.3). Nút Hủy đòi nhập lý do.
- **Không có nút xóa đơn.**

### 4.4 Thực đơn
- Bảng món: tên, danh mục, giá, trạng thái đang bán/tạm ngưng. Lọc theo danh mục. Local hiện thêm ảnh và mô tả; mô tả trống hiện "Mô tả đang được cập nhật."
- Quản lý: thêm món, sửa tên/giá/danh mục, tạm ngưng hoặc bật bán lại, xóa (theo 6.5).
- Thu ngân chỉ xem.

### 4.5 Tổng quan
Chọn tháng (mặc định tháng hiện tại; dữ liệu có sẵn 2026-07 đến 2026-09). Hiển thị:
1. Số đơn, doanh thu, giá trị trung bình mỗi đơn, số đơn hủy.
2. Top 5 món.
3. Doanh thu theo danh mục.
4. Doanh thu theo ngày trong tháng.
5. Doanh thu theo giờ trong ngày.
6. Doanh thu **hôm nay** (cập nhật khi đơn chuyển sang Hoàn thành).

Định nghĩa số liệu ở mục 6.6.

## 5. Mô hình dữ liệu

Tiền là số nguyên đồng (VND), không dùng số thực.

### category
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | INTEGER PK | 1 Cà phê, 2 Freeze, 3 Trà, 4 Bánh ngọt |
| name | TEXT | |
| description | TEXT | Chỉ nạp khi `SHOW_MEDIA` bật; có thể trống |

### product
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | INTEGER PK | Giữ id gốc (chi tiết đơn tham chiếu `mon_id`) |
| name | TEXT | Duy nhất, không phân biệt hoa thường, bắt buộc |
| price | INTEGER | > 0, bội số 1.000 |
| category_id | INTEGER FK | Bắt buộc |
| description | TEXT | Chỉ nạp khi `SHOW_MEDIA` bật; sau khi bỏ thẻ HTML |
| image | TEXT | Chỉ nạp khi `SHOW_MEDIA` bật |
| dang_ban | INTEGER | 1 = đang bán, 0 = tạm ngưng; mặc định 1 |

Bỏ cột `published_date`.

### orders
| Cột | Kiểu | Ghi chú |
|---|---|---|
| ma_don | TEXT PK | `CS-yymmdd-NNN`, NNN đếm lại từ 001 mỗi ngày |
| thoi_gian | TEXT | `YYYY-MM-DD HH:MM:SS`, giờ địa phương quán |
| loai_phuc_vu | TEXT | `Tại quán` / `Mang đi` / `Giao hàng` |
| so_ban | INTEGER NULL | 1–12 khi Tại quán; NULL với loại khác |
| trang_thai | TEXT | `Mới` / `Đang pha chế` / `Hoàn thành` / `Đã hủy` |
| thanh_toan | TEXT | `Tiền mặt` / `Chuyển khoản QR` / `Ví điện tử` |
| tong_tien | INTEGER | Bằng tổng `thanh_tien` các dòng; chốt lúc tạo đơn |
| ly_do_huy | TEXT NULL | Bắt buộc khi `Đã hủy` |
| thoi_gian_hoan_thanh | TEXT NULL | Ghi lúc chuyển sang Hoàn thành |

Cột `ghi_chu` của file `lich_su_don_hang.csv` luôn trống nên không dùng; ghi chú nằm ở dòng chi tiết.

### order_item
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | INTEGER PK | |
| ma_don | TEXT FK | |
| mon_id | INTEGER FK | |
| so_luong | INTEGER | 1–99 |
| don_gia | INTEGER | **Giá tại thời điểm bán**, sao chép từ `product.price` |
| thanh_tien | INTEGER | `so_luong × don_gia` |
| ghi_chu | TEXT NULL | ≤ 100 ký tự |

### Quan hệ
category 1–n product; orders 1–n order_item; product 1–n order_item.

### Làm sạch khi nạp menu (theo quyết định chủ quán)
| # | Xử lý |
|---|---|
| 1 | id 1: bỏ thẻ HTML, giữ văn bản |
| 2 | Món không có mô tả: để trống, giao diện hiện "Mô tả đang được cập nhật." |
| 3 | id 18 đổi tên thành **Phindi Cassia (L)** |
| 4 | id 22 giá 72.000 đ; id 35 giá 129.000 đ |
| 5 | Bỏ `published_date` |
| 6 | Tên viết hoa → dạng "Phin Đen Đá" (viết hoa chữ cái đầu mỗi từ) |
| 7 | Tên thương hiệu khác trong mô tả/tên món → "CoffeeShop"; id 43 đổi tên **Bánh Sô-Cô-La** |
| 8 | Thêm `dang_ban`, mặc định 1 |

Ghi chú: quy tắc 6 áp cho cả tên có ký hiệu như "Cookies & Cream", "Trà Sen Vàng (Củ Năng)"; cần viết thử để tránh lỗi kiểu "Sô-Cô-La" khác "Sô-cô-la".

## 6. Quy tắc nghiệp vụ

### 6.1 Tạo đơn
1. Đơn phải có ít nhất 1 dòng món.
2. Tại quán: `so_ban` là số nguyên 1–12, bắt buộc. Loại khác: `so_ban` luôn NULL (nếu client gửi lên thì bỏ qua).
3. Nhiều đơn cùng bàn được phép; không theo dõi bàn trống.
4. `so_luong` là số nguyên 1–99. 0, âm, thập phân, chữ → báo lỗi, **không tạo đơn**.
5. Chỉ chọn được món `dang_ban = 1`. Server từ chối món tạm ngưng hoặc không tồn tại.
6. `ghi_chu` ≤ 100 ký tự.
7. `don_gia` lấy từ `product.price` **tại thời điểm tạo đơn**; `tong_tien` tính ở server, không tin giá/tổng do client gửi.
8. Phương thức thanh toán bắt buộc, chọn từ 3 giá trị.
9. Đơn mới có trạng thái `Mới`. Tạo đơn và các dòng chi tiết trong **một giao dịch** (lỗi thì không để lại đơn dở).
10. Tổng tiền = tổng thành tiền các dòng, không phí, không giảm giá, không VAT.

### 6.2 Mã đơn
`CS-` + `yymmdd` của ngày tạo + `-` + số thứ tự 3 chữ số trong ngày (001…). Không trùng; tạo trong giao dịch để hai thu ngân bấm cùng lúc không trùng mã.

### 6.3 Vòng đời đơn
```
Mới ──► Đang pha chế ──► Hoàn thành   (cuối)
 │            │
 └────────────┴────────► Đã hủy       (cuối, bắt buộc có lý do)
```
- Chỉ tiến lên, không lùi. `Mới → Hoàn thành` trực tiếp **không** cho phép (phải qua Đang pha chế).
- `Hoàn thành` và `Đã hủy` là trạng thái cuối: không đổi, không sửa.
- Thu ngân và quản lý đều hủy được đơn Mới hoặc Đang pha chế.
- Không có chức năng xóa đơn. Gọi API xóa/đổi một đơn Hoàn thành → từ chối (lỗi, không thay đổi dữ liệu).
- Đơn đã tạo không sửa món, số lượng, bàn, thanh toán. Nhập sai thì hủy và tạo đơn mới.

### 6.4 Giá
- Sửa giá món chỉ ảnh hưởng đơn tạo **sau đó**; đơn cũ giữ nguyên `don_gia` và `tong_tien`.
- Giá nguyên dương, bội số 1.000 (đồng bộ với việc chủ quán làm tròn 72.090 và 128.790).

### 6.5 Thực đơn
- Chỉ quản lý thêm, sửa, tạm ngưng/bật bán, xóa.
- Tên bắt buộc, không trùng (không phân biệt hoa thường); danh mục bắt buộc và phải tồn tại.
- Món mới mặc định `dang_ban = 1` và xuất hiện ngay ở trang Gọi món.
- Tạm ngưng: món biến khỏi Gọi món nhưng vẫn hiện trong báo cáo và đơn cũ.
- **Xóa:** chỉ khi món chưa từng nằm trong dòng chi tiết đơn nào (kể cả đơn Đã hủy). Ngược lại từ chối và gợi ý "Tạm ngưng".
- Đơn đang Mới/Đang pha chế chứa món vừa bị tạm ngưng vẫn xử lý bình thường.

### 6.6 Định nghĩa số liệu báo cáo
Theo tháng chọn (`thoi_gian` thuộc tháng đó):
- **Số đơn**: số đơn Hoàn thành. Hiển thị riêng **số đơn hủy**.
- **Doanh thu**: tổng `tong_tien` của đơn **Hoàn thành**; đơn Đã hủy, Mới, Đang pha chế không tính.
- **Tỷ lệ hủy**: đơn Đã hủy ÷ tổng số đơn trong tháng (mọi trạng thái), hiển thị phần trăm một chữ số thập phân.
- **Giá trị trung bình/đơn**: doanh thu ÷ số đơn Hoàn thành, làm tròn đến đồng.
- **Top 5 món**: tổng `so_luong` trong đơn Hoàn thành, giảm dần; hòa thì món doanh thu cao hơn đứng trước, vẫn hòa thì theo tên. Hiển thị số ly và doanh thu món.
- **Doanh thu theo danh mục**: tổng `thanh_tien` các dòng của đơn Hoàn thành theo danh mục hiện tại của món.
- **Theo ngày / theo giờ**: gộp doanh thu đơn Hoàn thành theo ngày (1…cuối tháng, ngày không có đơn = 0) và theo giờ 0–23 của `thoi_gian`.
- **Doanh thu hôm nay**: đơn Hoàn thành trong ngày hiện tại (tính theo `thoi_gian` tạo đơn).

### 6.7 Dữ liệu lịch sử
Nạp 4.549 đơn và 7.409 dòng từ `lich_su_don_hang.csv` và `lich_su_chi_tiet_don.csv` (01/07–30/09/2026; 4.385 Hoàn thành, 164 Đã hủy). Kiểm tra khi nạp: mọi đơn có ≥ 1 dòng, `tong_tien` bằng tổng dòng, `mon_id` tồn tại, mã đơn không trùng, đơn Tại quán có bàn còn loại khác không. Dữ liệu đã được kiểm: không có sai lệch. Đơn Đã hủy lịch sử không có `ly_do_huy` → để NULL (ràng buộc bắt buộc chỉ áp cho đơn tạo từ UI).

### 6.8 Bảo mật
- Mật khẩu đọc từ biến môi trường, không ghi trong code hay DB. Trên Render, thiếu `APP_PASSWORD` hoặc `SECRET_KEY` → tool không khởi động (gunicorn dừng, mã thoát 3).
- Phiên đăng nhập bằng cookie ký bằng `SECRET_KEY`.
- Truy vấn dùng tham số hóa; thoát HTML khi hiển thị tên món, ghi chú, lý do hủy.
- Bản deploy không chứa mô tả, ảnh, thư mục `images/`.

## 7. Kịch bản kiểm tra

Giữ nguyên 10 kịch bản trong `Kich_ban_kiem_thu.md` (mục A) và bổ sung các kịch bản từ buổi phỏng vấn (mục B).

### A. Kịch bản gốc
| # | Thao tác | Kết quả mong đợi |
|---|---|---|
| 1 | Mở Tổng quan, chọn tháng 2026-09 | Xem bảng số liệu mẫu bên dưới |
| 2 | Gọi món: Tại quán, bàn 5, 2 Phin Sữa Đá (ít đá) + 1 Bánh Tiramisu, chuyển khoản | Đơn mới, tổng **93.000 đ**, trạng thái Mới |
| 3 | Gọi món Tại quán nhưng bỏ trống số bàn | Báo lỗi, không tạo đơn |
| 4 | Nhập số lượng -2 hoặc 0 | Báo lỗi |
| 5 | Chuyển đơn ở bước 2: Đang pha chế → Hoàn thành | Doanh thu hôm nay tăng 93.000 đ |
| 6 | Thử đổi đơn đã Hoàn thành về Mới; thử xóa đơn đã Hoàn thành | Bị từ chối |
| 7 | Thực đơn: tạm ngưng "Set Trà Cao Cấp" | Món không còn trong danh sách gọi món |
| 8 | Sửa giá Phin Đen Đá 29.000 → 32.000 | Đơn cũ giữ nguyên tổng tiền; đơn mới dùng giá mới |
| 9 | Thêm món mới "Cà phê muối" 39.000 đ | Xuất hiện ở trang gọi món |
| 10 | Tắt chương trình, chạy lại | Dữ liệu vẫn còn |

**Đáp án mẫu cho #1 (tháng 2026-09, tính từ CSV):**

| Chỉ số | Giá trị |
|---|---|
| Tổng đơn trong tháng | 1.451 (1.392 Hoàn thành, 59 Đã hủy) |
| Doanh thu | **134.399.000 đ** |
| Doanh thu theo danh mục | Cà phê 72.219.000 · Trà 30.842.000 · Freeze 22.660.000 · Bánh ngọt 8.678.000 |
| Top 5 (số ly) | 1. Phin Sữa Đá 210 · 2. Bạc Xỉu Đá 194 · 3. Phin Đen Đá 169 · 4. Cappuccino 108 · 5. Trà Thạch Vải 108 |

Cappuccino và Trà Thạch Vải cùng 108 ly; Cappuccino đứng trước nhờ doanh thu 7.020.000 > 4.860.000 (quy tắc hòa ở 6.6). Tổng doanh thu bốn danh mục = 134.399.000, khớp doanh thu.

Tháng khác để đối chiếu: 2026-07 có 1.514 đơn (1.456 Hoàn thành, 58 hủy), doanh thu 130.785.000 đ; 2026-08 có 1.584 đơn (1.537 Hoàn thành, 47 hủy), doanh thu 144.605.000 đ.

### B. Kịch bản bổ sung
| # | Thao tác | Kết quả mong đợi |
|---|---|---|
| 11 | Đăng nhập sai mật khẩu; mở thẳng URL trang khi chưa đăng nhập | Báo lỗi / chuyển về đăng nhập |
| 12 | Đăng nhập bằng mật khẩu thu ngân, mở trang Thực đơn và bấm sửa giá (hoặc gọi API sửa) | Không có nút sửa; API trả lỗi quyền, giá không đổi |
| 13 | Thu ngân mở Tổng quan | Xem được, số liệu giống quản lý |
| 14 | Quản lý đăng nhập, tạo món có giá 39.500 | Báo lỗi (không phải bội số 1.000) |
| 15 | Tạo món trùng tên "phin sữa đá" | Báo lỗi trùng tên |
| 16 | Gọi món Mang đi có số bàn gửi kèm | Đơn tạo thành công, `so_ban` rỗng |
| 17 | Tại quán, bàn 13 hoặc bàn 0 | Báo lỗi |
| 18 | Số lượng 100, 1.5, "abc" | Báo lỗi; 99 được chấp nhận |
| 19 | Ghi chú 101 ký tự | Báo lỗi; bấm nút gợi ý "ít đá" điền đúng ghi chú |
| 20 | Gửi đơn không có món | Báo lỗi, không tạo đơn |
| 21 | Chuyển đơn Mới thẳng sang Hoàn thành | Từ chối (phải qua Đang pha chế) |
| 22 | Hủy đơn Mới có lý do; hủy đơn không điền lý do | Cái đầu thành Đã hủy; cái sau báo lỗi |
| 23 | Hủy đơn đã Hoàn thành; chuyển đơn Đã hủy sang trạng thái khác | Từ chối |
| 24 | Đơn Đã hủy | Không tính vào doanh thu, top món, doanh thu theo danh mục; có tính vào số đơn hủy |
| 25 | Tạo 2 đơn cùng bàn 5 | Cả hai tạo được, mã đơn khác nhau |
| 26 | Tạo đơn thứ 2 trong cùng ngày | Mã tăng đúng (…-001, …-002); sang ngày mới đếm lại từ 001 |
| 27 | Xóa món đã có đơn (ví dụ Phin Sữa Đá) | Bị chặn, gợi ý Tạm ngưng |
| 28 | Tạo món mới "Test", xóa ngay | Xóa được |
| 29 | Tạm ngưng món khi đơn Mới chứa món đó đang mở | Đơn vẫn chuyển trạng thái bình thường; món vẫn hiện trong báo cáo cũ |
| 30 | Bật bán lại món đã tạm ngưng | Món quay lại trang Gọi món |
| 31 | Sau #8, mở chi tiết đơn cũ và đơn mới | Đơn cũ `don_gia` 29.000, đơn mới 32.000 |
| 32 | Tên món sau khi nạp | Có "Phindi Cassia (L)" (id 18), "Bánh Sô-Cô-La" (id 43); không còn "HIGHLANDS" hay tên thương hiệu khác; id 22 giá 72.000, id 35 giá 129.000; id 1 không còn thẻ HTML |
| 33 | Local, món mô tả trống | Hiện "Mô tả đang được cập nhật." |
| 34 | Chạy với `SHOW_MEDIA` tắt (giả lập bản Render) | DB không có mô tả, đường dẫn ảnh; giao diện chỉ tên và giá |
| 35 | Nạp dữ liệu lần 2 khi DB đã có | Không nhân đôi: vẫn 4.549 đơn, 7.409 dòng |
| 36 | Đếm sau khi nạp | 4.549 đơn (4.385 Hoàn thành, 164 Đã hủy); 7.409 dòng; tổng đơn mọi tháng = tổng dòng |
| 37 | Trang Đơn hàng: lọc 2026-09-15, lọc Đã hủy, tìm mã `CS-260915-001` | Kết quả đúng; trang 50 đơn; đơn Mới/Đang pha chế của hôm nay đứng đầu |
| 38 | Tổng quan tháng không có đơn (ví dụ 2026-06) | Hiện 0 đồng, 0 đơn, không lỗi, không chia cho 0 |
| 39 | Nhập tên món/ghi chú có `<script>` | Hiển thị như văn bản, không chạy mã |
| 40 | Khởi động với `RENDER` đặt mà thiếu `APP_PASSWORD` hoặc `SECRET_KEY` | Tool không chạy, báo rõ biến nào thiếu |
| 41 | Chạy trên máy, không đặt `APP_PASSWORD` | Vào thẳng Gọi món, không có trang đăng nhập, sửa được thực đơn |

## 8. Câu hỏi còn mở (chưa ảnh hưởng đến việc bắt đầu)
- Múi giờ quán: mặc định Asia/Ho_Chi_Minh; Render chạy UTC nên phải đặt múi giờ rõ ràng khi ghi `thoi_gian`.
- Nếu Render dùng gói không có persistent disk, dữ liệu sẽ mất khi khởi động lại; cần quyết định trước khi deploy.
- Quản lý có cần thêm/sửa danh mục không (hiện cố định 4 danh mục)?
