---
name: app-full-lifecycle-anti
version: 1.1.0
last_updated: 2026-07-15
changelog: "v1.1.0 - Added QRC, updated frontmatter dependencies and trigger keywords per SkillAuditor."
depends_on:
  - app-blueprint-designer
  - frontend-design
  - ui-ux-pro-max
description: "Kỹ năng toàn diện thực thi SOP 7 giai đoạn (workflow, app lifecycle) để xây dựng Web/App từ khâu ý tưởng, thiết kế Blueprint, đề xuất UI/UX, code, audit, cho đến triển khai production-ready. Triggers: SOP tạo app, web development process, full lifecycle."
---

# App Full Lifecycle (Anti) 🚀

Kỹ năng này kết hợp sức mạnh từ `app-blueprint-designer`, `frontend-design`, và các quy tắc phát triển web hiện đại. Nó giúp em đồng hành cùng anh từ một ý tưởng thô sơ đến một sản phẩm hoàn chỉnh, production-ready với trải nghiệm cao cấp.

## Quy Trình 7 Giai Đoạn (SOP)

### Giai đoạn 1: Tiếp Nhận & Tối Ưu Ý Tưởng
- **Mục tiêu:** Hiểu rõ ý tưởng ban đầu của anh và làm cho nó sắc bén, khả thi hơn.
- **Hành động:** 
  - Phân tích WHAT, WHO, WHY, HOW, WHEN.
  - Gom các câu hỏi (tối đa 3 câu) để làm rõ Target User, Core Action, Scope.
  - Tư vấn thêm các tính năng phù hợp để tối ưu ý tưởng.
  - *Chờ anh phản hồi và chốt ý tưởng.*

### Giai đoạn 2: Lập Kế Hoạch & App Blueprint
- **Mục tiêu:** Tạo bản thiết kế hệ thống (Blueprint) hoàn chỉnh trước khi code.
- **Hành động:**
  - Viết `blueprint.md` bao gồm: Vision, Problem Statement, Target Personas, Core User Journey, và MVP Feature Set (3-7 tính năng cốt lõi).
  - *Đề xuất và chờ anh phê duyệt Blueprint.*

### Giai đoạn 3: Đề Xuất UI/UX & Design System
- **Mục tiêu:** Định hình phong cách thiết kế mang tính cá nhân hoá cao, premium, tránh lối mòn templated.
- **Hành động:**
  - **Màu sắc:** Đề xuất bảng màu cụ thể (Hex code), ưu tiên Dark theme, Glassmorphism.
  - **Typography:** Chọn các font hiện đại từ Google Fonts (Inter, Outfit, Roboto).
  - **Visual:** Đề xuất micro-animations, hover effects, gradient.
  - Trình bày Design System rõ ràng.
  - *Chờ anh xác nhận giao diện và phong cách.*

### Giai đoạn 4: Xây Dựng & Code (Frontend First)
- **Mục tiêu:** Hiện thực hóa bản thiết kế bằng code chất lượng cao.
- **Hành động:**
  - Tech stack: React, TypeScript, Vite, Vanilla CSS (Không dùng Tailwind trừ khi anh yêu cầu rõ).
  - Code Clean, tuân thủ SOLID, DRY, naming có ý nghĩa.
  - Không dùng placeholder cẩu thả; sử dụng tool tạo ảnh hoặc mock data chuyên nghiệp.

### Giai đoạn 5: Audit & Đánh Giá (Chấm Điểm)
- **Mục tiêu:** Đảm bảo sản phẩm đạt tiêu chuẩn chất lượng cao nhất.
- **Hành động:**
  - Tự động đánh giá giao diện, trải nghiệm (UX/UI), hiệu năng, SEO.
  - Chấm điểm từng tiêu chí trên thang điểm 100.
  - Với những tiêu chí điểm thấp hoặc chưa hoàn thiện, liệt kê chi tiết, đề xuất giải pháp cụ thể và tư vấn hướng khắc phục.
  - *Gửi báo cáo Audit và chờ anh quyết định hướng xử lý.*

### Giai đoạn 6: Hoàn Thiện & Tối Ưu
- **Mục tiêu:** Xử lý các điểm yếu từ bước Audit và ráp nối logic hoàn chỉnh.
- **Hành động:**
  - Áp dụng các giải pháp đã được anh duyệt để nâng điểm Audit.
  - Chạy test toàn diện (build + dev server + browser check) để đảm bảo không có lỗi.

### Giai đoạn 7: Bàn Giao & Deploy
- **Mục tiêu:** Đưa ứng dụng ra môi trường thực tế.
- **Hành động:**
  - Đóng gói ứng dụng gọn gàng.
  - Cung cấp các lệnh deploy, hoặc hướng dẫn deploy lên Vercel/Netlify.
  - Tạo artifact `walkthrough.md` tổng kết toàn bộ quá trình và thành tựu.

## Quy Tắc Cốt Lõi Khi Thực Hiện
1. Xưng hô "anh" - "em", giao tiếp bằng Tiếng Việt thân thiện, tôn trọng và chuyên nghiệp.
2. Code luôn phải ở mức Production-ready, nói KHÔNG với code dummy hay basic.
3. Ưu tiên mở rộng code hiện có hơn là đập đi viết lại.
4. Luôn kiểm tra Knowledge Items (KI) và lịch sử trò chuyện trước khi bắt tay vào việc để bám sát context.

---

## ⚡ Quick Reference Card (QRC) v1.1.0

```text
┌──────────────────────────────────────────────────────────────┐
│       APP FULL LIFECYCLE (ANTI) – 7-STAGE SOP                │
├──────────────────────────────────────────────────────────────┤
│ 1. Ý TƯỞNG   : Hỏi đáp, làm rõ WHAT/WHO/WHY/HOW/WHEN (max 3) │
│ 2. BLUEPRINT : Lập kế hoạch, Core Journey, MVP Features      │
│ 3. UI/UX     : Đề xuất màu sắc (Dark theme), Font, Visual    │
│ 4. CODE      : Frontend First (React, TS, Vite, Vanilla CSS) │
│ 5. AUDIT     : Chấm điểm 100, rà soát UX/UI, SEO, Performance│
│ 6. TỐI ƯU    : Sửa lỗi từ Audit, Build, Dev server check     │
│ 7. BÀN GIAO  : Đóng gói, Hướng dẫn deploy, Tạo walkthrough   │
├──────────────────────────────────────────────────────────────┤
│ ⚠️ RULE: Production-ready code, Tiếng Việt thân thiện, No    │
│ dummy data, Luôn check KI trước khi làm.                     │
└──────────────────────────────────────────────────────────────┘
```
