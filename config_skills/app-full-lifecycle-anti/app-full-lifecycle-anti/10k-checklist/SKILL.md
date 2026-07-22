---
name: 10k-checklist
description: Audit a website, landing page, or UI against the Metics Media "$10K Checklist" — the 8 craft criteria that separate a $10K site from a $200 one (point of view, typography, color, hierarchy, imagery, motion, mobile, invisible craft). Trigger when the user asks to "check 10K", "audit UI/site", "$10K checklist", "kiểm tra web 10K", "review chất lượng site", "chấm điểm design", or wants a design-craft pass on a URL, screenshot, or codebase they're building.
license: Source — Metics Media, Field Guide No. 01 (Claude Code Era, MMXXVI)
---

# The $10K Checklist

Audit a website against the 8 criteria that separate premium craft from generic template output. This is a **taste and craft** review, not a functional QA — you're judging whether the site *feels* like it cost $10K, or like it cost $200.

## How to run the audit

1. **Identify the target.** Ask the user what to audit if unclear: a live URL, a local dev server, a screenshot, a Figma link, or the code in the current repo. If it's a codebase, launch the dev server (use the `run` skill if available) and open the actual rendered page — don't audit from source code alone. Design lives in pixels, not JSX.

2. **Inspect, don't guess.** For live/local pages, use `preview_inspect` for computed styles (colors, fonts, spacing), `preview_screenshot` for layout impression, and `preview_resize` to check mobile at 375×812. For static screenshots, read them directly. Never claim a color, font, or contrast ratio without evidence.

3. **Score each of the 8 items** on this rubric, giving concrete evidence (selectors, hex values, screenshots) for the verdict:
   - **PASS** — meets the $10K bar
   - **WEAK** — present but generic, on the $200 side
   - **FAIL** — missing or actively hurts the design
   - **N/A** — genuinely doesn't apply (rare; justify it)

4. **Report** in the format at the bottom of this file. Lead with the overall verdict, then item-by-item, then a prioritized fix list.

---

## The 8 criteria

### 01. Point of view, not a template
> The site commits to a specific design direction — brutalist, editorial, dark-luxury, retro-modern, whatever — and executes it without flinching. A $200 site is generic. A $10K site has taste.

**Audit questions:**
- Can you name the aesthetic in one phrase? (e.g. "swiss editorial", "dark-luxury with serif display", "brutalist with monospace") If your answer is "modern SaaS" or "clean minimal", that's a **WEAK**.
- Does every section reinforce that direction, or do parts drift (e.g. brutalist hero → generic bootstrap footer)?
- Is there one recognizable move a designer would remember? (unusual grid, distinctive header treatment, signature transition)

**FAIL signals:** Looks like a Tailwind UI / Framer template. Could be swapped with 20 other startup pages and no one would notice.

### 02. Typography that does work
> A paired display + body face, neither of them Inter or Roboto. Scale and weight carry hierarchy. The headlines feel chosen, not defaulted.

**Audit questions:**
- Grab the display face and body face — what are they? Inspect `font-family` on `h1` and `p`.
- If either is Inter, Roboto, or system-ui default → **WEAK** at best. These are the sound of "we didn't decide."
- Is there a real type scale (e.g. 12 / 14 / 16 / 20 / 32 / 56 / 96) or just "big, medium, small"?
- Do weights/widths do work — condensed display, italic accent, mono captions — or is everything Regular 400?

**PASS signals:** A pairing you'd remember (e.g. Söhne + Tiempos, GT America + Editorial New, PP Neue Machina + Fraunces). Tight hierarchy that reads without effort.

### 03. A restrained color system
> Three to five colors, used consistently. No rainbow palettes. Premium signals through restraint, not decoration.

**Audit questions:**
- Extract the palette (inspect background, text, accents, borders). Count distinct hues, not shades.
- More than 5 hues → **WEAK**. Rainbow gradient buttons + colored icons + illustrated stickers → **FAIL**.
- Is there one hero accent color that carries the brand, or is color scattered evenly (no focal point)?
- Are neutrals warm/cool consistent, or a mix of `#F5F5F5` grays with `#FAFAF7` warms with `#EFF1F5` cools (unintentional inconsistency)?

**PASS signals:** Two neutrals (a paper and an ink), one hero accent, maybe one supporting tone. Used with discipline.

### 04. Hierarchy that breathes
> Whitespace, scale, and contrast tell the viewer where to look without effort. The page has a clear primary, secondary, tertiary — no flat walls of content.

**Audit questions:**
- Where does your eye go first? Second? Third? If you can't answer, hierarchy has failed.
- Is there real whitespace (sections with `padding: 120px+`), or is everything crammed at 24px?
- Ratio between H1 and body — is it dramatic (e.g. 96px / 16px = 6:1), or timid (32px / 16px = 2:1)?
- Are there walls of same-size cards, or does layout vary — hero item, secondary grid, tertiary list?

**FAIL signals:** Flat grid of identical cards. Everything is 16–24px text. Sections separated only by thin lines.

