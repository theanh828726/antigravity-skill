# Audit Rubric — Phase 6 Scoring (Evidence-Required)

Rubric 5 chiều có trọng số. **Không có evidence → không có điểm.**

---

## Quy tắc evidence (bắt buộc)

Mỗi điểm 1-10 cho một chiều phải kèm **≥1 evidence artifact** theo 1 trong 4 dạng hợp lệ:

| Loại evidence | Cách thu | Ví dụ |
|---|---|---|
| **Screenshot** | `preview_screenshot` → lưu path | `evidence/audit-2026-07-15/checkout-mobile.jpg` — vùng bottom bar |
| **Computed style** | `preview_inspect` selector | `.btn-primary { color:#fff; bg:#2563EB; contrast:8.2:1; padding:12px 24px }` |
| **Runtime log** | `preview_console_logs` / `preview_network` | Console error trace, HTTP 500 response body |
| **Nguyên văn UI copy** | Quote trực tiếp | Error message: *"Something went wrong"* (không hữu ích) |

**Nếu không có evidence:** ghi `N/E` (No Evidence) cho chiều đó. Không được đoán điểm dựa trên "có vẻ ổn". Nếu **>30% chiều** bị `N/E`:
- Audit chưa hoàn thành.
- Không được sang Phase 7.
- Báo user lý do (preview MCP thiếu? App chưa chạy? Cần user cung cấp screenshot?).

**Weighted total chỉ được tính nếu tất cả 5 chiều có evidence.** Có `N/E` → báo "partial score, cần bổ sung evidence trước khi kết luận".

---

## Chiều 1 — Usability / Discoverability (weight 20%)

**Định nghĩa:** User tìm được và hiểu được Primary action nhanh.

**Cách chấm (với evidence):**
- **9-10**: CTA prominent, label rõ, không cần scroll. Evidence: screenshot + selector + label text.
- **7-8**: CTA visible nhưng cạnh tranh, hoặc label chung chung. Evidence: screenshot + label quote.
- **5-6**: Phải scan mới thấy. Evidence: screenshot + mô tả scan path.
- **3-4**: CTA ẩn trong menu / bị đè. Evidence: screenshot 2 vị trí (menu + landing).
- **1-2**: Không xác định được đâu là Primary. Evidence: screenshot + list các button candidate.

**Không được** chấm bằng trực giác. Nếu chỉ có "cảm giác OK" → `N/E`.

---

## Chiều 2 — Correctness & Error Prevention (weight 25%)

**Định nghĩa:** Ngăn thao tác nhầm, xử lý sạch loading/error/empty state.

**Cách chấm (với evidence):**
- **9-10**: Test rage-click không tạo duplicate. Inline validation trước submit. Undo/Confirm cho destructive. Evidence: network log (không có duplicate POST) + screenshot validation state.
- **7-8**: Có loading state nhưng không chặn hoàn toàn. Evidence: network log ghi 2 request đồng thời.
- **5-6**: Chỉ validate sau submit. Evidence: screenshot error banner top page.
- **3-4**: Có thể double-submit. Evidence: network log 3+ duplicate.
- **1-2**: App crash khi input sai. Evidence: console log stack trace.

---

## Chiều 3 — Performance & Accessibility (weight 15%)

**Định nghĩa:** Contrast pass, keyboard nav được, tốc độ chấp nhận được, screen reader OK.

**Cách chấm (với evidence):**
- **9-10**: Contrast ≥4.5:1 mọi chỗ. Tab order mượt. LCP <2.5s. Evidence: inspect ≥3 element key + tab order trace + Lighthouse report path.
- **7-8**: Fail 1-2 chỗ nhỏ. Evidence: inspect chỗ fail + kết quả overall.
- **5-6**: Nhiều chỗ contrast fail. Evidence: inspect list ≥3 fail.
- **3-4**: Không tab được. Evidence: screenshot + mô tả tab dừng ở đâu.
- **1-2**: Không semantic. Evidence: DOM inspect show `<div onClick>`.

**Baseline nguồn:** WCAG 2.2 (W3C, verify version hiện hành khi audit). Web Vitals threshold (LCP<2.5s, INP<200ms, CLS<0.1) từ web.dev — có thể user nới ở Phase 3 cho internal tool.

---

## Chiều 4 — User Trust (weight 20%)

**Định nghĩa:** Không dark pattern, không thao túng.

