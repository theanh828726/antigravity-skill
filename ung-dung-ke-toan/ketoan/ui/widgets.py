"""Widget và tiện ích giao diện dùng chung."""
from __future__ import annotations

import traceback
from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ketoan.domain.constants import SEV_BLOCK, SEV_LABEL, STATUS_COLOR, STATUS_LABEL
from ketoan.domain.money import fmt_decimal, fmt_money
from ketoan.reports import export
from ketoan.services.context import BusinessError, PermissionDenied
from ketoan.ui import icons, theme


# ---------------------------------------------------------------- thông báo
def error(parent, text: str, title: str = "Không thực hiện được"):
    QMessageBox.warning(parent, title, text)


def info(parent, text: str, title: str = "Thông báo"):
    QMessageBox.information(parent, title, text)


def confirm(parent, text: str, title: str = "Xác nhận") -> bool:
    box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, parent)
    box.button(QMessageBox.Yes).setText("Đồng ý")
    box.button(QMessageBox.No).setText("Không")
    box.setDefaultButton(QMessageBox.No)
    return box.exec() == QMessageBox.Yes


def run(parent, fn, *args, **kwargs):
    """Chạy thao tác nghiệp vụ, hiển thị lỗi thân thiện. Trả về (ok, kết quả)."""
    from ketoan.services.voucher_service import ValidationFailed
    try:
        return True, fn(*args, **kwargs)
    except ValidationFailed as e:
        IssuesDialog(e.issues, parent, "Chứng từ chưa đạt kiểm tra").exec()
    except PermissionDenied as e:
        error(parent, str(e), "Không có quyền")
    except BusinessError as e:
        error(parent, str(e))
    except Exception as e:  # lỗi không lường trước – không làm sập ứng dụng
        traceback.print_exc()
        error(parent, f"Lỗi hệ thống: {e}\n\nDữ liệu đã được hoàn tác (giao dịch chưa hoàn tất không được lưu).", "Lỗi")
    return False, None


