"""Kiểm thử giao diện (chạy offscreen): mở mọi chức năng, nhập chứng từ qua giao diện, ghi sổ, truy ngược.

Đặt biến môi trường KETOAN_SHOTS=<thư mục> để lưu ảnh chụp màn hình ở độ phân giải 1366×768.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402


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
def window(app, factory, tmp_path, monkeypatch):
    s = factory()                       # SQLite và (khi có KETOAN_PG_TEST_URL) cả PostgreSQL
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


def test_phase2_screens(window, tmp_path):
    from ketoan.data.seed import write_sample_invoices
    from ketoan.ui.phase2_views import CostingDialog
    w = window
    debt = w.open("m_congno")
    assert debt.t_sum.rowCount() > 1
    shot(w, "20_cong_no_tong_hop")
    kh3 = w.session.db.scalar("SELECT id FROM partner WHERE company_id=1 AND code='KH003'")
    debt._open_partner(kh3)
    assert debt.t_doc.rowCount() > 1
    shot(w, "21_cong_no_hoa_don_han_tt")
    debt.tabs.setCurrentIndex(2)
    shot(w, "22_tuoi_no")
    inv = w.open("m_htk")
    assert inv.t_nxt.rowCount() > 1
    shot(w, "23_nhap_xuat_ton")
    key = inv.t_nxt.item(0, 0).data(0x0100 + 1)
    inv._open_card(key)
    assert inv.t_card.rowCount() >= 2
    shot(w, "24_the_kho")
    w.open("c_opening_stock")
    shot(w, "25_ton_kho_dau_ky")
    w.cb_period.setCurrentIndex(w.cb_period.findText("Cả năm"))
    w._period_selected()
    dlg = CostingDialog(w, w)
    dlg.d_from.set_iso("2026-07-01")
    dlg.d_to.set_iso("2026-10-31")
    dlg.refresh()
    assert dlg.b_apply.isEnabled() and dlg.changes.rowCount() > 0
    dlg.show()
    if SHOTS:
        QApplication.processEvents()
        dlg.grab().save(os.path.join(SHOTS, "26_tinh_gia_xuat_kho.png"))
    dlg.apply()
    assert dlg.changes.rowCount() == 0                            # sau cập nhật không còn chênh lệch
    dlg.close()
    w.open("m_xuatloat")
    shot(w, "27_xuat_kho_hang_loat")
    rc = w.open("m_dtgv")
    assert rc.table.rowCount() > 1
    shot(w, "28_doi_chieu_dt_gv")
    xv = w.open("c_import_xml")
    files = write_sample_invoices(w.session.db, tmp_path / "xml")
    xv.choose([str(f) for f in files])
    assert xv.list.rowCount() == 4
    xv.list.selectRow(1)
    shot(w, "29_doc_hoa_don_xml")
    xv.list.selectRow(0)
    assert xv.b_create.isEnabled()
    xv.create_voucher()
    assert getattr(xv.invoices[0], "voucher_id", None)
    form = w.tabs.currentWidget()
    assert form.data["invoice_no"] == "0000199" and form.ed_due.isVisible()
    shot(w, "30_chung_tu_tu_xml")
    assert not w._warnings, w._warnings


def test_phase3_screens(window, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt as _Qt
    from ketoan.ui.phase3_report_views import TemplateManager
    w = window
    # --- TSCĐ: danh sách, chạy khấu hao tháng 7, hoàn tác
    av = w.open("m_tscd")
    assert av.table.rowCount() == 3
    shot(w, "40_tscd_danh_sach")
    av.tabs.setCurrentIndex(1)
    rt = av.run_tab
    rt.cb_month.setCurrentIndex(6)
    rt.refresh()
    assert rt.table.rowCount() == 3
    shot(w, "41_khau_hao_thang")
    rt.chk_post.setChecked(True)
    rt.apply()
    assert rt.hist.rowCount() == 7      # tháng 1–6 đã chạy sẵn trong dữ liệu mẫu + tháng 7 vừa chạy
    assert w.session.db.scalar("SELECT v.status FROM period_run r JOIN voucher v ON v.id=r.voucher_id WHERE r.kind='ASSET' AND r.month=7") == "POSTED"
    w.tabs.setCurrentWidget(av)
    rt.hist.selectRow(0)
    rt.undo()
    assert rt.hist.rowCount() == 6
    pv = w.open("m_ccdc")
    assert pv.table.rowCount() == 3
    shot(w, "42_ccdc_chi_phi_tra_truoc")
    # --- Giá thành (DN 2 – xây dựng): nhập SL, dở dang → lưu → chứng từ nháp
    w.cb_company.setCurrentIndex(1)
    w._company_selected(1)
    cv = w.open("gt_ct")
    cv.d_from.set_iso("2026-03-01")
    cv.d_to.set_iso("2026-03-31")
    cv.calc()
    assert len(cv.rows) == 2
    qty_col, we_col = cv.c_qty, cv.c_we
    cv.table.item(0, qty_col).setText("2")
    cv.table.item(0, we_col).setText("100.000.000")
    assert cv.rows[0].total == 616_000_000 and cv.table.item(0, cv.c_total).text() == "616.000.000"
    shot(w, "43_gia_thanh_cong_trinh")
    cv.save()
    assert w.tabs.currentWidget().data["status"] == "DRAFT"
    cv2 = w.open("gt_kdm")
    cv2.d_from.set_iso("2026-03-01"); cv2.d_to.set_iso("2026-03-31"); cv2.calc()
    assert cv2.c_common is not None
    shot(w, "44_gia_thanh_khong_dinh_muc")
    sct = w.open("gt_sct", project_id=cv.rows[0].project_id, d_from="2026-03-01", d_to="2026-03-31", new_tab=True)
    assert sct.table.rowCount() > 3
    shot(w, "45_so_chi_tiet_cong_trinh")
    w.cb_company.setCurrentIndex(0)
    w._company_selected(0)
    # --- Báo cáo tài chính theo mẫu + quản lý mẫu
    bs = w.open("bc_cdkt")
    assert bs.table.rowCount() >= 15 and "CHƯA KIỂM CHỨNG" in bs.banner.text()
    assert bs.footer.text().startswith("Nhấp đúp") or "lệch" not in bs.footer.text()
    shot(w, "46_bang_can_doi_mau_thu_nghiem")
    w.open("bc_kqkd")
    shot(w, "47_ket_qua_kinh_doanh_mau_thu_nghiem")
    cf = w.open("bc_lctt")
    assert "Chưa có mẫu" in cf.banner.text()
    mgr = TemplateManager(w, w)
    mgr.show()
    if SHOTS:
        QApplication.processEvents()
        mgr.grab().save(os.path.join(SHOTS, "48_quan_ly_mau_bao_cao.png"))
    mgr.close()
    # --- Thuế hỗ trợ
    for key, name in (("t_gtgt", "49_thue_gtgt"), ("t_doichieu", "50_doi_chieu_hoa_don"), ("t_tndn", "51_thue_tndn_tam_tinh"), ("t_tncn", "52_thue_tncn_tong_hop")):
        w.open(key)
        shot(w, name)
    # --- In hồ sơ, chuyển số dư cuối năm
    pp = w.open("m_inhs")
    pp.folder.setText(str(tmp_path / "hs"))
    pp.checks["chungtu"].setChecked(False)
    pp.export()
    files = sorted((tmp_path / "hs").glob("*.pdf"))
    assert len(files) >= 5 and all(f.read_bytes()[:4] == b"%PDF" for f in files) and (tmp_path / "hs" / "00_MUC_LUC.txt").exists()
    shot(w, "53_in_ho_so")
    ye = w.open("s_yearend")
    assert ye.pv["problems"]
    shot(w, "54_chuyen_so_du_cuoi_nam")
    assert not w._warnings, w._warnings
    _ = _Qt
