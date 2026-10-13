"""Kiểm thử tự động các quy tắc trong SPEC.md. Chạy: python -m unittest discover -s tests -v"""
import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from coffeeshop import create_app, rules, seed

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANAGER, CASHIER = "mgr-pass", "cash-pass"
NOW = datetime(2026, 10, 13, 10, 0, 0)

PHIN_SUA_DA, TIRAMISU, PHIN_DEN_DA, SET_TRA = 7, 39, 1, 35

DEFAULT = object()
_tmp = None
_template = None


def setUpModule():
    """Tạo DB mẫu một lần (nạp CSV + lịch sử), mỗi test chép ra bản riêng."""
    global _tmp, _template
    _tmp = tempfile.TemporaryDirectory()
    _template = Path(_tmp.name) / "template.db"
    create_app(base_config(_template))


def tearDownModule():
    _tmp.cleanup()


def base_config(db_path, **extra):
    cfg = {"DATABASE": str(db_path), "MANAGER_PASSWORD": MANAGER, "CASHIER_PASSWORD": CASHIER,
           "SECRET_KEY": "test", "NOW": lambda: NOW, "TESTING": True, "RENDER": False}
    cfg.update(extra)
    return cfg


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.dir.name) / "t.db"
        shutil.copy(_template, self.db_path)
        self.now = NOW
        self.app = create_app(base_config(self.db_path, NOW=lambda: self.now))
        self.client = self.app.test_client()

    def tearDown(self):
        self.dir.cleanup()

    def login(self, role="manager", client=None):
        c = client or self.client
        r = c.post("/login", data={"password": MANAGER if role == "manager" else CASHIER})
        self.assertEqual(r.status_code, 302)
        return c

    def db(self):
        """Kết nối tới DB của test; tự đóng khi test kết thúc (Windows khóa file đang mở)."""
        from coffeeshop import db
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def q(self, sql, *args):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def one(self, sql, *args):
        return self.q(sql, *args)[0][0]

    def order(self, items=DEFAULT, loai="Tại quán", so_ban=5, thanh_toan="Chuyển khoản QR", client=None, **extra):
        c = client or self.client
        body = {"loai_phuc_vu": loai, "so_ban": so_ban, "thanh_toan": thanh_toan,
                "items": [{"mon_id": PHIN_SUA_DA, "so_luong": 1}] if items is DEFAULT else items}
        body.update(extra)
        return c.post("/api/orders", json=body)

    def n_orders(self):
        return self.one("SELECT COUNT(*) FROM orders")

    def status(self, ma, new, reason="", client=None):
        return (client or self.client).post(f"/don-hang/{ma}/trang-thai",
                                            json={"trang_thai": new, "ly_do": reason})

    def finish(self, ma):
        self.assertEqual(self.status(ma, "Đang pha chế").status_code, 200)
        self.assertEqual(self.status(ma, "Hoàn thành").status_code, 200)


# ------------------------------------------------------------------ nạp dữ liệu

