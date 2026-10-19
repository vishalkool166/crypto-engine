# Changelog

## 1.0.0-rc1 — 2026-10-19 (source candidate, not production-certified)

This is a **release candidate**, not approval to merge to the AWS auto-deploy branch or to place live orders.

- Full-dataset admin user search and audit search/status/action filtering performed before pagination, with bounded queries, stable ordering and new isolated SQLite regression tests.
- Admin list screens use the shared pagination component; User table scrolls when space is limited. Original light/dark CSS variables and Outfit/Geist fonts remain unchanged.
- Added a page-level React error boundary that avoids displaying internal exception details to users.
- Added private no-store cache headers on auth/API responses and an optional, unit-tested session Origin guard. Guard remains **off by default** until staged browser tests.
- Added independent Cloudflare build environment validation for configured HTTPS API/WSS endpoint origins; no credentials included in frontend builds.
- Added integrity-checked **restore-to-new-file-only** SQLite operator utility and recovery tests.
- Added `SECURITY.md`, `CONTRIBUTING.md`, manual task-ledger validator and machine-readable v1 candidate release gates.
- Existing trading algorithms, Docker/Compose root paths, settings/config/scheduler/credential logic, GitHub repo identity, and original frontend palette retained.

## 0.2.0 — 2026-10-19 (engineering candidate; not deployed)

- Unified source layout around existing `crypto-engine` AWS root with editable React `dashboard/` for Cloudflare Pages.
- Retained AWS static `frontend/` fallback; removed GitHub Actions workflows as directed.
- Repaired initial server pagination for signals/trades, shared DataTable sorting, Overview/navigation hierarchy, private PWA caching and hard-coded frontend-to-backend API routing.
- Security-only Resend delivery adapter provided but **inactive**. Existing account credential and TOTP workflows unchanged.
- Added local verification scripts and two-host AWS/Cloudflare rollout playbook.
