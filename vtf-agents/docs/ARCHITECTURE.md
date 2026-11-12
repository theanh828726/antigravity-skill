# Kiến trúc

```
Telegram ──► bot/app.py (phân quyền owner/staff, nút Duyệt, nhắc việc)
               └► Orchestrator (TQ, có lịch sử hội thoại)
                    └► delegate ─► Agent VP-0x (vòng lặp tool-use riêng)
                                      └► Tool ─► DB / Gmail / Calendar / Drive
                                         └► tool có approval_action ─► bảng approvals (pending)
                                                  └► Telegram [Duyệt/Từ chối] ─► executor ─► evidence + audit_log
```

## Nguyên tắc
- **Hồ sơ chung**: `cases` là trục; việc, văn bản, phê duyệt, bằng chứng đều trỏ về `case_id`.
- **Phê duyệt cứng ở tầng code**, không dựa vào lời nhắc cho model: tool gắn `approval_action` không bao giờ chạy
  trực tiếp; chỉ `decide()` (owner) mới gọi executor, có khóa hàng chống bấm đúp.
- **Bằng chứng**: mỗi hành động ghi `evidence` (mã thư đã gửi, mã sự kiện, phiên bản văn bản, nguồn trích dẫn) và `audit_log`.
- **Dữ liệu ngoài là dữ liệu**: nội dung thư/tài liệu được dán nhãn không đáng tin; không có tool nào gửi/tạo/duyệt mà không qua duyệt.
- **Fallback an toàn**: bật `fallbacks` server-side của Claude theo mặc định (tắt bằng `CLAUDE_USE_FALLBACKS=false`).

## Thêm agent mới (HV, SK-01..03, TT)
1. Tạo `agents/<ma>.py` có `build() -> AgentDef` (system prompt + `Tool`), hành động ra ngoài thì khai `approval_action`
   và đăng ký `@executor("<action>")`.
2. Thêm vào `agent_registry()` và bỏ khỏi `INACTIVE` trong `core/orchestrator.py`; cập nhật `TQ_SYSTEM`.
3. Thêm bảng dữ liệu vào `db/models.py` (hội viên, sự kiện, giải đấu...), viết test theo mẫu `tests/test_flows.py`.

## Giới hạn hiện tại
- Chưa có migration (dùng `create_all`); thêm Alembic trước khi sửa schema trên dữ liệu thật.
- VP-05 tìm theo từ khóa; nâng lên pgvector/FTS bằng cách thay `core/knowledge.search`.
- PDF dạng ảnh scan chưa OCR.
- Adapter Google và Postgres chưa được kiểm thử với dịch vụ thật trong phiên dựng này.
