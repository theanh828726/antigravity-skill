"""Khởi tạo CSDL mới và dữ liệu minh họa liên kết đầy đủ.

Dữ liệu minh họa được tạo QUA LỚP NGHIỆP VỤ (lưu → kiểm tra → ghi sổ) nên sổ sách, báo cáo nhất quán
và truy ngược được chứng từ. Tên doanh nghiệp, mã số thuế, đối tượng đều là giả định.
"""
from __future__ import annotations

import random
from calendar import monthrange
from pathlib import Path

from ketoan.data.db import Database
from ketoan.domain.money import to_decimal
from ketoan.services.auth_service import create_user, ensure_default_roles
from ketoan.services.context import CurrentUser, Session

# ------------------------------------------------------------------ chế độ kế toán (chưa kiểm chứng)
REGIMES = [
    ("TT133_2016", "Chế độ kế toán doanh nghiệp nhỏ và vừa", "Thông tư 133/2016/TT-BTC", "2017-01-01", None,
     "Mẫu hệ thống TK đi kèm là dữ liệu minh họa. Cần kiểm chứng hiệu lực hiện hành và các văn bản sửa đổi, "
     "thay thế từ nguồn chính thức trước khi áp dụng."),
    ("TT200_2014", "Chế độ kế toán doanh nghiệp", "Thông tư 200/2014/TT-BTC", "2015-01-01", None,
     "Chưa có mẫu hệ thống TK đi kèm – nhập hệ thống TK bằng Excel. Cần kiểm chứng hiệu lực và văn bản thay thế."),
    ("TT99_2025", "Chế độ kế toán doanh nghiệp (văn bản mới)", "Thông tư 99/2025/TT-BTC", "2026-01-01", None,
     "Chưa có mẫu hệ thống TK đi kèm. Cần kiểm chứng văn bản gốc, ngày hiệu lực, phạm vi áp dụng trước khi dùng."),
]

TAX_RATES = [
    ("0", "Thuế suất 0%", "0"), ("5", "Thuế suất 5%", "5"), ("8", "Thuế suất 8% (mức giảm theo thời kỳ)", "8"),
    ("10", "Thuế suất 10%", "10"), ("KCT", "Không chịu thuế", "0"), ("KKKNT", "Không kê khai, tính nộp", "0"),
]

