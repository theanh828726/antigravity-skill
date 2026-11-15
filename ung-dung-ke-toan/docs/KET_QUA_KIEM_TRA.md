# Kết quả kiểm tra – Giai đoạn 1, 2, 3, 4 (v1.3.0)

Ngày kiểm tra: 14/11/2026 · Python 3.13 · PySide6 6.12 · SQLite · giao diện chạy offscreen ở **1366 × 768**.

```
$ QT_QPA_PLATFORM=offscreen python -m pytest -v tests
95 passed   (52 bài trên SQLite + 43 lượt trên PostgreSQL 16, gồm 6 bài đa người dùng)
```

## 1. Dữ liệu minh họa (`sample_data/ketoan_demo.db`)

| Hạng mục | Số liệu |
|---|---|
| Doanh nghiệp | 2 (Thương mại – Dịch vụ Minh Khang; Xây dựng – Vận tải Trường Sơn) – tên, MST đều giả định |
| Hệ thống TK (DN 1) | 123 tài khoản (mẫu TT133 – *chưa kiểm chứng*) |
| Đối tượng | 13 (5 KH, 4 NCC, 4 NV); 7 mặt hàng; 2 kho; 2 công trình; 4 bộ phận; 7 khoản mục CP; 2 TSCĐ |
| Chứng từ | DN 1: 198 đã ghi sổ, 1 đã kiểm tra, 5 nháp · DN 2: 2 đã ghi sổ; 40 phiếu xuất liên kết bảng kê bán |
| Bút toán sổ cái | 1.236 dòng |
| Tồn kho đầu kỳ | HH005 / KHO02: 2 chiếc, 9.200.000 – khớp số dư đầu năm TK 156 |
| Tính giá xuất kho | Tháng 01–06: đã chạy bình quân gia quyền cuối tháng trước kết chuyển (48 dòng cập nhật). Tháng 07–10: để sẵn **45 dòng** xuất tạm tính theo giá nhập gần nhất (chênh lệch 516.271) để người dùng chạy thử |
| Kỳ đã khóa | Tháng 01 – 06/2026 (đã tính giá xuất kho, kết chuyển 911 từng tháng) |
| CĐSPS cả năm 2026 | Đầu kỳ 2.788.500.000 = 2.788.500.000 · Phát sinh 24.245.740.215 = 24.245.740.215 · Cuối kỳ 5.303.899.517 = 5.303.899.517 → **cân đối cả 3 cặp cột** |
| Hóa đơn XML mẫu | 4 file trong `sample_data/hoa_don_xml/` (hợp lệ · NCC mới + lệch làm tròn thuế 1đ · đã nhập · không thuộc DN) |
| Trung tâm cảnh báo | 3 lỗi chặn · 6 cần kiểm tra · 3 thông tin (tình huống cài sẵn để minh họa) |

Dữ liệu được sinh **qua lớp nghiệp vụ** (lưu → kiểm tra → ghi sổ, kết chuyển, khóa kỳ) nên chính quá trình tạo dữ liệu mẫu cũng là
một bài kiểm tra tích hợp với ~200 chứng từ.

## 2. Luồng quan trọng: nhập chứng từ → ghi sổ → lên báo cáo → truy ngược

| Bước | Kiểm thử | Kết quả |
|---|---|---|
| Nhập bảng kê bán hàng (3 × 1.232.000, thuế 10%) | `test_full_flow_voucher_to_reports_and_back` | Tiền hàng 3.696.000 · thuế 369.600 · thanh toán 4.065.600 ✅ |
| Lưu → trạng thái Nháp, **chưa** lên sổ | 〃 | Sổ chi tiết 131 không đổi ✅ |
| Kiểm tra → Đã kiểm tra; Ghi sổ → Đã ghi sổ | 〃 | ✅ |
| Lên Sổ chi tiết 131 đúng 4.065.600, mang `voucher_id` | 〃 | ✅ truy ngược ra đúng số chứng từ |
| Nhật ký chung: đủ 131 / 5111 / 33311, Nợ = Có | 〃 | ✅ |
| CĐSPS cân, phát sinh tăng đúng 4.065.600 | 〃 | ✅ |
| Bỏ ghi sổ → số liệu rút khỏi sổ | 〃 | ✅ |
| Cùng luồng qua **giao diện**: chọn đối tượng, mã hàng, kho, SL, ĐG (định dạng `4.420.000`) → tự tính 8.840.000 + thuế 884.000, gợi ý đối tượng Nợ, tổng "cân đối" → Lưu → Ghi sổ → mở CĐSPS → Sổ chi tiết 131 chứa chứng từ → mở lại đúng tab chứng từ | `test_voucher_entry_post_and_drilldown` | ✅ |

