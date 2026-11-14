"""Kiểm thử giai đoạn 3: TSCĐ, CCDC, giá thành, mẫu báo cáo, thuế hỗ trợ, chuyển số dư cuối năm."""
from __future__ import annotations

import shutil
from decimal import Decimal

import pytest

from ketoan.data.db import SCHEMA_FILE, Database
from ketoan.data.seed import create_database
from ketoan.services.asset_service import AssetService, PrepaidService
from ketoan.services.auth_service import authenticate
from ketoan.services.closing_service import ClosingService
from ketoan.services.context import BusinessError, PermissionDenied, Session
from ketoan.services.cost_service import CostService
from ketoan.services.inventory_service import InventoryService
from ketoan.services.ledger_service import LedgerService
from ketoan.services.report_engine import ReportEngine, accounts_of, parse
from ketoan.services.tax_service import TaxService
from ketoan.services.voucher_service import VoucherService
from ketoan.services.yearend_service import YearEndService


@pytest.fixture(scope="module")
def demo_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("db3") / "demo.db"
    create_database(p).close()
    return p


@pytest.fixture()
def s(demo_path, tmp_path):
    p = tmp_path / "work.db"
    shutil.copy(demo_path, p)
    db = Database(p)
    yield Session(db, authenticate(db, "admin", "admin@123"), company_id=1)
    db.close()


def s2_of(s):
    return Session(s.db, s.user, company_id=2)


def balanced(s, a="2026-01-01", b="2026-12-31"):
    return all(v == 0 for v in LedgerService(s).trial_balance(a, b).balanced.values())


def test_migration_v3(tmp_path):
    db = Database(tmp_path / "v1.db")
    db.conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    db.execute("INSERT INTO meta VALUES('schema_version','1')")
    assert db.migrate() == [2, 3] and db.schema_version() == 3
    for t in ("prepaid_item", "period_run", "cost_sheet", "report_template", "report_line", "tax_adjustment", "tax_param"):
        assert db.scalar("SELECT 1 FROM sqlite_master WHERE name=?", (t,)), t


# ------------------------------------------------------------------ TSCĐ & CCDC
def test_depreciation_run_sequence_undo_and_balance(s):
    a = AssetService(s)
    assert {x["code"]: x["accumulated"] for x in a.assets("2026-06-30")} == {"TS001": 150_000_000, "TS002": 79_999_998}   # 120M+6×5M ; 60M+6×3.333.333
    pre = {r.code: r.amount for r in a.preview(2026, 7)}
    assert pre == {"TS001": 5_000_000, "TS002": 3_333_333}
    with pytest.raises(BusinessError):
        a.apply(2026, 9)                                  # chưa chạy tháng 7, 8
    with pytest.raises(BusinessError):
        a.apply(2026, 6)                                  # tháng 6 đã chạy / đã khóa
    vid = a.apply(2026, 7, post=True)
    assert VoucherService(s).get(vid)["status"] == "POSTED" and balanced(s)
    a.apply(2026, 8)                                      # nháp
    assert a.assets("2026-08-31")[0]["accumulated"] == 160_000_000
    with pytest.raises(BusinessError):
        a.undo(2026, 7)                                   # phải hoàn tác từ tháng mới nhất
    a.undo(2026, 8)
    a.undo(2026, 7)
    assert not s.db.scalar("SELECT 1 FROM voucher WHERE id=?", (vid,)) and a.assets("2026-12-31")[0]["accumulated"] == 150_000_000
    assert balanced(s)


def test_last_month_takes_remainder_and_disposal(s):
    s.db.execute("""INSERT INTO fixed_asset(company_id, code, name, asset_account, depreciation_account, expense_account, original_cost,
                    start_date, useful_months, department) VALUES(1,'TS9','Thử','2111','2141','6422',100,'2026-07-01',3,'KT')""")
    a = AssetService(s)
    got = []
    for m in (7, 8, 9):
        got.append({r.code: r.amount for r in a.preview(2026, m)}.get("TS9"))
        a.apply(2026, m)
    assert got == [33, 33, 34]                            # tổng đúng 100, tháng cuối nhận phần dư
    assert "TS9" not in {r.code for r in a.preview(2026, 10)}
    ts1 = s.db.scalar("SELECT id FROM fixed_asset WHERE company_id=1 AND code='TS001'")
    a.dispose(ts1, "2026-09-15")
    assert "TS001" not in {r.code for r in a.preview(2026, 10)}   # ngừng từ tháng sau tháng ghi giảm


