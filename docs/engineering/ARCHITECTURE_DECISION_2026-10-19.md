# ADR-002 — Retain AWS backend root, React in dashboard/, GitHub Actions disabled

**Decision date:** 2026-10-19. **Status:** Accepted by owner in conversation; incorporated into this local candidate, not deployed.

- Canonical repo is existing `vishalkool166/crypto-engine`, preserving its Git history.
- AWS remains the only Python engine; root-level import paths, service names, Dockerfile, Compose, database mount and scheduler are preserved.
- Editable frontend is merged from `vishalkool166/crypto-engine-frontend` into `dashboard/`; old backend `frontend/` compiled bundle is kept intact for compatibility.
- Cloudflare Pages hosts only `dashboard/dist`, using native Git deployment. Backend API/WS stays at the configured AWS domain.
- Owner declines GitHub Actions. Manual scripts and checked deployment documentation replace workflow definitions; no `.github/workflows` exists in release.
- Existing Outfit/Geist typography and original light/dark CSS tokens remain unchanged; navigation, layout and pagination edits are allowed after testing.
- Resend is restricted to account setup and security, with the provider adapter disabled until account-recovery lifecycle and tests are complete.
- The previously generated nested `backend/` + `frontend/` candidate is *not* the delivery architecture; it served only as a selectively merged engineering source.

**Consequences:** Engineering ledger items mentioning backend relocation or GitHub CI require interpretation under this decision. The previous candidate's root multi-stage Docker build is deliberately not used. Do not claim either deployment verified until actual AWS/Pages integration testing.
