"""Truy cập CSDL SQLite: kết nối, giao dịch nguyên tử, khởi tạo lược đồ.

Lưu ý triển khai: SQLite chỉ dành cho bản MỘT người dùng trên máy cục bộ.
Không đặt file .db trên thư mục chia sẻ mạng (LAN). Bản nhiều người dùng phải dùng
CSDL máy chủ (PostgreSQL) – lớp này được thiết kế để thay thế qua cùng giao diện
``Database.query/execute/transaction``.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = "3"

# Migration theo phiên bản: schema.sql là phiên bản 1; các phiên bản sau áp dụng tuần tự,
# kể cả với file dữ liệu tạo từ phiên bản cũ (nâng cấp tại chỗ, trong một giao dịch).
MIGRATIONS: dict[int, list[str]] = {
    2: [
        "ALTER TABLE voucher ADD COLUMN due_date TEXT",
        "ALTER TABLE voucher ADD COLUMN source_voucher_id INTEGER",
        "ALTER TABLE company ADD COLUMN costing_method TEXT NOT NULL DEFAULT 'BQCK'",
        """CREATE TABLE IF NOT EXISTS opening_stock (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            item_id INTEGER NOT NULL REFERENCES item(id),
            warehouse_id INTEGER NOT NULL REFERENCES warehouse(id),
            quantity TEXT NOT NULL DEFAULT '0',
            amount INTEGER NOT NULL DEFAULT 0,
            UNIQUE(company_id, year, item_id, warehouse_id))""",
        """CREATE TABLE IF NOT EXISTS costing_run (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, d_from TEXT NOT NULL, d_to TEXT NOT NULL,
            method TEXT NOT NULL, run_by TEXT, run_at TEXT, lines_updated INTEGER, total_change INTEGER, detail TEXT)""",
        "CREATE INDEX IF NOT EXISTS ix_voucher_source ON voucher(source_voucher_id)",
        "CREATE INDEX IF NOT EXISTS ix_le_item ON ledger_entry(company_id, item_id, warehouse_id, posting_date)",
        # hạn thanh toán cho chứng từ mua/bán đã có = ngày hóa đơn (hoặc ngày CT) + số ngày hạn TT của đối tượng
        """UPDATE voucher SET due_date = date(COALESCE(invoice_date, voucher_date), '+' ||
               COALESCE((SELECT payment_terms FROM partner p WHERE p.id = voucher.partner_id), 0) || ' days')
           WHERE due_date IS NULL AND vtype IN ('BKMH', 'BKBH', 'PKMB')""",
    ],
    3: [
        "ALTER TABLE fixed_asset ADD COLUMN accumulated_opening INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE fixed_asset ADD COLUMN disposal_date TEXT",
        """CREATE TABLE IF NOT EXISTS prepaid_item (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
            code TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'CCDC',
            source_account TEXT, expense_account TEXT, total_amount INTEGER NOT NULL DEFAULT 0,
            start_date TEXT, months INTEGER, allocated_opening INTEGER NOT NULL DEFAULT 0, department TEXT,
            active INTEGER NOT NULL DEFAULT 1, UNIQUE(company_id, code))""",
        """CREATE TABLE IF NOT EXISTS period_run (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, kind TEXT NOT NULL, year INTEGER NOT NULL,
            month INTEGER NOT NULL, voucher_id INTEGER, total INTEGER NOT NULL DEFAULT 0, run_by TEXT, run_at TEXT,
            UNIQUE(company_id, kind, year, month))""",
        """CREATE TABLE IF NOT EXISTS period_run_line (
            id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES period_run(id) ON DELETE CASCADE,
            ref_id INTEGER NOT NULL, amount INTEGER NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS cost_sheet (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, method TEXT NOT NULL, d_from TEXT NOT NULL, d_to TEXT NOT NULL,
            project_id INTEGER NOT NULL, quantity TEXT NOT NULL DEFAULT '0', wip_begin INTEGER NOT NULL DEFAULT 0,
            direct_cost INTEGER NOT NULL DEFAULT 0, common_cost INTEGER NOT NULL DEFAULT 0, wip_end INTEGER NOT NULL DEFAULT 0,
            total_cost INTEGER NOT NULL DEFAULT 0, unit_cost TEXT, norm_unit_cost TEXT, voucher_id INTEGER,
            saved_by TEXT, saved_at TEXT, UNIQUE(company_id, method, d_from, d_to, project_id))""",
        """CREATE TABLE IF NOT EXISTS report_template (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
            code TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, regime_code TEXT, version INTEGER NOT NULL DEFAULT 1,
            effective_from TEXT, source_ref TEXT, verified INTEGER NOT NULL DEFAULT 0, verified_by TEXT, verified_at TEXT,
            verified_note TEXT, created_by TEXT, created_at TEXT, UNIQUE(company_id, code, version))""",
        """CREATE TABLE IF NOT EXISTS report_line (
            id INTEGER PRIMARY KEY, template_id INTEGER NOT NULL REFERENCES report_template(id) ON DELETE CASCADE,
            seq INTEGER NOT NULL, code TEXT NOT NULL, label TEXT NOT NULL, formula TEXT, indent INTEGER NOT NULL DEFAULT 0,
            bold INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS tax_adjustment (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, year INTEGER NOT NULL, kind TEXT NOT NULL,
            label TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, note TEXT)""",
        """CREATE TABLE IF NOT EXISTS tax_param (
            company_id INTEGER NOT NULL, year INTEGER NOT NULL, key TEXT NOT NULL, value TEXT, source_note TEXT,
            PRIMARY KEY (company_id, year, key))""",
    ],
}
SCHEMA_FILE = Path(__file__).with_name("schema.sql")
APP_SIGNATURE = "ketoan-hocviendaotaoai"


class DatabaseError(Exception):
    pass


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn: sqlite3.Connection | None = None
        self._depth = 0
        self.open()

    # ------------------------------------------------------------ vòng đời
    def open(self):
        self.conn = sqlite3.connect(self.path, isolation_level=None, detect_types=0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = DELETE")
        self.conn.execute("PRAGMA synchronous = FULL")

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    @property
    def connected(self) -> bool:
        if self.conn is None:
            return False
        try:
            self.conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def init_schema(self):
        self.conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        with self.transaction():
            self.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', '1')")
            self.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('signature', ?)", (APP_SIGNATURE,))
        self.migrate()

    def schema_version(self) -> int:
        try:
            return int(self.scalar("SELECT value FROM meta WHERE key='schema_version'", default="1"))
        except sqlite3.Error:
            return 0

    def migrate(self) -> list[int]:
        """Nâng cấp lược đồ lên SCHEMA_VERSION. Trả về danh sách phiên bản đã áp dụng."""
        applied = []
        current = self.schema_version()
        for ver in sorted(v for v in MIGRATIONS if v > current):
            with self.transaction():
                for sql in MIGRATIONS[ver]:
                    self.execute(sql)
                self.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (str(ver),))
            applied.append(ver)
        return applied

    def is_app_database(self) -> bool:
        try:
            row = self.one("SELECT value FROM meta WHERE key='signature'")
            return bool(row) and row["value"] == APP_SIGNATURE
        except sqlite3.Error:
            return False

    # ------------------------------------------------------------ giao dịch
    @contextmanager
    def transaction(self):
        """Giao dịch lồng nhau an toàn: chỉ lớp ngoài cùng COMMIT/ROLLBACK.

        Bảo đảm nguyên tắc "lưu đầy đủ hoặc hoàn tác đầy đủ".
        """
        outer = self._depth == 0
        if outer:
            self.conn.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield self
        except BaseException:
            self._depth -= 1
            if outer:
                self.conn.execute("ROLLBACK")
            raise
        else:
            self._depth -= 1
            if outer:
                self.conn.execute("COMMIT")

    # ------------------------------------------------------------ truy vấn
    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, seq) -> sqlite3.Cursor:
        return self.conn.executemany(sql, seq)

    def query(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params=(), default=None):
        row = self.conn.execute(sql, params).fetchone()
        return default if row is None or row[0] is None else row[0]

    # ------------------------------------------------------------ sao lưu
    def backup_to(self, target: str | Path):
        dest = sqlite3.connect(str(target))
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