**Cách chấm (với evidence):**
- **9-10**: Nút Cancel visual weight ngang Confirm. Không countdown fake. Flow hủy tài khoản dễ tìm. Evidence: screenshot comparison + flow trace.
- **7-8**: 1 pattern nghi ngờ nhưng có justify. Evidence: screenshot + note lý do.
- **5-6**: Cancel button làm mờ/nhỏ. Evidence: inspect font-size + opacity của Cancel vs Confirm.
- **3-4**: Multiple dark pattern. Evidence: screenshot list.
- **1-2**: Toàn bộ flow manipulative. Evidence: flow diagram.

**Không được** chấm cao chỉ vì "brand có vẻ tử tế". Không có screenshot flow hủy = `N/E`.

---

## Chiều 5 — Cross-platform Fit (weight 20%)

**Định nghĩa:** Hoạt động tốt trên cả desktop + mobile, tuân platform convention.

**Cách chấm (với evidence):**
- **9-10**: Test cả 375×812 và 1440×900. Touch target đo ≥44pt. Safe area OK. Evidence: 2 screenshot + inspect button size.
- **7-8**: Responsive OK nhưng 1 platform thiếu polish. Evidence: 2 screenshot + point out gap.
- **5-6**: Mobile vỡ 1-2 chỗ. Evidence: mobile screenshot chỗ vỡ.
- **3-4**: Chỉ hoạt động 1 platform. Evidence: 2 screenshot.
- **1-2**: Desktop-only. Evidence: mobile screenshot unusable.

---

## Weighted total

```
Total = 0.20×Ch1 + 0.25×Ch2 + 0.15×Ch3 + 0.20×Ch4 + 0.20×Ch5
```

## Threshold quyết định (mặc định — user có thể override ở Phase 3)

Đây là **default heuristic**, không phải luật:

- **≥ 8.0**: Recommend ship, có thể có nice-to-fix.
- **6.5 - 7.9**: Recommend fix top 3 blocker trước.
- **< 6.5**: Recommend rework hoặc revisit design proposal.

User có thể set ngưỡng riêng (VD: internal tool có thể chấp nhận 6.0). Xem [project-thresholds.md](project-thresholds.md).

---

## Critical blocker — TÁCH RIÊNG khỏi rubric score

Rubric score cao KHÔNG có nghĩa được ship. Các nhóm sau **luôn block ship** dù điểm 10/10:

### Nhóm Security (không waive được in-session)
- XSS trong user input render
- SQL injection / prompt injection cho AI
- Secret/API key/DB credential hardcode trong client bundle
- Missing CSRF trên state-changing API
- Auth bypass, insecure direct object reference (IDOR)

### Nhóm Data integrity (không waive được in-session)
- Không có confirm cho delete-critical (financial, user account, uploaded file lâu dài)
- Race condition gây double-charge/duplicate order
- Không handle partial failure ở multi-step transaction (payment + inventory + email)
- Optimistic UI cho Payment/Transfer/Booking

### Nhóm PII / compliance (không waive được in-session)
- Log/analytics ghi email/phone/SSN/credit card không mask
- Gửi PII qua GET query param (bị log ở proxy/browser history)
- Không có cookie consent cho tracking non-essential (nếu target EU/UK/CA)
- Thiếu "Delete my data" flow (GDPR right to erasure)

### Nhóm Accessibility hard-fail (không waive được in-session)
- Nội dung critical chỉ truyền qua màu (colorblind không dùng được)
- Contrast fail cho error/warning text
- Video autoplay có lời không có captions

### Xử lý critical blocker
1. Ghi vào audit report dưới section **CRITICAL BLOCKER**.
2. **Không hỏi user** *"có accept không?"* — mặc định fix.
3. Nếu tự động fix được: fix ngay và re-verify.
4. Nếu cần user quyết (VD: đổi luồng business để bỏ optimistic UI cho payment): STOP và escalate — user phải quyết bằng suy nghĩ, không phải bấm "accept".

## Standard blocker / recommended — user quyết

Với các mục còn lại (usability weak, motion nhàm, font default, dark mode chưa fine-tune…):
- User có thể chọn **Fix / Defer to v2 / Accept as-is**.
- Nếu chọn Accept as-is hoặc Defer, phải ghi vào Scope Document dạng:
  ```
  [ACCEPTED-RISK-2026-07-15]: Font display dùng Inter thay vì premium pairing
  Lý do: Brand internal tool, không cần premium feel
  Impact: 10K craft score sẽ WEAK, không ảnh hưởng usability
  ```
- Không được ghi "user OK" mà không có justify.
