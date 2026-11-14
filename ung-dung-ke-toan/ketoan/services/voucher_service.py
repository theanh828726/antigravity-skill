"""Nghiệp vụ chứng từ: lưu, kiểm tra, ghi sổ, bỏ ghi sổ, xóa.

Vòng đời:  Nháp ──Kiểm tra──▶ Đã kiểm tra ──Ghi sổ──▶ Đã ghi sổ ──(khóa kỳ)──▶ Đã khóa kỳ
           ▲   (sửa đưa về Nháp)          ◀──Bỏ ghi sổ──┘
Mọi thao tác ghi dữ liệu nằm trong một giao dịch CSDL (lưu đủ hoặc hoàn tác đủ).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ketoan.domain.constants import (CHECKED, DRAFT, INVENTORY_PREFIXES, LOCKED, POSTED, SEV_BLOCK, SEV_INFO,
                                     SEV_REVIEW, VOUCHER_TYPES)
from ketoan.domain.money import dec_to_str, line_amount, round_money, tax_amount, to_decimal
from ketoan.services.context import BusinessError, Session
from ketoan.services.period_service import PeriodService


@dataclass
class Issue:
    severity: str
    rule: str
    message: str
    difference: int = 0
    voucher_id: int | None = None
    line_no: int | None = None
    voucher_label: str = ""


class ValidationFailed(BusinessError):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        blocks = [i for i in issues if i.severity == SEV_BLOCK]
        super().__init__("Chứng từ có lỗi chặn ghi sổ:\n" + "\n".join(f"• {i.message}" for i in blocks))


LINE_FIELDS = ["description", "debit_account", "credit_account", "debit_partner_id", "credit_partner_id", "item_id",
               "warehouse_id", "unit", "quantity", "unit_price", "amount", "tax_rate", "tax_amount", "project_id",
               "department_id", "expense_item_id"]
HEADER_FIELDS = ["vtype", "number", "voucher_date", "posting_date", "partner_id", "partner_name", "tax_code",
                 "description", "invoice_no", "invoice_series", "invoice_date", "due_date", "source_voucher_id"]
DEBT_VTYPES = ("BKMH", "BKBH", "PKMB")      # chứng từ phát sinh công nợ theo hóa đơn, có hạn thanh toán


class VoucherService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db
        self.periods = PeriodService(session)

    # ================================================================ đọc
    def next_number(self, vtype: str) -> str:
        prefix = VOUCHER_TYPES[vtype].prefix
        rows = self.db.query("SELECT number FROM voucher WHERE company_id=? AND vtype=?", (self.s.company_id, vtype))
        mx = 0
        for r in rows:
            tail = r["number"][len(prefix):] if r["number"].startswith(prefix) else ""
            if tail.isdigit():
                mx = max(mx, int(tail))
        return f"{prefix}{mx + 1:05d}"

    def get(self, voucher_id: int) -> dict:
        v = self.db.one("SELECT * FROM voucher WHERE id=? AND company_id=?", (voucher_id, self.s.company_id))
        if not v:
            raise BusinessError("Không tìm thấy chứng từ (có thể đã bị xóa).")
        lines = self.db.query("""
            SELECT l.*, dp.code AS debit_partner, cp.code AS credit_partner, i.code AS item, w.code AS warehouse,
                   p.code AS project, d.code AS department, e.code AS expense_item
            FROM voucher_line l
            LEFT JOIN partner dp ON dp.id=l.debit_partner_id LEFT JOIN partner cp ON cp.id=l.credit_partner_id
            LEFT JOIN item i ON i.id=l.item_id LEFT JOIN warehouse w ON w.id=l.warehouse_id
            LEFT JOIN project p ON p.id=l.project_id LEFT JOIN department d ON d.id=l.department_id
            LEFT JOIN expense_item e ON e.id=l.expense_item_id
            WHERE l.voucher_id=? ORDER BY l.line_no""", (voucher_id,))
        out = dict(v)
        out["partner_code"] = self.db.scalar("SELECT code FROM partner WHERE id=?", (v["partner_id"],)) if v["partner_id"] else ""
        out["lines"] = [dict(r) for r in lines]
        out["display_status"] = self.display_status(v)
        return out

    def display_status(self, v) -> str:
        if self.periods.is_locked(v["posting_date"]):
            return LOCKED
        return v["status"]

    def list(self, vtype: str | None = None, d_from: str | None = None, d_to: str | None = None,
             status: str | None = None, search: str = ""):
        where, params = ["v.company_id=?"], [self.s.company_id]
        if vtype:
            where.append("v.vtype=?"); params.append(vtype)
        if d_from:
            where.append("v.posting_date>=?"); params.append(d_from)
        if d_to:
            where.append("v.posting_date<=?"); params.append(d_to)
        if status and status != LOCKED:
            where.append("v.status=?"); params.append(status)
        if search:
            where.append("(v.number LIKE ? OR v.description LIKE ? OR v.invoice_no LIKE ? OR p.name LIKE ? OR v.partner_name LIKE ?)")
            params += [f"%{search}%"] * 5
        rows = self.db.query(f"""
            SELECT v.*, COALESCE(p.name, v.partner_name) AS partner_display, p.code AS partner_code
            FROM voucher v LEFT JOIN partner p ON p.id=v.partner_id
            WHERE {' AND '.join(where)} ORDER BY v.posting_date, v.vtype, v.number""", params)
        locked_cache: dict[str, bool] = {}
        result = []
        for r in rows:
            ym = r["posting_date"][:7]
            if ym not in locked_cache:
                locked_cache[ym] = self.periods.is_locked(r["posting_date"])
            d = dict(r)
            d["display_status"] = LOCKED if locked_cache[ym] else r["status"]
            if status == LOCKED and d["display_status"] != LOCKED:
                continue
            result.append(d)
        return result

    # ================================================================ chuẩn hóa
    def _resolve(self, table: str, code_or_id):
        if code_or_id in (None, ""):
            return None
        if isinstance(code_or_id, int):
            return code_or_id
        rid = self.db.scalar(f"SELECT id FROM {table} WHERE company_id=? AND code=?", (self.s.company_id, str(code_or_id).strip()))
        if rid is None:
            raise BusinessError(f"Mã '{code_or_id}' không có trong danh mục ({table}).")
        return rid

    def normalize_lines(self, vtype: str, lines: list[dict]) -> list[dict]:
        """Chuẩn hóa dòng: tra mã danh mục, tính Thành tiền / Tiền thuế theo chính sách làm tròn."""
        vt = VOUCHER_TYPES[vtype]
        out = []
        for raw in lines:
            ln = {k: raw.get(k) for k in LINE_FIELDS}
            for key, table in (("debit_partner", "partner"), ("credit_partner", "partner"), ("item", "item"),
                               ("warehouse", "warehouse"), ("project", "project"), ("department", "department"),
                               ("expense_item", "expense_item")):
                if key in raw:
                    ln[f"{key}_id"] = self._resolve(table, raw.get(key))
            ln["debit_account"] = (raw.get("debit_account") or "").strip() or None
            ln["credit_account"] = (raw.get("credit_account") or "").strip() or None
            qty, price = to_decimal(raw.get("quantity")), to_decimal(raw.get("unit_price"))
            ln["quantity"], ln["unit_price"] = dec_to_str(qty), dec_to_str(price)
            if qty and price and "quantity" in vt.columns:
                ln["amount"] = line_amount(qty, price)
            else:
                ln["amount"] = round_money(raw.get("amount"))
            rate = raw.get("tax_rate")
            ln["tax_rate"] = dec_to_str(rate) if rate not in (None, "") else None
            if vt.tax_account and ln["tax_rate"] is not None and raw.get("tax_amount") in (None, ""):
                ln["tax_amount"] = tax_amount(ln["amount"], ln["tax_rate"])
            else:
                ln["tax_amount"] = round_money(raw.get("tax_amount")) if vt.tax_account else 0
            if ln["item_id"] and not raw.get("unit"):
                ln["unit"] = self.db.scalar("SELECT unit FROM item WHERE id=?", (ln["item_id"],))
            else:
                ln["unit"] = raw.get("unit") or None
            if not any([ln["debit_account"], ln["credit_account"], ln["amount"], ln["description"], ln["item_id"]]):
                continue        # bỏ dòng trống
            out.append(ln)
        return out

    @staticmethod
    def totals(vtype: str, lines: list[dict]) -> dict:
        vt = VOUCHER_TYPES[vtype]
        amount = sum(int(l.get("amount") or 0) for l in lines)
        tax = sum(int(l.get("tax_amount") or 0) for l in lines) if vt.tax_account else 0
        debit = credit = 0
        for l in lines:
            a, t = int(l.get("amount") or 0), int(l.get("tax_amount") or 0) if vt.tax_account else 0
            if l.get("debit_account"):
                debit += a
            if l.get("credit_account"):
                credit += a
            if t:
                # bút toán thuế luôn có hai vế: TK thuế và TK đối ứng của dòng
                if vt.tax_side == "D":
                    debit += t
                    credit += t if l.get("credit_account") else 0
                else:
                    credit += t
                    debit += t if l.get("debit_account") else 0
        return {"amount": amount, "tax": tax, "payment": amount + tax, "debit": debit, "credit": credit,
                "difference": debit - credit}

    # ================================================================ lưu
    def save(self, header: dict, lines: list[dict], voucher_id: int | None = None) -> int:
        vtype = header["vtype"]
        if vtype not in VOUCHER_TYPES:
            raise BusinessError("Loại chứng từ không hợp lệ.")
        self.s.require("edit" if voucher_id else "add", "lưu chứng từ")
        for k in ("voucher_date", "posting_date"):
            try:
                date.fromisoformat(str(header.get(k) or ""))
            except ValueError:
                raise BusinessError("Ngày chứng từ / ngày hạch toán không hợp lệ.") from None
        if self.periods.is_locked(header["posting_date"]):
            raise BusinessError(f"Ngày hạch toán {header['posting_date']} thuộc kỳ đã khóa – không thể lưu.")
        if voucher_id:
            old = self.db.one("SELECT * FROM voucher WHERE id=? AND company_id=?", (voucher_id, self.s.company_id))
            if not old:
                raise BusinessError("Chứng từ không còn tồn tại.")
            if old["status"] == POSTED:
                raise BusinessError("Chứng từ đã ghi sổ. Hãy «Bỏ ghi sổ» trước khi sửa.")
            if self.periods.is_locked(old["posting_date"]):
                raise BusinessError("Chứng từ thuộc kỳ đã khóa – không thể sửa.")
        number = (header.get("number") or "").strip() or self.next_number(vtype)
        dup = self.db.scalar("SELECT id FROM voucher WHERE company_id=? AND vtype=? AND number=? AND id<>?",
                             (self.s.company_id, vtype, number, voucher_id or 0))
        if dup:
            raise BusinessError(f"Số chứng từ {number} đã tồn tại.")
        norm = self.normalize_lines(vtype, lines)
        if not norm:
            raise BusinessError("Chứng từ chưa có dòng hạch toán.")
        tot = self.totals(vtype, norm)
        partner_id = self._resolve("partner", header.get("partner_code") or header.get("partner_id"))
        now, user = datetime.now().isoformat(timespec="seconds"), self.s.user.username
        h = {k: (header.get(k) or None) for k in HEADER_FIELDS}
        h.update(number=number, partner_id=partner_id, vtype=vtype)
        if vtype in DEBT_VTYPES and not h["due_date"] and partner_id:
            h["due_date"] = self.default_due_date(partner_id, h["invoice_date"] or h["voucher_date"])
        with self.db.transaction():
            if voucher_id:
                self.db.execute(f"""UPDATE voucher SET {', '.join(k + '=?' for k in HEADER_FIELDS)}, status=?,
                    total_amount=?, total_tax=?, total_payment=?, updated_by=?, updated_at=?, checked_by=NULL,
                    checked_at=NULL WHERE id=?""",
                                [h[k] for k in HEADER_FIELDS] + [DRAFT, tot["amount"], tot["tax"], tot["payment"], user, now,
                                                                 voucher_id])
                self.db.execute("DELETE FROM voucher_line WHERE voucher_id=?", (voucher_id,))
                action = "Sửa chứng từ"
            else:
                cur = self.db.execute(f"""INSERT INTO voucher(company_id, {', '.join(HEADER_FIELDS)}, status, total_amount,
                    total_tax, total_payment, created_by, created_at, updated_by, updated_at)
                    VALUES(?, {', '.join('?' * len(HEADER_FIELDS))}, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                      [self.s.company_id] + [h[k] for k in HEADER_FIELDS] +
                                      [DRAFT, tot["amount"], tot["tax"], tot["payment"], user, now, user, now])
                voucher_id = cur.lastrowid
                action = "Thêm chứng từ"
            for i, ln in enumerate(norm, 1):
                self.db.execute(f"INSERT INTO voucher_line(voucher_id, line_no, {', '.join(LINE_FIELDS)}) "
                                f"VALUES(?, ?, {', '.join('?' * len(LINE_FIELDS))})",
                                [voucher_id, i] + [ln[k] for k in LINE_FIELDS])
            self.s.audit(action, "voucher", f"{vtype}/{number}",
                         {"ngay_hach_toan": h["posting_date"], "tong_thanh_toan": tot["payment"], "so_dong": len(norm)})
        return voucher_id

    # ================================================================ kiểm tra
    def validate(self, voucher_id: int) -> list[Issue]:
        v = self.get(voucher_id)
        return self.validate_data(v, v["lines"], voucher_id)

    def validate_data(self, header: dict, lines: list[dict], voucher_id: int | None = None) -> list[Issue]:
        vt = VOUCHER_TYPES[header["vtype"]]
        label = f"{header.get('number') or '(mới)'}"
        issues: list[Issue] = []

        def add(sev, rule, msg, diff=0, line_no=None):
            issues.append(Issue(sev, rule, msg, diff, voucher_id, line_no, label))

        accounts = {r["code"]: r for r in self.db.query(
            "SELECT code, name, is_detail, require_partner, active FROM account WHERE company_id=?", (self.s.company_id,))}
        pd = str(header.get("posting_date") or "")
        if not pd:
            add(SEV_BLOCK, "thieu_ngay", "Thiếu ngày hạch toán")
        else:
            if not self.periods.fiscal_year_of(pd):
                add(SEV_BLOCK, "ngoai_nam", f"Ngày hạch toán {pd} không thuộc năm tài chính nào đã khai báo")
            if self.periods.is_locked(pd) and header.get("status") != POSTED:
                add(SEV_BLOCK, "ky_khoa", f"Chứng từ chưa ghi sổ nhưng thuộc kỳ đã khóa ({pd[5:7]}/{pd[:4]})")
            vd = str(header.get("voucher_date") or "")
            if vd and vd > pd:
                add(SEV_INFO, "ngay_ct", f"Ngày chứng từ {vd} sau ngày hạch toán {pd}")
        if not lines:
            add(SEV_BLOCK, "khong_dong", "Chứng từ không có dòng hạch toán")
        for ln in lines:
            n = ln.get("line_no")
            amt = int(ln.get("amount") or 0)
            da, ca = ln.get("debit_account"), ln.get("credit_account")
            if not da and not ca:
                add(SEV_BLOCK, "thieu_tk", f"Dòng {n}: thiếu cả TK Nợ và TK Có", amt, n)
            for side, acc, pid in (("Nợ", da, ln.get("debit_partner_id")), ("Có", ca, ln.get("credit_partner_id"))):
                if not acc:
                    continue
                a = accounts.get(acc)
                if not a:
                    add(SEV_BLOCK, "tk_khong_ton_tai", f"Dòng {n}: TK {side} {acc} không có trong hệ thống tài khoản", amt, n)
                    continue
                if not a["is_detail"]:
                    add(SEV_BLOCK, "tk_tong_hop", f"Dòng {n}: TK {side} {acc} là TK tổng hợp, phải hạch toán TK chi tiết", amt, n)
                if not a["active"]:
                    add(SEV_BLOCK, "tk_ngung", f"Dòng {n}: TK {side} {acc} đã ngừng sử dụng", amt, n)
                if a["require_partner"] and not pid:
                    add(SEV_BLOCK, "thieu_doi_tuong", f"Dòng {n}: TK {side} {acc} bắt buộc chọn đối tượng {side}", amt, n)
                if acc.startswith(INVENTORY_PREFIXES) and not ln.get("item_id") and vt.code in ("BKMH", "BKBH", "PNK", "PXK"):
                    add(SEV_REVIEW, "thieu_ma_hang", f"Dòng {n}: TK kho {acc} chưa chọn mã hàng", amt, n)
                if acc.startswith(INVENTORY_PREFIXES) and ln.get("item_id") and not ln.get("warehouse_id"):
                    add(SEV_REVIEW, "thieu_kho", f"Dòng {n}: hàng tồn kho chưa chọn kho", amt, n)
            if amt == 0 and (da or ca):
                add(SEV_REVIEW, "dong_0", f"Dòng {n}: thành tiền bằng 0", 0, n)
            if amt < 0:
                add(SEV_REVIEW, "so_am", f"Dòng {n}: thành tiền âm – nên dùng bút toán đảo TK", amt, n)
            qty, price = to_decimal(ln.get("quantity")), to_decimal(ln.get("unit_price"))
            if qty and price:
                expect = line_amount(qty, price)
                # Dòng xuất kho do chức năng tính giá cập nhật: chấp nhận chênh lệch làm tròn ≤ 10 đồng
                tolerance = 10 if vt.code == "PXK" else 0
                if abs(expect - amt) > tolerance:
                    add(SEV_REVIEW, "lech_thanh_tien",
                        f"Dòng {n}: Thành tiền {amt:,} khác Số lượng × Đơn giá {expect:,}".replace(",", "."), amt - expect, n)
            if vt.tax_account and ln.get("tax_rate") not in (None, ""):
                expect_tax = tax_amount(amt, ln["tax_rate"])
                if expect_tax != int(ln.get("tax_amount") or 0):
                    diff = int(ln.get("tax_amount") or 0) - expect_tax
                    add(SEV_REVIEW, "lech_thue",
                        f"Dòng {n}: Tiền thuế khác Thành tiền × Thuế suất ({to_decimal(ln['tax_rate'])}%)", diff, n)
            if vt.tax_account and int(ln.get("tax_amount") or 0):
                contra = ca if vt.tax_side == "D" else da
                if not contra:
                    add(SEV_BLOCK, "thue_thieu_tk",
                        f"Dòng {n}: có tiền thuế nhưng thiếu TK {'Có' if vt.tax_side == 'D' else 'Nợ'} để hạch toán thuế", 0, n)
        tot = self.totals(header["vtype"], lines)
        if tot["difference"]:
            add(SEV_BLOCK, "lech_no_co",
                f"Chứng từ không cân đối: Tổng Nợ {tot['debit']:,} – Tổng Có {tot['credit']:,}".replace(",", "."),
                tot["difference"])
        if voucher_id and header.get("total_payment") is not None:
            if (int(header.get("total_amount") or 0), int(header.get("total_tax") or 0), int(header.get("total_payment") or 0)) != (
                    tot["amount"], tot["tax"], tot["payment"]):
                add(SEV_REVIEW, "lech_tong",
                    "Tổng tiền hàng / tiền thuế / thanh toán lưu trên chứng từ khác tổng các dòng",
                    int(header.get("total_payment") or 0) - tot["payment"])
        # Nghi trùng hóa đơn
        inv = (header.get("invoice_no") or "").strip()
        key_tax, key_partner = (header.get("tax_code") or "").strip(), header.get("partner_id")
        if inv and (key_tax or key_partner):
            cond, params = ("COALESCE(tax_code,'')=?", key_tax) if key_tax else ("partner_id=?", key_partner)
            dups = self.db.query(f"""SELECT number FROM voucher WHERE company_id=? AND id<>? AND vtype=? AND invoice_no=?
                                     AND COALESCE(invoice_series,'')=? AND {cond}""",
                                 (self.s.company_id, voucher_id or 0, header["vtype"], inv,
                                  (header.get("invoice_series") or "").strip(), params))
            for d in dups:
                add(SEV_REVIEW, "trung_hoa_don",
                    f"Nghi trùng hóa đơn {header.get('invoice_series') or ''} số {inv} với chứng từ {d['number']}")
        return issues

    def check(self, voucher_id: int) -> list[Issue]:
        self.s.require("edit", "kiểm tra chứng từ")
        v = self.get(voucher_id)
        if v["status"] == POSTED:
            raise BusinessError("Chứng từ đã ghi sổ.")
        issues = self.validate_data(v, v["lines"], voucher_id)
        if any(i.severity == SEV_BLOCK for i in issues):
            raise ValidationFailed(issues)
        with self.db.transaction():
            self.db.execute("UPDATE voucher SET status=?, checked_by=?, checked_at=? WHERE id=?",
                            (CHECKED, self.s.user.username, datetime.now().isoformat(timespec="seconds"), voucher_id))
            self.s.audit("Kiểm tra chứng từ", "voucher", f"{v['vtype']}/{v['number']}")
        return issues

    # ================================================================ ghi sổ
    def ledger_rows(self, v: dict) -> list[tuple]:
        vt = VOUCHER_TYPES[v["vtype"]]
        rows = []
        for ln in v["lines"]:
            a = int(ln["amount"] or 0)
            da, ca = ln["debit_account"], ln["credit_account"]
            common = (ln["item_id"], ln["warehouse_id"], ln["quantity"], ln["project_id"], ln["department_id"],
                      ln["expense_item_id"])
            desc = ln["description"] or v["description"]
            if da and a:
                rows.append((ln["id"], da, ca, ln["debit_partner_id"], *common, a, 0, desc, 0))
            if ca and a:
                rows.append((ln["id"], ca, da, ln["credit_partner_id"], *common, 0, a, desc, 0))
            t = int(ln["tax_amount"] or 0) if vt.tax_account else 0
            if t:
                tdesc = f"Thuế GTGT – {desc or ''}".strip(" –")
                nil = (None, None, None, ln["project_id"], ln["department_id"], None)
                if vt.tax_side == "D":
                    rows.append((ln["id"], vt.tax_account, ca, None, *nil, t, 0, tdesc, 1))
                    rows.append((ln["id"], ca, vt.tax_account, ln["credit_partner_id"], *nil, 0, t, tdesc, 1))
                else:
                    rows.append((ln["id"], da, vt.tax_account, ln["debit_partner_id"], *nil, t, 0, tdesc, 1))
                    rows.append((ln["id"], vt.tax_account, da, None, *nil, 0, t, tdesc, 1))
        return rows

    def post(self, voucher_id: int, skip_check_status: bool = False) -> list[Issue]:
        self.s.require("post", "ghi sổ")
        v = self.get(voucher_id)
        if v["status"] == POSTED:
            raise BusinessError("Chứng từ đã được ghi sổ.")
        issues = self.validate_data(v, v["lines"], voucher_id)
        if any(i.severity == SEV_BLOCK for i in issues):
            raise ValidationFailed(issues)
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.transaction():
            d = self._write_ledger(v)
            self.db.execute("""UPDATE voucher SET status=?, posted_by=?, posted_at=?,
                               checked_by=COALESCE(checked_by, ?), checked_at=COALESCE(checked_at, ?) WHERE id=?""",
                            (POSTED, self.s.user.username, now, self.s.user.username, now, voucher_id))
            self.s.audit("Ghi sổ", "voucher", f"{v['vtype']}/{v['number']}", {"tong_no": d["d"]})
        return issues

    def _write_ledger(self, v: dict) -> dict:
        """Xóa và sinh lại bút toán sổ cái của chứng từ; luôn kiểm tra tổng Nợ = tổng Có."""
        voucher_id = v["id"]
        self.db.execute("DELETE FROM ledger_entry WHERE voucher_id=?", (voucher_id,))
        for r in self.ledger_rows(v):
            self.db.execute("""INSERT INTO ledger_entry(company_id, voucher_id, posting_date, line_id, account_code,
                contra_account, partner_id, item_id, warehouse_id, quantity, project_id, department_id, expense_item_id,
                debit, credit, description, is_tax) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (self.s.company_id, voucher_id, v["posting_date"], *r))
        d = self.db.one("SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) c FROM ledger_entry WHERE voucher_id=?",
                        (voucher_id,))
        if d["d"] != d["c"]:     # chốt chặn cuối cùng – không bao giờ ghi sổ lệch
            raise BusinessError(f"Bút toán sinh ra không cân đối ({d['d']} ≠ {d['c']}). Đã hoàn tác.")
        return d

    def update_line_prices(self, changes: list[tuple]):
        """Cập nhật đơn giá/thành tiền dòng (dùng cho tính giá xuất kho) và ghi lại sổ nếu chứng từ đã ghi sổ.

        changes: [(line_id, unit_price(Decimal), amount(int))]. Gọi trong giao dịch của nơi gọi.
        """
        by_voucher: dict[int, list] = {}
        for line_id, price, amount in changes:
            vid = self.db.scalar("SELECT voucher_id FROM voucher_line WHERE id=?", (line_id,))
            by_voucher.setdefault(vid, []).append((line_id, price, amount))
        for vid, items in by_voucher.items():
            v = self.db.one("SELECT * FROM voucher WHERE id=?", (vid,))
            if self.periods.is_locked(v["posting_date"]):
                raise BusinessError(f"Chứng từ {v['number']} thuộc kỳ đã khóa – không cập nhật giá.")
            for line_id, price, amount in items:
                self.db.execute("UPDATE voucher_line SET unit_price=?, amount=? WHERE id=?",
                                (dec_to_str(price), amount, line_id))
            full = self.get(vid)
            tot = self.totals(full["vtype"], full["lines"])
            self.db.execute("UPDATE voucher SET total_amount=?, total_tax=?, total_payment=? WHERE id=?",
                            (tot["amount"], tot["tax"], tot["payment"], vid))
            if v["status"] == POSTED:
                self._write_ledger(full)

    def default_due_date(self, partner_id, base_date: str | None) -> str | None:
        if not base_date:
            return None
        terms = self.db.scalar("SELECT payment_terms FROM partner WHERE id=?", (partner_id,), 0) or 0
        from datetime import timedelta
        return (date.fromisoformat(base_date[:10]) + timedelta(days=int(terms))).isoformat()

    def unpost(self, voucher_id: int):
        self.s.require("post", "bỏ ghi sổ")
        v = self.get(voucher_id)
        if v["status"] != POSTED:
            raise BusinessError("Chứng từ chưa ghi sổ.")
        if self.periods.is_locked(v["posting_date"]):
            raise BusinessError("Chứng từ thuộc kỳ đã khóa – không thể bỏ ghi sổ. Cần mở khóa kỳ trước.")
        with self.db.transaction():
            self.db.execute("DELETE FROM ledger_entry WHERE voucher_id=?", (voucher_id,))
            self.db.execute("UPDATE voucher SET status=?, posted_by=NULL, posted_at=NULL WHERE id=?", (CHECKED, voucher_id))
            self.s.audit("Bỏ ghi sổ", "voucher", f"{v['vtype']}/{v['number']}")

    def delete(self, voucher_id: int):
        self.s.require("delete", "xóa chứng từ")
        v = self.get(voucher_id)
        if v["status"] == POSTED:
            raise BusinessError("Chứng từ đã ghi sổ – phải «Bỏ ghi sổ» trước khi xóa.")
        if self.periods.is_locked(v["posting_date"]):
            raise BusinessError("Chứng từ thuộc kỳ đã khóa – không thể xóa.")
        with self.db.transaction():
            self.db.execute("DELETE FROM voucher WHERE id=?", (voucher_id,))
            self.s.audit("Xóa chứng từ", "voucher", f"{v['vtype']}/{v['number']}",
                         {"tong_thanh_toan": v["total_payment"], "ngay": v["posting_date"]})
