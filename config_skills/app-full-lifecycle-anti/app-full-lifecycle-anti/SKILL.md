---
name: app-full-lifecycle-anti
version: 1.2.0
last_updated: 2026-07-22
changelog: "v1.2.0 - Refactored to meta-skill (orchestrator). Removed hardcoded Dark theme to comply with new global SOP color rules."
depends_on:
  - SOP
  - app-blueprint-designer
  - frontend-design
  - ui-ux-pro-max
description: "Meta-skill điều phối toàn diện vòng đời phát triển Web/App. Kết hợp SOP gốc với các skill UI/UX để từ ý tưởng đến production-ready. Triggers: SOP tạo app, web development process, full lifecycle."
---

# App Full Lifecycle (Anti) 🚀

Kỹ năng này hoạt động như một Meta-Skill, kết hợp sức mạnh từ `SOP` (Kỹ năng cốt lõi), `app-blueprint-designer`, `frontend-design`, và `ui-ux-pro-max` để đồng hành cùng anh từ một ý tưởng thô sơ đến một sản phẩm hoàn chỉnh.

## 🔄 Luồng Điều Phối (Orchestration Workflow)

Thay vì định nghĩa lại quy trình từ đầu, skill này kích hoạt chuỗi 7 giai đoạn của kỹ năng `SOP` chuẩn, đồng thời **bơm thêm (inject)** các tác vụ nâng cao vào các giai đoạn cụ thể:

### 1. Tại Giai đoạn 2 của SOP (Lên Kế Hoạch):
- Tự động gọi tư duy của `app-blueprint-designer` để lập bản thiết kế Blueprint hoàn chỉnh (Vision, Problem Statement, Target Personas, Core User Journey, và MVP Feature Set).

### 2. Tại Giai đoạn 3 của SOP (Design & Architecture):
- **BẮT BUỘC tuân thủ luật màu sắc:** Ưu tiên sử dụng màu do người dùng yêu cầu hoặc truy xuất từ MCP. TUYỆT ĐỐI KHÔNG hardcode mặc định Dark Theme nếu chưa được phép.
- Gọi tư duy của `frontend-design` để định hình triết lý thiết kế (Aesthetic Direction, Typography, Layout, Motion).
- Gọi công cụ `ui-ux-pro-max` (bằng command-line) để lấy các token CSS cụ thể, bảng màu chuẩn, font pairing, và GSAP animation snippets. Trình bày Design System.

### 3. Tại Giai đoạn 4 & 5 của SOP (Code & Audit):
- Áp dụng các rules chi tiết từ `ui-ux-pro-max` để audit UI (Contrast, Accessibility, Touch & Interaction).
- Code Clean, tuân thủ SOLID, DRY, naming có ý nghĩa (React, TS, Vite, Vanilla CSS).
- Không dùng placeholder cẩu thả.

## 🧠 QUY TẮC VÀNG (GOLDEN RULES)
1. **DELEGATE, DON'T DUPLICATE:** Luôn sử dụng kỹ năng `SOP` làm xương sống. Skill này chỉ làm nhiệm vụ gắn thêm các module nâng cao.
2. **USER COLORS ALWAYS WIN:** Tuyệt đối không tự ý quyết định phong cách/màu sắc (như mặc định Dark Theme) mà bỏ qua yêu cầu của người dùng/MCP.
3. **PRODUCTION-READY:** Code, hình ảnh, văn bản (UX copy) đều phải đạt chuẩn thực tế, không dùng dummy/lorem ipsum.

---

## ⚡ Quick Reference Card (QRC) v1.2.0

```text
┌──────────────────────────────────────────────────────────────┐
│       APP FULL LIFECYCLE (ANTI) – META ORCHESTRATOR          │
├──────────────────────────────────────────────────────────────┤
│ 1. KÍCH HOẠT SOP: Sử dụng luồng 7 bước của SOP chuẩn.        │
│ 2. INJECT P2    : Gọi app-blueprint-designer lập kế hoạch.   │
│ 3. INJECT P3    : Gọi frontend-design & ui-ux-pro-max.       │
│                   ⚠️ Chú ý: Tuân thủ tuyệt đối màu User/MCP. │
│ 4. INJECT P4+P5 : Audit UI/UX khắt khe theo ui-ux-pro-max.   │
├──────────────────────────────────────────────────────────────┤
│ ⚠️ RULE: Đây là Meta-skill, KHÔNG tự chế quy trình mới. Mọi  │
│ quyết định màu sắc/theme phải bám sát SOP gốc.               │
└──────────────────────────────────────────────────────────────┘
```
