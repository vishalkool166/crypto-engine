# Telegram setup and commands

Outgoing scan messages and incoming commands are separate paths. Release 2.1
uses **outbound polling** by default. The server asks Telegram for updates over
HTTPS, so incoming commands no longer depend on a Cloudflare inbound webhook.
The Telegram service starts even when `ENGINE_ENABLED=false`.

## Configure polling

1. Create or select your bot with [BotFather](https://t.me/BotFather).
2. Open a private chat with the bot, press Start, and send `/start`.
3. In the server `.env`, set:

   ```dotenv
   TELEGRAM_TRANSPORT=polling
   TELEGRAM_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_numeric_chat_id
   TELEGRAM_ALLOWED_USER_IDS=your_numeric_sender_id
   ```

4. Use the exact destination chat ID. A group ID is usually negative; the allowed
   sender ID is the person's positive numeric `from.id`, not that group ID.
5. Recreate the engine container with `docker compose up -d --build --force-recreate
   signal-engine`. A plain container restart does not apply changed env values.
6. In admin, open Telegram operations. Confirm polling and Connected. Startup
   removes a stale webhook without dropping pending updates, registers the command
   menu, and starts getUpdates. Do not run another bot client or call getUpdates
   manually while this service is polling; Telegram permits only one consumer.
7. Send `/ping`. Its reply confirms that a command reached this server and that
   the server could send a reply. Then try `/help` and `/health`.

To discover IDs before setup, use the private chat's `from.id` / `chat.id` in a
getUpdates response from Telegram's Bot API, or a trusted ID lookup bot. Never
share a token-bearing URL or full raw response publicly. Stop other polling
consumers before inspecting getUpdates, then recreate the engine afterwards.

## Group commands

Add the bot to your private group. With BotFather privacy mode enabled, send an
explicitly addressed command such as `/help@YourBotUsername`. Configure the
negative group chat ID and allowlist the real sender's numeric user ID. Messages
sent as an anonymous group administrator have no ordinary sender identity and
are intentionally not accepted as authenticated operator commands.

## Diagnostics

Admin → Telegram operations shows transport, connection, last transport error,
last received update, and last command result:

| Result | Meaning / next action |
| --- | --- |
| `completed` | The handler returned; check the reply in the configured chat. |
| `chat_mismatch` | Update reached the server from a different chat. Correct TELEGRAM_CHAT_ID. |
| `sender_not_allowed` | Update reached the server from a sender outside TELEGRAM_ALLOWED_USER_IDS. |
| `rate_limited` | The command budget was exceeded. Wait a minute. |
| `handler_failed` | Inspect engine logs for the failing command. |
| No received update | Verify the bot/token, polling connection, Redis, and any competing bot consumer. |

There is a 12-command-per-minute chat budget and a separate one-minute budget for
expensive scan/backfill/backtest tasks. Long-running work can delay later commands
until it completes. Commands are claimed before effects to prevent duplicate
execution. A process interruption during a claimed operation may require operator
inspection; automatic replay of an uncertain operation is deliberately avoided.

A connected transport is not proof that the exchange or strategy is healthy.
`/health` checks dependencies and scan freshness. `/scan` is unavailable when
execution is disabled or transitioning. Mode switching is available only in the
Google-authenticated admin app with TOTP; `/mode` remains read-only.

## Optional webhook mode

Set `TELEGRAM_TRANSPORT=webhook` and configure a separate `WEBHOOK_SECRET`.
`ADMIN_APP_ORIGIN` must point to your admin Pages hostname. Deploy its
`dashboard/functions/webhook/[[path]].js` with `APP_TARGET=admin`.
The registered URL is `https://admin.example.com/webhook/telegram`.

Use Reconnect commands after deployment. Confirm that the registered URL matches
and Telegram reports no recent delivery failure. The backend checks Telegram's
secret header, the configured chat, and the sender allowlist. Redis must be healthy.
Do not place an interactive Google/Cloudflare Access login challenge in front of
this webhook path: Telegram cannot complete it. Using polling avoids that inbound
dependency entirely. A public Pages project deliberately rejects webhooks.

## Command reference

| Command | Purpose |
| --- | --- |
| `/start`, `/help` | Show the operator menu. |
| `/ping` | Confirm inbound command and outbound reply delivery. |
| `/health` | Database, Redis, streams, and scan freshness. |
| `/status`, `/mode` | Engine summary and active environment; no mode mutation. |
| `/scan`, `/queue` | Guarded manual scan and current signal queue. |
| `/trades`, `/position ETH` | Active-account positions and detailed position context. |
| `/journey 42` | Recorded path for trade 42; use the trade ID from `/trades`. |
| `/balance`, `/profit` | Active exchange balance and recorded profit summary. |
| `/coin ETH`, `/btc`, `/funding`, `/fear`, `/brief` | Market research. |
| `/pnl`, `/daily`, `/stats`, `/grade`, `/history`, `/performance` | Stored performance summaries. |
| `/backtest ETH`, `/backfill ETH`, `/candles` | Cached-data research and candle coverage. |
| `/india`, `/orb`, `/indianstats` | Indian-market integration when configured. |
| `/pending`, `/discard 5`, `#5` | Stored content drafts. |

Messages preserve directional/status emoji, concise sections, and a timestamped
active-mode footer. Dynamic content is escaped before Telegram HTML formatting.
Historical trade summaries may include legacy or other-environment records; the
footer names the active service environment, not a certification of old records.

Bot API reference: [Telegram Bot API](https://core.telegram.org/bots/api).
