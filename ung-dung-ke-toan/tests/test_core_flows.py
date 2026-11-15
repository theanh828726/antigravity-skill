"""Kiểm thử các luồng nghiệp vụ quan trọng:
nhập chứng từ → kiểm tra → ghi sổ → lên sổ/báo cáo → truy ngược chứng từ; khóa kỳ; phân quyền; kết chuyển; sao lưu."""
from __future__ import annotations

import pytest

from ketoan.domain.constants import CHECKED, DRAFT, POSTED, SEV_BLOCK
from ketoan.domain.money import fmt_money, line_amount, round_money, tax_amount, to_decimal
from ketoan.services.auth_service import authenticate
from ketoan.services.alert_service import AlertService
from ketoan.services.catalog_service import CatalogService
from ketoan.services.closing_service import ClosingService
from ketoan.services.context import BusinessError, PermissionDenied, Session
from ketoan.services.ledger_service import LedgerService
from ketoan.services.period_service import PeriodService
from ketoan.services.system_service import BackupService, OpeningBalanceService
from ketoan.services.voucher_service import ValidationFailed, VoucherService


@pytest.fixture()
def session(factory):
    return factory()


def as_user(s: Session, username, pwd):
    return Session(s.db, authenticate(s.db, username, pwd), company_id=s.company_id)


# ------------------------------------------------------------------ tiền tệ
def test_money_policy():
    assert to_decimal("1.234.567") == 1234567
    assert to_decimal("1.234.567,5") == to_decimal("1234567.5")
    assert to_decimal("1,234,567.5") == to_decimal("1234567.5")
    assert to_decimal("12,5") == to_decimal("12.5")
    assert to_decimal("(1.000)") == -1000
    assert round_money("2.5") == 3 and round_money("-2.5") == -3          # ROUND_HALF_UP
    assert line_amount("3", "333333.335") == 1000000
    assert tax_amount(1_620_000, "10") == 162_000
    assert tax_amount(15, "10") == 2                                       # 1,5 -> 2
    assert fmt_money(-1234567) == "(1.234.567)"


# ------------------------------------------------------------------ luồng chính
def test_full_flow_voucher_to_reports_and_back(session):
    vs, ls = VoucherService(session), LedgerService(session)
    before = ls.account_detail("131", "2026-11-01", "2026-11-30", None)
    tb_before = ls.trial_balance("2026-11-01", "2026-11-30")
    vid = vs.save({"vtype": "BKBH", "voucher_date": "2026-11-14", "posting_date": "2026-11-14", "partner_code": "KH001",
                   "tax_code": "0109990101", "description": "Bán hàng kiểm thử", "invoice_no": "T0001",
                   "invoice_series": "1C26TST", "invoice_date": "2026-11-14"},
                  [{"description": "Bán bàn phím", "debit_account": "131", "credit_account": "5111", "debit_partner": "KH001",
                    "item": "HH003", "warehouse": "KHO01", "quantity": "3", "unit_price": "1.232.000", "tax_rate": "10"}])
    v = vs.get(vid)
    assert v["status"] == DRAFT
    assert (v["total_amount"], v["total_tax"], v["total_payment"]) == (3_696_000, 369_600, 4_065_600)
    # Chưa ghi sổ => chưa lên sổ
    assert ls.account_detail("131", "2026-11-01", "2026-11-30")["total_d"] == before["total_d"]
    vs.check(vid)
    assert vs.get(vid)["status"] == CHECKED
    vs.post(vid)
    assert vs.get(vid)["status"] == POSTED
    # Lên sổ chi tiết 131 đúng số tiền thanh toán, có voucher_id để truy ngược
    after = ls.account_detail("131", "2026-11-01", "2026-11-30")
    assert after["total_d"] - before["total_d"] == 4_065_600
    row = [r for r in after["rows"] if r["voucher_id"] == vid]
    assert row and sum(r["debit"] for r in row) == 4_065_600
    assert vs.get(row[0]["voucher_id"])["number"] == v["number"]            # truy ngược chứng từ gốc
    # Nhật ký chung có đủ bút toán (hàng + thuế), cân đối
    nkc = [r for r in ls.general_journal("2026-11-14", "2026-11-14") if r["voucher_id"] == vid]
    assert sum(r["debit"] for r in nkc) == sum(r["credit"] for r in nkc) == 4_065_600
    assert {r["account_code"] for r in nkc} == {"131", "5111", "33311"}
    # CĐSPS cân đối và phản ánh phát sinh mới
    tb = ls.trial_balance("2026-11-01", "2026-11-30")
    assert all(v == 0 for v in tb.balanced.values())
    assert tb.total.ps_d - tb_before.total.ps_d == 4_065_600
    # Bỏ ghi sổ => số liệu rút khỏi sổ
    vs.unpost(vid)
    assert ls.account_detail("131", "2026-11-01", "2026-11-30")["total_d"] == before["total_d"]


def test_unbalanced_voucher_is_blocked(session):
    vs = VoucherService(session)
    vid = vs.save({"vtype": "PKT", "voucher_date": "2026-11-14", "posting_date": "2026-11-14", "description": "Lệch"},
                  [{"description": "a", "debit_account": "6422", "amount": 1000},
                   {"description": "b", "credit_account": "1111", "amount": 900}])
    with pytest.raises(ValidationFailed) as e:
        vs.post(vid)
    assert any(i.rule == "lech_no_co" and i.difference == 100 for i in e.value.issues)
    assert not session.db.scalar("SELECT 1 FROM ledger_entry WHERE voucher_id=?", (vid,))


