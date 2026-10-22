# Signal Engine 3.2 — Atelier Visual System

**Scope:** Frontend redesign on top of the existing 3.1 unified strategy backend. No trading algorithm, API contract, authentication flow, database migration, environment-variable name, or execution safety switch has been modified as part of this design release.

## Art direction

Concept: **An intelligence instrument, not a crypto template.** Visual identity pairs restrained charcoal/verdigris with one intentional lime signal color, gigantic editorial typography, a serif accent, precise monospaced instrumentation, high contrast, and generous negative space.

### Public site
- New editorial landing experience with large expressive headline and clear research positioning.
- Bespoke responsive **Signal Field** SVG: four selectable independent strategy paths converging at one risk governor. This is **architecture art, not price prediction or market data**.
- Three illustrated explanations of market observation, strategy interpretation and risk governance.
- Market evidence numbers, charts and signal records continue to be sourced from existing `/api/v1/public/overview` endpoint. No new fabricated trading statistics.
- Methodology, signal, performance and status screens receive editorial masthead treatment and revised palette.
- Scroll storytelling powered by existing GSAP/ScrollTrigger; CSS-only generative geometric motion for system field.

### Admin
- New private console visual identity, fixed navigation system, stronger information hierarchy, and revised contrast.
- Original operator overview now begins with a runtime-derived status masthead and existing scan action; no fake P&L and no invented account state.
- Strategy Board, candlestick area, decision inspector, Strategy Lab, research evidence and actual order controls are reused and reskinned.
- Execution-mode control remains exactly the existing TOTP-protected component; per-strategy permissions remain persistent.
- Operator sign-in gains custom graphic sculpture while preserving existing Google SSO action and server allowlist.

## Interaction details
- Public homepage tabs switch among four visually different pathways with semantic buttons and `aria-pressed`.
- Honors `prefers-reduced-motion` by disabling the CSS kinetic field and GSAP animation (GSAP hooks already guard reduced-motion).
- Mobile typography and layouts have explicit breakpoints at 1350, 1100, 800, and 520 px.
- Keyboard skip links added to public and private shells.
- Buttons and links retain visible focus outlines; sidebar and admin status retain explicit text labels.
- No external fonts, paid design assets, image hosting, or API keys added. Existing Outfit dependency retained and system serif/monospace used.

## Major edited files

- `dashboard/src/features/public.tsx` — public homepage structure and content hierarchy.
- `dashboard/src/components/SignalField.tsx` — new interactive system illustration.
- `dashboard/src/features/overview.tsx` — real-data operator command masthead.
- `dashboard/src/App.tsx` — login, navigation metadata, skip links.
- `dashboard/src/components/workspace.tsx` — custom brand symbol.
- `dashboard/src/components/WorkspaceMotion.tsx` — editorial animation choreography.
- `dashboard/src/styles.css` — responsive art direction, component skin, modes.
- `dashboard/index.html` — metadata.
- `dashboard/package.json` and `dashboard/package-lock.json` — front-end version 3.2.0, no dependency added.

## Notes / limitations

- `docs/design-previews` screenshots are **browser-rendered, source-based reconstructions**, NOT authenticated screenshots of the running application. They use no real account details and intentionally blank/no-data states.
- Source review and TS syntax checks are not substitutes for `npm ci && npm run build` or human visual QA. Run the full build after dependencies are available.
- Neither this visual release nor the underlying 3.1 research strategy tests establish trading profitability.
