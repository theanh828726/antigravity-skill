# Ứng dụng Kế toán – Hocviendaotaoai

Phần mềm kế toán Windows (Python + PySide6) cho doanh nghiệp thương mại, dịch vụ, sản xuất, xây dựng, vận tải.
**Bản hiện tại: Giai đoạn 4 (v1.3.0)** – Giai đoạn 1–3 + **nhiều người dùng qua PostgreSQL**, kết chuyển chi phí 621/622/627 vào 154,
thuyết minh báo cáo tài chính theo mẫu nhập vào. Chạy được trên SQLite (một người dùng) và PostgreSQL (nhiều người dùng); có dữ liệu minh họa liên kết đầy đủ.

> **Lưu ý pháp lý quan trọng:** ứng dụng **không có mẫu báo cáo tài chính nào đã được kiểm chứng** theo văn bản chính thức (không lấy được
> toàn văn phụ lục mẫu từ nguồn chính thức trong quá trình phát triển). Bộ máy báo cáo cho phép nhập mẫu đã kiểm chứng; mẫu đi kèm chỉ để thử
> nghiệm kỹ thuật và luôn hiển thị «CHƯA KIỂM CHỨNG». Báo cáo thuế chỉ là báo cáo hỗ trợ tính toán, không phải tờ khai điện tử.

```
Danh mục → Nhập chứng từ → Kiểm tra → Ghi sổ → Công nợ, kho (GĐ2) → giá thành (GĐ3) → Sổ kế toán → Báo cáo
```
Dữ liệu chỉ nhập một lần; mọi dòng sổ mang khóa chứng từ để **truy ngược về chứng từ gốc**.

![Tổng quan](docs/screenshots/01_tong_quan.png)

## 1. Chạy nhanh

```bash
cd ung-dung-ke-toan
python -m pip install -r requirements.txt
python main.py                 # lần đầu tự tạo dữ liệu minh họa (SQLite, một người dùng)
python main.py --db postgresql://ketoan@máy-chủ:5432/ketoan          # nhiều người dùng (xem docs/HUONG_DAN_CAI_DAT.md)
```

| Tài khoản | Mật khẩu | Vai trò |
|---|---|---|
| `admin` | `admin@123` | Quản trị hệ thống (toàn quyền) |
| `ketoantruong` | `ktt@123` | Kế toán trưởng (ghi sổ, khóa kỳ, xuất dữ liệu) |
| `ketoanvien` | `ktv@123` | Kế toán viên (nhập, sửa, xóa – **không** ghi sổ, khóa kỳ) |
| `xem` | `xem@123` | Chỉ xem |

Tùy chọn: `--db <file.db>` mở file chỉ định · `--reset-demo` tạo lại dữ liệu minh họa.
Đóng gói & cài đặt Windows: xem [docs/HUONG_DAN_CAI_DAT.md](docs/HUONG_DAN_CAI_DAT.md).

## 2. Trạng thái chức năng

