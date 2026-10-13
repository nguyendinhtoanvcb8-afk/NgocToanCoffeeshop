"""Kết nối SQLite và lược đồ dữ liệu."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS category (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS product (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    price       INTEGER NOT NULL CHECK (price > 0 AND price % 1000 = 0),
    category_id INTEGER NOT NULL REFERENCES category(id),
    description TEXT,
    image       TEXT,
    dang_ban    INTEGER NOT NULL DEFAULT 1 CHECK (dang_ban IN (0, 1))
);

CREATE TABLE IF NOT EXISTS orders (
    ma_don               TEXT PRIMARY KEY,
    thoi_gian            TEXT NOT NULL,
    loai_phuc_vu         TEXT NOT NULL CHECK (loai_phuc_vu IN ('Tại quán', 'Mang đi', 'Giao hàng')),
    so_ban               INTEGER CHECK (so_ban IS NULL OR so_ban BETWEEN 1 AND 12),
    trang_thai           TEXT NOT NULL CHECK (trang_thai IN ('Mới', 'Đang pha chế', 'Hoàn thành', 'Đã hủy')),
    thanh_toan           TEXT NOT NULL CHECK (thanh_toan IN ('Tiền mặt', 'Chuyển khoản QR', 'Ví điện tử')),
    tong_tien            INTEGER NOT NULL CHECK (tong_tien >= 0),
    ly_do_huy            TEXT,
    thoi_gian_hoan_thanh TEXT,
    CHECK ((loai_phuc_vu = 'Tại quán') = (so_ban IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_orders_time ON orders(thoi_gian);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(trang_thai);

CREATE TABLE IF NOT EXISTS order_item (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ma_don     TEXT NOT NULL REFERENCES orders(ma_don),
    mon_id     INTEGER NOT NULL REFERENCES product(id),
    so_luong   INTEGER NOT NULL CHECK (so_luong BETWEEN 1 AND 99),
    don_gia    INTEGER NOT NULL CHECK (don_gia > 0),
    thanh_tien INTEGER NOT NULL,
    ghi_chu    TEXT,
    CHECK (thanh_tien = so_luong * don_gia)
);
CREATE INDEX IF NOT EXISTS idx_item_order ON order_item(ma_don);
CREATE INDEX IF NOT EXISTS idx_item_product ON order_item(mon_id);

-- Lớp bảo vệ cuối cùng ở tầng DB: đơn không xóa, đơn đã kết thúc không sửa,
-- dòng chi tiết bất biến sau khi tạo.
CREATE TRIGGER IF NOT EXISTS orders_no_delete BEFORE DELETE ON orders
BEGIN SELECT RAISE(ABORT, 'Không được xóa đơn hàng'); END;

CREATE TRIGGER IF NOT EXISTS orders_final_immutable BEFORE UPDATE ON orders
WHEN OLD.trang_thai IN ('Hoàn thành', 'Đã hủy')
BEGIN SELECT RAISE(ABORT, 'Đơn đã kết thúc, không được sửa'); END;

CREATE TRIGGER IF NOT EXISTS item_no_update BEFORE UPDATE ON order_item
BEGIN SELECT RAISE(ABORT, 'Chi tiết đơn không được sửa'); END;

CREATE TRIGGER IF NOT EXISTS item_no_delete BEFORE DELETE ON order_item
BEGIN SELECT RAISE(ABORT, 'Chi tiết đơn không được xóa'); END;
"""


def connect(path):
    # isolation_level=None: tự quản lý giao dịch bằng BEGIN/COMMIT.
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
