# Operator console guide

The admin site is a private workspace. Sign-in requires Google and a verified email listed in `ADMIN_EMAILS`. It does not provide public registration, customer accounts, subscriptions, or billing.

## Pages

| Page | Use |
| --- | --- |
| Overview | Service snapshot, recent signals, trade summary, and current execution environment. |
| Signals | Browse stored signal decisions, grades, factors and outcomes. Open a signal to inspect the persisted decision trace. |
| Trades & journey | View active-account positions and stored closed trades, inspect the execution environment, open Trade Journey snapshots, and close a position with TOTP. |
| Performance | Review the recorded equity curve, total P&L, win rate, signal-grade and instrument outcomes, results by system version and regime, numeric factor-score observations, recent signal history and closed trades. Use the Research link for cached-data backtests. Results describe stored history, not a promise about future trades. |
| Crypto universe | Inspect configured crypto instruments and pause or resume an existing instrument without changing its strategy parameters. |
| Indian markets | Inspect the existing operator-only market status, opening-range research, signals, and readiness when Angel One credentials and data are available. |
| Research | Run the supported cached-data replay, inspect the research evidence gate and stored replays, and access the private research assistant when configured. |
| Stored data | Inspect all SQLite application tables, including historical and otherwise unclassified tables. Search and export the displayed page as CSV. This view is read-only and masks secret-like columns. |
| System health | Inspect dependency readiness, scan telemetry, rejection stats, engine diagnostics, relative strength, recent decision traces, and filter analysis. |
| Telegram | Inspect polling/webhook connection state, command results and sender configuration, reconnect commands, and follow the command reference. |
| Audit trail | Review recorded operator and security actions. |
| Settings | Confirm origins, allowlisted admin email, session lifetime, execution mode, strategy version and whether credentials are configured. Secret values are not returned. |

## Performance and trade journey

The Performance page uses persisted trade and signal outcomes. Empty or partial history should appear as empty/partial; do not infer zero risk or a profitable strategy from missing records.

Trade Journey is available from both open and closed trade tables. It plots stored price snapshots with the saved entry, stop, target, and exit markers where available. Telegram supports `/journey TRADE_ID`; use the ID shown by `/trades` or the admin trade table. A journey with no points means there are no stored snapshots for that trade; it does not reconstruct missing history.

## Data and privacy

Use the Stored data page to identify which records exist before changing or migrating the schema. Search, pagination, and CSV export are for review. The API is operator-authenticated, but downloaded CSV and server backups remain sensitive. See [DATA.md](DATA.md) for the retained groups, redaction behavior and backup procedure.

## Theme

The light/dark control saves the choice in the browser. If a page appears to keep the prior theme after an upgrade, hard-refresh the site once so the current stylesheet replaces cached assets. Both color schemes use shared semantic tokens so panels, fields, borders, menus, tables and text change together.

## Execution environment

Use the mode control in the header or Overview. Both switch directions require TOTP, explicit confirmation, flat local/exchange accounts, and a managed restart. See [EXECUTION_MODES.md](EXECUTION_MODES.md).
