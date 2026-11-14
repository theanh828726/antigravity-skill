"""Đọc hóa đơn điện tử XML → đề xuất chứng từ để NGƯỜI DÙNG KIỂM TRA trước khi tạo.

CẤU TRÚC ĐƯỢC HỖ TRỢ (giai đoạn 2): hóa đơn GTGT dạng XML có các thẻ
    HDon/DLHDon/TTChung   : KHMSHDon (mẫu số), KHHDon (ký hiệu), SHDon (số), NLap (ngày lập), DVTTe (tiền tệ)
    HDon/DLHDon/NDHDon/NBan, NMua : Ten, MST, DChi
    .../DSHHDVu/HHDVu     : TChat, STT, MHHDVu, THHDVu, DVTinh, SLuong, DGia, ThTien, TSuat
    .../TToan             : TgTCThue (tổng tiền chưa thuế), TgTThue (tổng thuế), TgTTTBSo (tổng thanh toán)
Không phụ thuộc namespace. TChat: 1 hàng hóa/dịch vụ, 2 khuyến mại (thành tiền 0), 3 chiết khấu thương mại (ghi âm),
4 ghi chú (bỏ qua). Chỉ hỗ trợ đồng tiền VND. Cấu trúc này cần được kiểm chứng với file hóa đơn thực tế của nhà cung cấp
dịch vụ hóa đơn; thẻ không nhận diện được sẽ được báo trong danh sách cảnh báo.
Ứng dụng KHÔNG kiểm tra chữ ký số và KHÔNG tra cứu tình trạng hóa đơn trên hệ thống của cơ quan thuế.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from ketoan.domain.money import round_money, tax_amount, to_decimal
from ketoan.services.context import BusinessError, Session
from ketoan.services.voucher_service import VoucherService

MAX_XML_BYTES = 5 * 1024 * 1024


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _find(node, *path):
    cur = node
    for name in path:
        if cur is None:
            return None
        cur = next((c for c in cur if _local(c.tag) == name), None)
    return cur


def _deep(node, name):
    for el in node.iter():
        if _local(el.tag) == name:
            return el
    return None


def _text(node, name, default=""):
    el = _find(node, name) if node is not None else None
    return (el.text or "").strip() if el is not None and el.text else default


@dataclass
class XmlLine:
    stt: str
    kind: str              # TChat
    code: str
    name: str
    unit: str
    quantity: object
    price: object
    amount: int
    rate_text: str
    rate: object | None    # None: không chịu thuế / không kê khai
    item_code: str = ""    # mã hàng trong danh mục (đề xuất, người dùng sửa được)
    account: str = ""      # TK hàng/chi phí (mua) hoặc doanh thu (bán)
    warehouse: str = ""


@dataclass
class XmlInvoice:
    path: str
    form: str = ""
    series: str = ""
    number: str = ""
    date: str = ""
    currency: str = "VND"
    seller_name: str = ""
    seller_tax: str = ""
    seller_addr: str = ""
    buyer_name: str = ""
    buyer_tax: str = ""
    buyer_addr: str = ""
    lines: list = field(default_factory=list)
    total_before_tax: int = 0
    total_tax: int = 0
    total_payment: int = 0
    warnings: list = field(default_factory=list)
    direction: str = ""          # "BKMH" mua vào | "BKBH" bán ra | "" không thuộc doanh nghiệp
    partner_code: str = ""       # đối tượng khớp trong danh mục
    duplicate_of: str = ""


def parse_file(path: str | Path) -> XmlInvoice:
    p = Path(path)
    if p.stat().st_size > MAX_XML_BYTES:
        raise BusinessError(f"{p.name}: file quá lớn (> 5 MB).")
    try:
        root = ET.parse(str(p)).getroot()     # expat không tải thực thể ngoài
    except ET.ParseError as e:
        raise BusinessError(f"{p.name}: không đọc được XML ({e}).") from None
    dl = _deep(root, "DLHDon")
    if dl is None:
        raise BusinessError(f"{p.name}: không phải cấu trúc hóa đơn được hỗ trợ (thiếu thẻ DLHDon).")
    inv = XmlInvoice(str(p))
    tt = _find(dl, "TTChung")
    if tt is None:
        raise BusinessError(f"{p.name}: thiếu thẻ TTChung.")
    inv.form, inv.series, inv.number = _text(tt, "KHMSHDon"), _text(tt, "KHHDon"), _text(tt, "SHDon")
    inv.date = _text(tt, "NLap")[:10]
    inv.currency = _text(tt, "DVTTe", "VND") or "VND"
    if inv.currency.upper() != "VND":
        inv.warnings.append(f"Đồng tiền {inv.currency}: giai đoạn 2 chỉ hỗ trợ VND – cần nhập tay.")
    nd = _find(dl, "NDHDon")
    if nd is None:
        raise BusinessError(f"{p.name}: thiếu thẻ NDHDon.")
    nb, nm = _find(nd, "NBan"), _find(nd, "NMua")
    inv.seller_name, inv.seller_tax, inv.seller_addr = _text(nb, "Ten"), _text(nb, "MST"), _text(nb, "DChi")
    inv.buyer_name, inv.buyer_tax, inv.buyer_addr = _text(nm, "Ten"), _text(nm, "MST"), _text(nm, "DChi")
    ds = _find(nd, "DSHHDVu")
    for h in (ds if ds is not None else []):
        if _local(h.tag) != "HHDVu":
            continue
        kind = _text(h, "TChat", "1")
        if kind == "4":
            continue
        try:
            qty, price = to_decimal(_text(h, "SLuong")), to_decimal(_text(h, "DGia"))
            amount = round_money(_text(h, "ThTien"))
        except ValueError as e:
            inv.warnings.append(f"Dòng {_text(h, 'STT')}: {e}")
            continue
        if kind == "3" and amount > 0:
            amount = -amount
        rate_text = _text(h, "TSuat")
        rate = None
        if rate_text and rate_text.upper() not in ("KCT", "KKKNT"):
            try:
                rate = to_decimal(rate_text.rstrip("%"))
            except ValueError:
                inv.warnings.append(f"Dòng {_text(h, 'STT')}: thuế suất '{rate_text}' không đọc được.")
        if kind == "2":
            amount = 0
        inv.lines.append(XmlLine(_text(h, "STT"), kind, _text(h, "MHHDVu"), _text(h, "THHDVu"), _text(h, "DVTinh"),
                                 qty, price, amount, rate_text, rate))
    tto = _find(nd, "TToan")
    if tto is not None:
        inv.total_before_tax = round_money(_text(tto, "TgTCThue") or 0)
        inv.total_tax = round_money(_text(tto, "TgTThue") or 0)
        inv.total_payment = round_money(_text(tto, "TgTTTBSo") or 0)
    else:
        inv.warnings.append("Thiếu thẻ TToan (tổng thanh toán).")
    if not inv.lines:
        inv.warnings.append("Hóa đơn không có dòng hàng hóa, dịch vụ.")
    for name, val in (("ký hiệu", inv.series), ("số hóa đơn", inv.number), ("ngày lập", inv.date)):
        if not val:
            inv.warnings.append(f"Thiếu {name}.")
    return inv


class XmlInvoiceService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    def checks(self, inv: XmlInvoice) -> list[tuple]:
        """Đối chiếu nội bộ hóa đơn: [(nội dung, giá trị trên XML, giá trị tính lại, chênh lệch)]."""
        sum_amount = sum(l.amount for l in inv.lines)
        sum_tax = sum(tax_amount(l.amount, l.rate) for l in inv.lines if l.rate is not None)
        out = [("Tổng tiền chưa thuế", inv.total_before_tax, sum_amount, inv.total_before_tax - sum_amount),
               ("Tổng tiền thuế", inv.total_tax, sum_tax, inv.total_tax - sum_tax),
               ("Tổng thanh toán", inv.total_payment, inv.total_before_tax + inv.total_tax,
                inv.total_payment - inv.total_before_tax - inv.total_tax)]
        for l in inv.lines:
            if l.quantity and l.price and l.kind == "1":
                expect = round_money(l.quantity * l.price)
                if abs(expect - l.amount) > 1:
                    out.append((f"Dòng {l.stt}: SL × ĐG", l.amount, expect, l.amount - expect))
        return out

    def analyze(self, inv: XmlInvoice) -> XmlInvoice:
        comp = self.s.company
        my_tax = (comp["tax_code"] or "").strip()
        if my_tax and inv.buyer_tax == my_tax:
            inv.direction = "BKMH"
            other_tax, other_name = inv.seller_tax, inv.seller_name
        elif my_tax and inv.seller_tax == my_tax:
            inv.direction = "BKBH"
            other_tax, other_name = inv.buyer_tax, inv.buyer_name
        else:
            inv.direction = ""
            inv.warnings.append(f"MST người bán ({inv.seller_tax}) và người mua ({inv.buyer_tax}) đều khác MST doanh nghiệp "
                                f"({my_tax or 'chưa khai báo'}) – hóa đơn không thuộc doanh nghiệp đang mở.")
            other_tax, other_name = inv.seller_tax, inv.seller_name
        inv.partner_code = self.db.scalar("SELECT code FROM partner WHERE company_id=? AND tax_code=? AND tax_code<>'' "
                                          "ORDER BY (kind=?) DESC LIMIT 1",
                                          (self.s.company_id, other_tax, "NCC" if inv.direction == "BKMH" else "KH")) or ""
        if not inv.partner_code:
            inv.warnings.append(f"Chưa có đối tượng MST {other_tax} ({other_name}) trong danh mục – có thể tạo mới.")
        dup = self.db.scalar("""SELECT number FROM voucher WHERE company_id=? AND invoice_no=? AND COALESCE(invoice_series,'')=?
                                AND COALESCE(tax_code,'')=? LIMIT 1""",
                             (self.s.company_id, inv.number, inv.series, other_tax))
        inv.duplicate_of = dup or ""
        items = self.db.query("SELECT code, name, kind, stock_account FROM item WHERE company_id=? AND active=1",
                              (self.s.company_id,))
        by_code = {r["code"].lower(): r for r in items}
        by_name = {r["name"].strip().lower(): r for r in items}
        wh = self.db.scalar("SELECT code FROM warehouse WHERE company_id=? AND active=1 ORDER BY code LIMIT 1",
                            (self.s.company_id,)) or ""
        for l in inv.lines:
            it = by_code.get(l.code.lower()) if l.code else None
            it = it or by_name.get(l.name.strip().lower())
            if it:
                l.item_code = it["code"]
            is_service = (it is not None and it["kind"] == "DV") or (it is None and not l.quantity)
            if inv.direction == "BKMH":
                l.account = (it["stock_account"] if it and it["stock_account"] else ("" if is_service else "156"))
                l.warehouse = wh if l.account.startswith(("152", "153", "155", "156")) else ""
            elif inv.direction == "BKBH":
                l.account = "5113" if is_service else "5111"
                l.warehouse = "" if is_service else wh
        return inv

    def create_partner(self, inv: XmlInvoice) -> str:
        from ketoan.services.catalog_service import CatalogService
        key = "supplier" if inv.direction == "BKMH" else "customer"
        name, tax, addr = ((inv.seller_name, inv.seller_tax, inv.seller_addr) if inv.direction == "BKMH"
                           else (inv.buyer_name, inv.buyer_tax, inv.buyer_addr))
        prefix = "NCC" if key == "supplier" else "KH"
        n = 1
        while self.db.scalar("SELECT 1 FROM partner WHERE company_id=? AND code=?", (self.s.company_id, f"{prefix}{n:03d}")):
            n += 1
        code = f"{prefix}{n:03d}"
        CatalogService(self.s).save(key, {"code": code, "name": name, "tax_code": tax, "address": addr})
        inv.partner_code = code
        return code

    def create_voucher(self, inv: XmlInvoice, adjust_tax_rounding: bool = False) -> int:
        """Tạo chứng từ NHÁP từ hóa đơn đã được người dùng rà soát. Không tự ghi sổ."""
        if not inv.direction:
            raise BusinessError("Hóa đơn không thuộc doanh nghiệp đang mở.")
        if not inv.partner_code:
            raise BusinessError("Chưa chọn / tạo đối tượng cho hóa đơn.")
        if inv.duplicate_of:
            raise BusinessError(f"Hóa đơn đã được nhập ở chứng từ {inv.duplicate_of}.")
        missing = [l.stt for l in inv.lines if not l.account]
        if missing:
            raise BusinessError("Các dòng chưa có tài khoản hạch toán: " + ", ".join(missing))
        purchase = inv.direction == "BKMH"
        other_tax = inv.seller_tax if purchase else inv.buyer_tax
        lines = []
        for l in inv.lines:
            d = {"description": l.name, "item": l.item_code or None, "warehouse": l.warehouse or None,
                 "unit": l.unit or None, "amount": l.amount,
                 "tax_rate": l.rate if l.rate is not None else None,
                 "tax_amount": tax_amount(l.amount, l.rate) if l.rate is not None else 0}
            if l.kind == "1" and l.quantity and l.price and round_money(l.quantity * l.price) == l.amount:
                d.update(quantity=l.quantity, unit_price=l.price)
            elif l.quantity and l.kind == "1":
                d.update(quantity=l.quantity)
            if purchase:
                d.update(debit_account=l.account, credit_account="331", credit_partner=inv.partner_code)
            else:
                d.update(debit_account="131", credit_account=l.account, debit_partner=inv.partner_code)
            lines.append(d)
        diff = inv.total_tax - sum(int(d["tax_amount"] or 0) for d in lines)
        if adjust_tax_rounding and diff and abs(diff) <= len(lines):
            taxed = [d for d in lines if d["tax_rate"] is not None]
            if taxed:
                taxed[-1]["tax_amount"] = int(taxed[-1]["tax_amount"]) + diff
        header = {"vtype": inv.direction, "voucher_date": inv.date, "posting_date": inv.date,
                  "partner_code": inv.partner_code, "tax_code": other_tax, "invoice_no": inv.number,
                  "invoice_series": inv.series, "invoice_date": inv.date,
                  "description": f"{'Mua' if purchase else 'Bán'} hàng theo HĐ {inv.series} số {inv.number} (nhập từ XML)"}
        vid = VoucherService(self.s).save(header, lines)
        with self.db.transaction():
            self.s.audit("Tạo chứng từ từ hóa đơn XML", "voucher", vid, {"file": Path(inv.path).name, "so_hd": inv.number})
        return vid

