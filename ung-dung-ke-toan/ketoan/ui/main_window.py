"""Cửa sổ chính: thanh tiêu đề, thanh điều khiển, menu trái, vùng làm việc dạng tab, thanh trạng thái."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStatusBar, QTabWidget, QVBoxLayout, QWidget)

from ketoan import APP_BRAND, APP_NAME
from ketoan.services.period_service import PeriodService
from ketoan.services.system_service import CompanyService
from ketoan.ui import icons, theme
from ketoan.ui.registry import FUNCS, MENU
from ketoan.ui.widgets import DateEdit, PhaseView, error, info, vn_date


class Sidebar(QFrame):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.on_click = on_click
        self.collapsed = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(1)
        self.toggle = QPushButton()
        self.toggle.setObjectName("SidebarToggle")
        self.toggle.setIcon(icons.icon("menu", "#3E5C7A", 18))
        self.toggle.setText("  Thu gọn menu")
        self.toggle.setToolTip("Thu gọn / mở rộng menu (Ctrl+B)")
        self.toggle.clicked.connect(self.toggle_collapse)
        lay.addWidget(self.toggle)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for i, (label, ic, target) in enumerate(MENU):
            b = QPushButton(f"  {label}")
            b.setCheckable(True)
            b.setIcon(icons.icon(ic, "#2B4A6F", 18))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(30)
            b.clicked.connect(lambda _=False, idx=i: self.on_click(idx))
            b.toggled.connect(lambda on, btn=b, name=ic: btn.setIcon(icons.icon(name, "#FFFFFF" if on else "#2B4A6F", 18)))
            self.group.addButton(b, i)
            self.buttons.append((b, label))
            lay.addWidget(b)
        lay.addStretch(1)
        self.setFixedWidth(theme.SIDEBAR_WIDTH)

    def select(self, idx):
        if 0 <= idx < len(self.buttons):
            self.buttons[idx][0].setChecked(True)

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        for b, label in self.buttons:
            b.setText("" if self.collapsed else f"  {label}")
        self.toggle.setText("" if self.collapsed else "  Thu gọn menu")
        self.setFixedWidth(theme.SIDEBAR_COLLAPSED if self.collapsed else theme.SIDEBAR_WIDTH)
        if self.parent_brand is not None:
            for lab in self.parent_brand.findChildren(QLabel):
                if lab.objectName() in ("BrandName", "BrandSub"):
                    lab.setVisible(not self.collapsed)
            self.parent_brand.setFixedWidth(self.width())

    parent_brand = None


class MainWindow(QMainWindow):
    def __init__(self, session, app_dirs: dict, parent=None):
        super().__init__(parent)
        self.session = session
        self.backup_dir = Path(app_dirs["backup"])
        self.app_dirs = app_dirs
        self.setWindowTitle(f"{APP_NAME} – {APP_BRAND}")
        self.setWindowIcon(QIcon(icons.logo_pixmap(64)))
        self.resize(1366, 768)
        self.setMinimumSize(1100, 640)
        self._tab_keys: dict[QWidget, str] = {}
        self._stale: set = set()
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_controls())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.sidebar = Sidebar(self._menu_clicked)
        self.sidebar.parent_brand = self.brand
        body.addWidget(self.sidebar)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        body.addWidget(self.tabs, 1)
        root.addLayout(body, 1)
        self._build_status()
        self._shortcuts()
        self._load_companies()
        self._update_status()
        self.open("dashboard")
        self.sidebar.select(0)

    # ================================================================ dựng khung
    def _build_header(self):
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(42)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 12, 0)
        lay.setSpacing(8)
        self.brand = QWidget()
        bl = QHBoxLayout(self.brand)
        bl.setContentsMargins(10, 0, 0, 0)
        bl.setSpacing(7)
        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(30))
        bl.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        n1 = QLabel(APP_BRAND)
        n1.setObjectName("BrandName")
        n2 = QLabel("Giải pháp kế toán doanh nghiệp")
        n2.setObjectName("BrandSub")
        names.addWidget(n1)
        names.addWidget(n2)
        bl.addLayout(names)
        bl.addStretch(1)
        self.brand.setFixedWidth(theme.SIDEBAR_WIDTH)
        lay.addWidget(self.brand)
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:#2E5687")
        lay.addWidget(sep)
        t = QLabel("ỨNG DỤNG KẾ TOÁN")
        t.setObjectName("AppTitle")
        lay.addWidget(t)
        self.title_sub = QLabel()
        self.title_sub.setObjectName("AppTitleSub")
        lay.addWidget(self.title_sub, 1)
        self.header_user = QLabel()
        self.header_user.setObjectName("HeaderUser")
        lay.addWidget(self.header_user)
        return bar

    def _build_controls(self):
        bar = QFrame()
        bar.setObjectName("ControlBar")
        bar.setFixedHeight(48)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 3, 10, 4)
        lay.setSpacing(6)

        def field(caption, w):
            box = QWidget()
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(1)
            c = QLabel(caption)
            v.addWidget(c)
            v.addWidget(w)
            return box

        self.cb_company = QComboBox()
        self.cb_company.setFixedWidth(250)
        self.cb_data = QComboBox()
        self.cb_data.setFixedWidth(120)
        self.cb_year = QComboBox()
        self.cb_year.setFixedWidth(66)
        self.cb_period = QComboBox()
        self.cb_period.addItem("Cả năm", ("Y", 0))
        for q in range(1, 5):
            self.cb_period.addItem(f"Quý {q}", ("Q", q))
        for m in range(1, 13):
            self.cb_period.addItem(f"Tháng {m:02d}", ("M", m))
        self.cb_period.addItem("Tùy chọn", ("C", 0))
        self.cb_period.setFixedWidth(92)
        self.d_from = DateEdit(self.session.date_from)
        self.d_to = DateEdit(self.session.date_to)
        for cap, w in (("Doanh nghiệp", self.cb_company), ("Dữ liệu kế toán", self.cb_data), ("Năm", self.cb_year),
                       ("Kỳ", self.cb_period), ("Từ ngày", self.d_from), ("Đến ngày", self.d_to)):
            lay.addWidget(field(cap, w), 0, Qt.AlignBottom)
        lay.addSpacing(4)
        self.b_refresh = QPushButton("Cập nhật F5")
        self.b_refresh.setMinimumWidth(104)
        self.b_refresh.setObjectName("CtlPrimary")
        self.b_refresh.setIcon(icons.icon("refresh", "#FFFFFF", 15))
        self.b_refresh.setToolTip("Áp dụng kỳ đang chọn và cập nhật tab hiện tại (F5)")
        self.b_refresh.clicked.connect(self.refresh_current)
        lay.addWidget(self.b_refresh, 0, Qt.AlignBottom)
        self.b_cost = QPushButton("Tính giá xuất kho")
        self.b_cost.setObjectName("CtlButton")
        self.b_cost.setIcon(icons.icon("calc", "#2B4A6F", 15))
        self.b_cost.setToolTip("Tính giá xuất kho theo phương pháp của doanh nghiệp (bình quân gia quyền cuối tháng / FIFO) – "
                               "có bảng xem trước")
        self.b_cost.clicked.connect(lambda: self.open("m_tinhgia"))
        lay.addWidget(self.b_cost, 0, Qt.AlignBottom)
        self.b_close = QPushButton("Kết chuyển")
        self.b_close.setObjectName("CtlButton")
        self.b_close.setIcon(icons.icon("scale", "#2B4A6F", 15))
        self.b_close.setToolTip("Kết chuyển cuối kỳ – có bảng xem trước và hoàn tác")
        self.b_close.clicked.connect(lambda: self.open("s_closing"))
        lay.addWidget(self.b_close, 0, Qt.AlignBottom)
        self.b_settings = QPushButton("Cài đặt")
        self.b_settings.setObjectName("CtlButton")
        self.b_settings.setIcon(icons.icon("settings", "#2B4A6F", 15))
        self.b_settings.clicked.connect(lambda: self.open("s_company"))
        lay.addWidget(self.b_settings, 0, Qt.AlignBottom)
        self.b_help = QPushButton("Trợ giúp")
        self.b_help.setObjectName("CtlButton")
        self.b_help.setIcon(icons.icon("help", "#2B4A6F", 15))
        self.b_help.setToolTip("Trợ giúp và phím tắt (F1)")
        self.b_help.clicked.connect(self.show_help)
        lay.addWidget(self.b_help, 0, Qt.AlignBottom)
        lay.addStretch(1)
        self.cb_company.activated.connect(self._company_selected)
        self.cb_data.activated.connect(self._data_selected)
        self.cb_year.activated.connect(lambda _: self._period_selected())
        self.cb_period.activated.connect(lambda _: self._period_selected())
        self.d_from.dateChanged.connect(self._dates_edited)
        self.d_to.dateChanged.connect(self._dates_edited)
        return bar

    def _build_status(self):
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)
        self.st = {}
        for key in ("user", "data", "company", "conn", "time"):
            l = QLabel()
            self.st[key] = l
            if key == "time":
                sb.addPermanentWidget(l)
            else:
                sb.addWidget(l)
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(1000)
        self._update_status()

    def _shortcuts(self):
        for seq, fn in (("F5", self.refresh_current), ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
                        ("Ctrl+Tab", lambda: self._cycle(1)), ("Ctrl+Shift+Tab", lambda: self._cycle(-1)),
                        ("F1", self.show_help), ("Ctrl+B", self.sidebar.toggle_collapse),
                        ("Ctrl+Shift+A", lambda: self.open("s_alerts"))):
            QShortcut(QKeySequence(seq), self, activated=fn)

    # ================================================================ trạng thái
    def _tick(self):
        self.st["time"].setText(datetime.now().strftime("Ngày giờ: %d/%m/%Y %H:%M:%S"))
        if datetime.now().second % 15 == 0:
            self._update_conn()

    def _update_conn(self):
        ok = self.session.db.connected
        self.st["conn"].setText("● Kết nối: " + ("Đã kết nối (SQLite cục bộ)" if ok else "MẤT KẾT NỐI"))
        self.st["conn"].setStyleSheet("color:#8FE3A6" if ok else "color:#FF9C9C;font-weight:700")

    def _update_status(self):
        s = self.session
        c = s.company
        self.st["user"].setText(f"Người dùng: {s.user.full_name} ({s.user.role_name})")
        self.st["data"].setText(f"Dữ liệu: {Path(s.db.path).name}")
        self.st["company"].setText(f"Doanh nghiệp: {c['name'] if c else ''}")
        self._update_conn()
        self._tick()
        reg = s.regime_for()
        reg_txt = (f"Chế độ: {reg['legal_ref'].replace('Thông tư ', 'TT ')}" + ("" if reg["verified"] else " (chưa kiểm chứng)")
                   if reg else "Chế độ kế toán: chưa cấu hình")
        self.title_sub.setText(f"  ·  {c['name'] if c else ''}  ·  {reg_txt}")
        self.header_user.setText(f"{s.user.username}  ·  {s.user.role_name}")

    # ================================================================ doanh nghiệp / dữ liệu / kỳ
    def _load_companies(self):
        self.cb_company.blockSignals(True)
        self.cb_company.clear()
        for c in CompanyService(self.session).companies():
            self.cb_company.addItem(c["name"], c["id"])
        if not self.session.company_id and self.cb_company.count():
            self.session.company_id = self.cb_company.itemData(0)
        self.cb_company.setCurrentIndex(max(0, self.cb_company.findData(self.session.company_id)))
        self.cb_company.blockSignals(False)
        self.cb_data.clear()
        self.cb_data.addItem(Path(self.session.db.path).name, "current")
        self.cb_data.addItem("Mở dữ liệu khác…", "open")
        self.cb_data.addItem("Tạo dữ liệu mới…", "new")
        self.cb_data.setToolTip(self.session.db.path)
        self._load_years()

    def _load_years(self):
        years = PeriodService(self.session).years() or [date.today().year]
        self.cb_year.blockSignals(True)
        self.cb_year.clear()
        for y in years:
            self.cb_year.addItem(str(y), y)
        y = self.session.year if self.session.year in years else years[-1]
        self.cb_year.setCurrentIndex(self.cb_year.findData(y))
        self.cb_year.blockSignals(False)
        self._period_selected()

    def _period_selected(self):
        y = self.cb_year.currentData() or date.today().year
        kind, n = self.cb_period.currentData()
        if kind == "Y":
            a, b = date(y, 1, 1), date(y, 12, 31)
        elif kind == "Q":
            a, b = date(y, 3 * n - 2, 1), date(y, 3 * n, monthrange(y, 3 * n)[1])
        elif kind == "M":
            a, b = date(y, n, 1), date(y, n, monthrange(y, n)[1])
        else:
            a, b = self.d_from.pydate(), self.d_to.pydate()
        self._setting_dates = True
        self.d_from.set_iso(a)
        self.d_to.set_iso(b)
        self._setting_dates = False
        self.session.year = y
        self.session.set_period(a, b, self.cb_period.currentText() + (f" {y}" if kind != "C" else ""))

    _setting_dates = False

    def _dates_edited(self):
        if self._setting_dates:
            return
        self.cb_period.setCurrentIndex(self.cb_period.findText("Tùy chọn"))
        a, b = self.d_from.pydate(), self.d_to.pydate()
        if a > b:
            return
        self.session.year = a.year
        self.session.set_period(a, b, "Tùy chọn")

    def _company_selected(self, idx):
        cid = self.cb_company.itemData(idx)
        if cid == self.session.company_id:
            return
        if not self._confirm_close_all():
            self.cb_company.setCurrentIndex(self.cb_company.findData(self.session.company_id))
            return
        self.session.company_id = cid
        self.reload_all()

    def _data_selected(self, idx):
        action = self.cb_data.itemData(idx)
        self.cb_data.setCurrentIndex(0)
        if action == "current":
            return
        if not self.session.user.can("admin"):
            error(self, "Chỉ quản trị hệ thống được mở hoặc tạo dữ liệu kế toán khác.", "Không có quyền")
            return
        from ketoan.app import switch_database
        if action == "open":
            p, _ = QFileDialog.getOpenFileName(self, "Mở dữ liệu kế toán", str(self.app_dirs["data"]), "Dữ liệu kế toán (*.db)")
        else:
            p, _ = QFileDialog.getSaveFileName(self, "Tạo dữ liệu kế toán mới", str(Path(self.app_dirs["data"]) / "ketoan_moi.db"),
                                               "Dữ liệu kế toán (*.db)")
        if p and self._confirm_close_all():
            switch_database(self, p, create=(action == "new"))

    def _confirm_close_all(self) -> bool:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if getattr(w, "dirty", False):
                self.tabs.setCurrentIndex(i)
                if not w.can_close():
                    return False
        return True

    def reload_all(self):
        for w in list(self._tab_keys):
            if hasattr(w, "dirty"):
                w.dirty = False
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            self._tab_keys.pop(w, None)
            w.deleteLater()
        self._load_companies()
        self._update_status()
        self.open("dashboard")
        self.sidebar.select(0)

    def reload_years(self):
        self._load_years()

    def company_info_changed(self):
        idx = self.cb_company.findData(self.session.company_id)
        self.cb_company.setItemText(idx, self.session.company["name"])
        self._update_status()

    # ================================================================ tab
    def _add_tab(self, key: str, widget: QWidget, title: str, icon_name: str = "doc", color="#2B4A6F"):
        self._tab_keys[widget] = key
        i = self.tabs.addTab(widget, icons.icon(icon_name, color, 16), title)
        self.tabs.setTabToolTip(i, title)
        if key == "dashboard":
            from PySide6.QtWidgets import QTabBar
            self.tabs.tabBar().setTabButton(i, QTabBar.RightSide, None)
        self.tabs.setCurrentIndex(i)
        return widget

    def _find(self, key):
        for w, k in self._tab_keys.items():
            if k == key:
                return w
        return None

    def set_tab_title(self, widget, title):
        i = self.tabs.indexOf(widget)
        if i >= 0:
            self.tabs.setTabText(i, title)
            self.tabs.setTabToolTip(i, title)

    def close_widget(self, widget):
        i = self.tabs.indexOf(widget)
        if i >= 0:
            self.tabs.removeTab(i)
            self._tab_keys.pop(widget, None)
            widget.deleteLater()
        if self.tabs.count() == 0:
            self.open("dashboard")

    def close_tab(self, i):
        if i < 0:
            return
        w = self.tabs.widget(i)
        if hasattr(w, "can_close") and not w.can_close():
            return
        self.close_widget(w)

    def _cycle(self, step):
        n = self.tabs.count()
        if n:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % n)

    def _tab_changed(self, i):
        w = self.tabs.widget(i)
        key = self._tab_keys.get(w, "")
        idx = 0 if key == "dashboard" else next((n for n, m in enumerate(MENU) if key == f"menu:{m[0]}"), -1)
        if idx >= 0:
            self.sidebar.select(idx)
        else:
            self.sidebar.group.setExclusive(False)
            for b, _ in self.sidebar.buttons:
                b.setChecked(False)
            self.sidebar.group.setExclusive(True)
        if w in self._stale:
            self._stale.discard(w)
            if hasattr(w, "refresh") and not getattr(w, "editing", False):
                w.refresh()

    def refresh_current(self):
        w = self.tabs.currentWidget()
        if w is None:
            return
        if getattr(w, "editing", False) and getattr(w, "dirty", False):
            info(self, "Chứng từ đang nhập dở – hãy lưu hoặc hủy trước khi cập nhật.")
            return
        if hasattr(w, "apply_period"):
            w.apply_period(self.session.date_from.isoformat(), self.session.date_to.isoformat())
        if hasattr(w, "refresh"):
            w.refresh()
        self.statusBar().showMessage(f"Đã cập nhật – kỳ {self.session.period_label} "
                                     f"({vn_date(self.session.date_from.isoformat())} – {vn_date(self.session.date_to.isoformat())})",
                                     4000)

    def voucher_changed(self):
        cur = self.tabs.currentWidget()
        for w in self._tab_keys:
            if w is not cur:
                self._stale.add(w)

    def catalog_changed(self):
        self.voucher_changed()

    # ================================================================ điều hướng
    def _menu_clicked(self, idx):
        label, ic, target = MENU[idx]
        if isinstance(target, str):
            self.open(target)
            return
        key = f"menu:{label}"
        w = self._find(key)
        if w:
            self.tabs.setCurrentWidget(w)
            return
        from ketoan.ui.dashboard import SectionPage
        self._add_tab(key, SectionPage(self, label, target), label, ic)

    def open_voucher(self, voucher_id=None, vtype: str | None = None):
        from ketoan.ui.voucher_form import VoucherForm
        if voucher_id:
            key = f"voucher:{voucher_id}"
            w = self._find(key)
            if w:
                self.tabs.setCurrentWidget(w)
                return w
            w = VoucherForm(self, voucher_id=voucher_id)
            if not w.voucher_id:
                w.deleteLater()
                return None
            return self._add_tab(key, w, f"{w.vt.prefix} {w.title.text()}", "docs")
        if not self.session.user.can("add"):
            error(self, "Bạn không có quyền thêm chứng từ.", "Không có quyền")
            return None
        w = VoucherForm(self, vtype or "PKT")
        key = f"voucher:new:{id(w)}"
        w.saved.connect(lambda vid, widget=w: self._tab_keys.__setitem__(widget, f"voucher:{vid}"))
        return self._add_tab(key, w, "Chứng từ mới", "add")

    def open(self, key: str, new_tab: bool = False, **kwargs):
        if key == "s_closing":
            from ketoan.ui.system_views import ClosingDialog
            ClosingDialog(self, self).exec()
            return None
        if key == "m_tinhgia":
            from ketoan.ui.phase2_views import CostingDialog
            CostingDialog(self, self).exec()
            return None
        if key == "m_nhquy":
            idx = next(i for i, m in enumerate(MENU) if m[0] == "Ngân hàng – Quỹ")
            self.sidebar.select(idx)
            self._menu_clicked(idx)
            return None
        func = FUNCS.get(key)
        args = dict(func.args) if func else {}
        args.update(kwargs)
        tab_key = key if not kwargs else f"{key}:{sorted((k, str(v)) for k, v in kwargs.items())}"
        w = None if new_tab else self._find(tab_key)
        if w is None and not kwargs and not new_tab:
            w = self._find(key)
        if w:
            self.tabs.setCurrentWidget(w)
            return w
        if key in ("s_users", "s_backup") and not self.session.user.can("admin"):
            error(self, "Chức năng dành cho quản trị hệ thống.", "Không có quyền")
            return None
        title = func.title if func else key
        if func and func.pending:
            return self._add_tab(tab_key, PhaseView(func), title, func.icon)
        w = self._create(key, args)
        if w is None:
            return None
        if key == "r_sct" and args.get("account"):
            title = f"Sổ chi tiết {args['account']}"
        if key == "r_socai" and args.get("account"):
            title = f"Sổ cái {args['account']}"
        return self._add_tab(tab_key, w, title, func.icon if func else "doc")

    def _create(self, key, args):
        from ketoan.ui import catalog_views as cv, report_views as rv, system_views as sv
        from ketoan.ui.dashboard import Dashboard
        from ketoan.ui.voucher_list import VoucherListView
        d = {k: args[k] for k in ("d_from", "d_to") if k in args}
        if key == "dashboard":
            return Dashboard(self)
        if key.startswith("v_"):
            return VoucherListView(self, args.get("vtype"), args.get("status"))
        if key == "r_nkc":
            return rv.JournalView(self, **d)
        if key == "r_socai":
            return rv.GeneralLedgerView(self, args.get("account", "111"), **d)
        if key == "r_sct":
            return rv.AccountDetailView(self, args.get("account", "131"), args.get("partner_id"), **d)
        if key in ("r_soquy", "r_sotgnh"):
            return rv.AccountDetailView(self, args["account"], cash_book=True, **d)
        if key == "r_cdps":
            return rv.TrialBalanceView(self, **d)
        if key == "c_catalog":
            return cv.CatalogView(self, args.get("catalog", "account"))
        if key == "c_opening":
            return cv.OpeningBalanceView(self)
        from ketoan.ui import phase2_views as p2
        if key == "m_congno":
            return p2.DebtView(self, args.get("account", "131"))
        if key in ("m_htk", "m_thekho"):
            return p2.InventoryView(self, 1 if key == "m_thekho" else 0)
        if key == "c_opening_stock":
            return p2.OpeningStockView(self)
        if key == "m_xuatloat":
            return p2.BatchIssueView(self)
        if key == "m_dtgv":
            return p2.RevenueCogsView(self)
        if key == "c_import_xml":
            return p2.XmlInvoiceView(self)
        from ketoan.ui import phase3_report_views as p3r, phase3_views as p3
        if key == "m_tscd":
            return p3.AssetView(self)
        if key == "m_ccdc":
            return p3.PrepaidView(self)
        if key in ("gt_ct", "gt_dm", "gt_kdm", "gt_gd", "gt_dv", "gt_vt", "gt_kdd"):
            return p3.CostView(self, key)
        if key == "gt_sct":
            return p3.ProjectLedgerView(self, args.get("project_id"), args.get("d_from"), args.get("d_to"))
        if key == "m_inhs":
            return p3.PrintPackView(self)
        if key == "s_yearend":
            return p3.YearEndView(self)
        if key in ("bc_cdkt", "bc_kqkd", "bc_lctt"):
            return p3r.FinStatementView(self, {"bc_cdkt": "BS", "bc_kqkd": "IS", "bc_lctt": "CF"}[key])
        if key == "t_gtgt":
            return p3r.VatView(self)
        if key == "t_doichieu":
            return p3r.InvoiceReconView(self)
        if key == "t_tndn":
            return p3r.TndnView(self)
        if key == "t_tncn":
            return p3r.TncnView(self)
        if key == "s_alerts":
            return sv.AlertView(self)
        if key == "s_lock":
            return sv.PeriodLockView(self)
        if key == "s_users":
            return sv.UsersView(self)
        if key == "s_audit":
            return sv.AuditView(self)
        if key == "s_backup":
            return sv.BackupView(self)
        if key == "s_company":
            return sv.CompanyView(self)
        error(self, f"Chức năng «{key}» chưa được khai báo.")
        return None

    def show_help(self):
        from ketoan.ui.system_views import HelpDialog
        HelpDialog(self).exec()

    def closeEvent(self, e):
        if not self._confirm_close_all():
            e.ignore()
            return
        e.accept()
