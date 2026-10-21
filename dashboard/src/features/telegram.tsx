import { useState } from "react";

import { RefreshCw, Command } from "lucide-react";
import { request, useResource, number, price, time, words } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";

import {
  Panel,
  PageHead,
  Empty,
  Resource,
  Fact,
} from "../components/workspace";

export function Telegram() {
  const r = useResource(base + "/integrations"),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [registration, setRegistration] = useState<any>(null);
  async function register() {
    setPending(true);
    setError("");
    try {
      const result = await request(base + "/telegram/register", {
        method: "POST",
      });
      setRegistration(result?.telegram?.registration || null);
      r.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHead
        eyebrow="TELEGRAM OPERATIONS"
        title="Telegram operations"
        description="Private command access and trading reports use the configured operator chat. Signal, account, and research output stays on Telegram."
        action={
          <Button variant="outline" disabled={pending} onClick={register}>
            <RefreshCw size={14} />
            {pending ? "Registering…" : "Reconnect commands"}
          </Button>
        }
      />
      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}
      <Resource resource={r}>
        <Panel title="Command transport">
          <dl className="facts">
            <Fact
              label="Inbound transport"
              value={words(r.data?.telegram?.transport)}
            />
            <Fact
              label="Transport connection"
              value={
                r.data?.telegram?.command_service?.connected
                  ? "Connected"
                  : "Reconnecting / not configured"
              }
            />
            <Fact
              label="Transport error"
              value={
                r.data?.telegram?.command_service?.last_error || "None reported"
              }
            />
            <Fact
              label="Configured chat ID"
              value={r.data?.telegram?.configured_chat_id || "Required"}
            />
            <Fact
              label="Latest inbound update"
              value={time(r.data?.telegram?.command_service?.last_update_at)}
            />
            <Fact
              label="Latest command result"
              value={words(
                r.data?.telegram?.command_service?.last_result ||
                  "Awaiting command",
              )}
            />
          </dl>
          <p className="panel-note">
            Polling receives commands without an inbound tunnel or webhook. In
            groups, use /help@YourBotUsername and configure the sender’s numeric
            user ID. A chat_mismatch or sender_not_allowed result identifies an
            authorization mismatch.
          </p>
        </Panel>
        <Panel title="Integration state">
          <dl className="facts">
            <Fact
              label="Credentials"
              value={r.data?.telegram?.configured ? "Configured" : "Required"}
            />
            <Fact
              label="Provider status"
              value={words(r.data?.telegram?.status || "not_configured")}
            />
            <Fact
              label="Webhook"
              value={r.data?.telegram?.webhook?.url || "Not registered"}
            />
            <Fact
              label="Webhook destination check"
              value={
                r.data?.telegram?.status === "registered"
                  ? "Matches the configured admin domain"
                  : words(r.data?.telegram?.status || "not_configured")
              }
            />
            <Fact
              label="Pending updates"
              value={number(r.data?.telegram?.webhook?.pending_update_count, 0)}
            />
            <Fact
              label="Latest Telegram delivery error"
              value={
                r.data?.telegram?.webhook?.last_error_message || "None reported"
              }
            />
            <Fact
              label="Allowed sender IDs"
              value={
                r.data?.telegram?.allowed_users_configured
                  ? "Configured"
                  : "Empty · private chat only"
              }
            />
            <Fact
              label="Last registration"
              value={
                registration || r.data?.telegram?.registration
                  ? `Webhook ${(registration || r.data.telegram.registration).webhook ? "registered" : "failed"} · commands ${(registration || r.data.telegram.registration).commands ? "registered" : "failed"}`
                  : "No registration attempt this session"
              }
            />
          </dl>
        </Panel>
      </Resource>
      <Panel title="Command reference">
        <div className="command-grid">
          {[
            ["/health", "Dependency readiness and data freshness"],
            ["/status", "Operator summary and paper mode"],
            ["/scan", "Trigger a guarded market scan"],
            ["/coin ETH", "Inspect one configured instrument"],
            ["/trades", "Open paper positions"],
            ["/position ETH", "Inspect a paper position"],
            ["/journey 42", "Inspect the recorded price path for trade 42"],
            ["/performance", "Recorded performance breakdown"],
            ["/candles", "Stored candle availability"],
            ["/backtest ETH", "Cached-data research replay"],
            ["/india", "Private Indian-market status"],
            ["/help", "Complete command reference"],
          ].map(([cmd, desc]) => (
            <div key={cmd}>
              <code>{cmd}</code>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
