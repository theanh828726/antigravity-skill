"""Hệ thống: doanh nghiệp, chế độ kế toán (phiên bản), số dư đầu kỳ, sao lưu – khôi phục, nhật ký."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ketoan.data.db import APP_SIGNATURE, DatabaseError
from ketoan.domain.money import round_money
from ketoan.services.context import BusinessError, Session
from ketoan.services.period_service import PeriodService


class CompanyService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    def companies(self):
        return self.db.query("SELECT * FROM company ORDER BY code")

    def regimes(self):
        return self.db.query("SELECT * FROM accounting_regime ORDER BY effective_from")

    def regime_history(self):
        return self.db.query("""SELECT cr.*, r.name, r.legal_ref, r.verified FROM company_regime cr
                                JOIN accounting_regime r ON r.code=cr.regime_code WHERE cr.company_id=?
                                ORDER BY cr.effective_from""", (self.s.company_id,))

    def update_company(self, values: dict):
        self.s.require("admin", "cập nhật thông tin doanh nghiệp")
        if not (values.get("name") or "").strip():
            raise BusinessError("Tên doanh nghiệp không được trống.")
        with self.db.transaction():
            self.db.execute("""UPDATE company SET name=?, tax_code=?, address=?, business=?, director=?, chief_accountant=?
                               WHERE id=?""", (values["name"].strip(), values.get("tax_code"), values.get("address"),
                                               values.get("business"), values.get("director"),
                                               values.get("chief_accountant"), self.s.company_id))
            self.s.audit("Cập nhật doanh nghiệp", "company", self.s.company_id, values)

    def set_regime(self, regime_code: str, effective_from: str):
        """Áp dụng chế độ kế toán từ ngày – lưu lịch sử phiên bản, không ghi đè quá khứ."""
        self.s.require("admin", "cấu hình chế độ kế toán")
        if PeriodService(self.s).is_locked(effective_from):
            raise BusinessError("Ngày hiệu lực thuộc kỳ đã khóa.")
        with self.db.transaction():
            self.db.execute("""INSERT INTO company_regime(company_id, regime_code, effective_from) VALUES(?,?,?)
                               ON CONFLICT(company_id, effective_from) DO UPDATE SET regime_code=excluded.regime_code""",
                            (self.s.company_id, regime_code, effective_from))
            self.s.audit("Áp dụng chế độ kế toán", "company_regime", regime_code, {"tu_ngay": effective_from})

    def tax_rates(self):
        return self.db.query("SELECT * FROM tax_rate ORDER BY effective_from, CAST(rate AS REAL)")


class OpeningBalanceService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    def rows(self, year: int):
        return self.db.query("""SELECT ob.*, a.name AS account_name, p.code AS partner_code, p.name AS partner_name
                                FROM opening_balance ob LEFT JOIN account a ON a.company_id=ob.company_id AND a.code=ob.account_code
                                LEFT JOIN partner p ON p.id=ob.partner_id
                                WHERE ob.company_id=? AND ob.year=? ORDER BY ob.account_code, p.code""",
                             (self.s.company_id, year))

    def save(self, year: int, rows: list[dict]):
        """rows: [{account_code, partner_code, debit, credit}] – thay thế toàn bộ số dư đầu năm."""
        self.s.require("edit", "nhập số dư đầu kỳ")
        if PeriodService(self.s).is_locked(f"{year}-01-01"):
            raise BusinessError(f"Tháng 01/{year} đã khóa – không thể sửa số dư đầu năm.")
        errors, clean = [], []
        accounts = {r["code"]: r for r in self.db.query("SELECT * FROM account WHERE company_id=?", (self.s.company_id,))}
        for i, r in enumerate(rows, 1):
            acc = (r.get("account_code") or "").strip()
            d, c = round_money(r.get("debit")), round_money(r.get("credit"))
            if not acc and not d and not c:
                continue
            a = accounts.get(acc)
            if not a:
                errors.append(f"Dòng {i}: TK '{acc}' không tồn tại"); continue
            if not a["is_detail"]:
                errors.append(f"Dòng {i}: TK {acc} là TK tổng hợp – nhập vào TK chi tiết")
            pid = None
            pc = (r.get("partner_code") or "").strip()
            if pc:
                pid = self.db.scalar("SELECT id FROM partner WHERE company_id=? AND code=?", (self.s.company_id, pc))
                if not pid:
                    errors.append(f"Dòng {i}: đối tượng '{pc}' không tồn tại")
            elif a["require_partner"]:
                errors.append(f"Dòng {i}: TK {acc} bắt buộc chọn đối tượng")
            if d and c:
                errors.append(f"Dòng {i}: chỉ nhập dư Nợ hoặc dư Có")
            if d < 0 or c < 0:
                errors.append(f"Dòng {i}: số dư không được âm")
            clean.append((acc, pid, d, c))
        if errors:
            raise BusinessError("\n".join(errors))
        with self.db.transaction():
            self.db.execute("DELETE FROM opening_balance WHERE company_id=? AND year=?", (self.s.company_id, year))
            self.db.executemany("INSERT INTO opening_balance(company_id, year, account_code, partner_id, debit, credit) "
                                "VALUES(?,?,?,?,?,?)", [(self.s.company_id, year, *x) for x in clean])
            td, tc = sum(x[2] for x in clean), sum(x[3] for x in clean)
            self.s.audit("Cập nhật số dư đầu kỳ", "opening_balance", year, {"tong_no": td, "tong_co": tc, "so_dong": len(clean)})
        return td, tc


class BackupService:
    def __init__(self, session: Session, backup_dir: str | Path):
        self.s = session
        self.db = session.db
        self.dir = Path(backup_dir)

    def backup(self, target: str | Path | None = None) -> Path:
        self.s.require("admin", "sao lưu dữ liệu")
        self.dir.mkdir(parents=True, exist_ok=True)
        target = Path(target) if target else self.dir / f"ketoan_{datetime.now():%Y%m%d_%H%M%S}{self.db.backup_ext}"
        try:
            self.db.backup_to(target)
        except DatabaseError as e:
            raise BusinessError(str(e)) from None
        with self.db.transaction():
            self.s.audit("Sao lưu dữ liệu", "file", str(target))
        return target

    def list_backups(self):
        if not self.dir.exists():
            return []
        return sorted(self.dir.glob("*" + self.db.backup_ext), key=lambda p: p.stat().st_mtime, reverse=True)

    @staticmethod
    def validate_file(path: str | Path):
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            sig = con.execute("SELECT value FROM meta WHERE key='signature'").fetchone()
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            con.close()
        except sqlite3.Error as e:
            raise BusinessError(f"File không phải dữ liệu kế toán hợp lệ: {e}") from None
        if not sig or sig[0] != APP_SIGNATURE:
            raise BusinessError("File không phải dữ liệu của Ứng dụng Kế toán.")
        if integrity != "ok":
            raise BusinessError(f"File sao lưu bị lỗi toàn vẹn: {integrity}")

    def restore(self, source: str | Path) -> Path:
        """Khôi phục: tự sao lưu dữ liệu hiện tại trước rồi ghi đè (SQLite: backup API; PostgreSQL: pg_restore --clean)."""
        self.s.require("admin", "khôi phục dữ liệu")
        stamp = f"truoc_khoi_phuc_{datetime.now():%Y%m%d_%H%M%S}{self.db.backup_ext}"
        if self.db.dialect == "postgresql":
            try:
                self.db.validate_dump(source)
                safety = self.backup(self.dir / stamp)
                self.db.restore_from(source)
            except DatabaseError as e:
                raise BusinessError(str(e)) from None
        else:
            self.validate_file(source)
            safety = self.backup(self.dir / stamp)
            src = sqlite3.connect(str(source))
            try:
                src.backup(self.db.conn)
            finally:
                src.close()
        self.db.migrate()                     # bản sao lưu từ phiên bản cũ => nâng cấp lược đồ
        with self.db.transaction():
            self.s.audit("Khôi phục dữ liệu", "file", str(source), {"ban_sao_an_toan": str(safety)})
        return safety


class AuditService:
    def __init__(self, session: Session):
        self.db = session.db

    def rows(self, d_from: str, d_to: str, search: str = "", limit: int = 2000):
        params = [d_from, d_to + "T23:59:59"]
        cond = ""
        if search:
            cond = "AND (username LIKE ? OR action LIKE ? OR entity_id LIKE ? OR detail LIKE ?)"
            params += [f"%{search}%"] * 4
        return self.db.query(f"""SELECT * FROM audit_log WHERE ts BETWEEN ? AND ? {cond} ORDER BY id DESC LIMIT {int(limit)}""",
                             params)