class SeedTests(Base):
    def test_history_loaded(self):
        self.assertEqual(self.n_orders(), 4549)
        self.assertEqual(self.one("SELECT COUNT(*) FROM order_item"), 7409)
        self.assertEqual(self.one("SELECT COUNT(*) FROM orders WHERE trang_thai='Hoàn thành'"), 4385)
        self.assertEqual(self.one("SELECT COUNT(*) FROM orders WHERE trang_thai='Đã hủy'"), 164)
        self.assertEqual(self.one("SELECT COUNT(*) FROM product"), 46)

    def test_history_totals_match_items(self):
        bad = self.q("SELECT o.ma_don FROM orders o WHERE o.tong_tien != "
                     "(SELECT SUM(thanh_tien) FROM order_item i WHERE i.ma_don = o.ma_don)")
        self.assertEqual(bad, [])

    def test_owner_decisions_applied(self):
        names = {r["id"]: r["name"] for r in self.q("SELECT id, name FROM product")}
        price = {r["id"]: r["price"] for r in self.q("SELECT id, price FROM product")}
        self.assertEqual(names[1], "Phin Đen Đá")                 # #6
        self.assertEqual(names[10], "Phindi Cassia")
        self.assertEqual(names[18], "Phindi Cassia (L)")          # #3
        self.assertEqual(names[43], "Bánh Sô-Cô-La")              # #7
        self.assertEqual(price[22], 72000)                        # #4
        self.assertEqual(price[35], 129000)
        self.assertEqual(len({n.casefold() for n in names.values()}), len(names))
        self.assertTrue(all(p % 1000 == 0 for p in price.values()))
        self.assertTrue(all(r["dang_ban"] == 1 for r in self.q("SELECT dang_ban FROM product")))  # #8
        text = " ".join(r[0] or "" for r in self.q("SELECT description FROM product")) + " ".join(names.values())
        self.assertNotIn("<", text)                               # #1 không còn thẻ HTML
        self.assertNotIn("&nbsp;", text)
        self.assertNotIn("highlands", text.lower())               # #7
        # Bản CSV trong repo GitHub đã bị làm trống mô tả; chỉ kiểm khi dữ liệu có mô tả (bản gốc ở máy).
        if any(r[0] for r in self.q("SELECT description FROM product WHERE id = 1")):
            self.assertIn("CoffeeShop", self.one("SELECT description FROM product WHERE id = 1"))

    def test_no_published_date_column(self):
        cols = [r["name"] for r in self.q("PRAGMA table_info(product)")]
        self.assertNotIn("published_date", cols)

    def test_seed_is_idempotent_and_csv_untouched(self):
        before = {p.name: sha(p) for p in DATA.glob("*.csv")}
        app = create_app(base_config(self.db_path))
        self.assertFalse(app.config["SEEDED"])
        self.assertEqual(self.n_orders(), 4549)
        self.assertEqual(before, {p.name: sha(p) for p in DATA.glob("*.csv")})

    def test_media_dropped_when_disabled(self):
        path = Path(self.dir.name) / "nomedia.db"
        app = create_app(base_config(path, SHOW_MEDIA=False))
        self.assertTrue(app.config["SEEDED"])
        conn = sqlite3.connect(path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM product WHERE description IS NOT NULL "
                                      "OR image IS NOT NULL").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM category WHERE description IS NOT NULL").fetchone()[0], 0)
        conn.close()
        c = app.test_client()
        c.post("/login", data={"password": MANAGER})
        self.assertEqual(c.get("/media/Cold_Brew.jpg").status_code, 404)

    def test_clean_helpers(self):
        self.assertEqual(seed.strip_html("<p>Xin <b>chào</b>&nbsp;bạn</p>"), "Xin chào bạn")
        self.assertEqual(seed.clean_name("COOKIES & CREAM"), "Cookies & Cream")
        self.assertEqual(seed.clean_name("TRÀ SEN VÀNG (CỦ NĂNG)"), "Trà Sen Vàng (Củ Năng)")
        self.assertEqual(seed.clean_text("tại Highlands Coffee"), "tại CoffeeShop")



# ------------------------------------------------------------------ cấu hình đăng nhập (máy / Render)

