"""Chuyển số dư cuối năm sang đầu năm sau (số dư tài khoản theo đối tượng và tồn kho theo hàng + kho).

Điều kiện: năm nguồn không còn số dư tài khoản doanh thu/chi phí/xác định kết quả (loại 5–9) → phải kết chuyển trước.
TK lợi nhuận chưa phân phối năm nay (4212) được chuyển sang năm trước (4211) – theo cấu hình mẫu YEAR_END_MAP, cần đối chiếu
với hệ thống TK của chế độ áp dụng. Số dư đầu năm sau cũ bị THAY THẾ (có nhật ký); không thực hiện nếu tháng 01 năm sau đã khóa.
Tồn kho âm không chuyển được (cần xử lý trước).
"""
from __future__ import annotations

from collections import defaultdict

from ketoan.domain.money import dec_to_str, to_decimal
from ketoan.services.context import BusinessError, Session
from ketoan.services.inventory_service import InventoryService
from ketoan.services.period_service import PeriodService

YEAR_END_MAP = {"4212": "4211"}
PNL_PREFIXES = ("5", "6", "7", "8", "9")


class YearEndService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    def balances(self, year: int) -> dict[tuple, int]:
        """Số dư cuối năm (Nợ − Có) theo (TK, đối tượng)."""
        c = self.s.company_id
        agg: dict[tuple, int] = defaultdict(int)
        for r in self.db.query("""SELECT account_code a, partner_id p, SUM(debit-credit) n FROM opening_balance WHERE company_id=? AND year=?
                                  GROUP BY a, p""", (c, year)):
            agg[(r["a"], r["p"])] += r["n"]
        for r in self.db.query("""SELECT account_code a, partner_id p, SUM(debit-credit) n FROM ledger_entry WHERE company_id=?
                                  AND posting_date BETWEEN ? AND ? GROUP BY a, p""", (c, f"{year}-01-01", f"{year}-12-31")):
            agg[(r["a"], r["p"])] += r["n"]
        return {k: v for k, v in agg.items() if v}

    def preview(self, year: int) -> dict:
        bal = self.balances(year)
        problems = []
        pnl = [(a, n) for (a, p), n in bal.items() if a.startswith(PNL_PREFIXES)]
        if pnl:
            problems.append("Còn số dư TK doanh thu / chi phí / xác định kết quả: " +
                            ", ".join(f"{a} ({n:,})".replace(",", ".") for a, n in sorted(set(pnl))[:8]) + " – cần kết chuyển trước.")
        rows: dict[tuple, int] = defaultdict(int)
        for (a, p), n in bal.items():
            if a.startswith(PNL_PREFIXES):
                continue
            rows[(YEAR_END_MAP.get(a, a), p)] += n
        rows = {k: v for k, v in rows.items() if v}
        nxt = f"{year + 1}-01-01"
        inv = InventoryService(self.s)
        end: dict[tuple, list] = defaultdict(lambda: [to_decimal(0), 0])
        for k, (q, v) in inv.opening(f"{year}-01-01").items():
            end[k][0] += q
            end[k][1] += v
        for m in inv.movements(f"{year}-01-01", f"{year}-12-31"):
            k = (m["item_id"], m["warehouse_id"])
            q = to_decimal(m["quantity"])
            if m["is_in"]:
                end[k][0] += q; end[k][1] += m["debit"]
            else:
                end[k][0] -= q; end[k][1] -= m["credit"]
        stock, skipped = [], []
        for (iid, wid), (q, v) in end.items():
            if q < 0 or v < 0:
                skipped.append((iid, wid, q, v))
            elif q > 0 or v > 0:
                stock.append((iid, wid, q, v))
        if skipped:
            problems.append(f"{len(skipped)} cặp hàng/kho có tồn âm – không chuyển được, cần xử lý trước.")
        if PeriodService(self.s).is_locked(nxt):
            problems.append(f"Tháng 01/{year + 1} đã khóa – không thể thay số dư đầu năm.")
        existing = self.db.scalar("SELECT COUNT(*) FROM opening_balance WHERE company_id=? AND year=?", (self.s.company_id, year + 1), 0)
        return {"rows": rows, "stock": stock, "problems": problems, "existing_rows": existing,
                "total_debit": sum(v for v in rows.values() if v > 0), "total_credit": -sum(v for v in rows.values() if v < 0)}

    def carry_forward(self, year: int):
        self.s.require("admin", "chuyển số dư cuối năm")
        pv = self.preview(year)
        if pv["problems"]:
            raise BusinessError("Chưa thể chuyển số dư:\n• " + "\n• ".join(pv["problems"]))
        if pv["total_debit"] != pv["total_credit"]:
            raise BusinessError(f"Số dư cuối năm không cân đối (Nợ {pv['total_debit']:,} ≠ Có {pv['total_credit']:,}).".replace(",", "."))
        nxt = year + 1
        with self.db.transaction():
            PeriodService(self.s).ensure_year(nxt)
            self.db.execute("DELETE FROM opening_balance WHERE company_id=? AND year=?", (self.s.company_id, nxt))
            self.db.executemany("INSERT INTO opening_balance(company_id, year, account_code, partner_id, debit, credit) VALUES(?,?,?,?,?,?)",
                                [(self.s.company_id, nxt, a, p, max(n, 0), max(-n, 0)) for (a, p), n in sorted(pv["rows"].items(), key=lambda x: (x[0][0], x[0][1] or 0))])
            self.db.execute("DELETE FROM opening_stock WHERE company_id=? AND year=?", (self.s.company_id, nxt))
            self.db.executemany("INSERT INTO opening_stock(company_id, year, item_id, warehouse_id, quantity, amount) VALUES(?,?,?,?,?,?)",
                                [(self.s.company_id, nxt, i, w, dec_to_str(to_decimal(q)), v) for i, w, q, v in pv["stock"]])
            self.s.audit("Chuyển số dư cuối năm", "opening_balance", f"{year}->{nxt}",
                         {"so_dong_tk": len(pv["rows"]), "so_dong_kho": len(pv["stock"]), "tong_no": pv["total_debit"]})
        return pv
