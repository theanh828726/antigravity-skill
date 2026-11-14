"""Trung tâm cảnh báo và các màn hình hệ thống."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from ketoan import APP_BRAND, APP_NAME, APP_VERSION
from ketoan.domain.constants import PERMISSIONS, SEV_BLOCK, SEV_INFO, SEV_LABEL, SEV_REVIEW
from ketoan.services.alert_service import AlertService
from ketoan.services.auth_service import UserService
from ketoan.services.closing_service import ClosingService
from ketoan.services.period_service import PeriodService
from ketoan.services.system_service import AuditService, BackupService, CompanyService
from ketoan.ui import icons, theme
from ketoan.ui.widgets import (DateEdit, ExportBar, ReportTable, SectionHeader, confirm, info, run, tool_button, vn_date)

SEV_COLOR = {SEV_BLOCK: "#B42318", SEV_REVIEW: "#9A6700", SEV_INFO: "#1F5FA8"}


# ================================================================ Trung tâm cảnh báo
class AlertView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        bar = QHBoxLayout()
        t = QLabel("TRUNG TÂM CẢNH BÁO – KIỂM TRA VÀ ĐỐI CHIẾU")
        t.setObjectName("PageTitle")
        bar.addWidget(t)
        bar.addSpacing(10)
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        bar.addWidget(QLabel("Từ"))
        bar.addWidget(self.d_from)
        bar.addWidget(QLabel("đến"))
        bar.addWidget(self.d_to)
        self.cb_sev = QComboBox()
        self.cb_sev.addItem("Mọi mức độ", None)
        for k in (SEV_BLOCK, SEV_REVIEW, SEV_INFO):
            self.cb_sev.addItem(SEV_LABEL[k], k)
        self.cb_sev.currentIndexChanged.connect(self._render)
        bar.addWidget(self.cb_sev)
        b = tool_button("Kiểm tra lại", "refresh", "primary")
        b.clicked.connect(self.refresh)
        bar.addWidget(b)
        bar.addStretch(1)
        self.table = ReportTable()
        bar.addWidget(ExportBar(self.table, lambda: ("Danh sách cảnh báo kiểm tra – đối chiếu",
                                                     f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())}"),
                                self.s, self, True, []))
        root.addLayout(bar)
        cards = QHBoxLayout()
        self.cards = {}
        for k in (SEV_BLOCK, SEV_REVIEW, SEV_INFO):
            lab = QLabel()
            lab.setStyleSheet(f"background:white;border:1px solid {theme.BORDER};border-left:5px solid {SEV_COLOR[k]};"
                              "border-radius:4px;padding:5px 10px;")
            cards.addWidget(lab, 1)
            self.cards[k] = lab
        root.addLayout(cards)
        root.addWidget(self.table, 1)
        note = QLabel("Trung tâm cảnh báo chỉ PHÁT HIỆN và chỉ ra nơi xử lý; không tự sửa dữ liệu kế toán. "
                      "Nhấp đúp (hoặc Enter) để mở chứng từ / sổ liên quan.")
        note.setObjectName("Hint")
        root.addWidget(note)
        self.table.rowActivated.connect(self.open_target)
        self.alerts = []
        self.refresh()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        self.alerts = AlertService(self.s).collect(self.d_from.iso(), self.d_to.iso())
        self._render()

    def _render(self):
        sev = self.cb_sev.currentData()
        rows = [a for a in self.alerts if not sev or a.severity == sev]
        for k, lab in self.cards.items():
            n = sum(1 for a in self.alerts if a.severity == k)
            lab.setText(f"<span style='color:{SEV_COLOR[k]};font-weight:700;font-size:13pt'>{n}</span>&nbsp; {SEV_LABEL[k]}")
        self.table.fill(["Mức độ", "Nhóm kiểm tra", "Chứng từ liên quan", "Nguyên nhân", "Số chênh lệch", "Xử lý"],
                        [[SEV_LABEL[a.severity], a.group, a.voucher_label, a.message, a.difference,
                          {"voucher": "Mở chứng từ ▸", "costing": "Tính giá ▸"}.get(a.target[0] if a.target else "", "Mở sổ ▸")] for a in rows],
                        money_cols={4}, widths=[110, 230, 150, 520, 110, 100], keys=[i for i in range(len(rows))],
                        stretch_col=3)
        self._shown = rows
        for i, a in enumerate(rows):
            self.table.item(i, 0).setForeground(QColor(SEV_COLOR[a.severity]))
            self.table.item(i, 5).setForeground(QColor(theme.PRIMARY))

    def open_target(self, idx):
        a = self._shown[idx]
        t = a.target
        if not t:
            return
        if t[0] == "voucher":
            self.ctx.open_voucher(t[1])
        elif t[0] == "account_detail":
            self.ctx.open("r_sct", account=t[1], partner_id=t[2], d_from=self.d_from.iso(), d_to=self.d_to.iso(),
                          new_tab=True)
        elif t[0] == "opening_balance":
            self.ctx.open("c_opening")
        elif t[0] == "opening_stock":
            self.ctx.open("c_opening_stock")
        elif t[0] == "costing":
            self.ctx.open("m_tinhgia")
        elif t[0] == "trial_balance":
            self.ctx.open("r_cdps")


# ================================================================ Khóa sổ
class PeriodLockView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.ps = PeriodService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 8)
        self.heading = QLabel()
        self.heading.setObjectName("PageTitle")
        root.addWidget(self.heading)
        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        root.addLayout(self.grid)
        hint = QLabel("Khóa kỳ: không thể thêm, sửa, xóa, bỏ ghi sổ chứng từ có ngày hạch toán trong kỳ. "
                      "Mở khóa theo thứ tự từ kỳ sau về kỳ trước. Cần quyền «Khóa / mở khóa kỳ».")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)
        self.refresh()

    def refresh(self):
        y = self.s.year
        self.heading.setText(f"KHÓA SỔ KỲ KẾ TOÁN – NĂM {y}")
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        locked = self.ps.locked_months(y)
        for m in range(1, 13):
            box = QGroupBox(f"Tháng {m:02d}/{y}")
            bl = QVBoxLayout(box)
            pending = self.ps.pending_vouchers(y, m)
            if m in locked:
                ts = locked[m][1] or ""
                st = QLabel(f"<b style='color:#5B2D90'>🔒 Đã khóa</b><br/><span style='color:#5E6B7A'>{locked[m][0]} · "
                            f"{vn_date(ts[:10])} {ts[11:16]}</span>")
                b = QPushButton("Mở khóa")
                b.clicked.connect(lambda _=False, mm=m: self._do(self.ps.unlock, mm, "Mở khóa"))
            else:
                st = QLabel("<b style='color:#1E7A34'>Đang mở</b>" + (f"<br/><span style='color:#9A6700'>{pending} CT chưa ghi sổ"
                                                                       "</span>" if pending else "<br/>&nbsp;"))
                b = QPushButton("Khóa kỳ")
                b.setProperty("role", "primary")
                b.clicked.connect(lambda _=False, mm=m, pp=pending: self._lock(mm, pp))
            b.setEnabled(self.s.user.can("lock"))
            bl.addWidget(st)
            bl.addWidget(b)
            self.grid.addWidget(box, (m - 1) // 6, (m - 1) % 6)

    def _lock(self, m, pending):
        msg = f"Khóa sổ tháng {m:02d}/{self.s.year}?"
        if pending:
            msg += f"\n\nCảnh báo: còn {pending} chứng từ chưa ghi sổ trong kỳ – sau khi khóa sẽ không ghi sổ được."
        if confirm(self, msg):
            self._do(self.ps.lock, m, "Khóa")

    def _do(self, fn, m, _label):
        ok, _ = run(self, fn, self.s.year, m)
        if ok:
            self.refresh()
            self.ctx.voucher_changed()


# ================================================================ Người dùng & phân quyền
class UserDialog(QDialog):
    def __init__(self, roles, rec=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sửa người dùng" if rec else "Thêm người dùng")
        f = QFormLayout(self)
        self.username = QLineEdit(rec["username"] if rec else "")
        self.username.setReadOnly(bool(rec))
        self.full = QLineEdit(rec["full_name"] if rec else "")
        self.role = QComboBox()
        for r in roles:
            self.role.addItem(r["name"], r["code"])
        if rec:
            self.role.setCurrentIndex(self.role.findData(rec["role_code"]))
        self.active = QCheckBox("Đang hoạt động")
        self.active.setChecked(bool(rec["active"]) if rec else True)
        self.pwd = QLineEdit()
        self.pwd.setEchoMode(QLineEdit.Password)
        self.pwd.setPlaceholderText("Để trống nếu không đổi" if rec else "Tối thiểu 6 ký tự")
        for lab, w in (("Tên đăng nhập", self.username), ("Họ tên", self.full), ("Vai trò", self.role), ("", self.active),
                       ("Mật khẩu", self.pwd)):
            f.addRow(lab, w)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Lưu")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class UsersView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = UserService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        t = QLabel("NGƯỜI DÙNG & PHÂN QUYỀN")
        t.setObjectName("PageTitle")
        root.addWidget(t)
        root.addWidget(SectionHeader("Người dùng"))
        bar = QHBoxLayout()
        for text, ic, fn in (("Thêm", "add", self.add), ("Sửa", "edit", self.edit)):
            b = tool_button(text, ic)
            b.clicked.connect(fn)
            b.setEnabled(self.s.user.can("admin"))
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)
        self.users = ReportTable()
        self.users.rowActivated.connect(lambda _: self.edit())
        root.addWidget(self.users, 2)
        root.addWidget(SectionHeader("Ma trận phân quyền theo vai trò"))
        self.matrix = QTableWidget()
        self.matrix.verticalHeader().setVisible(False)
        root.addWidget(self.matrix, 2)
        bb = QHBoxLayout()
        bb.addStretch(1)
        self.b_save = tool_button("Lưu phân quyền", "save", "primary")
        self.b_save.clicked.connect(self.save_perms)
        self.b_save.setEnabled(self.s.user.can("admin"))
        bb.addWidget(self.b_save)
        root.addLayout(bb)
        self.refresh()

    def refresh(self):
        rows = self.svc.users()
        self.urows = rows
        self.users.fill(["Tên đăng nhập", "Họ tên", "Vai trò", "Trạng thái"],
                        [[r["username"], r["full_name"], r["role_name"], "Hoạt động" if r["active"] else "Đã khóa"] for r in rows],
                        widths=[140, 260, 180, 100], keys=[r["id"] for r in rows], stretch_col=1)
        roles = self.svc.roles()
        self.roles = roles
        self.matrix.setColumnCount(len(PERMISSIONS) + 1)
        self.matrix.setHorizontalHeaderLabels(["Vai trò"] + [p[1] for p in PERMISSIONS])
        self.matrix.setRowCount(len(roles))
        for i, r in enumerate(roles):
            self.matrix.setItem(i, 0, QTableWidgetItem(r["name"]))
            perms = set(r["permissions"].split(","))
            for j, (code, _) in enumerate(PERMISSIONS, 1):
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                it.setCheckState(Qt.Checked if code in perms else Qt.Unchecked)
                self.matrix.setItem(i, j, it)
        self.matrix.setColumnWidth(0, 170)
        for j in range(1, len(PERMISSIONS) + 1):
            self.matrix.setColumnWidth(j, 120)

    def _current(self):
        r = self.users.currentRow()
        return self.urows[r] if 0 <= r < len(self.urows) else None

    def add(self):
        dlg = UserDialog(self.roles, None, self)
        if dlg.exec():
            ok, _ = run(self, self.svc.save_user, None, dlg.username.text().strip(), dlg.full.text(), dlg.role.currentData(),
                        dlg.active.isChecked(), dlg.pwd.text())
            if ok:
                self.refresh()

    def edit(self):
        rec = self._current()
        if not rec:
            return
        dlg = UserDialog(self.roles, rec, self)
        if dlg.exec():
            ok, _ = run(self, self.svc.save_user, rec["id"], rec["username"], dlg.full.text(), dlg.role.currentData(),
                        dlg.active.isChecked(), dlg.pwd.text())
            if ok:
                self.refresh()

    def save_perms(self):
        for i, r in enumerate(self.roles):
            perms = {code for j, (code, _) in enumerate(PERMISSIONS, 1) if self.matrix.item(i, j).checkState() == Qt.Checked}
            ok, _ = run(self, self.svc.save_role_permissions, r["code"], perms)
            if not ok:
                return
        info(self, "Đã lưu phân quyền. Thay đổi có hiệu lực từ lần đăng nhập sau.")


# ================================================================ Nhật ký thay đổi
class AuditView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        bar = QHBoxLayout()
        t = QLabel("NHẬT KÝ THAY ĐỔI")
        t.setObjectName("PageTitle")
        bar.addWidget(t)
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Người dùng, thao tác, số chứng từ…")
        self.search.returnPressed.connect(self.refresh)
        for w in (QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to, self.search):
            bar.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        bar.addWidget(b)
        self.table = ReportTable()
        bar.addWidget(ExportBar(self.table, lambda: ("Nhật ký thay đổi dữ liệu", ""), self.s, self, True, []))
        root.addLayout(bar)
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        rows = AuditService(self.s).rows(self.d_from.iso(), self.d_to.iso(), self.search.text().strip())
        self.table.fill(["Thời điểm", "Người dùng", "Thao tác", "Đối tượng", "Mã", "Chi tiết"],
                        [[r["ts"].replace("T", " "), r["username"], r["action"], r["entity"], r["entity_id"], r["detail"] or ""]
                         for r in rows], widths=[140, 110, 170, 110, 140, 500], stretch_col=5)


# ================================================================ Sao lưu – khôi phục
class BackupView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = BackupService(self.s, ctx.backup_dir)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        t = QLabel("SAO LƯU – KHÔI PHỤC DỮ LIỆU")
        t.setObjectName("PageTitle")
        root.addWidget(t)
        info_lab = QLabel(f"Dữ liệu đang mở: <b>{self.s.db.path}</b><br/>Thư mục sao lưu: <b>{ctx.backup_dir}</b><br/>"
                          "Khôi phục sẽ tự động sao lưu dữ liệu hiện tại trước khi ghi đè (file «truoc_khoi_phuc_…»).")
        info_lab.setWordWrap(True)
        root.addWidget(info_lab)
        bar = QHBoxLayout()
        for text, ic, role, fn in (("Sao lưu ngay", "backup", "primary", self.backup),
                                   ("Sao lưu ra file…", "save", None, self.backup_as),
                                   ("Khôi phục từ bản đã chọn", "refresh", None, self.restore_selected),
                                   ("Khôi phục từ file…", "open", None, self.restore_file)):
            b = tool_button(text, ic, role)
            b.clicked.connect(fn)
            b.setEnabled(self.s.user.can("admin"))
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)
        self.table = ReportTable()
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        from datetime import datetime
        files = self.svc.list_backups()
        self.files = files
        self.table.fill(["File sao lưu", "Thời điểm", "Dung lượng (KB)"],
                        [[f.name, datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
                          f"{f.stat().st_size / 1024:,.0f}".replace(",", ".")] for f in files],
                        widths=[380, 170, 130], keys=list(range(len(files))))

    def backup(self):
        ok, p = run(self, self.svc.backup)
        if ok:
            info(self, f"Đã sao lưu: {p}")
            self.refresh()

    def backup_as(self):
        p, _ = QFileDialog.getSaveFileName(self, "Sao lưu ra file", "ketoan_saoluu.db", "Dữ liệu kế toán (*.db)")
        if p:
            ok, _ = run(self, self.svc.backup, p)
            if ok:
                info(self, f"Đã sao lưu: {p}")

    def _restore(self, path):
        if not confirm(self, f"Khôi phục dữ liệu từ:\n{path}\n\nDữ liệu hiện tại sẽ được sao lưu tự động rồi bị thay thế. "
                             "Tất cả tab đang mở sẽ được đóng. Tiếp tục?"):
            return
        ok, safety = run(self, self.svc.restore, path)
        if ok:
            info(self, f"Đã khôi phục. Bản an toàn của dữ liệu trước khi khôi phục: {safety}")
            self.ctx.reload_all()

    def restore_selected(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.files):
            self._restore(self.files[r])

    def restore_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file sao lưu", str(self.ctx.backup_dir), "Dữ liệu kế toán (*.db)")
        if p:
            self._restore(p)


# ================================================================ Doanh nghiệp & chế độ kế toán
class CompanyView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = CompanyService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        t = QLabel("DOANH NGHIỆP & CHẾ ĐỘ KẾ TOÁN")
        t.setObjectName("PageTitle")
        root.addWidget(t)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)
        # --- thông tin doanh nghiệp
        w1 = QWidget()
        f = QFormLayout(w1)
        c = self.s.company
        self.ed = {}
        for key, lab in (("name", "Tên doanh nghiệp"), ("tax_code", "Mã số thuế"), ("address", "Địa chỉ"),
                         ("business", "Lĩnh vực hoạt động"), ("director", "Giám đốc"), ("chief_accountant", "Kế toán trưởng")):
            e = QLineEdit(c[key] or "")
            self.ed[key] = e
            f.addRow(lab, e)
        b = tool_button("Lưu thông tin", "save", "primary")
        b.clicked.connect(self.save_company)
        b.setEnabled(self.s.user.can("admin"))
        f.addRow("", b)
        from ketoan.services.inventory_service import METHODS, InventoryService
        self.inv = InventoryService(self.s)
        self.cb_cost = QComboBox()
        for k, v in METHODS.items():
            self.cb_cost.addItem(v, k)
        self.cb_cost.setCurrentIndex(max(0, self.cb_cost.findData(self.inv.method())))
        bm = tool_button("Áp dụng phương pháp", "check")
        bm.clicked.connect(self.save_method)
        bm.setEnabled(self.s.user.can("admin"))
        row = QHBoxLayout()
        row.addWidget(self.cb_cost)
        row.addWidget(bm)
        row.addStretch(1)
        f.addRow("Tính giá xuất kho", row)
        note = QLabel("Phương pháp tính giá phải áp dụng nhất quán trong năm tài chính; thay đổi được ghi nhật ký. "
                      "Bình quân gia quyền cuối kỳ tính theo tháng, theo mã hàng + kho; FIFO theo ngày hạch toán.")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        f.addRow("", note)
        tabs.addTab(w1, "Thông tin doanh nghiệp")
        # --- chế độ kế toán (phiên bản)
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        warn = QLabel("⚠ Các chế độ kế toán, mẫu hệ thống tài khoản và mẫu báo cáo đi kèm đều ở trạng thái <b>CHƯA KIỂM "
                      "CHỨNG</b>. Trước khi áp dụng thực tế, cần đối chiếu văn bản gốc, hiệu lực và phạm vi áp dụng từ nguồn "
                      "chính thức. Việc áp dụng được lưu theo ngày hiệu lực (có lịch sử), không ghi đè kỳ trước.")
        warn.setWordWrap(True)
        warn.setStyleSheet("background:#FFF8E6;border:1px solid #F0D58C;border-radius:4px;padding:6px;")
        l2.addWidget(warn)
        self.reg_table = ReportTable()
        l2.addWidget(QLabel("<b>Danh mục chế độ kế toán</b>"))
        l2.addWidget(self.reg_table)
        self.hist = ReportTable()
        l2.addWidget(QLabel("<b>Lịch sử áp dụng của doanh nghiệp</b>"))
        l2.addWidget(self.hist)
        bar = QHBoxLayout()
        self.cb_reg = QComboBox()
        for r in self.svc.regimes():
            self.cb_reg.addItem(f"{r['legal_ref']} – {r['name']}", r["code"])
        self.reg_from = DateEdit(f"{self.s.year}-01-01")
        b2 = tool_button("Áp dụng từ ngày", "check", "primary")
        b2.clicked.connect(self.apply_regime)
        b2.setEnabled(self.s.user.can("admin"))
        for w in (QLabel("Chế độ"), self.cb_reg, QLabel("Hiệu lực từ"), self.reg_from, b2):
            bar.addWidget(w)
        bar.addStretch(1)
        l2.addLayout(bar)
        tabs.addTab(w2, "Chế độ kế toán")
        # --- thuế suất
        w3 = QWidget()
        l3 = QVBoxLayout(w3)
        n3 = QLabel("Bảng thuế suất GTGT là <b>cấu hình mẫu chưa kiểm chứng</b>; mức áp dụng thay đổi theo thời kỳ và văn bản "
                    "hướng dẫn. Ứng dụng không tự suy đoán thuế suất – người dùng chọn thuế suất trên từng dòng chứng từ.")
        n3.setWordWrap(True)
        l3.addWidget(n3)
        self.tax = ReportTable()
        l3.addWidget(self.tax, 1)
        tabs.addTab(w3, "Thuế suất GTGT")
        self.refresh()

    def refresh(self):
        regs = self.svc.regimes()
        self.reg_table.fill(["Mã", "Văn bản", "Tên chế độ", "Hiệu lực từ", "Kiểm chứng", "Ghi chú"],
                            [[r["code"], r["legal_ref"], r["name"], vn_date(r["effective_from"]),
                              "Đã kiểm chứng" if r["verified"] else "Chưa kiểm chứng", r["note"] or ""] for r in regs],
                            widths=[100, 170, 260, 90, 110, 500], stretch_col=5)
        self.reg_table.setMaximumHeight(130)
        hist = self.svc.regime_history()
        self.hist.fill(["Áp dụng từ ngày", "Văn bản", "Tên chế độ", "Kiểm chứng"],
                       [[vn_date(h["effective_from"]), h["legal_ref"], h["name"],
                         "Đã kiểm chứng" if h["verified"] else "Chưa kiểm chứng"] for h in hist],
                       widths=[120, 200, 320, 130])
        self.hist.setMaximumHeight(110)
        self.tax.fill(["Mã", "Tên", "Thuế suất (%)", "Hiệu lực từ", "Căn cứ", "Kiểm chứng"],
                      [[r["code"], r["name"], r["rate"], vn_date(r["effective_from"]), r["legal_ref"],
                        "Đã kiểm chứng" if r["verified"] else "Chưa kiểm chứng"] for r in self.svc.tax_rates()],
                      widths=[70, 260, 100, 100, 420, 120])

    def save_company(self):
        ok, _ = run(self, self.svc.update_company, {k: e.text() for k, e in self.ed.items()})
        if ok:
            info(self, "Đã lưu thông tin doanh nghiệp.")
            self.ctx.company_info_changed()

    def save_method(self):
        if confirm(self, f"Áp dụng phương pháp «{self.cb_cost.currentText()}» cho doanh nghiệp?\n"
                         "Nên chạy lại «Tính giá xuất kho» cho các tháng chưa khóa sau khi đổi."):
            ok, _ = run(self, self.inv.set_method, self.cb_cost.currentData())
            if ok:
                info(self, "Đã cập nhật phương pháp tính giá xuất kho.")

    def apply_regime(self):
        if confirm(self, f"Áp dụng «{self.cb_reg.currentText()}» từ ngày {vn_date(self.reg_from.iso())}?"):
            ok, _ = run(self, self.svc.set_regime, self.cb_reg.currentData(), self.reg_from.iso())
            if ok:
                self.refresh()
                self.ctx.company_info_changed()


# ================================================================ Kết chuyển cuối kỳ
class ClosingDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx, self.s = ctx, ctx.session
        self.cs = ClosingService(self.s)
        self.setWindowTitle("Kết chuyển cuối kỳ – xem trước")
        self.resize(900, 560)
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (QLabel("Kỳ kết chuyển: từ"), self.d_from, QLabel("đến"), self.d_to):
            bar.addWidget(w)
        b = tool_button("Xem trước", "search")
        b.clicked.connect(self.refresh)
        bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)
        note = QLabel("Kết chuyển doanh thu, thu nhập (511, 515, 711) và chi phí (632, 635, 642, 811, 821) sang 911, kết quả "
                      "sang 4212. Không tự tính thuế TNDN. Chứng từ kết chuyển ghi sổ vào ngày cuối kỳ và có thể hoàn tác khi "
                      "kỳ chưa khóa.")
        note.setWordWrap(True)
        note.setObjectName("Hint")
        lay.addWidget(note)
        lay.addWidget(SectionHeader("Bút toán dự kiến"))
        self.table = ReportTable()
        lay.addWidget(self.table, 2)
        lay.addWidget(SectionHeader("Chứng từ kết chuyển đã có trong kỳ"))
        self.hist = ReportTable()
        lay.addWidget(self.hist, 1)
        bb = QHBoxLayout()
        bb.addStretch(1)
        self.b_exec = tool_button("Thực hiện kết chuyển", "post", "post")
        self.b_undo = tool_button("Hoàn tác chứng từ đã chọn", "unpost")
        close = tool_button("Đóng", "cancel")
        self.b_exec.clicked.connect(self.execute)
        self.b_undo.clicked.connect(self.undo)
        close.clicked.connect(self.reject)
        for w in (self.b_exec, self.b_undo, close):
            bb.addWidget(w)
        lay.addLayout(bb)
        self.hist.rowActivated.connect(lambda vid: (self.ctx.open_voucher(vid), self.accept()))
        self.refresh()

    def refresh(self):
        lines = self.cs.preview(self.d_from.iso(), self.d_to.iso())
        self.table.fill(["Diễn giải", "TK Nợ", "TK Có", "Số tiền"],
                        [[l["description"], l["debit_account"], l["credit_account"], l["amount"]] for l in lines],
                        money_cols={3}, widths=[440, 90, 90, 160], center_cols={1, 2}, stretch_col=0)
        hist = self.cs.history(self.d_from.iso(), self.d_to.iso())
        self.hist.fill(["Số CT", "Ngày hạch toán", "Diễn giải", "Số tiền"],
                       [[h["number"], vn_date(h["posting_date"]), h["description"], h["total_amount"]] for h in hist],
                       money_cols={3}, widths=[90, 110, 450, 150], keys=[h["id"] for h in hist], stretch_col=2)
        self.b_exec.setEnabled(bool(lines) and self.s.user.can("post"))
        self.b_undo.setEnabled(bool(hist) and self.s.user.can("post"))

    def execute(self):
        if confirm(self, f"Tạo và ghi sổ chứng từ kết chuyển từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())}?"):
            ok, vid = run(self, self.cs.execute, self.d_from.iso(), self.d_to.iso())
            if ok:
                self.ctx.voucher_changed()
                self.refresh()
                info(self, "Đã kết chuyển và ghi sổ. Nhấp đúp chứng từ ở bảng dưới để xem.")

    def undo(self):
        r = self.hist.currentRow()
        it = self.hist.item(r, 0) if r >= 0 else None
        vid = it.data(Qt.UserRole + 1) if it else None
        if vid and confirm(self, "Hoàn tác (bỏ ghi sổ và xóa) chứng từ kết chuyển đã chọn?"):
            ok, _ = run(self, self.cs.undo, vid)
            if ok:
                self.ctx.voucher_changed()
                self.refresh()


# ================================================================ Trợ giúp
HELP_HTML = f"""
<h2 style="color:{theme.NAVY}">{APP_NAME} – {APP_BRAND}</h2>
<p>Phiên bản {APP_VERSION}. Luồng dữ liệu: <b>Danh mục → Nhập chứng từ → Kiểm tra → Ghi sổ → Sổ kế toán → Báo cáo</b>.
Chỉ chứng từ <b>Đã ghi sổ</b> mới lên sổ sách; mọi dòng sổ đều truy ngược được về chứng từ gốc (nhấp đúp).</p>
<h3>Phím tắt</h3>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>Phím</th><th>Chức năng</th><th>Phím</th><th>Chức năng</th></tr>
<tr><td>F5</td><td>Cập nhật tab hiện tại theo kỳ đang chọn</td><td>Ctrl+N</td><td>Thêm chứng từ</td></tr>
<tr><td>Ctrl+S</td><td>Lưu</td><td>F2</td><td>Sửa</td></tr>
<tr><td>Esc</td><td>Hủy thay đổi</td><td>F6</td><td>Kiểm tra</td></tr>
<tr><td>F9</td><td>Ghi sổ</td><td>Ctrl+F9</td><td>Bỏ ghi sổ</td></tr>
<tr><td>Insert</td><td>Thêm dòng</td><td>Ctrl+D</td><td>Sao chép dòng</td></tr>
<tr><td>Ctrl+Delete</td><td>Xóa dòng</td><td>Ctrl+V</td><td>Dán nhiều dòng từ Excel</td></tr>
<tr><td>F3</td><td>Tìm danh mục cho ô đang chọn</td><td>Enter</td><td>Sang ô kế tiếp / mở dòng</td></tr>
<tr><td>Ctrl+P</td><td>Xem trước khi in</td><td>Ctrl+W</td><td>Đóng tab</td></tr>
<tr><td>Ctrl+Tab</td><td>Chuyển tab</td><td>Ctrl+B</td><td>Thu gọn / mở rộng menu trái</td></tr>
<tr><td>F1</td><td>Trợ giúp</td><td>Ctrl+Shift+A</td><td>Trung tâm cảnh báo</td></tr>
</table>
<h3>Trạng thái chứng từ</h3>
<p><b>Nháp</b> (vừa lưu, có thể còn lỗi) → <b>Đã kiểm tra</b> (không còn lỗi chặn) → <b>Đã ghi sổ</b> (đã lên sổ) →
<b>Đã khóa kỳ</b> (kỳ đã khóa, không sửa/bỏ ghi sổ được). Sửa chứng từ đã ghi sổ: «Bỏ ghi sổ» trước.</p>
<h3>Giai đoạn 2 (đã triển khai)</h3>
<p>Quản lý công nợ (tổng hợp theo đối tượng/MST, chi tiết hóa đơn – hạn thanh toán, tuổi nợ, biên bản đối chiếu), tồn kho
đầu kỳ, nhập – xuất – tồn, thẻ kho, <b>tính giá xuất kho</b> (bình quân gia quyền cuối tháng / FIFO, có xem trước),
xuất kho hàng loạt từ bảng kê bán, đối chiếu doanh thu – giá vốn, đọc hóa đơn điện tử XML, cảnh báo tồn quỹ âm và
bán hàng chưa ghi giá vốn.</p>
<h3>Phạm vi giai đoạn 1</h3>
<p>Đã triển khai: giao diện tổng quan, danh mục (kèm nhập Excel), số dư đầu kỳ, nhập chứng từ, kiểm tra, ghi sổ / bỏ ghi
sổ, nhật ký chung, sổ cái, sổ chi tiết tài khoản, sổ quỹ, sổ tiền gửi, bảng cân đối số phát sinh, trung tâm cảnh báo, kết
chuyển cuối kỳ (xem trước + hoàn tác), khóa kỳ, phân quyền, nhật ký thay đổi, sao lưu – khôi phục, xuất Excel/PDF/in.</p>
<p>Các ô có nhãn <b>GĐ3</b> là chức năng chưa triển khai: TSCĐ, CCDC, giá thành, báo cáo tài chính theo mẫu, hỗ trợ
thuế, in hồ sơ.</p>
<h3>Lưu ý pháp lý</h3>
<p>Chế độ kế toán, hệ thống tài khoản, thuế suất trong dữ liệu mẫu chưa được kiểm chứng; cần đối chiếu văn bản gốc
trước khi áp dụng. Báo cáo của ứng dụng là báo cáo hỗ trợ tính toán, không phải tờ khai điện tử theo cấu trúc của cơ
quan tiếp nhận.</p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trợ giúp")
        self.resize(820, 620)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setHtml(HELP_HTML)
        lay.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Đóng")
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


