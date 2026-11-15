"""Danh sách chứng từ: lọc theo loại, kỳ, trạng thái; mở, thêm, xóa, ghi sổ hàng loạt."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from ketoan.domain.constants import CHECKED, DRAFT, LOCKED, POSTED, STATUS_COLOR, STATUS_LABEL, VOUCHER_TYPES
from ketoan.services.voucher_service import Issue, ValidationFailed, VoucherService
from ketoan.ui.widgets import (DateEdit, ExportBar, IssuesDialog, ReportTable, confirm, info, run, tool_button, vn_date)


class VoucherListView(QWidget):
    def __init__(self, ctx, vtype: str | None = None, status: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.vs = VoucherService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)
        f = QHBoxLayout()
        f.setSpacing(5)
        self.cb_type = QComboBox()
        self.cb_type.addItem("Tất cả loại chứng từ", None)
        for code, vt in VOUCHER_TYPES.items():
            self.cb_type.addItem(vt.name, code)
        self.cb_type.setCurrentIndex(max(0, self.cb_type.findData(vtype)))
        self.d_from = DateEdit(self.s.date_from)
        self.d_to = DateEdit(self.s.date_to)
        self.cb_status = QComboBox()
        self.cb_status.addItem("Mọi trạng thái", None)
        for st in (DRAFT, CHECKED, POSTED, LOCKED):
            self.cb_status.addItem(STATUS_LABEL[st], st)
        self.cb_status.setCurrentIndex(max(0, self.cb_status.findData(status)))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm số CT, diễn giải, số HĐ, đối tượng…")
        for w, lab in ((self.cb_type, None), (QLabel("Từ"), None), (self.d_from, None), (QLabel("đến"), None),
                       (self.d_to, None), (self.cb_status, None)):
            f.addWidget(w)
        f.addWidget(self.search, 1)
        b_view = tool_button("Lọc", "search", "primary", "Áp dụng bộ lọc (Enter)")
        b_view.clicked.connect(self.refresh)
        f.addWidget(b_view)
        root.addLayout(f)

        a = QHBoxLayout()
        a.setSpacing(4)
        self.b_new = tool_button("Thêm chứng từ", "add", None, "Thêm mới (Ctrl+N)")
        self.b_open = tool_button("Mở", "open", None, "Mở chứng từ (Enter / nhấp đúp)")
        self.b_post = tool_button("Ghi sổ các CT chọn", "post", "post", "Ghi sổ hàng loạt (bỏ qua chứng từ có lỗi chặn)")
        self.b_unpost = tool_button("Bỏ ghi sổ", "unpost")
        self.b_del = tool_button("Xóa", "delete", "danger")
        for b, fn in ((self.b_new, self.new), (self.b_open, self.open_current), (self.b_post, self.post_selected),
                      (self.b_unpost, self.unpost_selected), (self.b_del, self.delete_selected)):
            b.clicked.connect(fn)
            a.addWidget(b)
        a.addStretch(1)
        self.summary = QLabel()
        self.summary.setObjectName("Hint")
        a.addWidget(self.summary)
        a.addSpacing(8)
        self.table = ReportTable()
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        a.addWidget(ExportBar(self.table, self._title, self.s, self))
        root.addLayout(a)
        root.addWidget(self.table, 1)
        self.table.rowActivated.connect(lambda vid: self.ctx.open_voucher(vid))
        self.search.returnPressed.connect(self.refresh)
        for w in (self.cb_type, self.cb_status):
            w.currentIndexChanged.connect(self.refresh)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new, context=Qt.WidgetWithChildrenShortcut)
        u = self.s.user
        self.b_new.setEnabled(u.can("add"))
        self.b_post.setEnabled(u.can("post"))
        self.b_unpost.setEnabled(u.can("post"))
        self.b_del.setEnabled(u.can("delete"))
        self.refresh()

    def _title(self):
        vt = self.cb_type.currentData()
        return (f"Danh sách {VOUCHER_TYPES[vt].name.lower()}" if vt else "Danh sách chứng từ",
                f"Từ ngày {vn_date(self.d_from.iso())} đến ngày {vn_date(self.d_to.iso())}")

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        rows = self.vs.list(self.cb_type.currentData(), self.d_from.iso(), self.d_to.iso(), self.cb_status.currentData(),
                            self.search.text().strip())
        self.rows = rows
        data = [[vn_date(r["posting_date"]), r["number"], VOUCHER_TYPES[r["vtype"]].name, vn_date(r["voucher_date"]),
                 r["partner_code"] or "", r["partner_display"] or "", r["description"] or "",
                 f"{r['invoice_series'] or ''} {r['invoice_no'] or ''}".strip(), r["total_amount"], r["total_tax"],
                 r["total_payment"], STATUS_LABEL[r["display_status"]]] for r in rows]
        tot = [sum(r["total_amount"] for r in rows), sum(r["total_tax"] for r in rows), sum(r["total_payment"] for r in rows)]
        data.append(["", "", "Tổng cộng", "", "", "", f"{len(rows)} chứng từ", "", *tot, ""])
        self.table.fill(["Ngày HT", "Số CT", "Loại chứng từ", "Ngày CT", "Mã ĐT", "Tên đối tượng", "Diễn giải", "Hóa đơn",
                         "Tiền hàng", "Tiền thuế", "Tổng thanh toán", "Trạng thái"], data,
                        money_cols={8, 9, 10}, widths=[78, 74, 130, 78, 62, 170, 210, 100, 105, 92, 112, 88],
                        keys=[r["id"] for r in rows] + [None], total_rows={len(rows)}, center_cols={0, 3, 11})
        self.table.setColumnHidden(2, bool(self.cb_type.currentData()))   # đã lọc 1 loại thì ẩn cột loại
        for i, r in enumerate(rows):
            bg, fg = STATUS_COLOR[r["display_status"]]
            it = self.table.item(i, 11)
            it.setBackground(QColor(bg))
            it.setForeground(QColor(fg))
        n = {st: sum(1 for r in rows if r["display_status"] == st) for st in (DRAFT, CHECKED, POSTED, LOCKED)}
        self.summary.setText(" · ".join(f"{STATUS_LABEL[k]}: {v}" for k, v in n.items()))

    def selected_ids(self):
        ids = []
        for r in sorted({i.row() for i in self.table.selectedIndexes()}):
            it = self.table.item(r, 0)
            vid = it.data(Qt.UserRole + 1) if it else None
            if vid:
                ids.append(vid)
        return ids

    def new(self):
        self.ctx.open_voucher(None, self.cb_type.currentData() or "PKT")

    def open_current(self):
        ids = self.selected_ids()
        if ids:
            self.ctx.open_voucher(ids[0])

    def post_selected(self):
        ids = self.selected_ids()
        if not ids:
            return
        okc, fail = 0, []
        for vid in ids:
            v = next(r for r in self.rows if r["id"] == vid)
            if v["display_status"] in (POSTED, LOCKED):
                continue
            try:
                self.vs.post(vid)
                okc += 1
            except ValidationFailed as e:
                fail.extend(e.issues)
            except Exception as e:  # noqa: BLE001 – báo cáo từng chứng từ
                fail.append(Issue("BLOCK", "loi", str(e), 0, vid, None, v["number"]))
        self.refresh()
        self.ctx.voucher_changed()
        if fail:
            for i in fail:
                if i.voucher_label:
                    i.message = f"{i.voucher_label}: {i.message}"
            IssuesDialog(fail, self, f"Đã ghi sổ {okc} chứng từ – các chứng từ sau chưa ghi sổ").exec()
        else:
            info(self, f"Đã ghi sổ {okc} chứng từ.")

    def unpost_selected(self):
        ids = self.selected_ids()
        if ids and confirm(self, f"Bỏ ghi sổ {len(ids)} chứng từ đã chọn?"):
            for vid in ids:
                ok, _ = run(self, self.vs.unpost, vid)
                if not ok:
                    break
            self.refresh()
            self.ctx.voucher_changed()

    def delete_selected(self):
        ids = self.selected_ids()
        if ids and confirm(self, f"Xóa {len(ids)} chứng từ đã chọn? (chỉ xóa được chứng từ chưa ghi sổ, kỳ chưa khóa)"):
            for vid in ids:
                ok, _ = run(self, self.vs.delete, vid)
                if not ok:
                    break
            self.refresh()
            self.ctx.voucher_changed()
