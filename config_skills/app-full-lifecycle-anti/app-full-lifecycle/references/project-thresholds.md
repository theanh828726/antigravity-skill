# Project Thresholds

**Nguyên tắc:** Các con số "80% saliency", "misclick <0.5%", "LCP <2.5s" từ tài liệu UX Research là *ví dụ* từ context của các case study cụ thể, **không phải luật universal**. Skill này không hardcode chúng.

Ở Phase 3, hỏi user set (hoặc dùng default có nguồn). Ghi vào Scope Document. Ở Phase 6, so sánh với threshold user đã set — không tự bịa.

---

## Thresholds có nguồn chính thức (dùng làm default)

| Metric | Default | Nguồn | Khi nào override |
|---|---|---|---|
| Contrast body text | 4.5:1 | WCAG 2.2 AA (W3C) | AAA (7:1) cho app y tế/finance/gov target người lớn tuổi hoặc thị lực yếu |
| Contrast large text | 3:1 | WCAG 2.2 AA | AAA (4.5:1) cho case như trên |
| Touch target iOS | 44×44pt | Apple HIG | Chỉ tăng, không giảm |
| Touch target Android | 48×48dp | Material 3 | Chỉ tăng, không giảm |
| LCP | <2.5s | web.dev/vitals | Nới lên 4s cho internal tool không cần SEO/consumer perception |
| INP | <200ms | web.dev/vitals | Nới lên 500ms cho internal admin tool |
| CLS | <0.1 | web.dev/vitals | Khó nới — layout shift luôn khó chịu |

---

## Thresholds KHÔNG có nguồn universal — user phải quyết

**Không tự đặt số nếu user không nói.** Nếu user không care, skip metric đó khỏi audit.

### Misclick rate target

- **Không có "chuẩn" universal**. Số "0.5%" từ case study section 5.7 là ví dụ trong context checkout — không apply cho app khác.
- **Guide đề xuất user chọn**:
  - App payment/finance: thường target <1% (industry convention).
  - E-commerce checkout: 1-3%.
  - Consumer app không critical: 3-5%.
  - Internal tool: tùy — có thể không đo.
- **Cách đo**: cần production analytics (VD: track click → 5s sau back → count as misclick). Không có analytics → không có metric này.

### Attention heatmap saliency %

- **Không có "80% chuẩn"**. Số này từ predictive heatmap AI tool — chỉ dùng làm **baseline so sánh giữa các version**, không phải absolute threshold.
- **Nếu user muốn dùng**: cần AI attention tool (VA by 3M, Attention Insight, v.v.). Chưa có tool → không set threshold, chỉ chấm định tính "CTA có prominent không".

### Time on task

- **Không có universal**. Tùy task complexity.
- **Cách dùng**: đo internal usability test (5-10 user), lấy median làm baseline cho version 1, dùng làm target cho version 2 (giảm 15-30% là win).

### Task success rate

- **Convention NNG**: >80% cho task cốt lõi được coi là healthy. Nhưng không phải luật.
- User set threshold dựa trên criticality: task payment nên >95%, task nice-to-have có thể 70%.

### Post-task confidence

- Đo bằng survey 1-7. Trung bình >5 là healthy.
- Không có luật — chỉ dùng để so sánh giữa version.

---

## Template Phase 3 hỏi user

Ở Phase 3, hỏi 3 câu (chỉ hỏi nếu app có nature liên quan):

1. **App có xử lý financial transaction không?** Nếu có → recommend WCAG AAA, misclick <1%, contrast tăng.
2. **App có SEO / consumer perception là quan trọng không?** Nếu có → LCP/INP/CLS bám web.dev default. Nếu không (internal tool) → có thể nới.
3. **App có analytics production để đo misclick/task success không?** Nếu có → set target. Nếu chưa → skip, chỉ audit định tính.

---

## Cách audit dùng file này

Phase 6:
1. Đọc Scope Document xem user đã set threshold gì.
2. So sánh evidence với threshold user set.
3. **Không dùng default nếu user đã override.**
4. **Không audit metric mà user không set** (không tạo blocker giả).
