"""Kết chuyển cuối kỳ: doanh thu, chi phí → 911 → lợi nhuận chưa phân phối.

- Luôn có bảng XEM TRƯỚC; chỉ tạo chứng từ khi người dùng xác nhận.
- Chứng từ kết chuyển (loại KC) được tạo và ghi sổ trong cùng một giao dịch.
- Hoàn tác: bỏ ghi sổ + xóa chứng từ KC, chỉ khi kỳ chưa khóa.
- Phạm vi giai đoạn 1: KHÔNG tự tính chi phí thuế TNDN (TK 821). Nếu có số liệu 821 do người dùng
  hạch toán thì 821 được kết chuyển như chi phí.
- Danh sách TK kết chuyển là cấu hình mẫu theo hệ thống TK của dữ liệu minh họa
  (constants.CLOSING_*); cần đối chiếu với chế độ kế toán doanh nghiệp áp dụng.
"""
from __future__ import annotations

from ketoan.domain.constants import (CLOSING_EXPENSE_PREFIXES, CLOSING_PROFIT_ACCOUNT, CLOSING_RESULT_ACCOUNT,
                                     CLOSING_REVENUE_PREFIXES, POSTED)
from ketoan.services.context import BusinessError, Session
from ketoan.services.voucher_service import VoucherService


class ClosingService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db
        self.vs = VoucherService(session)

    def preview(self, d_from: str, d_to: str) -> list[dict]:
        c = self.s.company_id
        rows = self.db.query("""SELECT e.account_code acc, a.name, SUM(e.debit) d, SUM(e.credit) cr
                                FROM ledger_entry e LEFT JOIN account a ON a.company_id=e.company_id AND a.code=e.account_code
                                WHERE e.company_id=? AND e.posting_date BETWEEN ? AND ?
                                GROUP BY e.account_code, a.name ORDER BY e.account_code""", (c, d_from, d_to))
        lines, result = [], 0
        for r in rows:
            net = r["d"] - r["cr"]
            if not net:
                continue
            if r["acc"].startswith(CLOSING_REVENUE_PREFIXES):
                # Doanh thu/thu nhập: dư Có → Nợ TK DT / Có 911 (nếu dư Nợ thì đảo chiều)
                d, cr = (r["acc"], CLOSING_RESULT_ACCOUNT) if net < 0 else (CLOSING_RESULT_ACCOUNT, r["acc"])
                lines.append({"description": f"Kết chuyển {r['name']}", "debit_account": d, "credit_account": cr,
                              "amount": abs(net)})
                result -= net
            elif r["acc"].startswith(CLOSING_EXPENSE_PREFIXES):
                d, cr = (CLOSING_RESULT_ACCOUNT, r["acc"]) if net > 0 else (r["acc"], CLOSING_RESULT_ACCOUNT)
                lines.append({"description": f"Kết chuyển {r['name']}", "debit_account": d, "credit_account": cr,
                              "amount": abs(net)})
                result -= net
        # 911 hiện có (nếu đã có phát sinh 911 khác) cũng được tính vào kết quả
        existing_911 = self.db.scalar("""SELECT COALESCE(SUM(credit-debit),0) FROM ledger_entry WHERE company_id=?
                                         AND account_code LIKE ? AND posting_date BETWEEN ? AND ?""",
                                      (c, CLOSING_RESULT_ACCOUNT + "%", d_from, d_to), 0)
        result += existing_911
        if result:
            if result > 0:
                lines.append({"description": "Kết chuyển lãi", "debit_account": CLOSING_RESULT_ACCOUNT,
                              "credit_account": CLOSING_PROFIT_ACCOUNT, "amount": result})
            else:
                lines.append({"description": "Kết chuyển lỗ", "debit_account": CLOSING_PROFIT_ACCOUNT,
                              "credit_account": CLOSING_RESULT_ACCOUNT, "amount": -result})
        return lines

    def execute(self, d_from: str, d_to: str) -> int:
        self.s.require("post", "kết chuyển cuối kỳ")
        lines = self.preview(d_from, d_to)
        if not lines:
            raise BusinessError("Không có số dư doanh thu / chi phí cần kết chuyển trong kỳ.")
        header = {"vtype": "KC", "voucher_date": d_to, "posting_date": d_to,
                  "description": f"Kết chuyển xác định kết quả kinh doanh từ {d_from} đến {d_to}"}
        with self.db.transaction():
            vid = self.vs.save(header, lines)
            self.vs.post(vid)
            self.s.audit("Kết chuyển cuối kỳ", "voucher", vid, {"tu": d_from, "den": d_to, "so_dong": len(lines)})
        return vid

    def history(self, d_from: str, d_to: str):
        return self.db.query("""SELECT * FROM voucher WHERE company_id=? AND vtype='KC' AND posting_date BETWEEN ? AND ?
                                ORDER BY posting_date DESC, id DESC""", (self.s.company_id, d_from, d_to))

    def undo(self, voucher_id: int):
        self.s.require("post", "hoàn tác kết chuyển")
        v = self.vs.get(voucher_id)
        if v["vtype"] != "KC":
            raise BusinessError("Chỉ hoàn tác được chứng từ kết chuyển.")
        with self.db.transaction():
            if v["status"] == POSTED:
                self.vs.unpost(voucher_id)
            self.vs.delete(voucher_id)
            self.s.audit("Hoàn tác kết chuyển", "voucher", v["number"])
