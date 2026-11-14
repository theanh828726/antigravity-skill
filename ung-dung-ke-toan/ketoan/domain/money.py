"""Chính sách số học tiền tệ và số lượng.

- Không dùng float cho tiền. Mọi tính toán dùng ``decimal.Decimal``.
- Tiền VND lưu dạng INTEGER (đồng) trong CSDL => SUM trong SQL chính xác tuyệt đối.
- Làm tròn: ROUND_HALF_UP (làm tròn nửa lên – quy ước phổ biến trong kế toán VN).
    * Thành tiền  = round(Số lượng × Đơn giá, MONEY_DECIMALS)   – theo từng dòng
    * Tiền thuế   = round(Thành tiền × Thuế suất / 100, MONEY_DECIMALS) – theo từng dòng
    * Tổng chứng từ = tổng các dòng đã làm tròn (không làm tròn lại tổng).
- Số lượng: tối đa 4 chữ số thập phân; Đơn giá: tối đa 4 chữ số thập phân.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEY_DECIMALS = 0          # VND: không có đơn vị lẻ
QTY_DECIMALS = 4
PRICE_DECIMALS = 4

ZERO = Decimal("0")


def to_decimal(value) -> Decimal:
    """Chuyển giá trị bất kỳ (str/int/Decimal/None) thành Decimal. Chuỗi rỗng => 0.

    Hỗ trợ định dạng Việt Nam '1.234.567,89' và định dạng '1,234,567.89'.
    """
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    s = str(value).strip().replace(" ", "").replace(" ", "")
    if not s or s == "-":
        return ZERO
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    s = s.rstrip("%")
    if "," in s and "." in s:
        # dấu xuất hiện sau cùng là dấu thập phân
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            s = s.replace(",", ".")          # 12,5 => 12.5
        else:
            s = s.replace(",", "")           # 1,234,567 => 1234567
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3 and len(s.split(".")[0]) <= 3 and s.split(".")[0] not in ("0", "-0")):
        # 1.234.567 hoặc 1.234 (định dạng VN, nhóm nghìn)
        s = s.replace(".", "")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Giá trị số không hợp lệ: '{value}'") from exc
    return -d if negative else d


def round_money(value) -> int:
    d = to_decimal(value)
    q = Decimal(1).scaleb(-MONEY_DECIMALS)
    return int(d.quantize(q, rounding=ROUND_HALF_UP))


def round_qty(value) -> Decimal:
    return to_decimal(value).quantize(Decimal(1).scaleb(-QTY_DECIMALS), rounding=ROUND_HALF_UP).normalize()


def round_price(value) -> Decimal:
    return to_decimal(value).quantize(Decimal(1).scaleb(-PRICE_DECIMALS), rounding=ROUND_HALF_UP).normalize()


def line_amount(qty, price) -> int:
    return round_money(to_decimal(qty) * to_decimal(price))


def tax_amount(amount, rate) -> int:
    return round_money(to_decimal(amount) * to_decimal(rate) / Decimal(100))


def fmt_money(value, blank_zero: bool = True) -> str:
    """Định dạng tiền kiểu Việt Nam: 1.234.567 ; số âm hiển thị (1.234)."""
    if value is None or value == "":
        return ""
    v = int(value) if not isinstance(value, Decimal) else int(value)
    if v == 0 and blank_zero:
        return ""
    s = f"{abs(v):,}".replace(",", ".")
    return f"({s})" if v < 0 else s


def fmt_decimal(value, blank_zero: bool = True) -> str:
    if value is None or value == "":
        return ""
    d = to_decimal(value)
    if d == 0 and blank_zero:
        return ""
    d = d.normalize()
    sign = "-" if d < 0 else ""
    d = abs(d)
    int_part = int(d)
    frac = d - int_part
    s = f"{int_part:,}".replace(",", ".")
    if frac:
        frac_s = format(frac, "f").split(".")[1].rstrip("0")
        if frac_s:
            s += "," + frac_s
    return sign + s


def dec_to_str(value) -> str:
    """Lưu Decimal xuống CSDL dạng chuỗi chuẩn (không mất chính xác)."""
    d = to_decimal(value)
    return format(d.normalize(), "f") if d != 0 else "0"
