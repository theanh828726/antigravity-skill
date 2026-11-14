"""Màn hình nhập chứng từ: thông tin chung + lưới hạch toán + tổng tiền + vòng đời trạng thái.

Phím tắt: Ctrl+N thêm mới · F2 sửa · Ctrl+S lưu · Esc hủy · F6 kiểm tra · F9 ghi sổ · Ctrl+F9 bỏ ghi sổ
          Insert thêm dòng · Ctrl+D sao chép dòng · Ctrl+Delete xóa dòng · Ctrl+V dán từ Excel · F3 tìm danh mục
          Ctrl+P in · Enter sang ô kế tiếp.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QCompleter, QDialog, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ketoan.domain.constants import (CHECKED, DRAFT, LINE_COLUMNS, LOCKED, POSTED, SEV_BLOCK, VOUCHER_TYPES)
from ketoan.domain.money import fmt_decimal, fmt_money, line_amount, round_money, tax_amount, to_decimal
from ketoan.reports import export
from ketoan.services.catalog_service import CatalogService
from ketoan.services.voucher_service import VoucherService
from ketoan.ui.widgets import (DateEdit, IssuesDialog, ReportTable, confirm, error, info, run, set_badge, status_badge,
                               tool_button, vn_date)

COL = {c[0]: c for c in LINE_COLUMNS}
LOOKUP_KINDS = {"account", "partner", "item", "warehouse", "project", "department", "expense"}
NUM_KINDS = {"qty", "price", "money", "rate"}
SEP = " — "


# =============================================================== tra cứu danh mục
class LookupSource:
    """Bộ nhớ đệm danh mục cho tra cứu nhanh trong một phiên nhập liệu."""

    def __init__(self, session):
        self.cat = CatalogService(session)
        self._cache: dict[str, list] = {}

    def items(self, kind: str):
        if kind not in self._cache:
            self._cache[kind] = self.cat.lookup(kind)
        return self._cache[kind]

    def strings(self, kind):
        return [f"{code}{SEP}{name}" for _, code, name, _ in self.items(kind)]

    def find(self, kind, code):
        for rid, c, name, extra in self.items(kind):
            if c == code:
                return rid, c, name, extra
        return None

    def invalidate(self):
        self._cache.clear()


def _completer(parent, strings):
    comp = QCompleter(QStringListModel(strings), parent)
    comp.setCaseSensitivity(Qt.CaseInsensitive)
    comp.setFilterMode(Qt.MatchContains)
    comp.setCompletionMode(QCompleter.PopupCompletion)
    comp.setMaxVisibleItems(14)
    comp.popup().setMinimumWidth(380)
    return comp


class LookupDelegate(QStyledItemDelegate):
    def __init__(self, form):
        super().__init__(form.grid)
        self.form = form

    def createEditor(self, parent, option, index):
        key = self.form.columns[index.column()][0]
        kind = COL[key][3]
        ed = QLineEdit(parent)
        if kind in LOOKUP_KINDS:
            ed.setCompleter(_completer(ed, self.form.lookup.strings(kind)))
            ed.setPlaceholderText("Gõ mã/tên – F3 tìm")
        elif kind in NUM_KINDS:
            ed.setAlignment(Qt.AlignRight)
        return ed

    def setEditorData(self, editor, index):
        key = self.form.columns[index.column()][0]
        v = self.form.lines[index.row()].get(key)
        kind = COL[key][3]
        if kind in NUM_KINDS:
            editor.setText("" if v in (None, "", 0) else fmt_decimal(v))
        else:
            editor.setText("" if v is None else str(v))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        if SEP in text:
            text = text.split(SEP, 1)[0].strip()
        self.form.set_cell(index.row(), index.column(), text)


class LookupDialog(QDialog):
    def __init__(self, title, rows, parent=None, initial=""):
        super().__init__(parent)
        self.setWindowTitle(f"Tìm {title}")
        self.resize(640, 440)
        self.rows, self.result = rows, None
        lay = QVBoxLayout(self)
        self.search = QLineEdit(initial)
        self.search.setPlaceholderText("Nhập mã, tên hoặc mã số thuế để lọc…")
        lay.addWidget(self.search)
        self.table = ReportTable()
        lay.addWidget(self.table)
        self.search.textChanged.connect(self._filter)
        self.table.rowActivated.connect(self._pick)
        self.search.returnPressed.connect(lambda: self.table.rowCount() and self._pick(self.table.item(0, 0).data(Qt.UserRole + 1)))
        self._filter(initial)

    def _filter(self, text):
        t = text.lower().strip()
        rows = [r for r in self.rows if not t or t in f"{r[1]} {r[2]} {r[3] or ''}".lower()]
        self.table.fill(["Mã", "Tên", "Thông tin"], [[r[1], r[2], r[3] or ""] for r in rows],
                        widths=[110, 380, 120], keys=[r[1] for r in rows], stretch_col=1)
        if rows:
            self.table.selectRow(0)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Down, Qt.Key_Up) and self.search.hasFocus():
            self.table.setFocus()
            return
        super().keyPressEvent(e)

    def _pick(self, code):
        self.result = code
        self.accept()


class LookupEdit(QWidget):
    """Ô nhập đối tượng ở phần thông tin chung: mã + tên, tra cứu nhanh."""
    changed = Signal(object)

    def __init__(self, lookup: LookupSource, kind="partner", parent=None):
        super().__init__(parent)
        self.lookup, self.kind = lookup, kind
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Mã đối tượng (F3)")
        self.edit.setMaximumWidth(130)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Tên đối tượng")
        lay.addWidget(self.edit)
        lay.addWidget(self.name, 1)
        self.reload()
        self.edit.editingFinished.connect(self._resolve)
        QShortcut(QKeySequence(Qt.Key_F3), self.edit, activated=self.open_dialog, context=Qt.WidgetShortcut)

    def reload(self):
        self.edit.setCompleter(_completer(self.edit, self.lookup.strings(self.kind)))
        self.edit.completer().activated.connect(lambda _t: QTimer.singleShot(0, self._resolve))

    def open_dialog(self):
        if self.edit.isReadOnly():
            return
        dlg = LookupDialog("đối tượng", self.lookup.items(self.kind), self, self.edit.text())
        if dlg.exec() and dlg.result:
            self.edit.setText(dlg.result)
            self._resolve()

    def _resolve(self):
        text = self.edit.text().strip()
        if SEP in text:
            text = text.split(SEP, 1)[0].strip()
            self.edit.setText(text)
        hit = self.lookup.find(self.kind, text) if text else None
        if hit:
            self.name.setText(hit[2])
            self.edit.setStyleSheet("")
        elif text:
            self.edit.setStyleSheet("background:#FDECEC")
            self.edit.setToolTip("Mã không có trong danh mục")
        self.changed.emit(hit)

    def code(self):
        return self.edit.text().strip()

    def set_value(self, code, name):
        self.edit.setText(code or "")
        self.name.setText(name or "")

    def set_readonly(self, ro):
        self.edit.setReadOnly(ro)
        self.name.setReadOnly(ro)


class EntryGrid(QTableWidget):
    """Lưới nhập: Enter sang ô kế tiếp, tự thêm dòng ở cuối."""

    def __init__(self, form):
        super().__init__()
        self.form = form

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.state() != QAbstractItemView.EditingState:
            if self.form.editing:
                self.form.move_next()
                return
        if e.matches(QKeySequence.Paste) and self.form.editing:
            self.form.paste_rows()
            return
        if e.key() == Qt.Key_Delete and self.form.editing and not e.modifiers():
            for it in self.selectedItems():
                self.form.set_cell(it.row(), it.column(), "")
            return
        super().keyPressEvent(e)

    def closeEditor(self, editor, hint):
        super().closeEditor(editor, hint)
        if hint == QStyledItemDelegate.EditNextItem:
            pass


# =============================================================== màn hình chứng từ
class VoucherForm(QWidget):
    saved = Signal(int)

    def __init__(self, ctx, vtype: str = "PKT", voucher_id: int | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.vs = VoucherService(self.s)
        self.lookup = LookupSource(self.s)
        self.vtype = vtype
        self.voucher_id = voucher_id
        self.data: dict = {}
        self.lines: list[dict] = []
        self.editing = False
        self.dirty = False
        self._loading = False
        self._build()
        if voucher_id:
            self.load(voucher_id)
        else:
            self.new()

    # ------------------------------------------------------------- dựng giao diện
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)
        # Thanh thao tác
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.b = {}
        for key, text, ic, role, tip, sc in (
                ("new", "Thêm", "add", None, "Thêm chứng từ mới", "Ctrl+N"),
                ("edit", "Sửa", "edit", None, "Sửa chứng từ", "F2"),
                ("save", "Lưu", "save", "primary", "Lưu chứng từ", "Ctrl+S"),
                ("cancel", "Hủy", "cancel", None, "Hủy thay đổi chưa lưu", "Esc"),
                ("check", "Kiểm tra", "check", None, "Kiểm tra chứng từ", "F6"),
                ("post", "Ghi sổ", "post", "post", "Ghi sổ", "F9"),
                ("unpost", "Bỏ ghi sổ", "unpost", None, "Bỏ ghi sổ", "Ctrl+F9"),
                ("delete", "Xóa", "delete", "danger", "Xóa chứng từ (chưa ghi sổ)", None),
                ("print", "In", "printer", None, "Xem trước khi in", "Ctrl+P"),
                ("excel", "Xuất Excel", "excel", None, "Xuất chứng từ ra Excel", None)):
            btn = tool_button(text, ic, role, f"{tip} ({sc})" if sc else tip)
            btn.clicked.connect(getattr(self, f"do_{key}"))
            bar.addWidget(btn)
            self.b[key] = btn
            if sc:
                QShortcut(QKeySequence(sc), self, activated=lambda k=key: self.b[k].isEnabled() and getattr(self, f"do_{k}")(),
                          context=Qt.WidgetWithChildrenShortcut)
        bar.addStretch(1)
        self.title = QLabel()
        self.title.setObjectName("PageTitle")
        bar.addWidget(self.title)
        bar.addSpacing(8)
        self.badge = status_badge(DRAFT)
        bar.addWidget(self.badge)
        root.addLayout(bar)

        # Thông tin chung
        box = QFrame()
        box.setObjectName("TotalBox")
        g = QGridLayout(box)
        g.setContentsMargins(8, 6, 8, 6)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(4)
        self.cb_type = QComboBox()
        for code, vt in VOUCHER_TYPES.items():
            if code != "KC":
                self.cb_type.addItem(vt.name, code)
        self.cb_type.currentIndexChanged.connect(self._type_changed)
        self.ed_number = QLineEdit()
        self.ed_number.setPlaceholderText("Tự động")
        self.ed_vdate = DateEdit()
        self.ed_pdate = DateEdit()
        self.ed_vdate.dateChanged.connect(lambda d: (not self._loading) and self.ed_pdate.setDate(d))
        self.partner = LookupEdit(self.lookup)
        self.partner.changed.connect(self._partner_changed)
        self.ed_tax = QLineEdit()
        self.ed_desc = QLineEdit()
        self.ed_inv_no = QLineEdit()
        self.ed_inv_series = QLineEdit()
        self.ed_inv_date = DateEdit()
        self.ed_due = DateEdit()
        self.ed_due.setToolTip("Hạn thanh toán – mặc định = ngày hóa đơn + số ngày hạn TT của đối tượng; dùng cho tuổi nợ")
        self._due_touched = False
        self.ed_due.dateChanged.connect(lambda _: (not self._loading) and setattr(self, "_due_touched", True))
        lab = lambda t: QLabel(t)
        g.addWidget(lab("Loại chứng từ"), 0, 0); g.addWidget(self.cb_type, 0, 1)
        g.addWidget(lab("Số chứng từ"), 0, 2); g.addWidget(self.ed_number, 0, 3)
        g.addWidget(lab("Ngày chứng từ"), 0, 4); g.addWidget(self.ed_vdate, 0, 5)
        g.addWidget(lab("Ngày hạch toán"), 0, 6); g.addWidget(self.ed_pdate, 0, 7)
        g.addWidget(lab("Đối tượng"), 1, 0); g.addWidget(self.partner, 1, 1, 1, 3)
        g.addWidget(lab("Mã số thuế"), 1, 4); g.addWidget(self.ed_tax, 1, 5)
        self.lab_inv = [lab("Ký hiệu / Số HĐ"), lab("Ngày hóa đơn"), lab("Hạn thanh toán")]
        inv_box = QWidget()
        ib = QHBoxLayout(inv_box)
        ib.setContentsMargins(0, 0, 0, 0)
        ib.setSpacing(4)
        self.ed_inv_series.setPlaceholderText("Ký hiệu")
        self.ed_inv_no.setPlaceholderText("Số hóa đơn")
        ib.addWidget(self.ed_inv_series, 1)
        ib.addWidget(self.ed_inv_no, 1)
        self.inv_box = inv_box
        g.addWidget(self.lab_inv[0], 1, 6); g.addWidget(inv_box, 1, 7)
        g.addWidget(lab("Diễn giải"), 2, 0); g.addWidget(self.ed_desc, 2, 1, 1, 3)
        g.addWidget(self.lab_inv[1], 2, 4); g.addWidget(self.ed_inv_date, 2, 5)
        g.addWidget(self.lab_inv[2], 2, 6); g.addWidget(self.ed_due, 2, 7)
        for c, st in ((1, 2), (3, 1), (5, 1), (7, 1)):
            g.setColumnStretch(c, st)
        root.addWidget(box)
        for w in (self.ed_number, self.ed_tax, self.ed_desc, self.ed_inv_no, self.ed_inv_series):
            w.textEdited.connect(self._mark_dirty)
        for w in (self.ed_vdate, self.ed_pdate, self.ed_inv_date, self.ed_due):
            w.dateChanged.connect(self._mark_dirty)
        self.ed_inv_date.dateChanged.connect(lambda _: self._suggest_due())

        # Thanh công cụ lưới
        gbar = QHBoxLayout()
        gbar.setSpacing(4)
        self.gb = {}
        for key, text, ic, tip, fn in (("add", "Thêm dòng", "add", "Insert", self.add_line),
                                       ("copy", "Sao chép dòng", "copy", "Ctrl+D", self.copy_line),
                                       ("del", "Xóa dòng", "delete", "Ctrl+Delete", self.delete_line),
                                       ("paste", "Dán từ Excel", "excel", "Ctrl+V – dán nhiều dòng", self.paste_rows),
                                       ("find", "Tìm danh mục", "search", "F3", self.find_catalog)):
            btn = tool_button(text, ic, tip=tip)
            btn.clicked.connect(fn)
            gbar.addWidget(btn)
            self.gb[key] = btn
        for sc, fn in (("Insert", self.add_line), ("Ctrl+D", self.copy_line), ("Ctrl+Delete", self.delete_line),
                       ("F3", self.find_catalog)):
            QShortcut(QKeySequence(sc), self, activated=lambda f=fn: self.editing and f(),
                      context=Qt.WidgetWithChildrenShortcut)
        self.hint = QLabel()
        self.hint.setObjectName("Hint")
        gbar.addSpacing(8)
        gbar.addWidget(self.hint, 1)
        root.addLayout(gbar)

        self.grid = EntryGrid(self)
        self.grid.setItemDelegate(LookupDelegate(self))
        self.grid.verticalHeader().setVisible(False)
        self.grid.verticalHeader().setDefaultSectionSize(24)
        self.grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.grid.horizontalHeader().setHighlightSections(False)
        root.addWidget(self.grid, 1)

        # Tổng tiền
        tot = QHBoxLayout()
        tot.setSpacing(6)
        self.t = {}
        for key, label in (("amount", "Tổng tiền hàng"), ("tax", "Tổng tiền thuế"), ("payment", "Tổng thanh toán"),
                           ("debit", "Tổng phát sinh Nợ"), ("credit", "Tổng phát sinh Có"),
                           ("difference", "Chênh lệch Nợ – Có")):
            f = QFrame()
            f.setObjectName("TotalBox")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(8, 2, 8, 2)
            fl.setSpacing(0)
            l1 = QLabel(label)
            l1.setObjectName("TotalLabel")
            l2 = QLabel("0")
            l2.setObjectName("TotalValue")
            l2.setAlignment(Qt.AlignRight)
            fl.addWidget(l1)
            fl.addWidget(l2)
            tot.addWidget(f, 1)
            self.t[key] = l2
        root.addLayout(tot)

    # ------------------------------------------------------------- dữ liệu
    @property
    def vt(self):
        return VOUCHER_TYPES[self.vtype]

    def _setup_columns(self):
        self.columns = [COL[k] for k in self.vt.columns]
        self.grid.setColumnCount(len(self.columns))
        self.grid.setHorizontalHeaderLabels([c[1] for c in self.columns])
        for j, c in enumerate(self.columns):
            self.grid.setColumnWidth(j, c[2])
        has_inv = bool(self.vt.tax_account) or self.vtype == "PKMB"
        for w in self.lab_inv + [self.inv_box, self.ed_inv_date, self.ed_due]:
            w.setVisible(has_inv)
        self.hint.setText(self.vt.note or "Chỉ hiển thị các cột phù hợp loại chứng từ. Enter: sang ô kế tiếp.")

    def _blank_line(self):
        return {"debit_account": self.vt.default_debit or None, "credit_account": self.vt.default_credit or None,
                "description": self.ed_desc.text().strip() or None}

    def new(self, vtype: str | None = None):
        self._loading = True
        if vtype:
            self.vtype = vtype
        self.voucher_id = None
        self.data = {"status": DRAFT, "display_status": DRAFT}
        self.cb_type.setCurrentIndex(max(0, self.cb_type.findData(self.vtype)))
        self.ed_number.setText("")
        today = date.today()
        default = today if self.s.date_from <= today <= self.s.date_to else self.s.date_to
        self.ed_vdate.set_iso(default)
        self.ed_pdate.set_iso(default)
        self.ed_inv_date.set_iso(default)
        self.ed_due.set_iso(default)
        self._due_touched = False
        self.partner.set_value("", "")
        for w in (self.ed_tax, self.ed_desc, self.ed_inv_no, self.ed_inv_series):
            w.setText("")
        self.lines = [self._blank_line()]
        self._setup_columns()
        self._loading = False
        self.set_editing(True)
        self.render()
        self.dirty = False
        self._update_title()
        self.ed_desc.setFocus() if self.vtype else None

    def load(self, voucher_id: int):
        ok, v = run(self, self.vs.get, voucher_id)
        if not ok:
            return
        self._loading = True
        self.voucher_id, self.data, self.vtype = voucher_id, v, v["vtype"]
        self.cb_type.setCurrentIndex(max(0, self.cb_type.findData(self.vtype)))
        self._setup_columns()
        self.ed_number.setText(v["number"])
        self.ed_vdate.set_iso(v["voucher_date"])
        self.ed_pdate.set_iso(v["posting_date"])
        self.ed_inv_date.set_iso(v["invoice_date"] or v["voucher_date"])
        self.ed_due.set_iso(v.get("due_date") or v["invoice_date"] or v["voucher_date"])
        self._due_touched = bool(v.get("due_date"))
        pname = v["partner_name"] or (self.lookup.find("partner", v["partner_code"]) or (0, 0, ""))[2]
        self.partner.set_value(v["partner_code"], pname)
        self.ed_tax.setText(v["tax_code"] or "")
        self.ed_desc.setText(v["description"] or "")
        self.ed_inv_no.setText(v["invoice_no"] or "")
        self.ed_inv_series.setText(v["invoice_series"] or "")
        self.lines = []
        for ln in v["lines"]:
            d = {k: ln.get(k) for k in COL}
            d["quantity"] = to_decimal(ln["quantity"]) or None
            d["unit_price"] = to_decimal(ln["unit_price"]) or None
            d["tax_rate"] = to_decimal(ln["tax_rate"]) if ln["tax_rate"] not in (None, "") else None
            if d["tax_rate"] is not None and int(ln["tax_amount"] or 0) != tax_amount(ln["amount"] or 0, d["tax_rate"]):
                d["_tax_manual"] = True     # giữ nguyên tiền thuế người dùng đã nhập, không tự tính lại
            self.lines.append(d)
        self._loading = False
        self.set_editing(False)
        self.render()
        self.dirty = False
        self._update_title()

    def _update_title(self):
        n = self.ed_number.text() or "(mới)"
        self.title.setText(n)
        self.title.setToolTip(f"{self.vt.name} số {n}")
        st = self.data.get("display_status", DRAFT)
        set_badge(self.badge, st)
        title = f"{self.vt.prefix} {n}" if self.voucher_id else f"{self.vt.name} (mới)"
        self.ctx.set_tab_title(self, title + (" *" if self.dirty else ""))

    def _type_changed(self):
        code = self.cb_type.currentData()
        if self._loading or not code or code == self.vtype:
            return
        if self.voucher_id:
            self.cb_type.setCurrentIndex(self.cb_type.findData(self.vtype))
            return
        self.vtype = code
        for ln in self.lines:
            if not ln.get("amount"):
                ln["debit_account"] = self.vt.default_debit or None
                ln["credit_account"] = self.vt.default_credit or None
        self._setup_columns()
        self.render()
        self._update_title()

    def _suggest_due(self):
        """Gợi ý hạn thanh toán = ngày hóa đơn + số ngày hạn TT của đối tượng (khi người dùng chưa tự sửa)."""
        if self._loading or self._due_touched or not self.partner.code():
            return
        hit = self.lookup.find("partner", self.partner.code())
        if hit:
            due = self.vs.default_due_date(hit[0], self.ed_inv_date.iso())
            self._loading = True
            self.ed_due.set_iso(due)
            self._loading = False

    def _partner_changed(self, hit):
        if self._loading:
            return
        self._suggest_due()
        if hit:
            self.ed_tax.setText(hit[3] or "")
            # gợi ý đối tượng cho các dòng có TK bắt buộc đối tượng nhưng chưa chọn
            for ln in self.lines:
                for side in ("debit", "credit"):
                    acc = self.lookup.find("account", ln.get(f"{side}_account") or "")
                    if acc and acc[3] and not ln.get(f"{side}_partner"):
                        ln[f"{side}_partner"] = hit[1]
            self.render()
        self._mark_dirty()

    def _mark_dirty(self, *_):
        if self._loading or not self.editing:
            return
        if not self.dirty:
            self.dirty = True
            self._update_title()

    # ------------------------------------------------------------- trạng thái
    def set_editing(self, on: bool):
        self.editing = on
        st = self.data.get("display_status", DRAFT)
        locked = st in (POSTED, LOCKED)
        for w in (self.ed_number, self.ed_tax, self.ed_desc, self.ed_inv_no, self.ed_inv_series):
            w.setReadOnly(not on)
        for w in (self.ed_vdate, self.ed_pdate, self.ed_inv_date, self.ed_due):
            w.setReadOnly(not on)
        self.partner.set_readonly(not on)
        self.cb_type.setEnabled(on and not self.voucher_id)
        self.grid.setEditTriggers(QAbstractItemView.AllEditTriggers if on else QAbstractItemView.NoEditTriggers)
        u = self.s.user
        self.b["new"].setEnabled(u.can("add"))
        self.b["edit"].setEnabled(not on and bool(self.voucher_id) and not locked and u.can("edit"))
        self.b["save"].setEnabled(on and u.can("add" if not self.voucher_id else "edit"))
        self.b["cancel"].setEnabled(on)
        self.b["check"].setEnabled(st in (DRAFT,) and u.can("edit"))
        self.b["post"].setEnabled(st in (DRAFT, CHECKED) and u.can("post"))
        self.b["unpost"].setEnabled(st == POSTED and u.can("post"))
        self.b["delete"].setEnabled(bool(self.voucher_id) and st in (DRAFT, CHECKED) and u.can("delete"))
        self.b["print"].setEnabled(u.can("export"))
        self.b["excel"].setEnabled(u.can("export"))
        for b in self.gb.values():
            b.setEnabled(on)
        self.grid.setStyleSheet("" if on else "QTableWidget { background: #FAFBFD; }")

    # ------------------------------------------------------------- lưới
    def render(self):
        self.grid.blockSignals(True)
        self.grid.setRowCount(len(self.lines))
        for i, ln in enumerate(self.lines):
            ln["line_no"] = i + 1
            for j, (key, _, _, kind) in enumerate(self.columns):
                self._render_cell(i, j, key, kind, ln)
        self.grid.blockSignals(False)
        self.update_totals()

    def _render_cell(self, i, j, key, kind, ln):
        v = ln.get(key)
        if kind == "money":
            text = fmt_money(v)
        elif kind in ("qty", "price", "rate"):
            text = fmt_decimal(v) if v not in (None, "") else ""
        else:
            text = "" if v is None else str(v)
        it = self.grid.item(i, j) or QTableWidgetItem()
        it.setText(text)
        it.setToolTip("")
        it.setBackground(QColor("white"))
        if kind in NUM_KINDS or kind == "int":
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if key == "line_no":
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setTextAlignment(Qt.AlignCenter)
            it.setBackground(QColor("#F1F4F8"))
        elif kind in LOOKUP_KINDS and v:
            hit = self.lookup.find(kind, str(v))
            if hit:
                it.setToolTip(hit[2])
            else:
                it.setBackground(QColor("#FDECEC"))
                it.setToolTip("Mã không có trong danh mục (hoặc TK tổng hợp / ngừng dùng)")
        if key in ("amount", "tax_amount"):
            auto = (key == "amount" and ln.get("quantity") and ln.get("unit_price")) or \
                   (key == "tax_amount" and ln.get("tax_rate") not in (None, "") and not ln.get("_tax_manual"))
            if auto:
                it.setBackground(QColor("#F3F8EE"))
        self.grid.setItem(i, j, it)

    def set_cell(self, row: int, col: int, text: str):
        key, _, _, kind = self.columns[col]
        ln = self.lines[row]
        try:
            if kind in ("qty", "price", "rate"):
                ln[key] = to_decimal(text) if text != "" else None
            elif kind == "money":
                ln[key] = round_money(text) if text != "" else None
                if key == "tax_amount":
                    ln["_tax_manual"] = text != ""
                if key == "amount":
                    ln["_amount_manual"] = True
            else:
                ln[key] = text or None
        except ValueError as e:
            error(self, str(e))
            return
        # gợi ý theo danh mục
        if key == "item" and text:
            hit = self.lookup.find("item", text)
            if hit:
                ln["unit"] = ln.get("unit") or hit[3]
                if not ln.get("description"):
                    ln["description"] = hit[2]
                rate = self.s.db.scalar("SELECT tax_rate FROM item WHERE id=?", (hit[0],))
                if self.vt.tax_account and ln.get("tax_rate") is None and rate not in (None, ""):
                    ln["tax_rate"] = to_decimal(rate)
        if key in ("debit_account", "credit_account") and text:
            acc = self.lookup.find("account", text)
            side = key.split("_")[0]
            if acc and acc[3] and not ln.get(f"{side}_partner") and self.partner.code():
                ln[f"{side}_partner"] = self.partner.code()
        # tự tính
        if ln.get("quantity") and ln.get("unit_price") and key in ("quantity", "unit_price"):
            ln["amount"] = line_amount(ln["quantity"], ln["unit_price"])
        if self.vt.tax_account and ln.get("tax_rate") is not None and key in ("quantity", "unit_price", "amount", "tax_rate") \
                and not ln.get("_tax_manual"):
            ln["tax_amount"] = tax_amount(ln.get("amount") or 0, ln["tax_rate"])
        self.grid.blockSignals(True)
        for j, (k2, _, _, kd) in enumerate(self.columns):
            self._render_cell(row, j, k2, kd, ln)
        self.grid.blockSignals(False)
        self.update_totals()
        self._mark_dirty()

    def update_totals(self):
        lines = [{"amount": int(l.get("amount") or 0), "tax_amount": int(l.get("tax_amount") or 0),
                  "debit_account": l.get("debit_account"), "credit_account": l.get("credit_account")} for l in self.lines]
        t = VoucherService.totals(self.vtype, lines)
        for k in ("amount", "tax", "payment", "debit", "credit"):
            self.t[k].setText(fmt_money(t[k], blank_zero=False))
        d = t["difference"]
        self.t["difference"].setText(fmt_money(d, blank_zero=False) + ("  ✓ cân đối" if d == 0 else "  ✗ lệch"))
        self.t["difference"].setObjectName("TotalDiffOk" if d == 0 else "TotalDiffBad")
        self.t["difference"].style().unpolish(self.t["difference"])
        self.t["difference"].style().polish(self.t["difference"])

    def current_row(self):
        r = self.grid.currentRow()
        return r if r >= 0 else len(self.lines) - 1

    def add_line(self):
        if not self.editing:
            return
        r = self.current_row() + 1
        self.lines.insert(r, self._blank_line())
        self.render()
        self.grid.setCurrentCell(r, 1)
        self._mark_dirty()

    def copy_line(self):
        if not self.editing or not self.lines:
            return
        r = self.current_row()
        self.lines.insert(r + 1, dict(self.lines[r]))
        self.render()
        self.grid.setCurrentCell(r + 1, max(1, self.grid.currentColumn()))
        self._mark_dirty()

    def delete_line(self):
        if not self.editing or not self.lines:
            return
        rows = sorted({i.row() for i in self.grid.selectedIndexes()} or {self.current_row()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.lines):
                self.lines.pop(r)
        if not self.lines:
            self.lines.append(self._blank_line())
        self.render()
        self._mark_dirty()

    def move_next(self):
        r, c = self.grid.currentRow(), self.grid.currentColumn()
        if r < 0:
            return
        c += 1
        if c >= len(self.columns):
            c = 1
            r += 1
            if r >= len(self.lines):
                self.lines.append(self._blank_line())
                self.render()
        self.grid.setCurrentCell(r, c)

    def paste_rows(self):
        if not self.editing:
            return
        text = QGuiApplication.clipboard().text()
        if not text.strip():
            return
        rows = [r for r in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        while rows and not rows[-1].strip():
            rows.pop()
        r0 = max(self.grid.currentRow(), 0)
        c0 = max(self.grid.currentColumn(), 1)
        errors = 0
        for i, row in enumerate(rows):
            r = r0 + i
            while r >= len(self.lines):
                self.lines.append({})
            for j, val in enumerate(row.split("\t")):
                c = c0 + j
                if c >= len(self.columns):
                    break
                try:
                    self.set_cell(r, c, val.strip())
                except Exception:
                    errors += 1
        self.render()
        msg = f"Đã dán {len(rows)} dòng từ bộ nhớ tạm (bắt đầu tại cột «{self.columns[c0][1]}»)."
        if errors:
            msg += f" {errors} ô không đọc được."
        self.hint.setText(msg)

    def find_catalog(self):
        if not self.editing:
            return
        r, c = self.grid.currentRow(), self.grid.currentColumn()
        if r < 0 or c < 0:
            return
        key, label, _, kind = self.columns[c]
        if kind not in LOOKUP_KINDS:
            self.hint.setText("F3: đặt con trỏ vào cột danh mục (TK, đối tượng, mã hàng, kho, …) để tìm.")
            return
        dlg = LookupDialog(label.lower(), self.lookup.items(kind), self)
        if dlg.exec() and dlg.result:
            self.set_cell(r, c, dlg.result)

    # ------------------------------------------------------------- lưu & vòng đời
    def collect(self):
        header = {"vtype": self.vtype, "number": self.ed_number.text().strip(), "voucher_date": self.ed_vdate.iso(),
                  "posting_date": self.ed_pdate.iso(), "partner_code": self.partner.code() or None,
                  "partner_name": self.partner.name.text().strip() or None, "tax_code": self.ed_tax.text().strip() or None,
                  "description": self.ed_desc.text().strip() or None,
                  "source_voucher_id": self.data.get("source_voucher_id")}   # giữ liên kết chứng từ nguồn khi sửa
        if self.ed_inv_no.isVisible() or self.ed_inv_no.text().strip():
            inv = self.ed_inv_no.text().strip()
            header.update(invoice_no=inv or None, invoice_series=self.ed_inv_series.text().strip() or None,
                          invoice_date=self.ed_inv_date.iso() if inv else None, due_date=self.ed_due.iso())
        lines = []
        for ln in self.lines:
            d = {k: ln.get(k) for k in COL if k != "line_no"}
            if not ln.get("_tax_manual") and self.vt.tax_account:
                d["tax_amount"] = None if ln.get("tax_rate") is not None else ln.get("tax_amount")
            lines.append(d)
        return header, lines

    def do_save(self) -> bool:
        if not self.editing:
            return True
        header, lines = self.collect()
        ok, vid = run(self, self.vs.save, header, lines, self.voucher_id)
        if not ok:
            return False
        self.load(vid)
        self.saved.emit(vid)
        self.ctx.voucher_changed()
        issues = self.vs.validate(vid)
        blocks = [i for i in issues if i.severity == SEV_BLOCK]
        if blocks:
            self.hint.setText(f"Đã lưu NHÁP. Còn {len(blocks)} lỗi chặn ghi sổ – bấm «Kiểm tra» (F6) để xem chi tiết.")
        else:
            self.hint.setText("Đã lưu. Chứng từ đủ điều kiện ghi sổ (F9).")
        return True

    def _ensure_saved(self) -> bool:
        if self.editing:
            return self.do_save()
        return True

    def do_new(self):
        if self.dirty and not confirm(self, "Chứng từ đang có thay đổi chưa lưu. Bỏ qua thay đổi và tạo mới?"):
            return
        self.new(self.vtype)

    def do_edit(self):
        if self.data.get("display_status") in (POSTED, LOCKED):
            error(self, "Chứng từ đã ghi sổ hoặc thuộc kỳ đã khóa. Hãy «Bỏ ghi sổ» trước khi sửa.")
            return
        self.set_editing(True)
        self.grid.setFocus()

    def do_cancel(self):
        if self.dirty and not confirm(self, "Hủy các thay đổi chưa lưu?"):
            return
        if self.voucher_id:
            self.load(self.voucher_id)
        else:
            self.new(self.vtype)

    def do_check(self):
        if not self._ensure_saved() or not self.voucher_id:
            return
        ok, issues = run(self, self.vs.check, self.voucher_id)
        if ok:
            self.load(self.voucher_id)
            self.ctx.voucher_changed()
            if issues:
                IssuesDialog(issues, self, "Đã kiểm tra – có nội dung cần xem xét").exec()
            else:
                self.hint.setText("Kiểm tra đạt: không có lỗi. Có thể ghi sổ (F9).")

    def do_post(self):
        if not self._ensure_saved() or not self.voucher_id:
            return
        ok, issues = run(self, self.vs.post, self.voucher_id)
        if ok:
            self.load(self.voucher_id)
            self.ctx.voucher_changed()
            self.hint.setText("Đã ghi sổ. Số liệu đã lên sổ nhật ký chung, sổ cái, sổ chi tiết và bảng cân đối.")
            if issues:
                IssuesDialog(issues, self, "Đã ghi sổ – lưu ý").exec()

    def do_unpost(self):
        if not confirm(self, "Bỏ ghi sổ chứng từ này? Số liệu sẽ được rút khỏi sổ sách."):
            return
        ok, _ = run(self, self.vs.unpost, self.voucher_id)
        if ok:
            self.load(self.voucher_id)
            self.ctx.voucher_changed()
            self.hint.setText("Đã bỏ ghi sổ – chứng từ ở trạng thái Đã kiểm tra, có thể sửa (F2).")

    def do_delete(self):
        if not self.voucher_id or not confirm(self, f"Xóa chứng từ {self.ed_number.text()}? Thao tác được ghi nhật ký."):
            return
        ok, _ = run(self, self.vs.delete, self.voucher_id)
        if ok:
            self.ctx.voucher_changed()
            self.dirty = False
            self.ctx.close_widget(self)

    def _doc_payload(self):
        h, _ = self.collect()
        headers = ["STT"] + [c[1] for c in self.columns[1:]]
        rows, money = [], set()
        for j, c in enumerate(self.columns):
            if c[3] == "money":
                money.add(j)
        for ln in self.lines:
            row = []
            for key, _, _, kind in self.columns:
                v = ln.get(key)
                row.append(int(v or 0) if kind == "money" else (to_decimal(v) if kind in ("qty", "price", "rate") and v not in (None, "") else v))
            rows.append(row)
        t = VoucherService.totals(self.vtype, [{"amount": int(l.get("amount") or 0), "tax_amount": int(l.get("tax_amount") or 0),
                                                "debit_account": l.get("debit_account"),
                                                "credit_account": l.get("credit_account")} for l in self.lines])
        tot = [""] * len(self.columns)
        tot[1] = f"Tổng tiền hàng {fmt_money(t['amount'], False)} · Thuế {fmt_money(t['tax'], False)} · Thanh toán {fmt_money(t['payment'], False)}"
        rows.append(tot)
        sub = (f"Số: {h['number'] or '(chưa lưu)'} · Ngày chứng từ: {vn_date(h['voucher_date'])} · Ngày hạch toán: "
               f"{vn_date(h['posting_date'])} · Đối tượng: {h['partner_code'] or ''} {h['partner_name'] or ''} · "
               f"Diễn giải: {h['description'] or ''}")
        if h.get("invoice_no"):
            sub += f" · Hóa đơn {h.get('invoice_series') or ''} số {h['invoice_no']}"
        return self.vt.name, sub, headers, rows, money, {len(rows) - 1}

    def do_print(self):
        title, sub, headers, rows, money, totals = self._doc_payload()
        c = self.s.company
        html = export.to_html(title, sub, f"{c['name']} – MST: {c['tax_code'] or ''}", headers, rows, money, totals,
                              ["Người lập", "Kế toán trưởng", "Giám đốc"])
        export.print_preview(self, html, True)

    def do_excel(self):
        title, sub, headers, rows, money, totals = self._doc_payload()
        path, _ = QFileDialog.getSaveFileName(self, "Xuất Excel", f"{self.vt.prefix}_{self.ed_number.text() or 'moi'}.xlsx",
                                              "Excel (*.xlsx)")
        if path:
            c = self.s.company
            ok, _ = run(self, export.export_excel, path, title, sub, c["name"], headers, rows, money, totals)
            if ok:
                info(self, f"Đã xuất: {path}")

    # ------------------------------------------------------------- tab
    def can_close(self) -> bool:
        return not self.dirty or confirm(self, "Chứng từ có thay đổi chưa lưu. Đóng và bỏ thay đổi?")

    def refresh(self):
        self.lookup.invalidate()
        self.partner.reload()
        if self.voucher_id and not self.editing:
            self.load(self.voucher_id)
