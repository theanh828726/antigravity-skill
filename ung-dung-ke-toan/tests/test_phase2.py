"""Kiểm thử giai đoạn 2: migration, kho & tính giá xuất kho, công nợ – tuổi nợ, xuất kho hàng loạt,
đối chiếu doanh thu – giá vốn, đọc hóa đơn XML."""
from __future__ import annotations

import shutil

import pytest

from ketoan.data.db import SCHEMA_FILE, Database
from ketoan.data.seed import create_database, write_sample_invoices
from ketoan.domain.constants import POSTED
from ketoan.domain.money import to_decimal
from ketoan.services.alert_service import AlertService
from ketoan.services.auth_service import authenticate
from ketoan.services.context import BusinessError, Session
from ketoan.services.debt_service import DebtService
from ketoan.services.inventory_service import InventoryService
from ketoan.services.ledger_service import LedgerService
from ketoan.services.trade_service import TradeService
from ketoan.services.voucher_service import VoucherService
from ketoan.services.xml_invoice import XmlInvoiceService, parse_file


@pytest.fixture(scope="module")
def demo_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("db2") / "demo.db"
    create_database(p).close()
    return p


@pytest.fixture()
def s(demo_path, tmp_path):
    p = tmp_path / "work.db"
    shutil.copy(demo_path, p)
    db = Database(p)
    yield Session(db, authenticate(db, "admin", "admin@123"), company_id=1)
    db.close()


def _tb_balanced(s, a="2026-01-01", b="2026-12-31"):
    return all(v == 0 for v in LedgerService(s).trial_balance(a, b).balanced.values())


# ------------------------------------------------------------------ migration
def test_migration_upgrades_v1_database(tmp_path):
    p = tmp_path / "v1.db"
    db = Database(p)
    db.conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    db.execute("INSERT INTO meta VALUES('schema_version','1')")
    db.execute("INSERT INTO company(code, name) VALUES('X','X')")
    db.execute("INSERT INTO partner(company_id, code, name, payment_terms) VALUES(1,'P','P',15)")
    db.execute("""INSERT INTO voucher(company_id, vtype, number, voucher_date, posting_date, partner_id, invoice_date)
                  VALUES(1,'BKBH','BH1','2026-03-01','2026-03-01',1,'2026-03-02')""")
    assert db.migrate() == [2]
    assert db.schema_version() == 2
    assert db.scalar("SELECT due_date FROM voucher") == "2026-03-17"
    assert db.scalar("SELECT costing_method FROM company") == "BQCK"
    assert db.migrate() == []                      # chạy lại không làm gì
    db.close()


# ------------------------------------------------------------------ kho & tính giá
def test_opening_stock_nxt_and_card(s):
    inv = InventoryService(s)
    assert all(d == 0 for *_, d in inv.opening_vs_ledger(2026))
    hh005 = s.db.scalar("SELECT id FROM item WHERE company_id=1 AND code='HH005'")
    kho2 = s.db.scalar("SELECT id FROM warehouse WHERE company_id=1 AND code='KHO02'")
    rows = {(r.item_code, r.warehouse_code): r for r in inv.nxt("2026-01-01", "2026-12-31")}
    r = rows[("HH005", "KHO02")]
    assert (r.ob_q, r.ob_v, r.out_q, r.cb_q) == (2, 9_200_000, 3, -1)
    card = inv.stock_card(hh005, kho2, "2026-01-01", "2026-12-31")
    assert card["closing_q"] == -1 and card["rows"][-1]["bal_q"] == -1
    # tổng giá trị tồn cuối NXT = số dư TK 156 trên sổ
    total = sum(x.cb_v for x in rows.values())
    assert total == LedgerService(s).balance_at("156", "2026-01-01", "2026-12-31")


