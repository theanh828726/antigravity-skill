"""Sổ kế toán: Nhật ký chung, Sổ cái, Sổ chi tiết tài khoản (Sổ quỹ, Sổ TGNH), Bảng cân đối số phát sinh.

Truy ngược: CĐSPS (nhấp đúp TK) → Sổ chi tiết TK (nhấp đúp dòng) → Chứng từ gốc.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QComboBox, QCompleter, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ketoan.domain.money import fmt_money
from ketoan.services.ledger_service import LedgerService
from ketoan.ui.widgets import DateEdit, ExportBar, ReportTable, tool_button, vn_date


class BaseReport(QWidget):
    title_text = ""
    landscape = True

    def __init__(self, ctx, d_from=None, d_to=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.ls = LedgerService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(5)
        self.heading = QLabel(self.title_text.upper())
        self.heading.setObjectName("PageTitle")
        top.addWidget(self.heading)
        top.addSpacing(12)
        top.addWidget(QLabel("Từ ngày"))
        self.d_from = DateEdit(d_from or self.s.date_from)
        top.addWidget(self.d_from)
        top.addWidget(QLabel("đến"))
        self.d_to = DateEdit(d_to or self.s.date_to)
        top.addWidget(self.d_to)
        b = tool_button("Xem", "search", "primary", "Xem báo cáo")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        self.table = ReportTable()
        top.addWidget(ExportBar(self.table, self.titles, self.s, self, self.landscape))
        root.addLayout(top)
        self.filters = QHBoxLayout()          # hàng bộ lọc riêng: tài khoản, đối tượng, tùy chọn
        self.filters.setSpacing(6)
        root.addLayout(self.filters)
        root.addWidget(self.table, 1)
        self.footer = QLabel()
        self.footer.setObjectName("Hint")
        root.addWidget(self.footer)
        self.table.rowActivated.connect(self.drill)

    def build_filters(self):
        pass

    def titles(self):
        return self.title_text, f"Từ ngày {vn_date(self.d_from.iso())} đến ngày {vn_date(self.d_to.iso())}"

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def drill(self, key):
        if isinstance(key, int):
            self.ctx.open_voucher(key)

    def account_combo(self, default: str = ""):
        cb = QComboBox()
        cb.setEditable(True)
        cb.setMinimumWidth(320)
        for r in self.ls.accounts():
            cb.addItem(f"{r['code']} — {r['name']}", r["code"])
        cb.completer().setFilterMode(Qt.MatchContains)
        cb.completer().setCompletionMode(QCompleter.PopupCompletion)
        idx = cb.findData(default)
        cb.setCurrentIndex(idx if idx >= 0 else 0)
        return cb

    @staticmethod
    def combo_code(cb) -> str:
        data = cb.currentData()
        text = cb.currentText().split("—")[0].strip()
        if data and cb.itemText(cb.currentIndex()) == cb.currentText():
            return data
        return text


# ================================================================ Nhật ký chung
class JournalView(BaseReport):
    title_text = "Sổ nhật ký chung"

    def __init__(self, ctx, **kw):
        super().__init__(ctx, kw.get("d_from"), kw.get("d_to"))
        self.refresh()

    def refresh(self):
        rows = self.ls.general_journal(self.d_from.iso(), self.d_to.iso())
        data, keys, td, tc = [], [], 0, 0
        for r in rows:
            data.append([vn_date(r["posting_date"]), r["number"], vn_date(r["voucher_date"]), r["description"] or "",
                         r["account_code"], r["contra_account"] or "", r["partner_code"] or "", r["debit"], r["credit"]])
            keys.append(r["voucher_id"])
            td += r["debit"]
            tc += r["credit"]
        data.append(["", "", "", "Cộng phát sinh", "", "", "", td, tc])
        keys.append(None)
        self.table.fill(["Ngày ghi sổ", "Số CT", "Ngày CT", "Diễn giải", "Số hiệu TK", "TK đối ứng", "Mã đối tượng",
                         "Phát sinh Nợ", "Phát sinh Có"], data, money_cols={7, 8},
                        widths=[82, 82, 82, 380, 80, 80, 95, 125, 125], keys=keys, total_rows={len(data) - 1},
                        center_cols={0, 2, 4, 5}, stretch_col=3)
        self.footer.setText(f"{len(rows)} dòng bút toán · Tổng Nợ {fmt_money(td, False)} · Tổng Có {fmt_money(tc, False)} · "
                            f"{'Cân đối ✓' if td == tc else 'LỆCH ✗'} · Nhấp đúp để mở chứng từ gốc.")


# ================================================================ Sổ cái
class GeneralLedgerView(BaseReport):
    title_text = "Sổ cái"

    def __init__(self, ctx, account: str = "111", **kw):
        super().__init__(ctx, kw.get("d_from"), kw.get("d_to"))
        self.filters.addWidget(QLabel("Tài khoản"))
        self.cb_acc = self.account_combo(account)
        self.cb_acc.activated.connect(lambda _: self.refresh())
        self.filters.addWidget(self.cb_acc)
        self.filters.addStretch(1)
        self.refresh()

    def titles(self):
        code = self.combo_code(self.cb_acc)
        return (f"Sổ cái tài khoản {code} – {self.ls.account_name(code)}",
                f"Từ ngày {vn_date(self.d_from.iso())} đến ngày {vn_date(self.d_to.iso())}")

    def refresh(self):
        code = self.combo_code(self.cb_acc)
        d = self.ls.general_ledger(code, self.d_from.iso(), self.d_to.iso())
        ob = d["opening"]
        data = [["", "", "", "Số dư đầu kỳ", "", max(ob, 0), max(-ob, 0)]]
        keys = [None]
        for r in d["rows"]:
            data.append([vn_date(r["posting_date"]), r["number"], vn_date(r["voucher_date"]), r["description"] or "",
                         r["contra_account"] or "", r["debit"], r["credit"]])
            keys.append(r["voucher_id"])
        cb = d["closing"]
        totals = {0}
        data.append(["", "", "", "Cộng phát sinh trong kỳ", "", d["total_d"], d["total_c"]]); keys.append(None)
        totals.add(len(data) - 1)
        data.append(["", "", "", "Số dư cuối kỳ", "", max(cb, 0), max(-cb, 0)]); keys.append(None)
        totals.add(len(data) - 1)
        data.append(["", "", "", "TỔNG HỢP THEO TÀI KHOẢN ĐỐI ỨNG", "", None, None]); keys.append(None)
        totals.add(len(data) - 1)
        for contra, (dd, cc) in d["by_contra"]:
            data.append(["", "", "", f"Đối ứng {contra}", contra, dd, cc])
            keys.append(("acc", contra))
        self.table.fill(["Ngày ghi sổ", "Số CT", "Ngày CT", "Diễn giải", "TK đối ứng", "Phát sinh Nợ", "Phát sinh Có"],
                        data, money_cols={5, 6}, widths=[82, 82, 82, 430, 90, 130, 130], keys=keys, total_rows=totals,
                        center_cols={0, 2, 4}, stretch_col=3)
        self.footer.setText("Lưu ý: số dư lưỡng tính (131, 331…) trên sổ cái là số bù trừ; xem chi tiết theo đối tượng ở "
                            "Sổ chi tiết tài khoản. Nhấp đúp để mở chứng từ gốc.")

    def drill(self, key):
        if isinstance(key, tuple) and key[0] == "acc" and key[1] and key[1][0].isdigit():
            self.ctx.open("r_socai", account=key[1], d_from=self.d_from.iso(), d_to=self.d_to.iso(), new_tab=True)
        else:
            super().drill(key)


# ================================================================ Sổ chi tiết tài khoản / Sổ quỹ / Sổ TGNH
class AccountDetailView(BaseReport):
    title_text = "Sổ chi tiết tài khoản"

    def __init__(self, ctx, account: str = "131", partner_id=None, cash_book=False, **kw):
        self.cash_book = cash_book
        if cash_book:
            self.title_text = "Sổ quỹ tiền mặt" if account.startswith("111") else "Sổ tiền gửi ngân hàng"
        super().__init__(ctx, kw.get("d_from"), kw.get("d_to"))
        self.filters.addWidget(QLabel("Tài khoản"))
        self.cb_acc = self.account_combo(account)
        self.filters.addWidget(self.cb_acc)
        self.filters.addWidget(QLabel("Đối tượng"))
        self.cb_partner = QComboBox()
        self.cb_partner.setMinimumWidth(300)
        self.filters.addWidget(self.cb_partner)
        self.filters.addStretch(1)
        self.cb_acc.activated.connect(lambda _: (self._load_partners(), self.refresh()))
        self.cb_partner.activated.connect(lambda _: self.refresh())
        self._load_partners(partner_id)
        self.refresh()

    def _load_partners(self, select=None):
        code = self.combo_code(self.cb_acc)
        self.cb_partner.blockSignals(True)
        self.cb_partner.clear()
        self.cb_partner.addItem("Tất cả đối tượng", None)
        for p in self.ls.partners_of_account(code, self.d_from.iso(), self.d_to.iso()):
            self.cb_partner.addItem(f"{p['code']} — {p['name']}", p["id"])
        if select:
            self.cb_partner.setCurrentIndex(max(0, self.cb_partner.findData(select)))
        self.cb_partner.blockSignals(False)

    def titles(self):
        code = self.combo_code(self.cb_acc)
        name = self.ls.account_name(code)
        t = f"{self.title_text} – TK {code} {name}"
        if self.cb_partner.currentData():
            t += f" – {self.cb_partner.currentText()}"
        return t, f"Từ ngày {vn_date(self.d_from.iso())} đến ngày {vn_date(self.d_to.iso())}"

    def refresh(self):
        code = self.combo_code(self.cb_acc)
        d = self.ls.account_detail(code, self.d_from.iso(), self.d_to.iso(), self.cb_partner.currentData())
        ob = d["opening"]
        data = [["", "", "", "Số dư đầu kỳ", "", "", None, None, max(ob, 0), max(-ob, 0)]]
        keys = [None]
        for r in d["rows"]:
            b = r["balance"]
            data.append([vn_date(r["posting_date"]), r["number"], vn_date(r["voucher_date"]), r["description"] or "",
                         r["contra_account"] or "", r["partner_code"] or "", r["debit"], r["credit"], max(b, 0), max(-b, 0)])
            keys.append(r["voucher_id"])
        cb = d["closing"]
        data.append(["", "", "", "Cộng phát sinh trong kỳ", "", "", d["total_d"], d["total_c"], None, None]); keys.append(None)
        data.append(["", "", "", "Số dư cuối kỳ", "", "", None, None, max(cb, 0), max(-cb, 0)]); keys.append(None)
        if self.cash_book:
            heads = ["Ngày ghi sổ", "Số phiếu", "Ngày CT", "Diễn giải", "TK đối ứng", "Mã ĐT", "Thu / Gửi vào",
                     "Chi / Rút ra", "Tồn", "Âm quỹ"]
        else:
            heads = ["Ngày ghi sổ", "Số CT", "Ngày CT", "Diễn giải", "TK đối ứng", "Mã ĐT", "Phát sinh Nợ", "Phát sinh Có",
                     "Dư Nợ", "Dư Có"]
        self.table.fill(heads, data, money_cols={6, 7, 8, 9}, widths=[82, 82, 82, 330, 80, 80, 118, 118, 118, 110],
                        keys=keys, total_rows={0, len(data) - 2, len(data) - 1}, center_cols={0, 2, 4}, stretch_col=3)
        warn = ""
        if self.cash_book and code.startswith("111") and any(r["balance"] < 0 for r in d["rows"]):
            warn = "  ⚠ Có thời điểm tồn quỹ âm – kiểm tra thứ tự chứng từ thu/chi."
        self.footer.setText(f"{len(d['rows'])} dòng · Nhấp đúp để mở chứng từ gốc.{warn}")


# ================================================================ Bảng cân đối số phát sinh
class TrialBalanceView(BaseReport):
    title_text = "Bảng cân đối số phát sinh"

    def __init__(self, ctx, **kw):
        super().__init__(ctx, kw.get("d_from"), kw.get("d_to"))
        self.chk_lvl1 = QCheckBox("Chỉ TK cấp 1")
        self.chk_empty = QCheckBox("Hiện TK không có số liệu")
        for w in (self.chk_lvl1, self.chk_empty):
            w.toggled.connect(self.refresh)
            self.filters.addWidget(w)
        self.filters.addStretch(1)
        self.refresh()

    def refresh(self):
        tb = self.ls.trial_balance(self.d_from.iso(), self.d_to.iso(), self.chk_empty.isChecked())
        rows = [r for r in tb.rows if not self.chk_lvl1.isChecked() or r.level == 1]
        data = [[("   " * (r.level - 1)) + r.code, r.name, r.ob_d, r.ob_c, r.ps_d, r.ps_c, r.cb_d, r.cb_c] for r in rows]
        t = tb.total
        data.append(["", "TỔNG CỘNG", t.ob_d, t.ob_c, t.ps_d, t.ps_c, t.cb_d, t.cb_c])
        self.table.fill(["Số hiệu TK", "Tên tài khoản", "Dư Nợ đầu kỳ", "Dư Có đầu kỳ", "Phát sinh Nợ", "Phát sinh Có",
                         "Dư Nợ cuối kỳ", "Dư Có cuối kỳ"], data, money_cols={2, 3, 4, 5, 6, 7},
                        widths=[85, 300, 125, 125, 125, 125, 125, 125], keys=[("acc", r.code) for r in rows] + [None],
                        total_rows={len(data) - 1}, stretch_col=1)
        bold = QFont()
        bold.setBold(True)
        for i, r in enumerate(rows):
            if r.level == 1:
                for j in range(8):
                    self.table.item(i, j).setFont(bold)
        ok = all(v == 0 for v in tb.balanced.values())
        parts = " · ".join(f"{k}: {'cân ✓' if v == 0 else 'lệch ' + fmt_money(v, False)}" for k, v in tb.balanced.items())
        self.footer.setText(f"Kiểm tra cân đối – {parts}. Nhấp đúp vào tài khoản để xem sổ chi tiết và truy ngược chứng từ.")
        self.footer.setStyleSheet("" if ok else "color:#B42318;font-weight:600")

    def drill(self, key):
        if isinstance(key, tuple) and key[0] == "acc":
            self.ctx.open("r_sct", account=key[1], d_from=self.d_from.iso(), d_to=self.d_to.iso(), new_tab=True)
