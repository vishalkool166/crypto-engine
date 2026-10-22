# Signal Engine 3.3 — Studio frontend redesign

This release redesigns the **existing** public and private React applications. It preserves the 3.2 Binance connection, Groq configuration, four-strategy backend, data contracts, execution-mode authorization, and operator authentication. There are no new environment variables, external accounts or data providers.

## What changed

- Restored the **original 3-bar mark from 3.1**, using the same CSS bar proportions in shared navigation. Updated favicon SVG and both PWA SVG/PNG icon sizes. Removed the 3.2 diamond and the `S/E` login sculpture.
- Rebuilt the public homepage as an ivory-and-ink editorial experience with a responsive, keyboard-accessible interactive four-strategy drawing. Illustration curves are **not** Binance prices and are clearly labeled. Market observations and signal tables still come from the real API.
- Added GSAP sequencing, scroll-scrubbed headline/graphic reveals and step-driven visual emphasis to the public story. All new storytelling motion is optional, and reduced-motion preferences are respected. Admin trade controls and numbers do not depend on animation.
- Restyled the private workspace, operator status header, strategy rail, order-mode controls, research surfaces and Google login with a restrained neutral design. The strategy control backend remains unchanged.
- Preserved existing shadcn/Radix-style primitives. No replacement component framework, font CDN or additional runtime dependency.

## Scope and limitations

This release changes frontend presentation and brand assets, not the trading strategy formulas or execution permissions. All four strategies remain in the existing unified pipeline. Production build and authenticated browser validation still need to be run in the actual deployment environment, because npm packages and backend credentials are unavailable in the current build environment. React source parser checks, CSS grammar checks and focused backend regression tests have been run, but are not substitutes for deployment acceptance tests.

## Deployment

Use the repository's existing build/deploy steps and keep the already-configured `.env`. Do not overwrite real environment files with `.env.example`. Frontend theme defaults to light for new visitors, with saved user light/dark choices respected. Cached PWA service workers may require a refresh for the new icon to appear.

## Operator acceptance checklist

1. `cd dashboard && npm ci && npm run build`: both public and admin builds complete without errors.
2. Open the public pages at 390px, 768px, 1024px and desktop widths; verify navigation, interactive illustration, page flow and absence of horizontal overflow.
3. Open authenticated admin routes; verify the four strategy controls, trade charts, order mode, TOTP dialog, research comparison and Google login.
4. Test keyboard tab order, focus visibility and `prefers-reduced-motion: reduce`.
5. Verify favicon and installed PWA icons show the original three-bar symbol after cache refresh.
6. Verify the exchange remains in **paper** mode following deployment. This frontend-only release does not enable live trading.

No claims of profitable strategy performance, Awwwards judging outcome or verified production screenshots are made by this release.
