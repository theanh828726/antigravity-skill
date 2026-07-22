# 🚀 TimeTrack Pro — App Blueprint (Ví Dụ Mẫu)

> **Tagline**: Ứng dụng theo dõi thời gian thông minh cho freelancer — biến giờ làm việc thành hoá đơn chuyên nghiệp chỉ với 1 click.

---

## 📋 1. Product Overview

### Problem Statement
Freelancer thường mất 30–60 phút/tuần để tổng hợp thời gian làm việc từ nhiều nguồn (sticky notes, spreadsheet, memory) trước khi gửi hoá đơn. Kết quả thường sai sót và thiếu chuyên nghiệp, gây mất uy tín với client.

### Solution
TimeTrack Pro là time tracker tập trung vào freelancer: bắt đầu bấm giờ 1 click, gán vào project, và tự động tổng hợp thành hoá đơn PDF chuyên nghiệp. Mọi thứ trong một tool duy nhất.

### Vision
Trở thành công cụ quản lý tài chính đơn giản nhất cho cộng đồng freelancer Việt Nam và Đông Nam Á — từ time tracking → invoicing → báo cáo thu nhập.

---

## 👥 2. Target Users & Personas

### Primary Persona
- **Tên**: "Nam — Freelance Developer"
- **Độ tuổi**: 24–35 tuổi
- **Mục tiêu**: Theo dõi giờ làm chính xác, gửi hoá đơn nhanh, được thanh toán đúng hạn
- **Pain Points**: Quên ghi giờ, Excel lộn xộn, tạo invoice mất thời gian, client hỏi báo cáo không có
- **Cách dùng app**: Bật timer khi bắt đầu làm, tắt khi xong, cuối tháng xuất invoice

### Secondary Persona
- **Tên**: "Linh — Freelance Designer"
- **Độ tuổi**: 22–30 tuổi
- **Mục tiêu**: Quản lý nhiều client cùng lúc, biết mình đang earn bao nhiêu/giờ
- **Pain Points**: Không biết project nào profitable, client hay delay thanh toán
- **Cách dùng app**: Xem dashboard thu nhập theo tuần, reminder invoice quá hạn

---

## 🗺️ 3. Core User Journey (MVP)

1. **Onboarding**: Đăng ký → Tạo project đầu tiên → Gán hourly rate
2. **Core Action (Aha Moment)**: Bấm "Start Timer" → Làm việc → Bấm "Stop" → Xem giờ được log tự động
3. **Value Delivery**: Cuối tháng → Click "Generate Invoice" → PDF chuyên nghiệp sẵn sàng gửi client
4. **Retention Hook**: Dashboard hiển thị "Bạn đã earn $X tuần này" — gamification thu nhập

### Key Screens Flow:
```
Landing → Register → Dashboard → [Start Timer] → Timer Running → Stop → Log Entry
                                      ↑                                      |
                                      └──── Projects ←── Invoice ←───────────┘
```

---

## ⚡ 4. MVP Feature Set

| # | Feature | Mô tả | Priority |
|---|---------|--------|----------|
| 1 | **Timer** | Start/Stop/Pause timer với 1 click, gán vào project | 🔴 Must Have |
| 2 | **Project Manager** | Tạo, sửa, archive projects. Gán client & hourly rate | 🔴 Must Have |
| 3 | **Time Log** | Xem/sửa/xoá entries theo ngày. Manual entry nếu quên bấm | 🔴 Must Have |
| 4 | **Invoice Generator** | Tổng hợp time entries → PDF invoice gửi client | 🔴 Must Have |
| 5 | **Dashboard** | Tổng giờ tuần/tháng, earnings, project breakdown | 🟡 Should Have |
| 6 | **Client Manager** | Lưu thông tin client để điền invoice nhanh | 🟡 Should Have |
| 7 | **Reminders** | Nhắc bấm timer, nhắc invoice quá hạn | 🟢 Nice to Have |

### ❌ Out of Scope (v1)
- Tích hợp payment gateway (Stripe, PayPal)
- Mobile native app (iOS/Android)
- Team collaboration / multi-user
- Expense tracking
- Accounting integrations (QuickBooks, Xero)

---

## 🎨 5. Design System