# code, name, parent, nature, require_partner
TT133_ACCOUNTS = [
    ("111", "Tiền mặt", None, "N"), ("1111", "Tiền Việt Nam", "111", "N"), ("1112", "Ngoại tệ", "111", "N"),
    ("112", "Tiền gửi ngân hàng", None, "N"), ("1121", "Tiền Việt Nam", "112", "N"), ("1122", "Ngoại tệ", "112", "N"),
    ("121", "Chứng khoán kinh doanh", None, "N"),
    ("128", "Đầu tư nắm giữ đến ngày đáo hạn", None, "N"), ("1281", "Tiền gửi có kỳ hạn", "128", "N"),
    ("1288", "Các khoản đầu tư khác nắm giữ đến ngày đáo hạn", "128", "N"),
    ("131", "Phải thu của khách hàng", None, "L", 1),
    ("133", "Thuế GTGT được khấu trừ", None, "N"),
    ("1331", "Thuế GTGT được khấu trừ của hàng hóa, dịch vụ", "133", "N"),
    ("1332", "Thuế GTGT được khấu trừ của TSCĐ", "133", "N"),
    ("136", "Phải thu nội bộ", None, "L"), ("1361", "Vốn kinh doanh ở đơn vị trực thuộc", "136", "N"),
    ("1368", "Phải thu nội bộ khác", "136", "L"),
    ("138", "Phải thu khác", None, "L"), ("1381", "Tài sản thiếu chờ xử lý", "138", "N"),
    ("1386", "Cầm cố, thế chấp, ký quỹ, ký cược", "138", "N"), ("1388", "Phải thu khác", "138", "L"),
    ("141", "Tạm ứng", None, "N", 1),
    ("151", "Hàng mua đang đi đường", None, "N"), ("152", "Nguyên liệu, vật liệu", None, "N"),
    ("153", "Công cụ, dụng cụ", None, "N"), ("154", "Chi phí sản xuất, kinh doanh dở dang", None, "N"),
    ("155", "Thành phẩm", None, "N"), ("156", "Hàng hóa", None, "N"), ("157", "Hàng gửi đi bán", None, "N"),
    ("211", "Tài sản cố định", None, "N"), ("2111", "TSCĐ hữu hình", "211", "N"),
    ("2112", "TSCĐ thuê tài chính", "211", "N"), ("2113", "TSCĐ vô hình", "211", "N"),
    ("214", "Hao mòn tài sản cố định", None, "C"), ("2141", "Hao mòn TSCĐ hữu hình", "214", "C"),
    ("2142", "Hao mòn TSCĐ thuê tài chính", "214", "C"), ("2143", "Hao mòn TSCĐ vô hình", "214", "C"),
    ("2147", "Hao mòn bất động sản đầu tư", "214", "C"),
    ("217", "Bất động sản đầu tư", None, "N"),
    ("228", "Đầu tư góp vốn vào đơn vị khác", None, "N"), ("2281", "Đầu tư vào công ty liên doanh, liên kết", "228", "N"),
    ("2288", "Đầu tư khác", "228", "N"),
    ("229", "Dự phòng tổn thất tài sản", None, "C"), ("2291", "Dự phòng giảm giá chứng khoán kinh doanh", "229", "C"),
    ("2292", "Dự phòng tổn thất đầu tư vào đơn vị khác", "229", "C"), ("2293", "Dự phòng phải thu khó đòi", "229", "C"),
    ("2294", "Dự phòng giảm giá hàng tồn kho", "229", "C"),
    ("241", "Xây dựng cơ bản dở dang", None, "N"), ("2411", "Mua sắm TSCĐ", "241", "N"),
    ("2412", "Xây dựng cơ bản", "241", "N"), ("2413", "Sửa chữa lớn TSCĐ", "241", "N"),
    ("242", "Chi phí trả trước", None, "N"),
    ("331", "Phải trả cho người bán", None, "L", 1),
    ("333", "Thuế và các khoản phải nộp Nhà nước", None, "L"), ("3331", "Thuế giá trị gia tăng phải nộp", "333", "C"),
    ("33311", "Thuế GTGT đầu ra", "3331", "C"), ("33312", "Thuế GTGT hàng nhập khẩu", "3331", "C"),
    ("3332", "Thuế tiêu thụ đặc biệt", "333", "C"), ("3333", "Thuế xuất, nhập khẩu", "333", "C"),
    ("3334", "Thuế thu nhập doanh nghiệp", "333", "L"), ("3335", "Thuế thu nhập cá nhân", "333", "L"),
    ("3336", "Thuế tài nguyên", "333", "C"), ("3337", "Thuế nhà đất, tiền thuê đất", "333", "C"),
    ("3338", "Thuế bảo vệ môi trường và các loại thuế khác", "333", "C"),
    ("33381", "Thuế bảo vệ môi trường", "3338", "C"), ("33382", "Các loại thuế khác", "3338", "C"),
    ("3339", "Phí, lệ phí và các khoản phải nộp khác", "333", "C"),
    ("334", "Phải trả người lao động", None, "L"), ("335", "Chi phí phải trả", None, "C"),
    ("336", "Phải trả nội bộ", None, "L"), ("3361", "Phải trả nội bộ về vốn kinh doanh", "336", "C"),
    ("3368", "Phải trả nội bộ khác", "336", "L"),
    ("338", "Phải trả, phải nộp khác", None, "L"), ("3381", "Tài sản thừa chờ giải quyết", "338", "C"),
    ("3382", "Kinh phí công đoàn", "338", "C"), ("3383", "Bảo hiểm xã hội", "338", "C"),
    ("3384", "Bảo hiểm y tế", "338", "C"), ("3385", "Bảo hiểm thất nghiệp", "338", "C"),
    ("3386", "Nhận ký quỹ, ký cược", "338", "C"), ("3387", "Doanh thu chưa thực hiện", "338", "C"),
    ("3388", "Phải trả, phải nộp khác", "338", "L"),
    ("341", "Vay và nợ thuê tài chính", None, "C"), ("3411", "Các khoản đi vay", "341", "C"),
    ("3412", "Nợ thuê tài chính", "341", "C"),
    ("352", "Dự phòng phải trả", None, "C"), ("3521", "Dự phòng bảo hành sản phẩm hàng hóa", "352", "C"),
    ("3522", "Dự phòng bảo hành công trình xây dựng", "352", "C"), ("3524", "Dự phòng phải trả khác", "352", "C"),
    ("353", "Quỹ khen thưởng, phúc lợi", None, "C"), ("3531", "Quỹ khen thưởng", "353", "C"),
    ("3532", "Quỹ phúc lợi", "353", "C"), ("3533", "Quỹ phúc lợi đã hình thành TSCĐ", "353", "C"),
    ("3534", "Quỹ thưởng ban quản lý điều hành công ty", "353", "C"),
    ("356", "Quỹ phát triển khoa học và công nghệ", None, "C"),
    ("3561", "Quỹ phát triển khoa học và công nghệ", "356", "C"),
    ("3562", "Quỹ phát triển khoa học và công nghệ đã hình thành TSCĐ", "356", "C"),
    ("411", "Vốn đầu tư của chủ sở hữu", None, "C"), ("4111", "Vốn góp của chủ sở hữu", "411", "C"),
    ("4112", "Thặng dư vốn cổ phần", "411", "L"), ("4118", "Vốn khác", "411", "C"),
    ("413", "Chênh lệch tỷ giá hối đoái", None, "L"), ("418", "Các quỹ thuộc vốn chủ sở hữu", None, "C"),
    ("419", "Cổ phiếu quỹ", None, "N"),
    ("421", "Lợi nhuận sau thuế chưa phân phối", None, "L"),
    ("4211", "Lợi nhuận sau thuế chưa phân phối năm trước", "421", "L"),
    ("4212", "Lợi nhuận sau thuế chưa phân phối năm nay", "421", "L"),
    ("511", "Doanh thu bán hàng và cung cấp dịch vụ", None, "C"), ("5111", "Doanh thu bán hàng hóa", "511", "C"),
    ("5112", "Doanh thu bán thành phẩm", "511", "C"), ("5113", "Doanh thu cung cấp dịch vụ", "511", "C"),
    ("5118", "Doanh thu khác", "511", "C"),
    ("515", "Doanh thu hoạt động tài chính", None, "C"), ("611", "Mua hàng", None, "N"),
    ("631", "Giá thành sản xuất", None, "N"), ("632", "Giá vốn hàng bán", None, "N"),
    ("635", "Chi phí tài chính", None, "N"),
    ("642", "Chi phí quản lý kinh doanh", None, "N"), ("6421", "Chi phí bán hàng", "642", "N"),
    ("6422", "Chi phí quản lý doanh nghiệp", "642", "N"),
    ("711", "Thu nhập khác", None, "C"), ("811", "Chi phí khác", None, "N"),
    ("821", "Chi phí thuế thu nhập doanh nghiệp", None, "N"), ("911", "Xác định kết quả kinh doanh", None, "L"),
]