| Nhóm | Chức năng | Trạng thái |
|---|---|---|
| Giao diện | Header xanh đậm + logo, thanh điều khiển (Doanh nghiệp, Dữ liệu, Năm, Kỳ, Từ/Đến, F5, Tính giá XK, Kết chuyển, Cài đặt, Trợ giúp), menu trái 14 mục thu gọn được, tab làm việc giữ trạng thái, thanh trạng thái 5 mục, ô chức năng nhiều màu theo nhóm nghiệp vụ | ✅ GĐ1 |
| Danh mục | Hệ thống TK, khách hàng, NCC, nhân viên, vật tư hàng hóa, kho, công trình, bộ phận, khoản mục CP, TSCĐ; chặn xóa khi đã phát sinh; **nhập Excel có ánh xạ cột + kiểm tra trước + danh sách lỗi theo dòng** | ✅ GĐ1 |
| Số dư đầu kỳ | Theo TK chi tiết và đối tượng, kiểm tra cân đối | ✅ GĐ1 |
| Chứng từ | 10 loại (Bảng kê mua/bán, PK mua–bán, Phiếu thu/chi, Nhập/Xuất kho, Hạch toán, Ngân hàng, Khác); chỉ hiện cột phù hợp loại; thêm/sao chép dòng; dán nhiều dòng từ Excel; tra cứu nhanh (gõ mã/tên, F3); tự tính thành tiền, thuế; tổng tiền hàng/thuế/thanh toán/Nợ/Có/chênh lệch realtime | ✅ GĐ1 |
| Vòng đời | Nháp → Đã kiểm tra → Đã ghi sổ → Đã khóa kỳ; Bỏ ghi sổ; ghi sổ hàng loạt | ✅ GĐ1 |
| Sổ sách | Nhật ký chung, Sổ cái (kèm tổng hợp đối ứng), Sổ chi tiết TK (lọc đối tượng), Sổ quỹ tiền mặt, Sổ tiền gửi NH, Bảng cân đối số phát sinh (dư lưỡng tính theo đối tượng, kiểm tra cân đối) | ✅ GĐ1 |
| Truy ngược | CĐSPS → Sổ chi tiết → Chứng từ gốc (nhấp đúp/Enter) | ✅ GĐ1 |
| Trung tâm cảnh báo | 3 mức (Lỗi chặn ghi sổ / Cần kiểm tra / Thông tin): lệch Nợ–Có, thiếu TK/đối tượng, nghi trùng hóa đơn, tồn kho âm, công nợ bất thường, chênh lệch tổng hợp–chi tiết, chênh lệch tiền hàng/thuế/tổng, chứng từ thuộc kỳ khóa; mỗi cảnh báo có nguyên nhân, số chênh lệch, chứng từ, nút mở – **không tự sửa** | ✅ GĐ1 |
| Kết chuyển | Xem trước → xác nhận → tạo & ghi sổ; hoàn tác khi kỳ chưa khóa | ✅ GĐ1 |
| Hệ thống | Đa doanh nghiệp, đa năm, khóa kỳ theo tháng, phân quyền 8 quyền × vai trò, nhật ký thay đổi, sao lưu – khôi phục (tự sao lưu an toàn trước khi khôi phục), chế độ kế toán có phiên bản theo ngày hiệu lực | ✅ GĐ1 |
| Xuất | Excel (giữ kiểu số), PDF, xem trước khi in – mọi sổ, danh sách, chứng từ | ✅ GĐ1 |
| Công nợ | Tổng hợp theo đối tượng + MST + số quá hạn; chi tiết theo hóa đơn – hạn thanh toán (mặc định = ngày HĐ + hạn TT của đối tượng, sửa được trên chứng từ); phân tích tuổi nợ 5 nhóm; **biên bản đối chiếu công nợ** in/PDF. Thanh toán phân bổ tự động FIFO theo hạn (chỉ để theo dõi, không ghi sổ) | ✅ GĐ2 |
| Kho | Tồn kho đầu kỳ (SL + giá trị, đối chiếu số dư TK kho), Nhập – xuất – tồn theo hàng/kho/kỳ, Thẻ kho, truy ngược chứng từ | ✅ GĐ2 |
| Tính giá xuất kho | **Bình quân gia quyền cuối tháng** hoặc **FIFO** theo mã hàng + kho; bảng xem trước (tồn đầu, nhập, xuất cũ/mới, chênh lệch, cảnh báo) → xác nhận → cập nhật dòng xuất và ghi lại sổ trong một giao dịch; chạy lại không thay đổi kết quả. Phạm vi ghi rõ trên màn hình | ✅ GĐ2 |
| Mua – bán | **Đọc hóa đơn XML** (nhận diện mua vào/bán ra theo MST, khớp đối tượng & mã hàng, đối chiếu tổng tiền/thuế, phát hiện trùng, tạo đối tượng mới khi xác nhận) → tạo chứng từ **nháp**; **Xuất kho hàng loạt** từ bảng kê bán (liên kết chứng từ nguồn, không lập trùng); **Đối chiếu doanh thu – giá vốn** theo mặt hàng | ✅ GĐ2 |
| Cảnh báo bổ sung | Tồn quỹ tiền mặt âm, bán hàng chưa xuất kho/giá vốn, hàng hết SL còn giá trị (cần tính giá), tồn kho đầu kỳ lệch số dư TK kho; tồn âm có tính tồn đầu kỳ | ✅ GĐ2 |
| TSCĐ | Danh mục + nguyên giá, hao mòn lũy kế, giá trị còn lại; **khấu hao đường thẳng theo tháng** (xem trước → chạy → chứng từ hạch toán nháp/ghi sổ → hoàn tác); tháng cuối nhận phần dư; ghi giảm ngừng khấu hao từ tháng sau | ✅ GĐ3 |
| CCDC, chi phí trả trước | Khai báo (TK nguồn, TK chi phí, số tháng, đã phân bổ đầu kỳ); phân bổ đều hàng tháng với cùng cơ chế xem trước/chạy/hoàn tác | ✅ GĐ3 |
| Giá thành | Một bộ máy tập hợp chi phí TK 154 theo công trình/đối tượng: **giản đơn, không dở dang, theo định mức, không định mức (phân bổ chi phí chung theo CP trực tiếp)**, các ô công trình/dịch vụ/vận tải/sản xuất; dở dang cuối kỳ → đầu kỳ sau; kết chuyển giá thành tạo chứng từ nháp, hoàn tác được; **sổ chi tiết công trình** theo khoản mục | ✅ GĐ3 |
| Báo cáo tài chính | **Bộ máy mẫu có phiên bản**: nhập mẫu từ Excel (mã – chỉ tiêu – công thức theo TK: DN/CN/DNDK/CNDK/PSN/PSC/PSNDU/PSCDU), kiểm tra cú pháp – tham chiếu – vòng lặp, cột Đầu năm, truy ngược chỉ tiêu → sổ chi tiết → chứng từ, xác nhận kiểm chứng kèm căn cứ (quyền quản trị), cảnh báo trên mọi bản xem/in/xuất khi chưa kiểm chứng. Dùng cho BS / KQKD / LCTT | ✅ GĐ3 (mẫu chính thức: **người dùng nhập**) |
| Hỗ trợ thuế | **GTGT**: bảng kê mua vào/bán ra theo thuế suất người dùng chọn trên dòng, tổng hợp, đối chiếu thuế trên hóa đơn với bút toán sổ; **Đối chiếu hóa đơn – sổ**: lệch thuế, thiếu thông tin, trùng hóa đơn, lệch kỳ; **TNDN tạm tính**: lợi nhuận kế toán từ sổ, điều chỉnh và thuế suất do người dùng nhập kèm căn cứ (chưa nhập thuế suất thì không tính); **TNCN**: tổng hợp thu nhập và thuế đã khấu trừ theo nhân viên (chưa tính biểu thuế) | ✅ GĐ3 (hỗ trợ tính toán) |
| In hồ sơ, cuối năm | In hàng loạt PDF (CĐSPS, nhật ký chung, sổ cái, sổ quỹ, sổ TGNH, từng chứng từ) kèm mục lục, có nhật ký; **chuyển số dư cuối năm** (số dư theo đối tượng + tồn kho, 4212 → 4211, kiểm tra đã kết chuyển/tồn âm/kỳ khóa) | ✅ GĐ3 |
| **Nhiều người dùng (GĐ4)** | Backend **PostgreSQL** cùng giao diện với SQLite (tự chuyển cú pháp); hộp thoại kết nối + khởi tạo (`--db postgresql://… --init`); khóa dòng khi ghi sổ/bỏ ghi sổ/xóa, đánh số chứng từ bằng khóa tư vấn (không trùng số khi nhiều người nhập cùng lúc), **chặn sửa chồng** (số phiên bản chứng từ), chạy khấu hao/phân bổ/kết chuyển tuần tự; sao lưu/khôi phục bằng pg_dump/pg_restore; **toàn bộ bộ test chạy trên cả hai CSDL** | ✅ GĐ4 |
| Chi phí sản xuất → 154 (GĐ4) | Cho hệ thống TK có TK 621/622/627: kết chuyển chi phí đã gắn đối tượng, phân bổ chi phí chung chưa gắn theo tiêu thức (tổng CP trực tiếp hoặc nhân công trực tiếp), xem trước → chứng từ nháp → hoàn tác, chặn chạy trùng tháng | ✅ GĐ4 |
| Thuyết minh BCTC (GĐ4) | Dùng bộ máy mẫu có phiên bản (loại TM: dòng chữ + dòng số liệu từ sổ); mẫu chính thức do người dùng nhập | ✅ GĐ4 (mẫu chính thức: **người dùng nhập**) |
| Chưa triển khai | Tờ khai điện tử theo cấu trúc cơ quan thuế (cần đặc tả chính thức); biểu thuế TNCN và quyết toán; phân bổ chi phí theo giờ máy/định mức; chuyển dữ liệu tự động SQLite → PostgreSQL; sao lưu PostgreSQL không cần pg_dump | ⏳ |
| Nâng cấp dữ liệu | Migration lược đồ theo phiên bản: file dữ liệu GĐ1 (và bản sao lưu cũ khi khôi phục) tự nâng cấp trong một giao dịch | ✅ GĐ2 |
| GĐ3 | TSCĐ (khấu hao), CCDC (phân bổ), giá thành (8 loại), BCTC theo mẫu, hỗ trợ thuế GTGT/TNDN/TNCN, in hồ sơ | ⏳ ô hiển thị nhãn **GĐ3**, mở ra trang mô tả phạm vi – không giả lập |

