# Release verification — 2.1.0

## Executed checks

| Check | Result |
| --- | --- |
| Backend suite | 176 passed |
| TypeScript check | Passed |
| Public and admin production builds | Passed |
| Pages proxy unit tests | 5 passed |
| Playwright browser tests | 16 passed |
| Light/dark public and admin layouts | Passed at 320, 390, 768, 1440 px; desktop and phone screenshots visually inspected |
| Trade Journey and performance navigation | Passed against isolated API fixtures |
| Mode dialog prerequisites and TOTP form | Passed; browser tests do not submit a real switch |
| Mode transition guards, persistence, stale selection, account-check rejection | Passed with mocked exchange clients |
| Telegram actual help/start/ping dispatch, sender rejection, dedup, stale-webhook-to-polling flow | Passed with mocked Telegram transport |

The browser runner used Chromium 153 because the standard Playwright browser
archive was truncated by the environment. Screenshots contain isolated test
fixtures, not a user's account or fabricated runtime data.

## External acceptance still required

The package has not been deployed on the user's Docker host or Cloudflare account.
A Docker daemon was not available for starting this Compose stack here. Verify
image pulls, container creation, tunnel connection, host reboot recovery, Google
OAuth, real Redis, Telegram delivery, and exchange credentials on that deployment.
Actual real-money execution and a live-account mode switch were not performed.

Follow [UPGRADE_2_1.md](UPGRADE_2_1.md). Back up the database and runtime state first.
Preserve the existing completed .env. Verify `/ping`, `/help`, and `/health` on the
actual bot after recreation. Verify a database restore separately.

Historical results and test success do not certify strategy profitability.
Paper is the initial default; live requires explicit server opt-in and the
TOTP-confirmed transition in [EXECUTION_MODES.md](EXECUTION_MODES.md).
