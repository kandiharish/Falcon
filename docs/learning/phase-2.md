# Phase 2 — Design System + Application Shell

## 1. What we built

```
┌──────────────┬───────────────────────────────────────────────────────────────┐
│ 🦅 FALCON     │ ☰  FALCON › Overview   [🔍 Search… Ctrl K]  [CASE-2026-001 ▾] 🔔 ? 👤│ ← top bar
│              ├───────────────────────────────────────────────────────────────┤
│ Command      │ CASE-2026-001 Riverside…  ● Active  ▮High  👤 Lead  📍 Location │ ← context strip
│  Overview    ├───────────────────────────────────────────────────────────────┤
│  Investig. P4│                                                               │
│ Evidence     │                  PAGE CONTENT  (<Outlet />)                   │
│  Evidence  P5│                                                               │
│  Entities  P6│   Overview: current investigation · workflow · system status  │
│  …           │             · investigations table                            │
│ Governance   │   Other modules: "Planned for Phase N" + what they will do    │
│  Admin     P3│                                                               │
│ 🎨 Design sys│                                                               │
└──────────────┴───────────────────────────────────────────────────────────────┘
   sidebar (collapses to icons; becomes a drawer on phones)
```

- A **design system**: colour tokens, fonts, and reusable components.
- The **application shell**: sidebar, top bar, context strip — the frame around every page.
- Pages: **Overview**, a **Design system** showcase, "planned module" pages, **404**, **crash page**.
- Light + dark theme, keyboard shortcuts (Ctrl+K search, Ctrl+B sidebar), phone layout.

## 2. The layers of the design system

```
 ① TOKENS            index.css           --primary, --warning, --sidebar …   "the paint"
        ▼
 ② BASE COMPONENTS   components/ui/      Button, Table, Dialog, Sheet …      "the bricks"   (shadcn)
        ▼
 ③ FALCON COMPONENTS design-system/      StatusBadge, ConfidenceIndicator,    "FALCON bricks"
                                          AssertionLabel, WorkflowStepper …
        ▼
 ④ SHELL + PAGES     app-shell/, features/                                    "the house"
```

Rule: a page never invents colours or badges — it only combines parts from ① ② ③.
Change `--warning` once → every "Under Review" badge in the app changes.

## 3. How data reaches a screen (the service layer, upgraded)

```
 OverviewPage
     │  useInvestigations()                 ← queries.ts   (TanStack Query hook)
     ▼
 TanStack Query cache ── fresh? → return instantly (no network)
     │ stale / missing
     ▼
 InvestigationService.list()              ← investigationService.ts
     │
     ▼
 mock/fixtures.ts  (Phase 2)   ──►  real API /api/investigations  (Phase 4)
```

The page never knows the data is fake. In Phase 4 only `investigationService.ts` changes.

## 4. Key ideas

### 4.1 Design tokens
CSS variables hold every colour. Two sets: `:root` (light) and `.dark`. The theme switch only
adds/removes the class `dark` on `<html>`.

### 4.2 Accessibility built in (plan §36)
| Rule | Where you see it |
|---|---|
| Never colour alone | badges = icon + word + colour; confidence = bars + word + number |
| Contrast ≥ 4.5:1 for small text | semantic colours kept at lightness ≤ 0.55 in light mode |
| Keyboard reachable | Radix components; table rows have a real button; "Skip to content" link |
| One `<main>` landmark | fixed a nested `<main>` found in testing |
| Reduced motion | animations switch off if the OS asks |

### 4.3 Provenance labels (plan §13, §22)
`FACT · EXTRACTED · DETECTED · CORRELATED · INFERRED · USER ENTERED` — every future fact will
carry one. Hover a label to see what it means. This is how FALCON avoids presenting AI guesses
as truth.

### 4.4 Global state vs server state
```
 Server state (from the API)  → TanStack Query  (investigations, user, health)
 UI state (only in browser)   → Zustand         (which investigation is current)
 Preference                   → ThemeProvider   (light/dark, saved in localStorage)
```

### 4.5 Lazy loading (plan §39)
Each page's code downloads only when opened. The build output shows separate files:
`OverviewPage-….js`, `DesignSystemPage-….js`, …

### 4.6 One navigation config
`app/navigation.ts` defines all modules once. Sidebar, breadcrumbs, search and the
"planned module" pages are all generated from it — add a module in one place.

## 5. Why these choices

| Choice | Why | Instead of |
|---|---|---|
| Tailwind + shadcn/ui | we own the component code; accessible Radix underneath | Material UI / Ant Design: generic look, hard to restyle |
| Own ThemeProvider (40 lines) | we don't need a Next.js-oriented package | next-themes |
| TanStack Query | loading/error/cache/retry for free | `useState` + `useEffect` on every page |
| Zustand + persist | one line of state, remembered across reloads | Redux (heavy), Context (re-renders everything) |
| cmdk command palette | fast keyboard search | a plain input with manual filtering |
| Fonts via @fontsource | self-hosted, works offline, no tracking | Google Fonts CDN |
| Generated "planned" pages | every nav item works and says what's coming (plan §59) | dead links or blank pages |

## 6. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| shadcn CLI stopped at interactive prompts | CLIs need flags in automation (`-t vite -b radix -p nova`, `--overwrite`) |
| Unknown `cn` package appeared | **Verify before trusting** — it's from the shadcn-ui org (supply-chain safety) |
| Amber text too light on white | Check contrast, not just "looks fine" |
| Search crashed (`reading 'subscribe'`) | The dialog didn't wrap items in `<Command>`. Only a real browser test found it — the type-check passed |
| Crash showed React Router's developer screen | Added `RouteError`: human message + recovery buttons |
| Nested `<main>` | Found by reading the accessibility tree, not the screenshot |
| Horizontal scroll on phones | Search collapses to an icon; help hides below 640 px |
| Lint warnings in shadcn files | Turn rules off only for generated folders, keep them for our code |
| PowerShell 5.1 added a BOM to a file | Windows PowerShell's `utf8` = UTF-8 *with* BOM; prefer editors/tools that write plain UTF-8 |

## 7. Improvements for later

- Split the 545 kB main bundle further (vendor chunks). *(P12)*
- Automated component tests (Vitest + Testing Library) and E2E tests (Playwright). *(P12)*
- Real notifications + unread badge. *(P11)*
- Investigation switcher on phones (currently via Ctrl+K search only). *(P4)*
- Full-text global search across evidence, entities and events. *(P11)*

## 8. Try it yourself

1. http://localhost:5190 — switch investigation from the top bar; watch the strip, card and table update.
2. Press **Ctrl+K**, type `harbor`, press Enter.
3. Press **Ctrl+B** to collapse the sidebar.
4. Account menu → Appearance → Dark.
5. Open **Design system** (sidebar bottom) — hover the provenance labels, open the modal and drawer.
6. Make the browser window narrow — watch the layout adapt.
7. Visit http://localhost:5190/anything — the 404 page.