### Visual Identity
- **Style**: Minimal SaaS — dark mode, clean, professional nhưng không khô khan
- **Personality**: Productive · Trustworthy · Calm

### Color Palette
| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary | Indigo | #6366F1 | Buttons, CTAs, active states |
| Primary Dark | Deep Indigo | #4F46E5 | Hover states |
| Accent | Emerald | #10B981 | Running timer, success, earnings |
| Background | Near Black | #0F0F13 | Page background |
| Surface | Dark Gray | #1A1A24 | Cards, panels |
| Surface Raised | Medium Gray | #252532 | Inputs, dropdowns |
| Border | Subtle | #2E2E3E | Dividers, borders |
| Text Primary | Off White | #F1F0FF | Headings, body |
| Text Muted | Gray | #8B8BAD | Captions, placeholders |
| Warning | Amber | #F59E0B | Invoices due soon |
| Error | Red | #EF4444 | Errors, overdue |

### Typography
- **Heading Font**: Outfit (Google Fonts) — modern, geometric
- **Body Font**: Inter (Google Fonts) — readable, neutral
- **Mono Font**: JetBrains Mono — timer display, time values
- **Scale**: 48px / 36px / 28px / 22px / 16px / 14px / 12px

### Spacing & Radius
- **Spacing**: 8pt grid (4 / 8 / 12 / 16 / 24 / 32 / 48 / 64px)
- **Radius**: Tags(6px) / Inputs+Cards(12px) / Modals(16px) / Avatars(9999px)

---

## 🏗️ 6. Screen Architecture

### Screen List
| Screen | Route | Mô tả | Auth |
|--------|-------|--------|------|
| Landing | `/` | Hero, features, pricing, CTA | ❌ |
| Login/Register | `/auth` | Email/Password + Google | ❌ |
| Dashboard | `/dashboard` | Overview: giờ, earnings, active timer | ✅ |
| Projects | `/projects` | List projects + tạo mới | ✅ |
| Project Detail | `/projects/:id` | Time entries của project, stats | ✅ |
| Time Log | `/log` | All entries, filter theo ngày/project | ✅ |
| Invoices | `/invoices` | List invoices, tạo mới, download PDF | ✅ |
| Clients | `/clients` | Manage client info | ✅ |
| Settings | `/settings` | Profile, billing rate, preferences | ✅ |

### Component Inventory
- **Global**: Navbar (top), Sidebar (left, collapsible), ToastNotification
- **Timer**: TimerWidget (sticky top), ProjectSelector, TimerControls
- **Data**: TimeEntryCard, ProjectCard, InvoiceRow, ClientCard
- **Forms**: NewProjectModal, EditEntryModal, InvoiceBuilderForm
- **Empty States**: NoProjects, NoEntries, NoInvoices (với CTAs)

---

## ⚙️ 7. Technical Architecture

### Frontend Stack
- **Framework**: React 18 + TypeScript + Vite
- **Styling**: Vanilla CSS với CSS Custom Properties (design tokens)
- **State**: Zustand (timer state, global UI)
- **Routing**: React Router v6
- **PDF**: react-pdf / jsPDF cho invoice export

### Backend & Data
- **Backend**: Supabase (PostgreSQL + Auth + Storage)
- **Database Tables**: users, projects, clients, time_entries, invoices
- **Auth**: Supabase Auth (Email + Google OAuth)
- **Storage**: Supabase Storage (invoice PDF, logo upload)
- **Real-time**: Supabase Realtime (timer sync across tabs)

### Key APIs
- Không cần external API cho MVP

---

## 📝 8. AI Coding Prompts (Ready-to-Use)

### Prompt 1: Foundation — Layout & Design System

```
Create a dark-mode time tracking web app called "TimeTrack Pro" for freelancers.

Tagline: "Track time. Bill clients. Get paid."

Design System:
- Primary: #6366F1 (Indigo)
- Accent: #10B981 (Emerald) — for active timer
- Background: #0F0F13
- Surface: #1A1A24 (cards/panels)
- Border: #2E2E3E
- Text: #F1F0FF (primary), #8B8BAD (muted)
- Fonts: 'Outfit' for headings, 'Inter' for body, 'JetBrains Mono' for timer display (all from Google Fonts)
- Border radius: 12px for cards, 6px for badges

Build the app shell with:
1. Left sidebar (240px) with logo + nav links: Dashboard, Projects, Time Log, Invoices, Clients, Settings
2. Top bar with: current date, active timer widget (shows "00:00:00" in JetBrains Mono), Start button
3. Main content area with placeholder "Dashboard" heading

Stack: React + TypeScript + Vite. Mobile responsive — sidebar collapses on mobile.
Use mock data — no backend yet.
Ask me any questions if you need clarification on the layout.
```

