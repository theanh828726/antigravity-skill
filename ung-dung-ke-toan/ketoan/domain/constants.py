"""Hằng số nghiệp vụ dùng chung giữa các lớp."""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------- Trạng thái
DRAFT = "DRAFT"
CHECKED = "CHECKED"
POSTED = "POSTED"
LOCKED = "LOCKED"          # trạng thái hiển thị (suy ra từ kỳ đã khóa), không lưu

STATUS_LABEL = {
    DRAFT: "Nháp",
    CHECKED: "Đã kiểm tra",
    POSTED: "Đã ghi sổ",
    LOCKED: "Đã khóa kỳ",
}
STATUS_COLOR = {          # nền, chữ
    DRAFT: ("#FFF4D6", "#8A5A00"),
    CHECKED: ("#DCEBFF", "#0B4FA8"),
    POSTED: ("#DFF5E3", "#1E7A34"),
    LOCKED: ("#ECE4F7", "#5B2D90"),
}

# ---------------------------------------------------------------- Mức cảnh báo
SEV_BLOCK = "BLOCK"
SEV_REVIEW = "REVIEW"
SEV_INFO = "INFO"
SEV_LABEL = {SEV_BLOCK: "Lỗi chặn ghi sổ", SEV_REVIEW: "Cần kiểm tra", SEV_INFO: "Thông tin"}

# ---------------------------------------------------------------- Phân quyền
PERMISSIONS = [
    ("view", "Xem"),
    ("add", "Thêm"),
    ("edit", "Sửa"),
    ("delete", "Xóa"),
    ("post", "Ghi sổ / Bỏ ghi sổ"),
    ("lock", "Khóa / mở khóa kỳ"),
    ("export", "Xuất dữ liệu (Excel, PDF, in)"),
    ("admin", "Quản trị hệ thống (người dùng, sao lưu, khôi phục, cấu hình)"),
]
PERMISSION_CODES = [p for p, _ in PERMISSIONS]

# ---------------------------------------------------------------- Cột lưới chứng từ
# key, nhãn, độ rộng mặc định, kiểu (text|account|partner|item|warehouse|project|department|expense|qty|price|money|rate)
LINE_COLUMNS = [
    ("line_no", "STT", 36, "int"),
    ("description", "Diễn giải", 180, "text"),
    ("debit_account", "TK Nợ", 58, "account"),
    ("credit_account", "TK Có", 58, "account"),
    ("debit_partner", "Đối tượng Nợ", 86, "partner"),
    ("credit_partner", "Đối tượng Có", 86, "partner"),
    ("item", "Mã hàng", 76, "item"),
    ("warehouse", "Kho", 58, "warehouse"),
    ("unit", "ĐVT", 48, "text"),
    ("quantity", "Số lượng", 68, "qty"),
    ("unit_price", "Đơn giá", 92, "price"),
    ("amount", "Thành tiền", 106, "money"),
    ("tax_rate", "Thuế suất", 62, "rate"),
    ("tax_amount", "Tiền thuế", 92, "money"),
    ("project", "Công trình", 80, "project"),
    ("department", "Bộ phận", 70, "department"),
    ("expense_item", "Khoản mục CP", 90, "expense"),
]
LINE_COLUMN_KEYS = [c[0] for c in LINE_COLUMNS]

_BASE = ["line_no", "description", "debit_account", "credit_account"]
_OBJ = ["debit_partner", "credit_partner"]
_GOODS = ["item", "warehouse", "unit", "quantity", "unit_price", "amount"]
_TAX = ["tax_rate", "tax_amount"]
_COST = ["project", "department", "expense_item"]


@dataclass(frozen=True)
class VoucherType:
    code: str
    name: str
    prefix: str
    columns: list = field(default_factory=list)
    default_debit: str = ""
    default_credit: str = ""
    tax_account: str = ""         # TK thuế GTGT tự sinh bút toán thuế
    tax_side: str = ""            # 'D' thuế ghi Nợ TK thuế (đầu vào) | 'C' ghi Có TK thuế (đầu ra)
    color_group: str = "tong_hop"
    note: str = ""


VOUCHER_TYPES: dict[str, VoucherType] = {v.code: v for v in [
    VoucherType("BKMH", "Bảng kê mua hàng", "MH", _BASE + _OBJ + _GOODS + _TAX + _COST,
                "156", "331", "1331", "D", "mua_ban",
                "Thuế GTGT đầu vào tự hạch toán Nợ TK thuế / Có TK đối ứng của dòng."),
    VoucherType("BKBH", "Bảng kê bán hàng", "BH", _BASE + _OBJ + _GOODS + _TAX + _COST,
                "131", "5111", "33311", "C", "mua_ban",
                "Thuế GTGT đầu ra tự hạch toán Nợ TK đối ứng của dòng / Có TK thuế."),
    VoucherType("PKMB", "Phiếu kế toán mua – bán", "KMB", _BASE + _OBJ + ["amount"] + _COST,
                "", "", "", "", "mua_ban",
                "Điều chỉnh mua – bán (giảm giá, trả lại, chiết khấu). Thuế nhập trực tiếp bằng dòng TK thuế."),
    VoucherType("PT", "Phiếu thu", "PT", _BASE + _OBJ + ["amount"] + _COST,
                "1111", "131", "", "", "tien"),
    VoucherType("PC", "Phiếu chi", "PC", _BASE + _OBJ + ["amount"] + _COST,
                "331", "1111", "", "", "tien"),
    VoucherType("PNK", "Phiếu nhập kho", "NK", _BASE + _OBJ + _GOODS + _COST,
                "155", "154", "", "", "kho"),
    VoucherType("PXK", "Phiếu xuất kho", "XK", _BASE + _OBJ + _GOODS + _COST,
                "632", "156", "", "", "kho",
                "Giai đoạn 1: đơn giá xuất nhập tay. Tính giá xuất kho tự động thuộc giai đoạn 2."),
    VoucherType("PKT", "Nghiệp vụ hạch toán", "KT", _BASE + _OBJ + ["amount"] + _COST,
                "", "", "", "", "tong_hop"),
    VoucherType("NH", "Nghiệp vụ ngân hàng", "NH", _BASE + _OBJ + ["amount"] + _COST,
                "1121", "131", "", "", "tien"),
    VoucherType("CTK", "Chứng từ khác", "CK", _BASE + _OBJ + ["amount"] + _COST,
                "", "", "", "", "tong_hop"),
    VoucherType("KC", "Kết chuyển cuối kỳ", "KC", _BASE + _OBJ + ["amount"],
                "", "", "", "", "tong_hop",
                "Chứng từ do chức năng Kết chuyển sinh ra; hoàn tác bằng chức năng Kết chuyển."),
]}

# Tài khoản có dư lưỡng tính – CĐSPS trình bày cả hai bên theo từng đối tượng
DUAL_BALANCE_PREFIXES = ("131", "331", "138", "338", "141", "334", "136", "336", "333", "421", "413")

# Nhóm tài khoản phục vụ kết chuyển (cấu hình mẫu theo hệ thống TK của dữ liệu minh họa)
CLOSING_REVENUE_PREFIXES = ("511", "515", "711")
CLOSING_EXPENSE_PREFIXES = ("632", "635", "642", "811", "821")
CLOSING_RESULT_ACCOUNT = "911"
CLOSING_PROFIT_ACCOUNT = "4212"

INVENTORY_PREFIXES = ("152", "153", "155", "156")