## 3. Kiến trúc

```
ung-dung-ke-toan/
├── main.py                       # điểm chạy
├── ketoan/
│   ├── domain/                   # KHÔNG phụ thuộc Qt/DB
│   │   ├── money.py              # Decimal, chính sách làm tròn, định dạng VN
│   │   └── constants.py          # trạng thái, quyền, loại chứng từ & cột hiển thị
│   ├── data/                     # truy cập dữ liệu
│   │   ├── schema.sql            # lược đồ gốc (v1); các bản sau qua MIGRATIONS trong db.py
│   │   ├── db.py                 # SQLite + PostgreSQL: giao dịch lồng nhau, khóa, migration, sao lưu
│   │   └── seed.py               # tạo CSDL mới + dữ liệu minh họa (qua lớp nghiệp vụ)
│   ├── services/                 # nghiệp vụ
│   │   ├── context.py            # phiên: người dùng, doanh nghiệp, kỳ, kiểm quyền, nhật ký
│   │   ├── auth_service.py       # PBKDF2, vai trò, phân quyền
│   │   ├── catalog_service.py    # danh mục (metadata-driven) + nhập Excel
│   │   ├── voucher_service.py    # lưu / kiểm tra / ghi sổ / bỏ ghi sổ / xóa
│   │   ├── ledger_service.py     # NKC, sổ cái, sổ chi tiết, CĐSPS
│   │   ├── alert_service.py      # trung tâm cảnh báo
│   │   ├── closing_service.py    # kết chuyển cuối kỳ
│   │   ├── inventory_service.py  # GĐ2: tồn đầu kỳ, NXT, thẻ kho, tính giá xuất kho (BQCK/FIFO)
│   │   ├── debt_service.py       # GĐ2: công nợ, hạn thanh toán, tuổi nợ, đối chiếu
│   │   ├── trade_service.py      # GĐ2: xuất kho hàng loạt, đối chiếu doanh thu – giá vốn
│   │   ├── xml_invoice.py        # GĐ2: đọc hóa đơn điện tử XML
│   │   ├── asset_service.py      # GĐ3: TSCĐ, CCDC – khấu hao / phân bổ
│   │   ├── cost_service.py       # GĐ3: giá thành, sổ chi tiết công trình
│   │   ├── report_engine.py      # GĐ3: mẫu báo cáo có phiên bản + bộ tính công thức
│   │   ├── tax_service.py        # GĐ3: báo cáo hỗ trợ thuế
│   │   ├── yearend_service.py    # GĐ3: chuyển số dư cuối năm
│   │   ├── overhead_service.py   # GĐ4: kết chuyển chi phí 621/622/627 vào 154
│   │   ├── period_service.py     # năm tài chính, khóa kỳ
│   │   └── system_service.py     # doanh nghiệp, chế độ KT, số dư đầu, sao lưu, nhật ký
│   ├── reports/export.py         # Excel / PDF / in
│   └── ui/                       # PySide6 – chỉ gọi services, không viết SQL
├── tests/                        # 95 lượt kiểm thử khi có PostgreSQL (52 trên SQLite + 43 trên PostgreSQL, gồm 6 bài đa người dùng chạy song song nhiều kết nối): nghiệp vụ GĐ1–GĐ4 + giao diện offscreen
├── sample_data/                  # ketoan_demo.db + hoa_don_xml/ (4 hóa đơn XML mẫu)
├── packaging/                    # PyInstaller spec, build_windows.bat, Inno Setup
└── docs/                         # hướng dẫn cài đặt, kết quả kiểm tra, ảnh màn hình
```