def test_prepaid_allocation_and_validation(s):
    p = PrepaidService(s)
    assert {r.code: r.amount for r in p.preview(2026, 8)} == {"CP001": 3_000_000, "CC001": 2_000_000}
    p.apply(2026, 7, post=True)
    p.apply(2026, 8, post=True)
    items = {i["code"]: i for i in p.items("2026-08-31")}
    assert items["CC001"]["allocated"] == 2_000_000 and items["CP001"]["remaining"] == 36_000_000 - 8 * 3_000_000
    with pytest.raises(BusinessError):
        p.delete_item(items["CC001"]["id"])               # đã phân bổ => không xóa
    with pytest.raises(BusinessError):
        p.save_item(None, {"code": "X", "name": "X", "total_amount": 0, "months": 0, "start_date": "xx", "source_account": "999",
                           "expense_account": "6422"})
    assert balanced(s)


# ------------------------------------------------------------------ giá thành
def test_cost_methods_and_transfer(s):
    s2 = s2_of(s)
    cs = CostService(s2)
    rows, _ = cs.calculate("GD", "2026-03-01", "2026-03-31")
    by = {r.code: r for r in rows}
    assert by["CT01"].direct == 716_000_000 and by["CT02"].direct == 50_000_000 and cs.common_unallocated == 6_000_000
    rows, _ = cs.calculate("GD", "2026-03-01", "2026-03-31", {by["CT01"].project_id: {"quantity": 2, "wip_end": 100_000_000}})
    r = {x.code: x for x in rows}["CT01"]
    assert (r.total, r.unit) == (616_000_000, Decimal("308000000"))
    rows, _ = cs.calculate("KDM", "2026-03-01", "2026-03-31")
    r = {x.code: x for x in rows}
    assert r["CT01"].common + r["CT02"].common == 6_000_000 and r["CT01"].common == 5_608_355     # phân bổ theo CP trực tiếp
    rows, _ = cs.calculate("DM", "2026-03-01", "2026-03-31", {r["CT01"].project_id: {"quantity": 10, "norm_unit": 70_000_000}})
    x = {y.code: y for y in rows}["CT01"]
    assert (x.standard_total, x.variance) == (700_000_000, 16_000_000) and round(x.variance_pct, 2) == 2.29
    rows, _ = cs.calculate("KDD", "2026-03-01", "2026-03-31", {r["CT01"].project_id: {"quantity": 4, "wip_end": 999}})
    assert {y.code: y for y in rows}["CT01"].wip_end == 0         # không dở dang bỏ qua DDCK
    # lưu + kết chuyển
    rows, _ = cs.calculate("GD", "2026-03-01", "2026-03-31", {r["CT01"].project_id: {"quantity": 2, "wip_end": 100_000_000}})
    with pytest.raises(BusinessError):
        cs.save_and_transfer("GD", "2026-03-01", "2026-03-31", rows, "999")
    vid = cs.save_and_transfer("GD", "2026-03-01", "2026-03-31", rows, "632")
    v = VoucherService(s2).get(vid)
    assert v["status"] == "DRAFT" and [(l["debit_account"], l["credit_account"], l["amount"]) for l in v["lines"]] == [("632", "154", 616_000_000)]
    VoucherService(s2).post(vid)
    again, _ = cs.calculate("GD", "2026-03-01", "2026-03-31")      # chi phí trực tiếp không đổi sau khi đã kết chuyển
    assert {y.code: y for y in again}["CT01"].direct == 716_000_000
    with pytest.raises(BusinessError):
        cs.save_and_transfer("GD", "2026-03-01", "2026-03-31", again, "632")   # không kết chuyển trùng
    pl = cs.project_ledger(rows[0].project_id, "2026-03-01", "2026-03-31")
    assert pl["closing"] == 716_000_000 - 616_000_000 and pl["by_item"]["Nhân công trực tiếp"] == 85_000_000
    cs.undo_transfer("GD", "2026-03-01", "2026-03-31")
    assert not s.db.scalar("SELECT 1 FROM voucher WHERE id=?", (vid,))
    # dở dang cuối kỳ chuyển thành đầu kỳ của kỳ sau
    assert cs._previous_wip(rows[0].project_id, "2026-04-01", "GD") == 100_000_000
    assert balanced(s2, "2026-01-01", "2026-12-31")


