"""Điểm khởi chạy ứng dụng.

Cách dùng:
    python main.py                       # mở dữ liệu gần nhất (lần đầu: tự tạo dữ liệu minh họa)
    python main.py --db duong_dan.db     # mở file dữ liệu chỉ định
    python main.py --reset-demo          # tạo lại dữ liệu minh họa
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from ketoan import APP_BRAND, APP_NAME
from ketoan.data.db import SCHEMA_VERSION, Database, PostgresDatabase, is_pg_url, strip_password


def app_dirs() -> dict:
    base = Path(os.environ.get("APPDATA") or Path.home() / ".local" / "share") / APP_BRAND / "KeToan"
    dirs = {"base": base, "data": base / "data", "backup": base / "backup"}
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def _settings_file(dirs):
    return dirs["base"] / "settings.json"


def load_settings(dirs) -> dict:
    try:
        return json.loads(_settings_file(dirs).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(dirs, data: dict):
    _settings_file(dirs).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def open_or_create(target, demo: bool = True):
    """Mở CSDL (file SQLite hoặc URL PostgreSQL), nâng cấp lược đồ nếu cần. File SQLite chưa có → tạo mới."""
    from ketoan.data.seed import create_database
    if is_pg_url(str(target)):
        db = PostgresDatabase(str(target))
        if not db.has_schema():
            db.close()
            raise RuntimeError("CSDL PostgreSQL này chưa có dữ liệu của ứng dụng. Dùng «Kết nối PostgreSQL…» và tích «Khởi tạo» "
                               "(hoặc chạy: python main.py --db <URL> --init).")
    else:
        target = Path(target)
        if not target.exists():
            return create_database(target, demo=demo)
        db = Database(target)
    if not db.is_app_database():
        db.close()
        raise RuntimeError(f"{target} không phải dữ liệu của {APP_NAME}.")
    if db.schema_version() > int(SCHEMA_VERSION):
        db.close()
        raise RuntimeError("Dữ liệu được tạo bởi phiên bản mới hơn của ứng dụng – hãy cập nhật ứng dụng.")
    db.migrate()                       # nâng cấp dữ liệu phiên bản cũ (giao dịch nguyên tử)
    return db


def _login_and_switch(window, db, target: str, new_data: bool = False) -> bool:
    from ketoan.services.context import Session
    from ketoan.ui.system_views import LoginDialog
    dlg = LoginDialog(db, window, demo_hint=new_data)
    if new_data:
        dlg.u.setText("admin")
        dlg.msg.setText("Dữ liệu mới có sẵn tài khoản mặc định – hãy đổi mật khẩu ngay sau khi đăng nhập.")
    if not dlg.exec():
        db.close()
        return False
    old = window.session.db
    window.session = Session(db, dlg.user)
    old.close()
    s = load_settings(window.app_dirs)
    s["last_db"] = strip_password(target) if is_pg_url(target) else str(target)
    save_settings(window.app_dirs, s)
    window.reload_all()
    return True


def switch_database(window, path: str, create: bool = False):
    """Đổi sang file dữ liệu SQLite khác: đăng nhập lại trên dữ liệu mới."""
    from ketoan.data.seed import create_database
    from ketoan.ui.widgets import error
    p = Path(path)
    try:
        if create:
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(window, "Tạo dữ liệu mới", "Tên doanh nghiệp:")
            if not ok:
                return
            db = create_database(p, demo=False, company_name=name.strip() or "Doanh nghiệp mới")
        else:
            db = open_or_create(p)
    except Exception as e:  # noqa: BLE001
        error(window, str(e))
        return
    _login_and_switch(window, db, str(p), new_data=create)


def connect_postgres(window):
    """Hộp thoại kết nối PostgreSQL (nhiều người dùng); có thể khởi tạo CSDL trống."""
    from ketoan.data.seed import create_database
    from ketoan.ui.pg_dialog import PgConnectDialog
    from ketoan.ui.widgets import error
    dlg = PgConnectDialog(window)
    if not dlg.exec():
        return
    url = dlg.url()
    try:
        probe = PostgresDatabase(url)
        has = probe.has_schema()
        probe.close()
        if not has:
            if not dlg.init_new():
                raise RuntimeError("CSDL chưa có dữ liệu của ứng dụng – tích «Khởi tạo CSDL mới» nếu muốn tạo.")
            db = create_database(url, demo=dlg.demo(), company_name=dlg.company())
            new_data = True
        else:
            db, new_data = open_or_create(url), False
    except Exception as e:  # noqa: BLE001
        error(window, f"Không kết nối được PostgreSQL:\n{e}")
        return
    _login_and_switch(window, db, url, new_data=new_data and not dlg.demo())


def main(argv=None):
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--db", help="Đường dẫn file SQLite hoặc URL postgresql://người_dùng[:mật_khẩu]@máy:5432/tên_csdl")
    parser.add_argument("--init", action="store_true", help="Với PostgreSQL: khởi tạo CSDL trống (chưa có dữ liệu) rồi thoát")
    parser.add_argument("--demo", action="store_true", help="Kèm --init: nạp dữ liệu minh họa")
    parser.add_argument("--company", default="", help="Kèm --init: tên doanh nghiệp")
    parser.add_argument("--reset-demo", action="store_true", help="Tạo lại dữ liệu minh họa")
    parser.add_argument("--user", help=argparse.SUPPRESS)
    parser.add_argument("--password", help=argparse.SUPPRESS)
    args, qt_args = parser.parse_known_args(argv)

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_BRAND)
    from ketoan.ui import icons, theme
    app.setFont(theme.app_font())
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)
    app.setWindowIcon(QIcon(icons.logo_pixmap(64)))

    dirs = app_dirs()
    settings = load_settings(dirs)
    target = args.db or settings.get("last_db") or str(dirs["data"] / "ketoan_demo.db")
    try:
        if args.init:
            if not is_pg_url(target):
                raise RuntimeError("--init chỉ dùng với URL PostgreSQL (--db postgresql://...).")
            from ketoan.data.seed import create_database
            create_database(target, demo=args.demo, company_name=args.company).close()
            print("Đã khởi tạo CSDL PostgreSQL.")
            return 0
        if args.reset_demo and not is_pg_url(target) and Path(target).exists():
            from ketoan.data.seed import create_database
            create_database(target, demo=True).close()
        try:
            db = open_or_create(target)
        except Exception as first:  # noqa: BLE001 – PostgreSQL: thiếu/sai mật khẩu → hỏi lại
            if not is_pg_url(target) or "password" not in str(first).lower():
                raise
            from ketoan.ui.pg_dialog import PgConnectDialog
            dlg = PgConnectDialog(None, url=target, allow_init=False)
            if not dlg.exec():
                return 0
            target = dlg.url()
            db = open_or_create(target)
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, APP_NAME, f"Không mở được dữ liệu:\n{e}")
        return 2

    from ketoan.services.context import Session
    from ketoan.ui.system_views import LoginDialog
    if args.user:
        from ketoan.services.auth_service import authenticate
        user = authenticate(db, args.user, args.password or "")
    else:
        dlg = LoginDialog(db, demo_hint=bool(db.scalar("SELECT 1 FROM company WHERE is_demo=1")))
        if not dlg.exec():
            return 0
        user = dlg.user
    settings["last_db"] = strip_password(target) if is_pg_url(target) else str(target)     # không lưu mật khẩu
    save_settings(dirs, settings)

    from ketoan.ui.main_window import MainWindow
    session = Session(db, user)
    w = MainWindow(session, dirs)
    w.showMaximized() if not os.environ.get("KETOAN_WINDOWED") else w.show()
    rc = app.exec()
    db.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
