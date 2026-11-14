"""Fixture dùng chung: chạy các bài kiểm thử nghiệp vụ trên SQLite VÀ PostgreSQL.

PostgreSQL chỉ chạy khi đặt biến môi trường KETOAN_PG_TEST_URL, ví dụ:
    KETOAN_PG_TEST_URL=postgresql://postgres@127.0.0.1:54329/postgres
(tài khoản cần quyền tạo/xóa CSDL). Mỗi bài kiểm thử dùng một bản sao riêng của CSDL mẫu (CREATE DATABASE ... TEMPLATE).
"""
from __future__ import annotations

import os
import shutil
import uuid

import pytest

from ketoan.data.db import Database, PostgresDatabase, make_pg_url, parse_pg_url
from ketoan.data.seed import create_database
from ketoan.services.auth_service import authenticate
from ketoan.services.context import Session

PG_ADMIN = os.environ.get("KETOAN_PG_TEST_URL")
BACKENDS = ["sqlite"] + (["pg"] if PG_ADMIN else [])


def _admin_conn():
    import psycopg
    c = parse_pg_url(PG_ADMIN)
    return psycopg.connect(host=c["host"], port=c["port"], user=c["user"], password=c["password"], dbname="postgres", autocommit=True)


def pg_url(dbname: str) -> str:
    c = parse_pg_url(PG_ADMIN)
    return make_pg_url(c["host"], c["port"], dbname, c["user"], c["password"])


@pytest.fixture(scope="session")
def templates(tmp_path_factory):
    """CSDL mẫu dựng một lần cho cả phiên kiểm thử."""
    out = {}
    p = tmp_path_factory.mktemp("tpl") / "demo.db"
    create_database(p).close()
    out["sqlite"] = p
    if PG_ADMIN:
        name = "kt_tpl_" + uuid.uuid4().hex[:6]
        adm = _admin_conn()
        adm.execute(f'CREATE DATABASE "{name}" TEMPLATE template0 ENCODING \'UTF8\' LC_COLLATE \'C\' LC_CTYPE \'C.UTF-8\'')
        create_database(pg_url(name), reset=True).close()
        out["pg"] = name
        yield out
        adm.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        adm.close()
    else:
        yield out


@pytest.fixture(params=BACKENDS)
def backend(request):
    return request.param


@pytest.fixture()
def factory(backend, templates, tmp_path):
    """factory(company_id=1, username='admin', password='admin@123', same_db_as=None) → Session trên bản sao CSDL mẫu."""
    opened, dbs = [], []

    def make(company_id=1, username="admin", password="admin@123", same_db_as=None):
        if same_db_as is not None:                                  # kết nối thứ hai tới cùng CSDL (kiểm thử đa người dùng)
            db = same_db_as.db.clone()
        elif backend == "sqlite":
            p = tmp_path / f"work_{len(opened)}.db"
            shutil.copy(templates["sqlite"], p)
            db = Database(p)
        else:
            name = "kt_" + uuid.uuid4().hex[:8]
            adm = _admin_conn()
            adm.execute(f'CREATE DATABASE "{name}" TEMPLATE "{templates["pg"]}"')
            adm.close()
            dbs.append(name)
            db = PostgresDatabase(pg_url(name))
        opened.append(db)
        return Session(db, authenticate(db, username, password), company_id=company_id)

    yield make
    for d in opened:
        d.close()
    if dbs:
        adm = _admin_conn()
        for n in dbs:
            adm.execute(f'DROP DATABASE IF EXISTS "{n}" WITH (FORCE)')
        adm.close()