## 3. Kiểm soát & an toàn dữ liệu

| Nội dung | Kiểm thử | Kết quả |
|---|---|---|
| Chính sách tiền: đọc `1.234.567`, `1.234.567,5`, `1,234,567.5`, `12,5`, `(1.000)`; làm tròn nửa lên; định dạng `(1.234.567)` | `test_money_policy` | ✅ |
| Chứng từ lệch Nợ–Có bị chặn ghi sổ, báo đúng chênh lệch 100, **không sinh bút toán** | `test_unbalanced_voucher_is_blocked` | ✅ |
| Hạch toán TK tổng hợp / thiếu đối tượng bắt buộc bị chặn | `test_required_partner_and_parent_account_blocked` | ✅ |
| Kỳ khóa: không lưu mới, không bỏ ghi sổ; mở khóa phải theo thứ tự kỳ sau → trước | `test_locked_period` | ✅ |
| Phân quyền: người xem không lưu được; kế toán viên không ghi sổ / khóa kỳ; sai mật khẩu bị từ chối | `test_permissions` | ✅ |
| Lỗi giữa chừng (mã đối tượng không tồn tại) → **không còn chứng từ dở dang** | `test_transaction_rollback_on_error` | ✅ |
| Trung tâm cảnh báo phát hiện đủ: lệch Nợ–Có, thiếu đối tượng, trùng hóa đơn, tồn âm, công nợ bất thường, lệch thuế, kỳ khóa; mọi cảnh báo có nguyên nhân + đích mở | `test_alert_center_finds_all_demo_cases` | ✅ |
| Kết chuyển: xem trước → thực hiện → 511/911 về 0 → không kết chuyển trùng → hoàn tác khôi phục nguyên trạng | `test_closing_preview_execute_undo` | ✅ |
| Nhập Excel danh mục: thiếu mã, trùng mã trong file → báo đúng dòng, không ghi; xóa danh mục đã phát sinh bị chặn | `test_catalog_import_validation` | ✅ |
| Số dư đầu kỳ thiếu đối tượng bị từ chối; sao lưu → thêm dữ liệu → khôi phục về đúng trạng thái, ghi nhật ký | `test_opening_balance_and_backup_restore` | ✅ |
| Dán 2 dòng từ Excel vào lưới, tổng hiển thị "lệch", ghi sổ bị chặn (vẫn Nháp) | `test_paste_from_excel_and_unbalanced_block` | ✅ |
| Mở **toàn bộ** chức năng trong registry + 14 mục menu không lỗi; chức năng GĐ2/3 mở trang trạng thái | `test_dashboard_and_all_functions_open` | ✅ |
| Hộp thoại kết chuyển có bút toán xem trước; đăng nhập sai/đúng | `test_dialogs_render` | ✅ |
| Xuất Excel giữ kiểu số (tổng PS Nợ = PS Có), xuất PDF hợp lệ | `test_export_excel_pdf` | ✅ |

## 4. Giai đoạn 2 – công nợ, kho, mua bán

