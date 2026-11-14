"""Kết chuyển chi phí sản xuất vào TK 154 (cho hệ thống tài khoản có TK 621, 622, 627).

Hệ thống TK mẫu đi kèm (theo cấu hình TT133 minh họa) KHÔNG có TK 621/622/627; chức năng này dành cho doanh nghiệp đã khai báo
các tài khoản đó trong danh mục (ví dụ hệ thống TK theo chế độ doanh nghiệp). Danh sách TK được cấu hình khi chạy.

QUY ƯỚC (người dùng chọn, không phải quy định):
  • Chi phí TRỰC TIẾP (mặc định 621, 622): các bút toán đã gắn công trình/đối tượng → kết chuyển thẳng vào 154 của đối tượng đó.
  • Chi phí CHUNG (mặc định 627): phần đã gắn đối tượng kết chuyển thẳng; phần CHƯA gắn đối tượng được phân bổ cho các đối tượng
    theo tỷ lệ chi phí trực tiếp (hoặc theo tiêu thức chỉ nhân công trực tiếp), làm tròn đồng, đối tượng cuối nhận phần dư.
  • Chỉ xử lý theo MỘT THÁNG; mỗi tháng chạy một lần (chặn chạy trùng); chứng từ tạo ra là «Nghiệp vụ hạch toán» NHÁP
    (Nợ 154 theo đối tượng / Có TK chi phí); hoàn tác khi kỳ chưa khóa.
  • Chưa hỗ trợ: phân bổ theo giờ máy/định mức, chi phí sản xuất chung cố định/biến đổi, sản phẩm dở dang quy đổi.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ketoan.domain.money import round_money
from ketoan.services.asset_service import _month_end
from ketoan.services.context import BusinessError, Session
from ketoan.services.period_service import PeriodService
from ketoan.services.voucher_service import VoucherService

KIND = "OVERHEAD"
CRITERIA = {"DIRECT": "Tổng chi phí trực tiếp (621 + 622…)", "LABOR": "Chỉ chi phí nhân công trực tiếp (TK đầu tiên trong nhóm 622)"}


class OverheadService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db
        self.periods = PeriodService(session)

    def _validate_accounts(self, direct: list[str], overhead: list[str]):
        have = {r["code"] for r in self.db.query("SELECT code FROM account WHERE company_id=? AND is_detail=1", (self.s.company_id,))}
        missing = [a for a in direct + overhead if a not in have]
        if missing:
            raise BusinessError("TK chưa có trong hệ thống tài khoản (hoặc là TK tổng hợp): " + ", ".join(missing) +
                                ". Khai báo trong Danh mục → Hệ thống tài khoản (nhập Excel) trước.")
        if set(direct) & set(overhead):
            raise BusinessError("Một TK không thể vừa là chi phí trực tiếp vừa là chi phí chung.")
        if not self.db.scalar("SELECT 1 FROM account WHERE company_id=? AND code='154' AND is_detail=1", (self.s.company_id,)):
            raise BusinessError("Thiếu TK 154 chi tiết trong hệ thống tài khoản.")

    def preview(self, year: int, month: int, direct: list[str], overhead: list[str], criterion: str = "DIRECT") -> dict:
        direct, overhead = [a.strip() for a in direct if a.strip()], [a.strip() for a in overhead if a.strip()]
        self._validate_accounts(direct, overhead)
        d_from, d_to = f"{year}-{month:02d}-01", _month_end(year, month)
        projects = {r["id"]: r for r in self.db.query("SELECT id, code, name FROM project WHERE company_id=?", (self.s.company_id,))}
        by: dict[tuple, int] = defaultdict(int)                  # (project_id|None, account) -> số tiền
        for r in self.db.query("""SELECT account_code a, project_id p, SUM(debit-credit) n FROM ledger_entry WHERE company_id=?
                                  AND posting_date BETWEEN ? AND ? GROUP BY a, p""", (self.s.company_id, d_from, d_to)):
            for acc in direct + overhead:
                if r["a"] == acc or r["a"].startswith(acc):
                    by[(r["p"], acc)] += r["n"]
        already = self.db.one("SELECT * FROM period_run WHERE company_id=? AND kind=? AND year=? AND month=?",
                              (self.s.company_id, KIND, year, month))
        labor = direct[1] if criterion == "LABOR" and len(direct) > 1 else (direct[0] if criterion == "LABOR" and direct else None)
        base: dict[int, int] = defaultdict(int)
        for (p, acc), n in by.items():
            if p is not None and (acc in direct if criterion == "DIRECT" else acc == labor):
                base[p] += n
        lines, warnings = [], []
        for (p, acc), n in sorted(by.items(), key=lambda x: (x[0][1], x[0][0] or 0)):
            if p is not None and n:
                lines.append({"project_id": p, "account": acc, "amount": n, "kind": "Trực tiếp theo đối tượng" if acc in direct else "Chung – đã gắn đối tượng"})
        for acc in overhead:
            pool = by.get((None, acc), 0)
            if not pool:
                continue
            total = sum(base.values())
            if total <= 0:
                warnings.append(f"TK {acc}: {pool:,} chưa gắn đối tượng nhưng không có chi phí trực tiếp làm tiêu thức phân bổ – chưa kết chuyển.".replace(",", "."))
                continue
            ids = sorted(base, key=lambda i: projects[i]["code"] if i in projects else "")
            used = 0
            for i, pid in enumerate(ids):
                part = (pool - used) if i == len(ids) - 1 else round_money(pool * base[pid] / total)
                used += part
                if part:
                    lines.append({"project_id": pid, "account": acc, "amount": part, "kind": "Chung – phân bổ theo tiêu thức"})
        for (p, acc), n in by.items():
            if p is None and acc in direct and n:
                warnings.append(f"TK {acc}: {n:,} chi phí trực tiếp chưa gắn công trình/đối tượng – chưa kết chuyển (cần gắn đối tượng).".replace(",", "."))
        for ln in lines:
            pr = projects.get(ln["project_id"])
            ln["project_code"], ln["project_name"] = (pr["code"], pr["name"]) if pr else ("?", "")
        return {"lines": lines, "warnings": warnings, "run": already, "d_from": d_from, "d_to": d_to,
                "total": sum(l["amount"] for l in lines)}

    def apply(self, year: int, month: int, direct: list[str], overhead: list[str], criterion: str = "DIRECT") -> int:
        self.s.require("add", "kết chuyển chi phí vào 154")
        with self.db.transaction():
            self.db.advisory_lock(f"period-run:{self.s.company_id}:{KIND}")
            pv = self.preview(year, month, direct, overhead, criterion)
            if pv["run"]:
                raise BusinessError(f"Tháng {month:02d}/{year} đã kết chuyển chi phí vào 154. Hoàn tác trước nếu cần chạy lại.")
            if self.periods.is_locked(pv["d_to"]):
                raise BusinessError(f"Tháng {month:02d}/{year} đã khóa.")
            lines = [l for l in pv["lines"] if l["amount"] > 0]
            if not lines:
                raise BusinessError("Không có chi phí nào cần kết chuyển trong tháng.")
            vid = VoucherService(self.s).save({"vtype": "PKT", "voucher_date": pv["d_to"], "posting_date": pv["d_to"],
                                               "description": f"Kết chuyển chi phí sản xuất vào TK 154 tháng {month:02d}/{year}"},
                                              [{"description": f"{l['kind']} – {l['account']}", "debit_account": "154", "credit_account": l["account"],
                                                "amount": l["amount"], "project": l["project_code"]} for l in lines])
            self.db.execute("""INSERT INTO period_run(company_id, kind, year, month, voucher_id, total, run_by, run_at) VALUES(?,?,?,?,?,?,?,?)""",
                            (self.s.company_id, KIND, year, month, vid, pv["total"], self.s.user.username,
                             datetime.now().isoformat(timespec="seconds")))
            self.s.audit("Kết chuyển chi phí sản xuất vào 154", "period_run", f"{month:02d}/{year}", {"tong": pv["total"], "so_dong": len(lines)})
        return vid

    def undo(self, year: int, month: int):
        self.s.require("post", "hoàn tác kết chuyển chi phí vào 154")
        run = self.db.one("SELECT * FROM period_run WHERE company_id=? AND kind=? AND year=? AND month=?", (self.s.company_id, KIND, year, month))
        if not run:
            raise BusinessError("Tháng này chưa kết chuyển.")
        vs = VoucherService(self.s)
        with self.db.transaction():
            v = self.db.one("SELECT status FROM voucher WHERE id=?", (run["voucher_id"],))
            if v and v["status"] == "POSTED":
                vs.unpost(run["voucher_id"])
            if v:
                vs.delete(run["voucher_id"])
            self.db.execute("DELETE FROM period_run WHERE id=?", (run["id"],))
            self.s.audit("Hoàn tác kết chuyển chi phí vào 154", "period_run", f"{month:02d}/{year}")