DEMO_USERS = [("admin", "Quản trị hệ thống", "ADMIN", "admin@123"),
              ("ketoantruong", "Nguyễn Thị Kế Toán Trưởng", "KTT", "ktt@123"),
              ("ketoanvien", "Trần Văn Kế Toán", "KTV", "ktv@123"),
              ("xem", "Người xem báo cáo", "XEM", "xem@123")]


def create_database(path: str | Path, demo: bool = True, company_name: str = "", tax_code: str = "") -> Database:
    path = Path(path)
    if path.exists():
        path.unlink()
    db = Database(path)
    db.init_schema()
    with db.transaction():
        for code, name, ref, f, t, note in REGIMES:
            db.execute("INSERT INTO accounting_regime(code, name, legal_ref, effective_from, effective_to, verified, note) "
                       "VALUES(?,?,?,?,?,0,?)", (code, name, ref, f, t, note))
        for code, name, rate in TAX_RATES:
            db.execute("INSERT INTO tax_rate(code, name, rate, effective_from, legal_ref, verified) VALUES(?,?,?,?,?,0)",
                       (code, name, rate, "2000-01-01",
                        "Luật Thuế GTGT và văn bản hướng dẫn – mức áp dụng từng thời kỳ cần kiểm chứng"))
        ensure_default_roles(db)
        for u, n, r, p in DEMO_USERS:
            create_user(db, u, n, r, p)
    admin = CurrentUser("admin", "Quản trị hệ thống", "ADMIN", "Quản trị hệ thống", {"admin"})
    if demo:
        _seed_demo(db, admin)
    else:
        s = Session(db, admin)
        with db.transaction():
            cid = _create_company(db, "DN001", company_name or "Doanh nghiệp mới", tax_code, "", "", False)
            s.company_id = cid
            _create_accounts(db, cid)
            from datetime import date
            y = date.today().year
            db.execute("INSERT INTO fiscal_year(company_id, year, start_date, end_date) VALUES(?,?,?,?)",
                       (cid, y, f"{y}-01-01", f"{y}-12-31"))
            db.execute("INSERT INTO company_regime(company_id, regime_code, effective_from) VALUES(?,?,?)",
                       (cid, "TT133_2016", f"{y}-01-01"))
    return db


def _create_company(db, code, name, tax_code, address, business, demo=True):
    cur = db.execute("INSERT INTO company(code, name, tax_code, address, business, director, chief_accountant, is_demo) "
                     "VALUES(?,?,?,?,?,?,?,?)", (code, name, tax_code, address, business, "Lê Minh Giám Đốc",
                                                 "Nguyễn Thị Kế Toán Trưởng", 1 if demo else 0))
    return cur.lastrowid


def _create_accounts(db, cid):
    parents = {a[2] for a in TT133_ACCOUNTS if a[2]}
    level = {}
    for a in TT133_ACCOUNTS:
        code, name, parent, nature = a[:4]
        req = a[4] if len(a) > 4 else 0
        level[code] = 1 if not parent else level[parent] + 1
        db.execute("INSERT INTO account(company_id, code, name, parent_code, level, nature, is_detail, require_partner) "
                   "VALUES(?,?,?,?,?,?,?,?)", (cid, code, name, parent, level[code], nature,
                                               0 if code in parents else 1, req))


def _ins(db, table, cid, rows, cols):
    for r in rows:
        db.execute(f"INSERT INTO {table}(company_id, {', '.join(cols)}) VALUES(?, {', '.join('?' * len(cols))})", (cid, *r))


