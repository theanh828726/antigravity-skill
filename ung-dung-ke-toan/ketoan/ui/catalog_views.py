"""Danh mục: xem, thêm, sửa, xóa, nhập Excel có ánh xạ cột; Số dư đầu kỳ."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ketoan.domain.money import fmt_money, round_money
from ketoan.services.catalog_service import CATALOGS, CatalogService
from ketoan.services.system_service import OpeningBalanceService
from ketoan.ui import icons
from ketoan.ui.widgets import ExportBar, ReportTable, confirm, error, info, run, tool_button

CATALOG_ORDER = ["account", "customer", "supplier", "employee", "item", "warehouse", "project", "department",
                 "expense_item", "fixed_asset"]


class CatalogEditDialog(QDialog):
    def __init__(self, cat, record=None, parent=None):
        super().__init__(parent)
        self.cat = cat
        self.setWindowTitle(("Sửa " if record else "Thêm ") + cat.title.lower())
        self.setMinimumWidth(520)
        form = QFormLayout(self)
        self.w = {}
        for f in cat.fields:
            v = record[f.key] if record is not None and f.key in record.keys() else f.default
            if f.kind == "bool":
                w = QCheckBox()
                w.setChecked(bool(v))
            elif f.kind == "choice":
                w = QComboBox()
                for val, lab in f.choices:
                    w.addItem(lab, val)
                w.setCurrentIndex(max(0, w.findData(v)))
            elif f.kind == "date":
                w = QLineEdit(v or "")
                w.setPlaceholderText("yyyy-mm-dd")
            elif f.kind == "money":
                w = QLineEdit(fmt_money(v or 0))
                w.setAlignment(Qt.AlignRight)
            else:
                w = QLineEdit("" if v is None else str(v))
            if f.key == "code" and record is not None and cat.table == "account":
                w.setToolTip("Không đổi được số hiệu khi tài khoản đã phát sinh số liệu")
            self.w[f.key] = w
            form.addRow(f.label + (" *" if f.required else ""), w)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Lưu")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self) -> dict:
        out = {}
        for f in self.cat.fields:
            w = self.w[f.key]
            if isinstance(w, QCheckBox):
                out[f.key] = 1 if w.isChecked() else 0
            elif isinstance(w, QComboBox):
                out[f.key] = w.currentData()
            else:
                out[f.key] = w.text()
        return out


class ExcelImportDialog(QDialog):
    """Nhập danh mục từ Excel: chọn file → chọn sheet, dòng tiêu đề → ánh xạ cột → kiểm tra → nhập."""

    def __init__(self, session, cat_key, parent=None):
        super().__init__(parent)
        self.s, self.cat = session, CATALOGS[cat_key]
        self.svc = CatalogService(session)
        self.setWindowTitle(f"Nhập Excel – {self.cat.title}")
        self.resize(900, 600)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        b = tool_button("Chọn file Excel…", "excel")
        b.clicked.connect(self.choose)
        self.cb_sheet = QComboBox()
        self.sp_header = QSpinBox()
        self.sp_header.setRange(1, 50)
        self.sp_header.setValue(1)
        top.addWidget(self.path, 1)
        top.addWidget(b)
        top.addWidget(QLabel("Sheet"))
        top.addWidget(self.cb_sheet)
        top.addWidget(QLabel("Dòng tiêu đề"))
        top.addWidget(self.sp_header)
        lay.addLayout(top)
        lay.addWidget(QLabel("<b>Ánh xạ cột</b> – chọn cột Excel tương ứng với từng trường (* bắt buộc):"))
        self.map = QTableWidget(len(self.cat.fields), 2)
        self.map.setHorizontalHeaderLabels(["Trường dữ liệu", "Cột trong Excel"])
        self.map.verticalHeader().setVisible(False)
        self.map.setColumnWidth(0, 240)
        self.map.horizontalHeader().setStretchLastSection(True)
        self.map_cb = []
        for i, f in enumerate(self.cat.fields):
            self.map.setItem(i, 0, QTableWidgetItem(f.label + (" *" if f.required else "")))
            cb = QComboBox()
            self.map.setCellWidget(i, 1, cb)
            self.map_cb.append(cb)
        self.map.setMaximumHeight(28 * (len(self.cat.fields) + 1) + 6)
        lay.addWidget(self.map)
        self.result = ReportTable()
        lay.addWidget(QLabel("<b>Kết quả kiểm tra</b> (không có dữ liệu nào được ghi khi còn lỗi):"))
        lay.addWidget(self.result, 1)
        bar = QHBoxLayout()
        self.status = QLabel()
        bar.addWidget(self.status, 1)
        self.b_check = tool_button("Kiểm tra", "check")
        self.b_import = tool_button("Nhập dữ liệu", "import", "primary")
        b_close = tool_button("Đóng", "cancel")
        self.b_check.clicked.connect(lambda: self.process(True))
        self.b_import.clicked.connect(lambda: self.process(False))
        b_close.clicked.connect(self.reject)
        self.b_import.setEnabled(False)
        for w in (self.b_check, self.b_import, b_close):
            bar.addWidget(w)
        lay.addLayout(bar)
        self.cb_sheet.currentIndexChanged.connect(self.load_headers)
        self.sp_header.valueChanged.connect(self.load_headers)
        self.wb = None

    def choose(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file Excel", "", "Excel (*.xlsx *.xlsm)")
        if not p:
            return
        from openpyxl import load_workbook
        ok, wb = run(self, load_workbook, p, read_only=True, data_only=True)
        if not ok:
            return
        self.wb = wb
        self.path.setText(p)
        self.cb_sheet.blockSignals(True)
        self.cb_sheet.clear()
        self.cb_sheet.addItems(wb.sheetnames)
        self.cb_sheet.blockSignals(False)
        self.load_headers()

    def load_headers(self):
        if not self.wb:
            return
        ws = self.wb[self.cb_sheet.currentText()]
        hr = self.sp_header.value()
        heads = [str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows(min_row=hr, max_row=hr))]
        self.headers = heads
        for f, cb in zip(self.cat.fields, self.map_cb):
            cb.clear()
            cb.addItem("(không nhập)", -1)
            for j, h in enumerate(heads):
                cb.addItem(f"{chr(65 + j) if j < 26 else j + 1}: {h}", j)
            # tự gợi ý theo tên tiêu đề
            for j, h in enumerate(heads):
                if h and (h.lower() == f.label.lower() or h.lower() == f.key.lower() or f.label.lower() in h.lower()):
                    cb.setCurrentIndex(j + 1)
                    break
        self.b_import.setEnabled(False)
        self.status.setText(f"Đọc được {len(heads)} cột. Kiểm tra ánh xạ rồi bấm «Kiểm tra».")

    def records(self):
        ws = self.wb[self.cb_sheet.currentText()]
        hr = self.sp_header.value()
        out = []
        for i, row in enumerate(ws.iter_rows(min_row=hr + 1, values_only=True), start=hr + 1):
            if not any(v not in (None, "") for v in row):
                continue
            rec = {"_row": i}
            for f, cb in zip(self.cat.fields, self.map_cb):
                j = cb.currentData()
                if j is not None and j >= 0 and j < len(row):
                    v = row[j]
                    rec[f.key] = (v.isoformat()[:10] if hasattr(v, "isoformat") else
                                  (str(int(v)) if isinstance(v, float) and v.is_integer() and f.kind in ("text", "account")
                                   else ("" if v is None else str(v))))
            out.append(rec)
        return out

    def process(self, dry):
        if not self.wb:
            error(self, "Chưa chọn file Excel.")
            return
        recs = self.records()
        ok, res = run(self, self.svc.import_rows, self.cat.key, recs, dry)
        if not ok:
            return
        n, errors = res
        self.result.fill(["Dòng Excel", "Mã", "Lỗi"], [[e[0], e[1], e[2]] for e in errors], widths=[90, 120, 600],
                         stretch_col=2)
        if errors:
            self.status.setText(f"<span style='color:#B42318'><b>{len(errors)} dòng lỗi</b></span>, {n} dòng hợp lệ. "
                                "Sửa file Excel rồi kiểm tra lại.")
            self.b_import.setEnabled(False)
        elif dry:
            self.status.setText(f"<span style='color:#1E7A34'><b>{n} dòng hợp lệ.</b></span> Mã đã tồn tại sẽ được cập nhật. "
                                "Bấm «Nhập dữ liệu» để ghi.")
            self.b_import.setEnabled(True)
        else:
            info(self, f"Đã nhập {n} bản ghi vào danh mục {self.cat.title}.")
            self.accept()


class CatalogView(QWidget):
    def __init__(self, ctx, catalog: str = "account", parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = CatalogService(self.s)
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        split = QSplitter()
        self.list = QListWidget()
        self.list.setMaximumWidth(210)
        for k in CATALOG_ORDER:
            it = QListWidgetItem(icons.icon(CATALOGS[k].icon, "#1F5FA8", 18), CATALOGS[k].title)
            it.setData(Qt.UserRole, k)
            self.list.addItem(it)
        split.addWidget(self.list)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        bar = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setObjectName("PageTitle")
        bar.addWidget(self.heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm mã, tên, mã số thuế…")
        self.search.textChanged.connect(self.refresh)
        bar.addWidget(self.search, 1)
        self.btn = {}
        for key, text, ic, role in (("add", "Thêm", "add", "primary"), ("edit", "Sửa", "edit", None),
                                    ("del", "Xóa", "delete", "danger"), ("import", "Nhập Excel", "import", None)):
            b = tool_button(text, ic, role)
            b.clicked.connect(getattr(self, f"do_{key}"))
            bar.addWidget(b)
            self.btn[key] = b
        self.table = ReportTable()
        bar.addWidget(ExportBar(self.table, lambda: (f"Danh mục {self.cat.title.lower()}", ""), self.s, self, False, []))
        rl.addLayout(bar)
        rl.addWidget(self.table, 1)
        self.hint = QLabel("Nhấp đúp để sửa. Danh mục đã phát sinh số liệu không xóa được – bỏ chọn «Đang dùng» để ngừng.")
        self.hint.setObjectName("Hint")
        rl.addWidget(self.hint)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([200, 1100])
        root.addWidget(split)
        self.table.rowActivated.connect(lambda rid: self.do_edit(rid))
        self.list.currentRowChanged.connect(lambda _: self.refresh())
        u = self.s.user
        self.btn["add"].setEnabled(u.can("add"))
        self.btn["import"].setEnabled(u.can("add"))
        self.btn["edit"].setEnabled(u.can("edit"))
        self.btn["del"].setEnabled(u.can("delete"))
        self.list.setCurrentRow(CATALOG_ORDER.index(catalog) if catalog in CATALOG_ORDER else 0)

    @property
    def cat(self):
        return CATALOGS[self.list.currentItem().data(Qt.UserRole)]

    def refresh(self):
        if not self.list.currentItem():
            return
        cat = self.cat
        self.heading.setText(cat.title.upper())
        rows = self.svc.rows(cat.key, self.search.text().strip())
        data = []
        for r in rows:
            line = []
            for f in cat.fields:
                v = r[f.key]
                if f.kind == "bool":
                    v = "✓" if v else ""
                elif f.kind == "choice":
                    v = dict(f.choices).get(v, v)
                line.append(v)
            data.append(line)
        money = {j for j, f in enumerate(cat.fields) if f.kind == "money"}
        center = {j for j, f in enumerate(cat.fields) if f.kind in ("bool", "date")}
        self.table.fill([f.label for f in cat.fields], data, money_cols=money, widths=[f.width for f in cat.fields],
                        keys=[r["id"] for r in rows], center_cols=center)

    def _selected_id(self):
        r = self.table.currentRow()
        it = self.table.item(r, 0) if r >= 0 else None
        return it.data(Qt.UserRole + 1) if it else None

    def do_add(self):
        dlg = CatalogEditDialog(self.cat, None, self)
        while dlg.exec():
            ok, _ = run(self, self.svc.save, self.cat.key, dlg.values(), None)
            if ok:
                self.ctx.catalog_changed()
                self.refresh()
                return

    def do_edit(self, rid=None):
        rid = rid or self._selected_id()
        if not rid:
            return
        rec = self.svc.get(self.cat.key, rid)
        dlg = CatalogEditDialog(self.cat, rec, self)
        if not self.s.user.can("edit"):
            dlg.setWindowTitle(dlg.windowTitle() + " (chỉ xem)")
        while dlg.exec():
            ok, _ = run(self, self.svc.save, self.cat.key, dlg.values(), rid)
            if ok:
                self.ctx.catalog_changed()
                self.refresh()
                return

    def do_del(self):
        rid = self._selected_id()
        if rid and confirm(self, "Xóa bản ghi danh mục đã chọn?"):
            ok, _ = run(self, self.svc.delete, self.cat.key, rid)
            if ok:
                self.ctx.catalog_changed()
                self.refresh()

    def do_import(self):
        if ExcelImportDialog(self.s, self.cat.key, self).exec():
            self.ctx.catalog_changed()
            self.refresh()


class OpeningBalanceView(QWidget):
    """Số dư đầu năm tài chính theo tài khoản chi tiết và đối tượng."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = OpeningBalanceService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        bar = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setObjectName("PageTitle")
        bar.addWidget(self.heading)
        bar.addStretch(1)
        for text, ic, role, fn in (("Thêm dòng", "add", None, self.add_row), ("Xóa dòng", "delete", "danger", self.del_row),
                                   ("Lưu", "save", "primary", self.save)):
            b = tool_button(text, ic, role)
            b.clicked.connect(fn)
            b.setEnabled(self.s.user.can("edit"))
            bar.addWidget(b)
        root.addLayout(bar)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Số hiệu TK", "Tên tài khoản", "Mã đối tượng", "Dư Nợ", "Dư Có"])
        for j, w in enumerate((90, 320, 120, 150, 150)):
            self.table.setColumnWidth(j, w)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._changed)
        root.addWidget(self.table, 1)
        self.total = QLabel()
        root.addWidget(self.total)
        hint = QLabel("Số dư đầu năm nhập vào TK chi tiết; TK bắt buộc đối tượng (131, 331, 141…) nhập theo từng đối tượng. "
                      "Số lượng tồn kho đầu kỳ thuộc phân hệ Kho – Giai đoạn 2.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.refresh()

    def refresh(self):
        self.heading.setText(f"SỐ DƯ ĐẦU NĂM {self.s.year}")
        rows = self.svc.rows(self.s.year)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for r in rows:
            self._append(r["account_code"], r["account_name"], r["partner_code"], r["debit"], r["credit"])
        self.table.blockSignals(False)
        self._sum()

    def _append(self, acc="", name="", partner="", d=0, c=0):
        i = self.table.rowCount()
        self.table.insertRow(i)
        for j, v in enumerate((acc, name or "", partner or "", fmt_money(d), fmt_money(c))):
            it = QTableWidgetItem(v)
            if j == 1:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            if j >= 3:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, j, it)

    def _changed(self, it):
        if it.column() == 0:
            name = self.s.db.scalar("SELECT name FROM account WHERE company_id=? AND code=?", (self.s.company_id, it.text().strip()), "")
            self.table.blockSignals(True)
            self.table.item(it.row(), 1).setText(name or "(không có TK)")
            self.table.blockSignals(False)
        if it.column() >= 3:
            try:
                self.table.blockSignals(True)
                it.setText(fmt_money(round_money(it.text())))
            except ValueError:
                it.setText("")
            finally:
                self.table.blockSignals(False)
        self._sum()

    def _rows(self):
        out = []
        for i in range(self.table.rowCount()):
            g = lambda j: self.table.item(i, j).text() if self.table.item(i, j) else ""
            out.append({"account_code": g(0), "partner_code": g(2), "debit": g(3), "credit": g(4)})
        return out

    def _sum(self):
        d = c = 0
        for r in self._rows():
            try:
                d += round_money(r["debit"]); c += round_money(r["credit"])
            except ValueError:
                pass
        ok = d == c
        self.total.setText(f"<b>Tổng dư Nợ:</b> {fmt_money(d, False)} &nbsp; <b>Tổng dư Có:</b> {fmt_money(c, False)} &nbsp; "
                           + ("<span style='color:#1E7A34'><b>Cân đối ✓</b></span>" if ok else
                              f"<span style='color:#B42318'><b>Lệch {fmt_money(d - c, False)}</b></span>"))

    def add_row(self):
        self._append()
        self.table.setCurrentCell(self.table.rowCount() - 1, 0)

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._sum()

    def save(self):
        ok, res = run(self, self.svc.save, self.s.year, self._rows())
        if ok:
            d, c = res
            info(self, "Đã lưu số dư đầu năm." + ("" if d == c else f"\nLưu ý: tổng Nợ – Có đang lệch {fmt_money(d - c, False)}."))
            self.refresh()
            self.ctx.voucher_changed()