# ================================================================ Đăng nhập
class LoginDialog(QDialog):
    def __init__(self, db, parent=None, demo_hint=True):
        super().__init__(parent)
        from ketoan.services.auth_service import authenticate
        self._auth = authenticate
        self.db, self.user = db, None
        self.setWindowTitle(f"Đăng nhập – {APP_NAME}")
        self.setFixedWidth(400)
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(46))
        head.addWidget(logo)
        head.addWidget(QLabel(f"<span style='font-size:13pt;font-weight:700;color:{theme.NAVY}'>{APP_NAME.upper()}</span><br/>"
                              f"<span style='color:{theme.MUTED}'>{APP_BRAND}</span>"), 1)
        lay.addLayout(head)
        f = QFormLayout()
        self.u = QLineEdit("admin" if demo_hint else "")
        self.p = QLineEdit()
        self.p.setEchoMode(QLineEdit.Password)
        f.addRow("Tên đăng nhập", self.u)
        f.addRow("Mật khẩu", self.p)
        lay.addLayout(f)
        self.msg = QLabel()
        self.msg.setStyleSheet("color:#B42318")
        lay.addWidget(self.msg)
        if demo_hint:
            h = QLabel("Dữ liệu minh họa: admin/admin@123 · ketoantruong/ktt@123 · ketoanvien/ktv@123 · xem/xem@123")
            h.setObjectName("Hint")
            h.setWordWrap(True)
            lay.addWidget(h)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Đăng nhập")
        bb.button(QDialogButtonBox.Cancel).setText("Thoát")
        bb.accepted.connect(self.try_login)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.p.setFocus()

    def try_login(self):
        try:
            self.user = self._auth(self.db, self.u.text(), self.p.text())
            self.accept()
        except Exception as e:  # noqa: BLE001
            self.msg.setText(str(e))
            self.p.selectAll()
            self.p.setFocus()