class LoginConfigTests(Base):
    def make(self, name="x.db", **extra):
        return create_app(base_config(Path(self.dir.name) / name, **extra))

    def test_local_without_password_needs_no_login(self):
        app = self.make(MANAGER_PASSWORD="", CASHIER_PASSWORD="")
        self.assertFalse(app.config["AUTH_ENABLED"])
        c = app.test_client()
        for path in ("/goi-mon", "/don-hang", "/thuc-don", "/tong-quan"):
            self.assertEqual(c.get(path).status_code, 200, path)
        self.assertEqual(c.get("/login").status_code, 302)                 # không có trang đăng nhập
        self.assertEqual(c.post("/api/orders", json={"loai_phuc_vu": "Mang đi", "thanh_toan": "Tiền mặt",
                         "items": [{"mon_id": PHIN_SUA_DA, "so_luong": 1}]}).status_code, 201)
        # toàn quyền quản lý, và giao diện không có nút đăng xuất
        self.assertEqual(c.post("/thuc-don", json={"name": "Món thử", "price": 20000, "category_id": 1}).status_code, 200)
        self.assertNotIn("Đăng xuất", c.get("/goi-mon").get_data(as_text=True))

    def test_password_set_enables_login(self):
        app = self.make(MANAGER_PASSWORD="abc-xyz", CASHIER_PASSWORD="")
        self.assertTrue(app.config["AUTH_ENABLED"])
        c = app.test_client()
        self.assertEqual(c.get("/goi-mon").status_code, 302)
        self.assertEqual(c.post("/api/orders", json={}).status_code, 401)
        self.assertEqual(c.post("/login", data={"password": "sai"}).status_code, 401)
        self.assertEqual(c.post("/login", data={"password": ""}).status_code, 401)   # rỗng không khớp
        self.assertEqual(c.post("/login", data={"password": "abc-xyz"}).status_code, 302)
        self.assertEqual(c.get("/thuc-don").status_code, 200)
        self.assertIn("Đăng xuất", c.get("/goi-mon").get_data(as_text=True))
        c.post("/logout")
        self.assertEqual(c.get("/goi-mon").status_code, 302)

    def test_empty_cashier_password_is_not_a_backdoor(self):
        c = self.make(MANAGER_PASSWORD="abc-xyz", CASHIER_PASSWORD="").test_client()
        self.assertEqual(c.post("/login", data={"password": ""}).status_code, 401)
        self.assertEqual(c.get("/goi-mon").status_code, 302)

    def test_login_next_cannot_redirect_off_site(self):
        c = self.make(MANAGER_PASSWORD="abc-xyz", CASHIER_PASSWORD="").test_client()
        for nxt in ("//evil.example", "/\evil.example", "https://evil.example"):
            r = c.post("/login?next=" + nxt, data={"password": "abc-xyz"})
            self.assertEqual(r.headers["Location"], "/goi-mon", nxt)

    def test_cashier_password_without_app_password_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.make(MANAGER_PASSWORD="", CASHIER_PASSWORD="thu-ngan")

    def test_render_requires_app_password_and_secret_key(self):
        with self.assertRaises(RuntimeError) as cm:
            self.make("r1.db", RENDER=True, MANAGER_PASSWORD="", SECRET_KEY=None)
        self.assertIn("APP_PASSWORD", str(cm.exception))
        self.assertIn("SECRET_KEY", str(cm.exception))
        with self.assertRaises(RuntimeError) as cm:
            self.make("r2.db", RENDER=True, MANAGER_PASSWORD="", SECRET_KEY="k")
        self.assertIn("APP_PASSWORD", str(cm.exception))
        self.assertNotIn("SECRET_KEY", str(cm.exception))
        with self.assertRaises(RuntimeError) as cm:
            self.make("r3.db", RENDER=True, MANAGER_PASSWORD="pw", SECRET_KEY=None)
        self.assertIn("SECRET_KEY", str(cm.exception))
        self.assertNotIn("APP_PASSWORD", str(cm.exception))
        self.assertFalse((Path(self.dir.name) / "r3.db.secret").exists())   # không tự sinh khóa trên Render
        self.assertTrue(self.make("r4.db", RENDER=True, MANAGER_PASSWORD="pw", SECRET_KEY="k").config["AUTH_ENABLED"])

    def test_render_never_loads_descriptions_or_images(self):
        path = Path(self.dir.name) / "render.db"
        app = self.make("render.db", RENDER=True, MANAGER_PASSWORD="pw", SECRET_KEY="k", SHOW_MEDIA=True)
        self.assertFalse(app.config["SHOW_MEDIA"])              # cố bật cũng bị ép tắt
        conn = sqlite3.connect(path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM product").fetchone()[0], 46)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM product WHERE description IS NOT NULL "
                                      "OR image IS NOT NULL").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM category WHERE description IS NOT NULL").fetchone()[0], 0)
        conn.close()
        c = app.test_client()
        c.post("/login", data={"password": "pw"})
        self.assertEqual(c.get("/media/Cold_Brew.jpg").status_code, 404)
        page = c.get("/thuc-don").get_data(as_text=True)
        self.assertNotIn("<img", page)

    def test_wsgi_entrypoint_fails_clearly_on_render_without_env(self):
        import os
        import subprocess
        import sys
        code = f"import sys; sys.path.insert(0, {str(ROOT)!r}); import app; print('IMPORTED')"
        env = {k: v for k, v in os.environ.items() if k not in ("APP_PASSWORD", "SECRET_KEY", "CASHIER_PASSWORD")}
        env.update(RENDER="true", DATABASE_PATH=str(Path(self.dir.name) / "wsgi.db"), PYTHONIOENCODING="utf-8")
        bad = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", code], capture_output=True, text=True, env=env, encoding="utf-8")
        self.assertNotEqual(bad.returncode, 0)
        self.assertNotIn("IMPORTED", bad.stdout)
        self.assertIn("APP_PASSWORD", bad.stderr)
        self.assertIn("SECRET_KEY", bad.stderr)
        env.update(APP_PASSWORD="pw-test", SECRET_KEY="k-test")
        good = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", code], capture_output=True, text=True, env=env, encoding="utf-8")
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn("IMPORTED", good.stdout)

    def test_no_real_password_in_source(self):
        import re
        for f in list(ROOT.glob("*.py")) + list((ROOT / "coffeeshop").glob("*.py")) + [ROOT / "render.yaml"]:
            text = f.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(APP_PASSWORD|SECRET_KEY)\s*[:=]\s*[\"'][^\"']+[\"']", text), f.name)


# ------------------------------------------------------------------ đăng nhập, phân quyền

