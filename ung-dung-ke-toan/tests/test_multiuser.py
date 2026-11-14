"""Kiểm thử đa người dùng trên PostgreSQL: nhiều kết nối đồng thời tới cùng một CSDL.

Chỉ chạy khi có KETOAN_PG_TEST_URL (xem conftest.py). Mỗi người dùng = một kết nối + một Session riêng, chạy trong luồng riêng.
"""
from __future__ import annotations

import threading

import pytest

from ketoan.domain.constants import POSTED
from ketoan.services.context import BusinessError
from ketoan.services.voucher_service import VoucherService
from tests.conftest import PG_ADMIN

pytestmark = pytest.mark.skipif(not PG_ADMIN, reason="cần KETOAN_PG_TEST_URL (PostgreSQL)")


@pytest.fixture()
def pg_users(factory, backend):
    if backend != "pg":
        pytest.skip("chỉ PostgreSQL")
    a = factory()
    return a, factory(same_db_as=a, username="ketoantruong", password="ktt@123"), factory(same_db_as=a, username="ketoanvien", password="ktv@123")


def _simple(desc, amount=1000):
    return ({"vtype": "PKT", "voucher_date": "2026-12-10", "posting_date": "2026-12-10", "description": desc},
            [{"description": desc, "debit_account": "6422", "credit_account": "1111", "amount": amount}])


def _run_threads(fns):
    out, errs = [None] * len(fns), [None] * len(fns)

    def wrap(i, fn):
        try:
            out[i] = fn()
        except Exception as e:  # noqa: BLE001
            errs[i] = e
    ts = [threading.Thread(target=wrap, args=(i, f)) for i, f in enumerate(fns)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    return out, errs


def test_concurrent_numbering_has_no_duplicates(pg_users):
    a, b, c = pg_users
    def worker(s, n):
        return lambda: [VoucherService(s).save(*_simple(f"{s.user.username}-{k}")) for k in range(n)]
    out, errs = _run_threads([worker(a, 8), worker(b, 8), worker(c, 8)])
    assert errs == [None, None, None], errs
    numbers = [r["number"] for r in a.db.query("SELECT number FROM voucher WHERE company_id=1 AND vtype='PKT' AND posting_date='2026-12-10'")]
    assert len(numbers) == 24 == len(set(numbers))                       # 24 chứng từ, không trùng số


def test_two_users_post_same_voucher_only_one_wins(pg_users):
    a, b, _ = pg_users
    vid = VoucherService(a).save(*_simple("ghi sổ đồng thời"))
    out, errs = _run_threads([lambda: VoucherService(a).post(vid), lambda: VoucherService(b).post(vid)])
    assert sum(e is None for e in errs) == 1 and any("đã được ghi sổ" in str(e) for e in errs if e)
    assert a.db.scalar("SELECT COUNT(*) FROM ledger_entry WHERE voucher_id=?", (vid,)) == 2     # bút toán chỉ sinh một lần
    assert VoucherService(b).get(vid)["status"] == POSTED


def test_stale_edit_is_rejected_with_clear_message(pg_users):
    a, b, _ = pg_users
    vid = VoucherService(a).save(*_simple("bản gốc"))
    opened_by_a = VoucherService(a).get(vid)["version"]
    opened_by_b = VoucherService(b).get(vid)["version"]
    VoucherService(a).save(*_simple("A sửa trước", 2000), voucher_id=vid, expected_version=opened_by_a)
    with pytest.raises(BusinessError) as e:
        VoucherService(b).save(*_simple("B sửa sau trên bản cũ", 3000), voucher_id=vid, expected_version=opened_by_b)
    assert "đã được admin sửa" in str(e.value) and "tải lại" in str(e.value)
    assert VoucherService(a).get(vid)["lines"][0]["amount"] == 2000        # không bị ghi đè


def test_period_lock_visible_across_connections(pg_users):
    a, b, _ = pg_users
    from ketoan.services.period_service import PeriodService
    PeriodService(b).lock(2026, 12)
    with pytest.raises(BusinessError):
        VoucherService(a).save(*_simple("sau khi người khác khóa kỳ"))
    PeriodService(b).unlock(2026, 12)
    assert VoucherService(a).save(*_simple("sau khi mở khóa"))


def test_concurrent_depreciation_run_is_serialized(pg_users):
    a, b, _ = pg_users
    from ketoan.services.asset_service import AssetService
    out, errs = _run_threads([lambda: AssetService(a).apply(2026, 7), lambda: AssetService(b).apply(2026, 7)])
    assert sum(e is None for e in errs) == 1 and any("đã chạy" in str(e) for e in errs if e)
    assert a.db.scalar("SELECT COUNT(*) FROM period_run WHERE kind='ASSET' AND month=7") == 1


def test_pg_backup_and_restore_roundtrip(pg_users, tmp_path):
    a, _, _ = pg_users
    from ketoan.services.system_service import BackupService
    bk = BackupService(a, tmp_path / "bk")
    f = bk.backup()
    assert f.suffix == ".dump" and f.stat().st_size > 10_000
    n = a.db.scalar("SELECT COUNT(*) FROM voucher")
    VoucherService(a).save(*_simple("thêm sau khi sao lưu"))
    bk.restore(f)
    assert a.db.scalar("SELECT COUNT(*) FROM voucher") == n
    assert a.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action='Khôi phục dữ liệu'") == 1
