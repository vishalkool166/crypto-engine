# Phase 07 — UX and interaction delivery

**Candidate artifact:** the route and interaction contract for the current dashboard. This documents the implemented candidate, not production approval. Visual sign-off and browser captures remain pending.

## Route and role inventory

| Route | Workspace | Access | Primary actions and states |
|---|---|---|---|
| `/` | Overview | signed-in user | Review engine/account summary; drill into signals, trades and performance; loading, empty, API error and stale connection states |
| `/signals` | Signals | signed-in user; detail visibility follows tier delay | Filter monitored signals; inspect rationale/levels/decision trace; admin scan; empty, delayed/locked, loading and scan failure states |
| `/trades` | Portfolio | Pro/Elite or admin | Separate open exposure from paged history; inspect trade journey; close flow requires TOTP; loading, locked, empty, error and disconnected states |
| `/performance` | Research | Pro/Elite or admin | Inspect stored trade outcomes, grades, equity and version/regime summaries; backtest action is separate; empty and loading states |
| `/content` | Research | Elite or admin | View tiered content; loading/empty/error states |
| `/profile`, `/settings`, `/account` | Account | signed-in user or account-entry route | Profile, identity, verification, password recovery, session and security controls; generic auth failures and disabled feature states |
| `/engine`, `/india`, `/coins`, `/users`, `/system`, `/audit` | Administration | admin only | Operate engine/India scopes, manage universe/users, inspect diagnostics/audit; role-gated actions, explicit mutation result, empty/error states |
| `/pricing` | Account | public/signed-in | Compare configured product tiers; no checkout or billing claim unless service is enabled |
| `/demo/*` | Demo | public isolated mock context | Inspect mock pages and tier gates; explicit demo label; no real account or broker mutation |

Unknown signed-in routes return to Overview. Deep links are retained by the router. Tier checks in the UI are presentation only; API authorization remains authoritative.

## Screen hierarchy and records

- **Overview:** system mode/connectivity and source freshness first; then account/trade summaries and prioritized signals. Each summary drills into its source page. A live socket with no recent payload is labeled stale rather than current.
- **Signals:** discovery controls, active/watching/idle groups, then one selected detail panel with grade, rationale, price levels, timestamps and trace. Signal freshness and tier delay remain visible.
- **Trades:** active exposure precedes closed history. Open/closed status, realized/unrealized P&L, currency/units, direction and source are explicit. Close controls are visually isolated and confirmed with step-up authentication.
- **Performance:** stored closed-trade outcomes and source record counts; chart and breakdowns follow summary. Results are historical records, not a promise or a validated strategy claim. Strategy-quality validation is a separate research gate.
- **Administration:** operational health and active warnings precede low-priority diagnostics. User, universe, engine and India actions remain in separate routes; audit records are discoverable separately.

## Risk interaction prototypes (textual state contract)

| Action | Before | In progress | Success | Failure / recovery |
|---|---|---|---|---|
| Manual close | Show symbol, direction, size and current exposure; require explicit confirmation and TOTP where configured | Disable duplicate submit; preserve position context | Refresh authoritative position/history and show audit-backed result | Keep position visible, show safe error, allow retry only after state refresh |
| Engine scan / backtest | Explain scope and paper/research context; admin/tier gate | Show running state and prevent duplicate launch | Refresh result and timestamp | Preserve prior result; show error without implying scan completed |
| Universe/config change | Show current value and proposed value; warn about execution impact | Submit one versioned mutation; no optimistic success | Display saved state/version and audit event | Keep saved value, show validation or server error |
| User/session mutation | Identify affected account/session and irreversible scope | Require role authorization and confirmation | Refresh list and audit evidence | Do not hide target row; display authorization or conflict response |
| Password/security recovery | Generic public acknowledgement; do not reveal account existence | Disable repeated submit while request is pending | Explain next safe step without exposing token | Preserve generic public response; never log credential or reset token |

## Responsive and accessibility rules

- Reference widths: 1440px desktop, 1024px tablet, 768px compact layout, 390px and 320px mobile. Sidebar becomes bottom navigation with a keyboard-operable More sheet on small screens.
- Wide history remains horizontally scrollable only when the row is still usable; otherwise use focused record/detail views. Critical actions must remain discoverable without hover.
- Sortable table headers are buttons. Clickable rows accept Enter and Space. Focus indicators, labelled status, dialog focus handling and form error association are required.
- `prefers-reduced-motion: reduce` suppresses nonessential animation and smooth scrolling.
- Values identify currency/units and signs. State is conveyed by text/icon as well as color. WCAG 2.2 AA remains the audit target, not a claim of completed certification.

## Reference capture gate

Capture Overview, Signals, Trades, Performance, System/Admin, Settings/Security and one mobile view at 390px after the exact build is served in a browser. Review free, Pro, admin and demo journeys. No approved screenshots are attached to this local candidate; SE-07-012 stays planned until a human review accepts those captures.