class AuthTests(Base):
    def test_requires_login(self):
        for path in ("/goi-mon", "/don-hang", "/thuc-don", "/tong-quan"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/login", r.headers["Location"])
        r = self.client.post("/api/orders", json={})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.post("/thuc-don", json={"name": "x"}).status_code, 401)

    def test_session_survives_restart_without_secret_key(self):
        cfg = base_config(self.db_path, SECRET_KEY=None)
        first = create_app(cfg)
        c = first.test_client()
        c.post("/login", data={"password": MANAGER})
        self.assertEqual(c.get("/goi-mon").status_code, 200)
        second = create_app(cfg)                       # "khởi động lại" tool
        c2 = second.test_client()
        c2.set_cookie("session", c.get_cookie("session").value)
        self.assertEqual(c2.get("/goi-mon").status_code, 200)

    def test_wrong_password(self):
        r = self.client.post("/login", data={"password": "sai"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.get("/goi-mon").status_code, 302)

    def test_cashier_cannot_edit_menu(self):
        self.login("cashier")
        for path, body in (("/thuc-don", {"name": "Trà mới", "price": 30000, "category_id": 3}),
                           ("/thuc-don/1/sua", {"name": "A", "price": 99000, "category_id": 1}),
                           ("/thuc-don/1/ban", {"dang_ban": 0}),
                           ("/thuc-don/1/xoa", {})):
            self.assertEqual(self.client.post(path, json=body).status_code, 403, path)
        self.assertEqual(self.one("SELECT price FROM product WHERE id = 1"), 29000)
        self.assertEqual(self.one("SELECT dang_ban FROM product WHERE id = 1"), 1)
        self.assertEqual(self.one("SELECT COUNT(*) FROM product"), 46)
        page = self.client.get("/thuc-don").get_data(as_text=True)
        self.assertNotIn("Thêm món", page)

    def test_cashier_can_use_orders_and_overview(self):
        self.login("cashier")
        self.assertEqual(self.client.get("/tong-quan?thang=2026-09").status_code, 200)
        self.assertEqual(self.client.get("/don-hang").status_code, 200)
        self.assertEqual(self.client.get("/goi-mon").status_code, 200)
        self.assertEqual(self.order().status_code, 201)


# ------------------------------------------------------------------ tạo đơn

class CreateOrderTests(Base):
    def test_scenario_2_total_and_status(self):
        self.login()
        r = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 2, "ghi_chu": "ít đá"},
                              {"mon_id": TIRAMISU, "so_luong": 1}])
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["tong_tien"], 93000)
        ma = r.get_json()["ma_don"]
        row = self.q("SELECT * FROM orders WHERE ma_don = ?", ma)[0]
        self.assertEqual((row["trang_thai"], row["so_ban"], row["tong_tien"], row["thanh_toan"]),
                         ("Mới", 5, 93000, "Chuyển khoản QR"))
        items = self.q("SELECT * FROM order_item WHERE ma_don = ? ORDER BY id", ma)
        self.assertEqual([(i["so_luong"], i["don_gia"], i["thanh_tien"], i["ghi_chu"]) for i in items],
                         [(2, 29000, 58000, "ít đá"), (1, 35000, 35000, None)])

    def test_dine_in_requires_table(self):
        self.login()
        before = self.n_orders()
        for bad in (None, "", 0, 13, -1, "abc", 2.5):
            self.assertEqual(self.order(so_ban=bad).status_code, 400, repr(bad))
        self.assertEqual(self.n_orders(), before)

    def test_tables_1_to_12_ok_and_same_table_multiple_orders(self):
        self.login()
        a = self.order(so_ban=1).get_json()["ma_don"]
        b = self.order(so_ban=12).get_json()["ma_don"]
        c = self.order(so_ban=1).get_json()["ma_don"]
        self.assertEqual(len({a, b, c}), 3)

    def test_takeaway_and_delivery_have_no_table(self):
        self.login()
        for loai in ("Mang đi", "Giao hàng"):
            r = self.order(loai=loai, so_ban=7)          # số bàn gửi kèm bị bỏ qua
            self.assertEqual(r.status_code, 201)
            self.assertIsNone(self.one("SELECT so_ban FROM orders WHERE ma_don = ?", r.get_json()["ma_don"]))
            r = self.order(loai=loai, so_ban=None)
            self.assertEqual(r.status_code, 201)

    def test_quantity_validation(self):
        self.login()
        before = self.n_orders()
        for bad in (0, -2, 100, 1.5, "abc", "", None, True, "1.5"):
            r = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": bad}])
            self.assertEqual(r.status_code, 400, repr(bad))
        self.assertEqual(self.n_orders(), before)
        self.assertEqual(self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 99}]).status_code, 201)
        self.assertEqual(self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": "3"}]).status_code, 201)

    def test_note_length(self):
        self.login()
        ok = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 1, "ghi_chu": "a" * 100}])
        self.assertEqual(ok.status_code, 201)
        bad = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 1, "ghi_chu": "a" * 101}])
        self.assertEqual(bad.status_code, 400)

    def test_empty_order_rejected(self):
        self.login()
        before = self.n_orders()
        for items in ([], None, "x", [1]):
            self.assertEqual(self.order(items=items).status_code, 400)
        self.assertEqual(self.n_orders(), before)

    def test_invalid_enums_rejected(self):
        self.login()
        self.assertEqual(self.order(loai="Ăn tại chỗ").status_code, 400)
        self.assertEqual(self.order(thanh_toan="Thẻ").status_code, 400)
        self.assertEqual(self.order(thanh_toan=None).status_code, 400)

    def test_unknown_product_rejected_and_no_partial_order(self):
        self.login()
        before = self.n_orders()
        r = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 1}, {"mon_id": 9999, "so_luong": 1}])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.n_orders(), before)
        self.assertEqual(self.one("SELECT COUNT(*) FROM order_item WHERE ma_don NOT IN (SELECT ma_don FROM orders)"), 0)

    def test_server_ignores_client_prices(self):
        self.login()
        r = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 1, "don_gia": 1000, "thanh_tien": 1000}],
                       tong_tien=1000)
        self.assertEqual(r.get_json()["tong_tien"], 29000)

    def test_paused_product_not_orderable_nor_listed(self):
        self.login()
        self.client.post(f"/thuc-don/{SET_TRA}/ban", json={"dang_ban": 0})
        r = self.order(items=[{"mon_id": SET_TRA, "so_luong": 1}])
        self.assertEqual(r.status_code, 400)
        page = self.client.get("/goi-mon").get_data(as_text=True)
        self.assertNotIn("Set Trà Cao Cấp", page)
        self.assertIn("Phin Sữa Đá", page)

    def test_order_code_format_and_daily_sequence(self):
        self.login()
        self.assertEqual(self.order().get_json()["ma_don"], "CS-261013-001")
        self.assertEqual(self.order().get_json()["ma_don"], "CS-261013-002")
        self.now = datetime(2026, 10, 14, 8, 0, 0)
        self.assertEqual(self.order().get_json()["ma_don"], "CS-261014-001")

    def test_order_code_continues_after_history_day(self):
        self.login()
        last = self.one("SELECT MAX(ma_don) FROM orders WHERE ma_don LIKE 'CS-260930-%'")
        self.now = datetime(2026, 9, 30, 22, 0, 0)
        n = int(last[-3:]) + 1
        self.assertEqual(self.order().get_json()["ma_don"], f"CS-260930-{n:03d}")