| Nội dung | Kiểm thử | Kết quả |
|---|---|---|
| File dữ liệu phiên bản 1 tự nâng cấp lên phiên bản 2; hạn TT tính = ngày HĐ + hạn TT đối tượng; chạy lại không đổi | `test_migration_upgrades_v1_database` | ✅ |
| Tồn đầu kỳ khớp số dư TK 156; NXT HH005/KHO02 = 2 đầu kỳ, xuất 3, tồn −1; thẻ kho đúng; **tổng giá trị tồn cuối NXT = số dư TK 156 trên sổ** | `test_opening_stock_nxt_and_card` | ✅ |
| Tính giá BQCK tháng 7–10: chặn kỳ có tháng khóa / không trọn tháng; phát sinh 632 thay đổi đúng bằng tổng chênh lệch; sổ vẫn cân; **chạy lại không còn chênh lệch**; dòng phiếu xuất = bút toán Có 156; không phát sinh cảnh báo lệch thành tiền | `test_costing_bqck_apply_is_idempotent_and_balanced` | ✅ |
| Kịch bản tính tay: nhập 10 × 100, 10 × 120, xuất 15 → **BQCK 1.650**, **FIFO 1.600**; đổi phương pháp sang FIFO và cập nhật đúng | `test_costing_methods_hand_checked` | ✅ |
| **Tổng còn phải thu/trả theo hóa đơn = số dư công nợ trên sổ** cho mọi đối tượng 131 và 331; KH003 có nợ quá hạn; KH005 ứng trước 50.000.000 | `test_debt_aging_equals_ledger_balance` | ✅ |
| Hạn thanh toán mặc định theo đối tượng (KH003 – 45 ngày) | `test_due_date_default_from_partner_terms` | ✅ |
| Xuất kho hàng loạt: bảng kê bán chưa xuất → cảnh báo; lập + ghi sổ phiếu xuất Nợ 632 có liên kết nguồn; không lập trùng; đối chiếu DT–GV khớp số lượng | `test_batch_issue_from_sales` | ✅ |
| Đối chiếu doanh thu – giá vốn 6 tháng đầu năm: không lệch số lượng, lãi gộp dương | `test_revenue_cogs_demo` | ✅ |
| Hóa đơn XML: nhận diện chiều mua/bán, khớp đối tượng + mã hàng, tạo chứng từ **nháp** khớp tổng thanh toán; chặn nhập trùng; NCC mới phải tạo đối tượng trước; dồn lệch làm tròn → tổng thuế 7.037 khớp hóa đơn; hóa đơn không thuộc DN và XML sai cấu trúc bị từ chối | `test_xml_invoices` | ✅ |
| Cảnh báo tồn quỹ tiền mặt âm | `test_negative_cash_alert` | ✅ |
| Giao diện GĐ2: công nợ (3 tab, mở chi tiết đối tượng), NXT → thẻ kho, tồn đầu kỳ, tính giá (xem trước → cập nhật → hết chênh lệch), xuất kho hàng loạt, đối chiếu DT–GV, đọc 4 file XML → tạo chứng từ → mở đúng chứng từ có hạn thanh toán | `test_phase2_screens` | ✅ |

## 5. Giai đoạn 3 – TSCĐ, CCDC, giá thành, báo cáo, thuế, cuối năm

