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

SCHEMA_VERSION = "1"
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
            self.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (SCHEMA_VERSION,))
            self.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('signature', ?)", (APP_SIGNATURE,))

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