# ------------------------------------------------------------------ vòng đời đơn

class StatusTests(Base):
    def setUp(self):
        super().setUp()
        self.login()
        self.ma = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 2},
                                    {"mon_id": TIRAMISU, "so_luong": 1}]).get_json()["ma_don"]

    def test_full_flow_increases_today_revenue(self):
        base = rules.revenue_today(self.db(), NOW)
        self.assertEqual(self.status(self.ma, "Đang pha chế").status_code, 200)
        self.assertEqual(rules.revenue_today(self.db(), NOW), base)     # chưa hoàn thành: chưa tính
        self.assertEqual(self.status(self.ma, "Hoàn thành").status_code, 200)
        self.assertEqual(rules.revenue_today(self.db(), NOW), base + 93000)
        self.assertIn("93.000 đ", self.client.get("/tong-quan").get_data(as_text=True))
        self.assertIsNotNone(self.one("SELECT thoi_gian_hoan_thanh FROM orders WHERE ma_don = ?", self.ma))

    def test_cannot_skip_or_go_back(self):
        self.assertEqual(self.status(self.ma, "Hoàn thành").status_code, 409)     # Mới -> Hoàn thành
        self.assertEqual(self.status(self.ma, "Mới").status_code, 409)
        self.assertEqual(self.status(self.ma, "Đang pha chế").status_code, 200)
        self.assertEqual(self.status(self.ma, "Mới").status_code, 409)
        self.assertEqual(self.status(self.ma, "Đang pha chế").status_code, 409)
        self.assertEqual(self.status(self.ma, "Trạng thái lạ").status_code, 400)

    def test_completed_order_is_immutable(self):
        self.finish(self.ma)
        for new in ("Mới", "Đang pha chế", "Hoàn thành"):
            self.assertEqual(self.status(self.ma, new).status_code, 409, new)
        self.assertEqual(self.status(self.ma, "Đã hủy", "nhầm").status_code, 409)
        self.assertEqual(self.one("SELECT trang_thai FROM orders WHERE ma_don = ?", self.ma), "Hoàn thành")

    def test_orders_cannot_be_deleted(self):
        before = self.n_orders()
        for method in (self.client.post, self.client.delete):
            self.assertEqual(method(f"/don-hang/{self.ma}/xoa").status_code, 403)
        self.finish(self.ma)
        self.assertEqual(self.client.post(f"/don-hang/{self.ma}/xoa").status_code, 403)
        self.assertEqual(self.n_orders(), before)

    def test_cancel_requires_reason(self):
        self.assertEqual(self.status(self.ma, "Đã hủy", "").status_code, 400)
        self.assertEqual(self.status(self.ma, "Đã hủy", "   ").status_code, 400)
        self.assertEqual(self.status(self.ma, "Đã hủy", "x" * 201).status_code, 400)
        self.assertEqual(self.one("SELECT trang_thai FROM orders WHERE ma_don = ?", self.ma), "Mới")
        self.assertEqual(self.status(self.ma, "Đã hủy", "Khách đổi ý").status_code, 200)
        row = self.q("SELECT * FROM orders WHERE ma_don = ?", self.ma)[0]
        self.assertEqual((row["trang_thai"], row["ly_do_huy"]), ("Đã hủy", "Khách đổi ý"))

    def test_cancel_from_brewing_and_cashier_may_cancel(self):
        self.status(self.ma, "Đang pha chế")
        cashier = self.login("cashier", client=self.app.test_client())
        self.assertEqual(self.status(self.ma, "Đã hủy", "Pha sai", client=cashier).status_code, 200)

    def test_cancelled_is_final_and_excluded_from_revenue(self):
        self.status(self.ma, "Đã hủy", "Khách đi")
        for new in ("Mới", "Đang pha chế", "Hoàn thành"):
            self.assertEqual(self.status(self.ma, new).status_code, 409)
        self.assertEqual(rules.revenue_today(self.db(), NOW), 0)

    def test_unknown_order(self):
        self.assertEqual(self.status("CS-000000-999", "Đang pha chế").status_code, 404)

    def test_database_triggers_block_tampering(self):
        self.finish(self.ma)
        conn = sqlite3.connect(self.db_path)
        for sql in ("UPDATE orders SET tong_tien = 1 WHERE ma_don = ?",
                    "DELETE FROM orders WHERE ma_don = ?",
                    "UPDATE order_item SET so_luong = 5 WHERE ma_don = ?",
                    "DELETE FROM order_item WHERE ma_don = ?"):
            with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                conn.execute(sql, (self.ma,))
        conn.close()

    def test_order_list_filters_and_active_first(self):
        done = self.order().get_json()["ma_don"]
        self.finish(done)
        html = self.client.get("/don-hang").get_data(as_text=True)         # mặc định: hôm nay
        self.assertIn(self.ma, html)
        self.assertLess(html.index(self.ma), html.index(done))             # đơn đang xử lý lên đầu
        self.assertNotIn("CS-260930-001", html)
        html = self.client.get("/don-hang?tu=2026-09-15&den=2026-09-15&trang_thai=Đã+hủy").get_data(as_text=True)
        self.assertNotIn(self.ma, html)
        conn = self.db()
        rows, total, page, pages = rules.list_orders(conn, "2026-09-01", "2026-09-30")
        self.assertEqual(total, 1451)
        self.assertEqual((len(rows), pages), (50, 30))
        rows, total, *_ = rules.list_orders(conn, trang_thai="Đã hủy")
        self.assertEqual(total, 164)
        rows, total, *_ = rules.list_orders(conn, q="CS-260915-001")
        self.assertEqual(total, 1)
        conn.close()


