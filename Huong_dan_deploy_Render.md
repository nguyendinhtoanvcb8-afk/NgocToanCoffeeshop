# Hướng dẫn deploy tool CoffeeShop lên Render (gói Free)

Thông tin Render kiểm tra ngày 12/10/2026 – giao diện có thể đổi, kiểm tra lại trước buổi học.

## Cần có
- Tài khoản **GitHub** (github.com) và **Render** (render.com – đăng ký bằng tài khoản GitHub cho nhanh). Gói Hobby $0, dùng instance **Free**.
- Dự án tool đã chạy được trên máy, kiểm thử đạt (TH1).

## Bước 1 – Chuẩn bị dự án (nhờ Claude Code)
Dùng prompt Bước 1 trong `Prompt_mau_hoc_vien.txt`. Kết quả cần có:

| File | Nội dung |
|---|---|
| `requirements.txt` | `flask`, `gunicorn` |
| `.python-version` | `3.13` (Render mặc định dùng Python 3.14 cho dịch vụ mới) |
| `.gitignore` | `venv/`, `__pycache__/`, `*.db`, `.env` |
| `render.yaml` | (tùy chọn) mô tả dịch vụ – xem tool mẫu |
| `app.py` | đăng nhập bằng `APP_PASSWORD`; `SECRET_KEY` đọc từ biến môi trường; dữ liệu nạp không có mô tả, ảnh |

## Bước 2 – Đưa code lên GitHub
1. Trên github.com: **New repository** → đặt tên (vd. `coffeeshop-tool`) → chọn **Private** → không tạo README → Create.
2. Trong Claude Code: “Commit toàn bộ, thêm remote <URL repo> và push nhánh main. Kiểm tra commit không có file .db, .env, venv.”
3. Lần đầu push, máy hỏi đăng nhập GitHub → làm theo cửa sổ trình duyệt (hoặc dùng GitHub Desktop / `gh auth login`).

## Bước 3 – Tạo Web Service trên Render
1. Render Dashboard → **New** → **Web Service** → kết nối GitHub, cho phép Render đọc repo → chọn repo.
2. Thiết lập:
   - Language: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Instance Type: **Free**
3. **Environment Variables:**
   - `APP_PASSWORD` = mật khẩu bạn tự đặt (không dùng mật khẩu thật của mình)
   - `SECRET_KEY` = chuỗi ngẫu nhiên dài – nhờ Claude: `python -c "import secrets; print(secrets.token_hex(32))"`
4. **Deploy Web Service** → chờ build (2–5 phút) → mở địa chỉ `https://<ten>.onrender.com`.

Cách khác: **New → Blueprint** → chọn repo có `render.yaml` → Render tự tạo dịch vụ, tự sinh `SECRET_KEY`, hỏi `APP_PASSWORD`.

## Bước 4 – Kiểm tra
- Mở link → trang đăng nhập → vào được → gọi 1 món → Tổng quan.
- Xem tab **Logs** trên Render: thấy dòng truy cập của bạn.
- Mở link bằng điện thoại.

## Bước 5 – Cập nhật
Sửa nhỏ trên máy (vd. đổi tiêu đề) → chạy kiểm thử → commit, push → Render **tự deploy lại** (xem tab Events). Build lỗi thì bản cũ vẫn chạy.

## Giới hạn gói Free (theo tài liệu Render)
- Ngủ sau **15 phút** không có truy cập; lần mở tiếp theo chờ khoảng **1 phút**.
- **Ổ đĩa tạm:** file SQLite bị xóa khi ngủ, khởi động lại hoặc deploy lại → tool nạp lại dữ liệu mẫu, đơn tạo trên Internet sẽ mất. Muốn giữ dữ liệu: Render Postgres (bản free hết hạn sau 30 ngày) hoặc gói trả phí có ổ đĩa – ngoài phạm vi khóa học.
- 750 giờ chạy/tháng cho mỗi workspace; băng thông gói Hobby 5 GB/tháng.

## Sau khóa học
Xóa dịch vụ (Settings → Delete Web Service) nếu không dùng nữa; không đưa dữ liệu thật, dữ liệu cá nhân lên tool không có hệ thống bảo mật đầy đủ.

Nguồn: https://render.com/docs/deploy-flask · https://render.com/docs/free · https://render.com/docs/python-version · https://render.com/docs/environment-variables · https://render.com/docs/blueprint-spec