def _seed_demo(db: Database, admin: CurrentUser):
    from ketoan.services.closing_service import ClosingService
    from ketoan.services.period_service import PeriodService
    from ketoan.services.voucher_service import VoucherService

    s = Session(db, admin)
    with db.transaction():
        cid = _create_company(db, "MK", "Công ty TNHH Thương mại – Dịch vụ Minh Khang (minh họa)", "0109990001",
                              "Số 18 phố Minh Họa, quận Cầu Giấy, Hà Nội", "Thương mại, dịch vụ")
        s.company_id = cid
        _create_accounts(db, cid)
        for y in (2025, 2026):
            db.execute("INSERT INTO fiscal_year(company_id, year, start_date, end_date) VALUES(?,?,?,?)",
                       (cid, y, f"{y}-01-01", f"{y}-12-31"))
        db.execute("INSERT INTO company_regime(company_id, regime_code, effective_from) VALUES(?,?,?)",
                   (cid, "TT133_2016", "2025-01-01"))
        _ins(db, "partner", cid, [
            ("KH001", "Công ty CP Công nghệ Ánh Dương (minh họa)", "KH", "0109990101", "Hà Nội", 30),
            ("KH002", "Công ty TNHH Giải pháp Văn phòng Sao Mai (minh họa)", "KH", "0109990102", "Hà Nội", 30),
            ("KH003", "Trường THPT Minh Họa", "KH", "0109990103", "Bắc Ninh", 45),
            ("KH004", "Công ty CP Xây lắp Hoàng Gia (minh họa)", "KH", "0109990104", "Hải Phòng", 30),
            ("KH005", "Công ty TNHH Thiết bị Phương Nam (minh họa)", "KH", "0309990105", "TP. Hồ Chí Minh", 15),
            ("NCC001", "Công ty TNHH Phân phối Thiết bị Số (minh họa)", "NCC", "0109990201", "Hà Nội", 30),
            ("NCC002", "Công ty CP Linh kiện Điện tử Việt (minh họa)", "NCC", "0109990202", "Hưng Yên", 45),
            ("NCC003", "Công ty TNHH Vận tải Nhanh (minh họa)", "NCC", "0109990203", "Hà Nội", 15),
            ("NCC004", "Công ty Điện lực Minh Họa", "NCC", "0109990204", "Hà Nội", 10),
            ("NV001", "Lê Minh Giám Đốc", "NV", "8000000001", "Hà Nội", 0),
            ("NV002", "Phạm Thu Kinh Doanh", "NV", "8000000002", "Hà Nội", 0),
            ("NV003", "Đỗ Văn Kho", "NV", "8000000003", "Hà Nội", 0),
            ("NV004", "Nguyễn Thị Kế Toán Trưởng", "NV", "8000000004", "Hà Nội", 0),
        ], ["code", "name", "kind", "tax_code", "address", "payment_terms"])
        _ins(db, "item", cid, [
            ("HH001", "Máy tính xách tay 14 inch", "Chiếc", "HH", "156", "10"),
            ("HH002", "Màn hình 24 inch", "Chiếc", "HH", "156", "10"),
            ("HH003", "Bàn phím cơ không dây", "Chiếc", "HH", "156", "10"),
            ("HH004", "Chuột không dây", "Chiếc", "HH", "156", "10"),
            ("HH005", "Máy in laser A4", "Chiếc", "HH", "156", "10"),
            ("HH006", "Giấy A4 70gsm", "Ram", "HH", "156", "10"),
            ("DV001", "Dịch vụ lắp đặt, cấu hình", "Lần", "DV", None, "10"),
        ], ["code", "name", "unit", "kind", "stock_account", "tax_rate"])
        _ins(db, "warehouse", cid, [("KHO01", "Kho Cầu Giấy", "Hà Nội"), ("KHO02", "Kho Long Biên", "Hà Nội")],
             ["code", "name", "address"])
        _ins(db, "project", cid, [("CT001", "Lắp đặt hệ thống mạng – Tòa nhà Minh Họa A", "Công ty CP Xây lắp Hoàng Gia (minh họa)"),
                                  ("CT002", "Trang bị phòng máy – Trường THPT Minh Họa", "Trường THPT Minh Họa")],
             ["code", "name", "customer"])
        _ins(db, "department", cid, [("BGD", "Ban giám đốc"), ("KD", "Phòng kinh doanh"), ("KT", "Phòng kế toán"),
                                     ("KHO", "Bộ phận kho")], ["code", "name"])
        _ins(db, "expense_item", cid, [("CP01", "Tiền lương"), ("CP02", "Khấu hao TSCĐ"), ("CP03", "Điện, nước"),
                                       ("CP04", "Văn phòng phẩm"), ("CP05", "Vận chuyển"), ("CP06", "Phí ngân hàng"),
                                       ("CP07", "Phân bổ chi phí trả trước")], ["code", "name"])
        _ins(db, "fixed_asset", cid, [
            ("TS001", "Xe ô tô tải 1,5 tấn", "2111", "2141", "6421", 480_000_000, "2024-01-01", 96, "KD"),
            ("TS002", "Hệ thống máy chủ văn phòng", "2111", "2141", "6422", 200_000_000, "2024-07-01", 60, "KT"),
        ], ["code", "name", "asset_account", "depreciation_account", "expense_account", "original_cost", "start_date",
            "useful_months", "department"])
        pid = {r["code"]: r["id"] for r in db.query("SELECT id, code FROM partner WHERE company_id=?", (cid,))}
        ob = [("1111", None, 185_000_000, 0), ("1121", None, 1_672_800_000, 0), ("156", None, 9_200_000, 0), ("131", pid["KH001"], 120_000_000, 0),
              ("131", pid["KH002"], 85_500_000, 0), ("2111", None, 680_000_000, 0), ("242", None, 36_000_000, 0),
              ("2141", None, 0, 136_000_000), ("331", pid["NCC001"], 0, 158_000_000),
              ("331", pid["NCC002"], 0, 64_000_000), ("334", None, 0, 92_000_000), ("33311", None, 0, 28_500_000),
              ("4111", None, 0, 1_800_000_000), ("4211", None, 0, 510_000_000)]
        db.executemany("INSERT INTO opening_balance(company_id, year, account_code, partner_id, debit, credit) "
                       "VALUES(?,?,?,?,?,?)", [(cid, 2026, *x) for x in ob])
        # tồn kho đầu kỳ chi tiết – khớp số dư đầu năm TK 156
        db.execute("""INSERT INTO opening_stock(company_id, year, item_id, warehouse_id, quantity, amount)
                      SELECT ?, 2026, i.id, w.id, '2', 9200000 FROM item i, warehouse w
                      WHERE i.company_id=? AND i.code='HH005' AND w.company_id=? AND w.code='KHO02'""", (cid, cid, cid))

    from ketoan.services.inventory_service import InventoryService
    vs, cs, ps, inv = VoucherService(s), ClosingService(s), PeriodService(s), InventoryService(s)

    def mk(vtype, d, lines, partner=None, desc="", inv=None, series=None, post=True, check=False, **kw):
        tax = db.scalar("SELECT tax_code FROM partner WHERE company_id=? AND code=?", (cid, partner)) if partner else None
        h = {"vtype": vtype, "voucher_date": d, "posting_date": d, "partner_code": partner, "tax_code": tax,
             "description": desc, "invoice_no": inv, "invoice_series": series, "invoice_date": d if inv else None}
        h.update(kw)
        v = vs.save(h, lines)
        if post:
            vs.post(v)
        elif check:
            vs.check(v)
        return v

    rnd = random.Random(2026)
    cost = {"HH001": 15_500_000, "HH002": 3_200_000, "HH003": 850_000, "HH004": 240_000, "HH005": 4_600_000,
            "HH006": 62_000}
    markup = {"HH001": 1.32, "HH002": 1.38, "HH003": 1.45, "HH004": 1.6, "HH005": 1.35, "HH006": 1.4}
    stock = {k: 0 for k in cost}
    customers = ["KH001", "KH002", "KH003", "KH004"]
    inv_no = 120
    out_inv = 0
    for m in range(1, 11):
        last = f"2026-{m:02d}-{monthrange(2026, m)[1]:02d}"
        if m > 1:   # giá nhập biến động theo tháng => tính giá xuất kho có ý nghĩa
            for code in cost:
                cost[code] = int(round(cost[code] * (1 + rnd.uniform(-0.03, 0.04)), -3))
        # ---- Kế hoạch bán trong tháng (3 khách hàng × 3 mặt hàng), mua đủ hàng + dự trữ trước khi bán
        plan = []
        for k, cus in enumerate(rnd.sample(customers, 4)):
            items = []
            for code in rnd.sample(list(cost), 3):
                q = rnd.randint(6, 12) if code not in ("HH006", "HH004") else rnd.randint(30, 60)
                if code == "HH005":
                    q = 2
                items.append((code, q))
            plan.append((k, cus, items))
        need = {c: 0 for c in cost}
        for _, _, items in plan:
            for code, q in items:
                need[code] += q
        buy = {c: need[c] - stock[c] + (2 if c not in ("HH004", "HH006") else 10)
               for c in cost if need[c] > stock[c] and c != "HH005"}
        if m in (1, 6):
            buy["HH005"] = 6
        sup = "NCC001" if m % 2 else "NCC002"
        inv_no += 1
        lines = []
        for code, q in buy.items():
            lines.append({"description": f"Mua {code}", "debit_account": "156", "credit_account": "331",
                          "credit_partner": sup, "item": code, "warehouse": "KHO01", "quantity": q,
                          "unit_price": cost[code], "tax_rate": "10"})
            stock[code] += q
        mk("BKMH", f"2026-{m:02d}-04", lines, sup, f"Mua hàng hóa tháng {m:02d}/2026", f"{inv_no:07d}", "1C26TAA")
        # ---- Bán hàng + xuất kho giá vốn
        for k, cus, items in plan:
            day = 7 + k * 5
            sl, xl = [], []
            for code, q in items:
                q = min(stock[code], q)
                if q <= 0:
                    continue
                stock[code] -= q
                price = int(round(cost[code] * markup[code], -4))
                sl.append({"description": f"Bán {code}", "debit_account": "131", "credit_account": "5111",
                           "debit_partner": cus, "item": code, "warehouse": "KHO01", "quantity": q, "unit_price": price,
                           "tax_rate": "10"})
                xl.append({"description": f"Giá vốn {code}", "debit_account": "632", "credit_account": "156",
                           "item": code, "warehouse": "KHO01", "quantity": q, "unit_price": cost[code]})
            if m % 3 == 0 and k == 0:
                sl.append({"description": "Dịch vụ lắp đặt, cấu hình", "debit_account": "131", "credit_account": "5113",
                           "debit_partner": cus, "item": "DV001", "quantity": 1, "unit_price": 6_500_000, "tax_rate": "10",
                           "project": "CT001"})
            if not sl:
                continue
            out_inv += 1
            sale_id = mk("BKBH", f"2026-{m:02d}-{day:02d}", sl, cus, f"Bán hàng cho {cus}", f"{out_inv:07d}", "1C26TMK")
            mk("PXK", f"2026-{m:02d}-{day:02d}", xl, cus, f"Xuất kho bán hàng cho {cus} (giá tạm = giá nhập gần nhất)",
               source_voucher_id=sale_id)
        # ---- Thu tiền khách hàng (qua ngân hàng / tiền mặt)
        if m == 1:
            mk("PT", "2026-01-20", [{"description": "Thu nợ cũ", "debit_account": "1111", "credit_account": "131",
                                      "credit_partner": "KH001", "amount": 120_000_000}], "KH001", "Thu nợ năm trước KH001")
            mk("NH", "2026-01-08", [{"description": "Trả nợ cũ NCC001", "debit_account": "331", "credit_account": "1121",
                                      "debit_partner": "NCC001", "amount": 158_000_000}], "NCC001", "Chuyển khoản trả nợ NCC001")
        else:
            prev = f"2026-{m - 1:02d}"
            for r in db.query("""SELECT p.code, SUM(e.debit) amt FROM ledger_entry e JOIN partner p ON p.id=e.partner_id
                                 WHERE e.company_id=? AND e.account_code='131' AND substr(e.posting_date,1,7)=? AND e.debit>0
                                 GROUP BY p.code""", (cid, prev)):
                amt = int(r["amt"] * (1 if r["code"] != "KH003" else 0.6))
                mk("NH", f"2026-{m:02d}-15", [{"description": f"Khách hàng {r['code']} thanh toán",
                                                "debit_account": "1121", "credit_account": "131",
                                                "credit_partner": r["code"], "amount": amt}],
                   r["code"], f"Thu tiền hàng tháng {m - 1:02d} – {r['code']}")
            for r in db.query("""SELECT p.code, SUM(e.credit) amt FROM ledger_entry e JOIN partner p ON p.id=e.partner_id
                                 WHERE e.company_id=? AND e.account_code='331' AND substr(e.posting_date,1,7)=? AND e.credit>0
                                 GROUP BY p.code""", (cid, prev)):
                mk("NH", f"2026-{m:02d}-18", [{"description": f"Thanh toán {r['code']}", "debit_account": "331",
                                                "credit_account": "1121", "debit_partner": r["code"],
                                                "amount": r["amt"]}], r["code"], f"Trả tiền hàng tháng {m - 1:02d}")
        # ---- Chi phí: điện, vận chuyển, lương, khấu hao, phân bổ, phí NH
        mk("PC", f"2026-{m:02d}-22", [
            {"description": "Tiền điện văn phòng", "debit_account": "6422", "credit_account": "1111",
             "amount": rnd.randint(28, 46) * 100_000, "department": "KT", "expense_item": "CP03"},
            {"description": "Cước vận chuyển giao hàng", "debit_account": "6421", "credit_account": "1111",
             "amount": rnd.randint(30, 80) * 100_000, "department": "KD", "expense_item": "CP05"}],
           "NCC004", f"Chi phí điện, vận chuyển tháng {m:02d}")
        prev_salary = 92_000_000 if m == 1 else 68_000_000
        mk("NH", f"2026-{m:02d}-05", [{"description": "Chuyển khoản trả lương tháng trước", "debit_account": "334",
                                        "credit_account": "1121", "amount": prev_salary}], None,
           f"Thanh toán lương tháng {12 if m == 1 else m - 1:02d}")
        mk("PKT", last, [
            {"description": "Lương bộ phận bán hàng", "debit_account": "6421", "credit_account": "334",
             "amount": 38_000_000, "department": "KD", "expense_item": "CP01"},
            {"description": "Lương bộ phận quản lý", "debit_account": "6422", "credit_account": "334",
             "amount": 30_000_000, "department": "BGD", "expense_item": "CP01"}], None, f"Hạch toán lương tháng {m:02d}")
        mk("PKT", last, [
            {"description": "Khấu hao xe ô tô tải", "debit_account": "6421", "credit_account": "2141",
             "amount": 5_000_000, "department": "KD", "expense_item": "CP02"},
            {"description": "Khấu hao hệ thống máy chủ", "debit_account": "6422", "credit_account": "2141",
             "amount": 3_333_333, "department": "KT", "expense_item": "CP02"},
            {"description": "Phân bổ chi phí trả trước", "debit_account": "6422", "credit_account": "242",
             "amount": 3_000_000, "department": "KT", "expense_item": "CP07"}], None,
           f"Khấu hao, phân bổ tháng {m:02d} (nhập tay – tự động ở GĐ3)")
        mk("NH", last, [{"description": "Phí quản lý tài khoản", "debit_account": "6422", "credit_account": "1121",
                         "amount": 330_000, "expense_item": "CP06"},
                        {"description": "Lãi tiền gửi không kỳ hạn", "debit_account": "1121", "credit_account": "515",
                         "amount": rnd.randint(4, 9) * 100_000}], None, f"Phí, lãi ngân hàng tháng {m:02d}")
        if m == 2:
            mk("PC", "2026-02-10", [{"description": "Tạm ứng công tác phí", "debit_account": "141", "credit_account": "1111",
                                      "debit_partner": "NV002", "amount": 15_000_000}], "NV002", "Tạm ứng cho NV002")
        if m == 3:
            mk("PKT", "2026-03-12", [{"description": "Quyết toán tạm ứng – chi phí bán hàng", "debit_account": "6421",
                                       "credit_account": "141", "credit_partner": "NV002", "amount": 13_800_000,
                                       "department": "KD"},
                                      {"description": "Hoàn ứng bằng tiền mặt", "debit_account": "1111",
                                       "credit_account": "141", "credit_partner": "NV002", "amount": 1_200_000}],
               "NV002", "Quyết toán tạm ứng NV002")
        if m == 4:
            mk("PC", "2026-04-20", [{"description": "Nộp thuế GTGT tháng 12/2025", "debit_account": "33311",
                                      "credit_account": "1111", "amount": 28_500_000}], None, "Nộp thuế GTGT")
        if m == 3:   # nháp thuộc kỳ sẽ bị khóa => cảnh báo "chứng từ thuộc kỳ đã khóa"
            mk("PC", "2026-03-28", [{"description": "Mua văn phòng phẩm", "debit_account": "6422", "credit_account": "1111",
                                      "amount": 1_250_000, "expense_item": "CP04"}], None,
               "Chi văn phòng phẩm (nhập sót, chưa ghi sổ)", post=False)
        # Kết chuyển các tháng 1–6 rồi khóa sổ
        if m <= 6:   # tính giá xuất kho bình quân cuối tháng → kết chuyển (các tháng 7–10 để người dùng tự chạy)
            inv.costing_apply(f"2026-{m:02d}-01", last)
            cs.execute(f"2026-{m:02d}-01", last)

    # ---- Tình huống minh họa cho Trung tâm cảnh báo (tháng 10–11/2026)
    mk("PXK", "2026-10-28", [{"description": "Xuất máy in trưng bày", "debit_account": "6421", "credit_account": "156",
                              "item": "HH005", "warehouse": "KHO02", "quantity": 3, "unit_price": 4_600_000}],
       None, "Xuất 3 máy in từ kho Long Biên (tồn đầu năm 2) – tồn âm")
    mk("PT", "2026-10-30", [{"description": "Khách hàng ứng trước", "debit_account": "1111", "credit_account": "131",
                             "credit_partner": "KH005", "amount": 50_000_000}], "KH005", "KH005 ứng trước tiền hàng")
    mk("BKBH", "2026-11-06", [{"description": "Bán máy tính xách tay", "debit_account": "131", "credit_account": "5111",
                               "debit_partner": "KH002", "item": "HH001", "warehouse": "KHO01", "quantity": 2,
                               "unit_price": 19_530_000, "tax_rate": "10"}], "KH002", "Bán hàng KH002 (nháp)",
       "0009001", "1C26TMK", post=False)
    mk("PKT", "2026-11-10", [{"description": "Trích trước chi phí kiểm toán", "debit_account": "6422",
                              "credit_account": "335", "amount": 18_000_000}], None, "Trích trước chi phí (đã kiểm tra)",
       post=False, check=True)
    mk("PKT", "2026-11-11", [{"description": "Chi phí tiếp khách", "debit_account": "6422", "amount": 2_000_000},
                             {"description": "Chi tiền mặt", "credit_account": "1111", "amount": 1_800_000}], None,
       "Chứng từ lệch Nợ – Có (minh họa lỗi chặn)", post=False)
    first_buy = db.one("SELECT invoice_no, invoice_series FROM voucher WHERE company_id=? AND vtype='BKMH' ORDER BY id LIMIT 1",
                       (cid,))
    mk("BKMH", "2026-11-12", [{"description": "Mua chuột không dây", "debit_account": "156", "credit_account": "331",
                               "credit_partner": "NCC001", "item": "HH004", "warehouse": "KHO01", "quantity": 10,
                               "unit_price": 240_000, "tax_rate": "10"}], "NCC001",
       "Nhập trùng hóa đơn (minh họa nghi trùng)", first_buy["invoice_no"], first_buy["invoice_series"], post=False)
    mk("BKBH", "2026-11-13", [{"description": "Bán giấy A4", "debit_account": "131", "credit_account": "5111",
                               "item": "HH006", "warehouse": "KHO01", "quantity": 20, "unit_price": 81_000,
                               "tax_rate": "10", "tax_amount": 160_000}], None,
       "Thiếu đối tượng công nợ + lệch tiền thuế (minh họa)", post=False)
    with db.transaction():
        for m in range(1, 7):
            ps.lock(2026, m)

    # ---- Doanh nghiệp thứ hai (xây dựng – vận tải) để minh họa đa doanh nghiệp
    with db.transaction():
        cid2 = _create_company(db, "TS", "Công ty CP Xây dựng – Vận tải Trường Sơn (minh họa)", "0109990002",
                               "Khu công nghiệp Minh Họa, Bắc Ninh", "Xây dựng, vận tải")
        _create_accounts(db, cid2)
        db.execute("INSERT INTO fiscal_year(company_id, year, start_date, end_date) VALUES(?,?,?,?)",
                   (cid2, 2026, "2026-01-01", "2026-12-31"))
        db.execute("INSERT INTO company_regime(company_id, regime_code, effective_from) VALUES(?,?,?)",
                   (cid2, "TT133_2016", "2026-01-01"))
        _ins(db, "partner", cid2, [("CDT01", "Ban QLDA Giao thông Minh Họa", "KH", "0109990301"),
                                   ("NCC01", "Công ty TNHH Vật liệu Xây dựng Minh Họa", "NCC", "0109990302")],
             ["code", "name", "kind", "tax_code"])
        _ins(db, "project", cid2, [("CT01", "Đường liên xã Minh Họa – gói 01", "Ban QLDA Giao thông Minh Họa")],
             ["code", "name", "customer"])
        _ins(db, "warehouse", cid2, [("KCT", "Kho công trường", "Bắc Ninh")], ["code", "name", "address"])
        _ins(db, "item", cid2, [("XM", "Xi măng PCB40", "Tấn", "VT", "152", "10"),
                                ("THEP", "Thép cuộn D8", "Tấn", "VT", "152", "10")],
             ["code", "name", "unit", "kind", "stock_account", "tax_rate"])
        db.executemany("INSERT INTO opening_balance(company_id, year, account_code, partner_id, debit, credit) VALUES(?,?,?,?,?,?)",
                       [(cid2, 2026, "1121", None, 2_500_000_000, 0), (cid2, 2026, "4111", None, 0, 2_500_000_000)])
    s2 = Session(db, admin, company_id=cid2)
    vs2 = VoucherService(s2)
    v = vs2.save({"vtype": "BKMH", "voucher_date": "2026-03-02", "posting_date": "2026-03-02", "partner_code": "NCC01",
                  "tax_code": "0109990302", "description": "Mua vật liệu cho công trình CT01", "invoice_no": "0000451",
                  "invoice_series": "1C26TVL", "invoice_date": "2026-03-02"},
                 [{"description": "Xi măng PCB40", "debit_account": "152", "credit_account": "331", "credit_partner": "NCC01",
                   "item": "XM", "warehouse": "KCT", "quantity": 120, "unit_price": 1_450_000, "tax_rate": "10",
                   "project": "CT01"},
                  {"description": "Thép cuộn D8", "debit_account": "152", "credit_account": "331", "credit_partner": "NCC01",
                   "item": "THEP", "warehouse": "KCT", "quantity": 35, "unit_price": 15_800_000, "tax_rate": "10",
                   "project": "CT01"}])
    vs2.post(v)
    v = vs2.save({"vtype": "PXK", "voucher_date": "2026-03-10", "posting_date": "2026-03-10",
                  "description": "Xuất vật liệu thi công CT01"},
                 [{"description": "Xuất xi măng", "debit_account": "154", "credit_account": "152", "item": "XM",
                   "warehouse": "KCT", "quantity": 100, "unit_price": 1_450_000, "project": "CT01"},
                  {"description": "Xuất thép", "debit_account": "154", "credit_account": "152", "item": "THEP",
                   "warehouse": "KCT", "quantity": 30, "unit_price": 15_800_000, "project": "CT01"}])
    vs2.post(v)
    return db