# ------------------------------------------------------------------ thực đơn

class MenuTests(Base):
    def setUp(self):
        super().setUp()
        self.login()

    def price(self, pid):
        return self.one("SELECT price FROM product WHERE id = ?", pid)

    def test_add_product_appears_in_ordering(self):
        r = self.client.post("/thuc-don", json={"name": "Cà phê muối", "price": 39000, "category_id": 1})
        self.assertEqual(r.status_code, 200)
        pid = r.get_json()["id"]
        self.assertEqual(self.one("SELECT dang_ban FROM product WHERE id = ?", pid), 1)
        self.assertIn("Cà phê muối", self.client.get("/goi-mon").get_data(as_text=True))
        o = self.order(items=[{"mon_id": pid, "so_luong": 1}])
        self.assertEqual(o.get_json()["tong_tien"], 39000)

    def test_price_validation(self):
        for bad in (39500, "39.500", 0, -1000, "abc", "", None, 1.5, 20_000_000):
            r = self.client.post("/thuc-don", json={"name": f"Món {bad}", "price": bad, "category_id": 1})
            self.assertEqual(r.status_code, 400, repr(bad))
        r = self.client.post("/thuc-don", json={"name": "Món A", "price": "39.000", "category_id": 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.price(r.get_json()["id"]), 39000)
        self.assertEqual(self.client.post(f"/thuc-don/1/sua", json={"name": "Phin Đen Đá", "price": 29500,
                                                                   "category_id": 1}).status_code, 400)
        self.assertEqual(self.price(1), 29000)

    def test_name_and_category_validation(self):
        for name in ("phin sữa đá", "  PHIN   SỮA ĐÁ ", "", "   ", "x" * 81):
            r = self.client.post("/thuc-don", json={"name": name, "price": 30000, "category_id": 1})
            self.assertEqual(r.status_code, 400, repr(name))
        self.assertEqual(self.client.post("/thuc-don", json={"name": "Mới", "price": 30000, "category_id": 99}).status_code, 400)
        self.assertEqual(self.client.post("/thuc-don", json={"name": "Mới", "price": 30000, "category_id": None}).status_code, 400)
        r = self.client.post("/thuc-don/2/sua", json={"name": "Latte", "price": 69000, "category_id": 1})
        self.assertEqual(r.status_code, 400)                                 # trùng tên món khác
        r = self.client.post("/thuc-don/3/sua", json={"name": "Latte", "price": 66000, "category_id": 1})
        self.assertEqual(r.status_code, 200)                                 # giữ tên của chính nó
        self.assertEqual(self.client.post("/thuc-don/999/sua", json={"name": "Z", "price": 1000, "category_id": 1}).status_code, 404)

    def test_price_change_keeps_old_orders(self):
        old = self.order(items=[{"mon_id": PHIN_DEN_DA, "so_luong": 2}]).get_json()
        self.assertEqual(old["tong_tien"], 58000)
        hist_before = self.q("SELECT ma_don, tong_tien FROM orders ORDER BY ma_don")
        r = self.client.post(f"/thuc-don/{PHIN_DEN_DA}/sua", json={"name": "Phin Đen Đá", "price": 32000, "category_id": 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.price(PHIN_DEN_DA), 32000)
        self.assertEqual(self.one("SELECT tong_tien FROM orders WHERE ma_don = ?", old["ma_don"]), 58000)
        self.assertEqual(self.one("SELECT don_gia FROM order_item WHERE ma_don = ?", old["ma_don"]), 29000)
        new = self.order(items=[{"mon_id": PHIN_DEN_DA, "so_luong": 2}]).get_json()
        self.assertEqual(new["tong_tien"], 64000)
        self.assertEqual(self.one("SELECT don_gia FROM order_item WHERE ma_don = ?", new["ma_don"]), 32000)
        hist_after = [r for r in self.q("SELECT ma_don, tong_tien FROM orders ORDER BY ma_don")
                      if r["ma_don"] in {h["ma_don"] for h in hist_before}]
        self.assertEqual([tuple(r) for r in hist_before], [tuple(r) for r in hist_after])

    def test_pause_and_resume(self):
        self.assertEqual(self.client.post(f"/thuc-don/{SET_TRA}/ban", json={"dang_ban": 0}).status_code, 200)
        self.assertEqual(self.one("SELECT dang_ban FROM product WHERE id = ?", SET_TRA), 0)
        self.assertEqual(self.client.post(f"/thuc-don/{SET_TRA}/ban", json={"dang_ban": 1}).status_code, 200)
        self.assertIn("Set Trà Cao Cấp", self.client.get("/goi-mon").get_data(as_text=True))
        self.assertEqual(self.client.post("/thuc-don/999/ban", json={"dang_ban": 0}).status_code, 404)

    def test_pausing_does_not_block_open_order_or_reports(self):
        ma = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 1}]).get_json()["ma_don"]
        self.client.post(f"/thuc-don/{PHIN_SUA_DA}/ban", json={"dang_ban": 0})
        self.finish(ma)
        top = rules.month_report(self.db(), "2026-09")["top5"]
        self.assertEqual(top[0]["name"], "Phin Sữa Đá")

    def test_cannot_delete_product_with_orders(self):
        for pid in (PHIN_SUA_DA, SET_TRA):
            r = self.client.post(f"/thuc-don/{pid}/xoa", json={})
            used = self.one("SELECT COUNT(*) FROM order_item WHERE mon_id = ?", pid)
            self.assertEqual(r.status_code, 409 if used else 200, pid)
        self.assertEqual(self.one("SELECT COUNT(*) FROM product WHERE id = ?", PHIN_SUA_DA), 1)

    def test_cancelled_order_still_blocks_delete(self):
        pid = self.client.post("/thuc-don", json={"name": "Thử xóa", "price": 10000, "category_id": 1}).get_json()["id"]
        ma = self.order(items=[{"mon_id": pid, "so_luong": 1}]).get_json()["ma_don"]
        self.status(ma, "Đã hủy", "thử")
        self.assertEqual(self.client.post(f"/thuc-don/{pid}/xoa", json={}).status_code, 409)

    def test_can_delete_never_ordered_product(self):
        pid = self.client.post("/thuc-don", json={"name": "Test", "price": 10000, "category_id": 4}).get_json()["id"]
        self.assertEqual(self.client.post(f"/thuc-don/{pid}/xoa", json={}).status_code, 200)
        self.assertEqual(self.one("SELECT COUNT(*) FROM product WHERE id = ?", pid), 0)

    def test_html_is_escaped(self):
        self.client.post("/thuc-don", json={"name": "<script>alert(1)</script>", "price": 10000, "category_id": 1})
        page = self.client.get("/thuc-don").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        ma = self.order(items=[{"mon_id": PHIN_SUA_DA, "so_luong": 1, "ghi_chu": "<b>x</b>"}]).get_json()["ma_don"]
        self.assertNotIn("<b>x</b>", self.client.get(f"/don-hang/{ma}").get_data(as_text=True))


