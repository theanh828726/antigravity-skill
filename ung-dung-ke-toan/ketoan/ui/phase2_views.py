"""Giao diện giai đoạn 2: công nợ, kho (NXT, thẻ kho, tồn đầu kỳ, tính giá xuất kho),
xuất kho hàng loạt, đối chiếu doanh thu – giá vốn, đọc hóa đơn XML."""
from __future__ import annotations

import html as _html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ketoan.domain.money import fmt_decimal, fmt_money
from ketoan.reports import export
from ketoan.services.debt_service import ACCOUNTS, AGING_BUCKETS, DebtService
from ketoan.services.inventory_service import METHODS, InventoryService
from ketoan.services.trade_service import TradeService
from ketoan.services.xml_invoice import XmlInvoiceService, parse_file
from ketoan.ui.widgets import (DateEdit, ExportBar, ReportTable, SectionHeader, confirm, error, info, run, tool_button,
                               vn_date)


def _page_title(text):
    t = QLabel(text)
    t.setObjectName("PageTitle")
    return t


def _hint(text):
    h = QLabel(text)
    h.setObjectName("Hint")
    h.setWordWrap(True)
    return h


def _bold_rows(table, rows):
    f = QFont()
    f.setBold(True)
    for r in rows:
        for j in range(table.columnCount()):
            if table.item(r, j):
                table.item(r, j).setFont(f)


def _company_line(s):
    c = s.company
    return f"{c['name']} – MST: {c['tax_code'] or ''}"


