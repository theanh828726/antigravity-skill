"""Quản lý công nợ phải thu (131) / phải trả (331).

- Tổng hợp theo đối tượng: dư đầu kỳ, phát sinh, dư cuối kỳ (lưỡng tính theo từng đối tượng), mã số thuế, số quá hạn.
- Chi tiết theo hóa đơn & tuổi nợ: mỗi chứng từ làm TĂNG công nợ (Nợ 131 / Có 331) là một khoản phải thu/phải trả có
  ngày hóa đơn và hạn thanh toán; các khoản làm GIẢM công nợ được PHÂN BỔ TỰ ĐỘNG THEO FIFO (khoản đến hạn sớm trả
  trước). Đây là phân bổ phục vụ theo dõi tuổi nợ, không ghi vào sổ kế toán.
- Số dư đầu năm của đối tượng được coi là một khoản nợ đến hạn ngày đầu năm.
- Phạm vi: trong năm tài chính của ngày xem (số dư đầu năm + phát sinh từ đầu năm).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from ketoan.services.context import Session

ACCOUNTS = {"131": "Phải thu khách hàng", "331": "Phải trả người bán"}
AGING_BUCKETS = [("Trong hạn", None, 0), ("Quá hạn 1–30 ngày", 1, 30), ("31–60 ngày", 31, 60), ("61–90 ngày", 61, 90),
                 ("Trên 90 ngày", 91, None)]


def _iso(d):
    return d if isinstance(d, str) else d.isoformat()


@dataclass
class DebtDoc:
    partner_id: int
    voucher_id: int | None
    number: str
    doc_date: str
    invoice: str
    due_date: str
    amount: int
    paid: int = 0

    @property
    def remaining(self) -> int:
        return self.amount - self.paid

    def overdue_days(self, as_of: str) -> int:
        return (date.fromisoformat(as_of) - date.fromisoformat(self.due_date)).days

    def bucket(self, as_of: str) -> int:
        d = self.overdue_days(as_of)
        for i, (_, lo, hi) in enumerate(AGING_BUCKETS):
            if (lo is None or d >= lo) and (hi is None or d <= hi):
                return i
        return 0


class DebtService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    def _sign(self, acc: str) -> int:
        """+1: công nợ tăng bên Nợ (phải thu); -1: công nợ tăng bên Có (phải trả)."""
        return 1 if acc.startswith("131") else -1

    # ------------------------------------------------------------ tổng hợp
    def summary(self, acc: str, d_from, d_to) -> list[dict]:
        d_from, d_to = _iso(d_from), _iso(d_to)
        year = int(d_from[:4])
        c = self.s.company_id
        agg: dict[int, dict] = defaultdict(lambda: {"ob": 0, "ps_d": 0, "ps_c": 0})
        for r in self.db.query("""SELECT partner_id p, SUM(debit-credit) n FROM opening_balance WHERE company_id=? AND year=?
                                  AND account_code LIKE ? AND partner_id IS NOT NULL GROUP BY p""", (c, year, acc + "%")):
            agg[r["p"]]["ob"] += r["n"]
        for r in self.db.query("""SELECT partner_id p, SUM(debit-credit) n FROM ledger_entry WHERE company_id=? AND
                                  account_code LIKE ? AND posting_date>=? AND posting_date<? AND partner_id IS NOT NULL
                                  GROUP BY p""", (c, acc + "%", f"{year}-01-01", d_from)):
            agg[r["p"]]["ob"] += r["n"]
        for r in self.db.query("""SELECT partner_id p, SUM(debit) d, SUM(credit) cr FROM ledger_entry WHERE company_id=? AND
                                  account_code LIKE ? AND posting_date BETWEEN ? AND ? AND partner_id IS NOT NULL
                                  GROUP BY p""", (c, acc + "%", d_from, d_to)):
            agg[r["p"]]["ps_d"] += r["d"]
            agg[r["p"]]["ps_c"] += r["cr"]
        partners = {r["id"]: r for r in self.db.query("SELECT * FROM partner WHERE company_id=?", (c,))}
        overdue = defaultdict(int)
        for doc in self.documents(acc, d_to):
            if doc.remaining > 0 and doc.overdue_days(d_to) > 0:
                overdue[doc.partner_id] += doc.remaining
        out = []
        for pid, a in agg.items():
            p = partners.get(pid)
            cb = a["ob"] + a["ps_d"] - a["ps_c"]
            if not any((a["ob"], a["ps_d"], a["ps_c"])):
                continue
            out.append({"partner_id": pid, "code": p["code"] if p else "?", "name": p["name"] if p else "",
                        "tax_code": p["tax_code"] if p else "", "ob_d": max(a["ob"], 0), "ob_c": max(-a["ob"], 0),
                        "ps_d": a["ps_d"], "ps_c": a["ps_c"], "cb_d": max(cb, 0), "cb_c": max(-cb, 0),
                        "overdue": overdue.get(pid, 0)})
        return sorted(out, key=lambda r: r["code"])

    # ------------------------------------------------------------ chứng từ công nợ & tuổi nợ
    def documents(self, acc: str, as_of, partner_id: int | None = None) -> list[DebtDoc]:
        as_of = _iso(as_of)
        year = int(as_of[:4])
        c, sign = self.s.company_id, self._sign(acc)
        pcond, pp = ("AND partner_id=?", [partner_id]) if partner_id else ("", [])
        docs: dict[int, list[DebtDoc]] = defaultdict(list)
        for r in self.db.query(f"""SELECT partner_id p, SUM(debit-credit) n FROM opening_balance WHERE company_id=? AND year=?
                                   AND account_code LIKE ? AND partner_id IS NOT NULL {pcond} GROUP BY p""",
                               [c, year, acc + "%"] + pp):
            amt = r["n"] * sign
            if amt > 0:
                docs[r["p"]].append(DebtDoc(r["p"], None, "Số dư đầu năm", f"{year}-01-01", "", f"{year}-01-01", amt))
            elif amt < 0:
                docs.setdefault(r["p"], [])
                docs[r["p"]].append(DebtDoc(r["p"], None, "Trả trước đầu năm", f"{year}-01-01", "", f"{year}-01-01", amt))
        rows = self.db.query(f"""
            SELECT e.partner_id p, e.voucher_id, v.number, v.posting_date, v.invoice_no, v.invoice_series, v.invoice_date,
                   v.due_date, SUM(e.debit-e.credit) n
            FROM ledger_entry e JOIN voucher v ON v.id=e.voucher_id
            WHERE e.company_id=? AND e.account_code LIKE ? AND e.posting_date BETWEEN ? AND ? AND e.partner_id IS NOT NULL
            {pcond.replace('partner_id', 'e.partner_id')}
            GROUP BY e.partner_id, e.voucher_id ORDER BY v.posting_date, e.voucher_id""",
                             [c, acc + "%", f"{year}-01-01", as_of] + pp)
        payments: dict[int, int] = defaultdict(int)
        for r in rows:
            amt = r["n"] * sign
            if amt > 0:
                base = r["invoice_date"] or r["posting_date"]
                inv = f"{r['invoice_series'] or ''} {r['invoice_no'] or ''}".strip()
                docs[r["p"]].append(DebtDoc(r["p"], r["voucher_id"], r["number"], base, inv, r["due_date"] or base, amt))
            elif amt < 0:
                payments[r["p"]] += -amt
        out = []
        for pid in set(docs) | set(payments):
            pos = sorted([d for d in docs.get(pid, []) if d.amount > 0], key=lambda d: (d.due_date, d.doc_date, d.number))
            neg = [d for d in docs.get(pid, []) if d.amount < 0]
            pay = payments.get(pid, 0) + sum(-d.amount for d in neg)
            for d in pos:                         # phân bổ FIFO theo hạn thanh toán
                use = min(pay, d.amount)
                d.paid = use
                pay -= use
            out.extend(pos)
            if pay > 0:                           # trả thừa / ứng trước chưa có hóa đơn đối ứng
                out.append(DebtDoc(pid, None, "Ứng trước / trả thừa", as_of, "", as_of, -pay))
        return out

    def aging(self, acc: str, as_of, partner_id: int | None = None) -> list[dict]:
        as_of = _iso(as_of)
        partners = {r["id"]: r for r in self.db.query("SELECT * FROM partner WHERE company_id=?", (self.s.company_id,))}
        rows = []
        for d in self.documents(acc, as_of, partner_id):
            if d.remaining == 0:
                continue
            p = partners.get(d.partner_id)
            rows.append({"doc": d, "partner_code": p["code"] if p else "?", "partner_name": p["name"] if p else "",
                         "tax_code": p["tax_code"] if p else "",
                         "days": d.overdue_days(as_of) if d.remaining > 0 else 0,
                         "bucket": d.bucket(as_of) if d.remaining > 0 else 0})
        return sorted(rows, key=lambda r: (r["partner_code"], r["doc"].due_date))

    def aging_totals(self, acc: str, as_of) -> list[dict]:
        per: dict[int, dict] = {}
        for r in self.aging(acc, as_of):
            d = r["doc"]
            t = per.setdefault(d.partner_id, {"partner_code": r["partner_code"], "partner_name": r["partner_name"],
                                              "buckets": [0] * len(AGING_BUCKETS), "advance": 0, "total": 0})
            if d.remaining > 0:
                t["buckets"][r["bucket"]] += d.remaining
            else:
                t["advance"] += -d.remaining
            t["total"] += d.remaining
        return sorted(per.values(), key=lambda t: t["partner_code"])

    # ------------------------------------------------------------ biên bản đối chiếu
    def statement(self, acc: str, partner_id: int, d_from, d_to) -> dict:
        from ketoan.services.ledger_service import LedgerService
        detail = LedgerService(self.s).account_detail(acc, d_from, d_to, partner_id)
        p = self.db.one("SELECT * FROM partner WHERE id=?", (partner_id,))
        return {"partner": p, "detail": detail}