def test_costing_bqck_apply_is_idempotent_and_balanced(s):
    inv = InventoryService(s)
    with pytest.raises(BusinessError):
        inv.costing_preview("2026-06-01", "2026-07-31")          # tháng 6 đã khóa
    with pytest.raises(BusinessError):
        inv.costing_preview("2026-07-05", "2026-07-31")          # không trọn tháng
    pre = inv.costing_preview("2026-07-01", "2026-10-31")
    assert pre.changes and pre.method == "BQCK"
    before_632 = LedgerService(s).balance_at("632", "2026-07-01", "2026-10-31")
    res = inv.costing_apply("2026-07-01", "2026-10-31")
    after_632 = LedgerService(s).balance_at("632", "2026-07-01", "2026-10-31")
    assert after_632 - before_632 == res.total_change
    assert _tb_balanced(s)
    again = inv.costing_preview("2026-07-01", "2026-10-31")
    assert again.changes == []                                    # chạy lại không thay đổi
    # dòng phiếu xuất đã cập nhật => sổ cái khớp chứng từ
    for line_id, _, amount, *_ in res.changes[:5]:
        assert s.db.scalar("SELECT amount FROM voucher_line WHERE id=?", (line_id,)) == amount
        assert s.db.scalar("SELECT SUM(credit) FROM ledger_entry WHERE line_id=? AND account_code LIKE '156%'", (line_id,)) == amount
    # không phát sinh cảnh báo lệch thành tiền sau tính giá
    al = AlertService(s).collect("2026-07-01", "2026-10-31")
    assert not [a for a in al if a.rule == "lech_thanh_tien"]


def _mini_scenario(s):
    vs = VoucherService(s)
    s.db.execute("INSERT INTO item(company_id, code, name, unit, kind, stock_account) VALUES(1,'ITEST','Hàng thử','Cái','HH','156')")
    for d, q, p in (("2026-12-01", 10, 100), ("2026-12-05", 10, 120)):
        v = vs.save({"vtype": "PNK", "voucher_date": d, "posting_date": d},
                    [{"debit_account": "156", "credit_account": "3388", "item": "ITEST", "warehouse": "KHO01",
                      "quantity": q, "unit_price": p}])
        vs.post(v)
    out = vs.save({"vtype": "PXK", "voucher_date": "2026-12-10", "posting_date": "2026-12-10"},
                  [{"debit_account": "632", "credit_account": "156", "item": "ITEST", "warehouse": "KHO01", "quantity": 15,
                    "unit_price": 1}])
    vs.post(out)
    return out


def test_costing_methods_hand_checked(s):
    out = _mini_scenario(s)
    inv = InventoryService(s)
    line = s.db.scalar("SELECT id FROM voucher_line WHERE voucher_id=?", (out,))
    bq = {c[0]: c for c in inv.costing_preview("2026-12-01", "2026-12-31", "BQCK").changes}
    assert bq[line][2] == 1650                                   # 15 × (1000+1200)/20
    ff = {c[0]: c for c in inv.costing_preview("2026-12-01", "2026-12-31", "FIFO").changes}
    assert ff[line][2] == 1600                                   # 10 × 100 + 5 × 120
    inv.set_method("FIFO")
    inv.costing_apply("2026-12-01", "2026-12-31")
    assert s.db.scalar("SELECT amount FROM voucher_line WHERE id=?", (line,)) == 1600
    assert s.db.scalar("SELECT COUNT(*) FROM costing_run") >= 1
    assert _tb_balanced(s)


# ------------------------------------------------------------------ công nợ
def test_debt_aging_equals_ledger_balance(s):
    ds = DebtService(s)
    for acc in ("131", "331"):
        sign = 1 if acc == "131" else -1
        summary = {r["partner_id"]: (r["cb_d"] - r["cb_c"]) * sign for r in ds.summary(acc, "2026-01-01", "2026-11-14")}
        aging = {}
        for d in ds.documents(acc, "2026-11-14"):
            aging[d.partner_id] = aging.get(d.partner_id, 0) + d.remaining
        for pid, bal in summary.items():
            assert aging.get(pid, 0) == bal, (acc, pid)
    kh3 = [r for r in ds.aging_totals("131", "2026-11-14") if r["partner_code"] == "KH003"][0]
    assert sum(kh3["buckets"][1:]) > 0                           # khách trả 60% => có nợ quá hạn
    kh5 = [r for r in ds.aging_totals("131", "2026-11-14") if r["partner_code"] == "KH005"][0]
    assert kh5["advance"] == 50_000_000


def test_due_date_default_from_partner_terms(s):
    vs = VoucherService(s)
    vid = vs.save({"vtype": "BKBH", "voucher_date": "2026-12-01", "posting_date": "2026-12-01", "partner_code": "KH003",
                   "invoice_no": "T1", "invoice_series": "1C26TST", "invoice_date": "2026-12-02"},
                  [{"debit_account": "131", "credit_account": "5113", "debit_partner": "KH003", "amount": 1000,
                    "tax_rate": "10"}])
    assert vs.get(vid)["due_date"] == "2027-01-16"               # KH003: 45 ngày


