import { useEffect, useRef, useState, type FormEvent } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import gsap from "gsap";

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
    history = useResource(base + "/trades/history?limit=30&offset=0"),
    markStream = useResource(base + "/trades/ws_status", 10000);
  const [livePrices, setLivePrices] = useState<Record<string, number>>({}),
    [lastLiveTick, setLastLiveTick] = useState(0);
  const livePricesRef = useRef<Record<string, number>>({});
  useEffect(() => {
    const receive = (event: Event) => {
      const payload = (event as CustomEvent).detail;
      if (payload?.mark_prices && typeof payload.mark_prices === "object") {
        const next = payload.mark_prices as Record<string, number>;
        const changed = Object.entries(next).filter(([coin, mark]) => livePricesRef.current[coin] !== mark);
        livePricesRef.current = next;
        setLivePrices(next);
        setLastLiveTick(Date.now());
        if (changed.length) window.requestAnimationFrame(() => changed.forEach(([coin]) => {
          document.querySelectorAll<HTMLElement>(`.trade-pnl-meter[data-live-coin="${coin}"] strong`).forEach((node) =>
            gsap.fromTo(node, { y: 2, opacity: 0.65 }, { y: 0, opacity: 1, duration: 0.2, ease: "power1.out", overwrite: true }),
          );
        }));
      }
    };
    window.addEventListener("signal-engine-stream", receive);
    return () => window.removeEventListener("signal-engine-stream", receive);
  }, []);
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
  const openRows = Array.isArray(r.data) ? r.data : [];
  const liveTrade = (trade: any) => {
    if (trade?.is_open === false || ["win", "loss", "breakeven"].includes(String(trade?.outcome || "").toLowerCase())) return trade;
    const coin = String(trade?.coin || trade?.symbol || "").toUpperCase().replace(/USDT.*$/, "").replace(/[^A-Z0-9]/g, "");
    const mark = Number(livePrices[coin] || 0);
    const entry = Number(trade?.entry_price || trade?.actual_fill_entry || 0);
    if (!mark || !entry) return trade;
    const isShort = trade?.is_short ?? String(trade?.direction || "").toUpperCase() === "SHORT";
    const amount = Number(trade?.position_amt ?? (Number(trade?.position_size || 0) * (isShort ? -1 : 1)));
    const pnl = amount * (mark - entry);
    const margin = Number(trade?.margin_used || 0);
    return { ...trade, current_price: mark, profit_abs: pnl, unrealized_pnl: pnl, profit_ratio: margin > 0 ? pnl / margin : 0 };
  };
  const liveOpenRows = openRows.map(liveTrade);
  const focusedTrade = journeyTrade ? liveTrade(journeyTrade) : null;
  const largestMove = Math.max(5, ...liveOpenRows.map((t: any) => Math.abs(Number(t.profit_ratio || 0) * 100)));
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
      render: (t: any) => <span data-live-coin={String(t.coin || t.symbol || "").toUpperCase().replace(/USDT.*$/, "").replace(/[^A-Z0-9]/g, "")}>{price(t.current_price || t.current_rate)}</span>,
    },
    {
      key: "profit_abs",
      label: "Unrealized P&L",
      render: (t: any) => {
        const value = Number(t.profit_abs ?? t.unrealized_pnl ?? 0);
        const ratio = Number(t.profit_ratio || 0) * 100;
        const width = Math.min(50, Math.abs(ratio) / largestMove * 50);
        return (
          <div className="trade-pnl-meter" data-live-coin={String(t.coin || t.symbol || "").toUpperCase().replace(/USDT.*$/, "").replace(/[^A-Z0-9]/g, "")} aria-label={`${value >= 0 ? "Profit" : "Loss"}: ${number(value)} USDT, ${number(Math.abs(ratio))}% on margin`}>
            <strong className={value >= 0 ? "positive-value" : "negative-value"}>{value > 0 ? "+" : ""}{number(value)}</strong>
            <div className={`trade-pnl-track ${value < 0 ? "is-negative" : "is-positive"}`} aria-hidden="true">
              <span className="trade-pnl-center" />
              <span className="trade-pnl-fill" style={{ width: `${width}%` }} />
            </div>
            <small>{ratio > 0 ? "+" : "−"}{number(Math.abs(ratio))}% on margin</small>
          </div>
        );
      },
    },
    {
      key: "journey",
      label: "Trade details",
      render: (t: any) => (
        <Button
          variant="outline"
          size="sm"
          onClick={() => void inspectJourney(t)}
        >
          Open details
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
          <div className="trade-live-actions">
            <Badge tone={lastLiveTick && Date.now() - lastLiveTick < 5000 ? "green" : markStream.data?.mark_price_fresh ? "amber" : "red"}>
              {lastLiveTick && Date.now() - lastLiveTick < 5000 ? "Binance marks · live" : markStream.data?.mark_price_fresh ? "Binance stream · waiting" : "Binance stream · stale"}
            </Badge>
            <Refresh onClick={() => { r.refresh(); history.refresh(); markStream.refresh(); }} />
          </div>
        }
      />
      <Panel title="Open positions">
        <Resource resource={r}>
          <DataTable
            rows={liveOpenRows}
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
              { key: "outcome", label: "Outcome", render: (t) => <Badge tone={t.outcome === "win" ? "green" : t.outcome === "loss" ? "red" : "neutral"}>{t.outcome || "—"}</Badge> },
              {
                key: "net_pnl",
                label: "Net P&L",
                render: (t) => { const pnl = Number(t.net_pnl ?? t.pnl ?? 0); return <strong className={pnl >= 0 ? "positive-value" : "negative-value"}>{pnl > 0 ? "+" : ""}{number(pnl)}</strong>; },
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
                    Open details
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
      <DialogPrimitive.Root
        open={!!journeyTrade}
        onOpenChange={(open) => {
          if (!open) setJourneyTrade(null);
        }}
      >
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="dialog-overlay" />
          <DialogPrimitive.Content className="trade-detail-drawer">
            <header className="trade-detail-header">
              <div>
                <p className="eyebrow">TRADE JOURNEY</p>
                <DialogPrimitive.Title className="trade-detail-title">
                  {focusedTrade?.coin || focusedTrade?.symbol || "Trade"}
                  <span>{focusedTrade?.direction || (focusedTrade?.is_short ? "SHORT" : "LONG")}</span>
                </DialogPrimitive.Title>
                <DialogPrimitive.Description className="trade-detail-subtitle">
                  {focusedTrade?.execution_mode || "Recorded position"} · {focusedTrade?.outcome || (focusedTrade?.is_open ? "Running" : "Closed")}
                </DialogPrimitive.Description>
              </div>
              <DialogPrimitive.Close className="trade-detail-close" aria-label="Close trade details">
                <X size={18} />
              </DialogPrimitive.Close>
            </header>
            <div className="trade-detail-scroll">
              <section className="trade-detail-pnl">
                <small>{focusedTrade?.is_open ? "Unrealized P&L · Binance mark" : "Net realized P&L"}</small>
                <strong className={Number(focusedTrade?.profit_abs ?? focusedTrade?.pnl ?? 0) >= 0 ? "positive-value" : "negative-value"}>
                  {number(focusedTrade?.profit_abs ?? focusedTrade?.net_pnl_live ?? focusedTrade?.pnl)}
                </strong>
                <span>{focusedTrade?.profit_ratio != null ? `${number(Number(focusedTrade.profit_ratio) * 100)}% on margin` : focusedTrade?.duration || "P&L shown in account currency"}</span>
              </section>
              <section className="trade-detail-section">
                <h3>Position</h3>
                <div className="trade-detail-grid">
                  <Detail label="Entry" value={price(focusedTrade?.actual_fill_entry ?? focusedTrade?.entry_price)} />
                  <Detail label="Mark / exit" value={price(focusedTrade?.current_price ?? focusedTrade?.actual_fill_exit ?? focusedTrade?.exit_price)} />
                  <Detail label="Stop" value={price(focusedTrade?.sl_price ?? focusedTrade?.sl_signal)} />
                  <Detail label="Target" value={price(focusedTrade?.tp1_price ?? focusedTrade?.tp1)} />
                  <Detail label="Size" value={number(focusedTrade?.position_size ?? focusedTrade?.position_amt)} />
                  <Detail label="Margin · leverage" value={`${number(focusedTrade?.margin_used)} · ${focusedTrade?.leverage || focusedTrade?.binance_leverage || "—"}×`} />
                  <Detail label="Liquidation" value={price(focusedTrade?.liquidation_price)} />
                  <Detail label="Grade · score" value={`${focusedTrade?.grade || "—"} · ${focusedTrade?.score_at_entry ?? "—"}`} />
                </div>
              </section>
              <section className="trade-detail-section">
                <h3>Timing & context</h3>
                <div className="trade-detail-grid">
                  <Detail label="Opened" value={time(focusedTrade?.opened_at)} />
                  <Detail label="Closed" value={time(focusedTrade?.closed_at)} />
                  <Detail label="Duration" value={focusedTrade?.duration || (focusedTrade?.duration_hours != null ? `${number(focusedTrade.duration_hours)} hours` : "Still running")} />
                  <Detail label="Session" value={focusedTrade?.session_at_entry || "—"} />
                  <Detail label="Market regime" value={focusedTrade?.regime_at_entry || "—"} />
                  <Detail label="Close reason" value={focusedTrade?.close_reason || (focusedTrade?.is_open ? "Position open" : "—")} />
                  <Detail label="MAE · MFE" value={`${number(focusedTrade?.mae)} · ${number(focusedTrade?.mfe)}`} />
                  <Detail label="System version" value={focusedTrade?.system_version || "—"} />
                </div>
              </section>
              <section className="trade-detail-section">
                <h3>Execution costs</h3>
                <div className="trade-detail-grid">
                  <Detail label="Fees" value={number(focusedTrade?.total_commission ?? focusedTrade?.entry_commission)} />
                  <Detail label="Funding paid" value={number(focusedTrade?.funding_fees_paid)} />
                  <Detail label="Entry slippage" value={focusedTrade?.slippage_entry_pct == null ? "—" : `${number(focusedTrade.slippage_entry_pct)}%`} />
                  <Detail label="Fill at entry" value={price(focusedTrade?.actual_fill_entry)} />
                </div>
              </section>
              <section className="trade-detail-section">
                <h3>Recorded price path</h3>
                {journeyLoading ? <div className="loading" role="status">Loading trade journey…</div> : null}
                {journeyError ? <div className="error-state" role="alert">{journeyError}</div> : null}
                {!journeyLoading && !journeyError ? <JourneyChart points={journeyPoints} /> : null}
              </section>
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </>
  );
}

function Detail({ label, value }: { label: string; value: string | number }) {
  return <div className="trade-detail-fact"><small>{label}</small><strong>{value || "—"}</strong></div>;
}
