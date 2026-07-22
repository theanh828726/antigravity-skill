---
name: app-full-lifecycle
description: Xây dựng ứng dụng web/mobile end-to-end từ ý tưởng thô đến sản phẩm deploy — điều phối 7 phase (Idea → Optimize → Confirm → Design Proposal → Build → Audit/Score → Deploy). Kích hoạt khi người dùng nói "tạo app từ đầu đến cuối", "xây web trọn gói", "build app full", "làm sản phẩm hoàn chỉnh", "app lifecycle", "từ ý tưởng đến deploy", "làm website chuyên nghiệp", "tôi có ý tưởng app", "muốn tạo một ứng dụng", hoặc bất kỳ khi nào người dùng đưa ra ý tưởng app/web thô cần được refine, thiết kế, build và chấm điểm chất lượng trước khi giao. Tự động điều phối các skill con: app-builder (Phase 5), ui-ux-pro-max + design-system + frontend-design (Phase 4), 10k-checklist (Phase 6), run + deploy-checklist (Phase 7). Luôn dừng để hỏi xác nhận sau mỗi phase quan trọng — không tự ý nhảy phase.
version: "1.0.0"
last_updated: "2026-07-15"
license: MIT
---

# App Full Lifecycle — Từ Ý Tưởng Đến Deploy

Skill điều phối trọn vòng đời sản phẩm app/web: nhận ý tưởng thô của người dùng, sharpen nó, hỏi các xác nhận cần thiết, đề xuất design (font/color/style), build MVP, chấm điểm rubric, đề xuất fix và deploy.

**Nguyên tắc cốt lõi:** *Không phase nào được nhảy qua. Không quyết định thay user ở checkpoint. Mọi audit phải có evidence (không tự bịa số điểm).*

---

## Bản đồ 8 phase

```
PHASE 0 — PREFLIGHT          → Check skill dependency, load project thresholds
PHASE 1 — IDEA CAPTURE       → Ghi lại ý tưởng thô, không phán xét
PHASE 2 — IDEA OPTIMIZATION  → Challenge, sharpen, propose alternatives
PHASE 3 — CONFIRMATION Q&A   → Hỏi các thông tin thiếu + kiến trúc (có/không backend)
PHASE 4 — DESIGN PROPOSAL    → Đề xuất style/font/color/layout (user pick)
PHASE 5 — BUILD              → Code MVP theo scope đã chốt
PHASE 6 — AUDIT & SCORE      → Chấm rubric 5 chiều + 10K checklist (evidence-required)
PHASE 7 — FIX & DEPLOY       → Fix critical → user confirm điểm còn lại → ship
```

**Checkpoint bắt buộc dừng** (không tự nhảy phase): sau Phase 2, sau Phase 3, sau Phase 4, sau Phase 6, trước Phase 7.

---

## PHASE 0 — PREFLIGHT

Chạy 1 lần đầu session để tránh giữa chừng phát hiện thiếu tool.

### 0.1 Skill dependency check

Skill này delegate cho các skill/MCP khác. Kiểm tra tồn tại và ghi vào working memory:

| Dependency | Vai trò | Fallback nếu thiếu |
|---|---|---|
| `ui-ux-pro-max` | Phase 4 design proposal | Dùng heuristic tối giản: font từ Google Fonts pairing phổ biến, palette từ radix-ui/tailwind — **báo user rằng đề xuất kém căn cứ** |
| `design-system` | Phase 4 token architecture | Manual: viết CSS variables 3-layer (primitive/semantic/component) inline trong code |
| `frontend-design` | Phase 4 aesthetic direction | Chấp nhận WEAK rating ở tiêu chí "point of view" nếu user không có brand direction |
| `app-builder` | Phase 5 scaffold | Dùng `Write` tool tạo từng file thủ công theo pattern chuẩn (React/Next.js/vanilla) |
| `10k-checklist` | Phase 6 craft audit | Bỏ 8-criteria craft pass, chỉ chạy rubric 5 chiều. **Báo user rằng thiếu 1 tầng audit** |
| `run` | Phase 5-6 launch dev server | Dùng `Bash` chạy `npm run dev` / `python -m http.server` trực tiếp |
| `deploy-checklist` | Phase 7 pre-ship | Dùng inline checklist trong SKILL.md, ghi rõ đã bỏ qua step nào |
| `mcp__Claude_Preview__*` | Phase 6 evidence collection | Nếu thiếu preview MCP: yêu cầu user tự screenshot & inspect, hoặc dùng `mcp__claude-in-chrome__*` nếu có. **Nếu cả hai đều thiếu: không được chấm điểm — chỉ định tính** |

