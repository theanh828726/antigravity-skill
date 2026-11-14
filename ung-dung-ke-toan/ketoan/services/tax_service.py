"""Báo cáo HỖ TRỢ TÍNH TOÁN về thuế (GTGT, TNDN, TNCN) và đối chiếu hóa đơn – sổ kế toán.

PHẠM VI VÀ GIỚI HẠN (quan trọng):
  • Đây là báo cáo hỗ trợ tính toán từ số liệu đã ghi sổ; KHÔNG phải tờ khai điện tử đã đáp ứng cấu trúc, chỉ tiêu, mẫu biểu
    của cơ quan thuế và KHÔNG thay thế phần mềm/kênh nộp tờ khai chính thức.
  • Ứng dụng KHÔNG tự suy đoán thuế suất, điều kiện khấu trừ, khoản điều chỉnh hay biểu thuế: thuế suất lấy theo giá trị người
    dùng chọn trên từng dòng chứng từ; thuế suất TNDN và các khoản điều chỉnh do người dùng nhập kèm ghi chú căn cứ.
  • TNCN: chỉ tổng hợp số liệu thu nhập và thuế đã khấu trừ do kế toán hạch toán theo nhân viên; chưa tính thuế theo biểu thuế,
    giảm trừ gia cảnh hay quyết toán.
"""
from __future__ import annotations

from collections import defaultdict

from ketoan.domain.money import round_money, to_decimal
from ketoan.services.context import BusinessError, Session

INPUT_TAX_ACCOUNT, OUTPUT_TAX_ACCOUNT = "1331", "33311"
REV_PREFIXES = ("511", "515", "711")
EXP_PREFIXES = ("632", "635", "642", "811")        # không gồm 821 (chi phí thuế TNDN)
EMP_TAX_ACCOUNT, EMP_PAY_ACCOUNT = "3335", "334"