| Nội dung | Kiểm thử | Kết quả |
|---|---|---|
| Migration v1 → v3: tạo đủ các bảng GĐ3 | `test_migration_v3` | ✅ |
| Khấu hao: lũy kế 30/6 = 150.000.000 / 79.999.998 (đầu kỳ + 6 tháng); tháng 7 = 5.000.000 + 3.333.333; chặn chạy nhảy tháng / tháng đã khóa; ghi sổ → sổ vẫn cân; hoàn tác phải từ tháng mới nhất; hoàn tác xong số liệu về đúng như cũ | `test_depreciation_run_sequence_undo_and_balance` | ✅ |
| TSCĐ 100đ / 3 tháng → 33 + 33 + **34** (tháng cuối nhận phần dư, tổng không vượt nguyên giá); không chạy tiếp khi đã hết; ghi giảm ngừng từ tháng sau | `test_last_month_takes_remainder_and_disposal` | ✅ |
| Phân bổ CCDC/chi phí trả trước: tháng 8 = 3.000.000 + 2.000.000; không xóa khoản đã phân bổ; kiểm tra dữ liệu nhập | `test_prepaid_allocation_and_validation` | ✅ |
| Giá thành công trình (số liệu tính tay): CP trực tiếp CT01 716.000.000 / CT02 50.000.000; **giản đơn** (DDCK 100tr, SL 2 → 616.000.000, đơn vị 308.000.000); **không định mức** (CP chung 6.000.000 chia 5.608.355 + 391.645 theo tỷ lệ CP trực tiếp); **định mức** (700.000.000 → chênh 16.000.000, 2,29%); **không dở dang** bỏ qua DDCK; kết chuyển → chứng từ nháp Nợ 632/Có 154 = 616.000.000; không kết chuyển trùng; chi phí trực tiếp không đổi sau khi ghi sổ kết chuyển; hoàn tác; DDCK thành DDĐK kỳ sau | `test_cost_methods_and_transfer` | ✅ |
| Bộ phân tích công thức: nhận biết TK dùng trong công thức; bắt lỗi vòng tròn, hàm lạ, tham chiếu không tồn tại, cú pháp, mã lặp | `test_formula_parser_and_validation` | ✅ |
| Mẫu thử nghiệm: **Tổng tài sản = Tổng nguồn vốn** cả cột Kỳ này và cột Đầu năm (2.608.500.000 = số dư đầu năm); **Lợi nhuận trước thuế của báo cáo KQKD = lợi nhuận tính độc lập từ sổ** bởi dịch vụ thuế; mẫu mặc định ở trạng thái CHƯA KIỂM CHỨNG | `test_demo_templates_reconcile_and_are_unverified` | ✅ |
| Nhập mẫu: tăng phiên bản; mẫu có vòng lặp không được nhập; xác nhận kiểm chứng bắt buộc căn cứ; kế toán viên không có quyền nhập/xác nhận mẫu | `test_template_import_versioning_and_verification_rights` | ✅ |
| GTGT: thuế đầu vào/đầu ra theo hóa đơn = bút toán trên sổ; thuế suất lấy từ dòng chứng từ (10%); cố ý sửa sai tổng thuế và xóa số hóa đơn → phát hiện đúng chênh lệch 1.000 và thiếu thông tin | `test_vat_reconciliation_and_summary` | ✅ |
| TNDN: **chưa nhập thuế suất thì không tính**; tham số thiếu căn cứ bị từ chối; điều chỉnh tăng/giảm và thuế tạm tính đúng | `test_corporate_income_requires_user_rate` | ✅ |
| TNCN: tổng hợp thu nhập hạch toán 30.000.000 và thuế đã khấu trừ 1.500.000 theo nhân viên | `test_personal_income_summary` | ✅ |
| Chuyển số dư cuối năm: chặn khi chưa kết chuyển → sau khi tính giá + kết chuyển thì chuyển được; số dư đầu năm sau cân; 4212 → 4211; CĐSPS năm sau cân; chuyển cả tồn kho; tạo năm tài chính mới | `test_year_end_carry_forward` | ✅ |
| Giao diện GĐ3: TSCĐ (danh sách → chạy khấu hao tháng 7 ghi sổ → hoàn tác), CCDC, giá thành công trình (nhập SL, dở dang → tổng 616.000.000 → lưu → chứng từ nháp), không định mức, sổ chi tiết công trình, báo cáo tài chính theo mẫu có cảnh báo chưa kiểm chứng, LCTT chưa có mẫu → hướng dẫn, quản lý mẫu, 4 báo cáo thuế, **in hồ sơ PDF thật** (≥ 5 file hợp lệ + mục lục), chuyển số dư cuối năm | `test_phase3_screens` | ✅ |

### Kiểm chứng văn bản pháp lý (đã làm và kết quả)
- Tìm kiếm thông tin về Thông tư 99/2025/TT-BTC: các nguồn thứ cấp (báo, trang kế toán) cho thấy thông tư ban hành 27/10/2025, hiệu lực từ 01/01/2026,
  thay Thông tư 200/2014; doanh nghiệp nhỏ và vừa được lựa chọn áp dụng hoặc tiếp tục dùng Thông tư 133/2016. Đã tìm thấy trang Công báo số 1567+1568 (16/11/2025)
  chứa văn bản nhưng **không truy cập được toàn văn phụ lục mẫu báo cáo (B01, B02…)** nên **không đưa bất kỳ chỉ tiêu/công thức nào vào ứng dụng như mẫu chính thức**.
- Thuế GTGT: giảm 2% (10% → 8%) áp dụng theo Nghị quyết 204/2025/QH15 đến hết 31/12/2026 theo các nguồn thứ cấp – ứng dụng **không tự áp thuế suất**; người dùng chọn thuế suất
  trên từng dòng chứng từ.
- Kết luận: mọi nội dung pháp lý trong ứng dụng ở trạng thái **chưa kiểm chứng** và được đánh dấu như vậy; người dùng/kế toán trưởng cần đối chiếu văn bản gốc trước khi dùng thật.

## 6. Giai đoạn 4 – nhiều người dùng (PostgreSQL), chi phí sản xuất, thuyết minh

Toàn bộ bài kiểm thử nghiệp vụ GĐ1–GĐ3 và giao diện **chạy lại nguyên vẹn trên PostgreSQL 16** (mỗi bài một bản sao CSDL mẫu) – số liệu, sổ sách,
báo cáo, khóa kỳ, phân quyền, nhập Excel/XML, sao lưu/khôi phục đều cho kết quả giống SQLite. Khi chuyển backend đã xử lý: số nguyên 64 bit cho tiền đồng, `SUM` trả về
số nguyên, `LIKE` không phân biệt hoa thường, `GROUP BY` chặt chẽ, `RETURNING id`, migration theo từng hệ CSDL.

