"""Năm tài chính, khóa kỳ (theo tháng)."""
from __future__ import annotations

from datetime import date, datetime

from ketoan.services.context import BusinessError, Session


class PeriodService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    def years(self):
        return [r["year"] for r in self.db.query("SELECT year FROM fiscal_year WHERE company_id=? ORDER BY year",
                                                 (self.s.company_id,))]

    def ensure_year(self, year: int):
        self.db.execute("INSERT OR IGNORE INTO fiscal_year(company_id, year, start_date, end_date) VALUES(?,?,?,?)",
                        (self.s.company_id, year, f"{year}-01-01", f"{year}-12-31"))

    def fiscal_year_of(self, d: str):
        return self.db.one("SELECT * FROM fiscal_year WHERE company_id=? AND start_date<=? AND end_date>=?",
                           (self.s.company_id, d, d))

    def is_locked(self, d: str | date) -> bool:
        d = d if isinstance(d, str) else d.isoformat()
        y, m = int(d[:4]), int(d[5:7])
        return bool(self.db.scalar("SELECT 1 FROM period_lock WHERE company_id=? AND year=? AND month=?",
                                   (self.s.company_id, y, m)))

    def locked_months(self, year: int) -> dict[int, tuple]:
        return {r["month"]: (r["locked_by"], r["locked_at"]) for r in self.db.query(
            "SELECT * FROM period_lock WHERE company_id=? AND year=?", (self.s.company_id, year))}

    def pending_vouchers(self, year: int, month: int) -> int:
        prefix = f"{year:04d}-{month:02d}"
        return self.db.scalar("""SELECT COUNT(*) FROM voucher WHERE company_id=? AND substr(posting_date,1,7)=?
                                 AND status<>'POSTED'""", (self.s.company_id, prefix), 0)

    def lock(self, year: int, month: int):
        self.s.require("lock", "khóa kỳ")
        with self.db.transaction():
            self.db.execute("INSERT OR REPLACE INTO period_lock(company_id, year, month, locked_by, locked_at) VALUES(?,?,?,?,?)",
                            (self.s.company_id, year, month, self.s.user.username,
                             datetime.now().isoformat(timespec="seconds")))
            self.s.audit("Khóa kỳ", "period_lock", f"{month:02d}/{year}")

    def unlock(self, year: int, month: int):
        self.s.require("lock", "mở khóa kỳ")
        later = self.db.scalar("SELECT MAX(month) FROM period_lock WHERE company_id=? AND year=? AND month>?",
                               (self.s.company_id, year, month))
        if later:
            raise BusinessError(f"Phải mở khóa tháng {later:02d}/{year} trước (mở khóa theo thứ tự từ kỳ sau về kỳ trước).")
        with self.db.transaction():
            self.db.execute("DELETE FROM period_lock WHERE company_id=? AND year=? AND month=?",
                            (self.s.company_id, year, month))
            self.s.audit("Mở khóa kỳ", "period_lock", f"{month:02d}/{year}")
