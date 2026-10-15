# Engineering decisions and deferred choices

## ADR-001 — Keep the Python execution backend
**Decision:** Preserve Python/FastAPI and exchange-integration modules instead of porting the execution system to a UI builder.
**Reason:** A forced rewrite introduces correctness risk and would invalidate test and operational assumptions.
**Review trigger:** A concrete scaling or deployment requirement with comparative measurements.

## ADR-002 — Uncertain order state means no repeat submission
**Decision:** Write durable order intent before sending; treat ambiguous outcomes as reconciliation-required.
**Reason:** Network errors cannot distinguish rejection from acceptance; retries can create duplicate exposure.
**Limitation:** Not exactly-once execution. Broker state and protective orders must be checked.

## ADR-003 — Strategies cannot self-certify profitability
**Decision:** Freeze the original 18-coin settings, evaluate candidates on dated training windows, and use unseen holdouts for evaluation only.
**Reason:** Repeated parameter selection on the same history produces optimistic bias.
**Limitation:** This runtime cannot execute a complete 18-coin historical replay.

## ADR-004 — One shared UTC trading-session definition
**Decision:** Live sizing/scoring and offline replay use `engines/core/sessions.py`.
**Reason:** Independent time-window implementations can cause signal/live mismatch and false rejections.
**Limitation:** UTC-based windows are not DST-localized exchange sessions. Changing them requires a research study.

## ADR-005 — No silent assumptions for legacy tuning fields
**Decision:** Retain `sl` and `tier` values in `COIN_CONFIG` without wiring them into trading until their semantics can be justified and tested.
**Reason:** Arbitrarily treating `sl` as a mandatory stop can change liquidation and net risk.
**Review trigger:** Verified original optimization definition plus risk analysis.

## ADR-006 — Source documentation, not pass-by-pass marketing
**Decision:** Canonical README and stable references under `docs/`; verification evidence lives in `docs/STATUS.md`.
**Reason:** Maintainers need current runbooks and contracts, not overlapping historical status reports.
**Attribution:** The code has been AI-assisted. Documentation should describe tested behavior truthfully, not imply an invented team or independent review.