# ======================================================================= CÔNG NỢ
class DebtView(QWidget):
    def __init__(self, ctx, account: str = "131", parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = DebtService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)
        top = QHBoxLayout()
        top.addWidget(_page_title("QUẢN LÝ CÔNG NỢ"))
        top.addSpacing(10)
        self.cb_acc = QComboBox()
        for code, name in ACCOUNTS.items():
            self.cb_acc.addItem(f"{code} – {name}", code)
        self.cb_acc.setCurrentIndex(max(0, self.cb_acc.findData(account)))
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (self.cb_acc, QLabel("Từ ngày"), self.d_from, QLabel("đến / tính tuổi nợ tại"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        root.addLayout(top)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        # --- tổng hợp
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.setContentsMargins(0, 4, 0, 0)
        self.t_sum = ReportTable()
        bar1 = QHBoxLayout()
        bar1.addWidget(_hint("Nhấp đúp một đối tượng để xem chi tiết hóa đơn – tuổi nợ. Cột «Quá hạn» tính theo hạn thanh toán "
                             "trên chứng từ (mặc định = ngày hóa đơn + số ngày hạn TT của đối tượng)."), 1)
        bar1.addWidget(ExportBar(self.t_sum, lambda: (f"Tổng hợp công nợ {self.cb_acc.currentText()}", self._sub()), self.s, self))
        l1.addLayout(bar1)
        l1.addWidget(self.t_sum, 1)
        self.tabs.addTab(w1, "Tổng hợp theo đối tượng")
        # --- chi tiết hóa đơn & tuổi nợ
        w2 = QWidget(); l2 = QVBoxLayout(w2); l2.setContentsMargins(0, 4, 0, 0)
        bar2 = QHBoxLayout()
        bar2.addWidget(QLabel("Đối tượng"))
        self.cb_partner = QComboBox()
        self.cb_partner.setMinimumWidth(320)
        self.cb_partner.activated.connect(lambda _: self._render_detail())
        bar2.addWidget(self.cb_partner)
        self.b_stmt = tool_button("Biên bản đối chiếu công nợ", "printer", None,
                                  "In biên bản đối chiếu công nợ với đối tượng đang chọn")
        self.b_stmt.clicked.connect(self.print_statement)
        bar2.addWidget(self.b_stmt)
        bar2.addStretch(1)
        self.t_doc = ReportTable()
        bar2.addWidget(ExportBar(self.t_doc, lambda: (f"Chi tiết công nợ theo hóa đơn – {self.cb_partner.currentText()}",
                                                      f"Tính đến ngày {vn_date(self.d_to.iso())}"), self.s, self))
        l2.addLayout(bar2)
        l2.addWidget(self.t_doc, 1)
        l2.addWidget(_hint("Phân bổ thanh toán TỰ ĐỘNG theo FIFO (khoản đến hạn trước được trừ trước) – chỉ phục vụ theo dõi tuổi "
                           "nợ, không ghi sổ. Nhấp đúp để mở chứng từ gốc."))
        self.tabs.addTab(w2, "Chi tiết hóa đơn – hạn thanh toán")
        # --- tuổi nợ
        w3 = QWidget(); l3 = QVBoxLayout(w3); l3.setContentsMargins(0, 4, 0, 0)
        self.t_age = ReportTable()
        bar3 = QHBoxLayout()
        bar3.addStretch(1)
        bar3.addWidget(ExportBar(self.t_age, lambda: (f"Phân tích tuổi nợ {self.cb_acc.currentText()}",
                                                      f"Tại ngày {vn_date(self.d_to.iso())}"), self.s, self))
        l3.addLayout(bar3)
        l3.addWidget(self.t_age, 1)
        self.tabs.addTab(w3, "Phân tích tuổi nợ")
        self.t_sum.rowActivated.connect(self._open_partner)
        self.t_age.rowActivated.connect(self._open_partner)
        self.t_doc.rowActivated.connect(lambda vid: isinstance(vid, int) and self.ctx.open_voucher(vid))
        self.cb_acc.activated.connect(lambda _: self.refresh())
        self.refresh()

    def _sub(self):
        return f"Từ ngày {vn_date(self.d_from.iso())} đến ngày {vn_date(self.d_to.iso())}"

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    @property
    def acc(self):
        return self.cb_acc.currentData()

    def refresh(self):
        rows = self.svc.summary(self.acc, self.d_from.iso(), self.d_to.iso())
        tot = [sum(r[k] for r in rows) for k in ("ob_d", "ob_c", "ps_d", "ps_c", "cb_d", "cb_c", "overdue")]
        data = [[r["code"], r["name"], r["tax_code"] or "", r["ob_d"], r["ob_c"], r["ps_d"], r["ps_c"], r["cb_d"], r["cb_c"],
                 r["overdue"]] for r in rows]
        data.append(["", "TỔNG CỘNG", "", *tot])
        self.t_sum.fill(["Mã ĐT", "Tên đối tượng", "Mã số thuế", "Dư Nợ đầu kỳ", "Dư Có đầu kỳ", "Phát sinh Nợ", "Phát sinh Có",
                         "Dư Nợ cuối kỳ", "Dư Có cuối kỳ", "Quá hạn"], data, money_cols=set(range(3, 10)),
                        widths=[75, 260, 95, 115, 105, 120, 120, 120, 110, 110], keys=[r["partner_id"] for r in rows] + [None],
                        total_rows={len(rows)}, stretch_col=1)
        for i, r in enumerate(rows):
            if r["overdue"]:
                self.t_sum.item(i, 9).setForeground(QColor("#B42318"))
        cur = self.cb_partner.currentData()
        self.cb_partner.clear()
        self.cb_partner.addItem("Tất cả đối tượng", None)
        for r in rows:
            self.cb_partner.addItem(f"{r['code']} — {r['name']}", r["partner_id"])
        self.cb_partner.setCurrentIndex(max(0, self.cb_partner.findData(cur)))
        self._render_detail()
        ages = self.svc.aging_totals(self.acc, self.d_to.iso())
        heads = ["Mã ĐT", "Tên đối tượng"] + [b[0] for b in AGING_BUCKETS] + ["Ứng trước / trả thừa", "Còn phải " +
                                                                               ("thu" if self.acc == "131" else "trả")]
        data = [[a["partner_code"], a["partner_name"], *a["buckets"], a["advance"], a["total"]] for a in ages]
        sums = [sum(a["buckets"][i] for a in ages) for i in range(len(AGING_BUCKETS))]
        data.append(["", "TỔNG CỘNG", *sums, sum(a["advance"] for a in ages), sum(a["total"] for a in ages)])
        pid_by_code = {r["code"]: r["partner_id"] for r in rows}
        self.t_age.fill(heads, data, money_cols=set(range(2, len(heads))),
                        widths=[75, 250] + [110] * len(AGING_BUCKETS) + [130, 130],
                        keys=[pid_by_code.get(a["partner_code"]) for a in ages] + [None], total_rows={len(ages)},
                        stretch_col=1)

    def _render_detail(self):
        rows = self.svc.aging(self.acc, self.d_to.iso(), self.cb_partner.currentData())
        data, keys = [], []
        for r in rows:
            d = r["doc"]
            data.append([r["partner_code"], d.number, vn_date(d.doc_date), d.invoice, vn_date(d.due_date), d.amount, d.paid,
                         d.remaining, r["days"] if d.remaining > 0 and r["days"] > 0 else "",
                         AGING_BUCKETS[r["bucket"]][0] if d.remaining > 0 else "Ứng trước / trả thừa"])
            keys.append(d.voucher_id)
        total = sum(r["doc"].remaining for r in rows)
        data.append(["", "", "", "", "Còn lại", None, None, total, "", ""])
        keys.append(None)
        self.t_doc.fill(["Mã ĐT", "Chứng từ", "Ngày HĐ/CT", "Hóa đơn", "Hạn thanh toán", "Số phát sinh", "Đã thanh toán",
                         "Còn lại", "Số ngày quá hạn", "Nhóm tuổi nợ"], data, money_cols={5, 6, 7},
                        widths=[70, 100, 90, 140, 112, 120, 120, 120, 115, 150], keys=keys, total_rows={len(rows)},
                        center_cols={2, 4, 8})
        for i, r in enumerate(rows):
            if r["doc"].remaining > 0 and r["days"] > 0:
                for j in (4, 8, 9):
                    self.t_doc.item(i, j).setForeground(QColor("#B42318"))
        self.b_stmt.setEnabled(bool(self.cb_partner.currentData()) and self.s.user.can("export"))

    def _open_partner(self, pid):
        if pid:
            self.cb_partner.setCurrentIndex(max(0, self.cb_partner.findData(pid)))
            self._render_detail()
            self.tabs.setCurrentIndex(1)

    def print_statement(self):
        pid = self.cb_partner.currentData()
        if not pid:
            return
        st = self.svc.statement(self.acc, pid, self.d_from.iso(), self.d_to.iso())
        p, d, c = st["partner"], st["detail"], self.s.company
        sign = 1 if self.acc == "131" else -1
        rows = [[vn_date(r["posting_date"]), r["number"], r["description"] or "", r["debit"], r["credit"]] for r in d["rows"]]
        close = d["closing"] * sign
        side = ("Công ty phải thu" if close >= 0 else "Công ty phải trả lại") if self.acc == "131" else \
            ("Công ty phải trả" if close >= 0 else "Công ty đã trả trước")
        head = (f"Từ ngày {vn_date(self.d_from.iso())} đến ngày {vn_date(self.d_to.iso())}. Bên A: {c['name']} (MST {c['tax_code']}). "
                f"Bên B: {p['name']} (MST {p['tax_code'] or ''}). Số dư đầu kỳ: {fmt_money(d['opening'], False)}. "
                f"Số dư cuối kỳ: {fmt_money(abs(close), False)} – {side}.")
        rows.append(["", "", "Cộng phát sinh", d["total_d"], d["total_c"]])
        html = export.to_html("Biên bản đối chiếu công nợ", head, _company_line(self.s),
                              ["Ngày", "Chứng từ", "Diễn giải", "Phát sinh Nợ", "Phát sinh Có"], rows, {3, 4}, {len(rows) - 1},
                              [f"Đại diện bên A\n{c['name']}", f"Đại diện bên B\n{p['name']}"])
        export.print_preview(self, html, False)


# ======================================================================= KHO
class InventoryView(QWidget):
    def __init__(self, ctx, tab: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = InventoryService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)
        top = QHBoxLayout()
        top.addWidget(_page_title("QUẢN LÝ HÀNG TỒN KHO"))
        top.addSpacing(10)
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        self.cb_wh = QComboBox()
        self.cb_wh.addItem("Tất cả kho", None)
        for r in self.s.db.query("SELECT id, code, name FROM warehouse WHERE company_id=? ORDER BY code", (self.s.company_id,)):
            self.cb_wh.addItem(f"{r['code']} — {r['name']}", r["id"])
        for w in (QLabel("Từ ngày"), self.d_from, QLabel("đến"), self.d_to, QLabel("Kho"), self.cb_wh):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        bc = tool_button("Tính giá xuất kho…", "calc", None, "Mở bảng xem trước tính giá xuất kho")
        bc.clicked.connect(lambda: self.ctx.open("m_tinhgia"))
        top.addWidget(bc)
        top.addStretch(1)
        root.addLayout(top)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        # NXT
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.setContentsMargins(0, 4, 0, 0)
        b1 = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Lọc mã / tên hàng…")
        self.search.setMaximumWidth(260)
        self.search.textChanged.connect(lambda _: self._render_nxt())
        b1.addWidget(self.search)
        b1.addWidget(_hint("Số liệu từ chứng từ ĐÃ GHI SỔ trên TK 152, 153, 155, 156. Nhấp đúp để mở thẻ kho."), 1)
        self.t_nxt = ReportTable()
        b1.addWidget(ExportBar(self.t_nxt, lambda: ("Báo cáo nhập – xuất – tồn",
                                                    f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())} · "
                                                    f"{self.cb_wh.currentText()}"), self.s, self))
        l1.addLayout(b1)
        l1.addWidget(self.t_nxt, 1)
        self.tabs.addTab(w1, "Nhập – xuất – tồn")
        # Thẻ kho
        w2 = QWidget(); l2 = QVBoxLayout(w2); l2.setContentsMargins(0, 4, 0, 0)
        b2 = QHBoxLayout()
        b2.addWidget(QLabel("Mã hàng"))
        self.cb_item = QComboBox()
        self.cb_item.setMinimumWidth(320)
        self.cb_item.setEditable(True)
        for r in self.s.db.query("SELECT id, code, name FROM item WHERE company_id=? AND kind<>'DV' ORDER BY code",
                                 (self.s.company_id,)):
            self.cb_item.addItem(f"{r['code']} — {r['name']}", r["id"])
        self.cb_item.completer().setFilterMode(Qt.MatchContains)
        self.cb_item.activated.connect(lambda _: self._render_card())
        b2.addWidget(self.cb_item)
        b2.addStretch(1)
        self.t_card = ReportTable()
        b2.addWidget(ExportBar(self.t_card, lambda: (f"Thẻ kho – {self.cb_item.currentText()}",
                                                     f"{self.cb_wh.currentText()} · Từ {vn_date(self.d_from.iso())} đến "
                                                     f"{vn_date(self.d_to.iso())}"), self.s, self))
        l2.addLayout(b2)
        l2.addWidget(self.t_card, 1)
        self.tabs.addTab(w2, "Thẻ kho")
        self.t_nxt.rowActivated.connect(self._open_card)
        self.t_card.rowActivated.connect(lambda vid: isinstance(vid, int) and self.ctx.open_voucher(vid))
        self.cb_wh.activated.connect(lambda _: self.refresh())
        self.refresh()
        self.tabs.setCurrentIndex(tab)

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        self.rows = self.svc.nxt(self.d_from.iso(), self.d_to.iso(), self.cb_wh.currentData())
        self._render_nxt()
        self._render_card()

    def _render_nxt(self):
        t = self.search.text().strip().lower()
        rows = [r for r in self.rows if not t or t in r.item_code.lower() or t in r.item_name.lower()]
        data = [[r.item_code, r.item_name, r.unit, r.warehouse_code, r.ob_q, r.ob_v, r.in_q, r.in_v, r.out_q, r.out_v,
                 r.cb_q, r.cb_v] for r in rows]
        tot = [sum(r.ob_v for r in rows), sum(r.in_v for r in rows), sum(r.out_v for r in rows), sum(r.cb_v for r in rows)]
        data.append(["", "TỔNG CỘNG", "", "", None, tot[0], None, tot[1], None, tot[2], None, tot[3]])
        self.t_nxt.fill(["Mã hàng", "Tên hàng", "ĐVT", "Kho", "SL tồn đầu", "GT tồn đầu", "SL nhập", "GT nhập", "SL xuất",
                         "GT xuất", "SL tồn cuối", "GT tồn cuối"], data, money_cols={5, 7, 9, 11},
                        widths=[75, 220, 55, 70, 80, 115, 75, 120, 75, 120, 85, 120],
                        keys=[r.item_id * 100000 + (r.warehouse_id or 0) for r in rows] + [None], total_rows={len(rows)},
                        center_cols={2, 3}, stretch_col=1)
        for i, r in enumerate(rows):
            if r.cb_q < 0:
                for j in (10, 11):
                    self.t_nxt.item(i, j).setForeground(QColor("#B42318"))

    def _open_card(self, key):
        item_id, wh = divmod(key, 100000)
        self.cb_item.setCurrentIndex(max(0, self.cb_item.findData(item_id)))
        self.cb_wh.setCurrentIndex(max(0, self.cb_wh.findData(wh or None)))
        self._render_card()
        self.tabs.setCurrentIndex(1)

    def _render_card(self):
        iid = self.cb_item.currentData()
        if not iid:
            return
        c = self.svc.stock_card(iid, self.cb_wh.currentData(), self.d_from.iso(), self.d_to.iso())
        data = [["", "", "", "Tồn đầu kỳ", None, None, c["opening_q"], None, None, c["opening_v"]]]
        keys = [None]
        for r in c["rows"]:
            data.append([vn_date(r["posting_date"]), r["number"], r["account_code"] + "/" + (r["contra_account"] or ""),
                         r["description"] or "", r["in_q"] or None, r["out_q"] or None, r["bal_q"], r["debit"] or None,
                         r["credit"] or None, r["bal_v"]])
            keys.append(r["voucher_id"])
        data.append(["", "", "", "Tồn cuối kỳ", None, None, c["closing_q"], None, None, c["closing_v"]])
        keys.append(None)
        self.t_card.fill(["Ngày", "Chứng từ", "TK/TK ĐƯ", "Diễn giải", "SL nhập", "SL xuất", "SL tồn", "GT nhập", "GT xuất",
                          "GT tồn"], data, money_cols={7, 8, 9}, widths=[82, 85, 85, 330, 75, 75, 80, 120, 120, 120],
                         keys=keys, total_rows={0, len(data) - 1}, center_cols={0, 2}, stretch_col=3)


