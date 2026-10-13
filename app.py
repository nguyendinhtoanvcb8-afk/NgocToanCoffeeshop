"""Điểm vào WSGI cho Render: gunicorn app:app"""
import sys

from coffeeshop import create_app

try:
    app = create_app()
except RuntimeError as e:
    # Thiếu biến môi trường trên Render: in thông báo rõ ràng rồi ném lại exception.
    # Không dùng sys.exit(): gunicorn sẽ coi là worker chết thường và khởi động lại mãi;
    # còn exception khi import làm gunicorn dừng hẳn ("Worker failed to boot").
    print(f"LỖI CẤU HÌNH: {e}", file=sys.stderr, flush=True)
    raise