**Nguyên tắc dữ liệu**
- Tiền lưu `INTEGER` (đồng), số lượng/đơn giá lưu chuỗi `Decimal` – không dùng float.
- Làm tròn `ROUND_HALF_UP` theo từng dòng: *Thành tiền = round(SL × ĐG)*; *Tiền thuế = round(Thành tiền × TS%)*; tổng chứng từ = tổng các dòng đã làm tròn.
- Bảng `ledger_entry` chỉ được sinh khi **Ghi sổ** và xóa khi **Bỏ ghi sổ**; mọi báo cáo đọc từ bảng này → báo cáo luôn khớp chứng từ đã ghi sổ.
- Mọi thao tác ghi nằm trong `Database.transaction()` (BEGIN IMMEDIATE … COMMIT/ROLLBACK) – lưu đủ hoặc hoàn tác đủ; ghi sổ có chốt chặn cuối kiểm tra tổng Nợ = tổng Có.
- Thuế GTGT trên bảng kê mua/bán được sinh bút toán riêng (Nợ 1331 / Có TK đối ứng; Nợ TK đối ứng / Có 33311).
- Phiếu xuất kho liên kết bảng kê bán qua `voucher.source_voucher_id`; tính giá xuất kho chỉ sửa dòng xuất của kỳ chưa khóa và ghi lại sổ của chứng từ đó trong cùng giao dịch.
- **Đa người dùng qua LAN**: không chia sẻ file SQLite qua mạng. Lớp `Database` có giao diện `query/execute/transaction` để thay bằng PostgreSQL (chưa triển khai – GĐ4).

