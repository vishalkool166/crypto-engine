# Signal Engine — frontend product and UX specification

## Visual direction

A **contemporary financial operations dashboard**: calm composition, high readability, generous but not wasteful spacing, unambiguous numbers, restrained accent palette, clear typography and precise alignment. Avoid Bloomberg density, hacker/terminal motifs, Vercel black-console mimicry, glowing neon, decorative gradients, glass cards and repetitive AI-template metric tiles. Support light and dark themes without assuming either is final brand default.

No production visual design is approved until reference captures and one desktop/mobile flow are reviewed. Keep the design system small: tokens for neutral surfaces, action states, semantic positive/negative/warning, spacing, type scale, border, elevation, density and focus states. Charts communicate change; only animate where it aids comprehension.

## Information architecture

**User navigation**: Overview, Signals, Trades/Portfolio (if tier), Performance (if tier), Content (if tier), Account & Security. Pricing stays discoverable outside the primary operational flow.
**Admin workspace** (separate group/section): Engine, Indian Markets, Coins/Universe, Users & Subscriptions, Audit, Infrastructure/System, integrations. Admin should switch workspace without confusing customer data with platform operations.

Preserve all existing views/features in `src/pages` and `/demo/*` routes. A page can move, combine or split, but every old action needs a mapping and end-to-end test. Tier restrictions are enforced server-side too. Demo is visually clear and never served as live account data.

## Page-by-page acceptance contract

| Existing area | New purpose / hierarchy | Core behaviors |
|---|---|---|
| Home/Overview | clear current state and 3–5 essential summaries | Last updated/source, engine mode and connectivity, open exposure, signal highlights, concise activity; drill-down links |
| Signals | signal discovery, monitoring, investigation | Search/filter/sort full dataset; tab active/watching/history; signal detail with grade, rationale, levels, timestamps and decision trace |
| Trades | open positions vs closed-trade history | Open positions top priority; historical table with server paging; trade drawer, actual vs unrealized P&L distinction; protected actions |
| Performance | performance review, not claim of guaranteed returns | Date range, market/coin/grade filters, chart and export if API supports; realized vs simulated clearly labeled |
| Engine | admin trading operations and diagnostics | Health, reject reasons, settings/actions gated and reversible, audit of sensitive controls |
| India | Indian sessions, quotas, signals and journeys | Market state, source freshness, quota and broker cooldown, paper-mode distinction, controlled refresh |
| Users | account/role management for admin | List pages, search, filters, deactivate/reactivate, session management with role confirmation |
| Coins | universe and symbol configuration | Search, status, validations, versioned changes, dangerous toggle confirmation |
| System | real diagnostics and incident insight | Services, job results, Redis/DB/WS and errors; no pretend green health indicators |
| Audit | inspect who did what and when | Immutable event list, server-side search/filter/page, important trace IDs and dates |
| Content | currently tiered content area | Preserve accessible operations, separate from trading controls |
| Settings/Profile | account and device security | Profile, sessions, Google link if supported, email verification, recovery, MFA/TOTP; no trading-email settings |
| Login/onboarding | secure, understandable account entry | OAuth + existing identity policy, verification, recovery, generic errors, screen-reader friendly validation |
| Demo/Pricing | truthful product preview | Mock-data labeling, no live order side effects, tier controls isolated from real accounts |
| Chatbot | optional aid, not privileged shortcut | Preserve authorization/data boundaries and separate generated advice from verified execution metrics |

## Pagination and data rules — core defect targets

Inspected examples: shared `DataTable.tsx` changes sort indicators but doesn't reorder data; `useSignalHistory` defines `grade/outcome/coin` arguments but query key only includes `limit`; `useTradeHistory` supports `(limit, offset)` but the page uses a larger batch locally. The new table API will select one explicit mode (server or local) and implement it truthfully.

- Server-side pages for history, users, coins and audit where data can grow; **25 / 50 / 100** page-size choices with reasonable server maximum.
- Full-dataset filtering/sorting **on the backend** with allowlisted columns, stable secondary key, accurate results and page navigation.
- Where UI offers numbered pages use offset/total with stable sort; for rapidly appended event streams consider cursor-based pagination with `next_cursor`. Do not fake totals for cursor streams.
- Search/filter/sort/page encoded in URL where useful; restoring URL reproduces view; filter change resets page to first.
- Loading, empty-filter, no-data, unauthorized, API-down and timeout states explicitly distinguished.
- Live WebSocket updates may refresh a badge/summary; do not reorder a page being read unexpectedly. Provide 'new events available' indication.
- Pagination must handle data deletion, filtered-empty results, stale cursors and role-dependent counts.
- Query cache keys contain ALL effective parameters and user scope; invalidations target current queries, not a hardcoded old page (e.g. `['trades-history', 200, 0]`).

## Responsive and accessibility standards

- 1440px desktop, 1024px tablet, 768px compact laptop/tablet, 390px and 320px mobile as representative test targets; adapt fluidly rather than targeting one device.
- Desktop: narrow nav, clear content max width, no information overload; details can use side drawer. Tablet: collapsible nav and rearranged charts. Mobile: small-screen record cards for wide histories where useful, focusable row/detail controls, bottom sheet/drawer only where appropriate.
- Keyboard navigation for tables/sort controls, dialogs, filters, skip link and command palette; do not place functional sort on non-focusable header alone.
- WCAG 2.2 AA target; contrast, reduced motion, form labels/error association, live-region moderation and touch targets checked.
- Technical fields must show units (USD, %, quote/contract), sign, timezone, age and source. Never rely solely on color for losses, warnings or position type.

## Interaction acceptance rules

Every control: visible action → loading/disabled/success/error feedback → backend state/route change validated. Dangerous commands require clear confirmation plus step-up authentication when required. Mock/demo controls remain in demo context. A screenshot cannot satisfy a functionality gate. Maintain stable links and use error boundaries for third-party dependencies.

## UI testing records

Capture approved before/after snapshots for Overview, Signals, Trades, Performance, Admin/System, Settings/Security and all at 390px. Test the same journeys as free, pro, admin and demo. Record API response fixtures and WebSocket messages used for regression.
