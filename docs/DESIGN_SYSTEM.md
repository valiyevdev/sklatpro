# DESIGN SYSTEM — SKLAT PRO

## Design Language

Professional SaaS · Premium · Enterprise-grade · Modern · Clean · Minimal but informative · High information density without clutter · Strong hierarchy · Excellent spacing · Consistent components

---

## Color Palette

### Primary
| Token | Value | Usage |
|-------|-------|-------|
| `--primary-50` | `#eef2ff` | Light backgrounds |
| `--primary-100` | `#e0e7ff` | Hover backgrounds |
| `--primary-200` | `#c7d2fe` | Borders |
| `--primary-300` | `#a5b4fc` | Icons |
| `--primary-400` | `#818cf8` | Secondary buttons |
| `--primary-500` | `#6366f1` | Primary buttons, links |
| `--primary-600` | `#4f46e5` | Primary buttons hover |
| `--primary-700` | `#4338ca` | Active states |
| `--primary-800` | `#3730a3` | Dark accents |
| `--primary-900` | `#312e81` | Darkest accents |

### Semantic
| Token | Value | Usage |
|-------|-------|-------|
| `--success-500` | `#22c55e` | Success badges, confirmations |
| `--success-600` | `#16a34a` | Success hover |
| `--warning-500` | `#f59e0b` | Warning badges, alerts |
| `--warning-600` | `#d97706` | Warning hover |
| `--danger-500` | `#ef4444` | Errors, delete actions |
| `--danger-600` | `#dc262a` | Error hover |
| `--info-500` | `#3b82f6` | Informational |
| `--info-600` | `#2563eb` | Info hover |

### Neutral (Gray Scale)
| Token | Value | Usage |
|-------|-------|-------|
| `--gray-50` | `#f9fafb` | Page background |
| `--gray-100` | `#f3f4f6` | Card backgrounds |
| `--gray-200` | `#e5e7eb` | Borders |
| `--gray-300` | `#d1d5db` | Disabled borders |
| `--gray-400` | `#9ca3af` | Placeholder text |
| `--gray-500` | `#6b7280` | Secondary text |
| `--gray-600` | `#4b5563` | Body text |
| `--gray-700` | `#374151` | Headings |
| `--gray-800` | `#1f2937` | Dark text |
| `--gray-900` | `#111827` | Darkest text |

### Sidebar
| Token | Value | Usage |
|-------|-------|-------|
| `--sidebar-bg` | `#1e293b` | Sidebar background |
| `--sidebar-text` | `#94a3b8` | Sidebar text |
| `--sidebar-text-active` | `#ffffff` | Active sidebar item |
| `--sidebar-hover` | `#334155` | Sidebar item hover |
| `--sidebar-active-bg` | `#4f46e5` | Active sidebar item bg |

---

## Typography

### Font Family
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
```

### Scale
| Token | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| `--text-xs` | 0.75rem (12px) | 400 | 1rem | Labels, captions |
| `--text-sm` | 0.875rem (14px) | 400 | 1.25rem | Secondary text |
| `--text-base` | 1rem (16px) | 400 | 1.5rem | Body text |
| `--text-lg` | 1.125rem (18px) | 500 | 1.75rem | Card titles |
| `--text-xl` | 1.25rem (20px) | 600 | 1.75rem | Section titles |
| `--text-2xl` | 1.5rem (24px) | 600 | 2rem | Page titles |
| `--text-3xl` | 1.875rem (30px) | 700 | 2.25rem | Dashboard numbers |

---

## Spacing

| Token | Value |
|-------|-------|
| `--space-0` | 0 |
| `--space-1` | 0.25rem (4px) |
| `--space-2` | 0.5rem (8px) |
| `--space-3` | 0.75rem (12px) |
| `--space-4` | 1rem (16px) |
| `--space-5` | 1.25rem (20px) |
| `--space-6` | 1.5rem (24px) |
| `--space-8` | 2rem (32px) |
| `--space-10` | 2.5rem (40px) |
| `--space-12` | 3rem (48px) |

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-none` | 0 | — |
| `--radius-sm` | 0.25rem (4px) | Small elements |
| `--radius-md` | 0.375rem (6px) | Buttons, inputs |
| `--radius-lg` | 0.5rem (8px) | Cards |
| `--radius-xl` | 0.75rem (12px) | Modals, drawers |
| `--radius-2xl` | 1rem (16px) | Large cards |
| `--radius-full` | 9999px | Avatars, badges |

---

## Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle cards |
| `--shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.1)` | Cards, dropdowns |
| `--shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.1)` | Modals |
| `--shadow-xl` | `0 20px 25px -5px rgba(0,0,0,0.1)` | Floating elements |