Verify bằng cách: check file tồn tại (`~/.claude/skills/<name>/SKILL.md`) và MCP tool namespace (`mcp__Claude_Preview__preview_start` v.v. có trong danh sách tool không).

Nếu thiếu ≥3 dependency: **báo user và hỏi có muốn tiếp không** thay vì âm thầm degrade.

### 0.2 Load / khởi tạo project thresholds

Ngưỡng số cụ thể (misclick target, saliency, contrast beyond AA…) là **project-specific**, không hardcode. Đọc [references/project-thresholds.md](references/project-thresholds.md) để hiểu cấu trúc. Ở Phase 3, sẽ hỏi user override nếu cần.

### 0.3 Ghi chú kiến trúc: backend/database KHÔNG bắt buộc

Skill này **không** mặc định app phải có backend + DB. Sẽ hỏi rõ ở Phase 3.5 dựa trên trigger sau đây — nếu tất cả trigger đều "không", đề xuất kiến trúc client-only:

- Cần multi-device sync (login máy này → thấy data máy khác)?
- Cần multi-user shared state (chat, collab document)?
- Có secret/API key không được lộ ở client (Stripe secret, database credential)?
- Dữ liệu nhạy cảm cần server validate trước khi lưu (financial, health, PII)?
- Tính toán nặng vượt sức browser (ML inference, video encode)?

Nếu tất cả = "không" → đề xuất một trong: static site (Astro/Next SSG/plain HTML), client-side SPA + localStorage/IndexedDB, hoặc PWA offline-first. Không tự thêm Supabase/Postgres.

---

## PHASE 1 — IDEA CAPTURE

**Mục tiêu:** Ghi lại đúng ý tưởng của user, không tự thêm/bớt.

**Hành động:**
1. Hỏi user mô tả ý tưởng bằng 3-5 câu tự do (không format cứng).
2. Tóm tắt lại bằng 1 dòng: `[Loại app] cho [Ai] để [Giải quyết vấn đề gì]`.
3. Show lại tóm tắt → hỏi *"Đúng ý bạn chưa?"*.

**Không làm ở phase này:** Không đề xuất tech stack. Không hỏi feature chi tiết. Không tự sharpen. Chỉ *ghi nhận*.

---

## PHASE 2 — IDEA OPTIMIZATION

**Mục tiêu:** Biến ý tưởng thô thành ý tưởng có point-of-view rõ ràng.

**4 bước bắt buộc:**

### 2.1 Challenge (thách thức)
Hỏi thẳng 3 câu (không né):
- *"Nếu user không có app này, họ đang giải quyết vấn đề bằng cách nào?"* (nếu answer = "không có cách nào" → nghi ngờ có thị trường thật không)
- *"Có 3 sản phẩm nào đang làm điều tương tự? Vì sao user chọn của bạn?"* (nếu answer = "chưa có" → red flag về thị trường; nếu "nhiều lắm" → cần USP)
- *"Điều gì làm app này khác biệt trong 1 câu?"* (nếu user không trả được → chưa có point of view)

### 2.2 Sharpen (mài sắc)
Chốt lại 3 thứ:
- **1 câu positioning**: `App X là [thứ gì đó cụ thể] cho [ai đó cụ thể] khác biệt vì [1 lý do rõ ràng]`.
- **1 luồng nghiệp vụ core**: user vào app → làm gì đầu tiên → kết quả là gì (max 5 bước, viết bằng động từ).
- **1 metric thành công**: "Nếu 100 người dùng app 1 tuần, tôi muốn thấy [X]".

