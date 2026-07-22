---
name: app-blueprint-designer
description: >-
  Chuyên gia tạo bản thiết kế ứng dụng (App Blueprint) hoàn chỉnh từ yêu cầu
  đơn giản của người dùng. Kích hoạt khi người dùng muốn tạo/thiết kế một ứng
  dụng, website, hoặc sản phẩm số và cung cấp mô tả ngắn gọn về ý tưởng của
  họ. Output là một bản PRD/blueprint chi tiết sẵn sàng để phát triển.
  Trigger keywords: thiết kế app, tạo app, blueprint ứng dụng, lên kế hoạch
  app, design app, app design, build app, create app, app blueprint, PRD.
---

# App Blueprint Designer 🎨

Chuyên gia biến ý tưởng đơn giản thành bản thiết kế ứng dụng hoàn chỉnh, chi tiết, production-ready — theo phương pháp "Think First, Build Smart" lấy cảm hứng từ Lovable Prompt Strategy.

## Overview

Skill này giúp người dùng đi từ **một câu mô tả đơn giản** → **bản blueprint hoàn chỉnh** bao gồm:
- Vision & Problem Statement
- Target Users & Personas
- Core User Journey
- MVP Feature Set
- Design System Specs
- Technical Architecture gợi ý
- Prompt-ready output cho các AI coding tools (Lovable, Bolt, Cursor, v0...)

---

## Nguyên Tắc Cốt Lõi (từ Lovable Prompt Strategy)

Trước khi tạo blueprint, luôn áp dụng triết lý:
> **"Think First, Prompt Smart"** — Lên kế hoạch trước khi code. Không bao giờ bắt đầu với toàn bộ app cùng lúc.

1. **Atomic Building**: Mỗi feature là một "Lego brick" độc lập
2. **User Journey First**: Xác định hành trình người dùng trước khi nghĩ đến UI
3. **MVP Focus**: Chỉ 3–7 tính năng cốt lõi cho phiên bản đầu tiên
4. **Design Tokens Early**: Định nghĩa màu sắc, font, spacing trước khi build
5. **Frontend First**: Build UI với mock data trước, tích hợp backend sau

---

## Quick Start

Khi người dùng cung cấp ý tưởng (dù chỉ 1 câu), hãy:

1. **Phân tích** ý tưởng → xác định Problem, Solution, Target User
2. **Làm rõ** (nếu cần) tối đa 2–3 câu hỏi thiết yếu
3. **Tạo Blueprint** theo template chuẩn bên dưới
4. **Output** dưới dạng artifact markdown có cấu trúc đẹp

---

## Workflow Chi Tiết

### Bước 1: Phân Tích Ý Tưởng

Khi nhận yêu cầu, phân tích theo framework:

```
INPUT: "[Ý tưởng của người dùng]"

Phân tích nhanh:
- WHAT: Ứng dụng làm gì?
- WHO: Ai là người dùng chính?
- WHY: Vấn đề gì được giải quyết?
- HOW: Cơ chế hoạt động cơ bản?
- WHEN: Khi nào người dùng sẽ dùng app này?
```

### Bước 2: Hỏi Làm Rõ (Tối đa 3 câu)

Chỉ hỏi khi thực sự thiếu thông tin quan trọng. Ưu tiên hỏi:
1. **Target User**: "App này cho ai? Cá nhân, doanh nghiệp, hay nhóm cụ thể?"
2. **Core Action**: "Hành động quan trọng nhất người dùng sẽ làm là gì?"
3. **Scope**: "Đây là web app, mobile app, hay desktop?"

**Nếu thông tin đã đủ → bỏ qua bước này và tạo blueprint ngay.**

### Bước 3: Tạo App Blueprint

Sử dụng template chuẩn bên dưới. Output ra một artifact markdown hoàn chỉnh.

---

## Blueprint Template

Khi tạo blueprint, sử dụng cấu trúc 10 sections sau:

