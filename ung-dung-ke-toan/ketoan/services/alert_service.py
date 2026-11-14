"""Trung tâm cảnh báo – kiểm tra và đối chiếu.

Nguyên tắc: CHỈ PHÁT HIỆN và chỉ ra nơi xử lý; KHÔNG tự sửa dữ liệu kế toán.
Mỗi cảnh báo có: mức độ, nhóm, nguyên nhân, số chênh lệch, chứng từ liên quan, đích mở để xử lý.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ketoan.domain.constants import INVENTORY_PREFIXES, POSTED, SEV_BLOCK, SEV_INFO, SEV_REVIEW
from ketoan.domain.money import to_decimal
from ketoan.services.context import Session
from ketoan.services.voucher_service import VoucherService

RULE_GROUP = {
    "lech_no_co": "Chứng từ không cân đối Nợ – Có",
    "thieu_tk": "Thiếu tài khoản / đối tượng bắt buộc",
    "tk_khong_ton_tai": "Thiếu tài khoản / đối tượng bắt buộc",
    "tk_tong_hop": "Thiếu tài khoản / đối tượng bắt buộc",
    "tk_ngung": "Thiếu tài khoản / đối tượng bắt buộc",
    "thieu_doi_tuong": "Thiếu tài khoản / đối tượng bắt buộc",
    "thue_thieu_tk": "Thiếu tài khoản / đối tượng bắt buộc",
    "thieu_ma_hang": "Thiếu thông tin hàng tồn kho",
    "thieu_kho": "Thiếu thông tin hàng tồn kho",
    "trung_hoa_don": "Nghi trùng hóa đơn",
    "ton_am": "Tồn kho âm",
    "cong_no_bat_thuong": "Công nợ có số dư bất thường",
    "lech_tong_hop_chi_tiet": "Chênh lệch sổ tổng hợp và sổ chi tiết",
    "lech_thue": "Chênh lệch tiền hàng, tiền thuế, tổng thanh toán",
    "lech_thanh_tien": "Chênh lệch tiền hàng, tiền thuế, tổng thanh toán",
    "lech_tong": "Chênh lệch tiền hàng, tiền thuế, tổng thanh toán",
    "ky_khoa": "Chứng từ thuộc kỳ đã khóa",
    "ngoai_nam": "Ngày hạch toán ngoài năm tài chính",
    "so_du_dau_ky": "Số dư đầu kỳ",
    "chua_ghi_so": "Chứng từ chưa ghi sổ",
}


@dataclass
class Alert:
    severity: str
    rule: str
    message: str
    difference: int = 0
    voucher_id: int | None = None
    voucher_label: str = ""
    target: tuple = ()          # ("voucher", id) | ("account_detail", acc, partner_id) | ("opening_balance",)

    @property
    def group(self) -> str:
        return RULE_GROUP.get(self.rule, self.rule)


class AlertService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db
        self.vs = VoucherService(session)

    def collect(self, d_from: str, d_to: str) -> list[Alert]:
        alerts: list[Alert] = []
        alerts += self._voucher_checks(d_from, d_to)
        alerts += self._ledger_integrity(d_from, d_to)
        alerts += self._negative_stock(d_to)
        alerts += self._abnormal_debt(d_to)
        alerts += self._opening_balance(int(d_from[:4]))
        order = {SEV_BLOCK: 0, SEV_REVIEW: 1, SEV_INFO: 2}
        alerts.sort(key=lambda a: (order[a.severity], a.group, a.voucher_label))
        return alerts

    # ------------------------------------------------------------ từng chứng từ
    def _voucher_checks(self, d_from, d_to):
        out = []
        for v in self.db.query("SELECT id FROM voucher WHERE company_id=? AND posting_date BETWEEN ? AND ?",
                               (self.s.company_id, d_from, d_to)):
            vd = self.vs.get(v["id"])
            label = f"{vd['number']} ({vd['posting_date']})"
            issues = self.vs.validate_data(vd, vd["lines"], v["id"])
            for i in issues:
                sev = i.severity
                if vd["status"] == POSTED and sev == SEV_BLOCK:
                    sev = SEV_REVIEW   # đã ghi sổ trước khi phát sinh lỗi (vd đổi danh mục) – cần rà soát
                out.append(Alert(sev, i.rule, i.message, i.difference, v["id"], label, ("voucher", v["id"])))
            if vd["status"] != POSTED and not any(i.severity == SEV_BLOCK for i in issues):
                out.append(Alert(SEV_INFO, "chua_ghi_so", "Chứng từ hợp lệ nhưng chưa ghi sổ – chưa lên sổ sách, báo cáo",
                                 vd["total_payment"], v["id"], label, ("voucher", v["id"])))
        return out

    # ------------------------------------------------------------ đối chiếu sổ
    def _ledger_integrity(self, d_from, d_to):
        out, c = [], self.s.company_id
        # 1) Bút toán sổ cái của từng chứng từ phải cân và khớp chứng từ
        for r in self.db.query("""SELECT v.id, v.number, v.posting_date, SUM(e.debit) d, SUM(e.credit) cr
                                  FROM voucher v JOIN ledger_entry e ON e.voucher_id=v.id
                                  WHERE v.company_id=? AND v.posting_date BETWEEN ? AND ? GROUP BY v.id
                                  HAVING SUM(e.debit)<>SUM(e.credit)""", (c, d_from, d_to)):
            out.append(Alert(SEV_BLOCK, "lech_tong_hop_chi_tiet", "Bút toán trên sổ của chứng từ không cân đối",
                             r["d"] - r["cr"], r["id"], f"{r['number']} ({r['posting_date']})", ("voucher", r["id"])))
        for r in self.db.query("""SELECT v.id, v.number, v.posting_date FROM voucher v WHERE v.company_id=? AND v.status='POSTED'
                                  AND v.posting_date BETWEEN ? AND ?
                                  AND NOT EXISTS (SELECT 1 FROM ledger_entry e WHERE e.voucher_id=v.id)""", (c, d_from, d_to)):
            out.append(Alert(SEV_BLOCK, "lech_tong_hop_chi_tiet", "Chứng từ ở trạng thái Đã ghi sổ nhưng không có bút toán trên sổ",
                             0, r["id"], f"{r['number']} ({r['posting_date']})", ("voucher", r["id"])))
        # 2) TK bắt buộc đối tượng: tổng số dư TK (sổ tổng hợp) phải bằng tổng chi tiết theo đối tượng
        for a in self.db.query("SELECT code, name FROM account WHERE company_id=? AND require_partner=1 AND is_detail=1", (c,)):
            no_partner = self.db.scalar("""SELECT COALESCE(SUM(debit-credit),0) FROM ledger_entry WHERE company_id=?
                                           AND account_code=? AND partner_id IS NULL AND posting_date<=?""", (c, a["code"], d_to), 0)
            ob_no_partner = self.db.scalar("""SELECT COALESCE(SUM(debit-credit),0) FROM opening_balance WHERE company_id=?
                                              AND account_code=? AND partner_id IS NULL AND year=?""", (c, a["code"], int(d_to[:4])), 0)
            diff = no_partner + ob_no_partner
            if diff:
                out.append(Alert(SEV_REVIEW, "lech_tong_hop_chi_tiet",
                                 f"TK {a['code']} – {a['name']}: số liệu không gắn đối tượng, sổ tổng hợp lệch sổ chi tiết công nợ",
                                 diff, None, "", ("account_detail", a["code"], None)))
        # 3) Tổng phát sinh toàn sổ
        tot = self.db.one("""SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) cr FROM ledger_entry
                             WHERE company_id=? AND posting_date BETWEEN ? AND ?""", (c, d_from, d_to))
        if tot["d"] != tot["cr"]:
            out.append(Alert(SEV_BLOCK, "lech_tong_hop_chi_tiet", "Tổng phát sinh Nợ toàn sổ khác tổng phát sinh Có",
                             tot["d"] - tot["cr"], None, "", ("trial_balance",)))
        return out

    # ------------------------------------------------------------ tồn kho âm
    def _negative_stock(self, d_to):
        c = self.s.company_id
        bal: dict[tuple, object] = defaultdict(lambda: to_decimal(0))
        flagged = {}
        rows = self.db.query("""SELECT e.item_id, e.warehouse_id, e.quantity, e.debit, e.credit, e.voucher_id, e.posting_date,
                                       v.number, i.code icode, i.name iname, w.code wcode, e.account_code
                                FROM ledger_entry e JOIN voucher v ON v.id=e.voucher_id
                                JOIN item i ON i.id=e.item_id LEFT JOIN warehouse w ON w.id=e.warehouse_id
                                WHERE e.company_id=? AND e.item_id IS NOT NULL AND e.is_tax=0 AND e.posting_date<=?
                                ORDER BY e.posting_date, (e.debit=0), e.id""", (c, d_to))
        for r in rows:
            if not r["account_code"].startswith(INVENTORY_PREFIXES):
                continue
            key = (r["item_id"], r["warehouse_id"])
            q = to_decimal(r["quantity"])
            bal[key] += q if r["debit"] else -q
            if bal[key] < 0 and key not in flagged:
                flagged[key] = r
        out = []
        for key, r in flagged.items():
            out.append(Alert(SEV_REVIEW, "ton_am",
                             f"Hàng {r['icode']} – {r['iname']} tại kho {r['wcode'] or '(chưa chọn)'} bị âm từ ngày "
                             f"{r['posting_date']}; tồn hiện tại {bal[key].normalize()} (chưa tính số lượng tồn đầu năm – GĐ2)",
                             0, r["voucher_id"], f"{r['number']} ({r['posting_date']})", ("voucher", r["voucher_id"])))
        return out

    # ------------------------------------------------------------ công nợ bất thường
    def _abnormal_debt(self, d_to):
        c, out = self.s.company_id, []
        year = int(d_to[:4])
        checks = (("131", "Khách hàng có số dư Có (trả trước/thu thừa) – cần xác nhận", lambda n: n < 0),
                  ("331", "Nhà cung cấp có số dư Nợ (ứng trước/trả thừa) – cần xác nhận", lambda n: n > 0))
        for acc, text, abnormal in checks:
            rows = self.db.query("""
                SELECT p.id, p.code, p.name, SUM(n) net FROM (
                    SELECT partner_id, debit-credit n FROM opening_balance WHERE company_id=? AND year=? AND account_code LIKE ?
                    UNION ALL
                    SELECT partner_id, debit-credit FROM ledger_entry WHERE company_id=? AND account_code LIKE ?
                           AND posting_date BETWEEN ? AND ?) x
                JOIN partner p ON p.id=x.partner_id GROUP BY p.id HAVING SUM(n)<>0""",
                                 (c, year, acc + "%", c, acc + "%", f"{year}-01-01", d_to))
            for r in rows:
                if abnormal(r["net"]):
                    out.append(Alert(SEV_REVIEW, "cong_no_bat_thuong", f"{r['code']} – {r['name']}: {text}",
                                     r["net"], None, "", ("account_detail", acc, r["id"])))
        return out

    # ------------------------------------------------------------ số dư đầu kỳ
    def _opening_balance(self, year):
        r = self.db.one("""SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) cr FROM opening_balance
                           WHERE company_id=? AND year=?""", (self.s.company_id, year))
        out = []
        if r["d"] != r["cr"]:
            out.append(Alert(SEV_BLOCK, "so_du_dau_ky", f"Số dư đầu năm {year} không cân đối Nợ – Có",
                             r["d"] - r["cr"], None, "", ("opening_balance",)))
        for x in self.db.query("""SELECT ob.account_code FROM opening_balance ob JOIN account a ON a.company_id=ob.company_id
                                  AND a.code=ob.account_code WHERE ob.company_id=? AND ob.year=? AND a.is_detail=0""",
                               (self.s.company_id, year)):
            out.append(Alert(SEV_REVIEW, "lech_tong_hop_chi_tiet",
                             f"Số dư đầu năm nhập trên TK tổng hợp {x['account_code']} – cần nhập vào TK chi tiết",
                             0, None, "", ("opening_balance",)))
        return out

    def counts(self, alerts: list[Alert]) -> dict:
        res = {SEV_BLOCK: 0, SEV_REVIEW: 0, SEV_INFO: 0}
        for a in alerts:
            res[a.severity] += 1
        return res
