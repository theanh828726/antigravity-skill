"""Hộp thoại kết nối PostgreSQL (bản nhiều người dùng)."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QSpinBox, QVBoxLayout)

from ketoan.data.db import PostgresDatabase, make_pg_url, parse_pg_url


class PgConnectDialog(QDialog):
    def __init__(self, parent=None, url: str | None = None, allow_init: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Kết nối PostgreSQL (nhiều người dùng)")
        self.setMinimumWidth(520)
        c = parse_pg_url(url) if url else {"host": "localhost", "port": 5432, "dbname": "ketoan", "user": "ketoan", "password": None}
        lay = QVBoxLayout(self)
        note = QLabel("Nhiều người dùng cùng làm việc trên một máy chủ PostgreSQL; mỗi người đăng nhập bằng tài khoản của ứng dụng. "
                      "Mật khẩu CSDL <b>không được lưu</b> – để trống nếu máy đã cấu hình ~/.pgpass hoặc biến PGPASSWORD. "
                      "Nên dùng kết nối nội bộ hoặc VPN/TLS (thêm <code>?sslmode=require</code> bằng tham số --db).")
        note.setWordWrap(True)
        note.setObjectName("Hint")
        lay.addWidget(note)
        f = QFormLayout()
        self.host, self.dbname, self.user = QLineEdit(c["host"]), QLineEdit(c["dbname"]), QLineEdit(c["user"] or "")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(c["port"])
        self.pwd = QLineEdit(c["password"] or "")
        self.pwd.setEchoMode(QLineEdit.Password)
        for lab, w in (("Máy chủ", self.host), ("Cổng", self.port), ("Tên CSDL", self.dbname), ("Người dùng CSDL", self.user), ("Mật khẩu CSDL", self.pwd)):
            f.addRow(lab, w)
        lay.addLayout(f)
        self.chk_init = QCheckBox("Khởi tạo CSDL mới nếu CSDL này chưa có dữ liệu của ứng dụng")
        self.chk_demo = QCheckBox("Kèm dữ liệu minh họa (chỉ để thử nghiệm)")
        self._company_edit = QLineEdit()
        self._company_edit.setPlaceholderText("Tên doanh nghiệp (khi khởi tạo không có dữ liệu minh họa)")
        for w in (self.chk_init, self.chk_demo, self._company_edit):
            lay.addWidget(w)
            w.setVisible(allow_init)
        self.msg = QLabel()
        lay.addWidget(self.msg)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Kết nối")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        test = bb.addButton("Kiểm tra kết nối", QDialogButtonBox.ActionRole)
        test.clicked.connect(self.test)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def url(self) -> str:
        return make_pg_url(self.host.text().strip(), self.port.value(), self.dbname.text().strip(), self.user.text().strip(), self.pwd.text() or None)

    def init_new(self) -> bool:
        return self.chk_init.isChecked()

    def demo(self) -> bool:
        return self.chk_demo.isChecked()

    def company(self) -> str:
        return self._company_edit.text().strip() or "Doanh nghiệp mới"

    def test(self):
        try:
            db = PostgresDatabase(self.url())
            has = db.has_schema()
            db.close()
            self.msg.setText("<span style='color:#1E7A34'>Kết nối được. " + ("CSDL đã có dữ liệu ứng dụng." if has else "CSDL chưa có dữ liệu ứng dụng.") + "</span>")
        except Exception as e:  # noqa: BLE001
            self.msg.setText(f"<span style='color:#B42318'>Không kết nối được: {e}</span>")