---

## Borders

| Token | Value | Usage |
|-------|-------|-------|
| `--border` | `1px solid var(--gray-200)` | Default borders |
| `--border-focus` | `2px solid var(--primary-500)` | Focus states |

---

## Component Styles

### Buttons

#### Primary
```css
.btn-primary {
  background: var(--primary-600);
  color: white;
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-weight: 500;
}
.btn-primary:hover { background: var(--primary-700); }
```

#### Secondary
```css
.btn-secondary {
  background: white;
  color: var(--gray-700);
  border: 1px solid var(--gray-300);
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
}
```

#### Danger
```css
.btn-danger {
  background: var(--danger-500);
  color: white;
  border-radius: var(--radius-md);
}
```

#### Ghost
```css
.btn-ghost {
  background: transparent;
  color: var(--gray-600);
  border-radius: var(--radius-md);
}
.btn-ghost:hover { background: var(--gray-100); }
```

### Inputs
```css
.input {
  border: 1px solid var(--gray-300);
  border-radius: var(--radius-md);
  padding: 0.5rem 0.75rem;
  font-size: var(--text-base);
  width: 100%;
}
.input:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}
```

### Cards
```css
.card {
  background: white;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-6);
}
```

### Tables
```css
.table {
  width: 100%;
  border-collapse: collapse;
}
.table th {
  background: var(--gray-50);
  text-transform: uppercase;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--gray-500);
  letter-spacing: 0.05em;
  padding: var(--space-3) var(--space-4);
}
.table td {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--gray-200);
}
.table tr:hover { background: var(--gray-50); }
```

### Badges
```css
.badge { border-radius: var(--radius-full); padding: 0.125rem 0.625rem; font-size: var(--text-xs); font-weight: 500; }
.badge-success { background: #dcfce7; color: #166534; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-danger { background: #fee2e2; color: #991b1b; }
.badge-info { background: #dbeafe; color: #1e40af; }
.badge-neutral { background: var(--gray-100); color: var(--gray-700); }
```

---

## Layout

### App Shell
```
┌──────────────────────────────────────────────┐
│ Sidebar (240px) │        Topbar              │
│                 ├────────────────────────────┤
│  Navigation     │                            │
│  - Dashboard    │      Content Area          │
│  - Products     │                            │
│  - Inventory    │                            │
│  - Purchases    │                            │
│  - Sales        │                            │
│  - Orders       │                            │
│  - Lists        │                            │
│  - Contacts     │                            │
│  - Warehouses   │                            │
│  - Finance      │                            │
│  - Reports      │                            │
│  - Users        │                            │
│  - Notifications│                            │
│  - Settings     │                            │
│                 │                            │
└──────────────────────────────────────────────┘
```

### Breakpoints
| Name | Width | Sidebar | Content |
|------|-------|---------|---------|
| Desktop XL | 1440px+ | Fixed 240px | Full |
| Desktop | 1200px | Fixed 240px | Full |
| Laptop | 1024px | Collapsed icons | Full |
| Tablet | 768px | Overlay/hamburger | Full |
| Mobile L | 480px | Hidden | Stacked |
| Mobile | 390px | Hidden | Stacked |
| Mobile S | 360px | Hidden | Stacked |

---

## Dark Mode

```css
[data-theme="dark"] {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-surface: #1e293b;
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --border: #334155;
  --sidebar-bg: #0f172a;
}
```

---

## Icons

Using Bootstrap Icons. Consistent sizing:
- Navigation: 20px
- Buttons: 16px
- Table actions: 16px
- Stat cards: 24px
- Empty states: 48px

---

## Spacing in Components

### Stat Cards
```
Padding: 1.5rem (24px)
Gap between cards: 1rem (16px)
Icon size: 24px
Number: text-3xl, font-bold
Label: text-sm, text-gray-500
```

### Tables
```
Cell padding: 0.75rem 1rem
Header: uppercase, text-xs, font-semibold
Row hover: gray-50 background
Action gap: 0.5rem
```

### Forms
```
Label: text-sm, font-medium, text-gray-700
Input: border-gray-300, rounded-md
Error: text-sm, text-red-500
Helper: text-sm, text-gray-400
```

### Modals
```
Max width: 640px (default), 480px (sm), 960px (lg)
Padding: 1.5rem
Overlay: rgba(0,0,0,0.5)
Border radius: var(--radius-xl)
```

---

## Animations

```css
/* Transitions */
transition: all 150ms ease-in-out;

/* Sidebar slide */
.sidebar-enter { transform: translateX(-100%); }
.sidebar-active { transform: translateX(0); }

/* Fade in */
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

/* Slide up */
@keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
```
