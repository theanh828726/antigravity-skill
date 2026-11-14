"""Kiểm thử giao diện (chạy offscreen): mở mọi chức năng, nhập chứng từ qua giao diện, ghi sổ, truy ngược.

Đặt biến môi trường KETOAN_SHOTS=<thư mục> để lưu ảnh chụp màn hình ở độ phân giải 1366×768.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from ketoan.data.db import Database  # noqa: E402
from ketoan.data.seed import create_database  # noqa: E402
from ketoan.services.auth_service import authenticate  # noqa: E402
from ketoan.services.context import Session  # noqa: E402

SHOTS = os.environ.get("KETOAN_SHOTS")


@pytest.fixture(scope="module")
def app():
    from ketoan.ui import theme
    a = QApplication.instance() or QApplication([])
    a.setStyle("Fusion")
    a.setFont(theme.app_font())
    a.setStyleSheet(theme.STYLESHEET)
    return a


@pytest.fixture()
def window(app, tmp_path, monkeypatch):
    p = tmp_path / "ui.db"
    create_database(p).close()
    db = Database(p)
    s = Session(db, authenticate(db, "admin", "admin@123"))
    # các hộp thoại xác nhận/thông báo tự động đồng ý trong kiểm thử
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a[2]) or QMessageBox.Ok))
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from ketoan.ui.main_window import MainWindow
    dirs = {"base": tmp_path, "data": tmp_path, "backup": tmp_path / "bk"}
    w = MainWindow(s, dirs)
    w.resize(1366, 768)
    w.show()
    app.processEvents()
    w._warnings = warnings
    yield w
    w.close()
    db.close()


def shot(w, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        QApplication.processEvents()
        w.grab().save(os.path.join(SHOTS, f"{name}.png"))


def test_dashboard_and_all_functions_open(window):
    from ketoan.ui.registry import FUNCS, MENU
    w = window
    shot(w, "01_tong_quan")
    for key in FUNCS:
        if key in ("s_closing",):
            continue
        w.open(key)
        QApplication.processEvents()
    for i in range(len(MENU)):
        w._menu_clicked(i)
        QApplication.processEvents()
    assert w.tabs.count() > 30
    assert not w._warnings, w._warnings


def test_voucher_entry_post_and_drilldown(window):
    w = window
    w.cb_period.setCurrentIndex(w.cb_period.findText("Tháng 11"))
    w._period_selected()
    form = w.open_voucher(None, "BKBH")
    form.partner.edit.setText("KH001")
    form.partner._resolve()
    form.ed_desc.setText("Bán hàng nhập qua giao diện")
    form.ed_inv_no.setText("UI0001")
    form.ed_inv_series.setText("1C26TUI")
    cols = [c[0] for c in form.columns]
    form.set_cell(0, cols.index("item"), "HH002")
    form.set_cell(0, cols.index("warehouse"), "KHO01")
    form.set_cell(0, cols.index("quantity"), "2")
    form.set_cell(0, cols.index("unit_price"), "4.420.000")
    assert form.lines[0]["amount"] == 8_840_000 and form.lines[0]["tax_amount"] == 884_000
    assert form.lines[0]["debit_partner"] == "KH001"         # gợi ý đối tượng từ thông tin chung
    assert "cân đối" in form.t["difference"].text()
    shot(w, "02_nhap_chung_tu")
    assert form.do_save()
    vid = form.voucher_id
    assert vid and form.data["status"] == "DRAFT"
    form.do_post()
    assert form.data["status"] == "POSTED", w._warnings
    shot(w, "03_chung_tu_da_ghi_so")
    # Truy ngược: CĐSPS -> Sổ chi tiết 131 -> chứng từ
    tb = w.open("r_cdps")
    tb.refresh()
    shot(w, "04_can_doi_so_phat_sinh")
    sct = w.open("r_sct", account="131", d_from=w.session.date_from.isoformat(), d_to=w.session.date_to.isoformat(),
                 new_tab=True)
    keys = [sct.table.item(r, 0).data(0x0100 + 1) for r in range(sct.table.rowCount())]
    assert vid in keys
    shot(w, "05_so_chi_tiet_131")
    w.tabs.setCurrentWidget(form)
    opened = w.open_voucher(vid)
    assert opened is form                                     # mở lại đúng tab chứng từ gốc


def test_paste_from_excel_and_unbalanced_block(window):
    from PySide6.QtGui import QGuiApplication
    w = window
    form = w.open_voucher(None, "PKT")
    form.ed_desc.setText("Dán từ Excel")
    QGuiApplication.clipboard().setText("Chi phí A\t6422\t1111\t\t\t1.500.000\nChi phí B\t6421\t\t\t\t700.000\n")
    form.grid.setCurrentCell(0, 1)
    form.paste_rows()
    assert len(form.lines) == 2 and form.lines[0]["amount"] == 1_500_000
    assert "lệch" in form.t["difference"].text()
    assert form.do_save()
    form.do_post()
    assert form.data["status"] == "DRAFT"                     # lỗi chặn: không ghi sổ


def test_screens_for_handoff(window):
    w = window
    for key, name in (("r_nkc", "06_nhat_ky_chung"), ("r_socai", "07_so_cai"), ("s_alerts", "08_trung_tam_canh_bao"),
                      ("v_BKMH", "09_danh_sach_chung_tu"), ("c_catalog", "10_danh_muc"), ("s_lock", "11_khoa_so"),
                      ("m_tscd", "12_chuc_nang_giai_doan_3"), ("s_company", "13_che_do_ke_toan")):
        w.open(key)
        shot(w, name)
    w._menu_clicked(3)
    shot(w, "14_menu_so_sach")
    w.sidebar.toggle_collapse()
    w.tabs.setCurrentIndex(0)
    shot(w, "15_menu_thu_gon")


def test_dialogs_render(window):
    from ketoan.ui.system_views import ClosingDialog, HelpDialog, LoginDialog
    w = window
    w.cb_period.setCurrentIndex(w.cb_period.findText("Tháng 07"))
    w._period_selected()
    dlg = ClosingDialog(w, w)
    assert dlg.table.rowCount() > 0 and dlg.b_exec.isEnabled()     # tháng 7 chưa kết chuyển => có bút toán xem trước
    dlg.show()
    if SHOTS:
        QApplication.processEvents()
        dlg.grab().save(os.path.join(SHOTS, "16_ket_chuyen_xem_truoc.png"))
    dlg.close()
    login = LoginDialog(w.session.db)
    login.show()
    if SHOTS:
        QApplication.processEvents()
        login.grab().save(os.path.join(SHOTS, "17_dang_nhap.png"))
    login.p.setText("sai")
    login.try_login()
    assert login.user is None and "không đúng" in login.msg.text()
    login.p.setText("admin@123")
    login.try_login()
    assert login.user and login.user.username == "admin"
    HelpDialog(w).close()


def test_export_excel_pdf(window, tmp_path):
    from openpyxl import load_workbook
    from ketoan.reports import export
    w = window
    tb = w.open("r_cdps")
    bar = tb.findChild(__import__("ketoan.ui.widgets", fromlist=["ExportBar"]).ExportBar)
    title, sub, company = bar._payload()
    xlsx, pdf = tmp_path / "cdps.xlsx", tmp_path / "cdps.pdf"
    export.export_excel(str(xlsx), title, sub, company, tb.table.headers(), tb.table.data_rows(), tb.table.money_cols,
                        tb.table.total_rows)
    ws = load_workbook(xlsx).active
    assert ws["A2"].value == title.upper()
    total_row = [r for r in ws.iter_rows(values_only=True) if r[1] == "TỔNG CỘNG"][0]
    assert isinstance(total_row[4], int) and total_row[4] == total_row[5]      # tiền xuất dạng số, PS Nợ = PS Có
    export.export_pdf(str(pdf), bar.html(), True)
    assert pdf.read_bytes()[:4] == b"%PDF" and pdf.stat().st_size > 5000
