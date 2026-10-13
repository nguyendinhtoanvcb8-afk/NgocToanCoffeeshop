# CoffeeShop – công cụ quản lý quán

Flask + SQLite, giao diện tiếng Việt, responsive. Đặc tả đầy đủ ở [SPEC.md](SPEC.md); quyết định về dữ liệu thực đơn ở [data/Quyet_dinh_chu_quan.md](data/Quyet_dinh_chu_quan.md).

## Chạy trên máy (127.0.0.1)

Cần Python 3.10 trở lên.

```bash
pip install -r requirements.txt
python run.py
```

Mở <http://127.0.0.1:5000>. **Không đặt `APP_PASSWORD` thì không hỏi mật khẩu** và có toàn quyền (chỉ dùng trên máy cá nhân).

**Lần chạy đầu** tool tự tạo `coffeeshop.db` từ `data/*.csv` (menu đã làm sạch + 4.549 đơn lịch sử 01/07–30/09/2026) nên Tổng quan có số liệu ngay. Các lần sau dùng lại file DB, dữ liệu còn nguyên. Muốn nạp lại từ đầu: tắt tool, xóa `coffeeshop.db`, chạy lại.

Muốn thử đăng nhập trên máy:

```powershell
$env:APP_PASSWORD = "mat-khau-cua-ban"; python run.py      # PowerShell
```
```bash
APP_PASSWORD=mat-khau-cua-ban python run.py               # bash
```

### Biến môi trường

| Biến | Ý nghĩa |
|---|---|
| `APP_PASSWORD` | Mật khẩu đăng nhập (quyền **quản lý**). Bỏ trống: trên máy thì không hỏi mật khẩu; **trên Render thì bắt buộc** |
| `SECRET_KEY` | Khóa ký cookie đăng nhập. **Bắt buộc trên Render.** Trên máy bỏ trống thì tự sinh và lưu ở `coffeeshop.db.secret` để khởi động lại không bị đăng xuất |
| `CASHIER_PASSWORD` | Tùy chọn. Chỉ dùng cùng `APP_PASSWORD`: thêm một mật khẩu thứ hai cho vai trò **thu ngân** (không sửa được thực đơn) |
| `SHOW_MEDIA` | Chỉ trên máy: `1` (mặc định) nạp và hiện ảnh + mô tả món, `0` bỏ hẳn. Trên Render luôn bị ép về tắt |
| `DATABASE_PATH` | Đường dẫn file SQLite (mặc định `coffeeshop.db`) |
| `PORT` | Cổng khi chạy `run.py` (mặc định 5000) |

Không ghi mật khẩu vào code hay commit file `.env` (đã nằm trong `.gitignore`).

## Deploy lên Render (gói Free)

Dự án có sẵn `render.yaml`, `.python-version` (3.13), `.gitignore`, `requirements.txt` (flask, gunicorn) và `app.py` để chạy `gunicorn app:app`.

1. Đưa mã nguồn lên một repo GitHub. Khi kết nối Render, cho phép Render đọc đúng repo này.
2. Trên Render: **New → Blueprint** → chọn repo. Render đọc `render.yaml` và tạo web service `coffeeshop` gói Free.
3. Render hỏi giá trị `APP_PASSWORD` (đã khai báo `sync: false`, không nằm trong repo): nhập mật khẩu của bạn. `SECRET_KEY` được Render tự sinh.
4. Deploy xong, mở địa chỉ `https://<tên>.onrender.com` và đăng nhập bằng `APP_PASSWORD`.

Trên Render (có biến `RENDER`) nếu thiếu `APP_PASSWORD` hoặc `SECRET_KEY`, ứng dụng **dừng ngay** với thông báo `LỖI CẤU HÌNH: … thiếu biến môi trường: …` và deploy báo thất bại. Trên Render mô tả món và đường dẫn ảnh **không bao giờ** được nạp vào database.

### Giới hạn của gói Free (đọc kỹ)

- **Dữ liệu không bền.** Gói Free không có persistent disk. Mỗi lần service khởi động lại hoặc deploy lại, database được tạo lại từ CSV: **đơn mới, giá đã sửa, món mới thêm đều mất**, chỉ còn dữ liệu lịch sử và menu gốc. Phù hợp để chạy thử/trình diễn, không dùng để bán hàng thật. Muốn giữ dữ liệu cần gói trả phí có disk (đặt `DATABASE_PATH` vào disk) hoặc đổi sang PostgreSQL.
- **Tự ngủ** sau một thời gian không có truy cập; lần truy cập đầu tiên sau đó chờ khoảng một phút để khởi động (và nạp lại dữ liệu).
- Chạy một worker `gunicorn` mặc định; không tăng số worker khi dùng SQLite.

