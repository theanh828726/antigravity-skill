"""Chuyển dữ liệu từ file SQLite sang CSDL PostgreSQL (khi doanh nghiệp chuyển từ một người dùng sang nhiều người dùng).

An toàn dữ liệu:
  • Chỉ chuyển vào CSDL PostgreSQL TRỐNG (chưa có dữ liệu ứng dụng) – không bao giờ ghi đè.
  • Toàn bộ (tạo lược đồ + sao chép dữ liệu) nằm trong MỘT giao dịch: lỗi ở bất kỳ bước nào thì hoàn tác sạch, CSDL đích vẫn trống.
  • Đọc nguồn trong một giao dịch đọc để có ảnh chụp nhất quán; KHÔNG sửa file nguồn.
  • Giữ nguyên mã (id) mọi bản ghi và mật khẩu đã băm; đặt lại bộ đếm tự tăng để bản ghi mới không trùng id.
  • Sau khi sao chép, đối chiếu số dòng từng bảng và tổng Nợ/Có sổ cái, số dư đầu kỳ, tổng chứng từ; lệch thì hoàn tác.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ketoan.data.db import APP_SIGNATURE, SCHEMA_VERSION, Database, DatabaseError, PostgresDatabase

BATCH = 1000
CHECKSUMS = [
    ("ledger_entry", "SUM(debit), SUM(credit), COUNT(*)"),
    ("opening_balance", "SUM(debit), SUM(credit), COUNT(*)"),
    ("voucher", "SUM(total_amount), SUM(total_tax), SUM(total_payment), COUNT(*)"),
    ("voucher_line", "SUM(amount), SUM(tax_amount), COUNT(*)"),
    ("app_user", "COUNT(*), MIN(pwd_hash), MAX(pwd_hash)"),
]


@dataclass
class TransferResult:
    tables: dict = field(default_factory=dict)        # bảng -> số dòng đã chuyển
    checks: list = field(default_factory=list)        # (nội dung, nguồn, đích, khớp?)

    @property
    def total_rows(self) -> int:
        return sum(self.tables.values())

    @property
    def ok(self) -> bool:
        return all(c[3] for c in self.checks)


def _fk_order(src: sqlite3.Connection) -> list[str]:
    """Thứ tự bảng sao cho bảng được tham chiếu luôn được chuyển trước (sắp xếp tô-pô theo khóa ngoại)."""
    names = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    deps = {n: {r[2] for r in src.execute(f"PRAGMA foreign_key_list({n})") if r[2] != n} for n in names}
    out, left = [], set(names)
    while left:
        ready = sorted(n for n in left if not (deps[n] & left))
        if not ready:
            raise DatabaseError("Phụ thuộc khóa ngoại vòng tròn – không sắp xếp được thứ tự chuyển bảng.")
        out += ready
        left -= set(ready)
    return out


def transfer_sqlite_to_postgres(sqlite_path: str | Path, pg_url: str, progress=None) -> TransferResult:
    """progress(bảng, số_dòng_đã_chuyển, tổng_số_dòng) – tùy chọn. Ném DatabaseError nếu không thể chuyển an toàn."""
    sqlite_path = Path(sqlite_path)
    if not sqlite_path.exists():
        raise DatabaseError(f"Không tìm thấy file dữ liệu: {sqlite_path}")
    src_db = Database(sqlite_path)
    try:
        if not src_db.is_app_database():
            raise DatabaseError("File nguồn không phải dữ liệu của Ứng dụng Kế toán.")
        if src_db.schema_version() > int(SCHEMA_VERSION):
            raise DatabaseError("Dữ liệu nguồn do phiên bản mới hơn tạo ra – hãy cập nhật ứng dụng.")
        src_db.migrate()                                   # đưa nguồn về lược đồ mới nhất (chỉ thêm cột/bảng, an toàn)
        dst = PostgresDatabase(pg_url)
        try:
            if dst.has_schema():
                raise DatabaseError("CSDL PostgreSQL đích đã có dữ liệu ứng dụng – chỉ chuyển vào CSDL TRỐNG.")
            return _copy(src_db, dst, progress)
        finally:
            dst.close()
    finally:
        src_db.close()


def _copy(src_db: Database, dst: PostgresDatabase, progress) -> TransferResult:
    src = src_db.conn
    res = TransferResult()
    order = _fk_order(src)
    src.execute("BEGIN")                                    # ảnh chụp nhất quán của nguồn
    try:
        with dst.transaction():                             # DDL của PostgreSQL cũng được hoàn tác khi lỗi
            dst.init_schema()
            for table in order:
                if table == "meta":
                    continue                                # đích đã có meta (phiên bản, chữ ký) từ init_schema
                cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
                total = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                dst_cols = {r["column_name"] for r in dst.query(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=?", (table,))}
                missing = [c for c in cols if c not in dst_cols]
                if missing:
                    raise DatabaseError(f"Bảng {table}: đích thiếu cột {', '.join(missing)} – hai phiên bản lược đồ không khớp.")
                done = 0
                if total:
                    sql = f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})"
                    cur = src.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY 1")
                    while True:
                        chunk = cur.fetchmany(BATCH)
                        if not chunk:
                            break
                        dst.executemany(sql, [tuple(r) for r in chunk])
                        done += len(chunk)
                        if progress:
                            progress(table, done, total)
                    if "id" in cols:                        # bộ đếm tự tăng tiếp tục sau id lớn nhất
                        dst.execute("SELECT setval(pg_get_serial_sequence(?, 'id'), (SELECT MAX(id) FROM " + table + "))", (table,))
                res.tables[table] = total
            _verify(src_db, dst, res)
            if not res.ok:
                bad = "; ".join(f"{c[0]}: nguồn {c[1]} ≠ đích {c[2]}" for c in res.checks if not c[3])
                raise DatabaseError("Đối chiếu sau khi chuyển không khớp – đã hoàn tác. " + bad)
    finally:
        src.execute("ROLLBACK")                             # kết thúc giao dịch đọc (nguồn không bị thay đổi)
    return res


def _verify(src_db: Database, dst: PostgresDatabase, res: TransferResult):
    for table, n in res.tables.items():
        dn = dst.scalar(f"SELECT COUNT(*) FROM {table}")
        res.checks.append((f"Số dòng {table}", n, dn, n == dn))
    for table, expr in CHECKSUMS:
        a = tuple(src_db.one(f"SELECT {expr} FROM {table}"))
        b = tuple(dst.one(f"SELECT {expr} FROM {table}"))
        res.checks.append((f"Tổng đối chiếu {table}", a, b, a == b))
    sig = dst.scalar("SELECT value FROM meta WHERE key='signature'")
    res.checks.append(("Chữ ký ứng dụng", APP_SIGNATURE, sig, sig == APP_SIGNATURE))