### 05. Imagery with intent
> Not Unsplash defaults everyone's seen. Either custom photography, generated assets that match the art direction, or curation tight enough that the images feel commissioned.

**Audit questions:**
- Reverse-image-search the hero image mentally: does it feel like it could be on 500 other startup sites? (laptop-on-desk, diverse-team-laughing, abstract-3d-blob → **FAIL**)
- Do images share a treatment (color grade, aspect ratio, subject framing) that reads as one system?
- If there's no photography, are the illustrations/generated assets specific to the brand's world, or generic Undraw-style?

**PASS signals:** Photography with a consistent grade. Illustrations that reference the subject matter. Or the confident choice to have no imagery at all (pure typographic).

### 06. Motion that whispers
> Micro-interactions and scroll behavior feel hand-crafted, not AOS-fade-up slop. The bar: a designer would nod, not roll their eyes.

**Audit questions:**
- Hover a button, a link, a card. Is there a considered response (color shift with 200ms ease-out, subtle scale, underline draw), or nothing / a jarring default?
- Scroll the page. Do elements reveal with intent (staggered, directional, character-by-character on a headline), or does everything AOS-fade-up together?
- Does motion respect `prefers-reduced-motion`? Check with `preview_resize` colorScheme or DevTools.

**FAIL signals:** Every section fades up on scroll. Buttons have no hover state. Auto-playing carousel with dots. Parallax on everything.

### 07. Mobile that's designed, not shrunk
> Layout decisions for phone are different from desktop, not the desktop version compressed. This is where 90% of cheap sites collapse.

**Audit questions:**
- Resize to mobile (375×812 with `preview_resize preset: mobile`). Screenshot.
- Is the hero re-composed for portrait (different image crop, restacked text, adjusted type scale), or the desktop layout squeezed?
- Is navigation a proper mobile pattern (hamburger with considered menu, or bottom nav), or the desktop nav with tiny text?
- Are tap targets ≥44px? Inspect button/link heights.
- Do multi-column desktop grids collapse thoughtfully (some become carousels, some stack, some go 2-up not 1-up)?

**FAIL signals:** Horizontal scroll on mobile. Text at 12px. Desktop nav crammed into mobile. Images at desktop aspect ratios (letterboxed).

### 08. The invisible expensive stuff
> Sub-2s load, WCAG AA contrast, keyboard navigation, semantic HTML, real meta tags. Viewers don't see it directly but they feel "this site is fast and works" — the felt difference between expensive and cheap.

**Audit checks:**
- **Load:** Check Network tab or Lighthouse. LCP under 2.0s is the bar.
- **Contrast:** Sample body text against background — is contrast ratio ≥4.5:1? Inspect and compute, or eyeball obvious fails (light gray on white).
- **Keyboard:** Tab through the page. Are focus rings visible? Does tab order match visual order? Can you reach every interactive element?
- **Semantic HTML:** View source. Are headings a real h1/h2/h3 hierarchy, or all divs? Are buttons `<button>` or `<div onClick>`?
- **Meta tags:** `<title>`, `<meta description>`, Open Graph image, favicon. Missing any → **WEAK**.

**FAIL signals:** LCP > 4s. Body text at 3:1 contrast. No visible focus state. `<div>` soup. Placeholder title still says "Vite + React".

---

## Report format

```markdown
# $10K Checklist Audit — {site name / URL}

**Overall verdict:** {$10K / $2K / $500 / $200 tier} — {one-sentence why}

## Scorecard

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 01 | Point of view | PASS/WEAK/FAIL | {one line} |
| 02 | Typography | ... | ... |
| 03 | Color system | ... | ... |
| 04 | Hierarchy | ... | ... |
| 05 | Imagery | ... | ... |
| 06 | Motion | ... | ... |
| 07 | Mobile | ... | ... |
| 08 | Invisible craft | ... | ... |

## Findings (worst first)

### 🔴 {criterion} — {short title}
{2-4 sentences: what you saw, why it fails the bar, specific evidence — hex values, font names, selectors, LCP numbers}

### 🟡 {criterion} — {short title}
...

## Prioritized fix list

1. **{Highest-leverage fix}** — {what to change, why it moves the needle, rough effort}
2. ...
3. ...

## What's already working

- {Genuine PASSes, so the user knows what to preserve}
```

## Notes for running the audit

- **Be specific, not vague.** "Typography feels generic" is useless. "Body is Inter 400 16px, headings are Inter 700 — swap display face to something like Fraunces or GT Sectra to establish a real pairing" is useful.
- **Show evidence.** Hex codes from `preview_inspect`, screenshots from `preview_screenshot`, network waterfall numbers. Never claim a verdict without a source.
- **Rank by leverage, not by checklist order.** If typography is the biggest failure, lead the fix list with it, even though it's criterion #02.
- **Don't grade on a curve.** The whole point is the $10K bar. If a site is a solid $2K, say so — that's still useful.
- **One real risk.** If the design is competent but templated, name the specific aesthetic risk that would push it from $2K into $10K territory.
