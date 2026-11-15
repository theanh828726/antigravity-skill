"""Hộp thoại đổi mật khẩu (tự phục vụ; bắt buộc khi đăng nhập bằng mật khẩu mặc định)."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from ketoan.services.auth_service import change_password
from ketoan.services.context import BusinessError


class ChangePasswordDialog(QDialog):
    def __init__(self, db, username: str, forced: bool = False, parent=None):
        super().__init__(parent)
        self.db, self.username = db, username
        self.setWindowTitle("Đổi mật khẩu")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(("<b style='color:#B42318'>Bạn đang dùng mật khẩu mặc định – cần đổi trước khi làm việc.</b><br/>" if forced else "")
                             + "Mật khẩu mới tối thiểu 8 ký tự, có cả chữ và số, không trùng tên đăng nhập hoặc mật khẩu mặc định."))
        f = QFormLayout()
        self.old, self.new, self.new2 = QLineEdit(), QLineEdit(), QLineEdit()
        for w in (self.old, self.new, self.new2):
            w.setEchoMode(QLineEdit.Password)
        f.addRow("Mật khẩu hiện tại", self.old)
        f.addRow("Mật khẩu mới", self.new)
        f.addRow("Nhập lại mật khẩu mới", self.new2)
        lay.addLayout(f)
        self.msg = QLabel()
        self.msg.setStyleSheet("color:#B42318")
        lay.addWidget(self.msg)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Đổi mật khẩu")
        bb.button(QDialogButtonBox.Cancel).setText("Thoát" if forced else "Hủy")
        bb.accepted.connect(self.submit)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.old.setFocus()

    def submit(self):
        if self.new.text() != self.new2.text():
            self.msg.setText("Hai lần nhập mật khẩu mới không khớp.")
            return
        try:
            change_password(self.db, self.username, self.old.text(), self.new.text())
        except BusinessError as e:
            self.msg.setText(str(e))
            return
        self.accept()
