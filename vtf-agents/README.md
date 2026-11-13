# VTF AI Agent - Tổng quản GoClaw (điều hành qua Telegram)

Triển khai theo sơ đồ tổ chức v2.0: **1 Tổng quản (TQ) + 5 Agent Văn phòng (VP-01..05)**, dùng chung một
**hồ sơ công việc** (Postgres), điều hành bằng Telegram, mọi hành động ra bên ngoài phải được **Grand Master duyệt**.

| Agent | Chức năng | Công cụ chính |
|---|---|---|
| TQ | Hiểu yêu cầu, phân công, theo dõi, kiểm tra, tổng hợp | `delegate`, `case_overview`, `pending_approvals` |
| VP-01 | Công việc: hồ sơ, việc, hạn, tiến độ, KPI, nhắc việc | `create_case/task`, `update_task`, `kpi_summary` |
| VP-02 | Email: đọc, phân loại, soạn nháp; gửi sau khi duyệt | Gmail |
| VP-03 | Lịch: tra, trùng lịch, đề xuất khung giờ; tạo lịch sau duyệt | Google Calendar |
| VP-04 | Công văn: đến/đi, dự thảo, phiên bản, trình duyệt | Postgres + file upload |
| VP-05 | Hỏi đáp tài liệu có trích nguồn/phiên bản/điều | kho tri thức + Google Drive |

HV / SK / TT chưa kích hoạt: TQ báo đúng như vậy thay vì tự làm thay (xem `docs/ARCHITECTURE.md` để mở rộng).

## Chạy thử

1. Tạo bot với @BotFather lấy token; lấy Telegram user id của anh (ví dụ qua @userinfobot).
2. `cp .env.example .env` và điền `TELEGRAM_BOT_TOKEN`, `OWNER_TELEGRAM_IDS`, `ANTHROPIC_API_KEY`.
3. `docker compose up -d --build`
4. Nhắn bot: `/start`, rồi ví dụ: *"Lập hồ sơ Đại hội 2026, giao Lan chuẩn bị báo cáo trước 20/12 17:00"*.

Chưa điền khóa Google thì Gmail/Calendar/Drive chạy **mock trong bộ nhớ** (log ghi `Tích hợp Google: mock`);
điền `GOOGLE_*` để dùng thật. Refresh token cần các scope: `gmail.readonly`, `gmail.compose`, `calendar`, `drive.readonly`.

## Tự động hoá thư đến
Bot quét hộp thư mỗi `MAIL_POLL_SECONDS` (mặc định 120s). Với mỗi thư mới, agent tự: đọc → phân loại → (nếu cần phản hồi)
lập hồ sơ HS-…, tạo việc theo hạn, tra điều lệ trong kho tài liệu → soạn dự thảo trả lời → gửi lên Telegram:

`✅ Duyệt & gửi` · `🔁 Làm lại` (anh trả lời tin nhắn nhắc bằng góp ý; ra bản mới v2, v3…, tối đa `MAX_REVISIONS`) · `❌ Từ chối`
(sau khi từ chối vẫn có nút làm lại). Thư chỉ đi sau khi Duyệt, và gửi đúng luồng thư gốc. Thư thông báo/quảng cáo/tự động
được ghi nhận "không cần phản hồi" và báo nhẹ, không làm phiền. Mỗi thư chỉ xử lý một lần. Tắt bằng `AUTO_MAIL_ENABLED=false`.

## Lệnh Telegram
`/cases` `/tasks` `/pending` `/case HS-…` `/agents` `/reset`; gửi PDF/TXT/MD để lưu và lập chỉ mục.

## Phát triển
```
python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && pytest
```
Test dùng SQLite trong bộ nhớ, LLM kịch bản (không tốn token) và session Telegram giả.