# ------------------------------------------------------------------ tổng quan

class OverviewTests(Base):
    def test_september_matches_expected_answers(self):
        r = rules.month_report(self.db(), "2026-09")
        self.assertEqual(r["tong_don"], 1451)
        self.assertEqual(r["don_hoan_thanh"], 1392)
        self.assertEqual(r["don_huy"], 59)
        self.assertEqual(r["doanh_thu"], 134_399_000)
        self.assertEqual(r["trung_binh"], round(134_399_000 / 1392))
        self.assertAlmostEqual(r["ty_le_huy"], 59 / 1451 * 100)
        self.assertEqual([(t["name"], t["so_ly"]) for t in r["top5"]],
                         [("Phin Sữa Đá", 210), ("Bạc Xỉu Đá", 194), ("Phin Đen Đá", 169),
                          ("Cappuccino", 108), ("Trà Thạch Vải", 108)])      # hòa 108: doanh thu cao hơn đứng trước
        self.assertEqual({c["name"]: c["doanh_thu"] for c in r["theo_danh_muc"]},
                         {"Cà phê": 72_219_000, "Trà": 30_842_000, "Freeze": 22_660_000, "Bánh ngọt": 8_678_000})
        self.assertEqual(sum(c["doanh_thu"] for c in r["theo_danh_muc"]), r["doanh_thu"])
        self.assertEqual(len(r["theo_ngay"]), 30)
        self.assertEqual(sum(r["theo_ngay"]), r["doanh_thu"])
        self.assertEqual(sum(r["theo_gio"]), r["doanh_thu"])

    def test_other_months(self):
        conn = self.db()
        july = rules.month_report(conn, "2026-07")
        self.assertEqual((july["tong_don"], july["don_hoan_thanh"], july["don_huy"], july["doanh_thu"]),
                         (1514, 1456, 58, 130_785_000))
        aug = rules.month_report(conn, "2026-08")
        self.assertEqual((aug["tong_don"], aug["don_hoan_thanh"], aug["don_huy"], aug["doanh_thu"]),
                         (1584, 1537, 47, 144_605_000))

    def test_empty_month_has_no_errors(self):
        r = rules.month_report(self.db(), "2026-06")
        self.assertEqual((r["doanh_thu"], r["don_hoan_thanh"], r["trung_binh"], r["ty_le_huy"]), (0, 0, 0, 0.0))
        self.assertEqual(r["top5"], [])
        self.login()
        self.assertEqual(self.client.get("/tong-quan?thang=2026-06").status_code, 200)

    def test_bad_month_param_falls_back(self):
        self.login()
        for m in ("abc", "2026-13", "2026-9", "'; DROP TABLE orders;--"):
            self.assertEqual(self.client.get("/tong-quan", query_string={"thang": m}).status_code, 200)
        self.assertEqual(self.n_orders(), 4549)

    def test_page_shows_key_numbers(self):
        self.login("cashier")
        html = self.client.get("/tong-quan?thang=2026-09").get_data(as_text=True)
        self.assertIn("134.399.000 đ", html)
        self.assertIn("Phin Sữa Đá", html)
        self.assertIn("72.219.000 đ", html)

    def test_cancelled_and_open_orders_not_counted(self):
        self.login()
        self.now = datetime(2026, 10, 5, 9, 0, 0)
        a = self.order().get_json()["ma_don"]
        b = self.order().get_json()["ma_don"]
        c = self.order().get_json()["ma_don"]
        self.status(a, "Đã hủy", "x")
        self.finish(b)
        self.status(c, "Đang pha chế")
        r = rules.month_report(self.db(), "2026-10")
        self.assertEqual((r["tong_don"], r["don_hoan_thanh"], r["don_huy"], r["doanh_thu"]), (3, 1, 1, 29000))
        self.assertEqual(r["top5"][0]["so_ly"], 1)


if __name__ == "__main__":
    unittest.main()
