"""Mua – bán hàng: xuất kho hàng loạt từ bảng kê bán hàng, đối chiếu doanh thu – giá vốn.

Liên kết phiếu xuất ↔ bảng kê bán qua voucher.source_voucher_id (chỉ nhập một lần, truy ngược được).
"""
from __future__ import annotations

from collections import defaultdict

from ketoan.domain.constants import POSTED
from ketoan.domain.money import ZERO, to_decimal
from ketoan.services.context import BusinessError, Session
from ketoan.services.inventory_service import InventoryService
from ketoan.services.voucher_service import VoucherService


class TradeService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db
        self.vs = VoucherService(session)
        self.inv = InventoryService(session)

    # ------------------------------------------------------------ xuất kho hàng loạt
    def pending_issues(self, d_from: str, d_to: str) -> list[dict]:
        """Bảng kê bán hàng có mặt hàng tồn kho nhưng chưa có phiếu xuất kho liên kết."""
        rows = self.db.query("""
            SELECT v.id, v.number, v.posting_date, v.status, v.description, p.code partner_code, p.name partner_name,
                   l.id line_id, l.quantity, l.warehouse_id, i.id item_id, i.code item_code, i.name item_name, i.unit,
                   COALESCE(i.stock_account, '156') stock_account, w.code wh_code
            FROM voucher v JOIN voucher_line l ON l.voucher_id=v.id JOIN item i ON i.id=l.item_id
            LEFT JOIN partner p ON p.id=v.partner_id LEFT JOIN warehouse w ON w.id=l.warehouse_id
            WHERE v.company_id=? AND v.vtype='BKBH' AND v.posting_date BETWEEN ? AND ? AND i.kind<>'DV'
              AND NOT EXISTS (SELECT 1 FROM voucher x WHERE x.source_voucher_id=v.id)
            ORDER BY v.posting_date, v.number, l.line_no""", (self.s.company_id, d_from, d_to))
        out: dict[int, dict] = {}
        for r in rows:
            d = out.setdefault(r["id"], {"id": r["id"], "number": r["number"], "posting_date": r["posting_date"],
                                         "status": r["status"], "partner_code": r["partner_code"],
                                         "partner_name": r["partner_name"], "lines": []})
            d["lines"].append(dict(r))
        return list(out.values())

    def create_issues(self, sale_ids: list[int], post: bool = False) -> list[int]:
        """Lập phiếu xuất kho (Nợ 632 / Có TK kho) cho từng bảng kê bán; đơn giá tạm = bình quân đến ngày xuất.

        Cả lô nằm trong một giao dịch: lỗi ở bất kỳ chứng từ nào => không tạo phiếu nào.
        """
        self.s.require("add", "lập phiếu xuất kho hàng loạt")
        if post:
            self.s.require("post", "ghi sổ phiếu xuất kho")
        pending = {p["id"]: p for p in self.pending_issues("0000-01-01", "9999-12-31")}
        created = []
        with self.db.transaction():
            for sid in sale_ids:
                sale = pending.get(sid)
                if not sale:
                    raise BusinessError("Bảng kê đã có phiếu xuất kho hoặc không còn tồn tại.")
                lines = []
                for l in sale["lines"]:
                    if not l["warehouse_id"]:
                        raise BusinessError(f"{sale['number']}: dòng {l['item_code']} chưa chọn kho.")
                    price = self.inv.average_cost(l["item_id"], l["warehouse_id"], sale["posting_date"])
                    lines.append({"description": f"Xuất bán {l['item_name']}", "debit_account": "632",
                                  "credit_account": l["stock_account"], "item": l["item_code"], "warehouse": l["wh_code"],
                                  "quantity": l["quantity"], "unit_price": price})
                vid = self.vs.save({"vtype": "PXK", "voucher_date": sale["posting_date"], "posting_date": sale["posting_date"],
                                    "partner_code": sale["partner_code"], "source_voucher_id": sid,
                                    "description": f"Xuất kho theo {sale['number']} (giá tạm tính – chạy Tính giá xuất kho cuối kỳ)"},
                                   lines)
                if post:
                    self.vs.post(vid)
                created.append(vid)
            self.s.audit("Xuất kho hàng loạt", "voucher", "", {"so_phieu": len(created), "ghi_so": post})
        return created

    # ------------------------------------------------------------ đối chiếu doanh thu – giá vốn
    def revenue_cogs(self, d_from: str, d_to: str) -> list[dict]:
        c = self.s.company_id
        agg: dict[int, dict] = defaultdict(lambda: {"sold_q": ZERO, "revenue": 0, "out_q": ZERO, "cogs": 0})
        for r in self.db.query("""SELECT item_id, quantity, credit - debit amt FROM ledger_entry WHERE company_id=?
                                  AND account_code LIKE '511%' AND item_id IS NOT NULL AND is_tax=0
                                  AND posting_date BETWEEN ? AND ?""", (c, d_from, d_to)):
            a = agg[r["item_id"]]
            a["sold_q"] += to_decimal(r["quantity"]) * (1 if r["amt"] >= 0 else -1)
            a["revenue"] += r["amt"]
        for r in self.db.query("""SELECT item_id, quantity, debit - credit amt FROM ledger_entry WHERE company_id=?
                                  AND account_code LIKE '632%' AND item_id IS NOT NULL AND is_tax=0
                                  AND posting_date BETWEEN ? AND ?""", (c, d_from, d_to)):
            a = agg[r["item_id"]]
            a["out_q"] += to_decimal(r["quantity"]) * (1 if r["amt"] >= 0 else -1)
            a["cogs"] += r["amt"]
        items = {r["id"]: r for r in self.db.query("SELECT * FROM item WHERE company_id=?", (c,))}
        out = []
        for iid, a in agg.items():
            it = items.get(iid)
            is_service = it is not None and it["kind"] == "DV"
            margin = a["revenue"] - a["cogs"]
            out.append({"item_id": iid, "code": it["code"] if it else "?", "name": it["name"] if it else "",
                        "unit": it["unit"] if it else "", "kind": it["kind"] if it else "", **a,
                        "diff_q": a["sold_q"] - a["out_q"] if not is_service else ZERO,
                        "margin": margin, "margin_pct": (margin * 100 / a["revenue"]) if a["revenue"] else None,
                        "warning": ("Bán chưa xuất kho / chưa ghi giá vốn" if not is_service and a["sold_q"] > a["out_q"]
                                    else "Xuất kho giá vốn nhiều hơn số lượng bán" if not is_service and a["out_q"] > a["sold_q"]
                                    else "Giá vốn âm hoặc bằng 0" if not is_service and a["sold_q"] and a["cogs"] <= 0
                                    else "")})
        return sorted(out, key=lambda r: r["code"])

    def sale_without_cogs(self, d_from: str, d_to: str) -> list[dict]:
        """Bảng kê bán hàng ĐÃ GHI SỔ có hàng tồn kho nhưng chưa có phiếu xuất (dùng cho Trung tâm cảnh báo)."""
        return [p for p in self.pending_issues(d_from, d_to) if p["status"] == POSTED]

