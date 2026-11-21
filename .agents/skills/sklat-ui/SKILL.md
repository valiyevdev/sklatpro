---
name: SKLAT UI
description: Build or review UI inside the SKLAT Pro Django app. Use for any template, CSS, dashboard, form, or table work in this repository. Covers design tokens, component classes, card rules, Uzbek copy, money formatting, responsive checks, and Playwright verification.
---

# SKLAT Pro UI

Project-specific UI rules. Read `AGENTS.md` first; this skill only adds what is specific to the interface.

## Stack (do not change)

- Django 4.2, server-rendered templates in `templates/`, vanilla JavaScript, no build step.
- Global stylesheet: `static/css/design-system.css`. Page styles: `auth-pages.css`, `filter-panel.css`, `custom.css`.
- UI language is Uzbek Latin. Code, comments, and commit messages are English.

## Tokens: never hardcode

Every color, spacing, radius, shadow, and font size must come from a CSS variable in `design-system.css`.

| Group | Tokens |
| --- | --- |
| Spacing (4px base) | `--sp-1` `--sp-2` `--sp-3` `--sp-4` `--sp-5` `--sp-6` `--sp-8` `--sp-10` `--sp-12` `--sp-16` `--sp-20` |
| Radius | `--radius-xs` `--radius-sm` `--radius-md` `--radius-lg` `--radius-xl` `--radius-2xl` `--radius-full` |
| Brand | `--primary-50` … `--primary-900` (500 = `#6366f1`, 600 = `#4f46e5`) |
| Status | `--success-*` `--warning-*` `--danger-*` `--info-*` `--gray-50` … `--gray-900` |
| Surfaces | `--bg-page` `--bg-surface` `--bg-surface-hover` `--bg-overlay` |
| Borders | `--border-default` `--border-subtle` `--border-input` `--border-focus` |
| Text | `--text-primary` `--text-secondary` `--text-muted` `--text-disabled` `--text-on-primary` |
| Shadow | `--shadow-xs` … `--shadow-xl` `--shadow-focus` `--shadow-focus-error` |
| Type | `--text-xs` … `--text-5xl`, `--leading-tight` `--leading-normal` `--leading-relaxed` |
| Motion | `--transition-fast` `--transition-base` `--transition-slow` |
| Layers | `--z-dropdown` `--z-sticky` `--z-overlay` `--z-modal` `--z-toast` |

Add a new token only when a value repeats three or more times and no existing token fits. Put it in `:root` with a comment explaining why.

## Components: reuse before writing CSS

Existing classes (grep them in `design-system.css` before adding anything):

- Buttons: `btn-pro`, `btn-pro-primary`, and the related `btn-pro-*` variants.
- Cards: `card-pro`, `card-pro-body`; metrics: `stat-card`, `stat-card-icon`, `stat-card-value`.
- Data: `table-pro`, `cell-primary`, `pagination-pro`, `empty-state`.
- Forms: `input-pro`, `select-pro`, `input-pro-*` helpers.
- Navigation: `page-hero` (standard clean header with no border/background), `page-header`, `page-actions`, `breadcrumb-pro`, `tab-pro`, `sidebar-nav`.
- Feedback: `alert-pro`, `dropdown-item`, `link-modern`.

## Standard Page Header (Hero Component)

Always use `templates/components/hero_header.html` for main page headers instead of custom divs or cards:
- It has NO border and NO background in both light and dark mode.
- Includes `.page-hero-title`, `.page-hero-subtitle`, `.page-hero-stat` pill badge, and `.page-hero-btn`.
- Usage:
  ```html
  {% include 'components/hero_header.html' with title="Sarlavha" subtitle="Tavsif" stat_text="Holat matni" stat_icon="bi-check-circle-fill" action_url="/url/" action_text="Tugma" action_icon="bi-plus-lg" %}
  ```
- CSS is globally available in `design-system.css` via `.page-hero*` classes. Never add separate inline header CSS in page templates.

## Cards

Follow `card-style-guid.md`.

- Internal padding: `--sp-6` (24px) on desktop, `--sp-5` (20px) below 640px.
- One primary action per card. The whole card may be the action.
- Equal height per row, aligned bottoms, fixed media aspect ratio.
- Hover changes border or elevation only. No size or position shift.
- Title must be the heaviest text in the card; metadata the lightest.

## Required states

Every interactive element needs: default, hover, `:focus-visible`, active, disabled, and a loading state when it triggers a request.

Every data view needs: loading, empty, error, and long-content variants.

- Focus must be visible: `box-shadow: var(--shadow-focus)`. Never ship bare `outline: none`.
- Contrast: body text at least 4.5:1, large text at least 3:1.
- Icon-only buttons need `aria-label` in Uzbek.
- Status messages that appear after a request need `role="status"` or `aria-live="polite"`.
- Modals and side panels must trap focus and return focus to the trigger on close.
- Tables belong in an overflow container. At 390px they scroll, they never widen the page.

## Uzbek content

- Sentence case for labels and headings. No ALL CAPS and no English placeholders left behind.
- Money: `12 500 so'm` with a non-breaking space between groups, integer UZS. Backend stores `Decimal`, JSON exposes integer UZS.
- Dates: `20.11.2026`.
- Test with long text such as `mahsulotlar kategoriyasi` and `O'lchov birligi` to catch overflow.
- Apostrophes in `o'` and `g'` must be the typographic `‘` only if the file already uses it; otherwise keep the ASCII `'`.

## Responsive targets

Verify at `1280x720`, `1024x768`, and `390x844`. The 390px case is the one that breaks: check the topbar, filter panel, tables, and card grids first.

## Verification (mandatory before saying done)

1. `python manage.py check`
2. `python manage.py test`
3. `python tools/verify_ui.py` and open the screenshots in `tools/screens/`
4. Assert zero console errors, zero failed requests with status >= 400, no overlapping controls, no text overflow.
5. Exercise the new behavior through the real UI, not only through unit tests.

Report a `HISOBOT` section in Uzbek with actual `OK` / `FAIL` results.

## Do not

- Do not add React, Vue, Tailwind, Bootstrap CDN, or any build tooling.
- Do not hardcode hex colors or pixel spacing when a token exists.
- Do not restyle the app into a generic purple-gradient landing page. Keep the existing slate canvas and indigo accent.
- Do not leave `Lorem ipsum`, `TODO`, or English UI copy in templates.
- Do not claim a UI task is finished without a screenshot or a browser check.