```
# 🚀 [Tên App] — App Blueprint

> **Tagline**: [1 câu mô tả ngắn gọn nhất về app]

---

## 📋 1. Product Overview

### Problem Statement
[Vấn đề gì đang tồn tại? Tại sao người dùng cần giải pháp này?]

### Solution
[App này giải quyết vấn đề đó như thế nào? Điểm khác biệt là gì?]

### Vision
[App này sẽ trở thành gì trong 1–2 năm tới?]

---

## 👥 2. Target Users & Personas

### Primary Persona
- **Tên**: [Tên đại diện, VD: "Nam - Freelancer Designer"]
- **Độ tuổi**: [range]
- **Mục tiêu**: [Họ muốn đạt được gì?]
- **Pain Points**: [Vấn đề hiện tại của họ]
- **Cách dùng app**: [Họ sẽ dùng app khi nào, ở đâu?]

### Secondary Persona (nếu có)
[Tương tự]

---

## 🗺️ 3. Core User Journey (MVP)

Hành trình chính của người dùng (step-by-step):

1. **[Onboarding]**: [Mô tả bước 1]
2. **[Core Action]**: [Hành động chính — đây là "aha moment"]
3. **[Value Delivery]**: [Người dùng nhận được gì?]
4. **[Retention Hook]**: [Điều gì khiến họ quay lại?]

### Key Screens Flow:
[Screen 1] → [Screen 2] → [Screen 3] → [Screen 4]

---

## ⚡ 4. MVP Feature Set (3–7 Features)

> Nguyên tắc: Chỉ build những gì THIẾT YẾU cho core user journey. Mọi thứ khác là v2.

| # | Feature | Mô tả | Priority |
|---|---------|--------|----------|
| 1 | [Tên feature] | [Mô tả ngắn] | 🔴 Must Have |
| 2 | [Tên feature] | [Mô tả ngắn] | 🔴 Must Have |
| 3 | [Tên feature] | [Mô tả ngắn] | 🟡 Should Have |
| 4 | [Tên feature] | [Mô tả ngắn] | 🟡 Should Have |
| 5 | [Tên feature] | [Mô tả ngắn] | 🟢 Nice to Have |

### Out of Scope (v1)
- [Feature bị loại bỏ khỏi MVP 1]
- [Feature bị loại bỏ khỏi MVP 2]

---

## 🎨 5. Design System

### Visual Identity
- **Style**: [VD: Modern SaaS / Playful / Corporate / Dark & Moody]
- **Personality**: [3 từ mô tả cảm giác của app]

### Color Palette
| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary | [Màu chính] | #XXXXXX | Buttons, CTAs, links |
| Secondary | [Màu phụ] | #XXXXXX | Accents, highlights |
| Background | [Nền] | #XXXXXX | Page background |
| Surface | [Surface] | #XXXXXX | Cards, modals |
| Text Primary | [Chữ chính] | #XXXXXX | Headings, body |
| Text Muted | [Chữ phụ] | #XXXXXX | Captions, placeholders |
| Success | [Xanh lá] | #10B981 | Success states |
| Warning | [Vàng] | #F59E0B | Warning states |
| Error | [Đỏ] | #EF4444 | Error states |

### Typography
- **Display/Heading Font**: [VD: Inter, Outfit, Sora — Google Fonts]
- **Body Font**: [VD: Inter, Roboto]
- **Scale**: Display(48px) / H1(36px) / H2(28px) / H3(22px) / Body(16px) / Small(14px) / Caption(12px)

### Spacing System (8pt Grid)
- **Base Unit**: 8px
- **Scale**: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96px

### Border Radius
- **Small**: 6px (badges, tags)
- **Medium**: 12px (cards, inputs)
- **Large**: 16px (modals, panels)
- **Full**: 9999px (pills, avatars)

---

## 🏗️ 6. Screen Architecture

### Screen List (MVP)
| Screen | Route | Mô tả | Auth Required? |
|--------|-------|--------|----------------|
| Landing/Home | / | [Mô tả] | No |
| [Screen 2] | /[path] | [Mô tả] | Yes |
| [Screen 3] | /[path] | [Mô tả] | Yes |
| [Screen 4] | /[path] | [Mô tả] | Yes |

### Component Inventory
- **Layout**: Navbar, Sidebar, Footer, Modal, Drawer
- **Data Display**: Card, Table, List, Badge, Avatar, Tooltip
- **Forms**: Input, Select, Checkbox, Toggle, DatePicker, FileUpload
- **Feedback**: Toast/Notification, Loading Spinner, Empty State, Error State
- **Navigation**: Tabs, Breadcrumbs, Pagination

---

## ⚙️ 7. Technical Architecture (Gợi Ý)

### Frontend Stack
- **Framework**: [React + Vite / Next.js / Vue / etc.]
- **Styling**: [Vanilla CSS / Tailwind CSS / shadcn/ui]
- **State Management**: [Zustand / Redux / Context API]
- **Routing**: [React Router / Next.js App Router]

### Backend & Data
- **Backend**: [Supabase / Firebase / PocketBase / Custom Node.js]
- **Database**: [PostgreSQL / Firestore / SQLite]
- **Auth**: [Supabase Auth / Firebase Auth / Auth0 / Clerk]
- **Storage**: [Supabase Storage / Firebase Storage / S3]
- **API**: [REST / GraphQL / tRPC]

### Key Integrations (nếu cần)
- [API 1]: [Mục đích]
- [API 2]: [Mục đích]

---

## 📝 8. AI Coding Prompts (Ready-to-Use)

### Prompt 1: Foundation Setup
Dùng prompt này đầu tiên để khởi tạo app

  Create a [web app / mobile-first web app] called "[App Name]":
  
  [Tagline]
  
  Design System:
  - Primary color: [hex]
  - Background: [hex]
  - Font: [Font name] from Google Fonts
  - Style: [visual style description]
  - Dark mode: [Yes/No]
  
  Build the base layout with:
  - Navigation bar with logo and links: [list]
  - Hero section with headline: "[Main headline]"
  - [Other key sections]
  
  Stack: React + TypeScript + Vite. Mobile-first responsive design.
  Use mock data only — no backend yet.

### Prompt 2: Core Feature — [Feature 1 Name]

  Add the [Feature Name] feature:
  
  Requirement: [What this feature does]
  
  UI Layout:
  - [Component, layout, position on screen]
  
  Data/State:
  - [Data needed, fields, mock data structure]
  
  Logic & Behaviors:
  - [Click, submit, validation, empty state, loading state]
  
  Do NOT modify: [Pages/components to leave unchanged]

### Prompt 3: Authentication

  Add authentication using Supabase Auth:
  - Email/Password login
  - [OAuth: Google, GitHub if needed]
  - Protected routes: [list]
  - User profile in Supabase 'profiles' table
  - Redirect after login: [path]
  - Redirect after logout: [path]
  
  Do NOT change existing UI — only add auth layer.

---

## 📊 9. Success Metrics (KPIs)

| Metric | Mô tả | Target (Month 1) |
|--------|--------|-----------------|
| [Metric 1] | [VD: DAU - Daily Active Users] | [Target] |
| [Metric 2] | [VD: Core Action Completion Rate] | [Target] |
| [Metric 3] | [VD: User Retention D7] | [Target] |

---

## 🗓️ 10. Development Roadmap

### Phase 1 — MVP (Week 1–2)
- [ ] Foundation setup & design system
- [ ] Core screens skeleton
- [ ] Feature 1: [Name]
- [ ] Feature 2: [Name]
- [ ] Auth integration

### Phase 2 — Enhancement (Week 3–4)
- [ ] Feature 3: [Name]
- [ ] Feature 4: [Name]
- [ ] Mobile responsiveness polish
- [ ] Performance optimization

### Phase 3 — Growth (Month 2+)
- [ ] Feature 5+: Nice-to-have features
- [ ] Analytics integration
- [ ] SEO / Marketing site
```

