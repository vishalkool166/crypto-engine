# Rebuild decisions

- Two browser-facing applications: public and Google-authenticated operator.
- One dashboard source, two build targets. No backend-served frontend bundle.
- Public outputs include model levels, scores, timestamps, and sanitized traces. Account records and sizing remain private.
- Customer signup, pricing, subscription, and billing functionality removed.
- Google account allowlist plus subject pinning; opaque revocable sessions.
- Paper-only startup and no live-switch or Docker-purge HTTP routes.
- Existing Indian-market engine retained privately. Existing ML/vector research source retained without automatic model promotion.
- Public PWA retained. Admin PWA deferred; authenticated responses never cached.
- SQLite preserved; new operator tables added without deleting historical customer records.
- Two Pages upstream projects, one Worker Route gateway, one AWS Tunnel origin. No third custom app/API hostname.
- License remains the owner’s decision. No license inferred or added.
