# Pre-Release Checklist

Mỗi item được tag mức độ:

- 🔴 **[CRITICAL]** — không waive được in-session. Fail = không ship, bất kể user muốn gì.
- 🟡 **[STANDARD]** — waive được nếu user justify + record vào Scope Document.
- 🟢 **[RECOMMENDED]** — nice-to-have. Waive không cần justify.

---

## Accessibility (nguồn: WCAG 2.2 — W3C)

- 🔴 **[CRITICAL]** Contrast body text ≥ 4.5:1, large text ≥ 3:1.
- 🔴 **[CRITICAL]** Không có keyboard trap (mọi element tab ra được).
- 🔴 **[CRITICAL]** Không dùng màu là tín hiệu duy nhất (error phải có icon/text kèm).
- 🔴 **[CRITICAL]** Video có lời phải có captions/transcript.
- 🟡 **[STANDARD]** Tab được toàn page với `:focus-visible` rõ ràng.
- 🟡 **[STANDARD]** Screen reader (VoiceOver/TalkBack) đọc đúng thứ tự.
- 🟡 **[STANDARD]** `prefers-reduced-motion` — animation tự tắt.
- 🟡 **[STANDARD]** `prefers-color-scheme: dark` — dark mode contrast vẫn pass.
- 🟢 **[RECOMMENDED]** Content zoom 200% không vỡ layout.
- 🟢 **[RECOMMENDED]** Dynamic Type (font size hệ thống tăng) không cắt cụt label.

---

## Touch & Interaction (nguồn: Apple HIG, Material 3)

- 🔴 **[CRITICAL]** Touch target ≥ 44×44pt (iOS) / 48×48dp (Android) cho action chính.
- 🟡 **[STANDARD]** Spacing giữa tap target ≥ 8px.
- 🟡 **[STANDARD]** Bật bàn phím ảo, nút quan trọng không bị che khuất.
- 🟢 **[RECOMMENDED]** Loading feedback trong 100ms sau click.

---

## Correctness

- 🔴 **[CRITICAL]** Loading state khóa nút để chặn double API request cho payment/transfer/critical action.
- 🔴 **[CRITICAL]** Error boundary tồn tại (app không crash trắng màn hình).
- 🟡 **[STANDARD]** Empty state / error state / loading state có UI riêng (không "No data").
- 🟡 **[STANDARD]** Success state có feedback rõ (toast/snackbar/nav).
- 🟡 **[STANDARD]** Disabled button có giải thích inline (hoặc bỏ disable, thay bằng validation).
- 🟢 **[RECOMMENDED]** Label nút là động từ chỉ hành động (không "OK"/"Submit" — trừ context info-only dialog).
- 🟢 **[RECOMMENDED]** Chỉ 1 Filled Primary Button/màn hình (trừ dashboard đa mục tiêu).

---

## Security

- 🔴 **[CRITICAL]** Không hardcode secret/API key/DB credential trong client bundle.
- 🔴 **[CRITICAL]** User input sanitize trước khi render (chống XSS).
- 🔴 **[CRITICAL]** State-changing API có CSRF protection (form token hoặc SameSite cookie).
- 🔴 **[CRITICAL]** Auth token cho app xử lý PII lưu trong httpOnly cookie, không localStorage.
- 🟡 **[STANDARD]** Content Security Policy header cấu hình.
- 🟡 **[STANDARD]** HTTPS enforced (redirect HTTP → HTTPS).

---

## Data & Network

- 🔴 **[CRITICAL]** Xử lý partial failure trong multi-step transaction (payment + inventory + email).
- 🟡 **[STANDARD]** Test 3G throttling — app còn dùng được.
- 🟡 **[STANDARD]** Test offline — có message hoặc cache.
- 🟡 **[STANDARD]** Test API 5xx error — có fallback message hữu ích (không "Error 500").
- 🟢 **[RECOMMENDED]** Data persistence sau F5 (state cần thiết không mất).

---

## Privacy & Compliance

- 🔴 **[CRITICAL]** Log/analytics không ghi email/phone/SSN/credit card không mask.
- 🔴 **[CRITICAL]** PII không gửi qua GET query param.
- 🔴 **[CRITICAL]** Có "Delete my account/data" flow nếu app lưu PII (GDPR nếu target EU).
- 🟡 **[STANDARD]** Cookie consent cho tracking non-essential (nếu target EU/UK/CA/Brazil).
- 🟡 **[STANDARD]** Privacy policy accessible từ mọi trang.

---

## Performance (nguồn: web.dev/vitals — verify version)

- 🟡 **[STANDARD]** LCP < 2.5s (mobile 3G throttled) — default web.dev threshold.
- 🟡 **[STANDARD]** INP < 200ms.
- 🟡 **[STANDARD]** CLS < 0.1.
- 🟢 **[RECOMMENDED]** Lighthouse Performance ≥ 80 (nếu SEO quan trọng).
- 🟢 **[RECOMMENDED]** Bundle size < 200KB gzip cho landing page.

*Threshold có thể nới cho internal tool — set ở Phase 3.*

---

## Localization (nếu bilingual/multi-lang)

- 🟡 **[STANDARD]** Nút "Pay" vs "Thanh toán ngay" không vỡ layout.
- 🟡 **[STANDARD]** Number/date format đúng locale.
- 🟡 **[STANDARD]** Currency symbol đúng.
- 🟢 **[RECOMMENDED]** RTL support nếu target Ả Rập/Hebrew.

---

## Analytics & Monitoring (post-launch prep)

- 🟡 **[STANDARD]** Mọi Primary CTA có event tracking.
- 🟡 **[STANDARD]** Error reporting (Sentry/equivalent) gắn.
- 🟢 **[RECOMMENDED]** Guardrail metrics identified: bounce rate, error rate, cancel rate.

---

## Cách chạy checklist

1. Đi từ trên xuống, tick từng item.
2. Bất kỳ 🔴 fail → STOP. Không được sang Phase 7 ship. Không hỏi user waive.
3. Với 🟡 fail → hỏi user: **Fix / Defer to v2 / Accept as-is (với justify)**.
4. Với 🟢 fail → default là accept, chỉ mention nếu user hỏi.

**Không được** đánh dấu 🔴 là "passed" khi không có evidence verify. Nếu không verify được (VD: chưa test 3G) → ghi "UNVERIFIED", không "passed".