---

## Hướng Dẫn Sử Dụng Skill

### Khi Nào Kích Hoạt
- Người dùng muốn tạo/thiết kế một app/website
- Người dùng mô tả ý tưởng và hỏi cần làm gì
- Người dùng muốn "lên kế hoạch" cho một dự án số
- Keywords: "thiết kế app", "tạo app", "blueprint", "lên kế hoạch", "design app", "build app", "PRD"

### Output Format
- Luôn output ra **artifact markdown** có cấu trúc đẹp
- Sử dụng emoji, tables, và code blocks để tăng readability
- Điền đầy đủ 10 sections của template — không bỏ sót
- Các AI Prompts phải **ready-to-use** (copy-paste được ngay)
- Gợi ý màu sắc cụ thể (hex codes), không generic

### Điều Chỉnh Theo Context
- **App đơn giản** (todo, notes): Giản lược sections 7 (kỹ thuật)
- **App phức tạp** (SaaS, marketplace): Mở rộng sections 4, 6, 7
- **Mobile app**: Nhấn mạnh responsiveness, touch interactions
- **B2B tool**: Nhấn mạnh roles/permissions, data security

### Common Mistakes Cần Tránh
1. **Đừng nhồi nhét quá nhiều features** vào MVP — giữ 3–7 cốt lõi
2. **Đừng skip User Journey** — đây là phần quan trọng nhất
3. **Đừng generic hóa design** — luôn gợi ý hex cụ thể, không "màu xanh"
4. **Đừng bỏ qua empty states và error states** trong feature specs
5. **Đừng mix frontend và backend** trong cùng một prompt

---

## Ví Dụ Trigger

### Input:
"Tôi muốn tạo app giúp freelancer theo dõi thời gian làm việc"

### Expected Output:
Blueprint hoàn chỉnh 10 sections với:
- Persona: Freelancer, 25–35 tuổi, làm việc remote
- Core Journey: Start Timer → Log Task → View Report → Export Invoice
- MVP Features (5): Timer, Project Manager, Time Log, Reports Dashboard, Invoice Generator
- Design: Dark mode, professional, bảng màu Indigo (#6366F1) + Emerald (#10B981)
- 3 Ready-to-use AI prompts cho Lovable/Cursor/Bolt
