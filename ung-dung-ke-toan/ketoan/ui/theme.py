"""Bảng màu, phông chữ và stylesheet toàn ứng dụng."""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

NAVY = "#123B6D"          # thanh tiêu đề xanh đậm
NAVY_2 = "#0E2F57"
PRIMARY = "#1F5FA8"
SIDEBAR_BG = "#F3F6FA"
PAGE_BG = "#F6F8FB"        # xanh xám rất nhạt
BORDER = "#D5DDE8"
TEXT = "#1E2A38"
MUTED = "#5E6B7A"
SECTION = "#1B5FAA"        # tiêu đề nhóm màu xanh

# Màu ô chức năng theo nhóm nghiệp vụ (thống nhất toàn ứng dụng)
TILE_COLORS = {
    "tien": "#2E8B57",       # xanh lá: thu, chi, ngân hàng, sổ quỹ
    "mua_ban": "#1F6FB5",    # xanh dương: mua – bán, công nợ
    "kho": "#A47A1E",        # vàng nâu: kho
    "tong_hop": "#6A4AA5",   # tím: hạch toán tổng hợp, sổ kế toán
    "bao_cao": "#4C3D91",    # tím đậm: báo cáo tài chính
    "tai_san": "#C8641E",    # cam: TSCĐ, CCDC, giá thành, in hồ sơ
    "thue": "#9E3A3A",       # đỏ trầm: thuế
    "he_thong": "#3E5C7A",   # xanh xám: hệ thống
}
TILE_GROUP_LABEL = {
    "tien": "Tiền", "mua_ban": "Mua – bán, công nợ", "kho": "Kho", "tong_hop": "Tổng hợp, sổ sách",
    "bao_cao": "Báo cáo tài chính", "tai_san": "Tài sản, giá thành", "thue": "Thuế", "he_thong": "Hệ thống",
}

SIDEBAR_WIDTH = 208
SIDEBAR_COLLAPSED = 52


def app_font() -> QFont:
    families = set(QFontDatabase.families())
    for fam in ("Segoe UI", "Roboto", "Noto Sans", "Arial", "Liberation Sans", "DejaVu Sans"):
        if fam in families:
            f = QFont(fam)
            f.setPointSizeF(9.5)
            return f
    f = QFont()
    f.setPointSizeF(9.5)
    return f


