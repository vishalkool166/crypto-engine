# API and WebSocket security inventory

Source-generated from route decorators on 2026-10-20. This is a source review aid, not a live authorization test or release certification.

The inventory contains 130 HTTP operations and 1 WebSocket route.

## Guard semantics

| Source | Helper meaning |
| --- | --- |
| `api/routes.py` | `_auth` calls `auth.is_authenticated`; selected admin handlers additionally call `require_admin_access`. |
| `api/indian.py` | `_auth` calls `auth.is_authenticated`; setup, scan, refresh and quota diagnostics require administrator access. |
| `api/trading.py` | `_auth` calls `require_admin_access`; trade account and execution controls are administrator-only. |
| `api/engine_health.py` | `_auth` calls `require_admin_access`; rejection reset also requires TOTP. |
| `saas/admin.py` | `_auth` checks an active user and `is_admin`; unauthorized users receive 404. |
| `saas/email_routes.py` | Anonymous identity endpoints are unavailable unless both email-account flags are enabled; token flows and persistent throttling are enforced in the account service. |
| `main.py` | Session routes resolve current users; OAuth callbacks use Authlib; setup routes use setup/admin checks; TOTP and recovery controls have endpoint-specific proof. |

## Endpoint map

| Method | Path | Handler | Guard observed in handler | Behavior to verify | Source |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/engine/confidence/{coin}` | `engine_confidence` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:207` |
| `GET` | `/api/engine/filter-analysis` | `engine_filter_analysis` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:152` |
| `GET` | `/api/engine/health` | `engine_health` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:16` |
| `GET` | `/api/engine/rejections` | `engine_rejections` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:32` |
| `GET` | `/api/engine/rejections/coin/{coin}` | `engine_rejections_coin` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:53` |
| `POST` | `/api/engine/rejections/reset` | `engine_rejections_reset` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/engine_health.py:190` |
| `GET` | `/api/engine/relative-strength` | `engine_relative_strength` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:99` |
| `GET` | `/api/engine/relative-strength/{coin}` | `engine_relative_strength_coin` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:112` |
| `GET` | `/api/engine/score/{coin}` | `engine_score_coin` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:130` |
| `GET` | `/api/engine/traces` | `engine_traces` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:64` |
| `GET` | `/api/engine/traces/{coin}` | `engine_traces_coin` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/engine_health.py:81` |
| `GET` | `/api/indian/orb` | `indian_orb` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/indian.py:102` |
| `POST` | `/api/indian/orb/setup` | `indian_orb_setup` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/indian.py:183` |
| `GET` | `/api/indian/performance` | `indian_performance` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/indian.py:172` |
| `GET` | `/api/indian/quota` | `indian_quota_status` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/indian.py:242` |
| `POST` | `/api/indian/refresh` | `indian_refresh` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/indian.py:213` |
| `POST` | `/api/indian/scan` | `indian_scan_now` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/indian.py:197` |
| `GET` | `/api/indian/signals` | `indian_signals` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/indian.py:121` |
| `GET` | `/api/indian/signals/{signal_id}/journey` | `indian_signal_journey` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/indian.py:160` |
| `GET` | `/api/indian/status` | `indian_status` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/indian.py:19` |
| `GET` | `/api/audit/log` | `audit_log` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:686` |
| `POST` | `/api/backtest/all/run` | `backtest_all` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:535` |
| `GET` | `/api/backtest/history/all` | `backtest_history` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:567` |
| `POST` | `/api/backtest/{coin}` | `backtest` | `_auth` — authenticated-user helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:505` |
| `GET` | `/api/candles/{coin}/{tf}` | `get_candles` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:806` |
| `POST` | `/api/chat` | `chat_endpoint` | `get_current_user` — active session/user | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:961` |
| `GET` | `/api/coins` | `get_coins` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:699` |
| `GET` | `/api/coins/active` | `coins_active` | Public by design — public, non-sensitive symbol list | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:454` |
| `POST` | `/api/coins/add` | `add_coin` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:736` |
| `GET` | `/api/coins/states` | `coins_states` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:903` |
| `POST` | `/api/coins/toggle` | `toggle_coin` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:705` |
| `GET` | `/api/coins/validate/{coin}` | `validate_coin` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:792` |
| `DELETE` | `/api/coins/{coin}` | `remove_coin` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:772` |
| `GET` | `/api/dashboard` | `dashboard` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:164` |
| `GET` | `/api/dashboard/coin/{coin}` | `dashboard_coin_detail` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:225` |
| `GET` | `/api/dashboard/history` | `dashboard_history` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:203` |
| `GET` | `/api/dashboard/performance` | `dashboard_performance` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:187` |
| `GET` | `/api/dashboard/signals` | `dashboard_signals` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:195` |
| `GET` | `/api/dashboard/summary` | `dashboard_summary` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:179` |
| `GET` | `/api/dashboard/ticker` | `dashboard_ticker` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:219` |
| `GET` | `/api/dashboard/universe` | `dashboard_universe` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:211` |
| `GET` | `/api/engine/monthly-report` | `monthly_report` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:939` |
| `GET` | `/api/engine/monthly-report/history` | `monthly_report_history` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:950` |
| `GET` | `/api/fear-greed` | `fear_greed` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:484` |
| `GET` | `/api/macro-events` | `macro_events` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:493` |
| `GET` | `/api/market/{coin}` | `market` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:475` |
| `GET` | `/api/mode/status` | `mode_status` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:639` |
| `POST` | `/api/mode/toggle` | `mode_toggle` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:649` |
| `GET` | `/api/proxy/binance/aggTrades` | `proxy_binance_agg_trades` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:829` |
| `GET` | `/api/proxy/binance/price` | `proxy_binance_price` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:844` |
| `POST` | `/api/scan` | `scan` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:242` |
| `GET` | `/api/signal/{signal_id}` | `get_signal_by_id` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:429` |
| `GET` | `/api/signals` | `get_signals` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:260` |
| `GET` | `/api/signals/active` | `signals_active` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:399` |
| `GET` | `/api/signals/latest` | `signals_latest` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:366` |
| `GET` | `/api/signals/page` | `get_signals_page` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:312` |
| `GET` | `/api/stats` | `get_stats` | `_auth` — authenticated-user helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:469` |
| `POST` | `/api/sync/outcomes` | `sync_outcomes` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:626` |
| `GET` | `/api/system/disk` | `system_disk` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:890` |
| `POST` | `/api/system/docker-purge` | `docker_purge` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `api/routes.py:864` |
| `GET` | `/api/system/health` | `health` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:580` |
| `GET` | `/api/trades/{trade_id}/journey` | `trade_journey` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `api/routes.py:928` |
| `GET` | `/api/trades/balance` | `trades_balance` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:31` |
| `POST` | `/api/trades/close` | `trades_close` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `api/trading.py:168` |
| `GET` | `/api/trades/config` | `trades_config` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:355` |
| `GET` | `/api/trades/daily` | `trades_daily` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:91` |
| `GET` | `/api/trades/history` | `trades_history` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:66` |
| `POST` | `/api/trades/kill-switch` | `trades_kill_switch` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `api/trading.py:269` |
| `POST` | `/api/trades/mode` | `trades_mode` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `api/trading.py:377` |
| `GET` | `/api/trades/open` | `trades_open` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:19` |
| `GET` | `/api/trades/performance` | `trades_performance` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:102` |
| `GET` | `/api/trades/ping` | `trades_ping` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:326` |
| `GET` | `/api/trades/profit` | `trades_profit` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:55` |
| `POST` | `/api/trades/start` | `trades_start` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `api/trading.py:231` |
| `POST` | `/api/trades/stop` | `trades_stop` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `api/trading.py:250` |
| `GET` | `/api/trades/summary` | `trades_summary` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:113` |
| `GET` | `/api/trades/whitelist` | `trades_whitelist` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:368` |
| `GET` | `/api/trades/ws_status` | `trades_ws_status` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `api/trading.py:338` |
| `GET` | `/` | `legacy_dashboard_home` | Public by design — public legacy redirect | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:1173` |
| `GET` | `/api/health` | `api_health` | Public by design — public liveness | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:511` |
| `GET` | `/api/indian/startup-status` | `indian_startup_status` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:1113` |
| `GET` | `/api/langsmith/status` | `langsmith_status` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:1102` |
| `GET` | `/api/me` | `get_me` | `get_current_user` — active session/user | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:784` |
| `POST` | `/api/me/api-keys` | `create_api_key` | `get_current_user` — active session/user | State change or command; verify step-up, validation and audit as applicable | `main.py:822` |
| `DELETE` | `/api/me/api-keys/{key_id}` | `delete_api_key` | `get_current_user` — active session/user | State change or command; verify step-up, validation and audit as applicable | `main.py:849` |
| `GET` | `/api/me/sessions` | `get_my_sessions` | `get_current_user` — active session/user | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:701` |
| `POST` | `/api/me/sessions/revoke-all` | `revoke_all_my_sessions` | `get_current_user` — active session/user | State change or command; verify step-up, validation and audit as applicable | `main.py:738` |
| `POST` | `/api/me/sessions/{session_id}/revoke` | `revoke_my_session` | `get_current_user` — active session/user | State change or command; verify step-up, validation and audit as applicable | `main.py:719` |
| `GET` | `/api/pricing` | `get_pricing` | Public by design — public pricing catalogue | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:775` |
| `POST` | `/api/rag/reindex` | `rag_reindex` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `main.py:1088` |
| `GET` | `/api/rag/status` | `rag_status` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:1077` |
| `GET` | `/api/ready` | `api_readiness` | Public by design — public sanitized database/Redis readiness | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:517` |
| `GET` | `/api/ws/status` | `ws_status` | `require_admin_access` — administrator | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:1069` |
| `GET` | `/auth/callback/google` | `auth_callback_google` | Public by design — public OAuth callback; Authlib validates state | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:553` |
| `POST` | `/auth/generate-recovery-codes` | `auth_generate_recovery_codes` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `main.py:1035` |
| `GET` | `/auth/google` | `auth_google` | Public by design — public OAuth initiation | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:530` |
| `POST` | `/auth/login` | `auth_login` | Public by design — public password login with rate limit | State change or command; verify step-up, validation and audit as applicable | `main.py:888` |
| `POST` | `/auth/logout` | `auth_logout` | `get_current_user` — active session/user | State change or command; verify step-up, validation and audit as applicable | `main.py:685` |
| `POST` | `/auth/onboarding/complete` | `complete_onboarding` | `get_current_user` — active session/user | State change or command; verify step-up, validation and audit as applicable | `main.py:756` |
| `GET` | `/auth/qr.png` | `auth_qr_png` | `require_setup_access` — setup token before provisioning; administrator after | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:1055` |
| `POST` | `/auth/regenerate-totp` | `auth_regenerate_totp` | `require_admin_access` — administrator | State change or command; verify step-up, validation and audit as applicable | `main.py:1017` |
| `POST` | `/auth/request-totp` | `request_totp_via_telegram` | Public by design — public endpoint; requires dashboard password | State change or command; verify step-up, validation and audit as applicable | `main.py:932` |
| `POST` | `/auth/reset-password` | `auth_reset_password` | Public by design — public endpoint; requires TOTP or recovery proof | State change or command; verify step-up, validation and audit as applicable | `main.py:960` |
| `GET` | `/auth/session` | `auth_session` | `get_current_user` — active session/user | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:650` |
| `POST` | `/auth/set-credentials` | `auth_set_credentials` | `require_setup_access` — setup token before provisioning; administrator after | State change or command; verify step-up, validation and audit as applicable | `main.py:979` |
| `GET` | `/auth/setup` | `auth_setup` | `require_setup_access` — setup token before provisioning; administrator after | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:868` |
| `GET` | `/login` | `login_page` | Public by design — public legacy redirect | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:881` |
| `GET` | `/login.html` | `login_page` | Public by design — public legacy redirect | Read/redirect/provider callback; verify handler remains side-effect safe | `main.py:881` |
| `POST` | `/webhook/telegram` | `telegram_webhook` | `handle_webhook` — Telegram webhook secret | State change or command; verify step-up, validation and audit as applicable | `main.py:1159` |
| `WEBSOCKET` | `/ws/dashboard` | `dashboard_websocket` | `_get_ws_user` — active session; origin checked when supplied | Long-lived authenticated stream | `main.py:1124` |
| `GET` | `/api/admin/audit` | `admin_audit` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:390` |
| `GET` | `/api/admin/demo/stats` | `admin_demo_stats` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:322` |
| `GET` | `/api/admin/overview` | `admin_overview` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:40` |
| `GET` | `/api/admin/pricing` | `admin_get_pricing` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:439` |
| `GET` | `/api/admin/sessions` | `admin_get_sessions` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:217` |
| `POST` | `/api/admin/sessions/cleanup` | `admin_cleanup_sessions` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `saas/admin.py:263` |
| `POST` | `/api/admin/sessions/{session_id}/revoke` | `admin_revoke_session_endpoint` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `saas/admin.py:228` |
| `GET` | `/api/admin/stats` | `admin_stats` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:274` |
| `GET` | `/api/admin/system` | `admin_system` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:449` |
| `GET` | `/api/admin/users` | `admin_users` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:102` |
| `GET` | `/api/admin/users/{user_id}` | `admin_get_user` | `_auth` — administrator helper (see helper in source) | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/admin.py:115` |
| `POST` | `/api/admin/users/{user_id}/deactivate` | `admin_deactivate_user` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `saas/admin.py:176` |
| `POST` | `/api/admin/users/{user_id}/reactivate` | `admin_reactivate_user` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `saas/admin.py:197` |
| `POST` | `/api/admin/users/{user_id}/sessions/revoke-all` | `admin_revoke_all_sessions` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `saas/admin.py:248` |
| `POST` | `/api/admin/users/{user_id}/tier` | `admin_update_tier` | `_auth` — administrator helper (see helper in source) | State change or command; verify step-up, validation and audit as applicable | `saas/admin.py:144` |
| `POST` | `/auth/email/login` | `login` | Public by design — public; dual-flag gated and throttled | State change or command; verify step-up, validation and audit as applicable | `saas/email_routes.py:76` |
| `POST` | `/auth/email/register` | `register` | Public by design — public; dual-flag gated and throttled | State change or command; verify step-up, validation and audit as applicable | `saas/email_routes.py:51` |
| `POST` | `/auth/email/request-reset` | `request_reset` | Public by design — public; generic response and throttle | State change or command; verify step-up, validation and audit as applicable | `saas/email_routes.py:106` |
| `POST` | `/auth/email/reset` | `reset` | Public by design — public; single-use reset token | State change or command; verify step-up, validation and audit as applicable | `saas/email_routes.py:120` |
| `GET` | `/auth/email/status` | `status` | Public by design — public email-feature availability only | Read/redirect/provider callback; verify handler remains side-effect safe | `saas/email_routes.py:46` |
| `POST` | `/auth/email/verify` | `verify` | Public by design — public; single-use verification token | State change or command; verify step-up, validation and audit as applicable | `saas/email_routes.py:66` |

## Public and protocol exceptions

Anonymous routes are intentional only for liveness, public pricing, login/recovery, OAuth initiation/callback, feature-gated email authentication, legacy redirects, a non-sensitive symbol list, and the Telegram webhook (which delegates secret validation). `GET /auth/logout` was converted to `POST`; market scan and backtest launch routes are also POST. OAuth redirects/callbacks remain GET because the provider protocol returns there; Authlib state validation and verified Google identity are source checks that still need browser integration tests.

Personal SaaS API keys are read-only (GET/HEAD/OPTIONS), never receive the administrator role, and new keys expire after 90 days. The legacy dashboard master key remains a separate privileged credential. Existing account API keys with no expiry must be manually revoked and recreated.

The strict cookie-origin check remains opt-in (`STRICT_SESSION_ORIGIN_CHECK=true`) pending cross-origin browser validation. The current source-level route matrix checks classification and helper semantics; it does not prove tenant isolation, CSRF behavior in a real browser, provider callbacks, or every endpoint response permission.
