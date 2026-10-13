"""Ứng dụng Flask CoffeeShop."""
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)

from . import db, rules, seed
from .rules import RuleError

BASE_DIR = Path(__file__).resolve().parent.parent
VN_TZ = timezone(timedelta(hours=7))  # Việt Nam không có giờ mùa hè


def vn_now():
    return datetime.now(VN_TZ).replace(tzinfo=None, microsecond=0)


def _env_flag(name, default):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def create_app(config=None):
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
                static_folder=str(BASE_DIR / "static"))
    app.config.update(
        DATABASE=os.environ.get("DATABASE_PATH", str(BASE_DIR / "coffeeshop.db")),
        DATA_DIR=str(BASE_DIR / "data"),
        IMAGE_DIR=str(BASE_DIR / "images" / "products"),
        SHOW_MEDIA=_env_flag("SHOW_MEDIA", "1"),
        MANAGER_PASSWORD=os.environ.get("APP_PASSWORD", ""),
        CASHIER_PASSWORD=os.environ.get("CASHIER_PASSWORD", ""),
        SECRET_KEY=os.environ.get("SECRET_KEY") or None,
        RENDER=bool(os.environ.get("RENDER")),   # Render luôn đặt biến này
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        NOW=vn_now,
    )
    app.json.ensure_ascii = False  # giữ tiếng Việt nguyên dạng trong JSON/tojson
    if config:
        app.config.update(config)

    on_render = bool(app.config["RENDER"])
    if on_render:
        missing = [name for name, key in (("APP_PASSWORD", "MANAGER_PASSWORD"), ("SECRET_KEY", "SECRET_KEY"))
                   if not app.config[key]]
        if missing:
            raise RuntimeError(
                f"Đang chạy trên Render nhưng thiếu biến môi trường: {', '.join(missing)}. "
                "Vào Render → Environment để đặt rồi deploy lại.")
        # Nội dung mô tả và ảnh có bản quyền: không bao giờ nạp lên Internet.
        app.config["SHOW_MEDIA"] = False
    if app.config["CASHIER_PASSWORD"] and not app.config["MANAGER_PASSWORD"]:
        raise RuntimeError("CASHIER_PASSWORD chỉ dùng được khi đã đặt APP_PASSWORD.")
    # Không đặt APP_PASSWORD (chạy trên máy cá nhân) => không hỏi mật khẩu, toàn quyền.
    auth_enabled = bool(app.config["MANAGER_PASSWORD"])
    app.config["AUTH_ENABLED"] = auth_enabled

    def current_role():
        return session.get("role") if auth_enabled else "manager"

    if not app.config["SECRET_KEY"]:
        # Không đặt SECRET_KEY: lưu một khóa ngẫu nhiên cạnh file DB để khởi động lại
        # không làm mọi phiên đăng nhập đang mở bị vô hiệu.
        key_file = Path(app.config["DATABASE"] + ".secret")
        if not key_file.exists():
            key_file.write_text(secrets.token_hex(32))
        app.config["SECRET_KEY"] = key_file.read_text().strip()

    conn = db.connect(app.config["DATABASE"])
    db.init_schema(conn)
    app.config["SEEDED"] = seed.seed_if_empty(conn, app.config["DATA_DIR"], app.config["SHOW_MEDIA"])
    conn.close()

    # ------------------------------------------------------------ tiện ích
    def get_db():
        if "db" not in g:
            g.db = db.connect(app.config["DATABASE"])
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def wants_json():
        return request.is_json or request.path.startswith("/api/") or \
            request.accept_mimetypes.best == "application/json"

    def fail(message, status=400):
        if wants_json():
            return jsonify(error=message), status
        flash(message, "error")
        return redirect(request.referrer or url_for("orders"))

    def login_required(view):
        @wraps(view)
        def wrapper(*a, **kw):
            if current_role() not in ("cashier", "manager"):
                if wants_json():
                    return jsonify(error="Chưa đăng nhập"), 401
                return redirect(url_for("login", next=request.path))
            return view(*a, **kw)
        return wrapper

    def manager_required(view):
        @wraps(view)
        @login_required
        def wrapper(*a, **kw):
            if current_role() != "manager":
                if wants_json():
                    return jsonify(error="Chỉ quản lý được thực hiện thao tác này"), 403
                abort(403)
            return view(*a, **kw)
        return wrapper

    @app.template_filter("vnd")
    def vnd_filter(n):
        return rules.vnd(n)

    @app.context_processor
    def inject():
        return {"role": current_role(), "auth_enabled": auth_enabled,
                "show_media": app.config["SHOW_MEDIA"]}

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", title="Không đủ quyền",
                               message="Chỉ quản lý được vào trang này."), 403

    @app.errorhandler(404)
    def not_found(_e):
        if wants_json():
            return jsonify(error="Không tìm thấy"), 404
        return render_template("error.html", title="Không tìm thấy", message="Trang không tồn tại."), 404

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity(_e):
        return fail("Dữ liệu vi phạm ràng buộc của cơ sở dữ liệu", 409)

    @app.errorhandler(RuleError)
    def rule_error(e):
        return fail(e.message, e.status)

    # ------------------------------------------------------------ đăng nhập
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not auth_enabled:
            return redirect(url_for("order_entry"))
        if request.method == "POST":
            pw = request.form.get("password", "").encode()
            role = None
            # compare_digest chống dò mật khẩu theo thời gian; mật khẩu rỗng không bao giờ khớp.
            if pw and hmac.compare_digest(pw, app.config["MANAGER_PASSWORD"].encode()):
                role = "manager"
            elif pw and app.config["CASHIER_PASSWORD"] and \
                    hmac.compare_digest(pw, app.config["CASHIER_PASSWORD"].encode()):
                role = "cashier"
            if role:
                session.clear()
                session["role"] = role
                nxt = request.args.get("next", "")
                safe = nxt.startswith("/") and not nxt.startswith(("//", "/\\"))
                return redirect(nxt if safe else url_for("order_entry"))
            flash("Mật khẩu không đúng", "error")
            return render_template("login.html"), 401
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login") if auth_enabled else url_for("order_entry"))

    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("order_entry"))

    # ------------------------------------------------------------ gọi món
    @app.route("/goi-mon")
    @login_required
    def order_entry():
        conn = get_db()
        products = [{"id": p["id"], "name": p["name"], "price": p["price"],
                     "category_id": p["category_id"],
                     "image": p["image"] if app.config["SHOW_MEDIA"] else None}
                    for p in rules.list_products(conn, only_active=True)]
        categories = [{"id": c["id"], "name": c["name"]} for c in rules.list_categories(conn)]
        return render_template("order_entry.html", products=products, categories=categories,
                               tables=list(rules.TABLES), payments=rules.PAYMENTS,
                               service_types=rules.SERVICE_TYPES)

    @app.post("/api/orders")
    @login_required
    def api_create_order():
        payload = request.get_json(silent=True)
        result = rules.create_order(get_db(), payload, app.config["NOW"]())
        return jsonify(result), 201

    @app.route("/media/<path:filename>")
    @login_required
    def media(filename):
        if not app.config["SHOW_MEDIA"]:
            abort(404)
        return send_from_directory(app.config["IMAGE_DIR"], Path(filename).name)

    # ------------------------------------------------------------ đơn hàng
    @app.route("/don-hang")
    @login_required
    def orders():
        today = f"{app.config['NOW']():%Y-%m-%d}"
        if "tu" not in request.args and "den" not in request.args:
            tu = den = today
        else:
            tu, den = request.args.get("tu", ""), request.args.get("den", "")
        trang_thai = request.args.get("trang_thai", "")
        loai = request.args.get("loai", "")
        q = request.args.get("q", "").strip()
        try:
            page = int(request.args.get("page", "1"))
        except ValueError:
            page = 1
        rows, total, page, pages = rules.list_orders(get_db(), tu, den, trang_thai, loai, q, page)
        args = {"tu": tu, "den": den, "trang_thai": trang_thai, "loai": loai, "q": q}
        return render_template("orders.html", rows=rows, total=total, page=page, pages=pages,
                               f=args, statuses=rules.STATUSES, service_types=rules.SERVICE_TYPES)

    @app.route("/don-hang/<ma_don>")
    @login_required
    def order_detail(ma_don):
        order, items = rules.get_order(get_db(), ma_don)
        if order is None:
            abort(404)
        return render_template("order_detail.html", order=order, items=items,
                               transitions=rules.TRANSITIONS.get(order["trang_thai"], ()))

    @app.post("/don-hang/<ma_don>/trang-thai")
    @login_required
    def order_status(ma_don):
        data = request.get_json(silent=True) if request.is_json else request.form
        data = data or {}
        rules.change_status(get_db(), ma_don, data.get("trang_thai"), data.get("ly_do"),
                            app.config["NOW"]())
        if wants_json():
            return jsonify(ok=True)
        flash("Đã cập nhật trạng thái đơn", "ok")
        return redirect(url_for("order_detail", ma_don=ma_don))

    @app.route("/don-hang/<ma_don>/xoa", methods=["POST", "DELETE"])
    @login_required
    def order_delete(ma_don):
        # Luôn từ chối (không redirect) – giao diện cũng không có nút xóa đơn.
        return jsonify(error="Hệ thống không cho xóa đơn hàng. Hãy hủy đơn (có lý do) nếu đơn chưa hoàn thành."), 403

    # ------------------------------------------------------------ thực đơn
    @app.route("/thuc-don")
    @login_required
    def menu():
        conn = get_db()
        return render_template("menu.html", products=rules.list_products(conn),
                               categories=rules.list_categories(conn),
                               cat=request.args.get("dm", type=int))

    def _body():
        data = request.get_json(silent=True) if request.is_json else request.form
        return data or {}

    def _menu_done(message, **extra):
        if wants_json():
            return jsonify(ok=True, **extra)
        flash(message, "ok")
        return redirect(url_for("menu"))

    @app.post("/thuc-don")
    @manager_required
    def menu_add():
        d = _body()
        pid = rules.add_product(get_db(), d.get("name"), d.get("price"), d.get("category_id"))
        return _menu_done("Đã thêm món mới", id=pid)

    @app.post("/thuc-don/<int:pid>/sua")
    @manager_required
    def menu_edit(pid):
        d = _body()
        rules.update_product(get_db(), pid, d.get("name"), d.get("price"), d.get("category_id"))
        return _menu_done("Đã lưu thay đổi")

    @app.post("/thuc-don/<int:pid>/ban")
    @manager_required
    def menu_toggle(pid):
        active = str(_body().get("dang_ban", "")) in ("1", "true", "True")
        rules.set_product_active(get_db(), pid, active)
        return _menu_done("Đã bật bán lại" if active else "Đã tạm ngưng món")

    @app.post("/thuc-don/<int:pid>/xoa")
    @manager_required
    def menu_delete(pid):
        rules.delete_product(get_db(), pid)
        return _menu_done("Đã xóa món")

    # ------------------------------------------------------------ tổng quan
    @app.route("/tong-quan")
    @login_required
    def overview():
        conn = get_db()
        now = app.config["NOW"]()
        month = request.args.get("thang", "")
        if not rules.valid_month(month):
            month = f"{now:%Y-%m}"
        report = rules.month_report(conn, month)
        return render_template("overview.html", r=report, months=rules.available_months(conn, now),
                               today_revenue=rules.revenue_today(conn, now), today=f"{now:%d/%m/%Y}")

    return app