| Nội dung | Kiểm thử | Kết quả |
|---|---|---|
| 3 người dùng (3 kết nối, 3 luồng) cùng nhập 24 chứng từ → **không trùng số**, không lỗi | `test_concurrent_numbering_has_no_duplicates` | ✅ |
| 2 người cùng ghi sổ một chứng từ → **đúng một người thành công**, bút toán chỉ sinh một lần | `test_two_users_post_same_voucher_only_one_wins` | ✅ |
| Người B sửa trên bản cũ sau khi A đã sửa → bị chặn kèm thông báo «đã được admin sửa… tải lại», nội dung của A không bị ghi đè | `test_stale_edit_is_rejected_with_clear_message` | ✅ |
| Người này khóa kỳ → người kia không lưu được ngay lập tức; mở khóa thì lưu được | `test_period_lock_visible_across_connections` | ✅ |
| Hai người cùng chạy khấu hao tháng 7 → chỉ một lần chạy được ghi nhận | `test_concurrent_depreciation_run_is_serialized` | ✅ |
| Sao lưu PostgreSQL (`pg_dump`) → thêm dữ liệu → khôi phục (`pg_restore`) về đúng trạng thái, có nhật ký | `test_pg_backup_and_restore_roundtrip` | ✅ |
| Kết chuyển CP 621/622/627 vào 154: chặn khi thiếu TK; phân bổ chi phí chung 10.000.000 → 6.666.667 + 3.333.333 theo CP trực tiếp (hoặc 100% theo nhân công); phần đã gắn đối tượng giữ nguyên; tổng 164.000.000; không chạy trùng; giá thành nhận đủ; hoàn tác | `test_overhead_transfer_to_154` | ✅ |
| Mẫu thuyết minh (loại TM): dòng chữ không số liệu + dòng lấy số liệu từ sổ | `test_notes_template_kind` | ✅ |
| Gói PyInstaller: `--init --demo` khởi tạo CSDL PostgreSQL (211 chứng từ) rồi exe đóng gói kết nối và chạy | thủ công + workflow | ✅ |

CI (`ketoan-windows.yml`) chạy bộ kiểm thử với dịch vụ PostgreSQL 16 trên Linux và bộ kiểm thử SQLite + đóng gói trên Windows.

## 6b. Đóng gói
- PyInstaller (`packaging/ketoan.spec`) build thành công; bản đóng gói khởi động, tự tạo CSDL từ `schema.sql` đi kèm, đăng nhập
  và mở cửa sổ chính (kiểm tra trên Linux; trên Windows do workflow `ketoan-windows.yml` thực hiện, gồm bước khởi động exe).

## 7. Ảnh màn hình (1366 × 768)