### 2.3 Alternatives (đề xuất phương án)
Đưa ra **2-3 hướng tiếp cận khác nhau** cho cùng ý tưởng (không phải "phương án A tốt hơn B" — cho user chọn góc nhìn):
- Ví dụ: Ý tưởng "app học từ vựng" → (a) Spaced-repetition khô như Anki, (b) Game-hóa như Duolingo, (c) Đọc-truyện-học-từ như LingQ.
- Mỗi hướng: 1 câu mô tả + 1 điểm mạnh + 1 điểm yếu.

### 2.4 Checkpoint — DỪNG
Trình bày với user:
- 1 câu positioning đã sharpen
- 3 phương án tiếp cận
- Câu hỏi: *"Bạn chọn hướng nào, hay muốn tôi phối hợp?"*

**Không tự chọn hộ user.** Chỉ tiếp Phase 3 sau khi user reply.

---

## PHASE 3 — CONFIRMATION Q&A

**Mục tiêu:** Thu thập ĐỦ thông tin để design + build, không hỏi lan man.

Dùng question bank ở [references/questions-bank.md](references/questions-bank.md). Chia làm **3 lô**, mỗi lô max 5 câu, để user không mệt:

**Lô 1 — Users & Context**
- Ai là user chính (persona 1-2 câu)?
- Họ dùng app ở đâu (mobile vội / desktop rảnh / cả hai)?
- Trình độ tech (non-tech / mixed / power user)?
- Bao nhiêu user dự kiến trong 3 tháng đầu?
- Ngôn ngữ chính (VN / EN / bilingual)?

**Lô 2 — Scope MVP**
- Liệt kê **3-5 tính năng phải có** (must-have).
- Tính năng nào có thể để v2 (nice-to-have)?
- Có cần auth/login không? Nếu có → social hay email?
- Có cần lưu data lâu dài không? (session-only vs database)
- Có tích hợp gì bên ngoài không? (payment, email, AI, map…)

**Lô 3 — Constraints & Deploy**
- Deadline mong muốn?
- Budget hosting (free tier hay OK trả tiền)?
- Kỹ thuật ưu tiên gì (đơn giản chạy local? Cloud full-stack? PWA?)?
- Brand có sẵn (logo, màu, font) hay tự design từ đầu?
- Cần accessibility mức nào (WCAG AA là bắt buộc mặc định — hỏi nếu cần AAA)?

**Lô 3.5 — Kiến trúc backend (bắt buộc — không mặc định "có")**
Chạy 5 câu trigger ở Phase 0.3. Rồi hỏi user chốt 1 trong 3 kiến trúc:
- **Static / Client-only**: HTML/JS + localStorage. Deploy = 1 file hoặc GitHub Pages.
- **Client-side SPA + BaaS**: SPA + Supabase/Firebase (auth + DB managed). Không tự viết backend.
- **Full-stack**: Next.js API routes hoặc Python FastAPI + DB. Chỉ chọn khi có ≥1 trigger backend.

**Lô 4 — Project thresholds (optional override)**
Đọc [references/project-thresholds.md](references/project-thresholds.md). Hỏi user nếu muốn override default:
- Contrast target (default AA 4.5:1 — chỉ hỏi nếu app tài chính/y tế/gov cần AAA 7:1).
- Misclick tolerance target (default: không hardcode — nếu app có payment thì thường đặt <1%, còn lại tùy user chấp nhận).
- LCP/CLS budget (default lấy từ web.dev/vitals — user có thể nới cho internal tool).

**Checkpoint — DỪNG**: Show lại **Scope Document** dạng bảng gọn:

| Mục | Giá trị |
|---|---|
| Positioning | ... |
| Users | ... |
| Must-have (MVP) | 1, 2, 3 |
| Out of scope (v2) | ... |
| Auth | ... / Không |
| Data | ... |
| Deploy target | ... |
| Deadline | ... |

Hỏi: *"Scope này OK chưa? Có gì thêm/bớt?"* → chỉ tiếp Phase 4 sau khi user OK.

---

## PHASE 4 — DESIGN PROPOSAL

**Mục tiêu:** Đề xuất **hệ thống design cụ thể** (không mô tả chung chung).

