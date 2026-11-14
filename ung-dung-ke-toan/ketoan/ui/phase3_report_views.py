"""Giao diện giai đoạn 3 (phần 2): báo cáo tài chính theo mẫu quản lý phiên bản; báo cáo hỗ trợ thuế."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMenu, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ketoan.domain.money import fmt_money
from ketoan.services.report_engine import KINDS, ReportEngine
from ketoan.services.tax_service import TaxService
from ketoan.ui.phase2_views import _hint, _page_title
from ketoan.ui.widgets import DateEdit, ExportBar, ReportTable, SectionHeader, error, info, run, tool_button, vn_date

UNVERIFIED_BANNER = ("⚠ MẪU CHƯA KIỂM CHỨNG: chỉ tiêu và công thức chưa được đối chiếu với văn bản chính thức. Chỉ dùng để thử nghiệm kỹ thuật, "
                     "KHÔNG dùng để nộp hay công bố. Nhập mẫu theo văn bản đã kiểm chứng ở «Quản lý mẫu».")
TAX_BANNER = ("Báo cáo HỖ TRỢ TÍNH TOÁN từ số liệu đã ghi sổ – không phải tờ khai điện tử đã đáp ứng cấu trúc, chỉ tiêu, mẫu biểu của cơ quan thuế. "
              "Ứng dụng không tự suy đoán thuế suất, điều kiện khấu trừ hay biểu thuế; mọi tham số do người dùng nhập và chịu trách nhiệm đối chiếu quy định hiện hành.")


def banner(text: str, warn=True) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setStyleSheet(("background:#FFF8E6;border:1px solid #F0D58C;" if warn else "background:#EAF3FF;border:1px solid #B7D3F5;") + "border-radius:4px;padding:5px 8px;")
    return lab


# ======================================================================= BÁO CÁO TÀI CHÍNH THEO MẪU
class TemplateLinesDialog(QDialog):
    def __init__(self, engine: ReportEngine, tpl, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Chỉ tiêu – {tpl['name']} (v{tpl['version']})")
        self.resize(900, 560)
        lay = QVBoxLayout(self)
        status = ("<b style='color:#1E7A34'>ĐÃ KIỂM CHỨNG</b> bởi " + f"{tpl['verified_by']} – {tpl['verified_note']}") if tpl["verified"] else \
            "<b style='color:#B42318'>CHƯA KIỂM CHỨNG</b>"
        lay.addWidget(QLabel(f"{status}<br/>Căn cứ khai báo khi nhập: {tpl['source_ref'] or '(chưa ghi)'}"))
        t = ReportTable()
        t.fill(["Mã", "Chỉ tiêu", "Công thức", "Thụt lề", "In đậm"], [[l["code"], l["label"], l["formula"], l["indent"], "x" if l["bold"] else ""]
                                                                     for l in engine.lines(tpl["id"])], widths=[70, 380, 340, 60, 60], stretch_col=1, center_cols={3, 4})
        lay.addWidget(t)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Đóng")
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class TemplateImportDialog(QDialog):
    def __init__(self, engine: ReportEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Nhập mẫu báo cáo từ Excel")
        self.setMinimumWidth(560)
        f = QFormLayout(self)
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        bp = tool_button("Chọn file…", "excel")
        bp.clicked.connect(self.choose)
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        row.addWidget(bp)
        self.code, self.name = QLineEdit(), QLineEdit()
        self.kind = QComboBox()
        for k, v in KINDS.items():
            self.kind.addItem(f"{k} – {v}", k)
        self.regime, self.eff = QLineEdit(), QLineEdit()
        self.eff.setPlaceholderText("yyyy-mm-dd")
        self.source = QLineEdit()
        self.source.setPlaceholderText("Văn bản, phụ lục, mẫu số (vd: Thông tư …, Phụ lục …, mẫu …)")
        self.header = QSpinBox()
        self.header.setRange(0, 20)
        self.header.setValue(1)
        for lab, w in (("File Excel (cột A: mã · B: tên chỉ tiêu · C: công thức · D: thụt lề · E: in đậm)", row), ("Mã mẫu *", self.code),
                       ("Tên mẫu *", self.name), ("Loại *", self.kind), ("Mã chế độ kế toán", self.regime), ("Hiệu lực từ", self.eff),
                       ("Căn cứ văn bản *", self.source), ("Số dòng tiêu đề bỏ qua", self.header)):
            f.addRow(lab, w)
        f.addRow(_hint("Mẫu mới nhập ở trạng thái CHƯA KIỂM CHỨNG. Công thức: DN(111,112)+[A2]-PSC(511) – xem Trợ giúp."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Kiểm tra và nhập")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        bb.accepted.connect(self.do_import)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def choose(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file Excel", "", "Excel (*.xlsx *.xlsm)")
        if p:
            self.path.setText(p)

    def do_import(self):
        if not self.path.text():
            error(self, "Chưa chọn file Excel.")
            return
        if not self.source.text().strip():
            error(self, "Cần ghi căn cứ văn bản của mẫu.")
            return
        from openpyxl import load_workbook
        ok, wb = run(self, load_workbook, self.path.text(), read_only=True, data_only=True)
        if not ok:
            return
        ws = wb[wb.sheetnames[0]]
        lines = []
        for i, row in enumerate(ws.iter_rows(min_row=self.header.value() + 1, values_only=True), 1):
            if not any(v not in (None, "") for v in row):
                continue
            cell = lambda j: ("" if j >= len(row) or row[j] is None else str(row[j]).strip())
            lines.append({"code": cell(0), "label": cell(1), "formula": cell(2), "indent": int(float(cell(3) or 0)),
                          "bold": cell(4).lower() in ("1", "x", "true", "có")})
        ok, _ = run(self, self.engine.import_template, self.code.text(), self.name.text(), self.kind.currentData(), self.regime.text(), self.eff.text(),
                    self.source.text(), lines)
        if ok:
            self.accept()


class TemplateManager(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx, self.s = ctx, ctx.session
        self.engine = ReportEngine(self.s)
        self.setWindowTitle("Quản lý mẫu báo cáo tài chính")
        self.resize(980, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(banner("Mẫu báo cáo (chỉ tiêu + công thức) do người dùng nhập từ văn bản của chế độ kế toán áp dụng, có phiên bản. Mẫu mới nhập ở trạng thái "
                             "CHƯA KIỂM CHỨNG; người quản trị xác nhận kiểm chứng kèm căn cứ.", True))
        bar = QHBoxLayout()
        adm = self.s.user.can("admin")
        for text, ic, role, fn, en in (("Nhập mẫu từ Excel…", "import", "primary", self.do_import, adm), ("Xem chỉ tiêu", "list", None, self.view, True),
                                       ("Xác nhận đã kiểm chứng…", "check", None, self.verify, adm)):
            b = tool_button(text, ic, role)
            b.clicked.connect(fn)
            b.setEnabled(en)
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.table = ReportTable()
        lay.addWidget(self.table, 1)
        self.table.rowActivated.connect(lambda _: self.view())
        self.refresh()

    def refresh(self):
        self.rows = self.engine.templates()
        self.table.fill(["Mã mẫu", "Phiên bản", "Tên mẫu", "Loại", "Hiệu lực từ", "Căn cứ", "Kiểm chứng"],
                        [[t["code"], t["version"], t["name"], t["kind"], vn_date(t["effective_from"]), t["source_ref"] or "",
                          "Đã kiểm chứng" if t["verified"] else "CHƯA KIỂM CHỨNG"] for t in self.rows],
                        widths=[100, 70, 280, 50, 90, 280, 130], keys=list(range(len(self.rows))), center_cols={1, 3, 4})
        for i, t in enumerate(self.rows):
            self.table.item(i, 6).setForeground(QColor("#1E7A34" if t["verified"] else "#B42318"))

    def _cur(self):
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def do_import(self):
        if TemplateImportDialog(self.engine, self).exec():
            self.refresh()

    def view(self):
        t = self._cur()
        if t:
            TemplateLinesDialog(self.engine, t, self).exec()

    def verify(self):
        t = self._cur()
        if not t:
            return
        note, ok = QInputDialog.getMultiLineText(self, "Xác nhận kiểm chứng", f"Căn cứ đã đối chiếu cho mẫu {t['code']} v{t['version']} "
                                                 "(số hiệu văn bản, điều/phụ lục, ngày hiệu lực, nguồn chính thức):")
        if ok:
            ok, _ = run(self, self.engine.verify_template, t["id"], note)
            if ok:
                self.refresh()


class FinStatementView(QWidget):
    def __init__(self, ctx, kind: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s, self.kind = ctx, ctx.session, kind
        self.engine = ReportEngine(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        head = QHBoxLayout()
        head.addWidget(_page_title(KINDS[kind].upper()))
        head.addStretch(1)
        top = QHBoxLayout()
        self.cb = QComboBox()
        self.cb.setMinimumWidth(380)
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (self.cb, QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        bm = tool_button("Quản lý mẫu…", "settings")
        bm.clicked.connect(self.manage)
        top.addWidget(b)
        top.addWidget(bm)
        top.addStretch(1)
        self.table = ReportTable()
        head.addWidget(ExportBar(self.table, self.titles, self.s, self, False))
        root.addLayout(head)
        root.addLayout(top)
        self.banner = banner("")
        root.addWidget(self.banner)
        root.addWidget(self.table, 1)
        self.footer = _hint("Nhấp đúp một chỉ tiêu để xem sổ chi tiết tài khoản cấu thành → chứng từ gốc.")
        root.addWidget(self.footer)
        self.cb.activated.connect(lambda _: self.refresh())
        self.table.rowActivated.connect(self.drill)
        self.load_templates()
        self.refresh()

    def load_templates(self):
        self.tpls = [t for t in self.engine.templates(self.kind)]
        self.cb.clear()
        for t in self.tpls:
            self.cb.addItem(f"{t['name']} (v{t['version']})" + ("" if t["verified"] else " – CHƯA KIỂM CHỨNG"), t["id"])

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    @property
    def tpl(self):
        i = self.cb.currentIndex()
        return self.tpls[i] if 0 <= i < len(self.tpls) else None

    def titles(self):
        t = self.tpl
        name = KINDS[self.kind] + ("" if not t or t["verified"] else " (MẪU CHƯA KIỂM CHỨNG – KHÔNG DÙNG NỘP)")
        return name, f"Từ ngày {vn_date(self.d_from.iso())} đến ngày {vn_date(self.d_to.iso())}"

    def manage(self):
        TemplateManager(self.ctx, self).exec()
        self.load_templates()
        self.refresh()

    def refresh(self):
        t = self.tpl
        if not t:
            self.banner.setText("Chưa có mẫu cho loại báo cáo này. Bấm «Quản lý mẫu…» để nhập mẫu theo văn bản của chế độ kế toán áp dụng (file Excel: mã – chỉ tiêu – công thức).")
            self.table.fill(["Thông báo"], [["Chưa có mẫu báo cáo."]], stretch_col=0)
            return
        reg = self.s.regime_for(self.d_to.iso())
        if t["verified"]:
            self.banner.setText(f"Mẫu đã kiểm chứng bởi {t['verified_by']}: {t['verified_note']}")
            self.banner.setStyleSheet("background:#E8F6EC;border:1px solid #9FD4AF;border-radius:4px;padding:5px 8px;")
        else:
            self.banner.setText(UNVERIFIED_BANNER)
            self.banner.setStyleSheet("background:#FFF8E6;border:1px solid #F0D58C;border-radius:4px;padding:5px 8px;color:#8A3B00;font-weight:600;")
        ok, lines = run(self, self.engine.evaluate, t["id"], self.d_from.iso(), self.d_to.iso())
        if not ok:
            return
        bs = self.kind == "BS"
        heads = ["Mã", "Chỉ tiêu", "Kỳ này"] + (["Đầu năm"] if bs else []) + ["Tài khoản cấu thành"]
        data, keys, bold = [], [], set()
        for i, l in enumerate(lines):
            row = [l["code"], ("      " * l["indent"]) + l["label"], l["value"]] + ([l["open_value"]] if bs else []) + [", ".join(l["accounts"])]
            data.append(row)
            keys.append(tuple(l["accounts"]))
            if l["bold"]:
                bold.add(i)
        self.table.fill(heads, data, money_cols={2, 3} if bs else {2}, widths=[60, 460, 140] + ([140] if bs else []) + [230], keys=keys,
                        total_rows=bold, stretch_col=1)
        chk = next((l for l in lines if l["code"] == "K"), None)
        if chk and not chk["value"]:                       # dòng kiểm tra bằng 0: hiển thị rõ "0"
            r = next(i for i, l in enumerate(lines) if l["code"] == "K")
            for j in ((2, 3) if bs else (2,)):
                self.table.item(r, j).setText("0")
                self.table.item(r, j).setForeground(QColor("#1E7A34"))
        if chk and chk["value"]:
            self.footer.setText(f"<span style='color:#B42318;font-weight:600'>Dòng kiểm tra lệch {fmt_money(chk['value'])} – kiểm tra số liệu hoặc công thức mẫu.</span>")
        else:
            self.footer.setText("Nhấp đúp một chỉ tiêu để xem sổ chi tiết tài khoản cấu thành → chứng từ gốc. " + (f"Chế độ kế toán áp dụng: {reg['legal_ref']}." if reg else ""))

    def drill(self, accounts):
        accounts = list(accounts or [])
        if not accounts:
            return
        if len(accounts) == 1:
            self.ctx.open("r_sct", account=accounts[0], d_from=self.d_from.iso(), d_to=self.d_to.iso(), new_tab=True)
            return
        menu = QMenu(self)
        for a in accounts:
            menu.addAction(f"Sổ chi tiết TK {a} – {self.s.db.scalar('SELECT name FROM account WHERE company_id=? AND code=?', (self.s.company_id, a), '')}",
                           lambda acc=a: self.ctx.open("r_sct", account=acc, d_from=self.d_from.iso(), d_to=self.d_to.iso(), new_tab=True))
        from PySide6.QtGui import QCursor
        menu.exec(QCursor.pos())


# ======================================================================= THUẾ
class VatView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = TaxService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("THUẾ GTGT – BẢNG KÊ VÀ TỔNG HỢP"))
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        root.addLayout(top)
        root.addWidget(banner(TAX_BANNER))
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.t_in, self.t_out, self.t_sum = ReportTable(), ReportTable(), ReportTable()
        for t, name, title in ((self.t_in, "Hóa đơn mua vào", "Bảng kê hóa đơn, chứng từ hàng hóa dịch vụ mua vào"),
                               (self.t_out, "Hóa đơn bán ra", "Bảng kê hóa đơn, chứng từ hàng hóa dịch vụ bán ra"), (self.t_sum, "Tổng hợp & đối chiếu sổ", "Tổng hợp thuế GTGT")):
            w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0, 4, 0, 0)
            bar = QHBoxLayout(); bar.addStretch(1)
            bar.addWidget(ExportBar(t, lambda ti=title: (ti, f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())}"), self.s, self))
            l.addLayout(bar); l.addWidget(t, 1)
            self.tabs.addTab(w, name)
            t.rowActivated.connect(lambda vid: isinstance(vid, int) and self.ctx.open_voucher(vid))
        self.refresh()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def _inv(self, table, direction):
        rows = self.svc.vat_invoices(direction, self.d_from.iso(), self.d_to.iso())
        data = [[r["invoice_series"] or "", r["invoice_no"] or "", vn_date(r["invoice_date"]), r["tax_code"] or "", r["partner_name"] or "",
                 self.svc.rate_label(r["tax_rate"]), r["amount"], r["tax"], r["number"]] for r in rows]
        data.append(["", "", "", "", "TỔNG CỘNG", "", sum(r["amount"] for r in rows), sum(r["tax"] for r in rows), ""])
        table.fill(["Ký hiệu", "Số hóa đơn", "Ngày HĐ", "MST", "Tên đối tượng", "Thuế suất", "Giá trị chưa thuế", "Tiền thuế", "Chứng từ"], data,
                   money_cols={6, 7}, widths=[85, 90, 85, 100, 280, 100, 130, 110, 90], keys=[r["id"] for r in rows] + [None], total_rows={len(rows)},
                   center_cols={0, 2, 5, 8}, stretch_col=4)

    def refresh(self):
        self._inv(self.t_in, "BKMH")
        self._inv(self.t_out, "BKBH")
        sm = self.svc.vat_summary(self.d_from.iso(), self.d_to.iso())
        rows, tot = [], set()
        rows.append(["MUA VÀO", "", "", None]); tot.add(len(rows) - 1)
        for rate, amt, tax in sm["input_by_rate"]:
            rows.append([f"  Theo thuế suất: {rate}", amt, tax, None])
        rows.append(["  Cộng theo hóa đơn / chứng từ", sm["input_amount"], sm["input_inv"], None])
        rows.append(["  Phát sinh Nợ TK 1331 trên sổ", None, sm["input_ledger"], sm["input_inv"] - sm["input_ledger"]])
        rows.append(["BÁN RA", "", "", None]); tot.add(len(rows) - 1)
        for rate, amt, tax in sm["output_by_rate"]:
            rows.append([f"  Theo thuế suất: {rate}", amt, tax, None])
        rows.append(["  Cộng theo hóa đơn / chứng từ", sm["output_amount"], sm["output_inv"], None])
        rows.append(["  Phát sinh Có TK 33311 trên sổ", None, sm["output_ledger"], sm["output_inv"] - sm["output_ledger"]])
        rows.append(["TẠM TÍNH TRONG KỲ", "", "", None]); tot.add(len(rows) - 1)
        rows.append(["  Thuế GTGT đầu ra − đầu vào (theo hóa đơn)", None, sm["output_inv"] - sm["input_inv"], None])
        rows.append(["  Thuế GTGT được khấu trừ đầu năm (số dư Nợ TK 133)", None, sm["deductible_open_year"], None])
        self.t_sum.fill(["Chỉ tiêu", "Giá trị chưa thuế", "Tiền thuế", "Chênh lệch hóa đơn – sổ"], rows, money_cols={1, 2, 3},
                        widths=[420, 150, 150, 160], total_rows=tot, stretch_col=0)


class InvoiceReconView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = TaxService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("ĐỐI CHIẾU HÓA ĐƠN – SỔ KẾ TOÁN – DỮ LIỆU KÊ KHAI"))
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        self.table = ReportTable()
        top.addWidget(ExportBar(self.table, lambda: ("Đối chiếu hóa đơn – sổ kế toán", f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())}"), self.s, self))
        root.addLayout(top)
        root.addWidget(banner(TAX_BANNER))
        root.addWidget(self.table, 1)
        root.addWidget(_hint("Đối chiếu nội bộ giữa hóa đơn nhập trên chứng từ và bút toán thuế trên sổ; kiểm tra thiếu thông tin, trùng hóa đơn, lệch kỳ. "
                             "Chưa đối chiếu với dữ liệu hóa đơn trên hệ thống của cơ quan thuế hay dữ liệu tờ khai đã nộp."))
        self.table.rowActivated.connect(lambda vid: isinstance(vid, int) and self.ctx.open_voucher(vid))
        self.refresh()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        rows = self.svc.invoice_reconciliation(self.d_from.iso(), self.d_to.iso())
        lab = {"REVIEW": "Cần kiểm tra", "INFO": "Thông tin"}
        self.table.fill(["Mức độ", "Chứng từ", "Nội dung", "Trên chứng từ", "Trên sổ", "Chênh lệch"],
                        [[lab[r["severity"]], r["voucher"], r["issue"], r["invoice"], r["ledger"], r["diff"]] for r in rows],
                        money_cols={3, 4, 5}, widths=[100, 150, 600, 120, 120, 110], keys=[r["voucher_id"] for r in rows], stretch_col=2)
        for i, r in enumerate(rows):
            self.table.item(i, 0).setForeground(QColor("#9A6700" if r["severity"] == "REVIEW" else "#1F5FA8"))


class TndnView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = TaxService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("THUẾ TNDN – TẠM TÍNH HỖ TRỢ"))
        self.sp = QSpinBox()
        self.sp.setRange(2000, 2100)
        self.sp.setValue(self.s.year)
        self.d_to = DateEdit(self.s.date_to)
        for w in (QLabel("Năm"), self.sp, QLabel("Tính đến ngày"), self.d_to):
            top.addWidget(w)
        b = tool_button("Tính", "calc", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        self.table = ReportTable()
        top.addWidget(ExportBar(self.table, lambda: ("Tạm tính thuế thu nhập doanh nghiệp (hỗ trợ tính toán)", f"Năm {self.sp.value()} – đến ngày {vn_date(self.d_to.iso())}"), self.s, self, False))
        root.addLayout(top)
        root.addWidget(banner(TAX_BANNER))
        root.addWidget(self.table, 2)
        root.addWidget(SectionHeader("Tham số: thuế suất (người dùng nhập kèm căn cứ)"))
        row = QHBoxLayout()
        self.rate, self.note = QLineEdit(), QLineEdit()
        self.rate.setMaximumWidth(80)
        self.rate.setPlaceholderText("%")
        self.note.setPlaceholderText("Căn cứ: văn bản, điều khoản, đối tượng áp dụng…")
        bs = tool_button("Lưu thuế suất", "save")
        bs.clicked.connect(self.save_param)
        bs.setEnabled(self.s.user.can("admin"))
        for w in (QLabel("Thuế suất TNDN (%)"), self.rate, QLabel("Căn cứ"), self.note, bs):
            row.addWidget(w)
        row.itemAt(3).widget().setMinimumWidth(380)
        root.addLayout(row)
        root.addWidget(SectionHeader("Điều chỉnh tăng / giảm thu nhập chịu thuế (người dùng nhập)"))
        self.adj = QTableWidget(0, 4)
        self.adj.setHorizontalHeaderLabels(["Loại (Tăng / Giảm)", "Nội dung điều chỉnh", "Số tiền", "Ghi chú, căn cứ"])
        for j, w in enumerate((130, 420, 140, 400)):
            self.adj.setColumnWidth(j, w)
        self.adj.verticalHeader().setVisible(False)
        root.addWidget(self.adj, 1)
        bar = QHBoxLayout()
        for text, ic, fn in (("Thêm dòng", "add", self.add_adj), ("Xóa dòng", "delete", self.del_adj), ("Lưu điều chỉnh", "save", self.save_adj)):
            bt = tool_button(text, ic, "primary" if "Lưu" in text else None)
            bt.clicked.connect(fn)
            bt.setEnabled(self.s.user.can("edit"))
            bar.addWidget(bt)
        bar.addStretch(1)
        root.addLayout(bar)
        self.sp.valueChanged.connect(lambda _: self.load())
        self.load()

    def apply_period(self, d_from, d_to):
        self.d_to.set_iso(d_to)

    def load(self):
        y = self.sp.value()
        v, n = self.svc.get_param(y, "tndn_rate")
        self.rate.setText(v or "")
        self.note.setText(n or "")
        self.adj.setRowCount(0)
        for a in self.svc.adjustments(y):
            self._add_row("Tăng" if a["kind"] == "INC" else "Giảm", a["label"], fmt_money(a["amount"]), a["note"] or "")
        self.refresh()

    def _add_row(self, kind="Tăng", label="", amount="", note=""):
        i = self.adj.rowCount()
        self.adj.insertRow(i)
        for j, v in enumerate((kind, label, amount, note)):
            it = QTableWidgetItem(v)
            if j == 2:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.adj.setItem(i, j, it)

    def add_adj(self):
        self._add_row()

    def del_adj(self):
        if self.adj.currentRow() >= 0:
            self.adj.removeRow(self.adj.currentRow())

    def save_adj(self):
        rows = []
        for i in range(self.adj.rowCount()):
            g = lambda j: self.adj.item(i, j).text() if self.adj.item(i, j) else ""
            rows.append({"kind": {"tăng": "INC", "giảm": "DEC"}.get(g(0).strip().lower(), ""), "label": g(1), "amount": g(2), "note": g(3)})
        ok, _ = run(self, self.svc.save_adjustments, self.sp.value(), rows)
        if ok:
            info(self, "Đã lưu điều chỉnh.")
            self.refresh()

    def save_param(self):
        ok, _ = run(self, self.svc.set_param, self.sp.value(), "tndn_rate", self.rate.text(), self.note.text())
        if ok:
            info(self, "Đã lưu thuế suất.")
            self.refresh()

    def refresh(self):
        r = self.svc.corporate_income(self.sp.value(), self.d_to.iso())
        rows = [["1", "Doanh thu và thu nhập (TK 511, 515, 711) – loại trừ kết chuyển", r["revenue"]],
                ["2", "Chi phí (TK 632, 635, 642, 811) – loại trừ kết chuyển", r["expense"]],
                ["3", "Lợi nhuận kế toán trước thuế (1 − 2)", r["profit"]],
                ["4", "Điều chỉnh tăng (người dùng nhập)", r["increase"]],
                ["5", "Điều chỉnh giảm (người dùng nhập)", r["decrease"]],
                ["6", "Thu nhập tính thuế tạm tính (3 + 4 − 5)", r["taxable"]],
                ["7", "Thuế suất (%) – người dùng nhập", r["rate"] or "CHƯA NHẬP"],
                ["8", "Thuế TNDN tạm tính (nếu thu nhập tính thuế > 0)", r["tax"] if r["tax"] is not None else "Chưa tính được – nhập thuế suất"],
                ["9", "Chi phí thuế TNDN đã hạch toán trên sổ (TK 821)", r["booked"]]]
        self.table.fill(["STT", "Chỉ tiêu", "Số tiền"], rows, money_cols={2}, widths=[50, 560, 240], total_rows={2, 5, 7}, stretch_col=1)


class TncnView(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.ctx, self.s = ctx, ctx.session
        self.svc = TaxService(self.s)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        top = QHBoxLayout()
        top.addWidget(_page_title("THUẾ TNCN – TỔNG HỢP THEO NHÂN VIÊN"))
        self.d_from, self.d_to = DateEdit(self.s.date_from), DateEdit(self.s.date_to)
        for w in (QLabel("Từ"), self.d_from, QLabel("đến"), self.d_to):
            top.addWidget(w)
        b = tool_button("Xem", "search", "primary")
        b.clicked.connect(self.refresh)
        top.addWidget(b)
        top.addStretch(1)
        self.table = ReportTable()
        top.addWidget(ExportBar(self.table, lambda: ("Tổng hợp thu nhập và thuế TNCN đã khấu trừ theo nhân viên (hỗ trợ)",
                                                     f"Từ {vn_date(self.d_from.iso())} đến {vn_date(self.d_to.iso())}"), self.s, self))
        root.addLayout(top)
        root.addWidget(banner(TAX_BANNER + " Phần TNCN CHỈ tổng hợp số liệu đã hạch toán (Có TK 334, Nợ TK 334, Có TK 3335 theo nhân viên); chưa tính thuế theo biểu thuế, "
                              "giảm trừ gia cảnh, quyết toán."))
        root.addWidget(self.table, 1)
        self.refresh()

    def apply_period(self, d_from, d_to):
        self.d_from.set_iso(d_from)
        self.d_to.set_iso(d_to)

    def refresh(self):
        rows = self.svc.personal_income(self.d_from.iso(), self.d_to.iso())
        data = [[r["code"], r["name"], r["tax_code"] or "", r["accrued"], r["paid"], r["withheld"]] for r in rows]
        data.append(["", "TỔNG CỘNG", "", sum(r["accrued"] for r in rows), sum(r["paid"] for r in rows), sum(r["withheld"] for r in rows)])
        self.table.fill(["Mã NV", "Họ tên", "MST cá nhân", "Phải trả người lao động (Có TK 334)", "Đã chi trả / khấu trừ (Nợ TK 334)", "Thuế đã khấu trừ (Có TK 3335)"],
                        data, money_cols={3, 4, 5}, widths=[80, 260, 120, 210, 210, 200], total_rows={len(rows)}, stretch_col=1)

