# Design Constraints — Phân loại theo tính bắt buộc

**Nguyên tắc quan trọng:** phân biệt giữa (A) chuẩn chính thức không thương lượng, (B) heuristic tốt nhưng có exception, và (C) project-specific threshold. Đừng dùng heuristic như thể là luật.

Nguồn: WCAG 2.2 (W3C, phiên bản hiện hành khi audit), Apple HIG (developer.apple.com/design/human-interface-guidelines/), Material 3 (m3.material.io), Nielsen Norman Group articles. Khi audit, verify version của nguồn tại thời điểm chạy (chuẩn có thể update).

---

## A. MANDATORY — Chuẩn chính thức, cứng

Vi phạm = automatic fail. Không waive được trong-session.

### A1. Accessibility (WCAG 2.2 AA — mức tối thiểu web content)

- Contrast body text ≥ **4.5:1** (WCAG 1.4.3).
- Contrast large text (≥18pt hoặc ≥14pt bold) ≥ **3:1**.
- Contrast UI component boundaries + graphical objects ≥ **3:1** (WCAG 1.4.11).
- Focus indicator visible cho keyboard (WCAG 2.4.7, 2.4.11).
- Không dùng màu là tín hiệu duy nhất (WCAG 1.4.1).
- `prefers-reduced-motion` được respect (WCAG 2.3.3).
- Content không mất khi zoom 200% (WCAG 1.4.4).
- Keyboard trap không tồn tại (WCAG 2.1.2).

Ứng dụng gov/health/finance ở nhiều nước cần AAA — hỏi user ở Phase 3.

### A2. Touch target (platform HIG)

- iOS: ≥ **44×44pt** (Apple HIG — Layout).
- Android: ≥ **48×48dp** (Material 3 — Accessibility).
- Web mobile: khuyến nghị 44px minimum theo WCAG 2.5.5 (Target Size — AAA).

### A3. Semantic HTML / ARIA

- Interactive element phải là `<button>` / `<a>` / `<input>`, không `<div onClick>`.
- Icon-only button phải có `aria-label` hoặc `aria-labelledby`.
- Form input phải có `<label>` associate, không placeholder-only.

### A4. Security (không phải design nhưng liên quan UI code)

- Không hardcode secret/API key trong client bundle.
- Sanitize user input trước khi render (chống XSS).
- Auth token không lưu trong localStorage cho app xử lý PII (dùng httpOnly cookie).

---

## B. HEURISTIC — Best practice, có exception cho phép

Được phép vi phạm nếu có justify rõ. Đừng audit như thể là luật.

### B1. Button hierarchy

- **Convention**: 1 Primary CTA (Filled) trên mỗi màn hình → Material 3 khuyến nghị.
- **Exception**: Dashboard đa mục tiêu (multiple equal-weight actions), wizard step (Back + Next đều primary intent), split-action button, editor toolbar.
- **Audit stance**: Flag như *"observation"* nếu >1 Primary, không automatic FAIL.

### B2. Label nút = `[Động từ] + [Đối tượng]`

- **Best practice** (NNG): "Xóa tài khoản" thay vì "OK". Giảm scan-error.
- **Exception chấp nhận được**: "OK" trong info-only dialog (không thay đổi state), "Cancel" trong confirmation (universally understood).
- **Audit stance**: WEAK cho "Submit"/"Gửi" chung chung — không FAIL.

### B3. Typography — tránh Inter/Roboto/system default

- **Heuristic** (10K checklist — Metics Media): dùng Inter/Roboto = signal "chưa quyết định".
- **Exception**: User brand đã chọn Inter (Vercel, Linear đều dùng và OK). System font để tối ưu performance internal tool. Editorial content ưu tiên serif có sẵn trong OS.
- **Audit stance**: WEAK nếu default + không có justify, không FAIL.

### B4. Color restraint (≤5 hue)

- **Heuristic** (10K): 2 neutrals + 1 hero + 1 supporting.
- **Exception**: Data viz (categorical colors phải nhiều hơn), children/education (playful mặc định), design language như Material vốn colorful.
- **Audit stance**: Đếm hue chỉ để observation, không hardcode "6 hue = fail".

### B5. Motion duration 150-300ms

- **Heuristic** (Material 3): micro-interaction 150-300ms.
- **Exception**: Splash/onboarding animation có thể dài hơn (400-800ms). Data viz transition (Line chart update) có thể 600-1000ms để mắt track.
- **Audit stance**: Chỉ flag khi >500ms cho micro-interaction *không có justify*.

### B6. Optimistic UI

- **Best practice** (NNG): Like/Save/Comment OK. Payment/Transfer không nên.
- **Exception**: App game/social có thể optimistic cả joining room, sending invite — rollback rẻ.
- **Audit stance**: Flag CRITICAL nếu Payment/Delete-critical dùng optimistic. Còn lại = observation.

---

## C. PROJECT THRESHOLD — Set ở Phase 3, không hardcode

Xem [project-thresholds.md](project-thresholds.md). Ví dụ:

- Misclick rate target — mặc định không có. App payment thường <1%, internal tool có thể <5%.
- Attention heatmap saliency % cho Primary CTA — không có "80% là chuẩn". Nếu chạy predictive heatmap, threshold là baseline so sánh giữa các version, không phải absolute.
- LCP/FID/CLS budget — lấy từ web.dev/vitals (phiên bản hiện hành), nhưng có thể nới cho internal tool không cần performance thi đấu.
- Contrast beyond AA — chỉ khi target audience có visual impairment cao (senior app, medical).

---

## Cách audit sử dụng file này

Khi Phase 6 chạy:
1. Check tất cả A → hit = CRITICAL BLOCKER, không waive.
2. Check tất cả B → hit = observation, ghi vào WEAK/RECOMMENDED, kèm câu hỏi *"có justify không?"*.
3. Check tất cả C so với threshold user đã set ở Phase 3 → hit = STANDARD BLOCKER, user quyết.

**Cấm** viết "vi phạm 1 primary CTA rule → FAIL" hay "font Inter → FAIL" trong báo cáo.