**Nguồn dữ liệu:** phải dùng skill `ui-ux-pro-max` để lấy đề xuất có cơ sở. Không được tự chế font/color từ trí nhớ.

### 4.1 Chạy design system generator
```bash
python "${HOME}/.claude/skills/ui-ux-pro-max/scripts/search.py" "<product-type>" --design-system --stack <detected-stack>
```
Nếu không có stack, hỏi user hoặc default `html-tailwind`.

### 4.2 Trình bày **2 phương án design** (không 1, không 3)

Mỗi phương án gồm:
- **Point of view** (1 phrase): ví dụ *"Swiss editorial cho fintech nghiêm túc"* hoặc *"Playful gradient cho Gen-Z learning app"*.
- **Font pairing**: `Display: [tên] / Body: [tên]` — không được là Inter/Roboto/system default (theo tiêu chuẩn 10K).
- **Color system**: 2 neutrals + 1 hero accent + max 1 supporting (theo restraint principle).
- **Layout signature**: 1 chi tiết đáng nhớ (ví dụ *"sticky bottom CTA có swipe-to-confirm"*, *"hero split 60/40 với typography lớn"*).
- **Motion**: có/không, và nếu có thì mức độ (subtle 150–300ms / dramatic).
- **Mini preview**: 1 HTML mockup render bằng `show_widget` (dùng skill `visualize`) — user thấy trước khi chốt.

### 4.3 Ràng buộc design

Tách rõ 2 nhóm — **không dùng heuristic để reject phương án như thể vi phạm chuẩn**:

**A. Mandatory (từ chuẩn chính thức — không thương lượng):**
- Touch target ≥ 44×44pt iOS (Apple HIG) / 48×48dp Android (Material 3).
- Contrast body text ≥ 4.5:1 (WCAG 2.2 AA — W3C).
- Focus indicator visible cho keyboard nav (WCAG 2.4.7).
- Respect `prefers-reduced-motion` (WCAG 2.3.3).

**B. Heuristic (project-adjustable — được phép có exception có justify):**
- "1 Primary CTA/màn hình" — convention Material 3, không phải luật. Dashboard đa mục tiêu, wizard step, split-action có thể có 2 primary equal-weight nếu có lý do rõ.
- Font pairing tránh Inter/Roboto/system default — heuristic 10K craft, không phải fail. Nếu user brand có sẵn Inter thì respect.
- Label `[Động từ] + [Đối tượng]` — best practice NNG, nhưng "OK" trong dialog xác nhận đọc-only là chấp nhận được.

Đọc [references/design-constraints.md](references/design-constraints.md) để thấy phân loại đầy đủ + link nguồn.

### 4.4 Checkpoint — DỪNG
Show 2 preview + so sánh trade-off. Hỏi: *"Chọn phương án nào? Có muốn tôi mix element từ cả 2 không?"* → chờ user.

---

## PHASE 5 — BUILD

**Mục tiêu:** Code MVP hoạt động thực sự, không stub, không mock UI.

### 5.1 Delegate cho app-builder
Skill `app-builder` xử lý Phase 3-4-5 của nó (Scaffold, Build, Test) — không lặp lại logic. Chuyển sang:
- Đọc `hocvienai-new-skills/skills/app-builder/SKILL.md` Phase 3-5.
- Truyền scope đã chốt ở Phase 3 + design đã chốt ở Phase 4 làm input.

### 5.2 Nguyên tắc build (bổ sung từ tài liệu UX)
- **Loading state chặn double-submit**: mọi nút submit phải disable + spinner khi đang gọi API.
- **Empty state, error state, loading state**: 3 state này không được thiếu — đọc [references/pre-release-checklist.md](references/pre-release-checklist.md).
- **Optimistic UI**: được phép cho Like/Save/Comment. **KHÔNG** dùng cho Payment/Transfer/Delete-critical-data (rủi ro sai lệch state).
- **Snackbar (Undo)** thay Confirmation Dialog cho các thao tác xóa thông thường; giữ Dialog cho dữ liệu sống-còn.
- **Không disable button từ đầu** để "chống lỗi". Cho bấm → show inline validation ở field sai.

