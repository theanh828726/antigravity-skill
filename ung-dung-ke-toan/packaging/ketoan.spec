# -*- mode: python ; coding: utf-8 -*-
# Đóng gói Ứng dụng Kế toán thành thư mục chạy được trên Windows.
#   pyinstaller --noconfirm packaging/ketoan.spec      (chạy tại thư mục ung-dung-ke-toan)
# Kết quả: dist/UngDungKeToan/UngDungKeToan.exe
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "ketoan" / "data" / "schema.sql"), "ketoan/data")],
    hiddenimports=["openpyxl", "PySide6.QtPrintSupport"],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtPdf", "PySide6.QtBluetooth", "PySide6.QtPositioning", "tkinter", "pytest",
              "numpy", "pandas", "PIL", "lxml", "matplotlib", "scipy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="UngDungKeToan",
    console=False,
    icon=str(ROOT / "packaging" / "app.ico"),
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="UngDungKeToan")
