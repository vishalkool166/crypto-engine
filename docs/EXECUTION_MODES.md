# Paper and live execution

Paper uses the Binance USDⓈ-M demo exchange, not a local simulated balance.
Live uses the Binance USDⓈ-M production exchange. Real orders are possible in live.

## Setup

The default installation starts with `TRADING_MODE=paper`. To make the live option
available, configure these values on the server:

```dotenv
ENGINE_ENABLED=true
TRADING_MODE=paper
BINANCE_DEMO_API_KEY=your_demo_key
BINANCE_DEMO_SECRET=your_demo_secret
BINANCE_API_KEY=your_live_key
BINANCE_SECRET=your_live_secret
SIGNAL_ENGINE_ALLOW_LIVE_TRADING=I_UNDERSTAND_REAL_ORDERS
TOTP_SECRET=your_base32_authenticator_secret
```

Use a dedicated Binance futures account in one-way position mode, with only the
API permissions needed for the engine. Do not enable withdrawals for the key.
Both accounts must be reachable with the configured credentials. Keep API keys
and the TOTP secret server-side; they never belong in Vite/Pages browser variables.
Recreate the engine container after changing `.env`.

To create a new authenticator secret locally on a trusted machine with the Python
requirements installed:

```bash
python -c 'import pyotp; print(pyotp.random_base32())'
```

Add it manually as a time-based, six-digit, 30-second code in your authenticator.
Store it privately in `.env` as `TOTP_SECRET`. Keep the server clock synchronized.
Never paste a real secret or authenticator code into support chats or source control.

## Switch from admin

1. Click **PAPER / Change** in the admin header or execution panel.
2. Choose the other environment.
3. Read the account and restart requirements.
4. Type `ENABLE LIVE TRADING` or `RETURN TO PAPER`, exactly as shown.
5. Enter a fresh authenticator code and confirm.

The server requires a valid Google operator session, same-origin CSRF validation,
rate limiting, and a valid TOTP code protected against reuse through Redis.
Both switch directions require TOTP. Five attempts are allowed per five minutes.

## What the transition does

The running process pauses exchange writes and new execution operations. It
refuses the switch when an execution operation is in progress, when any local
trade is active/pending/needs reconciliation, or when the order journal has an
unresolved intent. It then checks **both accounts** for positions, ordinary
orders, conditional orders, and one-way position mode. A failed or malformed
account response blocks the switch.

It writes an audit event and saves `operator_execution_mode` in
`database/runtime_state.json`. The process then exits gracefully. Docker restarts
it with new exchange clients, account credentials, and WebSocket subscriptions.
The browser polls the service and reloads after the new mode becomes available.

No running process changes its account connection in place. No funds are moved.
No trades or orders are closed automatically by this control. Resolve positions
and orders first. Switching modes is not an emergency-stop control.

## Source of truth and restarts

`TRADING_MODE` is the initial default. Once an authenticated switch is saved,
`database/runtime_state.json` is authoritative. Ordinary container restarts retain
that selection; changing `.env` alone does not override it. Do not delete the
runtime file: it also contains risk state. A persisted live selection without
its credentials, opt-in, or TOTP configuration makes startup fail closed.

`MODE_SWITCH_RESTART=true` is set inside the included Compose service. Do not set
it for an unmanaged `uvicorn` process: the process must have a restart supervisor.
Keep exactly one API worker and one engine instance.

The new `execution_mode` column labels each new trade. Old rows remain `legacy`.
The historical performance screens show the stored ledger across environments;
inspect the Environment column in Trades & journey. Runtime sizing metrics and
closed-trade exchange synchronization use the active environment only. Unlabelled
legacy closed trades are excluded from those execution calculations.

If switching is blocked, inspect its reason, local trades, the order journal in
Stored data, and the exchange account directly. Never clear risk state or delete
an uncertain order intent merely to force the switch.

## Verification limits

Tests cover authorization, preflight failures, persistence, stale-mode rejection,
write guards, and restart restoration using fake exchange clients. They do not
certify exchange availability, strategy profitability, live fills, or your account
configuration. This build does not activate live trading without your server opt-in
and authenticated confirmation.

API references:
[Binance futures trade endpoints](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/trade).
