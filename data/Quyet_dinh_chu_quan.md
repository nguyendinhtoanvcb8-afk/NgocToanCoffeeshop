# Quyết định của chủ quán về dữ liệu thực đơn (trả lời các câu hỏi ở Bài 6)

Áp dụng khi nạp `product.csv`, `category.csv` vào cơ sở dữ liệu – **không sửa file CSV gốc**, xử lý bằng script.

| # | Vấn đề (Bài 6) | Quyết định |
|---|---|---|
| 1 | Mô tả có thẻ HTML (id 1) | Bỏ thẻ, giữ văn bản |
| 2 | 13 món trống mô tả | Để trống; giao diện hiện "Mô tả đang được cập nhật." |
| 3 | Trùng tên PHINDI CASSIA (id 10: 55.000 đ, id 18: 69.000 đ) | id 18 là ly lớn → đổi tên **PHINDI CASSIA (L)** |
| 4 | Giá lẻ bất thường | id 22: 72.090 → **72.000 đ**; id 35: 128.790 → **129.000 đ** |
| 5 | `published_date` không thống nhất | Bỏ cột này |
| 6 | Tên viết HOA | Lưu dạng "Phin Đen Đá" |
| 7 | Tên thương hiệu khác trong mô tả, tên món | Thay bằng "CoffeeShop"; id 43 đổi tên **BÁNH SÔ-CÔ-LA** |
| 8 | Thêm cột mới | `dang_ban` (1 = đang bán, 0 = tạm ngưng) – món đã có đơn không xóa, chỉ tạm ngưng |

## Khi đưa lên Internet (TH2 – Render)
- **Bỏ cột mô tả và đường dẫn ảnh** khỏi dữ liệu nạp: văn bản, ảnh gốc có bản quyền.
- Tool phải có **mật khẩu đăng nhập** (biến môi trường `APP_PASSWORD`).

## Dữ liệu lịch sử
`lich_su_don_hang.csv` (4549 đơn) và `lich_su_chi_tiet_don.csv` (7409 dòng): đơn bán từ 01/07 đến 30/09/2026 (dữ liệu học tập, giá đã theo quyết định trên). Nạp vào database để có báo cáo ngay khi chạy tool.

## Lưu ý bản quyền
Ảnh món (thư mục `images/` ở Bài 6) và một phần mô tả lấy từ website của một chuỗi cà phê có thật → không đưa lên Internet; bản deploy chỉ giữ tên món, giá.
