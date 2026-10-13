"""Chạy CoffeeShop trên máy ở http://127.0.0.1:5000 (không đặt APP_PASSWORD thì không hỏi mật khẩu)."""
import os
import sys

from coffeeshop import create_app

if __name__ == "__main__":
    try:
        app = create_app()
    except RuntimeError as e:
        sys.exit(f"LỖI CẤU HÌNH: {e}")
    if app.config["SEEDED"]:
        print("Lần chạy đầu: đã tạo database từ data/*.csv (kèm lịch sử đơn).")
    if not app.config["AUTH_ENABLED"]:
        print("Chưa đặt APP_PASSWORD: chạy không cần mật khẩu (chỉ dùng trên máy cá nhân).")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