def write_sample_invoices(db: Database, folder: str | Path) -> list[Path]:
    """Sinh hóa đơn điện tử XML minh họa (cấu trúc HDon/DLHDon) cho chức năng Đọc hóa đơn XML."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    me = db.one("SELECT * FROM company WHERE code='MK'")

    def xml(series, number, d, seller, buyer, lines, tax_total=None):
        rows, tot, tax = [], 0, 0
        for i, (code, name, unit, qty, price, rate) in enumerate(lines, 1):
            amt = round(qty * price)
            tot += amt
            tax += round(amt * rate / 100 + 1e-9) if isinstance(rate, (int, float)) else 0
            rows.append(f"""<HHDVu><TChat>1</TChat><STT>{i}</STT><MHHDVu>{code}</MHHDVu><THHDVu>{name}</THHDVu>
<DVTinh>{unit}</DVTinh><SLuong>{qty}</SLuong><DGia>{price}</DGia><ThTien>{amt}</ThTien>
<TSuat>{f"{rate}%" if isinstance(rate, (int, float)) else rate}</TSuat></HHDVu>""")
        tax = tax if tax_total is None else tax_total
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<HDon><DLHDon Id="data"><TTChung><PBan>2.0.0</PBan><THDon>HÓA ĐƠN GIÁ TRỊ GIA TĂNG</THDon><KHMSHDon>1</KHMSHDon>
<KHHDon>{series}</KHHDon><SHDon>{number}</SHDon><NLap>{d}</NLap><DVTTe>VND</DVTTe><TGia>1</TGia></TTChung>
<NDHDon><NBan><Ten>{seller[0]}</Ten><MST>{seller[1]}</MST><DChi>{seller[2]}</DChi></NBan>
<NMua><Ten>{buyer[0]}</Ten><MST>{buyer[1]}</MST><DChi>{buyer[2]}</DChi></NMua>
<DSHHDVu>{''.join(rows)}</DSHHDVu>
<TToan><TgTCThue>{tot}</TgTCThue><TgTThue>{tax}</TgTThue><TgTTTBSo>{tot + tax}</TgTTTBSo></TToan></NDHDon></DLHDon>
<DSCKS><NBan>(chữ ký số – không kiểm tra trong ứng dụng)</NBan></DSCKS></HDon>"""

    mine = (me["name"], me["tax_code"], me["address"])
    ncc1 = db.one("SELECT name, tax_code, address FROM partner WHERE company_id=? AND code='NCC001'", (me["id"],))
    first_sale = db.one("""SELECT v.invoice_series, v.invoice_no, v.invoice_date, p.name, p.tax_code, p.address, v.id
                           FROM voucher v JOIN partner p ON p.id=v.partner_id WHERE v.company_id=? AND v.vtype='BKBH'
                           ORDER BY v.id LIMIT 1""", (me["id"],))
    sale_lines = db.query("""SELECT i.code, i.name, i.unit, l.quantity, l.unit_price, l.tax_rate FROM voucher_line l
                             JOIN item i ON i.id=l.item_id WHERE l.voucher_id=? ORDER BY l.line_no""", (first_sale["id"],))
    files = {
        "01_mua_hang_NCC001.xml": xml("1C26TAA", "0000199", "2026-11-10", tuple(ncc1), mine,
                                      [("HH004", "Chuột không dây", "Chiếc", 50, 235000, 10),
                                       ("HH006", "Giấy A4 70gsm", "Ram", 100, 63000, 10)]),
        "02_mua_hang_NCC_moi_lech_lam_tron.xml": xml(
            "1C26THS", "0000057", "2026-11-12",
            ("Công ty TNHH Văn phòng phẩm Hoa Sen (minh họa)", "0109990401", "Số 5 phố Minh Họa, Hà Nội"), mine,
            [("VPP01", "Bìa hồ sơ nhựa", "Cái", 1, 12345, 10), ("VPP02", "Bút bi xanh", "Hộp", 1, 23455, 10),
             ("VPP03", "Kẹp giấy", "Hộp", 1, 34565, 10)], tax_total=7037),
        "03_ban_hang_da_nhap.xml": xml(first_sale["invoice_series"], first_sale["invoice_no"], first_sale["invoice_date"], mine,
                                       (first_sale["name"], first_sale["tax_code"], first_sale["address"]),
                                       [(r["code"], r["name"], r["unit"], int(to_decimal(r["quantity"])),
                                         int(to_decimal(r["unit_price"])), int(to_decimal(r["tax_rate"]))) for r in sale_lines]),
        "04_khong_thuoc_doanh_nghiep.xml": xml("1C26TXX", "0000001", "2026-11-01",
                                               ("Công ty A (minh họa)", "0100000011", "Hà Nội"),
                                               ("Công ty B (minh họa)", "0100000022", "Hà Nội"),
                                               [("X", "Hàng hóa X", "Cái", 1, 1000000, 10)]),
    }
    out = []
    for name, content in files.items():
        p = folder / name
        p.write_text(content, encoding="utf-8")
        out.append(p)
    return out


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "ketoan_demo.db"
    d = create_database(target, demo=True)
    for f in write_sample_invoices(d, Path(target).parent / "hoa_don_xml"):
        print("Hóa đơn mẫu:", f)
    print("Đã tạo", target)
