"""Kiểm thử bảo mật: đăng nhập, mật khẩu, phân quyền, dữ liệu nhập từ bên ngoài."""
from __future__ import annotations

import pytest

from ketoan.services import auth_service as au
from ketoan.services.auth_service import MAX_FAILED, authenticate, change_password, create_user, validate_password
from ketoan.services.context import BusinessError, PermissionDenied
from ketoan.services.voucher_service import VoucherService


def test_wrong_password_is_generic_and_audited(factory):
    s = factory()
    for who in ("admin", "khong_ton_tai"):
        with pytest.raises(BusinessError) as e:
            authenticate(s.db, who, "sai-mat-khau-1")
        assert str(e.value) == au.GENERIC_FAIL                      # không lộ tên đăng nhập có tồn tại hay không
    assert s.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action='Đăng nhập thất bại'") == 2


def test_lockout_after_repeated_failures_then_expires(factory):
    s = factory()
    for _ in range(MAX_FAILED):
        with pytest.raises(BusinessError):
            authenticate(s.db, "ketoanvien", "sai-mat-khau-1")
    with pytest.raises(BusinessError) as e:
        authenticate(s.db, "ketoanvien", "ktv@123")                    # đúng mật khẩu nhưng đang bị khóa tạm
    assert "tạm khóa" in str(e.value)
    s.db.execute("UPDATE app_user SET locked_until='2000-01-01T00:00:00' WHERE username='ketoanvien'")   # hết hạn khóa
    assert authenticate(s.db, "ketoanvien", "ktv@123").username == "ketoanvien"
    assert s.db.scalar("SELECT failed_attempts FROM app_user WHERE username='ketoanvien'") == 0


def test_default_password_forces_change_and_policy(factory):
    s = factory()
    u = authenticate(s.db, "admin", "admin@123")
    assert u.must_change                                              # mật khẩu mặc định → phải đổi
    for bad in ("short1", "chitoanchu", "12345678", "admin@123", "Admin"):
        with pytest.raises(BusinessError):
            validate_password(bad, "admin")
    with pytest.raises(BusinessError):
        change_password(s.db, "admin", "sai-mat-khau-1", "MatKhauMoi2026")          # phải nhập đúng mật khẩu cũ
    change_password(s.db, "admin", "admin@123", "MatKhauMoi2026")
    assert not authenticate(s.db, "admin", "MatKhauMoi2026").must_change
    with pytest.raises(BusinessError):
        authenticate(s.db, "admin", "admin@123")                        # mật khẩu cũ hết hiệu lực


def test_hash_rounds_upgraded_on_login(factory, monkeypatch):
    s = factory()
    monkeypatch.setattr(au, "PBKDF2_ROUNDS", 30_000)
    assert s.db.scalar("SELECT pwd_rounds FROM app_user WHERE username='xem'") == 20_000
    authenticate(s.db, "xem", "xem@123")
    assert s.db.scalar("SELECT pwd_rounds FROM app_user WHERE username='xem'") == 30_000      # nâng cấp khi đăng nhập thành công
    assert authenticate(s.db, "xem", "xem@123")                                                 # vẫn đăng nhập được


def test_new_users_must_meet_policy(factory):
    s = factory()
    with pytest.raises(BusinessError):
        create_user(s.db, "nv_moi", "Nhân viên", "KTV", "abc123")
    create_user(s.db, "nv_moi", "Nhân viên", "KTV", "MatKhau2026x")
    assert authenticate(s.db, "nv_moi", "MatKhau2026x").role_code == "KTV"


def test_permissions_enforced_in_service_layer(factory):
    s = factory()
    viewer = factory(username="xem", password="xem@123")
    clerk = factory(same_db_as=s, username="ketoanvien", password="ktv@123")
    hdr = {"vtype": "PKT", "voucher_date": "2026-12-10", "posting_date": "2026-12-10"}
    lines = [{"debit_account": "6422", "credit_account": "1111", "amount": 1}]
    with pytest.raises(PermissionDenied):
        VoucherService(viewer).save(hdr, lines)
    vid = VoucherService(clerk).save(hdr, lines)
    for fn in (lambda: VoucherService(clerk).post(vid), lambda: VoucherService(viewer).delete(vid)):
        with pytest.raises(PermissionDenied):
            fn()


def test_sql_metacharacters_are_data_not_code(factory):
    s = factory()
    from ketoan.services.catalog_service import CatalogService
    evil = "x'; DROP TABLE voucher; --"
    cat = CatalogService(s)
    cat.save("customer", {"code": "KH_EVIL", "name": evil})
    assert [r["name"] for r in cat.rows("customer", "DROP TABLE")] == [evil]       # tìm kiếm cũng tham số hóa
    assert s.db.scalar("SELECT COUNT(*) FROM voucher") > 0                          # bảng vẫn còn


def test_excel_export_neutralizes_formulas(tmp_path):
    from openpyxl import load_workbook
    from ketoan.reports.export import export_excel
    f = tmp_path / "x.xlsx"
    export_excel(str(f), "T", "", "C", ["Tên", "Số"], [["=HYPERLINK(\"http://evil\",\"x\")", 1], ["+cmd|' /C calc'!A0", 2], ["bình thường", 3]])
    ws = load_workbook(f).active
    assert ws["A6"].data_type == "s" and ws["A6"].value.startswith("=")              # lưu dạng văn bản, không phải công thức
    assert ws["A7"].data_type == "s" and ws["A8"].data_type == "s"


def test_xml_with_doctype_rejected(tmp_path):
    from ketoan.services.xml_invoice import parse_file
    bomb = tmp_path / "b.xml"
    bomb.write_text('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><HDon><DLHDon/></HDon>', encoding="utf-8")
    with pytest.raises(BusinessError) as e:
        parse_file(bomb)
    assert "DOCTYPE" in str(e.value)