### Bản quyền

Ảnh món trong `images/products/` (46 file) và mô tả món lấy từ website của một chuỗi cà phê có thật nên có bản quyền của bên thứ ba. Repo này đang để **Public** và thư mục `images/` **đã được đưa lên** theo quyết định của chủ dự án, nghĩa là ai cũng tải được các ảnh đó; quyết định này trái với `data/Quyet_dinh_chu_quan.md` và rủi ro bản quyền do chủ repo tự chịu. Bản CSV trong repo vẫn để trống cột `image` và `description` (bản đầy đủ chỉ ở máy tác giả, đã đặt `skip-worktree`). Trên Render, tool **không** nạp và **không** phục vụ ảnh/mô tả (`SHOW_MEDIA` bị ép tắt). Muốn gỡ ảnh khỏi repo: chuyển repo sang Private hoặc xóa thư mục `images/`, và nhớ rằng ảnh vẫn còn trong lịch sử git.

## Phân quyền

| | Thu ngân (cần `CASHIER_PASSWORD`) | Quản lý (`APP_PASSWORD`, hoặc chạy máy không mật khẩu) |
|---|---|---|
| Gọi món, xem/xử lý/hủy đơn, Tổng quan, xem Thực đơn | Có | Có |
| Thêm, sửa, tạm ngưng/bán lại, xóa món | Không | Có |

## Quy tắc chính

- **Đơn:** Tại quán bắt buộc số bàn 1–12 (nhiều đơn cùng bàn được); số lượng nguyên 1–99; ghi chú ≤ 100 ký tự. Tổng tiền tính ở server từ giá hiện tại, ghi lại `don_gia` từng dòng.
- **Trạng thái:** Mới → Đang pha chế → Hoàn thành, chỉ tiến lên. Mới hoặc Đang pha chế có thể → Đã hủy (bắt buộc ghi lý do). Hoàn thành và Đã hủy là trạng thái cuối: không sửa, không xóa. Không có chức năng xóa đơn. Tầng DB cũng có trigger chặn sửa/xóa.
- **Thực đơn:** giá nguyên dương, bội số 1.000; tên không trùng (không phân biệt hoa thường). Sửa giá chỉ áp cho đơn mới. Món đã nằm trong bất kỳ đơn nào (kể cả đơn hủy) không xóa được, chỉ tạm ngưng; món tạm ngưng biến khỏi trang Gọi món.
- **Tổng quan (theo tháng):** doanh thu và top 5 chỉ tính đơn Hoàn thành. Top 5 xếp theo số ly, hòa thì theo doanh thu món. Tỷ lệ hủy = đơn hủy ÷ tổng đơn trong tháng. Có thêm doanh thu theo ngày, theo giờ và doanh thu hôm nay.
- **Giờ:** mọi thời gian ghi theo giờ Việt Nam (UTC+7), kể cả khi server chạy giờ UTC.

## Kiểm thử tự động

```bash
python -m unittest discover -s tests -v
```

Không cần đặt biến môi trường (test tự tạo DB tạm, không đụng `coffeeshop.db`). Nội dung: nạp dữ liệu và quyết định chủ quán, cấu hình đăng nhập (máy / Render), phân quyền, tạo đơn và validate, vòng đời đơn, thực đơn, và đáp án Tổng quan các tháng 7–9/2026.

## Cấu trúc

```
app.py                  điểm vào WSGI cho Render: gunicorn app:app
run.py                  chạy trên máy ở 127.0.0.1
render.yaml             khai báo dịch vụ Render (plan free)
.python-version         3.13
coffeeshop/__init__.py  Flask app, đăng nhập, các route
coffeeshop/rules.py     quy tắc nghiệp vụ và báo cáo (không phụ thuộc Flask)
coffeeshop/seed.py      làm sạch menu + nạp CSV (không sửa CSV gốc)
coffeeshop/db.py        lược đồ SQLite, ràng buộc, trigger
templates/, static/     giao diện
tests/test_rules.py     kiểm thử
data/                   CSV gốc và Quyet_dinh_chu_quan.md
images/products/        ảnh món (chỉ dùng trên máy khi SHOW_MEDIA=1; Render không dùng)
```
