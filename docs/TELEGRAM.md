# Telegram alerts and commands

Telegram signal alerts are outgoing notifications. Commands are incoming
updates sent to your server through Telegram's webhook. Seeing scan alerts alone
does not verify that the webhook path is working.

## Configure the bot

1. Create a bot using [BotFather](https://t.me/BotFather). Keep the bot token
   private.
2. Open a private chat with the bot, press **Start**, and send `/start` once.
3. In the server `.env`, set:

   ```dotenv
   TELEGRAM_TRANSPORT=webhook
   TELEGRAM_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_numeric_chat_id
   TELEGRAM_ALLOWED_USER_IDS=your_numeric_sender_id
   WEBHOOK_SECRET=your_random_secret
   ```

   Generate the webhook secret independently from your Google session and proxy
   secrets. Keep it within Telegram's allowed characters: letters, digits,
   underscore, and hyphen.
4. By default, Telegram registers
   `https://<your-admin-host>/webhook/telegram`. Set `ADMIN_APP_ORIGIN` to your
   chosen admin origin. If you are hosting public only, set
   `TELEGRAM_WEBHOOK_URL=https://<your-public-host>/webhook/telegram`.
5. Make sure the selected frontend proxy sends `/webhook/telegram` to FastAPI
   without an interactive sign-in page or bot challenge. Cloudflare Pages users
   must deploy the `dashboard/functions/` files; Caddy users can use
   `deploy/Caddyfile.example`.
6. Recreate the service to apply the environment values:

   ```bash
   docker compose up -d --build --force-recreate signal-engine
   ```

7. Send `/ping`. A reply means the update reached the application and the app
   replied through Telegram. Then try `/help` and `/health`.

For a group, set `TELEGRAM_CHAT_ID` to the group's negative chat ID and
`TELEGRAM_ALLOWED_USER_IDS` to the operator's positive sender ID. Telegram
privacy mode supports commands addressed to the bot, such as
`/help@YourBotUsername`. Anonymous group administrator messages have no
allowlisted sender identity and are rejected.

## Available commands

| Command | What it does |
| --- | --- |
| `/start`, `/help` | Show the concise operator menu. |
| `/ping` | Verify incoming command and outgoing reply delivery. |
| `/health` | Check database, Redis, streams, and scan freshness. |
| `/status` | Show engine readiness and current execution mode. |
| `/scan` | Request a guarded manual scan. |
| `/trades` | Show positions on the active exchange account. |
| `/position ETH` | Show position details for an instrument. |
| `/journey 42` | Show the recorded price path for a trade ID. |
| `/performance` | Show saved trading results. |
| `/india`, `/orb`, `/indianstats` | Show Indian-market signal and performance data. |
| `/coin ETH`, `/brief` | Request a concise market research summary. |
| `/backtest ETH` | Run a cached-data research replay. |

The command menu is intentionally focused. It does not include draft-publishing
commands. `/scan` is unavailable when the engine is disabled or transitioning;
Telegram cannot switch paper/live mode. Use the authenticated private operator
interface and TOTP for execution-mode changes.

Messages use concise sections, direction and outcome markers, and an active-mode
timestamp. Signal and trade data in Telegram is private to the configured chat
and allowlisted senders. Treat it as operational output, not a performance
guarantee.

## Verify and troubleshoot

- Use Telegram's Bot API `getWebhookInfo` to confirm the registered URL and look
  for recent delivery errors. Never share a token-bearing Bot API URL or response.
- Check `docker compose logs --tail=150 signal-engine` for webhook registration
  failures and command handler errors. Tokens and raw authenticated URLs should
  never be pasted into tickets or public logs.
- Check that the webhook host points to the selected frontend/proxy, the
  `/webhook/telegram` route reaches FastAPI, and the `WEBHOOK_SECRET` is the same
  value used by the backend.
- Confirm `TELEGRAM_CHAT_ID` and `TELEGRAM_ALLOWED_USER_IDS`; scan notifications
  can work even when command sender validation rejects a user.
- Check Redis health. Command deduplication and rate limits fail closed when
  Redis is unavailable.
- If you switch transports, choose one consumer only. Polling mode removes the
  registered webhook; webhook mode registers it again on application startup.

`TELEGRAM_TRANSPORT=polling` remains an optional alternative for hosts that
cannot receive webhooks. It uses outbound HTTPS and Redis to ensure one
polling consumer. Keep the configured chat and sender allowlist in either mode.

Telegram API documentation: [Bot API](https://core.telegram.org/bots/api).