# ------------------------------------------------------------------ mua – bán
def test_batch_issue_from_sales(s):
    vs, ts = VoucherService(s), TradeService(s)
    sale = vs.save({"vtype": "BKBH", "voucher_date": "2026-12-03", "posting_date": "2026-12-03", "partner_code": "KH001"},
                   [{"debit_account": "131", "credit_account": "5111", "debit_partner": "KH001", "item": "HH002",
                     "warehouse": "KHO01", "quantity": 2, "unit_price": 4_500_000, "tax_rate": "10"}])
    vs.post(sale)
    assert sale in [p["id"] for p in ts.pending_issues("2026-12-01", "2026-12-31")]
    assert any(a.rule == "ban_chua_xuat" and a.voucher_id == sale
               for a in AlertService(s).collect("2026-12-01", "2026-12-31"))
    [pxk] = ts.create_issues([sale], post=True)
    v = vs.get(pxk)
    assert v["status"] == POSTED and v["source_voucher_id"] == sale
    assert v["lines"][0]["debit_account"] == "632" and v["lines"][0]["amount"] > 0
    assert sale not in [p["id"] for p in ts.pending_issues("2026-12-01", "2026-12-31")]
    with pytest.raises(BusinessError):
        ts.create_issues([sale])                                  # không lập trùng
    rc = {r["code"]: r for r in ts.revenue_cogs("2026-12-01", "2026-12-31")}
    assert rc["HH002"]["sold_q"] == rc["HH002"]["out_q"] == 2 and rc["HH002"]["warning"] == ""


def test_revenue_cogs_demo(s):
    rows = TradeService(s).revenue_cogs("2026-01-01", "2026-06-30")
    assert rows and all(r["diff_q"] == 0 for r in rows if r["kind"] != "DV")
    assert sum(r["revenue"] for r in rows) > sum(r["cogs"] for r in rows) > 0


def test_xml_invoices(s, tmp_path):
    files = {f.name: f for f in write_sample_invoices(s.db, tmp_path)}
    svc = XmlInvoiceService(s)
    a = svc.analyze(parse_file(files["01_mua_hang_NCC001.xml"]))
    assert (a.direction, a.partner_code, a.duplicate_of) == ("BKMH", "NCC001", "")
    assert [l.item_code for l in a.lines] == ["HH004", "HH006"] and not any(c[3] for c in svc.checks(a))
    vid = svc.create_voucher(a)
    v = VoucherService(s).get(vid)
    assert v["status"] == "DRAFT" and v["total_payment"] == a.total_payment and v["invoice_no"] == "0000199"
    with pytest.raises(BusinessError):
        svc.create_voucher(svc.analyze(parse_file(files["01_mua_hang_NCC001.xml"])))   # đã nhập => trùng
    b = svc.analyze(parse_file(files["02_mua_hang_NCC_moi_lech_lam_tron.xml"]))
    assert not b.partner_code and [c for c in svc.checks(b) if c[0] == "Tổng tiền thuế"][0][3] == -1
    with pytest.raises(BusinessError):
        svc.create_voucher(b)                                     # chưa có đối tượng
    code = svc.create_partner(b)
    assert s.db.scalar("SELECT tax_code FROM partner WHERE company_id=1 AND code=?", (code,)) == "0109990401"
    vid2 = svc.create_voucher(b, adjust_tax_rounding=True)
    assert VoucherService(s).get(vid2)["total_tax"] == 7037       # khớp tổng thuế trên hóa đơn
    c = svc.analyze(parse_file(files["03_ban_hang_da_nhap.xml"]))
    assert c.direction == "BKBH" and c.duplicate_of
    d = svc.analyze(parse_file(files["04_khong_thuoc_doanh_nghiep.xml"]))
    assert d.direction == "" and any("không thuộc doanh nghiệp" in w for w in d.warnings)
    bad = tmp_path / "bad.xml"
    bad.write_text("<root><x/></root>", encoding="utf-8")
    with pytest.raises(BusinessError):
        parse_file(bad)


def test_negative_cash_alert(s):
    vs = VoucherService(s)
    v = vs.save({"vtype": "PC", "voucher_date": "2026-12-20", "posting_date": "2026-12-20"},
                [{"debit_account": "6422", "credit_account": "1111", "amount": 900_000_000}])
    vs.post(v)
    assert any(a.rule == "quy_am" for a in AlertService(s).collect("2026-12-01", "2026-12-31"))
    assert to_decimal(0) == 0
