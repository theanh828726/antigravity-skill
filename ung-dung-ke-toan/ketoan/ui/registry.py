"""Danh mục chức năng: một nguồn duy nhất cho ô chức năng, menu và tab.

phase: giai đoạn triển khai của chức năng. phase <= IMPLEMENTED_PHASE: đã chạy được.
phase > IMPLEMENTED_PHASE: CHƯA triển khai – ô hiển thị nhãn giai đoạn, mở ra trang mô tả phạm vi dự kiến (không giả lập).
"""
from __future__ import annotations

from dataclasses import dataclass, field


IMPLEMENTED_PHASE = 2


@dataclass(frozen=True)
class Func:
    key: str
    title: str
    icon: str
    color: str
    phase: int = 1
    args: dict = field(default_factory=dict)
    plan: str = ""       # mô tả phạm vi dự kiến cho chức năng chưa triển khai

    @property
    def pending(self) -> bool:
        return self.phase > IMPLEMENTED_PHASE


def _f(*a, **k):
    f = Func(*a, **k)
    return f.key, f


FUNCS: dict[str, Func] = dict([
    # ---------------- Chứng từ nghiệp vụ
    _f("v_BKMH", "Bảng kê mua hàng", "cart", "mua_ban", 1, {"vtype": "BKMH"}),
    _f("v_BKBH", "Bảng kê bán hàng", "sale", "mua_ban", 1, {"vtype": "BKBH"}),
    _f("v_PKMB", "Phiếu kế toán mua – bán", "doc_swap", "mua_ban", 1, {"vtype": "PKMB"}),
    _f("v_PT", "Phiếu thu", "receipt_in", "tien", 1, {"vtype": "PT"}),
    _f("v_PC", "Phiếu chi", "receipt_out", "tien", 1, {"vtype": "PC"}),
    _f("v_PNK", "Phiếu nhập kho", "box_in", "kho", 1, {"vtype": "PNK"}),
    _f("v_PXK", "Phiếu xuất kho", "box_out", "kho", 1, {"vtype": "PXK"}),
    _f("v_PKT", "Nghiệp vụ hạch toán", "journal", "tong_hop", 1, {"vtype": "PKT"}),
    _f("v_NH", "Nghiệp vụ ngân hàng", "bank", "tien", 1, {"vtype": "NH"}),
    _f("v_CTK", "Chứng từ khác", "docs", "tong_hop", 1, {"vtype": "CTK"}),
    _f("v_ALL", "Danh sách chứng từ", "list", "tong_hop", 1, {"vtype": None}),
    # ---------------- Sổ sách
    _f("r_nkc", "Sổ nhật ký chung", "journal", "tong_hop"),
    _f("r_socai", "Sổ cái", "ledger", "tong_hop"),
    _f("r_sct", "Sổ chi tiết tài khoản", "columns", "tong_hop"),
    _f("r_cdps", "Bảng cân đối số phát sinh", "scale", "bao_cao"),
    _f("r_soquy", "Sổ quỹ tiền mặt", "cash", "tien", 1, {"account": "111"}),
    _f("r_sotgnh", "Sổ tiền gửi ngân hàng", "bank_book", "tien", 1, {"account": "112"}),
    _f("m_congno", "Quản lý công nợ", "debt", "mua_ban", 2),
    _f("m_htk", "Quản lý hàng tồn kho", "warehouse", "kho", 2),
    _f("m_xuatloat", "Xuất kho hàng loạt", "boxes", "kho", 2),
    _f("m_dtgv", "Đối chiếu doanh thu – giá vốn", "compare", "mua_ban", 2),
    _f("m_tinhgia", "Tính giá xuất kho", "calc", "kho", 2),
    _f("m_thekho", "Thẻ kho", "columns", "kho", 2),
    _f("c_opening_stock", "Tồn kho đầu kỳ", "box", "kho", 2),
    _f("m_tscd", "Tài sản cố định", "asset", "tai_san", 3,
       plan="Ghi tăng/giảm TSCĐ, tính khấu hao tự động theo đường thẳng, phân bổ chi phí khấu hao theo bộ phận. "
            "Hiện đã có danh mục TSCĐ (Danh mục → Tài sản cố định)."),
    _f("m_ccdc", "Công cụ dụng cụ", "tools", "tai_san", 3,
       plan="Ghi tăng CCDC, phân bổ chi phí trả trước theo số kỳ, bảng phân bổ."),
    _f("gt_ct", "Giá thành công trình xây dựng", "crane", "tai_san", 3,
       plan="Tập hợp chi phí 154 theo công trình, khoản mục; xác định dở dang, giá vốn công trình hoàn thành."),
    _f("gt_sct", "Sổ chi tiết công trình", "building", "tai_san", 3,
       plan="Sổ chi tiết chi phí theo công trình/khoản mục. Hiện có thể xem «Sổ chi tiết tài khoản» 154."),
    _f("gt_dm", "Giá thành sản xuất theo định mức", "factory", "tai_san", 3,
       plan="Định mức nguyên vật liệu, phân bổ chi phí chung theo định mức, tính giá thành sản phẩm."),
    _f("gt_kdm", "Giá thành sản xuất không định mức", "factory", "tai_san", 3,
       plan="Phân bổ chi phí theo tiêu thức (số lượng, hệ số, NVL trực tiếp)."),
    _f("gt_gd", "Giá thành sản xuất giản đơn", "calc", "tai_san", 3,
       plan="Tính giá thành theo phương pháp giản đơn: DDĐK + CP trong kỳ − DDCK."),
    _f("gt_dv", "Giá thành dịch vụ", "service", "tai_san", 3,
       plan="Tập hợp chi phí dịch vụ theo hợp đồng/đơn hàng, kết chuyển giá vốn."),
    _f("gt_vt", "Giá thành vận tải", "truck", "tai_san", 3,
       plan="Tập hợp chi phí theo đầu xe/tuyến, giá thành theo chuyến hoặc tấn.km."),
    _f("gt_kdd", "Giá thành sản xuất không có dở dang", "calc", "tai_san", 3,
       plan="Toàn bộ chi phí trong kỳ kết chuyển vào giá thành sản phẩm hoàn thành."),
    _f("m_nhquy", "Ngân hàng – Quỹ", "cash", "tien", 1),
    _f("m_inhs", "In hồ sơ", "printer", "tai_san", 3,
       plan="In hàng loạt chứng từ, sổ sách theo kỳ để lưu trữ hồ sơ kế toán; đóng quyển theo tháng/năm. "
            "Hiện mỗi sổ, chứng từ đều có nút In / Xem trước / PDF."),
    # ---------------- Báo cáo tài chính
    _f("bc_cdkt", "Báo cáo tình hình tài chính / Bảng cân đối kế toán", "report", "bao_cao", 3,
       plan="Mẫu báo cáo theo chế độ kế toán áp dụng cho từng doanh nghiệp, kỳ; chỉ tiêu và công thức được quản lý "
            "phiên bản và chỉ phát hành sau khi kiểm chứng văn bản gốc."),
    _f("bc_kqkd", "Báo cáo kết quả hoạt động kinh doanh", "chart", "bao_cao", 3,
       plan="Mẫu báo cáo theo chế độ kế toán áp dụng, truy ngược chỉ tiêu → sổ chi tiết → chứng từ."),
    _f("bc_lctt", "Báo cáo lưu chuyển tiền tệ", "cashflow", "bao_cao", 3,
       plan="Phương pháp trực tiếp/gián tiếp theo mẫu của chế độ áp dụng."),
    _f("bc_tm", "Thuyết minh báo cáo tài chính", "notes", "bao_cao", 3,
       plan="Thuyết minh theo mẫu, lấy số liệu tự động từ sổ sách."),
    # ---------------- Thuế
    _f("t_gtgt", "Thuế GTGT", "tax", "thue", 3,
       plan="Bảng kê hóa đơn mua vào/bán ra từ chứng từ, tổng hợp số liệu hỗ trợ lập tờ khai. Đây là báo cáo HỖ TRỢ "
            "TÍNH TOÁN, không phải tờ khai điện tử theo cấu trúc của cơ quan thuế."),
    _f("t_tndn", "Thuế TNDN", "tax", "thue", 3,
       plan="Hỗ trợ tính thuế TNDN tạm tính/quyết toán; chỉ tiêu, thuế suất lấy từ cấu hình đã kiểm chứng."),
    _f("t_tncn", "Thuế TNCN", "tax", "thue", 3,
       plan="Tổng hợp thu nhập, khấu trừ thuế TNCN theo nhân viên; biểu thuế được quản lý phiên bản."),
    _f("t_doichieu", "Đối chiếu hóa đơn – sổ kế toán – dữ liệu kê khai", "compare", "thue", 3,
       plan="Đối chiếu dữ liệu hóa đơn điện tử (XML) với chứng từ đã ghi sổ và số liệu kê khai."),
    # ---------------- Danh mục & hệ thống
    _f("c_catalog", "Danh mục", "folder", "he_thong"),
    _f("c_opening", "Số dư đầu kỳ", "scale", "he_thong"),
    _f("c_import_xml", "Đọc hóa đơn XML", "import", "mua_ban", 2),
    _f("s_alerts", "Trung tâm cảnh báo", "alert", "thue"),
    _f("s_lock", "Khóa sổ kỳ kế toán", "lock", "he_thong"),
    _f("s_users", "Người dùng & phân quyền", "users", "he_thong"),
    _f("s_audit", "Nhật ký thay đổi", "list", "he_thong"),
    _f("s_backup", "Sao lưu – khôi phục", "backup", "he_thong"),
    _f("s_company", "Doanh nghiệp & chế độ kế toán", "settings", "he_thong"),
    _f("s_closing", "Kết chuyển cuối kỳ", "scale", "tong_hop"),
    _f("dashboard", "Tổng quan", "home", "he_thong"),
])

