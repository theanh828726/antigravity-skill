"""Truy cập CSDL: SQLite (một người dùng, máy cục bộ) và PostgreSQL (nhiều người dùng qua mạng).

Hai backend dùng chung một giao diện (query / one / scalar / execute / transaction / migrate / backup_to). Mã nghiệp vụ viết
bằng SQL chuẩn tương thích cả hai (dấu ``?``, ``INSERT ... ON CONFLICT``); backend PostgreSQL tự chuyển đổi cú pháp.
KHÔNG đặt file SQLite trên thư mục chia sẻ mạng để nhiều người cùng mở – hãy dùng PostgreSQL.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

SCHEMA_VERSION = "6"

# Migration theo phiên bản: schema.sql là phiên bản 1; các phiên bản sau áp dụng tuần tự,
# kể cả với file dữ liệu tạo từ phiên bản cũ (nâng cấp tại chỗ, trong một giao dịch).
MIGRATIONS: dict[int, list] = {   # phần tử: câu SQL dùng chung, hoặc (dialect, SQL) chỉ chạy cho một hệ CSDL
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
        ("sqlite", """UPDATE voucher SET due_date = date(COALESCE(invoice_date, voucher_date), '+' ||
               COALESCE((SELECT payment_terms FROM partner p WHERE p.id = voucher.partner_id), 0) || ' days')
           WHERE due_date IS NULL AND vtype IN ('BKMH', 'BKBH', 'PKMB')"""),
        ("postgresql", """UPDATE voucher SET due_date = to_char(COALESCE(invoice_date, voucher_date)::date +
               COALESCE((SELECT payment_terms FROM partner p WHERE p.id = voucher.partner_id), 0)::int, 'YYYY-MM-DD')
           WHERE due_date IS NULL AND vtype IN ('BKMH', 'BKBH', 'PKMB')"""),
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
    4: [
        # số phiên bản chứng từ: phát hiện hai người cùng sửa một chứng từ (khóa lạc quan, đa người dùng)
        "ALTER TABLE voucher ADD COLUMN version INTEGER NOT NULL DEFAULT 0",
    ],
    5: [
        # chiều của bút toán (D: Nợ, C: Có) – cần để giữ được biến động số lượng kho khi thành tiền bằng 0
        "ALTER TABLE ledger_entry ADD COLUMN side TEXT",
        "UPDATE ledger_entry SET side = CASE WHEN debit > 0 THEN 'D' ELSE 'C' END WHERE side IS NULL",
    ],
    6: [
        # an toàn đăng nhập: chống dò mật khẩu (khóa tạm), số vòng băm lưu theo từng tài khoản để nâng cấp dần
        "ALTER TABLE app_user ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE app_user ADD COLUMN locked_until TEXT",
        "ALTER TABLE app_user ADD COLUMN pwd_rounds INTEGER NOT NULL DEFAULT 120000",
    ],
}
SCHEMA_FILE = Path(__file__).with_name("schema.sql")
APP_SIGNATURE = "ketoan-hocviendaotaoai"


class DatabaseError(Exception):
    pass


class BaseDatabase:
    dialect = ""
    backup_ext = ".db"
    errors: tuple = (Exception,)

    def __init__(self):
        self._depth = 0
        self.conn = None
        self.path = ""

    @property
    def display_name(self) -> str:
        return Path(self.path).name

    # ------------------------------------------------------------ lược đồ & phiên bản
    def _ddl(self, sql: str) -> str:
        return sql

    def _migration_sql(self, item):
        if isinstance(item, tuple):
            return item[1] if item[0] == self.dialect else None
        return item

    def schema_version(self) -> int:
        try:
            return int(self.scalar("SELECT value FROM meta WHERE key='schema_version'", default="1"))
        except self.errors:
            return 0

    def _set_meta(self, key: str, value: str):
        self.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def migrate(self) -> list[int]:
        """Nâng cấp lược đồ lên SCHEMA_VERSION. Trả về danh sách phiên bản đã áp dụng."""
        applied = []
        current = self.schema_version()
        for ver in sorted(v for v in MIGRATIONS if v > current):
            with self.transaction():
                for item in MIGRATIONS[ver]:
                    sql = self._migration_sql(item)
                    if sql:
                        self.execute(self._ddl(sql))
                self._set_meta("schema_version", str(ver))
            applied.append(ver)
        return applied

    def is_app_database(self) -> bool:
        try:
            row = self.one("SELECT value FROM meta WHERE key='signature'")
            return bool(row) and row["value"] == APP_SIGNATURE
        except self.errors:
            return False

    # ------------------------------------------------------------ giao dịch
    def _begin(self):
        self.conn.execute("BEGIN")

    def _commit(self):
        self.conn.execute("COMMIT")

    def _rollback(self):
        self.conn.execute("ROLLBACK")

    @contextmanager
    def transaction(self):
        """Giao dịch lồng nhau an toàn: chỉ lớp ngoài cùng COMMIT/ROLLBACK ("lưu đầy đủ hoặc hoàn tác đầy đủ")."""
        outer = self._depth == 0
        if outer:
            self._begin()
        self._depth += 1
        try:
            yield self
        except BaseException:
            self._depth -= 1
            if outer:
                self._rollback()
            raise
        else:
            self._depth -= 1
            if outer:
                self._commit()

    # ------------------------------------------------------------ khóa (đa người dùng)
    def advisory_lock(self, name: str):
        """Khóa theo tên đến hết giao dịch (tuần tự hóa các thao tác cùng loại giữa nhiều người dùng). SQLite: đã tuần tự sẵn."""

    def lock_row(self, table: str, row_id):
        """Khóa dòng để đọc – kiểm tra – ghi an toàn giữa nhiều người dùng. SQLite: đã tuần tự sẵn."""

    # ------------------------------------------------------------ truy vấn
    def execute(self, sql: str, params=()):
        raise NotImplementedError

    def query(self, sql: str, params=()):
        return self.execute(sql, params).fetchall()

    def one(self, sql: str, params=()):
        return self.execute(sql, params).fetchone()

    def scalar(self, sql: str, params=(), default=None):
        row = self.one(sql, params)
        return default if row is None or row[0] is None else row[0]


class Database(BaseDatabase):
    """SQLite – một người dùng, máy cục bộ."""
    dialect = "sqlite"
    errors = (sqlite3.Error,)

    def __init__(self, path: str | Path):
        super().__init__()
        self.path = str(path)
        self.open()

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

    def clone(self):
        return Database(self.path)

    def init_schema(self):
        self.conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        with self.transaction():
            self._set_meta("schema_version", "1")
            self._set_meta("signature", APP_SIGNATURE)
        self.migrate()

    def _begin(self):
        self.conn.execute("BEGIN IMMEDIATE")        # một người ghi tại một thời điểm

    def execute(self, sql: str, params=()):
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, seq):
        return self.conn.executemany(sql, seq)

    def backup_to(self, target: str | Path):
        dest = sqlite3.connect(str(target))
        try:
            self.conn.backup(dest)
        finally:
            dest.close()


# ====================================================================== PostgreSQL
NO_ID_TABLES = {"meta", "period_lock", "tax_param", "accounting_regime", "role"}       # bảng không có cột id (khóa chính tự nhiên)


def pg_ddl(sql: str) -> str:
    """Chuyển DDL kiểu SQLite sang PostgreSQL: khóa tự tăng; số nguyên 64 bit (tiền đồng vượt 2^31)."""
    s = re.sub(r"PRAGMA[^;]*;", "", sql)
    s = s.replace("INTEGER PRIMARY KEY", "BIGSERIAL PRIMARY KEY")
    return re.sub(r"\bINTEGER\b", "BIGINT", s)


@lru_cache(maxsize=4096)
def pg_sql(sql: str, with_params: bool) -> tuple[str, bool]:
    """Chuyển câu SQL: ``?`` → ``%s``; LIKE → ILIKE (SQLite không phân biệt hoa thường); thêm RETURNING id cho INSERT."""
    q = re.sub(r"\bLIKE\b", "ILIKE", sql)
    if with_params:
        q = q.replace("%", "%%").replace("?", "%s")
    m = re.match(r"\s*INSERT\s+INTO\s+(\w+)", q, re.I)
    returning = bool(m) and m.group(1).lower() not in NO_ID_TABLES and "returning" not in q.lower()
    if returning:
        q = q.rstrip().rstrip(";") + " RETURNING id"
    return q, returning


class PgRow(tuple):
    """Dòng kết quả truy cập được theo chỉ số, tên cột, keys() – giống sqlite3.Row."""
    _index: dict
    _cols: list

    def __getitem__(self, k):
        if isinstance(k, str):
            return tuple.__getitem__(self, self._index[k])
        return tuple.__getitem__(self, k)

    def keys(self):
        return list(self._cols)

    def get(self, k, default=None):
        return tuple.__getitem__(self, self._index[k]) if k in self._index else default


class PgCursor:
    def __init__(self, cur, lastrowid=None):
        self._cur, self.lastrowid = cur, lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


def parse_pg_url(url: str) -> dict:
    u = urlparse(url)
    return {"host": u.hostname or "localhost", "port": u.port or 5432, "dbname": (u.path or "/").lstrip("/") or "postgres",
            "user": unquote(u.username) if u.username else None, "password": unquote(u.password) if u.password else None}


def make_pg_url(host, port, dbname, user, password: str | None = None) -> str:
    cred = quote(user or "", safe="") + (":" + quote(password, safe="") if password else "")
    return f"postgresql://{cred + '@' if cred else ''}{host}:{port}/{dbname}"


def strip_password(url: str) -> str:
    c = parse_pg_url(url)
    return make_pg_url(c["host"], c["port"], c["dbname"], c["user"])


def is_pg_url(target) -> bool:
    return isinstance(target, str) and target.lower().startswith(("postgresql://", "postgres://"))


class PostgresDatabase(BaseDatabase):
    """PostgreSQL – nhiều người dùng. Mật khẩu có thể để trống nếu dùng ~/.pgpass hoặc biến PGPASSWORD."""
    dialect = "postgresql"
    backup_ext = ".dump"

    def __init__(self, url: str):
        super().__init__()
        import psycopg
        self._psycopg = psycopg
        self.errors = (psycopg.Error,)
        self.params = parse_pg_url(url)
        self.path = strip_password(url)
        self.open()

    def open(self):
        psycopg = self._psycopg
        p = {k: v for k, v in self.params.items() if v}
        self.conn = psycopg.connect(autocommit=True, row_factory=self._row_factory, connect_timeout=10,
                                    application_name="ketoan-hocviendaotaoai", **p)
        self.conn.adapters.register_loader("numeric", _IntegralNumericLoader)

    @staticmethod
    def _row_factory(cursor):
        cols = [c.name for c in cursor.description] if cursor.description else []
        index = {}
        for i, c in enumerate(cols):
            index.setdefault(c, i)

        def make(values):
            r = PgRow(values)
            r._index, r._cols = index, cols
            return r
        return make

    @property
    def display_name(self) -> str:
        return f"{self.params['dbname']}@{self.params['host']}"

    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None

    @property
    def connected(self) -> bool:
        if self.conn is None or self.conn.closed:
            return False
        try:
            self.conn.execute("SELECT 1")
            return True
        except self.errors:
            return False

    def has_schema(self) -> bool:
        return bool(self.scalar("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='meta'"))

    def init_schema(self):
        self.conn.execute(pg_ddl(SCHEMA_FILE.read_text(encoding="utf-8")))
        with self.transaction():
            self._set_meta("schema_version", "1")
            self._set_meta("signature", APP_SIGNATURE)
        self.migrate()

    def _ddl(self, sql: str) -> str:
        return pg_ddl(sql)

    def execute(self, sql: str, params=()):
        q, returning = pg_sql(sql, bool(params))
        cur = self.conn.cursor()
        cur.execute(q, tuple(params) if params else None)
        if returning:
            row = cur.fetchone()
            return PgCursor(cur, row[0] if row else None)
        return PgCursor(cur)

    def executemany(self, sql: str, seq):
        q, _ = pg_sql(sql, True)
        cur = self.conn.cursor()
        cur.executemany(q, [tuple(x) for x in seq])
        return PgCursor(cur)

    def advisory_lock(self, name: str):
        self.conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (name,))

    def lock_row(self, table: str, row_id):
        self.conn.execute(f"SELECT 1 FROM {table} WHERE id=%s FOR UPDATE", (row_id,))

    # ---- sao lưu / khôi phục bằng công cụ của PostgreSQL (cần pg_dump, pg_restore trong PATH)
    def _tool(self, name: str) -> str:
        exe = shutil.which(name)
        if not exe:
            raise DatabaseError(f"Không tìm thấy '{name}' – cần cài PostgreSQL client tools và thêm vào PATH, "
                                "hoặc sao lưu bằng công cụ của máy chủ PostgreSQL.")
        return exe

    def _env(self):
        env = dict(os.environ)
        if self.params.get("password"):
            env["PGPASSWORD"] = self.params["password"]
        return env

    def _conn_args(self):
        p = self.params
        args = ["-h", str(p["host"]), "-p", str(p["port"]), "-d", p["dbname"]]
        return args + (["-U", p["user"]] if p.get("user") else [])

    def backup_to(self, target: str | Path):
        r = subprocess.run([self._tool("pg_dump"), "-Fc", "-f", str(target), *self._conn_args()], env=self._env(),
                           capture_output=True, text=True)
        if r.returncode:
            raise DatabaseError(f"pg_dump lỗi: {r.stderr.strip()[:400]}")

    def restore_from(self, source: str | Path):
        self.close()
        try:
            r = subprocess.run([self._tool("pg_restore"), "--clean", "--if-exists", "--no-owner", *self._conn_args(), str(source)],
                               env=self._env(), capture_output=True, text=True)
        finally:
            self.open()
        if r.returncode and not self.only_benign_restore_errors(r.stderr):
            raise DatabaseError(f"pg_restore lỗi: {r.stderr.strip()[:400]}")

    @staticmethod
    def only_benign_restore_errors(stderr: str) -> bool:
        """pg_restore bản mới hơn máy chủ có thể báo lỗi vô hại khi áp dụng tham số chỉ có ở bản mới (vd transaction_timeout, PG 17 → 16).
        Chỉ coi là thành công khi MỌI lỗi đều thuộc loại này."""
        errors = re.findall(r"pg_restore: error: (.*)", stderr)
        return bool(errors) and all("unrecognized configuration parameter" in e and
                                    re.search(r"transaction_timeout|idle_session_timeout|default_table_access_method", e + stderr) for e in errors)

    def clone(self):
        """Kết nối mới tới cùng CSDL (cùng thông tin đăng nhập, kể cả mật khẩu chỉ giữ trong bộ nhớ)."""
        c = PostgresDatabase.__new__(PostgresDatabase)
        BaseDatabase.__init__(c)
        import psycopg
        c._psycopg, c.errors, c.params, c.path = psycopg, (psycopg.Error,), dict(self.params), self.path
        c.open()
        return c

    def validate_dump(self, source: str | Path):
        r = subprocess.run([self._tool("pg_restore"), "-l", str(source)], env=self._env(), capture_output=True, text=True)
        if r.returncode:
            raise DatabaseError("File không phải bản sao lưu PostgreSQL hợp lệ (pg_dump -Fc).")


def open_database(target: str | Path) -> BaseDatabase:
    """Mở CSDL theo đường dẫn file SQLite hoặc URL postgresql://user[:mật khẩu]@host:port/tên_csdl."""
    return PostgresDatabase(str(target)) if is_pg_url(str(target)) else Database(target)


try:                                   # bộ nạp NUMERIC: số nguyên → int (SUM của BIGINT trả về NUMERIC trong PostgreSQL)
    from psycopg.adapt import Loader as _Loader

    class _IntegralNumericLoader(_Loader):
        def load(self, data):
            text = bytes(data).decode()
            if "." not in text and "e" not in text.lower() and text.lstrip("-").isdigit():
                return int(text)
            from decimal import Decimal
            d = Decimal(text)
            return int(d) if d == d.to_integral_value() else d
except ImportError:                     # chưa cài psycopg: chỉ dùng được SQLite
    _IntegralNumericLoader = None