class OpeningStockView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = InventoryService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        bar = QHBoxLayout()
        self.heading = _page_title("")
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
        self.table.setHorizontalHeaderLabels(["Mã hàng", "Tên hàng", "Mã kho", "Số lượng", "Giá trị"])
        for j, w in enumerate((110, 320, 100, 120, 160)):
            self.table.setColumnWidth(j, w)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._changed)
        root.addWidget(self.table, 1)
        root.addWidget(SectionHeader("Đối chiếu với số dư đầu năm trên sổ (TK kho)"))
        self.cmp = ReportTable()
        self.cmp.setMaximumHeight(120)
        root.addWidget(self.cmp)
        root.addWidget(_hint("Tồn kho đầu kỳ theo từng mã hàng + kho; tổng giá trị theo TK kho của mã hàng phải bằng số dư đầu năm "
                             "của TK đó (Danh mục → Số dư đầu kỳ). Lệch sẽ hiện trong Trung tâm cảnh báo."))
        self.refresh()

    def refresh(self):
        self.heading.setText(f"TỒN KHO ĐẦU NĂM {self.s.year}")
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for r in self.svc.opening_rows(self.s.year):
            self._append(r["item_code"], r["item_name"], r["wh_code"], fmt_decimal(r["quantity"]), fmt_money(r["amount"]))
        self.table.blockSignals(False)
        self._compare()

    def _append(self, *vals):
        i = self.table.rowCount()
        self.table.insertRow(i)
        vals = vals or ("", "", "", "", "")
        for j, v in enumerate(vals):
            it = QTableWidgetItem(v)
            if j == 1:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            if j >= 3:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, j, it)

    def _changed(self, it):
        if it.column() == 0:
            name = self.s.db.scalar("SELECT name FROM item WHERE company_id=? AND code=?", (self.s.company_id, it.text().strip()), "")
            self.table.blockSignals(True)
            self.table.item(it.row(), 1).setText(name or "(không có mã hàng)")
            self.table.blockSignals(False)

    def _rows(self):
        g = lambda i, j: self.table.item(i, j).text() if self.table.item(i, j) else ""
        return [{"item_code": g(i, 0), "warehouse_code": g(i, 2), "quantity": g(i, 3), "amount": g(i, 4)}
                for i in range(self.table.rowCount())]

    def _compare(self):
        rows = self.svc.opening_vs_ledger(self.s.year)
        self.cmp.fill(["TK kho", "Tổng tồn kho chi tiết", "Số dư đầu năm trên sổ", "Chênh lệch"],
                      [[a, s_, o, d] for a, s_, o, d in rows], money_cols={1, 2, 3}, widths=[90, 180, 180, 150])
        for i, r in enumerate(rows):
            if r[3]:
                self.cmp.item(i, 3).setForeground(QColor("#B42318"))

    def add_row(self):
        self._append()
        self.table.setCurrentCell(self.table.rowCount() - 1, 0)

    def del_row(self):
        if self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())

    def save(self):
        ok, _ = run(self, self.svc.save_opening, self.s.year, self._rows())
        if ok:
            info(self, "Đã lưu tồn kho đầu kỳ.")
            self.refresh()
            self.ctx.voucher_changed()


