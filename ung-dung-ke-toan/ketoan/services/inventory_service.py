"""Kho: tồn đầu kỳ, nhập – xuất – tồn, thẻ kho, tính giá xuất kho.

Nguồn số liệu: bút toán ĐÃ GHI SỔ trên TK hàng tồn kho (152, 153, 155, 156) có mã hàng.
    Nợ TK kho  => nhập (số lượng, giá trị = số tiền Nợ)
    Có TK kho  => xuất (số lượng, giá trị = số tiền Có)
Theo dõi theo cặp (mã hàng, kho). Chứng từ nháp chưa tham gia tính tồn và tính giá.

PHẠM VI TÍNH GIÁ XUẤT KHO (giai đoạn 2):
  • BQCK – Bình quân gia quyền cuối kỳ theo THÁNG, theo từng mã hàng + kho:
        Đơn giá = (Giá trị tồn đầu tháng + Giá trị nhập trong tháng) / (SL tồn đầu tháng + SL nhập trong tháng)
  • FIFO – Nhập trước, xuất trước theo từng mã hàng + kho, xét theo ngày hạch toán (cùng ngày: nhập trước xuất).
  • Chỉ cập nhật dòng XUẤT đã ghi sổ trên chứng từ không có thuế GTGT tự sinh; kỳ phải chưa khóa;
    kỳ tính phải trọn tháng (từ ngày 01 đến ngày cuối tháng).
  • Chưa hỗ trợ: chuyển kho nội bộ (dòng Nợ và Có cùng là TK kho – được giữ nguyên và cảnh báo), bình quân tức thời,
    đích danh, hàng gửi bán (157), giá thành nhập kho thành phẩm (giai đoạn 3).
  • Làm tròn: đơn giá 4 chữ số thập phân; thành tiền làm tròn đồng; khi tồn cuối tháng về 0, dòng xuất cuối cùng
    nhận phần chênh lệch làm tròn để giá trị tồn bằng 0.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ketoan.domain.constants import INVENTORY_PREFIXES, VOUCHER_TYPES
from ketoan.domain.money import ZERO, round_money, round_price, to_decimal, dec_to_str
from ketoan.services.context import BusinessError, Session
from ketoan.services.period_service import PeriodService

METHODS = {
    "BQCK": "Bình quân gia quyền cuối kỳ (tháng)",
    "FIFO": "Nhập trước – xuất trước (FIFO)",
}
_ACC_COND = "(" + " OR ".join(f"e.account_code LIKE '{p}%'" for p in INVENTORY_PREFIXES) + ")"


def _iso(d):
    return d if isinstance(d, str) else d.isoformat()


@dataclass
class StockRow:
    item_id: int
    warehouse_id: int
    item_code: str = ""
    item_name: str = ""
    unit: str = ""
    warehouse_code: str = ""
    ob_q: object = ZERO
    ob_v: int = 0
    in_q: object = ZERO
    in_v: int = 0
    out_q: object = ZERO
    out_v: int = 0

    @property
    def cb_q(self):
        return self.ob_q + self.in_q - self.out_q

    @property
    def cb_v(self):
        return self.ob_v + self.in_v - self.out_v


@dataclass
class CostingResult:
    method: str
    d_from: str
    d_to: str
    rows: list = field(default_factory=list)        # dict cho mỗi (hàng, kho)
    changes: list = field(default_factory=list)     # (line_id, unit_price, amount, old_amount, voucher_number)
    warnings: list = field(default_factory=list)

    @property
    def total_change(self) -> int:
        return sum(c[2] - c[3] for c in self.changes)


class InventoryService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    # ------------------------------------------------------------ dữ liệu nền
    def _names(self):
        items = {r["id"]: r for r in self.db.query("SELECT id, code, name, unit, stock_account FROM item WHERE company_id=?",
                                                   (self.s.company_id,))}
        whs = {r["id"]: r for r in self.db.query("SELECT id, code, name FROM warehouse WHERE company_id=?",
                                                 (self.s.company_id,))}
        return items, whs

    def movements(self, d_from: str | None, d_to: str, item_id=None, warehouse_id=None):
        cond, params = ["e.company_id=?", "e.item_id IS NOT NULL", "e.is_tax=0", _ACC_COND, "e.posting_date<=?"], \
            [self.s.company_id, _iso(d_to)]
        if d_from:
            cond.append("e.posting_date>=?")
            params.append(_iso(d_from))
        if item_id:
            cond.append("e.item_id=?")
            params.append(item_id)
        if warehouse_id:
            cond.append("e.warehouse_id=?")
            params.append(warehouse_id)
        rows = self.db.query(f"""
            SELECT e.id, e.voucher_id, e.line_id, e.posting_date, e.item_id, e.warehouse_id, e.quantity, e.debit, e.credit, e.side,
                   e.account_code, e.contra_account, e.description, v.number, v.vtype, v.voucher_date
            FROM ledger_entry e JOIN voucher v ON v.id=e.voucher_id
            WHERE {' AND '.join(cond)}
            ORDER BY e.posting_date, (e.side='C'), e.id""", params)
        return [{**dict(r), "is_in": r["side"] == "D"} for r in rows]

    def opening(self, d_from, item_id=None, warehouse_id=None) -> dict:
        """Tồn đầu ngày d_from theo (hàng, kho): {key: [qty, value]}."""
        d_from = _iso(d_from)
        year = int(d_from[:4])
        res: dict[tuple, list] = defaultdict(lambda: [ZERO, 0])
        cond, params = "", []
        if item_id:
            cond += " AND item_id=?"; params.append(item_id)
        if warehouse_id:
            cond += " AND warehouse_id=?"; params.append(warehouse_id)
        for r in self.db.query(f"SELECT * FROM opening_stock WHERE company_id=? AND year=? {cond}",
                               [self.s.company_id, year] + params):
            k = (r["item_id"], r["warehouse_id"])
            res[k][0] += to_decimal(r["quantity"])
            res[k][1] += r["amount"]
        start = f"{year}-01-01"
        if d_from > start:
            prev = (date.fromisoformat(d_from) - timedelta(days=1)).isoformat()
            for m in self.movements(start, prev, item_id, warehouse_id):
                k = (m["item_id"], m["warehouse_id"])
                q = to_decimal(m["quantity"])
                if m["is_in"]:
                    res[k][0] += q; res[k][1] += m["debit"]
                else:
                    res[k][0] -= q; res[k][1] -= m["credit"]
        return res

    # ------------------------------------------------------------ nhập – xuất – tồn
    def nxt(self, d_from, d_to, warehouse_id=None, search: str = "") -> list[StockRow]:
        items, whs = self._names()
        rows: dict[tuple, StockRow] = {}

        def row(k):
            if k not in rows:
                it, wh = items.get(k[0]), whs.get(k[1])
                rows[k] = StockRow(k[0], k[1], it["code"] if it else "?", it["name"] if it else "", it["unit"] if it else "",
                                   wh["code"] if wh else "(chưa chọn kho)")
            return rows[k]

        for k, (q, v) in self.opening(d_from, warehouse_id=warehouse_id).items():
            r = row(k); r.ob_q, r.ob_v = q, v
        for m in self.movements(d_from, d_to, warehouse_id=warehouse_id):
            r = row((m["item_id"], m["warehouse_id"]))
            q = to_decimal(m["quantity"])
            if m["is_in"]:
                r.in_q += q; r.in_v += m["debit"]
            else:
                r.out_q += q; r.out_v += m["credit"]
        out = [r for r in rows.values() if any((r.ob_q, r.ob_v, r.in_q, r.in_v, r.out_q, r.out_v))]
        if search:
            t = search.lower()
            out = [r for r in out if t in r.item_code.lower() or t in r.item_name.lower()]
        return sorted(out, key=lambda r: (r.item_code, r.warehouse_code))

    def stock_card(self, item_id: int, warehouse_id, d_from, d_to) -> dict:
        op = self.opening(d_from, item_id, warehouse_id)
        oq = sum((v[0] for v in op.values()), ZERO)
        ov = sum(v[1] for v in op.values())
        q, val, rows = oq, ov, []
        for m in self.movements(d_from, d_to, item_id, warehouse_id):
            mq = to_decimal(m["quantity"])
            if m["is_in"]:
                q += mq; val += m["debit"]
            else:
                q -= mq; val -= m["credit"]
            d = dict(m)
            d.update(in_q=mq if m["is_in"] else ZERO, out_q=ZERO if m["is_in"] else mq, bal_q=q, bal_v=val)
            rows.append(d)
        return {"opening_q": oq, "opening_v": ov, "rows": rows, "closing_q": q, "closing_v": val}

    def average_cost(self, item_id: int, warehouse_id, on_date) -> object:
        """Đơn giá bình quân tạm tính đến hết ngày on_date (dùng làm giá tạm khi lập phiếu xuất)."""
        nxt_day = (date.fromisoformat(_iso(on_date)) + timedelta(days=1)).isoformat()
        op = self.opening(nxt_day, item_id, warehouse_id)
        q = sum((v[0] for v in op.values()), ZERO)
        v = sum(x[1] for x in op.values())
        if q > 0 and v > 0:
            return round_price(to_decimal(v) / q)
        last = self.db.one(f"""SELECT e.debit, e.quantity FROM ledger_entry e WHERE e.company_id=? AND e.item_id=?
                               AND e.debit>0 AND e.is_tax=0 AND {_ACC_COND} AND e.posting_date<=?
                               ORDER BY e.posting_date DESC, e.id DESC LIMIT 1""", (self.s.company_id, item_id, _iso(on_date)))
        if last and to_decimal(last["quantity"]):
            return round_price(to_decimal(last["debit"]) / to_decimal(last["quantity"]))
        return ZERO

    # ------------------------------------------------------------ tồn kho đầu kỳ
    def opening_rows(self, year: int):
        return self.db.query("""SELECT os.*, i.code item_code, i.name item_name, i.unit, i.stock_account, w.code wh_code
                                FROM opening_stock os JOIN item i ON i.id=os.item_id JOIN warehouse w ON w.id=os.warehouse_id
                                WHERE os.company_id=? AND os.year=? ORDER BY i.code, w.code""", (self.s.company_id, year))

    def opening_vs_ledger(self, year: int) -> list[tuple]:
        """Đối chiếu tổng giá trị tồn kho đầu kỳ theo TK kho với số dư đầu năm của TK đó: [(TK, kho, sổ, chênh lệch)]."""
        stock = defaultdict(int)
        for r in self.opening_rows(year):
            stock[r["stock_account"] or "156"] += r["amount"]
        ob = {r["a"]: r["n"] for r in self.db.query(f"""SELECT account_code a, SUM(debit-credit) n FROM opening_balance
                  WHERE company_id=? AND year=? AND ({' OR '.join(f"account_code LIKE '{p}%'" for p in INVENTORY_PREFIXES)})
                  GROUP BY account_code""", (self.s.company_id, year))}
        out = []
        for acc in sorted(set(stock) | set(ob)):
            out.append((acc, stock.get(acc, 0), ob.get(acc, 0), stock.get(acc, 0) - ob.get(acc, 0)))
        return out

    def save_opening(self, year: int, rows: list[dict]):
        self.s.require("edit", "nhập tồn kho đầu kỳ")
        if PeriodService(self.s).is_locked(f"{year}-01-01"):
            raise BusinessError(f"Tháng 01/{year} đã khóa – không thể sửa tồn kho đầu kỳ.")
        errors, clean, seen = [], [], set()
        for i, r in enumerate(rows, 1):
            ic, wc = (r.get("item_code") or "").strip(), (r.get("warehouse_code") or "").strip()
            if not ic and not wc and not r.get("quantity") and not r.get("amount"):
                continue
            iid = self.db.scalar("SELECT id FROM item WHERE company_id=? AND code=?", (self.s.company_id, ic))
            wid = self.db.scalar("SELECT id FROM warehouse WHERE company_id=? AND code=?", (self.s.company_id, wc))
            if not iid:
                errors.append(f"Dòng {i}: mã hàng '{ic}' không tồn tại")
            if not wid:
                errors.append(f"Dòng {i}: kho '{wc}' không tồn tại")
            try:
                q, v = to_decimal(r.get("quantity")), round_money(r.get("amount"))
            except ValueError as e:
                errors.append(f"Dòng {i}: {e}")
                continue
            if q < 0 or v < 0:
                errors.append(f"Dòng {i}: số lượng / giá trị không được âm")
            if q == 0 and v != 0:
                errors.append(f"Dòng {i}: có giá trị nhưng số lượng bằng 0")
            if (iid, wid) in seen:
                errors.append(f"Dòng {i}: trùng mã hàng + kho")
            seen.add((iid, wid))
            clean.append((iid, wid, dec_to_str(q), v))
        if errors:
            raise BusinessError("\n".join(errors))
        with self.db.transaction():
            self.db.execute("DELETE FROM opening_stock WHERE company_id=? AND year=?", (self.s.company_id, year))
            self.db.executemany("INSERT INTO opening_stock(company_id, year, item_id, warehouse_id, quantity, amount) "
                                "VALUES(?,?,?,?,?,?)", [(self.s.company_id, year, *c) for c in clean])
            self.s.audit("Cập nhật tồn kho đầu kỳ", "opening_stock", year,
                         {"so_dong": len(clean), "tong_gia_tri": sum(c[3] for c in clean)})

    # ------------------------------------------------------------ tính giá xuất kho
    def method(self) -> str:
        return self.db.scalar("SELECT costing_method FROM company WHERE id=?", (self.s.company_id,), "BQCK")

    def set_method(self, method: str):
        self.s.require("admin", "đổi phương pháp tính giá xuất kho")
        if method not in METHODS:
            raise BusinessError("Phương pháp không hợp lệ.")
        with self.db.transaction():
            self.db.execute("UPDATE company SET costing_method=? WHERE id=?", (method, self.s.company_id))
            self.s.audit("Đổi phương pháp tính giá xuất kho", "company", self.s.company_id, {"phuong_phap": method})

    def _check_period(self, d_from: str, d_to: str):
        a, b = date.fromisoformat(d_from), date.fromisoformat(d_to)
        last = (date(b.year + (b.month == 12), b.month % 12 + 1, 1) - timedelta(days=1))
        if a.day != 1 or b != last or a > b:
            raise BusinessError("Tính giá xuất kho theo tháng: chọn kỳ từ ngày 01 đến ngày cuối tháng (một hoặc nhiều tháng).")
        if a.year != b.year:
            raise BusinessError("Kỳ tính giá phải nằm trong một năm tài chính.")
        ps = PeriodService(self.s)
        locked = [m for m in range(a.month, b.month + 1) if ps.is_locked(f"{a.year}-{m:02d}-01")]
        if locked:
            raise BusinessError("Kỳ tính giá có tháng đã khóa: " + ", ".join(f"{m:02d}/{a.year}" for m in locked))

    def costing_preview(self, d_from: str, d_to: str, method: str | None = None) -> CostingResult:
        d_from, d_to = _iso(d_from), _iso(d_to)
        self._check_period(d_from, d_to)
        method = method or self.method()
        res = CostingResult(method, d_from, d_to)
        items, whs = self._names()
        opening = self.opening(d_from)
        events: dict[tuple, list] = defaultdict(list)
        skip_types = {c for c, vt in VOUCHER_TYPES.items() if vt.tax_account}
        for m in self.movements(d_from, d_to):
            k = (m["item_id"], m["warehouse_id"])
            events[k].append(m)
        for k in sorted(set(events) | {k for k, v in opening.items() if v[0] or v[1]},
                        key=lambda k: (items[k[0]]["code"] if k[0] in items else "", whs[k[1]]["code"] if k[1] in whs else "")):
            ob_q, ob_v = opening.get(k, [ZERO, 0])
            label = f"{items[k[0]]['code'] if k[0] in items else '?'} / {whs[k[1]]['code'] if k[1] in whs else '(chưa chọn kho)'}"
            evs = events.get(k, [])
            ins = [e for e in evs if e["is_in"]]
            outs = []
            for e in evs:
                if e["is_in"]:
                    continue
                if e["contra_account"] and e["contra_account"].startswith(INVENTORY_PREFIXES):
                    res.warnings.append(f"{label}: {e['number']} là chuyển kho/điều chỉnh nội bộ TK kho – giữ nguyên giá trị.")
                    continue
                if e["vtype"] in skip_types:
                    res.warnings.append(f"{label}: {e['number']} ({VOUCHER_TYPES[e['vtype']].name}) – không cập nhật dòng "
                                        "xuất trên chứng từ có thuế tự sinh.")
                    continue
                outs.append(e)
            out_ids = {e["id"] for e in outs}
            fixed_out = [e for e in evs if not e["is_in"] and e["id"] not in out_ids]
            new_amounts = (self._bqck if method == "BQCK" else self._fifo)(k, label, ob_q, ob_v, ins, outs, fixed_out, res)
            in_q = sum((to_decimal(e["quantity"]) for e in ins), ZERO)
            in_v = sum(e["debit"] for e in ins)
            out_q = sum((to_decimal(e["quantity"]) for e in evs if not e["is_in"]), ZERO)
            old_out_v = sum(e["credit"] for e in evs if not e["is_in"])
            new_out_v = sum(new_amounts.get(e["id"], e["credit"]) for e in evs if not e["is_in"])
            for e in outs:
                amt = new_amounts.get(e["id"], e["credit"])
                q = to_decimal(e["quantity"])
                price = round_price(to_decimal(amt) / q) if q else ZERO
                if amt != e["credit"]:
                    res.changes.append((e["line_id"], price, amt, e["credit"], e["number"]))
            res.rows.append({"key": k, "item_code": items[k[0]]["code"] if k[0] in items else "?",
                             "item_name": items[k[0]]["name"] if k[0] in items else "", "unit": items[k[0]]["unit"] if k[0] in items else "",
                             "warehouse": whs[k[1]]["code"] if k[1] in whs else "", "ob_q": ob_q, "ob_v": ob_v,
                             "in_q": in_q, "in_v": in_v, "out_q": out_q, "old_out_v": old_out_v, "new_out_v": new_out_v,
                             "cb_q": ob_q + in_q - out_q, "cb_v": ob_v + in_v - new_out_v})
        return res

    @staticmethod
    def _months(evs):
        by = defaultdict(list)
        for e in evs:
            by[e["posting_date"][:7]].append(e)
        return by

    def _bqck(self, k, label, ob_q, ob_v, ins, outs, fixed_out, res) -> dict:
        new = {}
        q, v = ob_q, ob_v
        months = sorted(set(self._months(ins)) | set(self._months(outs)) | set(self._months(fixed_out)))
        ins_m, outs_m, fixed_m = self._months(ins), self._months(outs), self._months(fixed_out)
        last_unit = None
        for ym in months:
            in_q = sum((to_decimal(e["quantity"]) for e in ins_m.get(ym, [])), ZERO)
            in_v = sum(e["debit"] for e in ins_m.get(ym, []))
            base_q, base_v = q + in_q, v + in_v
            if base_q > 0:
                unit = to_decimal(base_v) / base_q
                last_unit = unit
            elif last_unit is not None:
                unit = last_unit
                res.warnings.append(f"{label} tháng {ym[5:]}/{ym[:4]}: không có tồn và nhập dương – dùng đơn giá kỳ trước.")
            else:
                unit = None
                if outs_m.get(ym):
                    res.warnings.append(f"{label} tháng {ym[5:]}/{ym[:4]}: không xác định được đơn giá (không có tồn, "
                                        "không có nhập) – giữ nguyên giá xuất đang ghi.")
            month_outs = outs_m.get(ym, [])
            out_v = 0
            for e in month_outs:
                qq = to_decimal(e["quantity"])
                amt = round_money(qq * unit) if unit is not None else e["credit"]
                new[e["id"]] = amt
                out_v += amt
            fixed_v = sum(e["credit"] for e in fixed_m.get(ym, []))
            fixed_q = sum((to_decimal(e["quantity"]) for e in fixed_m.get(ym, [])), ZERO)
            out_q = sum((to_decimal(e["quantity"]) for e in month_outs), ZERO)
            q = base_q - out_q - fixed_q
            v = base_v - out_v - fixed_v
            if q == 0 and v != 0 and month_outs and unit is not None:
                last = month_outs[-1]
                new[last["id"]] += v            # dồn chênh lệch làm tròn vào dòng xuất cuối tháng
                v = 0
            if q < 0:
                res.warnings.append(f"{label}: tồn cuối tháng {ym[5:]}/{ym[:4]} âm {q.normalize()} – kiểm tra chứng từ nhập/xuất.")
        return new

    def _fifo(self, k, label, ob_q, ob_v, ins, outs, fixed_out, res) -> dict:
        new = {}
        layers: list[list] = [[ob_q, ob_v]] if ob_q > 0 else []
        events = sorted(ins + outs + fixed_out, key=lambda e: (e["posting_date"], 0 if e["is_in"] else 1, e["id"]))
        out_ids = {e["id"] for e in outs}
        last_unit = (to_decimal(ob_v) / ob_q) if ob_q > 0 else None
        for e in events:
            qq = to_decimal(e["quantity"])
            if e["is_in"]:
                layers.append([qq, e["debit"]])
                if qq:
                    last_unit = to_decimal(e["debit"]) / qq
                continue
            need, value = qq, 0
            while need > 0 and layers:
                lq, lv = layers[0]
                take = min(need, lq)
                tv = lv if take == lq else round_money(to_decimal(lv) * take / lq)
                value += tv
                layers[0] = [lq - take, lv - tv]
                if layers[0][0] <= 0:
                    layers.pop(0)
                need -= take
            if need > 0:
                if last_unit is None:
                    res.warnings.append(f"{label}: {e['number']} xuất vượt tồn, không có giá tham chiếu – giữ nguyên giá.")
                    value += round_money(to_decimal(e["credit"]) * need / qq) if qq else 0
                else:
                    res.warnings.append(f"{label}: {e['number']} xuất vượt tồn {need.normalize()} – tạm tính theo đơn giá nhập gần nhất.")
                    value += round_money(need * last_unit)
            if e["id"] in out_ids:
                new[e["id"]] = value
            else:
                # dòng giữ nguyên giá trị (chuyển kho...): lớp tồn đã trừ theo FIFO, chênh lệch không ghi đè
                pass
        return new

    def costing_apply(self, d_from: str, d_to: str, method: str | None = None) -> CostingResult:
        self.s.require("post", "tính giá xuất kho")
        from ketoan.services.voucher_service import VoucherService
        with self.db.transaction():
            res = self.costing_preview(d_from, d_to, method)
            VoucherService(self.s).update_line_prices([(c[0], c[1], c[2]) for c in res.changes])
            self.db.execute("""INSERT INTO costing_run(company_id, d_from, d_to, method, run_by, run_at, lines_updated, total_change,
                               detail) VALUES(?,?,?,?,?,?,?,?,?)""",
                            (self.s.company_id, d_from, d_to, res.method, self.s.user.username,
                             datetime.now().isoformat(timespec="seconds"), len(res.changes), res.total_change,
                             json.dumps(res.warnings, ensure_ascii=False)))
            self.s.audit("Tính giá xuất kho", "costing_run", f"{d_from}..{d_to}",
                         {"phuong_phap": res.method, "so_dong": len(res.changes), "chenh_lech": res.total_change})
        return res

    def costing_history(self, limit: int = 20):
        return self.db.query("SELECT * FROM costing_run WHERE company_id=? ORDER BY id DESC LIMIT ?",
                             (self.s.company_id, limit))
