import { useState } from "react";

import { request, useResource, number, price, time } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Resource,
  Refresh,
  Fact,
  DataTable,
} from "../components/workspace";

export function Markets() {
  const r = useResource(base + "/coins"),
    [pending, setPending] = useState(""),
    [message, setMessage] = useState("");
  async function toggle(row: any) {
    setPending(row.coin);
    setMessage("");
    try {
      await request(base + "/coins/toggle", {
        method: "POST",
        body: JSON.stringify({ coin: row.coin, enabled: !row.enabled }),
      });
      r.refresh();
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setPending("");
    }
  }
  return (
    <>
      <PageHead
        eyebrow="CONFIGURED UNIVERSE"
        title="A deliberate market scope."
        description="Enable or pause existing instruments. Strategy parameters are preserved; unsupported markets are not added through this interface."
        action={<Refresh onClick={r.refresh} />}
      />
      {message && (
        <p className="notice" role="alert">
          {message}
        </p>
      )}
      <Panel title="Crypto futures">
        <Resource resource={r}>
          <DataTable
            rows={r.data || []}
            columns={[
              {
                key: "coin",
                label: "Instrument",
                render: (r) => <strong>{r.coin} / USDT</strong>,
              },
              { key: "state", label: "Engine state" },
              {
                key: "price",
                label: "Last observed price",
                render: (r) => (r.price ? price(r.price) : "Awaiting data"),
              },
              { key: "grade", label: "Latest grade" },
              {
                key: "enabled",
                label: "Scanning",
                render: (r) => (
                  <Badge tone={r.enabled ? "green" : "neutral"}>
                    {r.enabled ? "Enabled" : "Paused"}
                  </Badge>
                ),
              },
              {
                key: "action",
                label: "Action",
                render: (r) => (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!!pending}
                    onClick={() => toggle(r)}
                  >
                    {pending === r.coin
                      ? "Updating…"
                      : r.enabled
                        ? "Pause"
                        : "Enable"}
                  </Button>
                ),
              },
            ]}
          />
        </Resource>
      </Panel>
    </>
  );
}

export function India() {
  const status = useResource(base + "/indian/status"),
    signals = useResource(base + "/indian/signals?limit=30");
  return (
    <>
      <PageHead
        eyebrow="PRIVATE INDIAN MARKETS"
        title="Opening-range research."
        description="The existing Angel One integration is retained as an operator-only surface. Credentials and data availability govern its readiness."
        action={
          <Refresh
            onClick={() => {
              status.refresh();
              signals.refresh();
            }}
          />
        }
      />
      <Resource resource={status}>
        <Panel title="Session status">
          <dl className="facts">
            <Fact
              label="Market"
              value={status.data?.market_open ? "Open" : "Closed"}
            />
            <Fact
              label="Opening range"
              value={status.data?.orb_ready ? "Ready" : "Awaiting range"}
            />
            <Fact
              label="Signals today"
              value={number(status.data?.signals_today, 0)}
            />
            <Fact
              label="Rate limited"
              value={status.data?.rate_limited ? "Yes" : "No"}
            />
            <Fact
              label="Data age"
              value={
                status.data?.data_age_secs == null
                  ? "Not available"
                  : number(status.data.data_age_secs, 0) + " seconds"
              }
            />
          </dl>
        </Panel>
      </Resource>
      <Panel title="Indian signal history">
        <Resource resource={signals}>
          <DataTable
            rows={signals.data || []}
            columns={[
              { key: "instrument", label: "Instrument" },
              { key: "direction", label: "Direction" },
              { key: "entry", label: "Entry", render: (r) => price(r.entry) },
              { key: "sl", label: "Stop", render: (r) => price(r.sl) },
              { key: "tp1", label: "Target", render: (r) => price(r.tp1) },
              { key: "outcome", label: "Outcome" },
              {
                key: "timestamp",
                label: "Generated",
                render: (r) => time(r.timestamp),
              },
            ]}
          />
        </Resource>
      </Panel>
    </>
  );
}