# ------------------------------------------------------------------ mẫu báo cáo
def test_formula_parser_and_validation():
    assert accounts_of(parse("DN(111,112)+[A]-PSNDU(511;911)*2")) == ["111", "112", "511"]
    errs = ReportEngine.validate_lines([{"code": "A", "label": "a", "formula": "[B]+1"}, {"code": "B", "label": "b", "formula": "[A]"},
                                        {"code": "C", "label": "c", "formula": "XX(1)"}, {"code": "D", "label": "d", "formula": "[Z]"},
                                        {"code": "E", "label": "e", "formula": "DN(1"}, {"code": "A", "label": "dup", "formula": ""}])
    text = " | ".join(errs)
    for frag in ("vòng tròn", "XX", "[Z]", "bị lặp"):
        assert frag in text, frag
    assert ReportEngine.validate_lines([{"code": "A", "label": "a", "formula": "DN(111)/2-3"}]) == []


def test_demo_templates_reconcile_and_are_unverified(s):
    eng = ReportEngine(s)
    bs = [t for t in eng.templates("BS")][0]
    assert bs["verified"] == 0
    lines = {l["code"]: l for l in eng.evaluate(bs["id"], "2026-01-01", "2026-12-31")}
    assert lines["K"]["value"] == 0 and lines["A9"]["value"] == lines["B9"]["value"] > 0
    assert lines["A9"]["open_value"] == lines["B9"]["open_value"] == 2_608_500_000        # cột Đầu năm khớp số dư đầu năm
    is_ = [t for t in eng.templates("IS")][0]
    lines = {l["code"]: l for l in eng.evaluate(is_["id"], "2026-01-01", "2026-12-31")}
    assert lines["10"]["value"] == TaxService(s).corporate_income(2026, "2026-12-31")["profit"]   # hai đường tính độc lập khớp nhau
    assert lines["1"]["accounts"] == ["511"]                                                      # truy ngược được TK


def test_template_import_versioning_and_verification_rights(s):
    eng = ReportEngine(s)
    rows = [{"code": "1", "label": "Tiền", "formula": "DN(111)"}, {"code": "2", "label": "Gấp đôi", "formula": "[1]*2"}]
    tid = eng.import_template("T1", "Mẫu thử", "BS", "TT133_2016", "2026-01-01", "Phụ lục X", rows)
    tid2 = eng.import_template("T1", "Mẫu thử", "BS", "TT133_2016", "2026-01-01", "Phụ lục X", rows)
    assert s.db.scalar("SELECT version FROM report_template WHERE id=?", (tid2,)) == 2
    with pytest.raises(BusinessError):
        eng.import_template("BAD", "x", "BS", "", "", "", [{"code": "1", "label": "a", "formula": "[1]"}])   # vòng lặp => không nhập
    assert not s.db.scalar("SELECT 1 FROM report_template WHERE code='BAD'")
    with pytest.raises(BusinessError):
        eng.verify_template(tid, "ngắn")                      # thiếu căn cứ
    eng.verify_template(tid, "Thông tư 000/0000 – phụ lục X – đã đối chiếu Công báo")
    assert s.db.scalar("SELECT verified FROM report_template WHERE id=?", (tid,)) == 1
    clerk = Session(s.db, authenticate(s.db, "ketoanvien", "ktv@123"), company_id=1)
    with pytest.raises(PermissionDenied):
        ReportEngine(clerk).verify_template(tid2, "đã kiểm chứng đầy đủ căn cứ")
    with pytest.raises(PermissionDenied):
        ReportEngine(clerk).import_template("T2", "x", "IS", "", "", "", rows)


