import { useState, type FormEvent } from "react";

import { request, useResource, number, price, time } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";
import {
  Panel,
  PageHead,
  Resource,
  Refresh,
  DataTable,
  JourneyChart,
} from "../components/workspace";

export function PaperTrades() {
  const r = useResource(base + "/trades/open"),
    history = useResource(base + "/trades/history?limit=30&offset=0");
  const [selected, setSelected] = useState<any>(null),
    [journeyTrade, setJourneyTrade] = useState<any>(null),
    [journeyPoints, setJourneyPoints] = useState<any[]>([]),
    [journeyLoading, setJourneyLoading] = useState(false),
    [journeyError, setJourneyError] = useState(""),
    [totp, setTotp] = useState(""),
    [error, setError] = useState(""),
    [pending, setPending] = useState(false);
  async function inspectJourney(trade: any) {
    const tradeId = trade.trade_id ?? trade.id;
    setJourneyTrade(trade);
    setJourneyPoints([]);
    setJourneyError("");
    setJourneyLoading(true);
    try {
      const data = await request(
        `${base}/trades/${encodeURIComponent(tradeId)}/journey`,
      );
      setJourneyPoints(Array.isArray(data.journey) ? data.journey : []);
    } catch (e) {
      setJourneyError((e as Error).message);
    } finally {
      setJourneyLoading(false);
    }
  }
  async function close(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      await request(base + "/trades/close", {
        method: "POST",
        body: JSON.stringify({
          trade_id: selected.id || selected.trade_id,
          totp_code: totp,
        }),
      });
      setSelected(null);
      setTotp("");
      r.refresh();
      history.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  const columns = [
    {
      key: "coin",
      label: "Instrument",
      render: (t: any) => <strong>{t.coin || t.symbol}</strong>,
    },
    {
      key: "direction",
      label: "Direction",
      render: (t: any) => (
        <Badge>{t.direction || (t.is_short ? "SHORT" : "LONG")}</Badge>
      ),
    },
    {
      key: "entry_price",
      label: "Entry",
      render: (t: any) => price(t.entry_price || t.open_rate),
    },
    {
      key: "current_price",
      label: "Mark",
      render: (t: any) => price(t.current_price || t.current_rate),
    },
    {
      key: "profit_abs",
      label: "Unrealized P&L",
      render: (t: any) => number(t.profit_abs ?? t.unrealized_pnl),
    },
    {
      key: "journey",
      label: "History",
      render: (t: any) => (
        <Button
          variant="outline"
          size="sm"
          onClick={() => void inspectJourney(t)}
        >
          Trade journey
        </Button>
      ),
    },
    {
      key: "action",
      label: "Action",
      render: (t: any) => (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setSelected(t);
            setError("");
          }}
        >
          Close position
        </Button>
      ),
    },
  ];
  return (
    <>
      <PageHead
        eyebrow="EXECUTION LEDGER"
        title="Trades & journey"
        description="Active-account positions and stored trade history. Inspect the journey or close a position with your authenticator."
        action={
          <Refresh
            onClick={() => {
              r.refresh();
              history.refresh();
            }}
          />
        }
      />
      <Panel title="Open positions">
        <Resource resource={r}>
          <DataTable
            rows={Array.isArray(r.data) ? r.data : []}
            columns={columns}
            empty="No open positions"
          />
        </Resource>
      </Panel>
      <Panel title="Recent closed records">
        <Resource resource={history}>
          <DataTable
            rows={history.data?.trades || []}
            columns={[
              { key: "coin", label: "Instrument" },
              { key: "direction", label: "Direction" },
              {
                key: "entry_price",
                label: "Entry",
                render: (t) => price(t.entry_price),
              },
              { key: "outcome", label: "Outcome" },
              {
                key: "net_pnl",
                label: "Net P&L",
                render: (t) => number(t.net_pnl ?? t.pnl),
              },
              {
                key: "closed_at",
                label: "Closed",
                render: (t) => time(t.closed_at),
              },
              {
                key: "journey",
                label: "Details",
                render: (t) => (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void inspectJourney(t)}
                  >
                    Trade journey
                  </Button>
                ),
              },
            ]}
          />
        </Resource>
      </Panel>
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!pending && !open) setSelected(null);
        }}
        title="Close this position?"
        description="This submits a closing order to the active exchange account. Confirm the instrument, environment, and authenticator code."
      >
        <form onSubmit={close}>
          <p className="confirm-instrument">
            {selected?.coin || selected?.symbol}
          </p>
          <label className="field">
            Authenticator code
            <input
              required
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={totp}
              onChange={(e) => setTotp(e.target.value)}
              autoComplete="one-time-code"
            />
          </label>
          {error && (
            <p className="error-text" role="alert">
              {error}
            </p>
          )}
          <Button variant="destructive" disabled={pending} type="submit">
            {pending ? "Closing…" : "Confirm close"}
          </Button>
        </form>
      </Dialog>
      <Dialog
        open={!!journeyTrade}
        onOpenChange={(open) => {
          if (!open) setJourneyTrade(null);
        }}
        title={`${journeyTrade?.coin || "Trade"} · trade journey`}
        description="Recorded price snapshots with the stored entry, stop, and target levels."
      >
        {journeyLoading ? (
          <div className="loading" role="status">
            Loading trade journey…
          </div>
        ) : null}
        {journeyError ? (
          <div className="error-state" role="alert">
            {journeyError}
          </div>
        ) : null}
        {!journeyLoading && !journeyError ? (
          <JourneyChart points={journeyPoints} />
        ) : null}
      </Dialog>
    </>
  );
}