### 5.3 Iterative delivery
Không code hết một lần rồi show. Cứ mỗi feature xong → chạy dev server (dùng skill `run`) → screenshot → confirm với user trước khi sang feature tiếp.

---

## PHASE 6 — AUDIT & SCORE

**Mục tiêu:** Chấm điểm khách quan, có evidence. Không được tự bịa số.

### 6.1 Chuẩn bị
1. Chạy app thật (dev server hoặc deployed). *Không audit từ source code — design lives in pixels.*
2. Dùng `preview_inspect` cho contrast, font, spacing. Dùng `preview_resize` cho mobile 375×812.

### 6.2 Chạy 2 rubric song song

**Rubric A — 5 chiều UX (từ tài liệu UX Research, section 5.3):**
| Chiều | Trọng số | Điểm 1-10 |
|---|---|---|
| Usability / Discoverability | 20% | ? |
| Correctness & Error Prevention | 25% | ? |
| Performance & Accessibility | 15% | ? |
| User Trust (không dark pattern) | 20% | ? |
| Cross-platform Fit | 20% | ? |

Xem chi tiết tiêu chí và cách chấm ở [references/audit-rubric.md](references/audit-rubric.md).

**Rubric B — 10K Checklist (design craft):**
Chạy skill `10k-checklist` để có 8-criteria pass. Xem hướng dẫn ở `~/.claude/skills/10k-checklist/SKILL.md`.

### 6.3 Anti-pattern scan
Đối chiếu với 12 misconceptions ở [references/anti-patterns.md](references/anti-patterns.md). Bất kỳ hit nào → note vào báo cáo.

### 6.4 Pre-release checklist
Chạy toàn bộ [references/pre-release-checklist.md](references/pre-release-checklist.md) (9 mục bắt buộc). Bất kỳ mục nào FAIL → không được sang Phase 7.

### 6.5 Báo cáo audit

**Yêu cầu evidence — cứng:** Mỗi điểm 1-10 phải kèm ≥1 evidence artifact cụ thể. Không có evidence → điểm đó ghi `N/E` (No Evidence) chứ không được đoán. Format evidence hợp lệ:
- Screenshot file path (từ `preview_screenshot`) + mô tả vùng
- CSS selector + computed value (từ `preview_inspect`) — VD: `.btn-primary { color: #fff; background: #2563EB; contrast: 8.2:1 }`
- Log/network trace (từ `preview_console_logs` / `preview_network`)
- Quote nguyên văn error message hoặc UI copy

Nếu >30% chiều bị `N/E` → audit chưa hoàn thành, chưa được sang Phase 7.

Format cố định:

```
## Audit Report

### Điểm tổng: X.X/10 (weighted) — evidence coverage: X/5 chiều có evidence
### 10K Checklist: X PASS / X WEAK / X FAIL / X N/E trên 8

### Top 3 điểm mạnh (kèm evidence)
1. [Statement] — Evidence: [path/selector/quote]
2. ...

### Top N điểm cần fix — phân loại
**CRITICAL BLOCKER** (không được ship, không được waive by user in-session):
- [Vấn đề] — [Evidence] — [Fix đề xuất]

**STANDARD BLOCKER** (không nên ship, user có thể waive with recorded justification):
- ...

**RECOMMENDED** (nice-to-fix):
- ...
```

### 6.6 Critical blocker — không được "accept as-is"

Các nhóm sau **không được user waive** trong session này. Phải fix hoặc escalate ra ngoài skill (yêu cầu security review, hoặc user quyết định bằng văn bản riêng):

- **Security**: XSS trong user input, SQL injection, secret key hardcode trong client bundle, missing CSRF trên state-changing API, auth bypass.
- **Data loss / integrity**: Không có confirm cho delete-critical, không có backup path cho destructive migration, race condition gây double-charge/duplicate order, không handle partial failure ở multi-step transaction.
- **PII / compliance**: Log/analytics chứa email/phone/SSN không mask, không có consent cho cookie tracking (nếu target EU), gửi PII qua GET query param.
- **Accessibility hard-fail**: Nội dung quan trọng chỉ truyền qua màu (colorblind fail), video autoplay không có captions cho nội dung có lời, contrast fail cho error/warning text.

