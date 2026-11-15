"""Giao diện giai đoạn 3 (phần 1): TSCĐ, CCDC – chi phí trả trước, giá thành, sổ chi tiết công trình, in hồ sơ,
chuyển số dư cuối năm."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QSpinBox, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from ketoan.domain.money import fmt_decimal, fmt_money, round_money, to_decimal
from ketoan.reports import print_pack
from ketoan.services.asset_service import PREPAID_KINDS, AssetService, PrepaidService
from ketoan.services.cost_service import METHODS, PRESETS, CostService
from ketoan.services.yearend_service import YearEndService
from ketoan.ui.phase2_views import _hint, _page_title
from ketoan.ui.widgets import (DateEdit, ExportBar, ReportTable, SectionHeader, confirm, error, info, run, tool_button, vn_date)

MONTHS = [f"Tháng {m:02d}" for m in range(1, 13)]


# ======================================================================= chạy khấu hao / phân bổ theo tháng
class RunTab(QWidget):
    """Xem trước → chạy (tạo chứng từ nháp hoặc ghi sổ) → lịch sử → hoàn tác. Dùng cho TSCĐ và CCDC/chi phí trả trước."""

    def __init__(self, ctx, svc, noun: str, base_label: str, parent=None):
        super().__init__(parent)
        self.ctx, self.s, self.svc, self.noun = ctx, ctx.session, svc, noun
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        top = QHBoxLayout()
        self.sp_year = QSpinBox()
        self.sp_year.setRange(2000, 2100)
        self.sp_year.setValue(self.s.date_to.year)
        self.cb_month = QComboBox()
        self.cb_month.addItems(MONTHS)
        self.cb_month.setCurrentIndex(self.s.date_to.month - 1)
        self.chk_post = QCheckBox("Ghi sổ ngay")
        self.chk_post.setEnabled(self.s.user.can("post"))
        b = tool_button("Xem trước", "search", "primary")
        b.clicked.connect(self.refresh)
        self.b_run = tool_button(f"Chạy {noun} tháng này", "post", "post")
        self.b_run.clicked.connect(self.apply)
        self.b_run.setEnabled(self.s.user.can("add"))
        for w in (QLabel("Năm"), self.sp_year, QLabel("Tháng"), self.cb_month, b, self.chk_post, self.b_run):
            top.addWidget(w)
        top.addStretch(1)
        lay.addLayout(top)
        self.table = ReportTable()
        top.addWidget(ExportBar(self.table, lambda: (f"Bảng {noun} tháng {self.cb_month.currentIndex() + 1:02d}/{self.sp_year.value()}", ""),
                                self.s, self))
        lay.addWidget(self.table, 2)
        self.base_label = base_label
        lay.addWidget(SectionHeader("Lịch sử các lần chạy"))
        bar = QHBoxLayout()
        self.b_undo = tool_button("Hoàn tác lần chạy đã chọn", "unpost")
        self.b_undo.clicked.connect(self.undo)
        self.b_undo.setEnabled(self.s.user.can("post"))
        bar.addWidget(self.b_undo)
        bar.addWidget(_hint("Mỗi lần chạy tạo một chứng từ «Nghiệp vụ hạch toán». Phải chạy tuần tự từng tháng; hoàn tác từ tháng mới nhất, kỳ chưa khóa. "
                            "Nhấp đúp để mở chứng từ."), 1)
        lay.addLayout(bar)
        self.hist = ReportTable()
        self.hist.rowActivated.connect(lambda k: k[0] and self.ctx.open_voucher(k[0]))
        lay.addWidget(self.hist, 1)
        self.refresh()

    def refresh(self):
        y, m = self.sp_year.value(), self.cb_month.currentIndex() + 1
        try:
            rows = self.svc.preview(y, m)
            self.table.fill(["Mã", "Tên", self.base_label, "Đã hạch toán trước", f"Số tháng {m:02d}", "Còn lại sau tháng", "TK Nợ", "TK Có"],
                            [[r.code, r.name, r.base, r.done_before, r.amount, r.remaining_after, r.debit_account, r.credit_account] for r in rows]
                            + [["", "TỔNG CỘNG", sum(r.base for r in rows), sum(r.done_before for r in rows), sum(r.amount for r in rows),
                                sum(r.remaining_after for r in rows), "", ""]],
                            money_cols={2, 3, 4, 5}, widths=[80, 280, 130, 140, 120, 130, 70, 70], total_rows={len(rows)}, center_cols={6, 7}, stretch_col=1)
        except Exception as e:  # noqa: BLE001 – thiếu TK trong danh mục…
            self.table.fill(["Thông báo"], [[str(e)]], stretch_col=0)
        runs = self.svc.runs(y)
        self._runs = runs
        self.hist.fill(["Tháng", "Chứng từ", "Trạng thái", "Số tiền", "Người chạy", "Thời điểm"],
                       [[f"{r['month']:02d}/{r['year']}", r["number"] or "(đã xóa)", r["status"] or "", r["total"], r["run_by"],
                         (r["run_at"] or "").replace("T", " ")] for r in runs], money_cols={3},
                       widths=[80, 100, 100, 130, 110, 150], keys=[(r["voucher_id"], r["year"], r["month"]) for r in runs], center_cols={0, 1, 2})

    def apply(self):
        y, m = self.sp_year.value(), self.cb_month.currentIndex() + 1
        if not confirm(self, f"Chạy {self.noun} tháng {m:02d}/{y} và tạo chứng từ" + (" (ghi sổ ngay)?" if self.chk_post.isChecked() else " nháp?")):
            return
        ok, vid = run(self, self.svc.apply, y, m, self.chk_post.isChecked())
        if ok:
            self.ctx.voucher_changed()
            self.cb_month.setCurrentIndex(min(m, 11))
            self.refresh()
            self.ctx.open_voucher(vid)

    def undo(self):
        r = self.hist.currentRow()
        it = self.hist.item(r, 0) if r >= 0 else None
        key = it.data(Qt.UserRole + 1) if it else None
        if key and confirm(self, f"Hoàn tác {self.noun} tháng {key[2]:02d}/{key[1]} (bỏ ghi sổ và xóa chứng từ)?"):
            ok, _ = run(self, self.svc.undo, key[1], key[2])
            if ok:
                self.ctx.voucher_changed()
                self.refresh()


class AssetView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = AssetService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("TÀI SẢN CỐ ĐỊNH"))
        top.addStretch(1)
        root.addLayout(top)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.setContentsMargins(0, 4, 0, 0)
        bar = QHBoxLayout()
        for text, ic, role, fn in (("Mở danh mục TSCĐ (thêm / sửa)", "folder", None, lambda: self.ctx.open("c_catalog", catalog="fixed_asset")),
                                   ("Ghi giảm TSCĐ…", "unpost", None, self.dispose), ("Hủy ghi giảm", "refresh", None, lambda: self.dispose(True))):
            b = tool_button(text, ic, role)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addWidget(_hint("Hao mòn lũy kế = đã khấu hao đầu kỳ + các lần chạy trong phần mềm đến cuối kỳ đang chọn."), 1)
        self.table = ReportTable()
        bar.addWidget(ExportBar(self.table, lambda: ("Danh sách tài sản cố định", f"Tại ngày {vn_date(self.s.date_to.isoformat())}"), self.s, self))
        l1.addLayout(bar)
        l1.addWidget(self.table, 1)
        self.tabs.addTab(w1, "Danh sách & giá trị còn lại")
        self.run_tab = RunTab(ctx, self.svc, "khấu hao", "Nguyên giá")
        self.tabs.addTab(self.run_tab, "Tính khấu hao tháng")
        self.refresh()

    def apply_period(self, d_from, d_to):
        pass

    def refresh(self):
        rows = self.svc.assets()
        data = [[a["code"], a["name"], a["original_cost"], vn_date(a["start_date"]), a["useful_months"], a["monthly"], a["accumulated"],
                 a["net_value"], f"{a['depreciation_account'] or ''} / {a['expense_account'] or ''}",
                 ("Đã ghi giảm " + vn_date(a["disposal_date"])) if a["disposal_date"] else ("Đang dùng" if a["active"] else "Ngừng dùng")] for a in rows]
        data.append(["", "TỔNG CỘNG", sum(a["original_cost"] for a in rows), "", None, None, sum(a["accumulated"] for a in rows),
                     sum(a["net_value"] for a in rows), "", ""])
        self.table.fill(["Mã", "Tên tài sản", "Nguyên giá", "Bắt đầu KH", "Số tháng", "KH / tháng", "Hao mòn lũy kế", "Giá trị còn lại",
                         "TK hao mòn / chi phí", "Trạng thái"], data, money_cols={2, 5, 6, 7},
                        widths=[70, 250, 120, 90, 70, 105, 125, 125, 130, 150], keys=[a["id"] for a in rows] + [None], total_rows={len(rows)},
                        center_cols={3, 4, 8}, stretch_col=1)
        self.run_tab.refresh()

    def dispose(self, cancel=False):
        r = self.table.currentRow()
        it = self.table.item(r, 0) if r >= 0 else None
        aid = it.data(Qt.UserRole + 1) if it else None
        if not aid:
            error(self, "Chưa chọn tài sản.")
            return
        d = ""
        if not cancel:
            d, ok = QInputDialog.getText(self, "Ghi giảm TSCĐ", "Ngày ghi giảm (yyyy-mm-dd) – ngừng khấu hao từ tháng sau:",
                                         text=self.s.date_to.isoformat())
            if not ok:
                return
            try:
                date.fromisoformat(d.strip())
            except ValueError:
                error(self, "Ngày không hợp lệ.")
                return
        ok, _ = run(self, self.svc.dispose, aid, d.strip())
        if ok:
            self.refresh()
            info(self, "Đã cập nhật. Bút toán thanh lý (nếu có) hạch toán qua chứng từ nghiệp vụ.")


class PrepaidDialog(QDialog):
    def __init__(self, rec=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sửa khoản phân bổ" if rec else "Thêm công cụ dụng cụ / chi phí trả trước")
        self.setMinimumWidth(480)
        f = QFormLayout(self)
        g = lambda k, d="": (rec[k] if rec is not None and rec[k] is not None else d)
        self.code, self.name = QLineEdit(g("code")), QLineEdit(g("name"))
        self.kind = QComboBox()
        for k, v in PREPAID_KINDS:
            self.kind.addItem(v, k)
        self.kind.setCurrentIndex(max(0, self.kind.findData(g("kind", "CCDC"))))
        self.src, self.exp = QLineEdit(g("source_account", "242")), QLineEdit(g("expense_account", "6422"))
        self.total = QLineEdit(fmt_money(g("total_amount", 0)))
        self.start = QLineEdit(g("start_date", date.today().replace(day=1).isoformat()))
        self.months = QLineEdit(str(g("months", 12)))
        self.opening = QLineEdit(fmt_money(g("allocated_opening", 0)))
        self.dept = QLineEdit(g("department"))
        self.active = QCheckBox("Đang dùng")
        self.active.setChecked(bool(g("active", 1)))
        for lab, w in (("Mã *", self.code), ("Tên *", self.name), ("Loại", self.kind), ("TK nguồn (153, 242…) *", self.src),
                       ("TK chi phí phân bổ *", self.exp), ("Tổng giá trị *", self.total), ("Bắt đầu phân bổ (yyyy-mm-dd) *", self.start),
                       ("Số tháng phân bổ *", self.months), ("Đã phân bổ đầu kỳ", self.opening), ("Mã bộ phận", self.dept), ("", self.active)):
            f.addRow(lab, w)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Lưu")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def values(self):
        return {"code": self.code.text(), "name": self.name.text(), "kind": self.kind.currentData(), "source_account": self.src.text().strip(),
                "expense_account": self.exp.text().strip(), "total_amount": self.total.text(), "start_date": self.start.text().strip(),
                "months": self.months.text(), "allocated_opening": self.opening.text(), "department": self.dept.text().strip(),
                "active": self.active.isChecked()}


class PrepaidView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = PrepaidService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.addWidget(_page_title("CÔNG CỤ DỤNG CỤ & CHI PHÍ TRẢ TRƯỚC"))
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.setContentsMargins(0, 4, 0, 0)
        bar = QHBoxLayout()
        u = self.s.user
        for text, ic, role, fn, perm in (("Thêm", "add", "primary", self.add, "add"), ("Sửa", "edit", None, self.edit, "edit"),
                                         ("Xóa", "delete", "danger", self.delete, "delete")):
            b = tool_button(text, ic, role)
            b.clicked.connect(fn)
            b.setEnabled(u.can(perm))
            bar.addWidget(b)
        bar.addWidget(_hint("Ghi tăng CCDC / chi phí trả trước bằng chứng từ mua (Nợ 153 / 242); tại đây khai báo thời gian và TK phân bổ."), 1)
        self.table = ReportTable()
        bar.addWidget(ExportBar(self.table, lambda: ("Danh sách CCDC, chi phí trả trước", f"Tại ngày {vn_date(self.s.date_to.isoformat())}"), self.s, self))
        l1.addLayout(bar)
        l1.addWidget(self.table, 1)
        self.table.rowActivated.connect(lambda rid: self.edit(rid))
        self.tabs.addTab(w1, "Danh sách")
        self.run_tab = RunTab(ctx, self.svc, "phân bổ", "Tổng giá trị")
        self.tabs.addTab(self.run_tab, "Phân bổ hàng tháng")
        self.refresh()

    def apply_period(self, d_from, d_to):
        pass

    def refresh(self):
        rows = self.svc.items()
        kinds = dict(PREPAID_KINDS)
        data = [[p["code"], p["name"], kinds.get(p["kind"], p["kind"]), p["total_amount"], vn_date(p["start_date"]), p["months"], p["monthly"],
                 p["allocated"], p["remaining"], f"{p['source_account']} → {p['expense_account']}", "Đang dùng" if p["active"] else "Ngừng"] for p in rows]
        data.append(["", "TỔNG CỘNG", "", sum(p["total_amount"] for p in rows), "", None, None, sum(p["allocated"] for p in rows),
                     sum(p["remaining"] for p in rows), "", ""])
        self.table.fill(["Mã", "Tên", "Loại", "Tổng giá trị", "Bắt đầu", "Số tháng", "Phân bổ / tháng", "Đã phân bổ", "Còn lại", "TK nguồn → chi phí", "Trạng thái"],
                        data, money_cols={3, 6, 7, 8}, widths=[70, 250, 130, 115, 90, 70, 110, 115, 115, 120, 90],
                        keys=[p["id"] for p in rows] + [None], total_rows={len(rows)}, center_cols={4, 5, 9}, stretch_col=1)
        self.run_tab.refresh()

    def _sel(self):
        r = self.table.currentRow()
        it = self.table.item(r, 0) if r >= 0 else None
        return it.data(Qt.UserRole + 1) if it else None

    def add(self):
        dlg = PrepaidDialog(None, self)
        while dlg.exec():
            ok, _ = run(self, self.svc.save_item, None, dlg.values())
            if ok:
                self.refresh()
                return

    def edit(self, rid=None):
        rid = rid or self._sel()
        if not rid:
            return
        rec = self.s.db.one("SELECT * FROM prepaid_item WHERE id=?", (rid,))
        dlg = PrepaidDialog(rec, self)
        while dlg.exec():
            ok, _ = run(self, self.svc.save_item, rid, dlg.values())
            if ok:
                self.refresh()
                return

    def delete(self):
        rid = self._sel()
        if rid and confirm(self, "Xóa khoản đã chọn?"):
            ok, _ = run(self, self.svc.delete_item, rid)
            if ok:
                self.refresh()


# ======================================================================= GIÁ THÀNH
class _Adapter:
    """Cho phép ExportBar xuất dữ liệu từ bảng nhập liệu tự dựng."""

    def __init__(self):
        self.heads, self.rows, self.money_cols, self.total_rows = [], [], set(), set()

    def headers(self):
        return self.heads

    def data_rows(self):
        return self.rows


class CostView(QWidget):
    def __init__(self, ctx, key: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s, self.key = ctx, ctx.session, key
        self.svc = CostService(self.s)
        label, method, debit = PRESETS[key]
        self.label = label
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        head = QHBoxLayout()
        head.addWidget(_page_title(f"GIÁ THÀNH {label.upper()}"))
        top = QHBoxLayout()
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        self.cb_method = QComboBox()
        for k, v in METHODS.items():
            self.cb_method.addItem(v, k)
        self.cb_method.setCurrentIndex(self.cb_method.findData(method))
        self.ed_debit = QLineEdit(debit)
        self.ed_debit.setMaximumWidth(80)
        self.ed_debit.setMinimumWidth(64)
        self.ed_debit.setToolTip("TK Nợ khi kết chuyển giá thành (155 thành phẩm / 632 giá vốn / 1541…) – Có TK 154")
        for w in (QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to, QLabel("Cách tính"), self.cb_method, QLabel("TK Nợ kết chuyển"), self.ed_debit):
            top.addWidget(w)
        b = tool_button("Tính từ sổ", "calc", "primary")
        b.clicked.connect(self.calc)
        top.addWidget(b)
        bo = tool_button("Kết chuyển CP 621/622/627 vào 154…", "refresh", None, "Kết chuyển chi phí sản xuất (nếu hệ thống TK có TK 621, 622, 627)")
        bo.clicked.connect(lambda: OverheadDialog(self.ctx, self).exec())
        top.addWidget(bo)
        top.addStretch(1)
        self.adapter = _Adapter()
        head.addStretch(1)
        head.addWidget(ExportBar(self.adapter, lambda: (f"Bảng tính giá thành {label.lower()}", f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())} – "
                                                        f"{self.cb_method.currentText()}"), self.s, self))
        root.addLayout(head)
        root.addLayout(top)
        self.hint = _hint("")
        root.addWidget(self.hint)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._edited)
        self.table.cellDoubleClicked.connect(lambda r, c: self._open_ledger(r))
        root.addWidget(self.table, 1)
        bar = QHBoxLayout()
        self.status = QLabel()
        bar.addWidget(self.status, 1)
        self.b_save = tool_button("Lưu & tạo chứng từ kết chuyển giá thành (nháp)", "post", "post")
        self.b_undo = tool_button("Hoàn tác kết chuyển kỳ này", "unpost")
        self.b_save.clicked.connect(self.save)
        self.b_undo.clicked.connect(self.undo)
        self.b_save.setEnabled(self.s.user.can("add"))
        self.b_undo.setEnabled(self.s.user.can("post"))
        bar.addWidget(self.b_save)
        bar.addWidget(self.b_undo)
        root.addLayout(bar)
        self.cb_method.activated.connect(lambda _: self.calc())
        self.inputs: dict = {}
        self.rows, self.items, self.cols = [], [], []
        self.calc()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    @property
    def method(self):
        return self.cb_method.currentData()

    def refresh(self):
        self.calc()

    def calc(self):
        try:
            self.rows, self.items = self.svc.calculate(self.method, self.d_from.iso(), self.d_to.iso(), self.inputs)
        except Exception as e:  # noqa: BLE001
            error(self, str(e))
            return
        notes = {"GD": "Giá thành = dở dang đầu kỳ + chi phí phát sinh − dở dang cuối kỳ. Nhập dở dang cuối kỳ và số lượng hoàn thành (ô vàng).",
                 "KDD": "Không có dở dang cuối kỳ: toàn bộ chi phí trong kỳ (+ dở dang đầu kỳ nếu có) tính vào giá thành.",
                 "DM": "Như giản đơn, thêm so sánh với định mức: giá thành định mức = số lượng × định mức đơn vị (nhập, ô vàng). Phần mềm không tự lập hay duyệt định mức.",
                 "KDM": "Phân bổ chi phí chung (TK 154 chưa gắn công trình/đối tượng) cho các đối tượng theo tỷ lệ chi phí trực tiếp."}
        extra = ""
        if self.svc.common_unallocated:
            extra = f" ⚠ Có {fmt_money(self.svc.common_unallocated)} chi phí 154 chưa gắn đối tượng – KHÔNG nằm trong giá thành (chọn cách «Không định mức» để phân bổ)."
        self.hint.setText(notes[self.method] + " Chỉ tính từ chi phí đã ghi sổ trên TK 154. Nhấp đúp để mở sổ chi tiết đối tượng." + extra)
        self.render()

    def render(self):
        m = self.method
        heads = ["Mã", "Đối tượng"] + [self.svc.item_name(e) for e in self.items] + ["CP trực tiếp"]
        if m == "KDM":
            heads.append("CP chung phân bổ")
        heads += ["Dở dang đầu kỳ", "Dở dang cuối kỳ", "SL hoàn thành", "Giá thành", "Giá thành đơn vị"]
        if m == "DM":
            heads += ["Định mức đơn vị", "Giá thành định mức", "Chênh lệch", "% chênh lệch"]
        heads.append("Chứng từ KC")
        self.cols = heads
        n_items = len(self.items)
        self.c_direct = 2 + n_items
        c = self.c_direct + 1
        self.c_common = c if m == "KDM" else None
        c += 1 if m == "KDM" else 0
        self.c_wb, self.c_we, self.c_qty = c, c + 1, c + 2
        self.c_total, self.c_unit = c + 3, c + 4
        self.c_norm = c + 5 if m == "DM" else None
        self.editable = {self.c_wb, self.c_qty} | ({self.c_we} if m != "KDD" else set()) | ({self.c_norm} if m == "DM" else set())
        self.table.blockSignals(True)
        self.table.setColumnCount(len(heads))
        self.table.setHorizontalHeaderLabels(heads)
        self.table.setRowCount(len(self.rows) + 1)
        for i, r in enumerate(self.rows):
            self._fill_row(i, r)
        t = len(self.rows)
        self._fill_total()
        for j, w in enumerate([75, 200] + [150] * n_items + [120] * (len(heads) - 2 - n_items)):
            self.table.setColumnWidth(j, w)
        self.table.blockSignals(False)
        self._update_export()
        saved = [r for r in self.rows if r.saved and r.voucher_id]
        self.status.setText(f"{len(self.rows)} đối tượng · {len(saved)} đã kết chuyển giá thành kỳ này" if self.rows else "Chưa có chi phí 154 đã ghi sổ trong kỳ.")
        self.b_undo.setEnabled(bool(saved) and self.s.user.can("post"))
        self.b_save.setEnabled(bool(self.rows) and self.s.user.can("add"))
        _ = t

    def _vals(self, r):
        out = [r.code, r.name] + [r.by_item.get(e, 0) for e in self.items] + [r.direct]
        if self.method == "KDM":
            out.append(r.common)
        out += [r.wip_begin, r.wip_end, r.quantity, r.total, r.unit]
        if self.method == "DM":
            out += [r.norm_unit, r.standard_total, r.variance, r.variance_pct]
        out.append("")
        return out

    def _fill_row(self, i, r):
        vals = self._vals(r)
        for j, v in enumerate(vals):
            if j == len(vals) - 1:
                v = ("Đã KC" if r.voucher_id else ("Đã lưu" if r.saved else ""))
            if j in (self.c_qty,) or (self.c_norm is not None and j == self.c_norm):
                text = fmt_decimal(v) if v not in (None, 0) and to_decimal(v) != 0 else ""
            elif j == self.c_unit:
                text = fmt_decimal(v) if v is not None else ""
            elif self.method == "DM" and j == len(vals) - 2:
                text = f"{v:.1f}%" if v is not None else ""
            elif j >= 2 and isinstance(v, (int, float)) or (j >= 2 and v is None):
                text = fmt_money(v) if v is not None else ""
            else:
                text = str(v)
            it = self.table.item(i, j) or QTableWidgetItem()
            it.setText(text)
            if j >= 2 and j != len(vals) - 1:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if j in self.editable:
                it.setFlags(it.flags() | Qt.ItemIsEditable)
                it.setBackground(QColor("#FFFDE8"))
            else:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setBackground(QColor("white"))
            self.table.setItem(i, j, it)

    def _fill_total(self):
        t = len(self.rows)
        sums = {j: sum(self._vals(r)[j] for r in self.rows) for j in list(range(2, self.c_direct + 1)) +
                ([self.c_common] if self.c_common else []) + [self.c_wb, self.c_we, self.c_total]}
        for j in range(len(self.cols)):
            it = self.table.item(t, j) or QTableWidgetItem()
            it.setText("TỔNG CỘNG" if j == 1 else (fmt_money(sums[j]) if j in sums else ""))
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setBackground(QColor("#EEF3F9"))
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if j != 1 else Qt.AlignLeft)
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            self.table.setItem(t, j, it)

    def _edited(self, it):
        r_i, col = it.row(), it.column()
        if r_i >= len(self.rows) or col not in self.editable:
            return
        r = self.rows[r_i]
        txt = it.text().strip()
        try:
            val = to_decimal(txt) if txt else to_decimal(0)
            inp = self.inputs.setdefault(r.project_id, {})
            if col == self.c_wb:
                r.wip_begin = round_money(val); inp["wip_begin"] = r.wip_begin
            elif col == self.c_we:
                r.wip_end = round_money(val); inp["wip_end"] = r.wip_end
            elif col == self.c_qty:
                r.quantity = val; inp["quantity"] = val
            elif col == self.c_norm:
                r.norm_unit = val; inp["norm_unit"] = val
        except ValueError as e:
            error(self, str(e))
        self.table.blockSignals(True)
        self._fill_row(r_i, r)
        self._fill_total()
        self.table.blockSignals(False)
        self._update_export()

    def _update_export(self):
        a = self.adapter
        a.heads = self.cols
        a.rows = [[(r if not isinstance(r, str) else r) for r in self._vals(x)[:-1]] + [("Đã KC" if x.voucher_id else "")] for x in self.rows]
        money = set(range(2, len(self.cols) - 1)) - {self.c_qty, self.c_unit} - ({self.c_norm, len(self.cols) - 2} if self.method == "DM" else set())
        a.money_cols = money
        a.total_rows = set()

    def _open_ledger(self, row):
        if row < len(self.rows):
            self.ctx.open("gt_sct", project_id=self.rows[row].project_id, d_from=self.d_from.iso(), d_to=self.d_to.iso(), new_tab=True)

    def save(self):
        if not confirm(self, "Lưu bảng tính và tạo chứng từ NHÁP kết chuyển giá thành (Nợ " + self.ed_debit.text() + " / Có 154) cho các đối tượng "
                             "có giá thành > 0 và số lượng hoàn thành > 0?"):
            return
        ok, vid = run(self, self.svc.save_and_transfer, self.method, self.d_from.iso(), self.d_to.iso(), self.rows, self.ed_debit.text().strip())
        if ok:
            self.ctx.voucher_changed()
            self.calc()
            self.ctx.open_voucher(vid)

    def undo(self):
        if confirm(self, "Hoàn tác kết chuyển giá thành kỳ này (xóa chứng từ kết chuyển; bảng tính đã nhập được giữ)?"):
            ok, _ = run(self, self.svc.undo_transfer, self.method, self.d_from.iso(), self.d_to.iso())
            if ok:
                self.ctx.voucher_changed()
                self.calc()


class OverheadDialog(QDialog):
    """Kết chuyển chi phí 621/622/627 vào 154: xem trước → tạo chứng từ nháp → hoàn tác."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        from ketoan.services.overhead_service import CRITERIA, OverheadService
        self.ctx, self.s = ctx, ctx.session
        self.svc = OverheadService(self.s)
        self.setWindowTitle("Kết chuyển chi phí sản xuất vào TK 154")
        self.resize(960, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(_hint("Dành cho hệ thống tài khoản có TK 621, 622, 627 (khai báo trong Danh mục nếu chưa có). Chi phí đã gắn công trình/đối tượng "
                            "kết chuyển thẳng; chi phí chung chưa gắn đối tượng được phân bổ theo tiêu thức đã chọn. Mỗi tháng chạy một lần; chứng từ tạo ra là NHÁP."))
        bar = QHBoxLayout()
        self.sp_year = QSpinBox()
        self.sp_year.setRange(2000, 2100)
        self.sp_year.setValue(self.s.date_to.year)
        self.cb_month = QComboBox()
        self.cb_month.addItems(MONTHS)
        self.cb_month.setCurrentIndex(self.s.date_to.month - 1)
        self.ed_direct, self.ed_over = QLineEdit("621,622"), QLineEdit("627")
        self.cb_crit = QComboBox()
        for k, v in CRITERIA.items():
            self.cb_crit.addItem(v, k)
        for w in (QLabel("Năm"), self.sp_year, QLabel("Tháng"), self.cb_month, QLabel("TK trực tiếp"), self.ed_direct, QLabel("TK chung"), self.ed_over,
                  QLabel("Tiêu thức"), self.cb_crit):
            bar.addWidget(w)
        b = tool_button("Xem trước", "search", "primary")
        b.clicked.connect(self.refresh)
        bar.addWidget(b)
        lay.addLayout(bar)
        self.table = ReportTable()
        lay.addWidget(self.table, 2)
        self.warn = ReportTable()
        self.warn.setMaximumHeight(110)
        lay.addWidget(self.warn)
        bb = QHBoxLayout()
        self.status = QLabel()
        bb.addWidget(self.status, 1)
        self.b_apply = tool_button("Tạo chứng từ kết chuyển (nháp)", "post", "post")
        self.b_undo = tool_button("Hoàn tác tháng này", "unpost")
        self.b_apply.clicked.connect(self.apply)
        self.b_undo.clicked.connect(self.undo)
        bb.addWidget(self.b_apply)
        bb.addWidget(self.b_undo)
        lay.addLayout(bb)
        self.refresh()

    def _args(self):
        sp = lambda t: [x.strip() for x in t.split(",") if x.strip()]
        return self.sp_year.value(), self.cb_month.currentIndex() + 1, sp(self.ed_direct.text()), sp(self.ed_over.text()), self.cb_crit.currentData()

    def refresh(self):
        ok, pv = run(self, self.svc.preview, *self._args())
        if not ok:
            self.table.fill(["Thông báo"], [["Không xem trước được – xem thông báo lỗi."]], stretch_col=0)
            self.b_apply.setEnabled(False)
            return
        self.table.fill(["Đối tượng", "Tên", "TK chi phí", "Loại", "Số tiền kết chuyển vào 154"],
                        [[l["project_code"], l["project_name"], l["account"], l["kind"], l["amount"]] for l in pv["lines"]] + [["", "TỔNG CỘNG", "", "", pv["total"]]],
                        money_cols={4}, widths=[90, 300, 90, 230, 190], total_rows={len(pv["lines"])}, stretch_col=1)
        self.warn.fill(["Cảnh báo"], [[w] for w in pv["warnings"]] or [["Không có cảnh báo."]], stretch_col=0)
        done = bool(pv["run"])
        self.status.setText("<b style='color:#1E7A34'>Tháng này đã kết chuyển.</b>" if done else f"{len(pv['lines'])} dòng, tổng {fmt_money(pv['total'], False)}")
        self.b_apply.setEnabled(bool(pv["lines"]) and not done and self.s.user.can("add"))
        self.b_undo.setEnabled(done and self.s.user.can("post"))

    def apply(self):
        ok, vid = run(self, self.svc.apply, *self._args())
        if ok:
            self.ctx.voucher_changed()
            self.refresh()
            self.ctx.open_voucher(vid)

    def undo(self):
        y, m = self.sp_year.value(), self.cb_month.currentIndex() + 1
        if confirm(self, f"Hoàn tác kết chuyển chi phí tháng {m:02d}/{y}?"):
            ok, _ = run(self, self.svc.undo, y, m)
            if ok:
                self.ctx.voucher_changed()
                self.refresh()


class ProjectLedgerView(QWidget):
    def __init__(self, ctx, project_id=None, d_from=None, d_to=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = CostService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("SỔ CHI TIẾT CÔNG TRÌNH (TK 154)"))
        self.cb = QComboBox()
        self.cb.setMinimumWidth(320)
        for r in self.s.db.query("SELECT id, code, name FROM project WHERE company_id=? ORDER BY code", (self.s.company_id,)):
            self.cb.addItem(f"{r['code']} — {r['name']}", r["id"])
        if project_id:
            self.cb.setCurrentIndex(max(0, self.cb.findData(project_id)))
        self.d_from, self.d_to = DateEdit(d_from or self.s.date_from), DateEdit(d_to or self.s.date_to)
        for w in (self.cb, QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        self.table = ReportTable()
        top.addWidget(ExportBar(self.table, lambda: (f"Sổ chi tiết chi phí – {self.cb.currentText()}", f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())}"),
                                self.s, self))
        root.addLayout(top)
        root.addWidget(self.table, 3)
        root.addWidget(SectionHeader("Tổng hợp chi phí phát sinh theo khoản mục"))
        self.summary = ReportTable()
        root.addWidget(self.summary, 1)
        self.table.rowActivated.connect(lambda vid: isinstance(vid, int) and self.ctx.open_voucher(vid))
        self.cb.activated.connect(lambda _: self.refresh())
        self.refresh()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        pid = self.cb.currentData()
        if not pid:
            self.table.fill(["Thông báo"], [["Chưa có công trình trong danh mục."]])
            return
        d = self.svc.project_ledger(pid, self.d_from.iso(), self.d_to.iso())
        rows = [["", "", "Số dư đầu kỳ", "", "", None, None, d["opening"]]]
        keys = [None]
        for r in d["rows"]:
            rows.append([vn_date(r["posting_date"]), r["number"], r["description"] or "", r["expense_name"] or "", r["contra_account"] or "", r["debit"], r["credit"], r["balance"]])
            keys.append(r["voucher_id"])
        rows.append(["", "", "Số dư cuối kỳ", "", "", sum(r["debit"] for r in d["rows"]), sum(r["credit"] for r in d["rows"]), d["closing"]])
        keys.append(None)
        self.table.fill(["Ngày", "Số CT", "Diễn giải", "Khoản mục", "TK ĐƯ", "Phát sinh Nợ", "Phát sinh Có", "Dư"], rows, money_cols={5, 6, 7},
                        widths=[82, 85, 330, 160, 70, 120, 120, 125], keys=keys, total_rows={0, len(rows) - 1}, center_cols={0, 4}, stretch_col=2)
        sm = sorted(d["by_item"].items())
        self.summary.fill(["Khoản mục", "Chi phí phát sinh"], [[k, v] for k, v in sm] + [["TỔNG CỘNG", sum(v for _, v in sm)]], money_cols={1},
                          widths=[300, 150], total_rows={len(sm)})


# ======================================================================= IN HỒ SƠ
class PrintPackView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 8)
        root.addWidget(_page_title("IN HỒ SƠ KẾ TOÁN"))
        root.addWidget(_hint("Xuất hàng loạt các sổ và chứng từ ĐÃ GHI SỔ của kỳ ra file PDF (A4) vào một thư mục, kèm mục lục, để lưu trữ hoặc in. "
                             "Cần quyền «Xuất dữ liệu». Mỗi lần in được ghi nhật ký."))
        bar = QHBoxLayout()
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (QLabel("Từ ngày"), self.d_from, QLabel("đến"), self.d_to):
            bar.addWidget(w)
        bar.addStretch(1)
        root.addLayout(bar)
        self.checks = {}
        for key, label in print_pack.ITEMS:
            c = QCheckBox(label)
            c.setChecked(key != "chungtu")
            self.checks[key] = c
            root.addWidget(c)
        self.folder = QLineEdit(str(Path.home() / "HoSoKeToan"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Thư mục lưu"))
        row.addWidget(self.folder, 1)
        bf = tool_button("Chọn…", "folder")
        bf.clicked.connect(self.choose)
        row.addWidget(bf)
        root.addLayout(row)
        self.b_run = tool_button("Xuất hồ sơ PDF", "printer", "primary")
        self.b_run.clicked.connect(self.export)
        self.b_run.setEnabled(self.s.user.can("export"))
        root.addWidget(self.b_run, 0, Qt.AlignLeft)
        self.result = QListWidget()
        root.addWidget(self.result, 1)

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        pass

    def choose(self):
        p = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu hồ sơ", self.folder.text())
        if p:
            self.folder.setText(p)

    def export(self):
        sel = [k for k, c in self.checks.items() if c.isChecked()]
        if not sel:
            error(self, "Chưa chọn nội dung cần in.")
            return
        ok, files = run(self, print_pack.build, self.s, sel, self.d_from.iso(), self.d_to.iso(), self.folder.text().strip())
        if ok:
            self.result.clear()
            for f in files:
                self.result.addItem(str(f))
            info(self, f"Đã xuất {len(files) - 1} file PDF + mục lục vào:\n{self.folder.text()}")


# ======================================================================= CHUYỂN SỐ DƯ CUỐI NĂM
class YearEndView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = YearEndService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("CHUYỂN SỐ DƯ CUỐI NĂM SANG ĐẦU NĂM SAU"))
        self.sp = QSpinBox()
        self.sp.setRange(2000, 2100)
        self.sp.setValue(self.s.year)
        top.addWidget(QLabel("Năm nguồn"))
        top.addWidget(self.sp)
        b = tool_button("Xem trước", "search", "primary")
        b.clicked.connect(self.refresh)
        self.b_go = tool_button("Chuyển số dư", "post", "post")
        self.b_go.clicked.connect(self.go)
        self.b_go.setEnabled(self.s.user.can("admin"))
        top.addWidget(b)
        top.addWidget(self.b_go)
        top.addStretch(1)
        root.addLayout(top)
        root.addWidget(_hint("Điều kiện: đã kết chuyển hết doanh thu, chi phí, xác định kết quả; không có tồn kho âm; tháng 01 năm sau chưa khóa. "
                             "TK 4212 (lợi nhuận năm nay) chuyển sang 4211 theo cấu hình mẫu – cần đối chiếu hệ thống TK áp dụng. Số dư đầu năm sau cũ bị thay thế."))
        self.problems = QLabel()
        self.problems.setWordWrap(True)
        root.addWidget(self.problems)
        self.table = ReportTable()
        root.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        y = self.sp.value()
        pv = self.svc.preview(y)
        self.pv = pv
        names = {r["code"]: r["name"] for r in self.s.db.query("SELECT code, name FROM account WHERE company_id=?", (self.s.company_id,))}
        pn = {r["id"]: r["code"] for r in self.s.db.query("SELECT id, code FROM partner WHERE company_id=?", (self.s.company_id,))}
        rows = [[a, names.get(a, ""), pn.get(p, ""), max(n, 0), max(-n, 0)] for (a, p), n in sorted(pv["rows"].items(), key=lambda x: (x[0][0], x[0][1] or 0))]
        rows.append(["", "TỔNG CỘNG", "", pv["total_debit"], pv["total_credit"]])
        self.table.fill(["Số hiệu TK", "Tên tài khoản", "Đối tượng", f"Dư Nợ đầu năm {y + 1}", f"Dư Có đầu năm {y + 1}"], rows, money_cols={3, 4},
                        widths=[90, 320, 110, 150, 150], total_rows={len(rows) - 1}, stretch_col=1)
        if pv["problems"]:
            self.problems.setText("<span style='color:#B42318'><b>Chưa thể chuyển:</b><br/>• " + "<br/>• ".join(pv["problems"]) + "</span>")
        else:
            self.problems.setText(f"<span style='color:#1E7A34'><b>Đủ điều kiện.</b></span> {len(pv['rows'])} dòng số dư, {len(pv['stock'])} dòng tồn kho. "
                                  f"Năm {y + 1} hiện có {pv['existing_rows']} dòng số dư đầu năm (sẽ bị thay thế).")
        self.b_go.setEnabled(not pv["problems"] and self.s.user.can("admin"))

    def go(self):
        y = self.sp.value()
        if confirm(self, f"Chuyển số dư cuối năm {y} sang đầu năm {y + 1}? Số dư đầu năm {y + 1} hiện có sẽ bị thay thế."):
            ok, _ = run(self, self.svc.carry_forward, y)
            if ok:
                self.ctx.voucher_changed()
                info(self, f"Đã chuyển số dư sang năm {y + 1}. Chọn năm {y + 1} trên thanh điều khiển để xem.")
                self.refresh()
                self.ctx.reload_years()
