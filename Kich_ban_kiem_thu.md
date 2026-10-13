# Kịch bản kiểm thử bằng tay – tool CoffeeShop

| # | Thao tác | Kết quả mong đợi |
|---|---|---|
| 1 | Mở Tổng quan, chọn tháng 2026-09 | Có số đơn, doanh thu, top 5 món, doanh thu theo danh mục (đối chiếu đáp án) |
| 2 | Gọi món: Tại quán, bàn 5, 2 Phin Sữa Đá (ít đá) + 1 Bánh Tiramisu, chuyển khoản | Đơn mới, tổng **93.000 đ**, trạng thái Mới |
| 3 | Gọi món Tại quán nhưng bỏ trống số bàn | Báo lỗi, không tạo đơn |
| 4 | Nhập số lượng -2 hoặc 0 | Báo lỗi |
| 5 | Chuyển đơn ở bước 2: Đang pha chế → Hoàn thành | Doanh thu hôm nay tăng 93.000 đ |
| 6 | Thử đổi đơn đã Hoàn thành về Mới; thử xóa đơn đã Hoàn thành | Bị từ chối |
| 7 | Thực đơn: tạm ngưng "Set Trà Cao Cấp" | Món không còn trong danh sách gọi món |
| 8 | Sửa giá Phin Đen Đá 29.000 → 32.000 | Đơn cũ giữ nguyên tổng tiền; đơn mới dùng giá mới |
| 9 | Thêm món mới "Cà phê muối" 39.000 đ | Xuất hiện ở trang gọi món |
| 10 | Tắt chương trình, chạy lại | Dữ liệu vẫn còn |