# ------------------------------------------------------------------ thuế hỗ trợ
def test_vat_reconciliation_and_summary(s):
    t = TaxService(s)
    sm = t.vat_summary("2026-01-01", "2026-12-31")
    assert sm["input_inv"] == sm["input_ledger"] and sm["output_inv"] == sm["output_ledger"] and sm["output_inv"] > sm["input_inv"] > 0
    assert sm["output_by_rate"][0][0] == "10%"                                                   # thuế suất lấy từ dòng chứng từ, không suy đoán
    assert not [r for r in t.invoice_reconciliation("2026-01-01", "2026-12-31") if r["severity"] == "REVIEW"]
    vid = s.db.scalar("SELECT id FROM voucher WHERE company_id=1 AND vtype='BKBH' AND status='POSTED' ORDER BY id LIMIT 1")
    s.db.execute("UPDATE voucher SET total_tax=total_tax+1000, invoice_no=NULL WHERE id=?", (vid,))   # giả lập sai lệch
    issues = t.invoice_reconciliation("2026-01-01", "2026-12-31")
    assert any(r["diff"] == 1000 for r in issues) and any("thiếu" in r["issue"] for r in issues)


def test_corporate_income_requires_user_rate(s):
    t = TaxService(s)
    r = t.corporate_income(2026, "2026-12-31")
    assert r["rate"] is None and r["tax"] is None                        # chưa nhập thuế suất => không tính, không tự đoán
    with pytest.raises(BusinessError):
        t.set_param(2026, "tndn_rate", "20", "")                         # thiếu căn cứ
    t.save_adjustments(2026, [{"kind": "INC", "label": "Chi phí không hợp lệ", "amount": 10_000_000}, {"kind": "DEC", "label": "Thu nhập miễn", "amount": 4_000_000}])
    t.set_param(2026, "tndn_rate", "20", "Giá trị thử nghiệm do người dùng nhập")
    r = t.corporate_income(2026, "2026-12-31")
    assert r["taxable"] == r["profit"] + 6_000_000 and r["tax"] == round(r["taxable"] * 20 / 100)


def test_personal_income_summary(s):
    rows = {r["code"]: r for r in TaxService(s).personal_income("2026-01-01", "2026-12-31")}
    assert rows["NV001"]["accrued"] == 30_000_000 and rows["NV001"]["withheld"] == 1_500_000


# ------------------------------------------------------------------ chuyển số dư cuối năm
def test_year_end_carry_forward(s):
    ye = YearEndService(s)
    assert any("kết chuyển" in p for p in ye.preview(2026)["problems"])
    inv = InventoryService(s)
    inv.costing_apply("2026-07-01", "2026-10-31")
    vs = VoucherService(s)
    vs.post(vs.save({"vtype": "PNK", "voucher_date": "2026-12-05", "posting_date": "2026-12-05"},
                    [{"debit_account": "156", "credit_account": "1111", "item": "HH005", "warehouse": "KHO02", "quantity": 1, "unit_price": 4_600_000}]))
    ClosingService(s).execute("2026-07-01", "2026-12-31")
    pv = ye.preview(2026)
    assert pv["problems"] == [], pv["problems"]
    ye.carry_forward(2026)
    ob = s.db.query("SELECT account_code, SUM(debit) d, SUM(credit) c FROM opening_balance WHERE company_id=1 AND year=2027 GROUP BY account_code")
    assert sum(r["d"] for r in ob) == sum(r["c"] for r in ob) > 0
    assert not any(r["account_code"] == "4212" for r in ob) and any(r["account_code"] == "4211" for r in ob)
    tb = LedgerService(s).trial_balance("2027-01-01", "2027-01-31")
    assert tb.total.ob_d == tb.total.ob_c == sum(r["d"] for r in ob) and all(v == 0 for v in tb.balanced.values())
    assert s.db.scalar("SELECT COUNT(*) FROM opening_stock WHERE company_id=1 AND year=2027") >= 1
    assert s.db.scalar("SELECT COUNT(*) FROM fiscal_year WHERE company_id=1 AND year=2027") == 1