class TaxService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    # ------------------------------------------------------------ GTGT
    def vat_invoices(self, direction: str, d_from: str, d_to: str) -> list[dict]:
        """direction: BKMH (mua vào) | BKBH (bán ra). Mỗi dòng = (chứng từ, thuế suất)."""
        rows = self.db.query("""
            SELECT v.id, v.number, v.posting_date, v.invoice_series, v.invoice_no, v.invoice_date, v.tax_code,
                   COALESCE(p.name, v.partner_name) AS partner_name, p.code AS partner_code, l.tax_rate,
                   SUM(l.amount) AS amount, SUM(l.tax_amount) AS tax
            FROM voucher v JOIN voucher_line l ON l.voucher_id=v.id LEFT JOIN partner p ON p.id=v.partner_id
            WHERE v.company_id=? AND v.vtype=? AND v.status='POSTED' AND v.posting_date BETWEEN ? AND ?
            GROUP BY v.id, l.tax_rate ORDER BY v.posting_date, v.number""", (self.s.company_id, direction, d_from, d_to))
        return [dict(r) for r in rows]

    @staticmethod
    def rate_label(rate) -> str:
        return "Không có thuế suất" if rate in (None, "") else f"{to_decimal(rate).normalize():f}%"

    def vat_summary(self, d_from: str, d_to: str) -> dict:
        def by_rate(rows):
            agg: dict[str, list] = defaultdict(lambda: [0, 0])
            for r in rows:
                k = self.rate_label(r["tax_rate"])
                agg[k][0] += r["amount"]
                agg[k][1] += r["tax"]
            return sorted(((k, v[0], v[1]) for k, v in agg.items()))
        inp, out = self.vat_invoices("BKMH", d_from, d_to), self.vat_invoices("BKBH", d_from, d_to)
        c = self.s.company_id
        led_in = self.db.scalar("""SELECT COALESCE(SUM(debit),0) FROM ledger_entry WHERE company_id=? AND account_code LIKE ?
                                   AND posting_date BETWEEN ? AND ?""", (c, INPUT_TAX_ACCOUNT + "%", d_from, d_to), 0)
        led_out = self.db.scalar("""SELECT COALESCE(SUM(credit),0) FROM ledger_entry WHERE company_id=? AND account_code LIKE ?
                                    AND posting_date BETWEEN ? AND ?""", (c, OUTPUT_TAX_ACCOUNT + "%", d_from, d_to), 0)
        ob = self.db.scalar("""SELECT COALESCE(SUM(debit-credit),0) FROM opening_balance WHERE company_id=? AND year=? AND account_code LIKE '133%'""",
                            (c, int(d_from[:4])), 0)
        return {"input_by_rate": by_rate(inp), "output_by_rate": by_rate(out),
                "input_inv": sum(r["tax"] for r in inp), "output_inv": sum(r["tax"] for r in out),
                "input_amount": sum(r["amount"] for r in inp), "output_amount": sum(r["amount"] for r in out),
                "input_ledger": led_in, "output_ledger": led_out, "deductible_open_year": ob}

    def invoice_reconciliation(self, d_from: str, d_to: str) -> list[dict]:
        """Đối chiếu hóa đơn – sổ kế toán: [{severity, voucher_id, voucher, issue, invoice, ledger, diff}]."""
        out, c = [], self.s.company_id
        vouchers = self.db.query("""SELECT v.* FROM voucher v WHERE v.company_id=? AND v.vtype IN ('BKMH','BKBH') AND v.status='POSTED'
                                    AND v.posting_date BETWEEN ? AND ? ORDER BY v.posting_date, v.number""", (c, d_from, d_to))
        seen: dict[tuple, str] = {}
        for v in vouchers:
            side = "debit" if v["vtype"] == "BKMH" else "credit"
            ledger_tax = self.db.scalar(f"SELECT COALESCE(SUM({side}),0) FROM ledger_entry WHERE voucher_id=? AND is_tax=1 AND "
                                        f"account_code LIKE ?", (v["id"], (INPUT_TAX_ACCOUNT if v["vtype"] == "BKMH" else OUTPUT_TAX_ACCOUNT) + "%"), 0)
            lbl = f"{v['number']} ({v['posting_date']})"
            if ledger_tax != v["total_tax"]:
                out.append({"severity": "REVIEW", "voucher_id": v["id"], "voucher": lbl, "issue": "Tiền thuế trên chứng từ khác bút toán thuế trên sổ",
                            "invoice": v["total_tax"], "ledger": ledger_tax, "diff": v["total_tax"] - ledger_tax})
            if v["total_tax"]:
                missing = [n for n, val in (("ký hiệu", v["invoice_series"]), ("số hóa đơn", v["invoice_no"]),
                                            ("ngày hóa đơn", v["invoice_date"]), ("mã số thuế đối tượng", v["tax_code"])) if not val]
                if missing:
                    out.append({"severity": "REVIEW", "voucher_id": v["id"], "voucher": lbl,
                                "issue": "Có thuế GTGT nhưng thiếu " + ", ".join(missing), "invoice": v["total_tax"], "ledger": ledger_tax, "diff": 0})
            if v["invoice_no"]:
                key = (v["vtype"], v["invoice_series"] or "", v["invoice_no"], v["tax_code"] or "")
                if key in seen:
                    out.append({"severity": "REVIEW", "voucher_id": v["id"], "voucher": lbl,
                                "issue": f"Trùng hóa đơn {key[1]} số {key[2]} với chứng từ {seen[key]}", "invoice": v["total_tax"],
                                "ledger": ledger_tax, "diff": 0})
                seen[key] = v["number"]
            if v["invoice_date"] and v["invoice_date"][:7] != v["posting_date"][:7]:
                out.append({"severity": "INFO", "voucher_id": v["id"], "voucher": lbl,
                            "issue": f"Ngày hóa đơn {v['invoice_date']} khác kỳ hạch toán {v['posting_date'][:7]} – kiểm tra kỳ kê khai",
                            "invoice": v["total_tax"], "ledger": ledger_tax, "diff": 0})
        # bút toán thuế ghi thẳng vào TK thuế không qua hóa đơn mua/bán
        for r in self.db.query("""SELECT e.voucher_id, v.number, v.posting_date, e.account_code, e.debit, e.credit FROM ledger_entry e
                                  JOIN voucher v ON v.id=e.voucher_id WHERE e.company_id=? AND e.is_tax=0 AND v.vtype NOT IN ('BKMH','BKBH')
                                  AND (e.account_code LIKE ? OR e.account_code LIKE ?) AND e.posting_date BETWEEN ? AND ?""",
                               (c, INPUT_TAX_ACCOUNT + "%", OUTPUT_TAX_ACCOUNT + "%", d_from, d_to)):
            out.append({"severity": "INFO", "voucher_id": r["voucher_id"], "voucher": f"{r['number']} ({r['posting_date']})",
                        "issue": f"Hạch toán trực tiếp TK {r['account_code']} không qua bảng kê hóa đơn (nộp thuế, khấu trừ, điều chỉnh…)",
                        "invoice": 0, "ledger": r["debit"] - r["credit"], "diff": 0})
        return out

    # ------------------------------------------------------------ TNDN
    def get_param(self, year: int, key: str):
        r = self.db.one("SELECT * FROM tax_param WHERE company_id=? AND year=? AND key=?", (self.s.company_id, year, key))
        return (r["value"], r["source_note"]) if r else (None, None)

    def set_param(self, year: int, key: str, value: str, note: str):
        self.s.require("admin", "cấu hình tham số thuế")
        if key == "tndn_rate":
            try:
                v = to_decimal(value)
            except ValueError:
                raise BusinessError("Thuế suất không hợp lệ.") from None
            if not 0 <= v <= 100:
                raise BusinessError("Thuế suất phải từ 0 đến 100%.")
            value = format(v.normalize(), "f")
        if not (note or "").strip():
            raise BusinessError("Cần ghi căn cứ (văn bản, điều khoản, đối tượng áp dụng) cho tham số thuế.")
        with self.db.transaction():
            self.db.execute("""INSERT INTO tax_param(company_id, year, key, value, source_note) VALUES(?,?,?,?,?)
                               ON CONFLICT(company_id, year, key) DO UPDATE SET value=excluded.value, source_note=excluded.source_note""",
                            (self.s.company_id, year, key, value, note.strip()))
            self.s.audit("Cập nhật tham số thuế", "tax_param", f"{key}/{year}", {"gia_tri": value, "can_cu": note.strip()})

    def adjustments(self, year: int):
        return self.db.query("SELECT * FROM tax_adjustment WHERE company_id=? AND year=? ORDER BY kind, id", (self.s.company_id, year))

    def save_adjustments(self, year: int, rows: list[dict]):
        self.s.require("edit", "nhập điều chỉnh thuế TNDN")
        clean = []
        for i, r in enumerate(rows, 1):
            label = (r.get("label") or "").strip()
            if not label and not r.get("amount"):
                continue
            if r.get("kind") not in ("INC", "DEC"):
                raise BusinessError(f"Dòng {i}: loại điều chỉnh phải là Tăng hoặc Giảm.")
            try:
                amt = round_money(r.get("amount"))
            except ValueError as e:
                raise BusinessError(f"Dòng {i}: {e}") from None
            if not label or amt < 0:
                raise BusinessError(f"Dòng {i}: cần nội dung và số tiền không âm.")
            clean.append((r["kind"], label, amt, (r.get("note") or "").strip()))
        with self.db.transaction():
            self.db.execute("DELETE FROM tax_adjustment WHERE company_id=? AND year=?", (self.s.company_id, year))
            self.db.executemany("INSERT INTO tax_adjustment(company_id, year, kind, label, amount, note) VALUES(?,?,?,?,?,?)",
                                [(self.s.company_id, year, *x) for x in clean])
            self.s.audit("Cập nhật điều chỉnh TNDN", "tax_adjustment", year, {"so_dong": len(clean)})

    def corporate_income(self, year: int, d_to: str) -> dict:
        """Tạm tính từ đầu năm đến d_to. Doanh thu/chi phí loại trừ bút toán kết chuyển (đối ứng 911)."""
        c, start = self.s.company_id, f"{year}-01-01"
        rev = exp = 0
        for r in self.db.query("""SELECT account_code a, SUM(credit-debit) n FROM ledger_entry WHERE company_id=? AND posting_date BETWEEN ? AND ?
                                  AND COALESCE(contra_account,'')<>'911' GROUP BY a""", (c, start, d_to)):
            if r["a"].startswith(REV_PREFIXES):
                rev += r["n"]
            elif r["a"].startswith(EXP_PREFIXES):
                exp -= r["n"]
        profit = rev - exp
        adj = self.adjustments(year)
        inc = sum(a["amount"] for a in adj if a["kind"] == "INC")
        dec = sum(a["amount"] for a in adj if a["kind"] == "DEC")
        taxable = profit + inc - dec
        rate, note = self.get_param(year, "tndn_rate")
        tax = None
        if rate is not None:
            tax = round_money(max(taxable, 0) * to_decimal(rate) / 100)
        booked = self.db.scalar("""SELECT COALESCE(SUM(debit-credit),0) FROM ledger_entry WHERE company_id=? AND account_code LIKE '821%'
                                   AND COALESCE(contra_account,'')<>'911' AND posting_date BETWEEN ? AND ?""", (c, start, d_to), 0)
        return {"revenue": rev, "expense": exp, "profit": profit, "increase": inc, "decrease": dec, "taxable": taxable,
                "rate": rate, "rate_note": note, "tax": tax, "booked": booked}

    # ------------------------------------------------------------ TNCN
    def personal_income(self, d_from: str, d_to: str) -> list[dict]:
        c = self.s.company_id
        rows = self.db.query("""
            SELECT p.id, p.code, p.name, p.tax_code,
                   COALESCE(SUM(CASE WHEN e.account_code LIKE ? THEN e.credit END),0) AS accrued,
                   COALESCE(SUM(CASE WHEN e.account_code LIKE ? THEN e.debit END),0) AS paid,
                   COALESCE(SUM(CASE WHEN e.account_code LIKE ? THEN e.credit - e.debit END),0) AS withheld
            FROM ledger_entry e JOIN partner p ON p.id=e.partner_id
            WHERE e.company_id=? AND p.kind='NV' AND e.posting_date BETWEEN ? AND ?
              AND (e.account_code LIKE ? OR e.account_code LIKE ?) GROUP BY p.id ORDER BY p.code""",
                             (EMP_PAY_ACCOUNT + "%", EMP_PAY_ACCOUNT + "%", EMP_TAX_ACCOUNT + "%", c, d_from, d_to,
                              EMP_PAY_ACCOUNT + "%", EMP_TAX_ACCOUNT + "%"))
        return [dict(r) for r in rows]
