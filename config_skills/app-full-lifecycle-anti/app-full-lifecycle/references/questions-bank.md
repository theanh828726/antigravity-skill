# Question Bank — Phase 3 Confirmation

Danh sách câu hỏi đầy đủ theo lô. Chỉ hỏi cái nào chưa rõ từ conversation trước. **Đừng hỏi cùng lúc quá 5 câu** — user mệt.

## Lô 1 — Users & Context (bắt buộc)

1. **User chính là ai?** — mô tả 1-2 câu (tuổi, nghề, tech-savvy hay không).
2. **Dùng ở đâu?** — mobile trên đường / desktop tại bàn / cả hai. Ảnh hưởng thumb-reach zone.
3. **Trình độ tech?** — non-tech (grandma-friendly) / mixed / power user (cần shortcut).
4. **Quy mô 3 tháng đầu?** — <100 / 100-1000 / >1000. Ảnh hưởng chọn DB và hosting tier.
5. **Ngôn ngữ chính?** — VN / EN / bilingual. Nút "Đăng ký ngay" dài hơn "Sign up" 2-3 lần → ảnh hưởng layout.

## Lô 2 — Scope MVP (bắt buộc)

6. **3-5 tính năng phải có?** — không quá 5. Nếu user liệt kê >5, force ranking.
7. **Nice-to-have (v2)?** — cái nào có thể đợi phiên bản sau.
8. **Auth?** — cần login không. Nếu có: email/password / social (Google, GitHub) / magic link.
9. **Data persistence?** — session-only (mất khi refresh) / localStorage / database thật.
10. **Tích hợp bên ngoài?** — payment (Stripe/VNPay) / email (Resend) / AI (Claude/OpenAI) / map / analytics.

## Lô 3 — Constraints & Deploy (bắt buộc)

11. **Deadline?** — 1 ngày / 1 tuần / 1 tháng. Ảnh hưởng cắt scope.
12. **Hosting budget?** — free tier only / $5-20/tháng OK / enterprise.
13. **Preference kỹ thuật?** — đơn giản chạy local file / cloud full-stack / PWA cài được / native.
14. **Brand có sẵn?** — có logo/font/color hay tự design (→ Phase 4 mở rộng).
15. **Accessibility?** — mặc định WCAG AA. Hỏi nếu cần AAA (dành cho gov/health/finance).

## Lô 4 — Optional (chỉ hỏi nếu relevant)

16. **Cần offline?** → PWA + service worker.
17. **Real-time (chat, live update)?** → WebSocket / SSE.
18. **Multi-tenant?** → cần schema riêng, row-level security.
19. **Compliance (GDPR, HIPAA)?** → constraints về data storage, cookie consent.
20. **SEO cần thiết?** → Next.js SSR thay vì SPA thuần.

## Anti-patterns khi hỏi

- ❌ Hỏi "bạn muốn dùng React hay Vue?" khi user non-tech → tự đề xuất.
- ❌ Hỏi "database schema thế nào?" ở Phase 3 → để Phase 5.
- ❌ Hỏi "bạn có prefer dark mode không?" trước khi có design direction.
- ❌ Bắn 15 câu 1 lần → user sẽ trả lời qua loa hoặc bỏ cuộc.
