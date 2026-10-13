"""Nạp dữ liệu từ data/*.csv vào SQLite, áp dụng Quyet_dinh_chu_quan.md.

Không bao giờ ghi vào file CSV gốc. Chạy lặp lại an toàn: chỉ nạp khi bảng còn trống.
"""
import csv
import html
import re
import unicodedata
from pathlib import Path

# Quyết định #3, #4, #7 – áp theo id món.
RENAME_BY_ID = {18: "Phindi Cassia (L)", 43: "Bánh Sô-Cô-La"}
PRICE_BY_ID = {22: 72000, 35: 129000}

BRAND_RE = re.compile(r"highlands(\s+coffee)?", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]*>")
SPACE_RE = re.compile(r"\s+")


def _nfc(text):
    return unicodedata.normalize("NFC", text or "")


def strip_html(text):
    """Quyết định #1: bỏ thẻ HTML, giữ văn bản."""
    text = TAG_RE.sub("", text or "")
    text = html.unescape(text).replace("\xa0", " ")
    return SPACE_RE.sub(" ", text).strip()


def clean_text(text):
    """Bỏ thẻ HTML + thay tên thương hiệu khác bằng CoffeeShop (#1, #7)."""
    return BRAND_RE.sub("CoffeeShop", strip_html(_nfc(text)))


def clean_name(raw, product_id=None):
    """Quyết định #6, #7, #3: 'PHIN ĐEN ĐÁ' -> 'Phin Đen Đá', đổi tên theo id."""
    if product_id in RENAME_BY_ID:
        return RENAME_BY_ID[product_id]
    name = BRAND_RE.sub("CoffeeShop", _nfc(raw)).strip()
    return SPACE_RE.sub(" ", name).title()


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_menu(data_dir, show_media):
    """Trả về (categories, products) đã làm sạch, chưa ghi DB."""
    data_dir = Path(data_dir)
    categories = []
    for r in _read(data_dir / "category.csv"):
        categories.append({
            "id": int(r["id"]),
            "name": _nfc(r["name"]).strip(),
            "description": clean_text(r["description"]) if show_media else None,
        })
    products = []
    for r in _read(data_dir / "product.csv"):
        pid = int(r["id"])
        price = PRICE_BY_ID.get(pid, int(r["price"]))
        desc = clean_text(r["description"]) if show_media else None
        products.append({
            "id": pid,
            "name": clean_name(r["name"], pid),
            "price": price,
            "category_id": int(r["category_id"]),
            "description": desc or None,
            "image": (r["image"].strip() or None) if show_media else None,
            "dang_ban": 1,  # #8
        })
        # Cột published_date bị bỏ (#5).
    return categories, products


def load_history(data_dir):
    """Đọc và kiểm tra lịch sử đơn. Ném ValueError nếu dữ liệu không nhất quán."""
    data_dir = Path(data_dir)
    orders = _read(data_dir / "lich_su_don_hang.csv")
    items = _read(data_dir / "lich_su_chi_tiet_don.csv")

    codes = [o["ma_don"] for o in orders]
    if len(codes) != len(set(codes)):
        raise ValueError("Mã đơn lịch sử bị trùng")
    sums, counts = {}, {}
    for it in items:
        qty, price, line = int(it["so_luong"]), int(it["don_gia"]), int(it["thanh_tien"])
        if qty * price != line:
            raise ValueError(f"Thành tiền sai ở đơn {it['ma_don']}")
        sums[it["ma_don"]] = sums.get(it["ma_don"], 0) + line
        counts[it["ma_don"]] = counts.get(it["ma_don"], 0) + 1
    for o in orders:
        if o["ma_don"] not in counts:
            raise ValueError(f"Đơn {o['ma_don']} không có dòng chi tiết")
        if sums[o["ma_don"]] != int(o["tong_tien"]):
            raise ValueError(f"Tổng tiền đơn {o['ma_don']} không khớp chi tiết")
        if (o["loai_phuc_vu"] == "Tại quán") != bool(o["so_ban"]):
            raise ValueError(f"Số bàn đơn {o['ma_don']} không hợp lệ")
    if set(sums) - set(codes):
        raise ValueError("Chi tiết đơn tham chiếu đơn không tồn tại")
    return orders, items


def seed_if_empty(conn, data_dir, show_media):
    """Nạp menu + lịch sử trong một giao dịch. Trả về True nếu đã nạp."""
    if conn.execute("SELECT COUNT(*) FROM product").fetchone()[0] > 0:
        return False
    categories, products = load_menu(data_dir, show_media)
    orders, items = load_history(data_dir)

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany(
            "INSERT INTO category(id, name, description) VALUES (:id, :name, :description)",
            categories)
        conn.executemany(
            "INSERT INTO product(id, name, price, category_id, description, image, dang_ban) "
            "VALUES (:id, :name, :price, :category_id, :description, :image, :dang_ban)",
            products)
        conn.executemany(
            "INSERT INTO orders(ma_don, thoi_gian, loai_phuc_vu, so_ban, trang_thai, thanh_toan, tong_tien) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(o["ma_don"], o["thoi_gian"], o["loai_phuc_vu"],
              int(o["so_ban"]) if o["so_ban"] else None,
              o["trang_thai"], o["thanh_toan"], int(o["tong_tien"])) for o in orders])
        conn.executemany(
            "INSERT INTO order_item(ma_don, mon_id, so_luong, don_gia, thanh_tien, ghi_chu) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(i["ma_don"], int(i["mon_id"]), int(i["so_luong"]), int(i["don_gia"]),
              int(i["thanh_tien"]), i["ghi_chu"] or None) for i in items])
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return True