Với các items khác (usability weak, motion nhàm, font chưa premium…) → user có quyền chọn accept as-is, nhưng phải record vào Scope Document dạng `[ACCEPTED-RISK: <lý do>]`.

### 6.7 Checkpoint — DỪNG
Show báo cáo. Hỏi user:
1. Critical blocker — tự fix ngay (không cần hỏi).
2. Standard blocker — user chọn fix hết / fix top N / defer to v2 (mỗi defer phải justify).
3. Recommended — user chọn cái nào ship kèm.

---

## PHASE 7 — FIX & DEPLOY

### 7.1 Fix theo priority đã chốt
- Fix từng cái, mỗi cái xong → re-run inspect để verify → mark done.
- Không fix song song nhiều cái nếu chưa test cái trước.

### 7.2 Re-audit ngắn
Sau khi fix, chạy lại rubric cho những chiều đã đụng vào. Điểm phải tăng — nếu tăng không đáng kể, giải thích với user vì sao.

### 7.3 Deploy checklist
Delegate cho skill `deploy-checklist`. Bổ sung 3 mục đặc thù UX:
- [ ] Chạy Lighthouse (hoặc equivalent) — Accessibility score ≥ 90.
- [ ] Test luồng chính trên mobile thật (không chỉ DevTools).
- [ ] Analytics events đã gắn cho mọi Primary CTA (để đo Misclick rate sau này).

### 7.4 Ship
- Chọn deploy target theo Phase 3 (Vercel/Netlify/Railway/local).
- Sau khi ship, gửi user:
  - URL production
  - README (tự sinh)
  - 1 câu "Điều cần theo dõi trong 7 ngày đầu" (guardrail metrics: bounce rate, error rate, support tickets).

---

## Nguyên tắc điều phối skill

- **KHÔNG** tự implement lại logic đã có trong skill khác. Luôn delegate:
  - Design details → `ui-ux-pro-max`, `design-system`, `frontend-design`
  - Code MVP → `app-builder`
  - Audit craft → `10k-checklist`
  - Run app → `run`
  - Deploy → `deploy-checklist`
- **LUÔN** verify skill tồn tại trước khi call (một số skill có thể chưa cài).
- **CẤM** skip checkpoint. Nếu user gõ "cứ làm đi, tin bạn" → vẫn phải trình bày kết quả từng phase, chỉ được rút gọn Q&A chứ không được nhảy phase.

## Edge cases

**User đưa ý tưởng quá mơ hồ ("tôi muốn 1 app hay hay")**: Không tiếp. Quay lại Phase 1, hỏi cụ thể "cho ai, giải quyết vấn đề gì".

**User muốn nhảy thẳng vào code**: Nhắc rằng bỏ Phase 2-3 sẽ tăng rework 3-5×. Nếu vẫn cương quyết, ghi chú vào Scope Document dạng `[SKIPPED BY USER]` và tiếp.

**User đã có design sẵn**: Bỏ Phase 4, sang thẳng Phase 5. Nhưng Phase 6 vẫn audit design đó — không được vì user tự làm mà miễn score.

**App quá lớn cho 1 session**: Chia MVP thành phase con (v0.1, v0.2). Chỉ deploy v0.1 sau khi qua đủ 7 phase.

**User không biết technical**: Ở Phase 4-5, thay vì hỏi "React hay Vue?", đề xuất mặc định + giải thích 1 dòng "chọn cái này vì bạn muốn deploy nhanh, ít maintain".

---

## Output cuối cùng

Khi hoàn thành Phase 7, giao cho user 5 thứ:
1. **URL production** (hoặc file zip nếu local)
2. **Scope Document** (từ Phase 3, đã confirmed)
3. **Design System snapshot** (từ Phase 4: font, color, spacing tokens)
4. **Audit Report** (từ Phase 6 — cả trước fix và sau fix)
5. **Post-launch watch list** (3-5 metric guardrail cần theo dõi tuần đầu)
