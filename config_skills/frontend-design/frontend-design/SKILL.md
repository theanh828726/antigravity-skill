---
name: frontend-design
version: 1.1.0
last_updated: 2026-07-22
changelog: "v1.1.0 - Refactored to comply with SkillMaster standard format (added Phases, Golden Rules, QRC)."
description: "Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults. Kích hoạt khi cần định hình triết lý thiết kế, đưa ra quyết định thẩm mỹ, chọn font/layout cá nhân hóa thay vì default."
depends_on:
  - ui-ux-pro-max
---

# 🎨 Frontend Design - Triết Lý & Định Hướng Thẩm Mỹ

Skill này định hình tư duy như một Design Lead tại một studio cao cấp. Mục tiêu là tạo ra những thiết kế mang đậm tính cá nhân hóa (distinctive point of view), dám đưa ra những quyết định táo bạo về màu sắc, typography và layout, từ chối sự rập khuôn (templated).

---

## BƯỚC 0: TIẾP NHẬN YÊU CẦU
- Xác định rõ bối cảnh: Chủ thể (Subject) là gì? Khán giả (Audience) là ai? Mục tiêu chính của trang (Single Job)?
- Phân tích Brand Voice và phong cách mong muốn từ người dùng.

---

## PHASE 1: ĐỊNH HÌNH PHONG CÁCH (AESTHETIC DIRECTION)
- **The Hero is a Thesis:** Bắt đầu bằng yếu tố đặc trưng nhất của chủ đề (headline, ảnh, animation, live demo). Không dùng template "số to + nhãn nhỏ + gradient" nếu nó không thực sự phù hợp.
- **Complexity Match:** Giao diện tối đa (Maximalist) cần sự cầu kỳ, giao diện tối giản (Minimal) cần sự chính xác tuyệt đối trong spacing và typography.

---

## PHASE 2: TYPOGRAPHY & LAYOUT (CẤU TRÚC & CHỮ)
- **Typography mang tính cách:** Kết hợp Display và Body fonts một cách có chủ đích. Thiết lập Type Scale rõ ràng với weights, widths và spacing. Biến typography thành yếu tố ghi nhớ.
- **Structure is Information:** Không dùng các yếu tố cấu trúc (như đánh số 01/02/03) để trang trí nếu nội dung không thực sự là một chuỗi tuần tự. Cấu trúc phải phản ánh đúng logic thông tin.

---

## PHASE 3: MOTION & ANIMATION (CHUYỂN ĐỘNG)
- **Sử dụng Motion có chủ đích:** Page-load sequence, scroll-reveal, hover micro-interactions, hoặc ambient atmosphere.
- Tránh hiệu ứng phân tán. Sự tĩnh lặng đôi khi tốt hơn; lạm dụng animation sẽ làm trang web trông giống "AI-generated".

---

## PHASE 4: UX WRITING (VIẾT NỘI DUNG)
- Chữ xuất hiện để giúp UI dễ hiểu và dễ dùng, không phải để trang trí.
- **Active Voice:** Nút bấm phải nói rõ chức năng ("Lưu thay đổi", không dùng "Gửi"). Tính nhất quán cao ("Publish" -> "Published").
- **Error & Empty States:** Lỗi không cần xin lỗi mà phải nói rõ cách sửa. Màn hình trống là một lời mời hành động.
- Viết ngắn gọn, rõ ràng, hướng đến người dùng cuối.

---

## PHASE 5: TỰ ĐÁNH GIÁ (SELF-CRITIQUE)
- Dành sự "táo bạo" vào 1 chỗ duy nhất (Signature Element). Giữ mọi thứ xung quanh tinh tế và kỷ luật.
- Đảm bảo Responsive, Keyboard focus, và Accessibility.

---

## 🧠 QUY TẮC VÀNG (GOLDEN RULES)
1. **TRÁNH RẬP KHUÔN:** Bỏ qua các default design của AI (như kem/nâu đỏ, đen/xanh neon, cột báo chí).
2. **CÁ TÍNH HÓA:** Mỗi component, màu sắc, font chữ phải được lựa chọn CÓ LÝ DO từ bối cảnh dự án.
3. **ÍT NHƯNG CHẤT:** "Trước khi ra khỏi nhà, hãy soi gương và tháo bớt một món phụ kiện" - Chanel.

---

## ⚡ Quick Reference Card (QRC) v1.1.0

```text
┌──────────────────────────────────────────────────────────────┐
│       FRONTEND DESIGN – AESTHETIC PHILOSOPHY                 │
├──────────────────────────────────────────────────────────────┤
│ P1: AESTHETIC → Xác định Hero, Complexity Match              │
│ P2: TYPO/LAYOUT → Font cá tính, Cấu trúc là thông tin        │
│ P3: MOTION      → Chuyển động có chủ đích, tránh lạm dụng    │
│ P4: UX WRITING  → Viết hướng tới user, Active voice          │
│ P5: CRITIQUE    → Đánh giá sự táo bạo, UX accessibility      │
├──────────────────────────────────────────────────────────────┤
│ ⚠️ RULE: Táo bạo ở 1 điểm, tối giản phần còn lại. KHÔNG dùng │
│ placeholder text. Luôn giải thích lý do đằng sau design.     │
└──────────────────────────────────────────────────────────────┘
```
