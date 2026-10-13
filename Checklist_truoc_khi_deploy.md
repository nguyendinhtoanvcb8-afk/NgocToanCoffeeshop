# Checklist trước khi deploy lên Internet

- [ ] Kiểm thử trên máy đạt hết (`python -m pytest -q`)
- [ ] Có đăng nhập; mật khẩu đặt trong biến môi trường `APP_PASSWORD`, không nằm trong code
- [ ] `SECRET_KEY` riêng, đặt trong biến môi trường
- [ ] Không có dữ liệu thật, dữ liệu cá nhân, nội dung có bản quyền (mô tả, ảnh gốc)
- [ ] `.gitignore` loại `venv/`, `*.db`, `.env`; repo GitHub để **Private**
- [ ] `requirements.txt` có `gunicorn`; chạy thử `gunicorn app:app` (macOS/Linux) hoặc nhờ Claude kiểm tra
- [ ] `debug=False`
- [ ] README ghi cách chạy, cách deploy, tên tác giả
- [ ] Hiểu giới hạn gói Free: ngủ sau 15 phút, dữ liệu SQLite bị xóa khi ngủ/khởi động lại