DASHBOARD_GROUPS = [
    ("CHỨNG TỪ NGHIỆP VỤ", ["v_BKMH", "v_BKBH", "v_PKMB", "v_PT", "v_PC", "v_PNK", "v_PXK", "v_PKT", "v_NH", "v_CTK"]),
    ("SỔ SÁCH VÀ QUẢN TRỊ", ["r_nkc", "r_socai", "r_sct", "r_cdps", "r_soquy", "r_sotgnh", "m_congno", "m_htk",
                             "m_xuatloat", "m_dtgv", "m_tinhgia", "m_tscd", "m_ccdc", "gt_ct", "gt_sct", "gt_dm", "gt_kdm", "gt_gd",
                             "gt_dv", "gt_vt", "gt_kdd", "m_nhquy", "m_inhs"]),
    ("BÁO CÁO TÀI CHÍNH", ["r_cdps", "bc_cdkt", "bc_kqkd", "bc_lctt", "bc_tm"]),
    ("BÁO CÁO THUẾ", ["t_gtgt", "t_tndn", "t_tncn", "t_doichieu"]),
]

# Menu trái: (nhãn, icon, [(tiêu đề nhóm, [func keys])]) – mục có 1 chức năng duy nhất mở thẳng chức năng đó
MENU = [
    ("Tổng quan", "home", "dashboard"),
    ("Danh mục", "folder", [("DANH MỤC", ["c_catalog", "c_opening", "c_opening_stock", "c_import_xml"])]),
    ("Chứng từ nghiệp vụ", "docs", [("CHỨNG TỪ NGHIỆP VỤ", DASHBOARD_GROUPS[0][1] + ["v_ALL"]),
                                    ("TIỆN ÍCH MUA – BÁN", ["c_import_xml", "m_xuatloat", "m_dtgv"])]),
    ("Sổ sách kế toán", "book", [("SỔ SÁCH KẾ TOÁN", ["r_nkc", "r_socai", "r_sct", "r_cdps", "r_soquy", "r_sotgnh"])]),
    ("Báo cáo tài chính", "chart", [DASHBOARD_GROUPS[2]]),
    ("Báo cáo thuế", "tax", [DASHBOARD_GROUPS[3], ("KIỂM TRA, ĐỐI CHIẾU", ["s_alerts"])]),
    ("Quản lý công nợ", "debt", [("QUẢN LÝ CÔNG NỢ", ["m_congno", "r_sct", "v_BKMH", "v_BKBH", "v_PT", "v_PC", "v_NH"])]),
    ("Quản lý hàng tồn kho", "warehouse", [("QUẢN LÝ HÀNG TỒN KHO", ["m_htk", "m_thekho", "m_tinhgia", "m_xuatloat", "m_dtgv",
                                                                    "c_opening_stock", "v_PNK", "v_PXK"])]),
    ("Tài sản cố định", "asset", [("TÀI SẢN CỐ ĐỊNH", ["m_tscd"])]),
    ("Công cụ dụng cụ", "tools", [("CÔNG CỤ DỤNG CỤ", ["m_ccdc"])]),
    ("Giá thành", "factory", [("GIÁ THÀNH", ["gt_ct", "gt_sct", "gt_dm", "gt_kdm", "gt_gd", "gt_dv", "gt_vt", "gt_kdd"])]),
    ("Ngân hàng – Quỹ", "bank", [("NGÂN HÀNG – QUỸ", ["v_PT", "v_PC", "v_NH", "r_soquy", "r_sotgnh"])]),
    ("In hồ sơ", "printer", [("IN HỒ SƠ", ["m_inhs"])]),
    ("Hệ thống", "settings", [("HỆ THỐNG", ["s_company", "s_users", "s_lock", "s_closing", "s_alerts", "s_audit",
                                            "s_backup"])]),
]