## 4. Chế độ kế toán & quy định

- Chế độ kế toán gắn với **doanh nghiệp + ngày hiệu lực** (bảng `company_regime`, có lịch sử), không mặc định cho mọi doanh nghiệp.
- Danh mục chế độ (TT133/2016, TT200/2014, TT99/2025), mẫu hệ thống TK (theo TT133 cho dữ liệu minh họa) và bảng thuế suất GTGT đều được đánh dấu **CHƯA KIỂM CHỨNG** trên giao diện. Phải đối chiếu văn bản gốc, hiệu lực, phạm vi từ nguồn chính thức trước khi dùng thật.
- Ứng dụng **không tự suy đoán** thuế suất, chỉ tiêu báo cáo hay công thức; kết chuyển không tự tính thuế TNDN.
- Báo cáo thuế (GĐ3) sẽ là **báo cáo hỗ trợ tính toán**, tách biệt với tờ khai điện tử theo cấu trúc của cơ quan tiếp nhận.

## 5. Kiểm thử

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q tests        # Windows PowerShell: $env:QT_QPA_PLATFORM="offscreen"
KETOAN_PG_TEST_URL=postgresql://postgres@localhost:5432/postgres python -m pytest -q tests   # thêm PostgreSQL + đa người dùng
```
Kết quả và mô tả các luồng: [docs/KET_QUA_KIEM_TRA.md](docs/KET_QUA_KIEM_TRA.md) (kiểm thử chạy trên SQLite và PostgreSQL).
Workflow `.github/workflows/ketoan-windows.yml` chạy kiểm thử trên Linux + Windows, đóng gói `.exe` và kiểm tra exe khởi động.

## 6. Phím tắt chính

`F5` cập nhật · `Ctrl+N` thêm · `F2` sửa · `Ctrl+S` lưu · `Esc` hủy · `F6` kiểm tra · `F9` ghi sổ · `Ctrl+F9` bỏ ghi sổ ·
`Insert` thêm dòng · `Ctrl+D` sao chép dòng · `Ctrl+Delete` xóa dòng · `Ctrl+V` dán từ Excel · `F3` tìm danh mục ·
`Enter` sang ô kế tiếp / mở dòng · `Ctrl+P` in · `Ctrl+W` đóng tab · `Ctrl+Tab` chuyển tab · `Ctrl+B` thu gọn menu ·
`Ctrl+Shift+A` trung tâm cảnh báo · `F1` trợ giúp.