| | |
|---|---|
| ![](screenshots/01_tong_quan.png) Tổng quan | ![](screenshots/02_nhap_chung_tu.png) Nhập chứng từ |
| ![](screenshots/03_chung_tu_da_ghi_so.png) Đã ghi sổ (chỉ đọc) | ![](screenshots/04_can_doi_so_phat_sinh.png) Bảng cân đối số phát sinh |
| ![](screenshots/05_so_chi_tiet_131.png) Truy ngược sổ chi tiết | ![](screenshots/08_trung_tam_canh_bao.png) Trung tâm cảnh báo |
| ![](screenshots/09_danh_sach_chung_tu.png) Danh sách chứng từ | ![](screenshots/10_danh_muc.png) Danh mục |
| ![](screenshots/11_khoa_so.png) Khóa sổ | ![](screenshots/16_ket_chuyen_xem_truoc.png) Kết chuyển – xem trước |
| ![](screenshots/12_chuc_nang_giai_doan_3.png) Chức năng chưa triển khai | ![](screenshots/15_menu_thu_gon.png) Menu thu gọn |
| ![](screenshots/20_cong_no_tong_hop.png) Công nợ – tổng hợp | ![](screenshots/21_cong_no_hoa_don_han_tt.png) Công nợ – hóa đơn, hạn TT |
| ![](screenshots/22_tuoi_no.png) Phân tích tuổi nợ | ![](screenshots/23_nhap_xuat_ton.png) Nhập – xuất – tồn |
| ![](screenshots/24_the_kho.png) Thẻ kho | ![](screenshots/26_tinh_gia_xuat_kho.png) Tính giá xuất kho – xem trước |
| ![](screenshots/27_xuat_kho_hang_loat.png) Xuất kho hàng loạt | ![](screenshots/28_doi_chieu_dt_gv.png) Đối chiếu doanh thu – giá vốn |
| ![](screenshots/29_doc_hoa_don_xml.png) Đọc hóa đơn XML | ![](screenshots/30_chung_tu_tu_xml.png) Chứng từ nháp tạo từ XML |
| ![](screenshots/40_tscd_danh_sach.png) TSCĐ | ![](screenshots/41_khau_hao_thang.png) Khấu hao tháng |
| ![](screenshots/42_ccdc_chi_phi_tra_truoc.png) CCDC, chi phí trả trước | ![](screenshots/43_gia_thanh_cong_trinh.png) Giá thành công trình |
| ![](screenshots/44_gia_thanh_khong_dinh_muc.png) Giá thành không định mức | ![](screenshots/45_so_chi_tiet_cong_trinh.png) Sổ chi tiết công trình |
| ![](screenshots/46_bang_can_doi_mau_thu_nghiem.png) Bảng cân đối – mẫu thử nghiệm | ![](screenshots/47_ket_qua_kinh_doanh_mau_thu_nghiem.png) KQKD – mẫu thử nghiệm |
| ![](screenshots/48_quan_ly_mau_bao_cao.png) Quản lý mẫu báo cáo | ![](screenshots/49_thue_gtgt.png) Thuế GTGT |
| ![](screenshots/50_doi_chieu_hoa_don.png) Đối chiếu hóa đơn – sổ | ![](screenshots/51_thue_tndn_tam_tinh.png) TNDN tạm tính |
| ![](screenshots/52_thue_tncn_tong_hop.png) TNCN tổng hợp | ![](screenshots/54_chuyen_so_du_cuoi_nam.png) Chuyển số dư cuối năm |

## 8. Giới hạn đã biết
- Tính giá xuất kho chưa hỗ trợ: chuyển kho nội bộ, bình quân tức thời, đích danh, hàng gửi bán (157), giá thành nhập kho
  thành phẩm (GĐ3) – các dòng liên quan được giữ nguyên và cảnh báo trong bảng xem trước.
- Phân bổ thanh toán cho tuổi nợ là FIFO tự động (chưa có chức năng chỉ định thanh toán cho hóa đơn cụ thể / bù trừ công nợ).
- Đọc hóa đơn XML: chỉ cấu trúc HDon/DLHDon, tiền VND; không kiểm tra chữ ký số, không tra cứu trạng thái hóa đơn với cơ quan
  thuế – cấu trúc cần kiểm chứng với file thực tế của nhà cung cấp hóa đơn.
- Nhiều người dùng: chưa có chuyển dữ liệu tự động từ SQLite sang PostgreSQL; sao lưu/khôi phục cần pg_dump/pg_restore; chưa kiểm thử với tải lớn (hàng chục người dùng đồng thời) và chưa có danh sách người đang trực tuyến.
- **Báo cáo tài chính / thuyết minh**: không có mẫu chính thức đi kèm (xem mục kiểm chứng); người dùng nhập mẫu đã kiểm chứng.
- Khấu hao chỉ đường thẳng; thời gian sử dụng/ngưỡng ghi nhận do người dùng nhập; chưa có nâng cấp/đánh giá lại TSCĐ, khấu hao nhanh.
- Giá thành: chưa có phân bổ chi phí sản xuất chung tự động (TK 621/622/627 không có trong hệ thống TK mẫu), quy đổi dở dang theo mức độ hoàn thành, giá thành phân bước.
- Thuế: chưa có tờ khai điện tử theo cấu trúc cơ quan thuế; TNDN thuế suất/điều chỉnh nhập tay; TNCN chưa tính theo biểu thuế.
- Khấu hao, phân bổ trong dữ liệu mẫu là bút toán nhập tay; tự động hóa thuộc GĐ3.
- Số dư đầu năm sau chưa tự chuyển từ năm trước (chức năng chuyển số dư cuối năm thuộc GĐ3).
- Chưa kiểm thử trên màn hình Windows thật trong phiên này (môi trường Linux offscreen); workflow Windows bổ sung kiểm thử + khởi động exe.
