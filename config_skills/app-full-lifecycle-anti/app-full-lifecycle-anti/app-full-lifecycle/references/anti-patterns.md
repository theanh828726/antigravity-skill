# Anti-Patterns Scan — 12 Common Misconceptions

Từ tài liệu UX Research section 3.6. Ở Phase 6, scan design/build của mình xem có hit pattern nào không.

## 1. "Nút càng to càng tốt"
**Hit signal:** Primary CTA chiếm >30% chiều cao viewport, đè content quan trọng.
**Fix:** Cân bằng — CTA đủ prominent nhưng không phá hierarchy.

## 2. "Màu đỏ luôn tốt nhất cho CTA"
**Hit signal:** Nút Save/Confirm màu đỏ. Nút Delete cũng đỏ. User nhầm cả hai.
**Fix:** Đỏ reserve cho destructive. Primary dùng brand accent hoặc màu neutral-đối-lập.

## 3. "Mọi hành động cần animation"
**Hit signal:** Animation >300ms cho micro-interaction. Power user phải chờ.
**Fix:** Animation 150-250ms max. Toggle skip cho power user hoặc respect `prefers-reduced-motion`.

## 4. "Ít nút = dễ dùng hơn"
**Hit signal:** Mọi thứ ẩn trong hamburger menu. Discoverability = 0.
**Fix:** Bottom nav 3-5 item cho tính năng chính. Hamburger chỉ cho tertiary.

## 5. "User sẽ đọc toàn bộ nội dung"
**Hit signal:** Long paragraph text cho instruction. Modal có 5 dòng warning.
**Fix:** Bullet points, bold keywords. Người ta scan không đọc.

## 6. "Icon luôn tiết kiệm không gian"
**Hit signal:** Icon-only button không có label (trừ home/search phổ biến).
**Fix:** Icon + label. Hoặc icon-only với `aria-label` + tooltip.

## 7. "Disabled button giúp tránh lỗi"
**Hit signal:** Submit button disabled ngay khi mở form. User không biết cần gì.
**Fix:** Cho bấm → inline validation ở field sai.

## 8. "Mobile chỉ là web thu nhỏ"
**Hit signal:** Sidebar desktop scale xuống mobile. Hover-only interaction.
**Fix:** Mobile-first design. Bottom nav + thumb-reach + touch feedback.

## 9. "Conversion cao = UX tốt"
**Hit signal:** A/B test winner có Cancel rate cao, Support ticket tăng.
**Fix:** Guardrail metrics — không chỉ nhìn conversion.

## 10. "Đẹp = dễ dùng"
**Hit signal:** Glassmorphism đẹp nhưng contrast fail. Font display artistic nhưng khó đọc.
**Fix:** Usability > Aesthetics. Aesthetic-usability effect có tồn tại nhưng không đủ.

## 11. "Design system tự động tạo consistency"
**Hit signal:** Component chuẩn nhưng lắp sai context — luồng UX vẫn gãy.
**Fix:** Consistency ở flow-level, không chỉ component-level.

## 12. "Accessibility chỉ cho người khuyết tật"
**Hit signal:** Bỏ WCAG vì "app của tôi cho young/tech user".
**Fix:** Contrast tốt giúp cả người dùng ngoài nắng. Touch target to giúp trên xe xóc.

---

## Additional anti-patterns thường gặp (bonus)

### 13. Placeholder as label
Field chỉ có placeholder text — user bắt đầu gõ là mất label.
**Fix:** Label visible + placeholder gợi ý format.

### 14. Modal spam
Popup layered: cookie consent → newsletter → app rating → tour.
**Fix:** Priority. 1 modal 1 lần, dùng delay + trigger context.

### 15. Autoplay video with sound
Hero video autoplay + sound = user reflex mute và bực.
**Fix:** Autoplay tắt tiếng, có nút unmute.

### 16. Infinite scroll không có anchor
User cuộn 500 item, click 1 cái, back → mất vị trí.
**Fix:** URL preserve position, hoặc "Load more" button.