### Prompt 2: Timer Feature

```
Add the core Timer feature to TimeTrack Pro:

Requirement: User clicks "Start Timer" → picks a project → timer counts up → clicks "Stop" → entry is saved.

UI:
- Timer widget in top bar: shows elapsed time "HH:MM:SS" in JetBrains Mono font, size 20px
- When active: emerald (#10B981) pulsing dot indicator
- "Start" button → opens project selector dropdown → timer starts
- While running: shows "Stop" and "Pause" buttons, shows project name
- After stopping: shows "Great work! X hours logged" toast notification

State (Zustand):
- isRunning: boolean
- startTime: Date | null
- elapsedSeconds: number
- selectedProjectId: string | null
- entries: TimeEntry[] (mock data)

Mock projects: ["Website Redesign — TechCorp", "Mobile App — StartupXYZ", "Logo Design — CafeABC"]

Behaviors:
- Timer persists in localStorage (if user refreshes, timer continues)
- Prevent starting timer if no project selected (show inline error)
- Entry appears in Time Log immediately after stopping

Do NOT modify: sidebar, routing, or any existing pages.
```

### Prompt 3: Dashboard

```
Build the Dashboard page (/dashboard) for TimeTrack Pro:

Layout (top to bottom):
1. Stats Row (4 cards): "Today" (hours), "This Week" (hours + earnings), "This Month" (earnings), "Pending Invoices" ($)
2. Active Projects section: cards showing each project with progress bar (hours used vs estimated), hourly rate, total earned
3. Recent Time Entries: last 5 entries with project name, date, duration, edit button

Design:
- Stats cards: Surface (#1A1A24) background, Primary (#6366F1) accent for numbers
- Earnings in Emerald (#10B981)
- Overdue invoices in Red (#EF4444)

Use this mock data:
- Today: 3h 45m
- This Week: 18h 20m | $1,648
- This Month: $4,230
- Pending: $850

Empty state: If no projects, show "Create your first project" CTA button.

Do NOT modify: sidebar, timer widget, or other pages.
```

---

## 📊 9. Success Metrics (KPIs)

| Metric | Mô tả | Target Month 1 |
|--------|--------|----------------|
| Signups | Người dùng đăng ký mới | 200 users |
| Timer Activations | Số lần bấm Start Timer | ≥ 5 lần/user/tuần |
| Invoice Generated | Số hoá đơn được tạo | ≥ 1/user/tháng |
| D7 Retention | Người dùng quay lại sau 7 ngày | ≥ 30% |
| Time to First Value | Từ đăng ký → log entry đầu tiên | < 3 phút |

---

## 🗓️ 10. Development Roadmap

### Phase 1 — MVP (Week 1–2)
- [x] Design system & app shell
- [ ] Timer feature (Start/Stop/Pause)
- [ ] Project Manager (CRUD)
- [ ] Time Log (view, edit, manual entry)
- [ ] Supabase auth integration

### Phase 2 — Core Value (Week 3–4)
- [ ] Invoice Generator (PDF export)
- [ ] Client Manager
- [ ] Dashboard với real data
- [ ] Mobile responsive polish

### Phase 3 — Growth (Month 2)
- [ ] Email reminders (invoice due, idle timer)
- [ ] Google OAuth
- [ ] Reports & analytics
- [ ] Landing page & SEO

---

## 💡 Build Tips

1. Bắt đầu với **Prompt 1** → verify layout đẹp trước
2. Tiếp theo **Prompt 2** (Timer) — đây là core feature
3. Sau mỗi feature: test kỹ trước khi prompt tiếp
4. Nếu muốn sửa UI nhỏ: dùng visual editor thay vì prompt
5. Khi tích hợp Supabase: setup auth trước, database tables sau
