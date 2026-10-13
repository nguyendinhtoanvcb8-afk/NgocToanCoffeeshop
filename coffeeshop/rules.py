"""Quy tắc nghiệp vụ (theo SPEC.md mục 6). Không phụ thuộc Flask."""
import re
import sqlite3
import unicodedata
from datetime import datetime

SERVICE_TYPES = ("Tại quán", "Mang đi", "Giao hàng")
PAYMENTS = ("Tiền mặt", "Chuyển khoản QR", "Ví điện tử")
STATUSES = ("Mới", "Đang pha chế", "Hoàn thành", "Đã hủy")
FINAL_STATUSES = ("Hoàn thành", "Đã hủy")
TRANSITIONS = {
    "Mới": ("Đang pha chế", "Đã hủy"),
    "Đang pha chế": ("Hoàn thành", "Đã hủy"),
}
NOTE_MAX = 100
REASON_MAX = 200
NAME_MAX = 80
PRICE_MAX = 10_000_000
TABLES = range(1, 13)
QTY_MAX = 99
PAGE_SIZE = 50


class RuleError(Exception):
    """Vi phạm quy tắc nghiệp vụ; message hiển thị cho người dùng."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def vnd(n):
    return f"{int(n):,}".replace(",", ".") + " đ"


def _clean(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text or ""))).strip()


def parse_int(value, field, lo=None, hi=None):
    """Chỉ nhận số nguyên thật (không bool, không thập phân, không chữ)."""
    if isinstance(value, bool):
        raise RuleError(f"{field} không hợp lệ")
    if isinstance(value, int):
        n = value
    elif isinstance(value, str) and re.fullmatch(r"\s*-?\d+\s*", value):
        n = int(value)
    else:
        raise RuleError(f"{field} phải là số nguyên")
    if lo is not None and n < lo or hi is not None and n > hi:
        raise RuleError(f"{field} phải từ {lo} đến {hi}")
    return n


def parse_price(value):
    """Giá nguyên dương, bội số 1.000. Cho phép dấu chấm/phẩy ngăn cách nghìn."""
    if isinstance(value, bool):
        raise RuleError("Giá không hợp lệ")
    if isinstance(value, int):
        n = value
    else:
        s = str(value or "").strip()
        if re.fullmatch(r"\d+", s):
            n = int(s)
        elif re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
            n = int(re.sub(r"[.,]", "", s))
        else:
            raise RuleError("Giá phải là số nguyên đồng")
    if n <= 0:
        raise RuleError("Giá phải lớn hơn 0")
    if n % 1000 != 0:
        raise RuleError("Giá phải là bội số của 1.000 đ")
    if n > PRICE_MAX:
        raise RuleError("Giá quá lớn")
    return n


def _begin(conn):
    conn.execute("BEGIN IMMEDIATE")


# ---------------------------------------------------------------- đơn hàng

def next_order_code(conn, now):
    prefix = f"CS-{now:%y%m%d}-"
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(ma_don, ?) AS INTEGER)) FROM orders WHERE ma_don LIKE ?",
        (len(prefix) + 1, prefix + "%")).fetchone()
    return f"{prefix}{(row[0] or 0) + 1:03d}"


def create_order(conn, payload, now):
    """Tạo đơn theo 6.1. Giá và tổng luôn tính ở server."""
    if not isinstance(payload, dict):
        raise RuleError("Dữ liệu đơn không hợp lệ")
    loai = payload.get("loai_phuc_vu")
    if loai not in SERVICE_TYPES:
        raise RuleError("Chọn loại phục vụ: Tại quán, Mang đi hoặc Giao hàng")
    so_ban = None
    if loai == "Tại quán":
        raw = payload.get("so_ban")
        if raw in (None, ""):
            raise RuleError("Đơn Tại quán bắt buộc chọn số bàn (1–12)")
        so_ban = parse_int(raw, "Số bàn", 1, 12)
    thanh_toan = payload.get("thanh_toan")
    if thanh_toan not in PAYMENTS:
        raise RuleError("Chọn phương thức thanh toán")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise RuleError("Đơn phải có ít nhất 1 món")

    lines = []
    for idx, it in enumerate(raw_items, 1):
        if not isinstance(it, dict):
            raise RuleError(f"Dòng {idx} không hợp lệ")
        mon_id = parse_int(it.get("mon_id"), f"Món ở dòng {idx}")
        qty = parse_int(it.get("so_luong"), f"Số lượng ở dòng {idx}")
        if not 1 <= qty <= QTY_MAX:
            raise RuleError(f"Số lượng ở dòng {idx} phải từ 1 đến {QTY_MAX}")
        note = _clean(it.get("ghi_chu"))
        if len(note) > NOTE_MAX:
            raise RuleError(f"Ghi chú ở dòng {idx} tối đa {NOTE_MAX} ký tự")
        lines.append((mon_id, qty, note or None))

    _begin(conn)
    try:
        priced, total = [], 0
        for mon_id, qty, note in lines:
            p = conn.execute("SELECT name, price, dang_ban FROM product WHERE id = ?",
                             (mon_id,)).fetchone()
            if p is None:
                raise RuleError("Món không tồn tại")
            if not p["dang_ban"]:
                raise RuleError(f"Món \"{p['name']}\" đang tạm ngưng")
            line_total = qty * p["price"]
            total += line_total
            priced.append((mon_id, qty, p["price"], line_total, note))
        ma_don = next_order_code(conn, now)
        conn.execute(
            "INSERT INTO orders(ma_don, thoi_gian, loai_phuc_vu, so_ban, trang_thai, thanh_toan, tong_tien) "
            "VALUES (?, ?, ?, ?, 'Mới', ?, ?)",
            (ma_don, f"{now:%Y-%m-%d %H:%M:%S}", loai, so_ban, thanh_toan, total))
        conn.executemany(
            "INSERT INTO order_item(ma_don, mon_id, so_luong, don_gia, thanh_tien, ghi_chu) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(ma_don, *row) for row in priced])
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"ma_don": ma_don, "tong_tien": total}


def change_status(conn, ma_don, new_status, reason, now):
    """Chuyển trạng thái theo 6.3. Chỉ tiến lên; trạng thái cuối là bất biến."""
    reason = _clean(reason)
    if new_status not in STATUSES:
        raise RuleError("Trạng thái không hợp lệ")
    if new_status == "Đã hủy":
        if not reason:
            raise RuleError("Hủy đơn phải ghi lý do")
        if len(reason) > REASON_MAX:
            raise RuleError(f"Lý do tối đa {REASON_MAX} ký tự")
    _begin(conn)
    try:
        row = conn.execute("SELECT trang_thai FROM orders WHERE ma_don = ?", (ma_don,)).fetchone()
        if row is None:
            raise RuleError("Không tìm thấy đơn", 404)
        current = row["trang_thai"]
        if current in FINAL_STATUSES:
            raise RuleError(f"Đơn đã {current.lower()}, không thể thay đổi", 409)
        if new_status not in TRANSITIONS[current]:
            raise RuleError(f"Không thể chuyển từ \"{current}\" sang \"{new_status}\"", 409)
        conn.execute(
            "UPDATE orders SET trang_thai = ?, ly_do_huy = ?, thoi_gian_hoan_thanh = ? "
            "WHERE ma_don = ? AND trang_thai = ?",
            (new_status,
             reason if new_status == "Đã hủy" else None,
             f"{now:%Y-%m-%d %H:%M:%S}" if new_status == "Hoàn thành" else None,
             ma_don, current))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def list_orders(conn, tu=None, den=None, trang_thai=None, loai=None, q=None, page=1):
    where, args = [], []
    if tu:
        where.append("thoi_gian >= ?")
        args.append(f"{tu} 00:00:00")
    if den:
        where.append("thoi_gian <= ?")
        args.append(f"{den} 23:59:59")
    if trang_thai in STATUSES:
        where.append("trang_thai = ?")
        args.append(trang_thai)
    if loai in SERVICE_TYPES:
        where.append("loai_phuc_vu = ?")
        args.append(loai)
    if q:
        where.append("ma_don LIKE ?")
        args.append(f"%{q.strip()}%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM orders {clause}", args).fetchone()[0]
    pages = max(1, -(-total // PAGE_SIZE))
    page = min(max(1, page), pages)
    rows = conn.execute(
        f"SELECT * FROM orders {clause} "
        "ORDER BY (trang_thai IN ('Mới', 'Đang pha chế')) DESC, thoi_gian DESC, ma_don DESC "
        "LIMIT ? OFFSET ?", args + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
    return rows, total, page, pages


def get_order(conn, ma_don):
    order = conn.execute("SELECT * FROM orders WHERE ma_don = ?", (ma_don,)).fetchone()
    if order is None:
        return None, []
    items = conn.execute(
        "SELECT i.*, p.name AS ten_mon FROM order_item i JOIN product p ON p.id = i.mon_id "
        "WHERE i.ma_don = ? ORDER BY i.id", (ma_don,)).fetchall()
    return order, items


# ---------------------------------------------------------------- thực đơn

def _check_name(conn, name, exclude_id=None):
    name = _clean(name)
    if not name:
        raise RuleError("Tên món không được để trống")
    if len(name) > NAME_MAX:
        raise RuleError(f"Tên món tối đa {NAME_MAX} ký tự")
    for r in conn.execute("SELECT id, name FROM product"):
        if r["id"] != exclude_id and r["name"].casefold() == name.casefold():
            raise RuleError(f"Đã có món tên \"{r['name']}\"")
    return name


def _check_category(conn, category_id):
    cid = parse_int(category_id, "Danh mục")
    if conn.execute("SELECT 1 FROM category WHERE id = ?", (cid,)).fetchone() is None:
        raise RuleError("Danh mục không tồn tại")
    return cid


def add_product(conn, name, price, category_id):
    _begin(conn)
    try:
        name = _check_name(conn, name)
        price = parse_price(price)
        cid = _check_category(conn, category_id)
        cur = conn.execute(
            "INSERT INTO product(name, price, category_id, dang_ban) VALUES (?, ?, ?, 1)",
            (name, price, cid))
        conn.execute("COMMIT")
        return cur.lastrowid
    except Exception:
        conn.execute("ROLLBACK")
        raise


def update_product(conn, pid, name, price, category_id):
    """Sửa không đụng tới order_item nên đơn cũ giữ nguyên đơn giá (6.4)."""
    _begin(conn)
    try:
        if conn.execute("SELECT 1 FROM product WHERE id = ?", (pid,)).fetchone() is None:
            raise RuleError("Không tìm thấy món", 404)
        name = _check_name(conn, name, exclude_id=pid)
        price = parse_price(price)
        cid = _check_category(conn, category_id)
        conn.execute("UPDATE product SET name = ?, price = ?, category_id = ? WHERE id = ?",
                     (name, price, cid, pid))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def set_product_active(conn, pid, active):
    cur = conn.execute("UPDATE product SET dang_ban = ? WHERE id = ?", (1 if active else 0, pid))
    if cur.rowcount == 0:
        raise RuleError("Không tìm thấy món", 404)


def delete_product(conn, pid):
    """Chỉ xóa được món chưa từng nằm trong đơn nào (kể cả đơn đã hủy)."""
    _begin(conn)
    try:
        if conn.execute("SELECT 1 FROM product WHERE id = ?", (pid,)).fetchone() is None:
            raise RuleError("Không tìm thấy món", 404)
        used = conn.execute("SELECT COUNT(*) FROM order_item WHERE mon_id = ?", (pid,)).fetchone()[0]
        if used:
            raise RuleError("Món đã có trong đơn hàng nên không thể xóa. Hãy dùng \"Tạm ngưng\".", 409)
        conn.execute("DELETE FROM product WHERE id = ?", (pid,))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def list_products(conn, only_active=False):
    sql = ("SELECT p.*, c.name AS ten_dm, "
           "(SELECT COUNT(*) FROM order_item i WHERE i.mon_id = p.id) AS so_dong_don "
           "FROM product p JOIN category c ON c.id = p.category_id ")
    if only_active:
        sql += "WHERE p.dang_ban = 1 "
    return conn.execute(sql + "ORDER BY p.category_id, p.id").fetchall()


def list_categories(conn):
    return conn.execute("SELECT * FROM category ORDER BY id").fetchall()


# ---------------------------------------------------------------- báo cáo

def valid_month(value):
    return bool(value) and bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value))


def month_report(conn, month):
    """Số liệu theo 6.6: doanh thu chỉ tính đơn Hoàn thành."""
    like = f"{month}-%"
    counts = {r["trang_thai"]: r["n"] for r in conn.execute(
        "SELECT trang_thai, COUNT(*) AS n FROM orders WHERE thoi_gian LIKE ? GROUP BY trang_thai", (like,))}
    done = counts.get("Hoàn thành", 0)
    cancelled = counts.get("Đã hủy", 0)
    all_orders = sum(counts.values())
    revenue = conn.execute(
        "SELECT COALESCE(SUM(tong_tien), 0) FROM orders WHERE trang_thai = 'Hoàn thành' AND thoi_gian LIKE ?",
        (like,)).fetchone()[0]

    top = conn.execute(
        "SELECT p.id, p.name, SUM(i.so_luong) AS so_ly, SUM(i.thanh_tien) AS doanh_thu "
        "FROM order_item i JOIN orders o ON o.ma_don = i.ma_don JOIN product p ON p.id = i.mon_id "
        "WHERE o.trang_thai = 'Hoàn thành' AND o.thoi_gian LIKE ? "
        "GROUP BY p.id ORDER BY so_ly DESC, doanh_thu DESC, p.name LIMIT 5", (like,)).fetchall()
    by_cat = conn.execute(
        "SELECT c.name, COALESCE(SUM(i.thanh_tien), 0) AS doanh_thu "
        "FROM category c JOIN product p ON p.category_id = c.id "
        "LEFT JOIN order_item i ON i.mon_id = p.id "
        "AND i.ma_don IN (SELECT ma_don FROM orders WHERE trang_thai = 'Hoàn thành' AND thoi_gian LIKE ?) "
        "GROUP BY c.id ORDER BY c.id", (like,)).fetchall()

    year, mon = int(month[:4]), int(month[5:])
    days_in = (datetime(year + (mon == 12), mon % 12 + 1, 1) - datetime(year, mon, 1)).days
    daily = [0] * days_in
    for r in conn.execute(
            "SELECT CAST(SUBSTR(thoi_gian, 9, 2) AS INTEGER) AS d, SUM(tong_tien) AS s FROM orders "
            "WHERE trang_thai = 'Hoàn thành' AND thoi_gian LIKE ? GROUP BY d", (like,)):
        daily[r["d"] - 1] = r["s"]
    hourly = [0] * 24
    for r in conn.execute(
            "SELECT CAST(SUBSTR(thoi_gian, 12, 2) AS INTEGER) AS h, SUM(tong_tien) AS s FROM orders "
            "WHERE trang_thai = 'Hoàn thành' AND thoi_gian LIKE ? GROUP BY h", (like,)):
        hourly[r["h"]] = r["s"]

    return {
        "month": month,
        "tong_don": all_orders,
        "don_hoan_thanh": done,
        "don_huy": cancelled,
        "doanh_thu": revenue,
        "trung_binh": round(revenue / done) if done else 0,
        "ty_le_huy": (cancelled / all_orders * 100) if all_orders else 0.0,
        "top5": [dict(r) for r in top],
        "theo_danh_muc": [dict(r) for r in by_cat],
        "theo_ngay": daily,
        "theo_gio": hourly,
    }


def revenue_today(conn, now):
    return conn.execute(
        "SELECT COALESCE(SUM(tong_tien), 0) FROM orders "
        "WHERE trang_thai = 'Hoàn thành' AND thoi_gian LIKE ?", (f"{now:%Y-%m-%d} %",)).fetchone()[0]


def available_months(conn, now):
    months = {r[0] for r in conn.execute("SELECT DISTINCT SUBSTR(thoi_gian, 1, 7) FROM orders")}
    months.add(f"{now:%Y-%m}")
    return sorted(months, reverse=True)
