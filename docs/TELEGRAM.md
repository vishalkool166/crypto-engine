# Telegram operator bot

The Telegram bot sends scheduled signal notices and accepts private operator commands through a Cloudflare Pages Function. Outgoing messages and incoming commands use separate paths: a bot that can send scan alerts may still have a broken or misrouted webhook.

## What you need

- A Telegram bot token from [@BotFather](https://t.me/BotFather).
- The destination chat ID. Use your private chat with the bot for the simplest setup, or a private group if needed.
- The numeric Telegram user ID allowed to issue commands. For a private chat, the chat ID and user ID are often the same; set both values explicitly anyway.
- Redis running and healthy. The webhook uses Redis to deduplicate updates and enforce command budgets.
- The admin Pages project deployed with `APP_TARGET=admin` and the `/webhook/*` Function route enabled.

## Configure it

1. In Telegram, create the bot with `@BotFather` and copy the token into `TELEGRAM_TOKEN` on the server.
2. Open a private chat with the bot and press **Start**. Send a message so Telegram has an update to report.
3. Find the numeric sender ID from the `from.id` field in Telegram's `getUpdates` response, or use a trusted ID lookup bot. Do not paste the bot token, `getUpdates` URL, or response into a public chat.
4. Set `TELEGRAM_CHAT_ID` to the exact destination chat ID. For a group, it is usually a negative number.
5. Set `TELEGRAM_ALLOWED_USER_IDS` to one or more numeric sender IDs, comma-separated. Group chats require this setting; the handler ignores group commands when the list is empty. Restrict it to the people who should control the private engine.
6. Generate a separate webhook secret, for example with `openssl rand -hex 32`, and set it as `WEBHOOK_SECRET` on the server. Keep it distinct from `SESSION_SECRET` and `ORIGIN_PROXY_SECRET`.
7. Set `ADMIN_APP_ORIGIN` to the admin Pages custom domain. The bot registers `https://admin.example.com/webhook/telegram`; the public Pages project intentionally refuses webhook requests.
8. Confirm Redis is healthy, restart the backend after changing `.env`, sign in to the admin console, and open **Telegram**.
9. Select **Register webhook**. This calls Telegram's `setWebhook` and `setMyCommands`. The screen reports the registered URL, pending updates, latest provider error, allowed-sender configuration, and whether command registration succeeded.
10. Send `/health` in the configured chat. Then send `/help` and `/trades`. A scan notification alone only proves that outbound Telegram delivery works.

## Commands

| Command | What it does |
| --- | --- |
| `/help` | Lists the operator commands. |
| `/status` | Shows engine status and paper mode. |
| `/health` | Checks service dependencies and data freshness. |
| `/scan` | Starts a guarded manual scan. |
| `/queue` | Shows the current signal queue. |
| `/coin ETH` | Shows analysis for a configured coin. |
| `/btc` | Shows the Bitcoin market overview. |
| `/funding` | Shows funding rates. |
| `/fear` | Shows the fear and greed reading. |
| `/trades` | Lists open paper positions and their trade IDs. |
| `/position ETH` | Shows a position's current details. |
| `/journey 42` | Summarizes stored price snapshots for trade ID 42. Use the ID shown by `/trades` or the admin Trades page. |
| `/balance`, `/profit` | Shows demo account balance and recorded profit summary. |
| `/pnl`, `/daily`, `/stats`, `/grade`, `/history`, `/performance` | Shows recorded performance summaries. |
| `/backtest ETH` | Runs the supported cached-data research replay. |
| `/backfill ETH`, `/candles` | Checks or backfills research candle data. |
| `/mode` | Reports configured mode. This command cannot switch to live trading. |
| `/india`, `/orb`, `/indianstats` | Shows Indian-market status, opening-range levels, and recorded statistics when that integration is configured. |
| `/brief` | Sends the market briefing. |
| `/pending`, `/discard 5`, `#5` | Reviews or discards a content draft when content storage is enabled. |

Commands that trigger expensive work are rate-limited. The release remains paper-only.

## If commands receive no response

1. In Admin → Telegram, confirm **Webhook destination check** says the registered URL matches the expected admin URL. If it reports `url_mismatch`, fix `ADMIN_APP_ORIGIN` and register again.
2. Confirm the Pages **admin** project's `APP_TARGET` is `admin`. The public project's `APP_TARGET=public` and rejects webhook traffic by design.
3. Confirm Pages Functions are deployed from `dashboard/functions/`, with `/webhook/*` included in `dashboard/public/_routes.json`. Direct Upload without Functions will not proxy commands.
4. Check that `TELEGRAM_CHAT_ID` matches the chat receiving commands. For groups, set `TELEGRAM_ALLOWED_USER_IDS` to the sender's numeric `from.id` value, not the negative group chat ID.
5. Check Redis health. If Redis is unavailable, the handler returns HTTP 503 rather than executing a command without deduplication and rate limiting.
6. Inspect the Telegram page's pending update count and latest delivery error, then inspect backend logs for the rejected chat/sender or command failure. Never log or share the bot token or webhook secret.
7. After correcting configuration, register the webhook again and retest `/health`, then `/trades`, then `/journey <id>`.

## Operational notes

- The webhook verifies Telegram's `X-Telegram-Bot-Api-Secret-Token` header.
- The bot accepts text messages in the configured chat only. It checks sender IDs before dispatch.
- A global per-chat command budget and a separate expensive-command budget limit abusive repeats.
- Outbound formatting preserves emoji and escapes dynamic text before applying Telegram's supported bold, italic, and code markup.
- Telegram delivery cannot prove a trade was executable or profitable. All trade summaries are marked as paper records.
