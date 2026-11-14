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
from ketoan.data.db import Database


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


def open_or_create(path: Path, demo: bool = True) -> Database:
    from ketoan.data.seed import create_database
    if not path.exists():
        return create_database(path, demo=demo)
    db = Database(path)
    if not db.is_app_database():
        db.close()
        raise RuntimeError(f"File {path} không phải dữ liệu của {APP_NAME}.")
    return db


def switch_database(window, path: str, create: bool = False):
    """Đổi sang file dữ liệu khác: đăng nhập lại trên dữ liệu mới."""
    from ketoan.data.seed import create_database
    from ketoan.services.context import Session
    from ketoan.ui.system_views import LoginDialog
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
    dlg = LoginDialog(db, window, demo_hint=create)
    if create:
        dlg.u.setText("admin")
        dlg.msg.setText("Dữ liệu mới có sẵn tài khoản mặc định – hãy đổi mật khẩu ngay sau khi đăng nhập.")
    if not dlg.exec():
        db.close()
        return
    old = window.session.db
    window.session = Session(db, dlg.user)
    old.close()
    s = load_settings(window.app_dirs)
    s["last_db"] = str(p)
    save_settings(window.app_dirs, s)
    window.reload_all()


def main(argv=None):
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--db", help="Đường dẫn file dữ liệu")
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
    path = Path(args.db or settings.get("last_db") or dirs["data"] / "ketoan_demo.db")
    try:
        if args.reset_demo and path.exists():
            from ketoan.data.seed import create_database
            create_database(path, demo=True).close()
        db = open_or_create(path)
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
    settings["last_db"] = str(path)
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
