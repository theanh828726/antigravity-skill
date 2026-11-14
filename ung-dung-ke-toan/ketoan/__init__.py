"""Ứng dụng Kế toán – Hocviendaotaoai.

Kiến trúc phân lớp:
    domain   : kiểu dữ liệu, tiền tệ, hằng số nghiệp vụ (không phụ thuộc Qt/DB)
    data     : kết nối CSDL, lược đồ, giao dịch, dữ liệu mẫu
    services : nghiệp vụ (chứng từ, ghi sổ, sổ sách, cảnh báo, phân quyền, ...)
    reports  : xuất Excel / PDF / in
    ui       : giao diện PySide6
"""

APP_NAME = "Ứng dụng Kế toán"
APP_BRAND = "Hocviendaotaoai"
APP_VERSION = "1.2.0-gd3"