class CostingDialog(QDialog):
    """Tính giá xuất kho: xem trước theo mã hàng + kho → xác nhận → cập nhật dòng xuất (ghi lại sổ)."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx, self.s = ctx, ctx.session
        self.svc = InventoryService(self.s)
        self.setWindowTitle("Tính giá xuất kho – xem trước")
        self.resize(1180, 640)
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        self.cb_method = QComboBox()
        for k, v in METHODS.items():
            self.cb_method.addItem(v, k)
        self.cb_method.setCurrentIndex(max(0, self.cb_method.findData(self.svc.method())))
        self.cb_method.setEnabled(False)
        self.cb_method.setToolTip("Phương pháp theo cấu hình doanh nghiệp (Cài đặt → Doanh nghiệp & chế độ kế toán)")
        for w in (QLabel("Kỳ tính giá: từ"), self.d_from, QLabel("đến"), self.d_to, QLabel("Phương pháp"), self.cb_method):
            bar.addWidget(w)
        b = tool_button("Xem trước", "search", "primary")
        b.clicked.connect(self.refresh)
        bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)
        scope = QLabel("<b>Phạm vi:</b> bình quân gia quyền cuối tháng hoặc FIFO theo từng mã hàng + kho; cập nhật dòng xuất "
                       "ĐÃ GHI SỔ (phiếu xuất, chứng từ không có thuế tự sinh) trong kỳ chưa khóa, kỳ trọn tháng; sổ sách được ghi "
                       "lại tự động trong cùng giao dịch. Chưa hỗ trợ chuyển kho nội bộ, bình quân tức thời, đích danh, hàng gửi "
                       "bán – các dòng này được giữ nguyên và cảnh báo. Chứng từ nháp không tham gia.")
        scope.setWordWrap(True)
        scope.setObjectName("Hint")
        lay.addWidget(scope)
        split = QSplitter(Qt.Vertical)
        self.table = ReportTable()
        split.addWidget(self.table)
        low = QWidget(); ll = QHBoxLayout(low); ll.setContentsMargins(0, 0, 0, 0)
        self.changes = ReportTable()
        self.warn = ReportTable()
        ll.addWidget(self.changes, 3)
        ll.addWidget(self.warn, 2)
        split.addWidget(low)
        split.setSizes([360, 180])
        lay.addWidget(split, 1)
        bb = QHBoxLayout()
        self.summary = QLabel()
        bb.addWidget(self.summary, 1)
        self.b_apply = tool_button("Cập nhật giá xuất kho", "post", "post")
        close = tool_button("Đóng", "cancel")
        self.b_apply.clicked.connect(self.apply)
        close.clicked.connect(self.reject)
        bb.addWidget(self.b_apply)
        bb.addWidget(close)
        lay.addLayout(bb)
        self.changes.rowActivated.connect(lambda vid: (self.ctx.open_voucher(vid), self.accept()))
        self.refresh()

    def refresh(self):
        try:
            res = self.svc.costing_preview(self.d_from.iso(), self.d_to.iso())
        except Exception as e:  # noqa: BLE001 – báo lỗi kỳ không hợp lệ ngay trên hộp thoại
            self.table.fill(["Thông báo"], [[str(e)]], stretch_col=0)
            self.changes.fill([], [])
            self.warn.fill([], [])
            self.summary.setText(f"<span style='color:#B42318'>{_html.escape(str(e))}</span>")
            self.b_apply.setEnabled(False)
            return
        self.res = res
        data = [[r["item_code"], r["item_name"], r["warehouse"], r["ob_q"], r["ob_v"], r["in_q"], r["in_v"], r["out_q"],
                 r["old_out_v"], r["new_out_v"], r["new_out_v"] - r["old_out_v"], r["cb_q"], r["cb_v"]] for r in res.rows]
        self.table.fill(["Mã hàng", "Tên hàng", "Kho", "SL tồn đầu", "GT tồn đầu", "SL nhập", "GT nhập", "SL xuất",
                         "GT xuất hiện ghi", "GT xuất tính lại", "Chênh lệch", "SL tồn cuối", "GT tồn cuối"], data,
                        money_cols={4, 6, 8, 9, 10, 12}, widths=[70, 180, 60, 75, 110, 65, 115, 65, 115, 115, 100, 80, 110],
                        stretch_col=1)
        lid_to_v = {r["id"]: r["voucher_id"] for r in self.s.db.query(
            f"SELECT id, voucher_id FROM voucher_line WHERE id IN ({','.join('?' * len(res.changes)) or 'NULL'})",
            [c[0] for c in res.changes])}
        self.changes.fill(["Chứng từ", "Đơn giá mới", "Thành tiền cũ", "Thành tiền mới", "Chênh lệch"],
                          [[c[4], c[1], c[3], c[2], c[2] - c[3]] for c in res.changes], money_cols={2, 3, 4},
                          widths=[100, 110, 120, 120, 110], keys=[lid_to_v.get(c[0]) for c in res.changes])
        self.warn.fill(["Cảnh báo"], [[w] for w in res.warnings] or [["Không có cảnh báo."]], stretch_col=0)
        self.summary.setText(f"<b>{len(res.changes)}</b> dòng xuất sẽ được cập nhật · Tổng chênh lệch giá vốn: "
                             f"<b>{fmt_money(res.total_change, False)}</b> · Phương pháp: {METHODS[res.method]}")
        self.b_apply.setEnabled(bool(res.changes) and self.s.user.can("post"))

    def apply(self):
        if not confirm(self, f"Cập nhật đơn giá cho {len(self.res.changes)} dòng xuất kho và ghi lại sổ sách?\n"
                             "Thao tác được ghi nhật ký; có thể chạy lại khi số liệu nhập thay đổi."):
            return
        ok, res = run(self, self.svc.costing_apply, self.d_from.iso(), self.d_to.iso())
        if ok:
            self.ctx.voucher_changed()
            info(self, f"Đã cập nhật {len(res.changes)} dòng xuất kho. Chênh lệch giá vốn: {fmt_money(res.total_change, False)}.")
            self.refresh()


# ======================================================================= MUA – BÁN
class BatchIssueView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = TradeService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("XUẤT KHO HÀNG LOẠT"))
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (QLabel("Bảng kê bán từ"), self.d_from, QLabel("đến"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        root.addLayout(top)
        root.addWidget(_hint("Danh sách bảng kê bán hàng có mặt hàng tồn kho nhưng CHƯA có phiếu xuất kho liên kết. Phiếu xuất "
                             "lập ra: Nợ 632 / Có TK kho của mã hàng, đơn giá TẠM TÍNH bình quân đến ngày xuất – cuối kỳ chạy "
                             "«Tính giá xuất kho» để tính lại chính xác. Tích chọn rồi bấm «Lập phiếu xuất»."))
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)
        bb = QHBoxLayout()
        self.chk_all = QCheckBox("Chọn tất cả")
        self.chk_all.toggled.connect(self._toggle_all)
        self.chk_post = QCheckBox("Ghi sổ ngay sau khi lập")
        self.chk_post.setEnabled(self.s.user.can("post"))
        bb.addWidget(self.chk_all)
        bb.addWidget(self.chk_post)
        bb.addStretch(1)
        self.b_make = tool_button("Lập phiếu xuất", "box_out", "primary")
        self.b_make.clicked.connect(self.make)
        self.b_make.setEnabled(self.s.user.can("add"))
        bb.addWidget(self.b_make)
        root.addLayout(bb)
        self.table.cellDoubleClicked.connect(lambda r, c: self.ctx.open_voucher(self.items[r]["id"]))
        self.refresh()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        self.items = self.svc.pending_issues(self.d_from.iso(), self.d_to.iso())
        heads = ["Chọn", "Bảng kê", "Ngày", "Trạng thái", "Khách hàng", "Mặt hàng (SL – kho)"]
        self.table.setColumnCount(len(heads))
        self.table.setHorizontalHeaderLabels(heads)
        self.table.setRowCount(len(self.items))
        from ketoan.domain.constants import STATUS_LABEL
        for i, p in enumerate(self.items):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, chk)
            desc = "; ".join(f"{l['item_code']} × {fmt_decimal(l['quantity'])} – {l['wh_code'] or 'chưa chọn kho'}"
                             for l in p["lines"])
            for j, v in enumerate((p["number"], vn_date(p["posting_date"]), STATUS_LABEL[p["status"]],
                                   f"{p['partner_code'] or ''} {p['partner_name'] or ''}", desc), 1):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, it)
        for j, w in enumerate((50, 90, 85, 100, 300, 520)):
            self.table.setColumnWidth(j, w)
        self.table.horizontalHeader().setStretchLastSection(True)

    def _toggle_all(self, on):
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def make(self):
        ids = [self.items[i]["id"] for i in range(self.table.rowCount()) if self.table.item(i, 0).checkState() == Qt.Checked]
        if not ids:
            error(self, "Chưa chọn bảng kê nào.")
            return
        if not confirm(self, f"Lập {len(ids)} phiếu xuất kho" + (" và ghi sổ" if self.chk_post.isChecked() else " (nháp)") + "?"):
            return
        ok, created = run(self, self.svc.create_issues, ids, self.chk_post.isChecked())
        if ok:
            self.ctx.voucher_changed()
            info(self, f"Đã lập {len(created)} phiếu xuất kho.")
            self.refresh()


class RevenueCogsView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = TradeService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("ĐỐI CHIẾU DOANH THU – GIÁ VỐN"))
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        self.table = ReportTable()
        top.addWidget(ExportBar(self.table, lambda: ("Đối chiếu doanh thu – giá vốn",
                                                     f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())}"),
                                self.s, self))
        root.addLayout(top)
        root.addWidget(self.table, 1)
        root.addWidget(_hint("Doanh thu: phát sinh TK 511 có mã hàng; giá vốn: phát sinh TK 632 có mã hàng (chứng từ đã ghi sổ). "
                             "Dịch vụ không đối chiếu số lượng. Lệch số lượng → dùng «Xuất kho hàng loạt»; giá vốn chưa chính xác "
                             "→ chạy «Tính giá xuất kho»."))
        self.refresh()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        rows = self.svc.revenue_cogs(self.d_from.iso(), self.d_to.iso())
        data = [[r["code"], r["name"], r["unit"], r["sold_q"], r["revenue"], r["out_q"], r["cogs"], r["diff_q"] or None,
                 r["margin"], f"{r['margin_pct']:.1f}%" if r["margin_pct"] is not None else "", r["warning"]] for r in rows]
        tot = [sum(r[k] for r in rows) for k in ("revenue", "cogs", "margin")]
        data.append(["", "TỔNG CỘNG", "", None, tot[0], None, tot[1], None, tot[2],
                     f"{tot[2] * 100 / tot[0]:.1f}%" if tot[0] else "", ""])
        self.table.fill(["Mã hàng", "Tên hàng", "ĐVT", "SL bán", "Doanh thu", "SL xuất (giá vốn)", "Giá vốn", "Lệch SL",
                         "Lãi gộp", "Tỷ suất", "Cảnh báo"], data, money_cols={4, 6, 8},
                        widths=[75, 220, 55, 75, 130, 110, 130, 75, 120, 70, 260], total_rows={len(rows)}, center_cols={2, 9})
        for i, r in enumerate(rows):
            if r["warning"]:
                self.table.item(i, 10).setForeground(QColor("#B42318"))


# ======================================================================= HÓA ĐƠN XML
class XmlInvoiceView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = XmlInvoiceService(self.s)
        self.invoices = []
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("ĐỌC HÓA ĐƠN ĐIỆN TỬ XML"))
        b = tool_button("Chọn file XML…", "import", "primary")
        b.clicked.connect(self.choose)
        top.addWidget(b)
        top.addStretch(1)
        root.addLayout(top)
        root.addWidget(_hint("Cấu trúc hỗ trợ: hóa đơn GTGT XML (thẻ HDon/DLHDon: TTChung, NBan, NMua, DSHHDVu/HHDVu, TToan), "
                             "tiền VND. Ứng dụng KHÔNG kiểm tra chữ ký số, KHÔNG tra cứu trạng thái hóa đơn với cơ quan thuế. "
                             "Kết quả chỉ là ĐỀ XUẤT – kiểm tra, sửa mã hàng/TK/kho rồi bấm «Tạo chứng từ nháp»."))
        split = QSplitter(Qt.Vertical)
        self.list = ReportTable()
        split.addWidget(self.list)
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(0, 0, 0, 0)
        self.head = QLabel()
        self.head.setWordWrap(True)
        self.head.setTextFormat(Qt.RichText)
        dl.addWidget(self.head)
        self.lines = QTableWidget()
        self.lines.verticalHeader().setVisible(False)
        self.lines.itemChanged.connect(self._edit_line)
        dl.addWidget(self.lines, 2)
        low = QHBoxLayout()
        self.checks = ReportTable()
        self.warns = ReportTable()
        low.addWidget(self.checks, 3)
        low.addWidget(self.warns, 2)
        dl.addLayout(low, 1)
        bb = QHBoxLayout()
        self.chk_round = QCheckBox("Dồn chênh lệch làm tròn tiền thuế (≤ số dòng × 1đ) vào dòng cuối cho khớp hóa đơn")
        bb.addWidget(self.chk_round)
        bb.addStretch(1)
        self.b_partner = tool_button("Tạo đối tượng mới", "user")
        self.b_create = tool_button("Tạo chứng từ nháp", "add", "primary")
        self.b_partner.clicked.connect(self.create_partner)
        self.b_create.clicked.connect(self.create_voucher)
        bb.addWidget(self.b_partner)
        bb.addWidget(self.b_create)
        dl.addLayout(bb)
        split.addWidget(detail)
        split.setSizes([150, 450])
        root.addWidget(split, 1)
        self.list.itemSelectionChanged.connect(self.show_current)
        self._render_list()
        self.show_current()

    def choose(self, paths=None):
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(self, "Chọn hóa đơn XML", "", "Hóa đơn XML (*.xml)")
        errors = []
        for p in paths or []:
            try:
                self.invoices.append(self.svc.analyze(parse_file(p)))
            except Exception as e:  # noqa: BLE001 – từng file báo lỗi riêng
                errors.append(str(e))
        self._render_list()
        if errors:
            error(self, "\n".join(errors), "Một số file không đọc được")
        if self.invoices:
            self.list.selectRow(len(self.invoices) - 1)

    def _status(self, inv):
        if inv.duplicate_of:
            return f"Đã nhập ({inv.duplicate_of})"
        if not inv.direction:
            return "Không thuộc DN"
        if getattr(inv, "voucher_id", None):
            return "Đã tạo chứng từ"
        if not inv.partner_code or any(c[3] for c in self.svc.checks(inv)):
            return "Cần kiểm tra"
        return "Sẵn sàng"

    def _render_list(self):
        self.list.fill(["File", "Loại", "Ký hiệu", "Số HĐ", "Ngày", "Đối tác", "MST", "Tổng thanh toán", "Trạng thái"],
                       [[Path(i.path).name, {"BKMH": "Mua vào", "BKBH": "Bán ra"}.get(i.direction, "?"), i.series, i.number,
                         vn_date(i.date), i.seller_name if i.direction != "BKBH" else i.buyer_name,
                         i.seller_tax if i.direction != "BKBH" else i.buyer_tax, i.total_payment, self._status(i)]
                        for i in self.invoices], money_cols={7}, widths=[200, 62, 72, 72, 80, 230, 92, 110, 150],
                       keys=list(range(len(self.invoices))))
        colors = {"Sẵn sàng": "#1E7A34", "Cần kiểm tra": "#9A6700"}
        for r, inv in enumerate(self.invoices):
            self.list.item(r, 8).setForeground(QColor(colors.get(self._status(inv), "#B42318")))

    @property
    def current(self):
        r = self.list.currentRow()
        return self.invoices[r] if 0 <= r < len(self.invoices) else None

    def show_current(self):
        inv = self.current
        self.b_partner.setEnabled(False)
        self.b_create.setEnabled(False)
        if not inv:
            self.head.setText("<i>Chưa có hóa đơn. Bấm «Chọn file XML…» (có thể chọn nhiều file; file mẫu trong sample_data/hoa_don_xml).</i>")
            self.lines.setRowCount(0)
            self.checks.fill([], [])
            self.warns.fill([], [])
            return
        kind = {"BKMH": "MUA VÀO → Bảng kê mua hàng", "BKBH": "BÁN RA → Bảng kê bán hàng"}.get(inv.direction, "KHÔNG THUỘC DOANH NGHIỆP")
        e = _html.escape
        self.head.setText(f"<b>{kind}</b> · Ký hiệu <b>{e(inv.series)}</b> số <b>{e(inv.number)}</b> ngày {vn_date(inv.date)} · "
                          f"Người bán: {e(inv.seller_name)} (MST {e(inv.seller_tax)}) · Người mua: {e(inv.buyer_name)} "
                          f"(MST {e(inv.buyer_tax)}) · Đối tượng trong danh mục: <b>{e(inv.partner_code or 'chưa có')}</b>")
        heads = ["STT", "Mã trên HĐ", "Tên hàng hóa, dịch vụ", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền", "Thuế suất",
                 "Mã hàng (danh mục)", "TK hạch toán", "Kho"]
        self.lines.blockSignals(True)
        self.lines.setColumnCount(len(heads))
        self.lines.setHorizontalHeaderLabels(heads)
        self.lines.setRowCount(len(inv.lines))
        for i, l in enumerate(inv.lines):
            vals = [l.stt, l.code, l.name, l.unit, fmt_decimal(l.quantity), fmt_decimal(l.price), fmt_money(l.amount),
                    l.rate_text, l.item_code, l.account, l.warehouse]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j < 8:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    it.setBackground(QColor("#F5F7FA"))
                else:
                    it.setBackground(QColor("#FFFDE8"))
                if j in (4, 5, 6):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.lines.setItem(i, j, it)
        for j, w in enumerate((36, 75, 250, 50, 70, 95, 105, 62, 135, 95, 70)):
            self.lines.setColumnWidth(j, w)
        self.lines.blockSignals(False)
        chks = self.svc.checks(inv)
        self.checks.fill(["Đối chiếu", "Trên hóa đơn", "Tính lại", "Chênh lệch"], [list(c) for c in chks],
                         money_cols={1, 2, 3}, widths=[200, 120, 120, 100])
        for i, c in enumerate(chks):
            if c[3]:
                self.checks.item(i, 3).setForeground(QColor("#B42318"))
        ws = list(inv.warnings) + ([f"Hóa đơn đã được nhập ở chứng từ {inv.duplicate_of}."] if inv.duplicate_of else [])
        self.warns.fill(["Cảnh báo"], [[w] for w in ws] or [["Không có cảnh báo."]], stretch_col=0)
        ready = bool(inv.direction) and not inv.duplicate_of and not getattr(inv, "voucher_id", None)
        self.b_partner.setEnabled(ready and not inv.partner_code and self.s.user.can("add"))
        self.b_create.setEnabled(ready and bool(inv.partner_code) and self.s.user.can("add"))
        tax_diff = next((c[3] for c in chks if c[0] == "Tổng tiền thuế"), 0)
        self.chk_round.setEnabled(bool(tax_diff) and abs(tax_diff) <= len(inv.lines))

    def _edit_line(self, it):
        inv = self.current
        if not inv:
            return
        l = inv.lines[it.row()]
        val = it.text().strip()
        if it.column() == 8:
            if val and not self.s.db.scalar("SELECT 1 FROM item WHERE company_id=? AND code=?", (self.s.company_id, val)):
                error(self, f"Mã hàng '{val}' không có trong danh mục.")
                it.setText(l.item_code)
                return
            l.item_code = val
        elif it.column() == 9:
            if val and not self.s.db.scalar("SELECT 1 FROM account WHERE company_id=? AND code=? AND is_detail=1",
                                            (self.s.company_id, val)):
                error(self, f"TK '{val}' không có hoặc là TK tổng hợp.")
                it.setText(l.account)
                return
            l.account = val
        elif it.column() == 10:
            l.warehouse = val

    def create_partner(self):
        inv = self.current
        if inv and confirm(self, "Tạo đối tượng mới theo thông tin trên hóa đơn (tên, MST, địa chỉ)?"):
            ok, code = run(self, self.svc.create_partner, inv)
            if ok:
                inv.warnings = [w for w in inv.warnings if not w.startswith("Chưa có đối tượng")]
                self.ctx.catalog_changed()
                self._render_list()
                self.show_current()
                info(self, f"Đã tạo đối tượng {code}.")

    def create_voucher(self):
        inv = self.current
        if not inv:
            return
        ok, vid = run(self, self.svc.create_voucher, inv, self.chk_round.isChecked())
        if ok:
            inv.voucher_id = vid
            self.ctx.voucher_changed()
            self._render_list()
            self.show_current()
            self.ctx.open_voucher(vid)

