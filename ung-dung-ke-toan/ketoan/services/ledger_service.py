"""Sổ kế toán: Nhật ký chung, Sổ cái, Sổ chi tiết tài khoản, Bảng cân đối số phát sinh.

Tất cả số liệu đọc từ bảng ledger_entry (chỉ có chứng từ ĐÃ GHI SỔ) và opening_balance.
Mỗi dòng sổ mang voucher_id để truy ngược về chứng từ gốc.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ketoan.domain.constants import DUAL_BALANCE_PREFIXES, VOUCHER_TYPES
from ketoan.services.context import Session


def _iso(d) -> str:
    return d if isinstance(d, str) else d.isoformat()


@dataclass
class TBRow:
    code: str
    name: str
    level: int
    is_detail: bool
    ob_d: int = 0
    ob_c: int = 0
    ps_d: int = 0
    ps_c: int = 0
    cb_d: int = 0
    cb_c: int = 0

    def has_data(self) -> bool:
        return any((self.ob_d, self.ob_c, self.ps_d, self.ps_c, self.cb_d, self.cb_c))


@dataclass
class TrialBalance:
    rows: list
    total: TBRow
    balanced: dict = field(default_factory=dict)


class LedgerService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    # ----------------------------------------------------------- tiện ích
    def accounts(self):
        return self.db.query("SELECT * FROM account WHERE company_id=? ORDER BY code", (self.s.company_id,))

    def account_name(self, code: str) -> str:
        return self.db.scalar("SELECT name FROM account WHERE company_id=? AND code=?", (self.s.company_id, code), "")

    def opening_net(self, acc_prefix: str, d_from, partner_id: int | None = None) -> int:
        """Số dư (Nợ − Có) đầu ngày d_from = số dư đầu năm + phát sinh từ đầu năm đến trước d_from."""
        d_from = _iso(d_from)
        year = int(d_from[:4])
        pcond, pparams = ("AND partner_id=?", [partner_id]) if partner_id else ("", [])
        ob = self.db.scalar(f"""SELECT COALESCE(SUM(debit-credit),0) FROM opening_balance
                                WHERE company_id=? AND year=? AND account_code LIKE ? {pcond}""",
                            [self.s.company_id, year, acc_prefix + "%"] + pparams, 0)
        ps = self.db.scalar(f"""SELECT COALESCE(SUM(debit-credit),0) FROM ledger_entry
                                WHERE company_id=? AND account_code LIKE ? AND posting_date>=? AND posting_date<? {pcond}""",
                            [self.s.company_id, acc_prefix + "%", f"{year}-01-01", d_from] + pparams, 0)
        return ob + ps

    # ----------------------------------------------------------- Nhật ký chung
    def general_journal(self, d_from, d_to):
        return self.db.query("""
            SELECT e.id, e.voucher_id, e.posting_date, v.number, v.voucher_date, v.vtype, e.description,
                   e.account_code, e.contra_account, e.debit, e.credit, p.code AS partner_code, p.name AS partner_name
            FROM ledger_entry e JOIN voucher v ON v.id=e.voucher_id LEFT JOIN partner p ON p.id=e.partner_id
            WHERE e.company_id=? AND e.posting_date BETWEEN ? AND ?
            ORDER BY e.posting_date, v.number, e.voucher_id, e.line_id, e.is_tax, e.credit>0, e.id""",
                             (self.s.company_id, _iso(d_from), _iso(d_to)))

    # ----------------------------------------------------------- Sổ chi tiết / Sổ cái
    def account_detail(self, acc_prefix: str, d_from, d_to, partner_id: int | None = None):
        """Trả về dict: opening, rows (có số dư lũy kế), total_d, total_c, closing."""
        pcond, pparams = ("AND e.partner_id=?", [partner_id]) if partner_id else ("", [])
        rows = self.db.query(f"""
            SELECT e.id, e.voucher_id, e.posting_date, v.number, v.voucher_date, v.vtype, e.description,
                   e.account_code, e.contra_account, e.debit, e.credit, p.code AS partner_code, p.name AS partner_name
            FROM ledger_entry e JOIN voucher v ON v.id=e.voucher_id LEFT JOIN partner p ON p.id=e.partner_id
            WHERE e.company_id=? AND e.account_code LIKE ? AND e.posting_date BETWEEN ? AND ? {pcond}
            ORDER BY e.posting_date, v.number, e.id""",
                             [self.s.company_id, acc_prefix + "%", _iso(d_from), _iso(d_to)] + pparams)
        opening = self.opening_net(acc_prefix, d_from, partner_id)
        bal, out, td, tc = opening, [], 0, 0
        for r in rows:
            bal += r["debit"] - r["credit"]
            td += r["debit"]
            tc += r["credit"]
            d = dict(r)
            d["balance"] = bal
            out.append(d)
        return {"opening": opening, "rows": out, "total_d": td, "total_c": tc, "closing": bal}

    def general_ledger(self, acc_prefix: str, d_from, d_to):
        """Sổ cái (hình thức Nhật ký chung): phát sinh theo TK đối ứng, kèm tổng hợp đối ứng."""
        detail = self.account_detail(acc_prefix, d_from, d_to)
        by_contra = defaultdict(lambda: [0, 0])
        for r in detail["rows"]:
            by_contra[r["contra_account"] or "(nhiều TK)"][0] += r["debit"]
            by_contra[r["contra_account"] or "(nhiều TK)"][1] += r["credit"]
        detail["by_contra"] = sorted(by_contra.items())
        return detail

    def partners_of_account(self, acc_prefix: str, d_from, d_to):
        return self.db.query("""
            SELECT DISTINCT p.id, p.code, p.name FROM partner p WHERE p.company_id=? AND p.id IN (
                SELECT partner_id FROM ledger_entry WHERE company_id=? AND account_code LIKE ? AND posting_date<=?
                UNION SELECT partner_id FROM opening_balance WHERE company_id=? AND account_code LIKE ? AND year=?)
            ORDER BY p.code""", (self.s.company_id, self.s.company_id, acc_prefix + "%", _iso(d_to),
                                 self.s.company_id, acc_prefix + "%", int(_iso(d_from)[:4])))

    # ----------------------------------------------------------- Bảng cân đối số phát sinh
    def trial_balance(self, d_from, d_to, show_empty: bool = False) -> TrialBalance:
        d_from, d_to = _iso(d_from), _iso(d_to)
        year = int(d_from[:4])
        c = self.s.company_id
        # (account, partner) -> [opening_net, ps_d, ps_c]
        agg: dict[tuple, list] = defaultdict(lambda: [0, 0, 0])
        for r in self.db.query("""SELECT account_code a, partner_id p, SUM(debit-credit) n FROM opening_balance
                                  WHERE company_id=? AND year=? GROUP BY a, p""", (c, year)):
            agg[(r["a"], r["p"])][0] += r["n"]
        for r in self.db.query("""SELECT account_code a, partner_id p, SUM(debit-credit) n FROM ledger_entry
                                  WHERE company_id=? AND posting_date>=? AND posting_date<? GROUP BY a, p""",
                               (c, f"{year}-01-01", d_from)):
            agg[(r["a"], r["p"])][0] += r["n"]
        for r in self.db.query("""SELECT account_code a, partner_id p, SUM(debit) d, SUM(credit) cr FROM ledger_entry
                                  WHERE company_id=? AND posting_date BETWEEN ? AND ? GROUP BY a, p""", (c, d_from, d_to)):
            agg[(r["a"], r["p"])][1] += r["d"]
            agg[(r["a"], r["p"])][2] += r["cr"]

        accounts = {r["code"]: r for r in self.accounts()}
        leaf: dict[str, TBRow] = {}
        plain_net: dict[str, list] = defaultdict(lambda: [0, 0])     # phần bù trừ: [đầu kỳ, cuối kỳ]
        for (acc, pid), (ob, psd, psc) in agg.items():
            meta = accounts.get(acc)
            row = leaf.setdefault(acc, TBRow(acc, meta["name"] if meta else "(TK không có trong danh mục)",
                                             meta["level"] if meta else 1, True))
            cb = ob + psd - psc
            row.ps_d += psd
            row.ps_c += psc
            if acc.startswith(DUAL_BALANCE_PREFIXES) and pid is not None:
                # TK lưỡng tính chi tiết theo đối tượng: dư Nợ / dư Có trình bày riêng từng đối tượng
                row.ob_d += max(ob, 0); row.ob_c += max(-ob, 0)
                row.cb_d += max(cb, 0); row.cb_c += max(-cb, 0)
            else:
                plain_net[acc][0] += ob
                plain_net[acc][1] += cb
        for acc, (ob, cb) in plain_net.items():
            row = leaf[acc]
            row.ob_d += max(ob, 0); row.ob_c += max(-ob, 0)
            row.cb_d += max(cb, 0); row.cb_c += max(-cb, 0)

        result: dict[str, TBRow] = dict(leaf)

        def ensure(code):
            if code in result:
                return result[code]
            meta = accounts[code]
            result[code] = TBRow(code, meta["name"], meta["level"], bool(meta["is_detail"]))
            return result[code]

        for code, row in list(leaf.items()):
            parent = accounts[code]["parent_code"] if code in accounts else None
            while parent and parent in accounts:
                p = ensure(parent)
                for f in ("ob_d", "ob_c", "ps_d", "ps_c", "cb_d", "cb_c"):
                    setattr(p, f, getattr(p, f) + getattr(row, f))
                parent = accounts[parent]["parent_code"]
        if show_empty:
            for code in accounts:
                ensure(code)
        rows = sorted((r for r in result.values() if show_empty or r.has_data()), key=lambda r: r.code)
        total = TBRow("", "Tổng cộng", 0, False)
        for r in rows:
            top = accounts.get(r.code)
            if top is None or not top["parent_code"]:
                for f in ("ob_d", "ob_c", "ps_d", "ps_c", "cb_d", "cb_c"):
                    setattr(total, f, getattr(total, f) + getattr(r, f))
        balanced = {"Đầu kỳ": total.ob_d - total.ob_c, "Phát sinh": total.ps_d - total.ps_c,
                    "Cuối kỳ": total.cb_d - total.cb_c}
        return TrialBalance(rows, total, balanced)

    # ----------------------------------------------------------- tiện ích cho tổng quan
    def balance_at(self, acc_prefix: str, d_from, d_to) -> int:
        """Số dư (Nợ − Có) cuối ngày d_to, tính từ đầu năm tài chính của d_from."""
        ps = self.db.scalar("""SELECT COALESCE(SUM(debit-credit),0) FROM ledger_entry WHERE company_id=? AND account_code LIKE ?
                               AND posting_date BETWEEN ? AND ?""", (self.s.company_id, acc_prefix + "%", _iso(d_from), _iso(d_to)), 0)
        return self.opening_net(acc_prefix, d_from) + ps

    def summary(self, d_from, d_to) -> dict:
        c = self.s.company_id
        rev = self.db.scalar("""SELECT COALESCE(SUM(credit-debit),0) FROM ledger_entry WHERE company_id=? AND account_code LIKE '511%'
                                AND posting_date BETWEEN ? AND ? AND COALESCE(contra_account,'')<>'911'""", (c, _iso(d_from), _iso(d_to)), 0)
        cnt = {r["status"]: r["n"] for r in self.db.query(
            "SELECT status, COUNT(*) n FROM voucher WHERE company_id=? AND posting_date BETWEEN ? AND ? GROUP BY status",
            (c, _iso(d_from), _iso(d_to)))}
        bal = lambda p: self.balance_at(p, d_from, d_to)
        return {"cash": bal("111"), "bank": bal("112"), "receivable": bal("131"), "payable": -bal("331"),
                "revenue": rev, "counts": cnt}

    @staticmethod
    def vtype_name(code: str) -> str:
        return VOUCHER_TYPES[code].name if code in VOUCHER_TYPES else code