# ---------------------------------------------------------------- ngày
class DateEdit(QDateEdit):
    def __init__(self, value: date | str | None = None, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setMinimumWidth(98)
        self.set_iso(value or date.today())

    def set_iso(self, value):
        if isinstance(value, str):
            value = date.fromisoformat(value[:10])
        self.setDate(QDate(value.year, value.month, value.day))

    def iso(self) -> str:
        return self.date().toString("yyyy-MM-dd")

    def pydate(self) -> date:
        return date.fromisoformat(self.iso())


def vn_date(iso: str | None) -> str:
    if not iso:
        return ""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


# ---------------------------------------------------------------- tiêu đề nhóm
class SectionHeader(QWidget):
    def __init__(self, title: str, parent=None, right: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 2)
        lab = QLabel(title)
        lab.setObjectName("SectionTitle")
        line = QFrame()
        line.setObjectName("SectionLine")
        line.setFrameShape(QFrame.NoFrame)
        lay.addWidget(lab)
        lay.addWidget(line, 1)
        if right:
            lay.addWidget(right)


def status_badge(status: str) -> QLabel:
    lab = QLabel(STATUS_LABEL.get(status, status))
    bg, fg = STATUS_COLOR.get(status, ("#EEE", "#333"))
    lab.setStyleSheet(f"background:{bg}; color:{fg}; border:1px solid {fg}; border-radius:9px; padding:2px 10px;"
                      "font-weight:600;")
    return lab


def set_badge(lab: QLabel, status: str):
    bg, fg = STATUS_COLOR.get(status, ("#EEE", "#333"))
    lab.setText(STATUS_LABEL.get(status, status))
    lab.setStyleSheet(f"background:{bg}; color:{fg}; border:1px solid {fg}; border-radius:9px; padding:2px 10px;"
                      "font-weight:600;")


def tool_button(text: str, icon_name: str | None = None, role: str | None = None, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    if icon_name:
        color = "#FFFFFF" if role in ("primary", "post") else "#2B4A6F"
        b.setIcon(icons.icon(icon_name, color, 16))
    if role:
        b.setProperty("role", role)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


# ---------------------------------------------------------------- bảng báo cáo
class ReportTable(QTableWidget):
    """Bảng chỉ đọc: giữ giá trị gốc (Qt.UserRole) để xuất Excel giữ kiểu số; UserRole+1 giữ khóa truy ngược."""
    rowActivated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(23)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.money_cols: set[int] = set()
        self.total_rows: set[int] = set()
        self.itemDoubleClicked.connect(self._activated)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=lambda: self._activated(self.currentItem()))

    def _activated(self, item):
        if item is None:
            return
        key = self.item(item.row(), 0).data(Qt.UserRole + 1) if self.item(item.row(), 0) else None
        if key is not None:
            self.rowActivated.emit(key)

    def fill(self, headers: list[str], rows: list[list], money_cols=(), widths=None, keys=None, total_rows=(),
             center_cols=(), stretch_col: int | None = None):
        self.setSortingEnabled(False)
        self.clear()
        self.money_cols, self.total_rows = set(money_cols), set(total_rows)
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                if j in self.money_cols and isinstance(v, int):
                    it = QTableWidgetItem(fmt_money(v))
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif isinstance(v, Decimal):
                    it = QTableWidgetItem(fmt_decimal(v))
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    it = QTableWidgetItem("" if v is None else str(v))
                    if j in center_cols:
                        it.setTextAlignment(Qt.AlignCenter)
                it.setData(Qt.UserRole, v)
                if i in self.total_rows:
                    it.setFont(bold)
                    it.setBackground(QColor("#EEF3F9"))
                self.setItem(i, j, it)
            if keys is not None and keys[i] is not None and self.item(i, 0):
                self.item(i, 0).setData(Qt.UserRole + 1, keys[i])
        if widths:
            for j, w in enumerate(widths):
                self.setColumnWidth(j, w)
        if stretch_col is not None:
            self.horizontalHeader().setSectionResizeMode(stretch_col, QHeaderView.Stretch)

    def data_rows(self) -> list[list]:
        return [[self.item(i, j).data(Qt.UserRole) if self.item(i, j) else None for j in range(self.columnCount())]
                for i in range(self.rowCount())]

    def headers(self) -> list[str]:
        return [self.horizontalHeaderItem(j).text() for j in range(self.columnCount())]


class ExportBar(QWidget):
    """Các nút In / Xem trước, Xuất Excel, Xuất PDF cho một ReportTable."""

    def __init__(self, table: ReportTable, title_fn, session, parent=None, landscape=True, signers=None):
        super().__init__(parent)
        self.table, self.title_fn, self.s, self.landscape = table, title_fn, session, landscape
        self.signers = signers or ["Người lập biểu", "Kế toán trưởng", "Giám đốc"]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for text, ic, fn, tip in (("In", "printer", self.preview, "Xem trước khi in (Ctrl+P)"),
                                  ("Excel", "excel", self.excel, "Xuất Excel"),
                                  ("PDF", "pdf", self.pdf, "Xuất PDF")):
            b = tool_button(text, ic, tip=tip)
            b.clicked.connect(fn)
            lay.addWidget(b)
        QShortcut(QKeySequence("Ctrl+P"), self.parent() or self, activated=self.preview,
                  context=Qt.WidgetWithChildrenShortcut)

    def _payload(self):
        title, subtitle = self.title_fn()
        c = self.s.company
        company = f"{c['name']} – MST: {c['tax_code'] or ''}" if c else ""
        return title, subtitle, company

    def _check(self) -> bool:
        if not self.s.user.can("export"):
            error(self, f"Người dùng '{self.s.user.username}' không có quyền «Xuất dữ liệu».", "Không có quyền")
            return False
        return True

    def html(self):
        title, subtitle, company = self._payload()
        return export.to_html(title, subtitle, company, self.table.headers(), self.table.data_rows(),
                              self.table.money_cols, self.table.total_rows, self.signers)

    def preview(self):
        if self._check():
            export.print_preview(self, self.html(), self.landscape)

    def excel(self):
        if not self._check():
            return
        title, subtitle, company = self._payload()
        path, _ = QFileDialog.getSaveFileName(self, "Xuất Excel", f"{_slug(title)}.xlsx", "Excel (*.xlsx)")
        if path:
            ok, _ = run(self, export.export_excel, path, title, subtitle, company, self.table.headers(),
                        self.table.data_rows(), self.table.money_cols, self.table.total_rows)
            if ok:
                self.s.audit("Xuất Excel", "report", title, {"file": path})
                info(self, f"Đã xuất: {path}")

    def pdf(self):
        if not self._check():
            return
        title, _, _ = self._payload()
        path, _ = QFileDialog.getSaveFileName(self, "Xuất PDF", f"{_slug(title)}.pdf", "PDF (*.pdf)")
        if path:
            ok, _ = run(self, export.export_pdf, path, self.html(), self.landscape)
            if ok:
                self.s.audit("Xuất PDF", "report", title, {"file": path})
                info(self, f"Đã xuất: {path}")


def _slug(text: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")[:60] or "bao_cao"


# ---------------------------------------------------------------- hộp thoại danh sách lỗi
class IssuesDialog(QDialog):
    def __init__(self, issues, parent=None, title="Kết quả kiểm tra"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 360)
        lay = QVBoxLayout(self)
        n_block = sum(1 for i in issues if i.severity == SEV_BLOCK)
        head = QLabel(f"<b>{n_block}</b> lỗi chặn ghi sổ, <b>{len(issues) - n_block}</b> nội dung cần xem xét. "
                      "Dữ liệu chưa bị thay đổi – vui lòng sửa chứng từ rồi thực hiện lại.")
        head.setWordWrap(True)
        lay.addWidget(head)
        t = ReportTable()
        colors = {SEV_BLOCK: "#B42318", "REVIEW": "#9A6700", "INFO": "#1F5FA8"}
        t.fill(["Mức độ", "Dòng", "Nội dung", "Chênh lệch"],
               [[SEV_LABEL[i.severity], i.line_no or "", i.message, i.difference] for i in issues],
               money_cols={3}, widths=[120, 50, 520, 100], stretch_col=2)
        for r, i in enumerate(issues):
            t.item(r, 0).setForeground(QColor(colors.get(i.severity, "#333")))
        lay.addWidget(t)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Đóng")
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class PhaseView(QWidget):
    """Trang cho chức năng CHƯA triển khai – nêu rõ trạng thái và phạm vi dự kiến (không giả lập)."""

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        box = QFrame()
        box.setObjectName("PhaseBox")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(icons.pixmap(func.icon, theme.TILE_COLORS[func.color], 40))
        title = QLabel(f"<span style='font-size:13pt;font-weight:700;color:{theme.NAVY}'>{func.title}</span><br/>"
                       f"<span style='color:#8A5A00;font-weight:600'>Trạng thái: CHƯA TRIỂN KHAI – thuộc Giai đoạn {func.phase}"
                       "</span>")
        top.addWidget(ic)
        top.addSpacing(10)
        top.addWidget(title, 1)
        bl.addLayout(top)
        plan = QLabel(f"<b>Phạm vi dự kiến:</b> {func.plan or 'Đang hoàn thiện đặc tả.'}")
        plan.setWordWrap(True)
        bl.addSpacing(6)
        bl.addWidget(plan)
        note = QLabel("Chức năng này chưa ghi nhận hay tính toán dữ liệu. Các số liệu liên quan hiện có thể xem qua "
                      "Sổ chi tiết tài khoản, Bảng cân đối số phát sinh và Trung tâm cảnh báo.")
        note.setWordWrap(True)
        note.setObjectName("Hint")
        bl.addWidget(note)
        lay.addWidget(box)
        lay.addStretch(1)
