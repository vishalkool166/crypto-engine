# Release verification · Signal Engine 3.4

**Source changes:** Four strategy evaluators; one main scanner; scanner/market state reporting; signal expiry; operator health telemetry; decision evidence; trade journey, public methodology and 3.4 styling.

**Checks completed locally**

- `python -m compileall -q`: Python module syntax passes (Python 3.13 packaging environment).
- TypeScript compiler AST parsing: all 28 dashboard TypeScript/TSX source files parse without syntax diagnostics.
- PostCSS parsing: `dashboard/src/styles.css` parses without CSS syntax errors.
- `PYTHONPATH=. pytest -q tests/test_3_4_improvements.py tests/test_unified_strategy_pipeline.py tests/test_strategy_replay.py tests/test_strategy_lab_v3.py`: **41 passed** (includes structure-level, condition-evidence, historical isolation, retention and existing research regression checks).
- Broader suite without two collection-blocked modules: **170 passed, 3 failed, 2 errors** in the environment. Remaining failures/errors arise from unavailable/incomplete `slowapi`, `pyotp` and `redis` packages. This result **is not a full green suite**.
- Full test collection is blocked by `slowapi` missing. Installing from the local configured Python index was unsuccessful.

**Checks still required after installation:**

- Frontend `npm ci && npm run build` and real browser UI/mobile/a11y testing; the local npm cache is missing packages, and an online install failed.
- Runtime validation of the `/system/telemetry` API against the actual host (including Docker and EC2 access permissions).
- Browser verification of Radix portal overlay/drawer stacking, chart interactions and light/dark themed nested components.
- Authenticated Binance demo orders, order reconciliation and Groq API availability using the user's own existing server credentials.
- Strategy-level profit and target probability claims: none are validated.

No live trades, authentication credentials, fabricated market observations or private account values are contained in the release ZIP.

**Documentation/release packaging pass:** Canonical guides and public contribution/security policies were added; previous draft/upgrade narratives and source-based preview images were removed. The default Compose stack no longer requires a Cloudflare token; Cloudflare remains available through the documented optional overlay. CI files are provided but have not been executed on GitHub in this packaging environment.

**Final documentation verification:** all local Markdown links resolved; GitHub workflow and issue template YAML parsed; the focused 3.4 test subset passed **41/41** again, and Python compileall passed. Docker Compose configuration is valid YAML but was **not** run with a Docker installation here. The release manifest is regenerated at packaging time and verified against the extracted archive.
