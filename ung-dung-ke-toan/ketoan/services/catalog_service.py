"""Danh mục dùng chung: tài khoản, đối tượng, vật tư, kho, công trình, bộ phận, khoản mục CP, TSCĐ.

Danh mục được mô tả bằng metadata (CATALOGS) để giao diện, nhập Excel và kiểm tra dùng chung một nguồn.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ketoan.domain.money import round_money, to_decimal
from ketoan.services.context import BusinessError, Session


@dataclass
class Field:
    key: str
    label: str
    kind: str = "text"        # text | int | money | bool | choice | account | date
    required: bool = False
    width: int = 120
    choices: list = field(default_factory=list)   # [(value, label)]
    default: object = None


@dataclass
class Catalog:
    key: str
    title: str
    table: str
    fields: list
    fixed: dict = field(default_factory=dict)     # điều kiện cố định, ví dụ kind='NV'
    icon: str = "list"


PARTNER_KINDS = [("KH", "Khách hàng"), ("NCC", "Nhà cung cấp"), ("NV", "Nhân viên"), ("KHAC", "Khác")]
ITEM_KINDS = [("HH", "Hàng hóa"), ("VT", "Nguyên vật liệu"), ("TP", "Thành phẩm"), ("CCDC", "Công cụ dụng cụ"),
              ("DV", "Dịch vụ")]
NATURES = [("N", "Dư Nợ"), ("C", "Dư Có"), ("L", "Lưỡng tính")]

CATALOGS: dict[str, Catalog] = {c.key: c for c in [
    Catalog("account", "Hệ thống tài khoản", "account", [
        Field("code", "Số hiệu TK", required=True, width=90),
        Field("name", "Tên tài khoản", required=True, width=300),
        Field("parent_code", "TK cấp trên", "account", width=90),
        Field("nature", "Tính chất", "choice", True, 100, NATURES, "L"),
        Field("is_detail", "Hạch toán", "bool", width=80, default=1),
        Field("require_partner", "Bắt buộc đối tượng", "bool", width=135, default=0),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], icon="book"),
    Catalog("customer", "Khách hàng", "partner", [
        Field("code", "Mã khách hàng", required=True, width=100),
        Field("name", "Tên khách hàng", required=True, width=260),
        Field("tax_code", "Mã số thuế", width=110),
        Field("address", "Địa chỉ", width=260),
        Field("phone", "Điện thoại", width=100),
        Field("email", "Email", width=150),
        Field("payment_terms", "Hạn TT (ngày)", "int", width=90, default=0),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], fixed={"kind": "KH"}, icon="users"),
    Catalog("supplier", "Nhà cung cấp", "partner", [
        Field("code", "Mã NCC", required=True, width=100),
        Field("name", "Tên nhà cung cấp", required=True, width=260),
        Field("tax_code", "Mã số thuế", width=110),
        Field("address", "Địa chỉ", width=260),
        Field("phone", "Điện thoại", width=100),
        Field("email", "Email", width=150),
        Field("payment_terms", "Hạn TT (ngày)", "int", width=90, default=0),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], fixed={"kind": "NCC"}, icon="truck"),
    Catalog("employee", "Nhân viên", "partner", [
        Field("code", "Mã nhân viên", required=True, width=100),
        Field("name", "Họ và tên", required=True, width=220),
        Field("tax_code", "MST cá nhân", width=110),
        Field("address", "Địa chỉ", width=240),
        Field("phone", "Điện thoại", width=100),
        Field("email", "Email", width=150),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], fixed={"kind": "NV"}, icon="user"),
    Catalog("item", "Vật tư, hàng hóa", "item", [
        Field("code", "Mã hàng", required=True, width=100),
        Field("name", "Tên vật tư, hàng hóa", required=True, width=260),
        Field("unit", "ĐVT", width=60),
        Field("kind", "Loại", "choice", True, 120, ITEM_KINDS, "HH"),
        Field("stock_account", "TK kho", "account", width=80),
        Field("tax_rate", "Thuế suất (%)", width=90),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], icon="box"),
    Catalog("warehouse", "Kho", "warehouse", [
        Field("code", "Mã kho", required=True, width=90),
        Field("name", "Tên kho", required=True, width=240),
        Field("address", "Địa chỉ", width=260),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], icon="warehouse"),
    Catalog("project", "Công trình, đơn hàng", "project", [
        Field("code", "Mã công trình", required=True, width=100),
        Field("name", "Tên công trình", required=True, width=280),
        Field("customer", "Chủ đầu tư / khách hàng", width=200),
        Field("start_date", "Ngày khởi công", "date", width=100),
        Field("end_date", "Ngày hoàn thành", "date", width=100),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], icon="building"),
    Catalog("department", "Bộ phận", "department", [
        Field("code", "Mã bộ phận", required=True, width=100),
        Field("name", "Tên bộ phận", required=True, width=260),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], icon="org"),
    Catalog("expense_item", "Khoản mục chi phí", "expense_item", [
        Field("code", "Mã khoản mục", required=True, width=100),
        Field("name", "Tên khoản mục chi phí", required=True, width=280),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], icon="tag"),
    Catalog("fixed_asset", "Tài sản cố định", "fixed_asset", [
        Field("code", "Mã tài sản", required=True, width=90),
        Field("name", "Tên tài sản", required=True, width=240),
        Field("asset_account", "TK nguyên giá", "account", width=90),
        Field("depreciation_account", "TK khấu hao", "account", width=90),
        Field("expense_account", "TK chi phí", "account", width=90),
        Field("original_cost", "Nguyên giá", "money", width=120, default=0),
        Field("start_date", "Ngày tính KH", "date", width=100),
        Field("useful_months", "Số tháng KH", "int", width=90),
        Field("department", "Bộ phận sử dụng", width=140),
        Field("active", "Đang dùng", "bool", width=80, default=1),
    ], icon="asset"),
]}

# Các tham chiếu để chặn xóa danh mục đã phát sinh
_REFERENCES = {
    "partner": [("voucher_line", "debit_partner_id"), ("voucher_line", "credit_partner_id"),
                ("voucher", "partner_id"), ("opening_balance", "partner_id")],
    "item": [("voucher_line", "item_id")],
    "warehouse": [("voucher_line", "warehouse_id")],
    "project": [("voucher_line", "project_id")],
    "department": [("voucher_line", "department_id")],
    "expense_item": [("voucher_line", "expense_item_id")],
}

LOOKUP_TABLES = {   # loại cột lưới -> bảng
    "partner": "partner", "item": "item", "warehouse": "warehouse", "project": "project",
    "department": "department", "expense": "expense_item",
}


class CatalogService:
    def __init__(self, session: Session):
        self.s = session
        self.db = session.db

    # ------------------------------------------------------------------ đọc
    def rows(self, key: str, search: str = "", only_active: bool = False):
        cat = CATALOGS[key]
        where, params = ["company_id=?"], [self.s.company_id]
        for k, v in cat.fixed.items():
            where.append(f"{k}=?")
            params.append(v)
        if only_active:
            where.append("active=1")
        if search:
            where.append("(code LIKE ? OR name LIKE ?" + (" OR tax_code LIKE ?" if cat.table == "partner" else "") + ")")
            params += [f"%{search}%", f"%{search}%"] + ([f"%{search}%"] if cat.table == "partner" else [])
        return self.db.query(f"SELECT * FROM {cat.table} WHERE {' AND '.join(where)} ORDER BY code", params)

    def get(self, key: str, rec_id: int):
        return self.db.one(f"SELECT * FROM {CATALOGS[key].table} WHERE id=? AND company_id=?", (rec_id, self.s.company_id))

    def lookup(self, kind: str):
        """Danh sách tra cứu nhanh cho lưới chứng từ: [(id/code, code, name, extra)]."""
        if kind == "account":
            return [(r["code"], r["code"], r["name"], r["require_partner"]) for r in self.db.query(
                "SELECT code, name, require_partner FROM account WHERE company_id=? AND active=1 AND is_detail=1 ORDER BY code",
                (self.s.company_id,))]
        table = LOOKUP_TABLES[kind]
        extra = {"partner": "tax_code", "item": "unit"}.get(kind, "''")
        return [(r["id"], r["code"], r["name"], r["extra"]) for r in self.db.query(
            f"SELECT id, code, name, {extra} AS extra FROM {table} WHERE company_id=? AND active=1 ORDER BY code",
            (self.s.company_id,))]

    def id_by_code(self, table: str, code: str):
        if not code:
            return None
        return self.db.scalar(f"SELECT id FROM {table} WHERE company_id=? AND code=?", (self.s.company_id, code.strip()))

    # ------------------------------------------------------------------ ghi
    def normalize(self, key: str, values: dict) -> dict:
        """Kiểm tra + chuẩn hóa một bản ghi. Trả dict sạch hoặc ném BusinessError (danh sách lỗi)."""
        cat = CATALOGS[key]
        errors, out = [], {}
        for f in cat.fields:
            v = values.get(f.key, f.default)
            if isinstance(v, str):
                v = v.strip()
            if f.required and (v is None or v == ""):
                errors.append(f"«{f.label}» không được để trống")
                continue
            try:
                if f.kind == "bool":
                    v = 1 if str(v).strip().lower() in ("1", "true", "x", "có", "co", "yes") or v is True else 0
                elif f.kind == "int":
                    v = int(to_decimal(v)) if v not in (None, "") else None
                elif f.kind == "money":
                    v = round_money(v) if v not in (None, "") else 0
                elif f.kind == "choice":
                    valid = [c[0] for c in f.choices]
                    labels = {c[1].lower(): c[0] for c in f.choices}
                    if v in (None, ""):
                        v = f.default
                    elif v not in valid:
                        if str(v).lower() in labels:
                            v = labels[str(v).lower()]
                        else:
                            errors.append(f"«{f.label}» = '{v}' không hợp lệ (chọn: {', '.join(valid)})")
                elif f.kind == "account" and v:
                    if not self.db.scalar("SELECT 1 FROM account WHERE company_id=? AND code=?", (self.s.company_id, v)):
                        if not (key == "account" and f.key == "parent_code" and v in values.get("_pending_codes", ())):
                            errors.append(f"«{f.label}» = '{v}' không có trong hệ thống tài khoản")
                elif f.kind == "date" and v:
                    from datetime import date as _d
                    _d.fromisoformat(str(v)[:10])
                    v = str(v)[:10]
            except (ValueError, TypeError):
                errors.append(f"«{f.label}» = '{v}' sai định dạng")
            out[f.key] = v
        if key == "account" and out.get("code"):
            if not out["code"].isdigit():
                errors.append("Số hiệu tài khoản chỉ gồm chữ số")
            if out.get("parent_code") and not out["code"].startswith(out["parent_code"]):
                errors.append("Số hiệu TK con phải bắt đầu bằng số hiệu TK cấp trên")
        if errors:
            raise BusinessError("; ".join(errors))
        out.update(cat.fixed)
        return out

    def save(self, key: str, values: dict, rec_id: int | None = None) -> int:
        cat = CATALOGS[key]
        self.s.require("edit" if rec_id else "add", f"cập nhật danh mục {cat.title}")
        data = self.normalize(key, values)
        dup = self.db.scalar(f"SELECT id FROM {cat.table} WHERE company_id=? AND code=? AND id<>?",
                             (self.s.company_id, data["code"], rec_id or 0))
        if dup:
            raise BusinessError(f"Mã '{data['code']}' đã tồn tại trong {cat.title.lower()}.")
        with self.db.transaction():
            if key == "account":
                data["level"] = 1 if not data.get("parent_code") else (
                    (self.db.scalar("SELECT level FROM account WHERE company_id=? AND code=?",
                                    (self.s.company_id, data["parent_code"]), 0) or 0) + 1)
                if rec_id:
                    old = self.get(key, rec_id)
                    if old["code"] != data["code"] and self._account_used(old["code"]):
                        raise BusinessError("Tài khoản đã phát sinh số liệu, không được đổi số hiệu.")
                if data.get("parent_code"):
                    self.db.execute("UPDATE account SET is_detail=0 WHERE company_id=? AND code=?",
                                    (self.s.company_id, data["parent_code"]))
                    if self._account_used(data["parent_code"]):
                        raise BusinessError(f"TK cấp trên {data['parent_code']} đã phát sinh số liệu; "
                                            "cần chuyển số liệu sang TK chi tiết trước khi mở TK con.")
            cols = list(data.keys())
            if rec_id:
                self.db.execute(f"UPDATE {cat.table} SET {', '.join(c + '=?' for c in cols)} WHERE id=? AND company_id=?",
                                [data[c] for c in cols] + [rec_id, self.s.company_id])
                self.s.audit("Sửa danh mục", cat.table, data["code"], data)
            else:
                cur = self.db.execute(
                    f"INSERT INTO {cat.table}(company_id, {', '.join(cols)}) VALUES(?, {', '.join('?' * len(cols))})",
                    [self.s.company_id] + [data[c] for c in cols])
                rec_id = cur.lastrowid
                self.s.audit("Thêm danh mục", cat.table, data["code"], data)
        return rec_id

    def _account_used(self, code: str) -> bool:
        c = self.s.company_id
        return bool(
            self.db.scalar("SELECT 1 FROM ledger_entry WHERE company_id=? AND account_code=? LIMIT 1", (c, code)) or
            self.db.scalar("""SELECT 1 FROM voucher_line l JOIN voucher v ON v.id=l.voucher_id
                              WHERE v.company_id=? AND (l.debit_account=? OR l.credit_account=?) LIMIT 1""", (c, code, code)) or
            self.db.scalar("SELECT 1 FROM opening_balance WHERE company_id=? AND account_code=? LIMIT 1", (c, code)))

    def delete(self, key: str, rec_id: int):
        cat = CATALOGS[key]
        self.s.require("delete", f"xóa danh mục {cat.title}")
        rec = self.get(key, rec_id)
        if not rec:
            return
        if cat.table == "account":
            if self._account_used(rec["code"]):
                raise BusinessError(f"Tài khoản {rec['code']} đã phát sinh số liệu, không thể xóa. "
                                    "Có thể bỏ chọn «Đang dùng» để ngừng sử dụng.")
            if self.db.scalar("SELECT 1 FROM account WHERE company_id=? AND parent_code=?", (self.s.company_id, rec["code"])):
                raise BusinessError(f"Tài khoản {rec['code']} đang có tài khoản con.")
        for table, col in _REFERENCES.get(cat.table, []):
            if self.db.scalar(f"SELECT 1 FROM {table} WHERE {col}=? LIMIT 1", (rec_id,)):
                raise BusinessError(f"'{rec['code']}' đã được sử dụng trên chứng từ/số dư, không thể xóa. "
                                    "Có thể bỏ chọn «Đang dùng» để ngừng sử dụng.")
        with self.db.transaction():
            self.db.execute(f"DELETE FROM {cat.table} WHERE id=? AND company_id=?", (rec_id, self.s.company_id))
            self.s.audit("Xóa danh mục", cat.table, rec["code"], dict(rec))

    # ------------------------------------------------------------------ nhập Excel
    def import_rows(self, key: str, records: list[dict], dry_run: bool = True):
        """Kiểm tra (và nhập nếu dry_run=False) danh sách bản ghi đã ánh xạ cột.

        Trả về (số bản ghi hợp lệ, [(dòng excel, mã, thông báo lỗi)]). Khi có lỗi thì KHÔNG nhập gì.
        """
        cat = CATALOGS[key]
        errors, clean, seen = [], [], set()
        pending_codes = {str(r.get("code", "")).strip() for r in records}
        for r in records:
            row_no = r.pop("_row", "?")
            try:
                r["_pending_codes"] = pending_codes
                data = self.normalize(key, r)
                if data["code"] in seen:
                    raise BusinessError(f"Mã '{data['code']}' bị lặp trong file")
                seen.add(data["code"])
                existing = self.db.scalar(f"SELECT id FROM {cat.table} WHERE company_id=? AND code=?",
                                          (self.s.company_id, data["code"]))
                clean.append((row_no, existing, data))
            except BusinessError as e:
                errors.append((row_no, r.get("code", ""), str(e)))
        if dry_run or errors:
            return len(clean), errors
        self.s.require("add", f"nhập Excel danh mục {cat.title}")
        if key == "account":
            clean.sort(key=lambda x: len(x[2]["code"]))   # TK cha trước TK con
        with self.db.transaction():
            for _, existing, data in clean:
                self.save(key, data, existing)
            self.s.audit("Nhập Excel danh mục", cat.table, "", {"so_ban_ghi": len(clean)})
        return len(clean), []