STYLESHEET = f"""
QWidget {{ color: {TEXT}; }}
QMainWindow, #Page {{ background: {PAGE_BG}; }}
QToolTip {{ background: #FFFFE8; color: #222; border: 1px solid #C9C9A0; padding: 4px; }}

/* ---------- Thanh tiêu đề & thanh điều khiển ---------- */
#HeaderBar {{ background: {NAVY}; }}
#BrandName {{ color: white; font-weight: 700; font-size: 11pt; }}
#BrandSub {{ color: #A9C3E6; font-size: 8pt; }}
#AppTitle {{ color: white; font-weight: 600; font-size: 10.5pt; }}
#AppTitleSub {{ color: #BFD3EE; }}
#HeaderUser {{ color: #DCE8F7; }}

#ControlBar {{ background: #E9EFF6; border-bottom: 1px solid {BORDER}; }}
#ControlBar QLabel {{ color: {MUTED}; font-size: 7.5pt; }}
#ControlBar QComboBox, #ControlBar QDateEdit {{ min-height: 20px; max-height: 24px; padding: 1px 4px; background: white;
    border: 1px solid #C3CEDC; border-radius: 3px; }}
QPushButton#CtlButton {{ background: white; border: 1px solid #C3CEDC; border-radius: 3px; padding: 3px 9px; min-height: 20px; }}
QPushButton#CtlButton:hover {{ background: #E3EEFB; border-color: {PRIMARY}; }}
QPushButton#CtlButton:disabled {{ color: #9AA6B4; background: #F1F3F6; }}
QPushButton#CtlPrimary {{ background: {PRIMARY}; color: white; border: 1px solid {PRIMARY}; border-radius: 3px;
    padding: 3px 10px; font-weight: 600; min-height: 20px; }}
QPushButton#CtlPrimary:hover {{ background: #184F8E; }}

/* ---------- Menu trái ---------- */
#Sidebar {{ background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}
#Sidebar QPushButton {{ text-align: left; border: none; padding: 6px 10px; border-radius: 4px; color: #23354B; }}
#Sidebar QPushButton:hover {{ background: #E1EAF5; }}
#Sidebar QPushButton:checked {{ background: {PRIMARY}; color: white; font-weight: 600; }}
#SidebarToggle {{ border: none; color: {MUTED}; padding: 4px; }}

/* ---------- Tab làm việc ---------- */
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDER}; background: {PAGE_BG}; }}
QTabBar::tab {{ background: #E6ECF3; border: 1px solid {BORDER}; border-bottom: none; padding: 5px 10px;
    margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; color: #33475E; max-width: 220px; }}
QTabBar::tab:selected {{ background: white; color: {NAVY}; font-weight: 600; border-top: 2px solid {PRIMARY}; }}
QTabBar::tab:hover:!selected {{ background: #DCE6F2; }}

/* ---------- Tiêu đề nhóm ---------- */
#SectionTitle {{ color: {SECTION}; font-weight: 700; font-size: 10pt; letter-spacing: 0.3px; }}
#SectionLine {{ background: #C9D7EA; max-height: 1px; min-height: 1px; }}
#PageTitle {{ color: {NAVY}; font-weight: 700; font-size: 12pt; }}
#Hint {{ color: {MUTED}; font-size: 8.5pt; }}

/* ---------- Bảng ---------- */
QTableView, QTableWidget, QTreeWidget {{ background: white; gridline-color: #E3E8EF; border: 1px solid {BORDER};
    selection-background-color: #CFE2FA; selection-color: #0F2340; alternate-background-color: #F8FAFD; }}
QHeaderView::section {{ background: #EAF0F7; color: #26405F; font-weight: 600; border: none;
    border-right: 1px solid #D6DEE9; border-bottom: 1px solid #C9D4E2; padding: 4px; }}
QTableCornerButton::section {{ background: #EAF0F7; border: none; }}

/* ---------- Ô nhập ---------- */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit {{ background: white; border: 1px solid #C3CEDC;
    border-radius: 3px; padding: 2px 5px; min-height: 22px; selection-background-color: #9CC3F0; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {PRIMARY}; }}
QLineEdit:read-only {{ background: #F2F5F9; color: #44556A; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 4px; margin-top: 10px; background: white; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {SECTION}; font-weight: 700; }}

/* ---------- Nút thao tác ---------- */
QPushButton {{ background: white; border: 1px solid #C3CEDC; border-radius: 3px; padding: 4px 10px; min-height: 20px; }}
QPushButton:hover {{ background: #E8F1FC; border-color: {PRIMARY}; }}
QPushButton:pressed {{ background: #D3E4F8; }}
QPushButton:disabled {{ color: #A3AEBB; background: #F3F5F8; border-color: #DCE2EA; }}
QPushButton[role="primary"] {{ background: {PRIMARY}; color: white; border-color: {PRIMARY}; font-weight: 600; }}
QPushButton[role="primary"]:hover {{ background: #184F8E; }}
QPushButton[role="post"] {{ background: #2E8B57; color: white; border-color: #2E8B57; font-weight: 600; }}
QPushButton[role="post"]:hover {{ background: #24724A; }}
QPushButton[role="danger"] {{ color: #A12C2C; }}
QPushButton[role="primary"]:disabled, QPushButton[role="post"]:disabled {{ background: #B9C6D6; border-color: #B9C6D6; color: #EEF2F7; }}

/* ---------- Thanh trạng thái ---------- */
QStatusBar {{ background: {NAVY_2}; color: #D9E5F5; }}
QStatusBar QLabel {{ color: #D9E5F5; padding: 0 8px; }}
QStatusBar::item {{ border: none; }}

/* ---------- Tổng tiền ---------- */
#TotalBox {{ background: white; border: 1px solid {BORDER}; border-radius: 4px; }}
#TotalLabel {{ color: {MUTED}; font-size: 8.5pt; }}
#TotalValue {{ font-weight: 700; font-size: 10.5pt; color: {NAVY}; }}
#TotalDiffOk {{ font-weight: 700; font-size: 10.5pt; color: #1E7A34; }}
#TotalDiffBad {{ font-weight: 700; font-size: 10.5pt; color: #B42318; }}
#PhaseBox {{ background: #FFF8E6; border: 1px solid #F0D58C; border-radius: 6px; }}
"""