def test_required_partner_and_parent_account_blocked(session):
    vs = VoucherService(session)
    vid = vs.save({"vtype": "PT", "voucher_date": "2026-11-14", "posting_date": "2026-11-14"},
                  [{"debit_account": "111", "credit_account": "131", "amount": 5000}])
    rules = {i.rule for i in vs.validate(vid) if i.severity == SEV_BLOCK}
    assert {"tk_tong_hop", "thieu_doi_tuong"} <= rules


def test_locked_period(session):
    vs, ps = VoucherService(session), PeriodService(session)
    with pytest.raises(BusinessError):
        vs.save({"vtype": "PKT", "voucher_date": "2026-02-10", "posting_date": "2026-02-10"},
                [{"debit_account": "6422", "credit_account": "1111", "amount": 1}])
    posted_in_feb = session.db.scalar("SELECT id FROM voucher WHERE company_id=1 AND status='POSTED' AND posting_date LIKE '2026-02%'")
    with pytest.raises(BusinessError):
        vs.unpost(posted_in_feb)
    with pytest.raises(BusinessError):
        ps.unlock(2026, 3)                     # phải mở từ kỳ sau về trước
    ps.unlock(2026, 6)
    assert not ps.is_locked("2026-06-15")


def test_permissions(session):
    viewer = as_user(session, "xem", "xem@123")
    with pytest.raises(PermissionDenied):
        VoucherService(viewer).save({"vtype": "PKT", "voucher_date": "2026-11-14", "posting_date": "2026-11-14"},
                                    [{"debit_account": "6422", "credit_account": "1111", "amount": 1}])
    clerk = as_user(session, "ketoanvien", "ktv@123")
    vid = VoucherService(clerk).save({"vtype": "PKT", "voucher_date": "2026-11-14", "posting_date": "2026-11-14"},
                                     [{"debit_account": "6422", "credit_account": "1111", "amount": 1}])
    with pytest.raises(PermissionDenied):
        VoucherService(clerk).post(vid)          # kế toán viên không có quyền ghi sổ
    with pytest.raises(PermissionDenied):
        PeriodService(clerk).lock(2026, 7)
    with pytest.raises(BusinessError):
        authenticate(session.db, "admin", "sai-mat-khau")


def test_transaction_rollback_on_error(session):
    """Lỗi giữa chừng => không có dữ liệu dở dang."""
    vs = VoucherService(session)
    n_before = session.db.scalar("SELECT COUNT(*) FROM voucher")
    with pytest.raises(BusinessError):
        vs.save({"vtype": "BKBH", "voucher_date": "2026-11-14", "posting_date": "2026-11-14"},
                [{"debit_account": "131", "credit_account": "5111", "debit_partner": "KH_KHONG_CO", "amount": 10}])
    assert session.db.scalar("SELECT COUNT(*) FROM voucher") == n_before


def test_alert_center_finds_all_demo_cases(session):
    alerts = AlertService(session).collect("2026-01-01", "2026-12-31")
    rules = {a.rule for a in alerts}
    for r in ("lech_no_co", "thieu_doi_tuong", "trung_hoa_don", "ton_am", "cong_no_bat_thuong", "lech_thue", "ky_khoa"):
        assert r in rules, r
    for a in alerts:
        assert a.message and a.target            # mỗi cảnh báo có nguyên nhân và nơi mở xử lý


def test_closing_preview_execute_undo(session):
    cs, ls = ClosingService(session), LedgerService(session)
    preview = cs.preview("2026-07-01", "2026-07-31")
    assert preview and any(l["debit_account"] == "5111" for l in preview)
    vid = cs.execute("2026-07-01", "2026-07-31")
    tb = ls.trial_balance("2026-07-01", "2026-07-31")
    rows = {r.code: r for r in tb.rows}
    assert rows["511"].cb_c == rows["511"].ob_c and rows["911"].cb_d == rows["911"].cb_c == 0
    assert cs.preview("2026-07-01", "2026-07-31") == []        # không kết chuyển trùng
    cs.undo(vid)
    assert cs.preview("2026-07-01", "2026-07-31") == preview


def test_catalog_import_validation(session):
    cat = CatalogService(session)
    ok, errors = cat.import_rows("customer", [
        {"_row": 2, "code": "KH900", "name": "Khách mới", "tax_code": "0100000999"},
        {"_row": 3, "code": "", "name": "Thiếu mã"},
        {"_row": 4, "code": "KH900", "name": "Trùng mã trong file"},
    ], dry_run=True)
    assert ok == 1 and {e[0] for e in errors} == {3, 4}
    ok, errors = cat.import_rows("customer", [{"_row": 2, "code": "KH901", "name": "Khách A"}], dry_run=False)
    assert ok == 1 and not errors and cat.id_by_code("partner", "KH901")
    with pytest.raises(BusinessError):
        cat.delete("customer", cat.id_by_code("partner", "KH001"))   # đã phát sinh => không xóa


def test_opening_balance_and_backup_restore(session, tmp_path):
    ob = OpeningBalanceService(session)
    with pytest.raises(BusinessError):
        ob.save(2026, [{"account_code": "131", "debit": 1}])     # thiếu đối tượng; tháng 1 cũng đã khóa
    bk = BackupService(session, tmp_path / "bk")
    f = bk.backup()
    n = session.db.scalar("SELECT COUNT(*) FROM voucher")
    VoucherService(session).save({"vtype": "PKT", "voucher_date": "2026-11-14", "posting_date": "2026-11-14"},
                                 [{"debit_account": "6422", "credit_account": "1111", "amount": 1}])
    assert session.db.scalar("SELECT COUNT(*) FROM voucher") == n + 1
    bk.restore(f)
    assert session.db.scalar("SELECT COUNT(*) FROM voucher") == n
    assert session.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action='Khôi phục dữ liệu'") == 1
