"""Tập hợp chi phí (TK 154) và tính giá thành theo đối tượng (công trình / đơn hàng / sản phẩm / tuyến / hợp đồng).

Đối tượng tính giá thành = danh mục «Công trình, đơn hàng» (chiều `project` trên chứng từ).

CÁC CÁCH TÍNH (giai đoạn 3):
  GD   Giản đơn           : Giá thành = Dở dang đầu kỳ + CP phát sinh − Dở dang cuối kỳ (dở dang cuối kỳ do người dùng nhập).
  KDD  Không có dở dang   : Dở dang cuối kỳ = 0 → toàn bộ CP trong kỳ (+ dở dang đầu kỳ nếu có) vào giá thành.
  DM   Theo định mức      : như GD, thêm so sánh với định mức: Giá thành định mức = SL × Định mức đơn vị (người dùng nhập);
                            hiển thị chênh lệch và tỷ lệ chênh lệch theo định mức. KHÔNG tự lập/duyệt định mức.
  KDM  Không định mức     : như GD, có phân bổ CHI PHÍ CHUNG (chi phí 154 chưa gắn đối tượng) cho các đối tượng theo tỷ lệ
                            chi phí trực tiếp của từng đối tượng.
Công trình xây dựng / Dịch vụ / Vận tải dùng cùng bộ máy (đối tượng = công trình / hợp đồng / đầu xe, tuyến) với TK ghi nhận
giá vốn mặc định phù hợp loại hình; người dùng đổi được.

Giá thành là số liệu tính theo quy ước trên đây từ chi phí đã GHI SỔ trên TK 154; chưa có: phân bổ chi phí sản xuất chung theo
tiêu thức tự động từ TK 627/621/622 (hệ thống TK mẫu không có các TK này), quy đổi sản phẩm dở dang theo mức độ hoàn thành,
giá thành phân bước. Kết chuyển giá thành tạo chứng từ NHÁP: Nợ TK giá vốn/thành phẩm / Có 154 (theo từng đối tượng).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ketoan.domain.money import ZERO, dec_to_str, round_money, round_price, to_decimal
from ketoan.services.context import BusinessError, Session
from ketoan.services.period_service import PeriodService
from ketoan.services.voucher_service import VoucherService

COST_ACCOUNT = "154"
METHODS = {"GD": "Giản đơn", "KDD": "Không có dở dang", "DM": "Theo định mức", "KDM": "Không định mức"}
# loại hình → (nhãn, cách tính mặc định, TK Nợ mặc định khi kết chuyển giá thành)
PRESETS = {
    "gt_ct": ("Công trình xây dựng", "GD", "632"),
    "gt_dm": ("Sản xuất theo định mức", "DM", "155"),
    "gt_kdm": ("Sản xuất không định mức", "KDM", "155"),
    "gt_gd": ("Sản xuất giản đơn", "GD", "155"),
    "gt_dv": ("Dịch vụ", "GD", "632"),
    "gt_vt": ("Vận tải", "GD", "632"),
    "gt_kdd": ("Sản xuất không có dở dang", "KDD", "155"),
}


@dataclass
class CostRow:
    project_id: int
    code: str
    name: str
    by_item: dict = field(default_factory=dict)      # khoản mục -> số tiền trực tiếp
    direct: int = 0
    common: int = 0
    wip_begin: int = 0
    wip_end: int = 0
    quantity: object = ZERO
    norm_unit: object = ZERO
    saved: bool = False
    voucher_id: int | None = None

    @property
    def total(self) -> int:
        return self.wip_begin + self.direct + self.common - self.wip_end

    @property
    def unit(self):
        return round_price(to_decimal(self.total) / self.quantity) if self.quantity else None

    @property
    def standard_total(self):
        return round_money(self.quantity * self.norm_unit) if self.norm_unit and self.quantity else None

    @property
    def variance(self):
        st = self.standard_total
        return None if st is None else self.total - st

    @property
    def variance_pct(self):
        st = self.standard_total
        return None if not st else self.variance * 100 / st


class CostService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db
        self.periods = PeriodService(session)

    # ------------------------------------------------------------ tập hợp chi phí
    def _kc_vouchers(self) -> set[int]:
        return {r["voucher_id"] for r in self.db.query(
            "SELECT voucher_id FROM cost_sheet WHERE company_id=? AND voucher_id IS NOT NULL", (self.s.company_id,))}

    def collect(self, d_from: str, d_to: str):
        """Chi phí phát sinh TK 154 trong kỳ theo (công trình, khoản mục); loại trừ chứng từ kết chuyển giá thành."""
        skip = self._kc_vouchers()
        agg: dict[tuple, int] = {}
        for r in self.db.query("""SELECT voucher_id, project_id, expense_item_id, debit - credit AS n FROM ledger_entry
                                  WHERE company_id=? AND account_code LIKE '154%' AND posting_date BETWEEN ? AND ?""",
                               (self.s.company_id, d_from, d_to)):
            if r["voucher_id"] in skip:
                continue
            k = (r["project_id"], r["expense_item_id"])
            agg[k] = agg.get(k, 0) + r["n"]
        return agg

    def _names(self):
        pr = {r["id"]: r for r in self.db.query("SELECT id, code, name FROM project WHERE company_id=?", (self.s.company_id,))}
        ex = {r["id"]: r for r in self.db.query("SELECT id, code, name FROM expense_item WHERE company_id=?", (self.s.company_id,))}
        return pr, ex

    def _previous_wip(self, project_id: int, d_from: str, method_family: str) -> int:
        r = self.db.one("""SELECT wip_end FROM cost_sheet WHERE company_id=? AND project_id=? AND d_to < ?
                           ORDER BY d_to DESC LIMIT 1""", (self.s.company_id, project_id, d_from))
        return r["wip_end"] if r else 0

    def calculate(self, method: str, d_from: str, d_to: str, inputs: dict | None = None) -> tuple[list[CostRow], list]:
        """inputs: {project_id: {quantity, wip_begin, wip_end, norm_unit}}. Trả về (các dòng, danh sách khoản mục)."""
        if method not in METHODS:
            raise BusinessError("Cách tính giá thành không hợp lệ.")
        inputs = inputs or {}
        pr, ex = self._names()
        costs = self.collect(d_from, d_to)
        saved = {r["project_id"]: r for r in self.db.query(
            "SELECT * FROM cost_sheet WHERE company_id=? AND method=? AND d_from=? AND d_to=?",
            (self.s.company_id, method, d_from, d_to))}
        rows: dict[int, CostRow] = {}
        common_by_item: dict = {}
        for (pid, eid), amt in costs.items():
            if pid is None:
                common_by_item[eid] = common_by_item.get(eid, 0) + amt
                continue
            r = rows.setdefault(pid, CostRow(pid, pr[pid]["code"] if pid in pr else "?", pr[pid]["name"] if pid in pr else ""))
            r.by_item[eid] = r.by_item.get(eid, 0) + amt
        for pid in set(saved) - set(rows):
            rows[pid] = CostRow(pid, pr[pid]["code"] if pid in pr else "?", pr[pid]["name"] if pid in pr else "")
        # dở dang đầu kỳ: đã chốt kỳ trước (nếu có)
        for pid, r in rows.items():
            r.direct = sum(r.by_item.values())
            sv, inp = saved.get(pid), inputs.get(pid, {})
            r.wip_begin = inp.get("wip_begin", sv["wip_begin"] if sv else self._previous_wip(pid, d_from, method))
            r.quantity = to_decimal(inp.get("quantity", sv["quantity"] if sv else 0))
            r.norm_unit = to_decimal(inp.get("norm_unit", (sv["norm_unit_cost"] if sv and sv["norm_unit_cost"] else 0)))
            r.wip_end = 0 if method == "KDD" else round_money(inp.get("wip_end", sv["wip_end"] if sv else 0))
            if sv:
                r.saved, r.voucher_id = True, sv["voucher_id"]
        if method == "KDM":               # phân bổ chi phí chung theo tỷ lệ chi phí trực tiếp
            common_total = sum(common_by_item.values())
            base = sum(r.direct for r in rows.values())
            order = sorted(rows.values(), key=lambda r: r.code)
            alloc = 0
            for i, r in enumerate(order):
                r.common = (common_total - alloc) if i == len(order) - 1 else (round_money(common_total * r.direct / base) if base else 0)
                alloc += r.common
        out = sorted(rows.values(), key=lambda r: r.code)
        items = sorted({e for r in out for e in r.by_item}, key=lambda e: (ex[e]["code"] if e in ex else "~"))
        self._item_names = {e: (ex[e]["name"] if e in ex else "Chưa phân khoản mục") for e in items}
        self.common_unallocated = 0 if method == "KDM" else sum(common_by_item.values())
        return out, items

    def item_name(self, eid) -> str:
        return getattr(self, "_item_names", {}).get(eid, "Chưa phân khoản mục")

    # ------------------------------------------------------------ lưu & kết chuyển giá thành
    def save_and_transfer(self, method: str, d_from: str, d_to: str, rows: list[CostRow], debit_account: str,
                          make_voucher: bool = True) -> int | None:
        self.s.require("add", "lưu bảng tính giá thành")
        if not self.db.scalar("SELECT 1 FROM account WHERE company_id=? AND code=? AND is_detail=1", (self.s.company_id, debit_account)):
            raise BusinessError(f"TK Nợ '{debit_account}' không có hoặc là TK tổng hợp.")
        if self.periods.is_locked(d_to):
            raise BusinessError("Kỳ tính giá thành đã khóa.")
        todo = [r for r in rows if r.total > 0 and r.quantity and r.quantity > 0]
        if make_voucher and not todo:
            raise BusinessError("Chưa có đối tượng nào đủ điều kiện kết chuyển (cần giá thành > 0 và số lượng hoàn thành > 0).")
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.transaction():
            vid = None
            if make_voucher:
                for r in todo:
                    if r.saved and r.voucher_id and self.db.scalar("SELECT 1 FROM voucher WHERE id=?", (r.voucher_id,)):
                        raise BusinessError(f"Đối tượng {r.code} đã kết chuyển giá thành kỳ này (chứng từ có sẵn) – hoàn tác trước.")
                lines = [{"description": f"Kết chuyển giá thành {r.name} ({r.code})", "debit_account": debit_account,
                          "credit_account": COST_ACCOUNT, "amount": r.total, "project": r.code} for r in todo]
                vid = VoucherService(self.s).save({"vtype": "PKT", "voucher_date": d_to, "posting_date": d_to,
                                                   "description": f"Kết chuyển giá thành ({METHODS[method]}) từ {d_from} đến {d_to}"},
                                                  lines)
            done_ids = {r.project_id for r in todo}
            for r in rows:
                self.db.execute("""INSERT INTO cost_sheet(company_id, method, d_from, d_to, project_id, quantity, wip_begin,
                    direct_cost, common_cost, wip_end, total_cost, unit_cost, norm_unit_cost, voucher_id, saved_by, saved_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(company_id, method, d_from, d_to, project_id) DO UPDATE SET quantity=excluded.quantity,
                    wip_begin=excluded.wip_begin, direct_cost=excluded.direct_cost, common_cost=excluded.common_cost,
                    wip_end=excluded.wip_end, total_cost=excluded.total_cost, unit_cost=excluded.unit_cost,
                    norm_unit_cost=excluded.norm_unit_cost, voucher_id=COALESCE(excluded.voucher_id, cost_sheet.voucher_id),
                    saved_by=excluded.saved_by, saved_at=excluded.saved_at""",
                                (self.s.company_id, method, d_from, d_to, r.project_id, dec_to_str(r.quantity), r.wip_begin,
                                 r.direct, r.common, r.wip_end, r.total, dec_to_str(r.unit) if r.unit else None,
                                 dec_to_str(r.norm_unit) if r.norm_unit else None, vid if r.project_id in done_ids else None,
                                 self.s.user.username, now))
            self.s.audit("Lưu bảng tính giá thành", "cost_sheet", f"{d_from}..{d_to}",
                         {"cach_tinh": method, "so_doi_tuong": len(rows), "chung_tu": vid})
        return vid

    def undo_transfer(self, method: str, d_from: str, d_to: str):
        self.s.require("post", "hoàn tác kết chuyển giá thành")
        vids = {r["voucher_id"] for r in self.db.query(
            "SELECT DISTINCT voucher_id FROM cost_sheet WHERE company_id=? AND method=? AND d_from=? AND d_to=? AND voucher_id IS NOT NULL",
            (self.s.company_id, method, d_from, d_to))}
        if not vids:
            raise BusinessError("Kỳ này chưa có chứng từ kết chuyển giá thành.")
        vs = VoucherService(self.s)
        with self.db.transaction():
            for vid in vids:
                v = self.db.one("SELECT status FROM voucher WHERE id=?", (vid,))
                if v and v["status"] == "POSTED":
                    vs.unpost(vid)
                if v:
                    vs.delete(vid)
            self.s.audit("Hoàn tác kết chuyển giá thành", "cost_sheet", f"{d_from}..{d_to}", {"cach_tinh": method})

    # ------------------------------------------------------------ sổ chi tiết công trình
    def project_ledger(self, project_id: int, d_from: str, d_to: str) -> dict:
        c = self.s.company_id
        opening = self.db.scalar("""SELECT COALESCE(SUM(debit-credit),0) FROM ledger_entry WHERE company_id=? AND account_code LIKE '154%'
                                    AND project_id=? AND posting_date>=? AND posting_date<?""",
                                 (c, project_id, f"{d_from[:4]}-01-01", d_from), 0)
        rows = self.db.query("""SELECT e.voucher_id, e.posting_date, v.number, e.description, e.contra_account, e.debit, e.credit,
                                       x.code AS expense_code, x.name AS expense_name
                                FROM ledger_entry e JOIN voucher v ON v.id=e.voucher_id
                                LEFT JOIN expense_item x ON x.id=e.expense_item_id
                                WHERE e.company_id=? AND e.account_code LIKE '154%' AND e.project_id=? AND e.posting_date BETWEEN ? AND ?
                                ORDER BY e.posting_date, e.id""", (c, project_id, d_from, d_to))
        bal, out = opening, []
        for r in rows:
            bal += r["debit"] - r["credit"]
            d = dict(r)
            d["balance"] = bal
            out.append(d)
        by_item: dict[str, int] = {}
        for r in rows:
            k = r["expense_name"] or "Chưa phân khoản mục"
            by_item[k] = by_item.get(k, 0) + r["debit"] - r["credit"]
        return {"opening": opening, "rows": out, "closing": bal, "by_item": by_item}
