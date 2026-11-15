"""Tài sản cố định (khấu hao đường thẳng) và công cụ dụng cụ / chi phí trả trước (phân bổ đều theo tháng).

QUY ƯỚC (cấu hình chính sách – người dùng chịu trách nhiệm lựa chọn phù hợp chế độ áp dụng):
  • Khấu hao / phân bổ ĐƯỜNG THẲNG: mức tháng = Nguyên giá (hoặc Tổng giá trị) / Số tháng, làm tròn đồng.
  • Bắt đầu tính từ THÁNG của «Ngày bắt đầu»; tháng cuối nhận phần còn lại để tổng đúng bằng nguyên giá (không vượt).
  • TSCĐ đã ghi giảm (thanh lý) ngừng khấu hao từ tháng sau tháng ghi giảm.
  • Số tính đến đầu kỳ chạy = «Đã khấu hao / phân bổ đầu kỳ» (nhập) + các lần chạy trong phần mềm.
  • Phải chạy tuần tự từng tháng (trừ tháng 1); mỗi tháng chỉ chạy một lần; hoàn tác khi kỳ chưa khóa.
  • Không tự quyết thời gian sử dụng hữu ích, tỷ lệ khấu hao hay điều kiện ghi nhận TSCĐ theo quy định – các giá trị này do
    người dùng nhập và cần đối chiếu quy định hiện hành.
Mỗi lần chạy sinh MỘT chứng từ «Nghiệp vụ hạch toán» (Nợ TK chi phí / Có TK hao mòn hoặc TK nguồn) liên kết với lần chạy.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime

from ketoan.domain.money import round_money
from ketoan.services.context import BusinessError, Session
from ketoan.services.period_service import PeriodService
from ketoan.services.voucher_service import VoucherService

KIND_ASSET, KIND_PREPAID = "ASSET", "PREPAID"
PREPAID_KINDS = [("CCDC", "Công cụ dụng cụ"), ("CPTT", "Chi phí trả trước")]


@dataclass
class RunRow:
    ref_id: int
    code: str
    name: str
    base: int            # nguyên giá / tổng giá trị
    done_before: int     # đã khấu hao / phân bổ trước tháng chạy
    amount: int          # số tháng này
    remaining_after: int
    debit_account: str
    credit_account: str
    department: str | None


def _month_end(y, m) -> str:
    return date(y, m, monthrange(y, m)[1]).isoformat()


def _monthly(base: int, months: int) -> int:
    return round_money(base / months) if months else 0


def _amount_for(base: int, months: int, done: int, start_date: str, year: int, month: int) -> int:
    """Số khấu hao / phân bổ của tháng: mức đều; tháng cuối (đủ số tháng) nhận toàn bộ phần còn lại."""
    remain = base - done
    if remain <= 0 or not months:
        return 0
    idx = (year * 12 + month) - (int(start_date[:4]) * 12 + int(start_date[5:7])) + 1
    return remain if idx >= months else min(remain, _monthly(base, months))


class _RunMixin:
    kind = ""

    def __init__(self, session: Session):
        self.s = session
        self.db = session.db
        self.periods = PeriodService(session)

    # ----------------------------------------------------------- lịch sử chạy
    def runs(self, year: int | None = None):
        cond, params = "", [self.s.company_id, self.kind]
        if year:
            cond, params = " AND year=?", params + [year]
        return self.db.query(f"""SELECT r.*, v.number, v.status FROM period_run r LEFT JOIN voucher v ON v.id=r.voucher_id
                                 WHERE r.company_id=? AND r.kind=?{cond} ORDER BY r.year DESC, r.month DESC""", params)

    def _done_before(self, ref_id: int, year: int, month: int) -> int:
        return self.db.scalar("""SELECT COALESCE(SUM(l.amount),0) FROM period_run_line l JOIN period_run r ON r.id=l.run_id
                                 WHERE r.company_id=? AND r.kind=? AND l.ref_id=? AND (r.year*100+r.month) < ?""",
                              (self.s.company_id, self.kind, ref_id, year * 100 + month), 0)

    def _check_run(self, year: int, month: int):
        if not 1 <= month <= 12:
            raise BusinessError("Tháng không hợp lệ.")
        if self.db.scalar("SELECT 1 FROM period_run WHERE company_id=? AND kind=? AND year=? AND month=?",
                          (self.s.company_id, self.kind, year, month)):
            raise BusinessError(f"Tháng {month:02d}/{year} đã chạy. Hoàn tác trước nếu cần chạy lại.")
        for k in range(1, month):        # phải chạy tuần tự; tháng chưa có khoản nào phát sinh thì được bỏ qua
            if not self.db.scalar("SELECT 1 FROM period_run WHERE company_id=? AND kind=? AND year=? AND month=?",
                                  (self.s.company_id, self.kind, year, k)) and any(r.amount for r in self.preview(year, k)):
                raise BusinessError(f"Chưa chạy tháng {k:02d}/{year} – phải chạy tuần tự từng tháng.")
        if self.periods.is_locked(f"{year}-{month:02d}-01"):
            raise BusinessError(f"Tháng {month:02d}/{year} đã khóa.")

    def preview(self, year: int, month: int) -> list[RunRow]:
        raise NotImplementedError

    def _description(self, year, month) -> str:
        raise NotImplementedError

    def apply(self, year: int, month: int, post: bool = False) -> int:
        self.s.require("add", "tính khấu hao / phân bổ")
        if post:
            self.s.require("post", "ghi sổ chứng từ khấu hao / phân bổ")
        with self.db.transaction():
            self.db.advisory_lock(f"period-run:{self.s.company_id}:{self.kind}")      # tuần tự giữa nhiều người dùng
            self._check_run(year, month)
            rows = [r for r in self.preview(year, month) if r.amount]
            if not rows:
                raise BusinessError(f"Không có khoản nào phát sinh trong tháng {month:02d}/{year}.")
            last = _month_end(year, month)
            dept_ok = {r["code"] for r in self.db.query("SELECT code FROM department WHERE company_id=?", (self.s.company_id,))}
            lines = [{"description": f"{r.name} ({r.code})", "debit_account": r.debit_account, "credit_account": r.credit_account,
                      "amount": r.amount, "department": r.department if r.department in dept_ok else None} for r in rows]
            vs = VoucherService(self.s)
            vid = vs.save({"vtype": "PKT", "voucher_date": last, "posting_date": last,
                           "description": self._description(year, month)}, lines)
            if post:
                vs.post(vid)
            cur = self.db.execute("""INSERT INTO period_run(company_id, kind, year, month, voucher_id, total, run_by, run_at)
                                     VALUES(?,?,?,?,?,?,?,?)""",
                                  (self.s.company_id, self.kind, year, month, vid, sum(r.amount for r in rows),
                                   self.s.user.username, datetime.now().isoformat(timespec="seconds")))
            self.db.executemany("INSERT INTO period_run_line(run_id, ref_id, amount) VALUES(?,?,?)",
                                [(cur.lastrowid, r.ref_id, r.amount) for r in rows])
            self.s.audit(self._description(year, month), "period_run", f"{month:02d}/{year}",
                         {"so_dong": len(rows), "tong": sum(r.amount for r in rows), "ghi_so": post})
        return vid

    def undo(self, year: int, month: int):
        self.s.require("post", "hoàn tác khấu hao / phân bổ")
        run = self.db.one("SELECT * FROM period_run WHERE company_id=? AND kind=? AND year=? AND month=?",
                          (self.s.company_id, self.kind, year, month))
        if not run:
            raise BusinessError("Tháng này chưa chạy.")
        later = self.db.scalar("SELECT 1 FROM period_run WHERE company_id=? AND kind=? AND (year*100+month) > ?",
                               (self.s.company_id, self.kind, year * 100 + month))
        if later:
            raise BusinessError("Phải hoàn tác các tháng sau trước (hoàn tác từ tháng mới nhất).")
        vs = VoucherService(self.s)
        with self.db.transaction():
            if run["voucher_id"]:
                v = self.db.one("SELECT status FROM voucher WHERE id=?", (run["voucher_id"],))
                if v and v["status"] == "POSTED":
                    vs.unpost(run["voucher_id"])
                if v:
                    vs.delete(run["voucher_id"])             # xóa luôn bản ghi period_run qua voucher_id
            self.db.execute("DELETE FROM period_run WHERE id=?", (run["id"],))
            self.s.audit("Hoàn tác " + self._description(year, month).lower(), "period_run", f"{month:02d}/{year}")


class AssetService(_RunMixin):
    kind = KIND_ASSET

    def _description(self, year, month):
        return f"Trích khấu hao TSCĐ tháng {month:02d}/{year}"

    def assets(self, as_of: str | None = None):
        """Danh sách TSCĐ kèm hao mòn lũy kế, giá trị còn lại tại ngày as_of (mặc định cuối kỳ đang chọn)."""
        as_of = as_of or self.s.date_to.isoformat()
        ym = int(as_of[:4]) * 100 + int(as_of[5:7])
        out = []
        for a in self.db.query("SELECT * FROM fixed_asset WHERE company_id=? ORDER BY code", (self.s.company_id,)):
            done = self.db.scalar("""SELECT COALESCE(SUM(l.amount),0) FROM period_run_line l JOIN period_run r ON r.id=l.run_id
                                     WHERE r.company_id=? AND r.kind='ASSET' AND l.ref_id=? AND (r.year*100+r.month)<=?""",
                                  (self.s.company_id, a["id"], ym), 0)
            accum = a["accumulated_opening"] + done
            d = dict(a)
            d.update(accumulated=accum, net_value=a["original_cost"] - accum,
                     monthly=_monthly(a["original_cost"], a["useful_months"] or 0))
            out.append(d)
        return out

    def preview(self, year: int, month: int) -> list[RunRow]:
        ym_end = _month_end(year, month)
        rows = []
        for a in self.db.query("SELECT * FROM fixed_asset WHERE company_id=? AND active=1 ORDER BY code", (self.s.company_id,)):
            if not a["start_date"] or not a["useful_months"] or a["start_date"][:7] > ym_end[:7]:
                continue
            if a["disposal_date"] and a["disposal_date"][:7] < ym_end[:7]:
                continue                                           # ngừng từ tháng sau tháng ghi giảm
            done = a["accumulated_opening"] + self._done_before(a["id"], year, month)
            remain = a["original_cost"] - done
            if remain <= 0:
                continue                                           # đã khấu hao hết
            amount = _amount_for(a["original_cost"], a["useful_months"], done, a["start_date"], year, month)
            if not (a["asset_account"] and a["depreciation_account"] and a["expense_account"]):
                raise BusinessError(f"TSCĐ {a['code']}: thiếu TK nguyên giá / hao mòn / chi phí trong danh mục.")
            rows.append(RunRow(a["id"], a["code"], a["name"], a["original_cost"], done, amount, remain - amount,
                               a["expense_account"], a["depreciation_account"], a["department"]))
        return rows

    def dispose(self, asset_id: int, disposal_date: str):
        self.s.require("edit", "ghi giảm TSCĐ")
        a = self.db.one("SELECT * FROM fixed_asset WHERE id=? AND company_id=?", (asset_id, self.s.company_id))
        if not a:
            raise BusinessError("Không tìm thấy tài sản.")
        if self.periods.is_locked(disposal_date):
            raise BusinessError("Ngày ghi giảm thuộc kỳ đã khóa.")
        with self.db.transaction():
            self.db.execute("UPDATE fixed_asset SET disposal_date=? WHERE id=?", (disposal_date or None, asset_id))
            self.s.audit("Ghi giảm TSCĐ", "fixed_asset", a["code"], {"ngay": disposal_date})


class PrepaidService(_RunMixin):
    kind = KIND_PREPAID

    def _description(self, year, month):
        return f"Phân bổ công cụ dụng cụ, chi phí trả trước tháng {month:02d}/{year}"

    def items(self, as_of: str | None = None, kind: str | None = None):
        as_of = as_of or self.s.date_to.isoformat()
        ym = int(as_of[:4]) * 100 + int(as_of[5:7])
        out = []
        for p in self.db.query("SELECT * FROM prepaid_item WHERE company_id=? ORDER BY code", (self.s.company_id,)):
            if kind and p["kind"] != kind:
                continue
            done = self.db.scalar("""SELECT COALESCE(SUM(l.amount),0) FROM period_run_line l JOIN period_run r ON r.id=l.run_id
                                     WHERE r.company_id=? AND r.kind='PREPAID' AND l.ref_id=? AND (r.year*100+r.month)<=?""",
                                  (self.s.company_id, p["id"], ym), 0)
            d = dict(p)
            allocated = p["allocated_opening"] + done
            d.update(allocated=allocated, remaining=p["total_amount"] - allocated,
                     monthly=_monthly(p["total_amount"], p["months"] or 0))
            out.append(d)
        return out

    def save_item(self, rec_id, values: dict) -> int:
        self.s.require("edit" if rec_id else "add", "cập nhật CCDC / chi phí trả trước")
        errors = []
        code, name = (values.get("code") or "").strip(), (values.get("name") or "").strip()
        if not code or not name:
            errors.append("Mã và tên không được trống")
        try:
            total, months = round_money(values.get("total_amount")), int(values.get("months") or 0)
            opening = round_money(values.get("allocated_opening") or 0)
        except (ValueError, TypeError) as e:
            raise BusinessError(f"Số liệu không hợp lệ: {e}") from None
        if total <= 0 or months <= 0:
            errors.append("Tổng giá trị và số tháng phân bổ phải lớn hơn 0")
        if opening < 0 or opening > total:
            errors.append("Đã phân bổ đầu kỳ phải từ 0 đến tổng giá trị")
        try:
            date.fromisoformat((values.get("start_date") or "")[:10])
        except ValueError:
            errors.append("Ngày bắt đầu không hợp lệ (yyyy-mm-dd)")
        for key, label in (("source_account", "TK nguồn"), ("expense_account", "TK chi phí")):
            if not self.db.scalar("SELECT 1 FROM account WHERE company_id=? AND code=? AND is_detail=1",
                                  (self.s.company_id, values.get(key))):
                errors.append(f"{label} '{values.get(key) or ''}' không có hoặc là TK tổng hợp")
        if self.db.scalar("SELECT 1 FROM prepaid_item WHERE company_id=? AND code=? AND id<>?", (self.s.company_id, code, rec_id or 0)):
            errors.append(f"Mã '{code}' đã tồn tại")
        if errors:
            raise BusinessError("; ".join(errors))
        cols = (values.get("kind") or "CCDC", values["source_account"], values["expense_account"], total,
                values["start_date"][:10], months, opening, values.get("department") or None, 1 if values.get("active", 1) else 0)
        with self.db.transaction():
            if rec_id:
                self.db.execute("""UPDATE prepaid_item SET code=?, name=?, kind=?, source_account=?, expense_account=?,
                    total_amount=?, start_date=?, months=?, allocated_opening=?, department=?, active=? WHERE id=? AND company_id=?""",
                                (code, name, *cols, rec_id, self.s.company_id))
            else:
                rec_id = self.db.execute("""INSERT INTO prepaid_item(company_id, code, name, kind, source_account, expense_account,
                    total_amount, start_date, months, allocated_opening, department, active) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                                         (self.s.company_id, code, name, *cols)).lastrowid
            self.s.audit("Lưu CCDC / chi phí trả trước", "prepaid_item", code, values)
        return rec_id

    def delete_item(self, rec_id: int):
        self.s.require("delete", "xóa CCDC / chi phí trả trước")
        if self.db.scalar("SELECT 1 FROM period_run_line l JOIN period_run r ON r.id=l.run_id WHERE r.kind='PREPAID' AND l.ref_id=?",
                          (rec_id,)):
            raise BusinessError("Khoản này đã có phân bổ – không thể xóa (bỏ chọn «Đang dùng» để ngừng).")
        with self.db.transaction():
            self.db.execute("DELETE FROM prepaid_item WHERE id=? AND company_id=?", (rec_id, self.s.company_id))
            self.s.audit("Xóa CCDC / chi phí trả trước", "prepaid_item", rec_id)

    def preview(self, year: int, month: int) -> list[RunRow]:
        ym_end = _month_end(year, month)
        rows = []
        for p in self.db.query("SELECT * FROM prepaid_item WHERE company_id=? AND active=1 ORDER BY code", (self.s.company_id,)):
            if p["start_date"][:7] > ym_end[:7]:
                continue
            done = p["allocated_opening"] + self._done_before(p["id"], year, month)
            remain = p["total_amount"] - done
            if remain <= 0:
                continue                                           # đã phân bổ hết
            amount = _amount_for(p["total_amount"], p["months"], done, p["start_date"], year, month)
            rows.append(RunRow(p["id"], p["code"], p["name"], p["total_amount"], done, amount, remain - amount,
                               p["expense_account"], p["source_account"], p["department"]))
        return rows
