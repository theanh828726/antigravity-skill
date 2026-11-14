# Hướng dẫn cài đặt – Ứng dụng Kế toán (Hocviendaotaoai)

## Yêu cầu
- Windows 10/11 64-bit, màn hình từ **1366 × 768** (tối ưu 16:9).
- Bản chạy từ mã nguồn: Python **3.11 – 3.13** (https://www.python.org/downloads/, tick *Add python.exe to PATH*).

## Cách 1 – Dùng bản đóng gói sẵn (khuyến nghị cho người dùng cuối)
1. Lấy thư mục `UngDungKeToan` (artifact **UngDungKeToan-windows** của workflow GitHub Actions, hoặc tự build theo Cách 3).
2. Chép cả thư mục vào ví dụ `C:\Hocviendaotaoai\UngDungKeToan`.
3. Chạy `UngDungKeToan.exe`. Lần đầu ứng dụng tự tạo dữ liệu minh họa tại
   `%APPDATA%\Hocviendaotaoai\KeToan\data\ketoan_demo.db`.
4. Đăng nhập `admin / admin@123` (hoặc tài khoản khác trong README).

> Windows SmartScreen có thể cảnh báo vì file chưa ký số: chọn *More info → Run anyway*. Khi phát hành chính thức nên ký số
> bằng chứng thư Code Signing của doanh nghiệp.

## Cách 2 – Chạy từ mã nguồn
```bat
cd ung-dung-ke-toan
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Cách 3 – Tự đóng gói & tạo bộ cài
```bat
cd ung-dung-ke-toan
packaging\build_windows.bat
```
Script tự: tạo `.venv` → cài thư viện → **chạy kiểm thử (dừng nếu lỗi)** → PyInstaller → kèm dữ liệu mẫu.
Kết quả: `dist\UngDungKeToan\UngDungKeToan.exe`.

Bộ cài `.exe` (tùy chọn): cài Inno Setup 6 rồi chạy
`"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss` → `dist\CaiDat_UngDungKeToan_1.2.0-gd3.exe`.

## Dữ liệu, sao lưu, bảo mật
| Mục | Vị trí / cách làm |
|---|---|
| Dữ liệu mặc định | `%APPDATA%\Hocviendaotaoai\KeToan\data\` (file `.db`) |
| Sao lưu | Hệ thống → Sao lưu – khôi phục → *Sao lưu ngay* (thư mục `...\KeToan\backup\`) |
| Khôi phục | Chọn bản sao lưu → *Khôi phục*; ứng dụng tự sao lưu dữ liệu hiện tại trước (file `truoc_khoi_phuc_*.db`) |
| Mở / tạo dữ liệu khác | Thanh điều khiển → *Dữ liệu kế toán* → *Mở dữ liệu khác…* / *Tạo dữ liệu mới…* (quyền quản trị) |
| Mật khẩu | Lưu dạng băm PBKDF2-SHA256; **đổi mật khẩu các tài khoản mặc định** ngay khi dùng thật (Hệ thống → Người dùng & phân quyền) |

**Quan trọng:** bản này dùng SQLite cho **một người dùng trên một máy**. Không đặt file `.db` trong thư mục chia sẻ mạng (LAN)
để nhiều người cùng mở – có nguy cơ hỏng dữ liệu. Nhu cầu nhiều người dùng sẽ triển khai trên PostgreSQL.

## Bắt đầu với doanh nghiệp thật
1. *Dữ liệu kế toán → Tạo dữ liệu mới…*, nhập tên doanh nghiệp, đăng nhập `admin / admin@123`, **đổi mật khẩu**.
2. *Cài đặt* → cập nhật thông tin doanh nghiệp, chọn **chế độ kế toán + ngày hiệu lực** (sau khi đã kiểm chứng văn bản).
3. *Danh mục* → rà soát hệ thống tài khoản; nhập khách hàng, NCC, vật tư… bằng *Nhập Excel* (có ánh xạ cột, kiểm tra trước).
4. *Danh mục → Số dư đầu kỳ* → nhập số dư đầu năm, bảo đảm *Cân đối ✓*.
5. *Danh mục → Tồn kho đầu kỳ* → nhập số lượng, giá trị tồn đầu theo mã hàng + kho (khớp số dư TK kho).
6. *Cài đặt* → chọn **phương pháp tính giá xuất kho** (bình quân gia quyền cuối tháng hoặc FIFO), dùng nhất quán cả năm.
7. Hằng tháng: nhập chứng từ (hoặc *Đọc hóa đơn XML*) → Kiểm tra (F6) → Ghi sổ (F9) → *Xuất kho hàng loạt* cho bảng kê bán →
   **Tính giá xuất kho** → *Đối chiếu doanh thu – giá vốn* → Trung tâm cảnh báo → Kết chuyển → Khóa kỳ.

## Báo cáo tài chính và thuế – cách dùng đúng
1. *Hệ thống → Cài đặt → Chế độ kế toán*: chọn chế độ áp dụng + ngày hiệu lực **sau khi đã đối chiếu văn bản chính thức**.
2. *Báo cáo tài chính → (báo cáo) → Quản lý mẫu…*: nhập mẫu từ file Excel (cột A mã, B tên chỉ tiêu, C công thức, D thụt lề, E in đậm) lấy
   từ văn bản đã kiểm chứng; sửa lỗi nếu ứng dụng báo (cú pháp, tham chiếu, vòng lặp); quản trị viên bấm *Xác nhận đã kiểm chứng* kèm căn cứ.
   Mẫu thử nghiệm đi kèm (DEMO_BS, DEMO_IS) **không dùng để nộp**.
3. *Báo cáo thuế*: tham số thuế (thuế suất TNDN, điều chỉnh) do người dùng nhập kèm căn cứ; báo cáo chỉ hỗ trợ tính toán.
4. Cuối năm: kết chuyển hết doanh thu/chi phí → khóa kỳ → *Hệ thống → Chuyển số dư cuối năm*.

## Nâng cấp từ bản Giai đoạn 1 và 2
Mở file dữ liệu cũ bằng bản mới: ứng dụng **tự nâng cấp lược đồ** (thêm hạn thanh toán, liên kết chứng từ, tồn kho đầu
kỳ, phương pháp tính giá, TSCĐ/CCDC, giá thành, mẫu báo cáo, tham số thuế) trong một giao dịch; hạn thanh toán của chứng từ mua/bán cũ được tính = ngày hóa đơn + hạn TT
của đối tượng. Nên **sao lưu trước khi nâng cấp**. Bản cũ không mở được dữ liệu đã nâng cấp.

## Hóa đơn XML mẫu
`sample_data/hoa_don_xml/` có 4 file minh họa: hóa đơn mua hợp lệ, hóa đơn từ nhà cung cấp mới có lệch làm tròn thuế 1đ,
hóa đơn bán đã nhập (phát hiện trùng), hóa đơn không thuộc doanh nghiệp. Mở bằng *Chứng từ nghiệp vụ → Đọc hóa đơn XML*.

## Xử lý sự cố
| Hiện tượng | Cách xử lý |
|---|---|
| "File không phải dữ liệu của Ứng dụng Kế toán" | Chọn đúng file `.db` do ứng dụng tạo/sao lưu |
| Không ghi sổ được | Bấm *Kiểm tra (F6)* xem danh sách lỗi chặn; hoặc mở *Trung tâm cảnh báo* |
| Không sửa được chứng từ | Chứng từ đã ghi sổ → *Bỏ ghi sổ*; nếu thuộc kỳ đã khóa → người có quyền mở khóa kỳ |
| Không thấy nút / bị từ chối | Tài khoản thiếu quyền – quản trị cấp quyền trong *Người dùng & phân quyền* |
