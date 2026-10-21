import { useState, type FormEvent } from "react";

import { FlaskConical } from "lucide-react";
import { request, useResource, number, time, words } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Metric,
  Resource,
  Fact,
  DataTable,
} from "../components/workspace";

export function Research() {
  const r = useResource(base + "/research"),
    universe = useResource(base + "/coins"),
    history = useResource(base + "/backtest/history/all"),
    assistant = useResource(base + "/assistant/status");
  const [coin, setCoin] = useState(""),
    [result, setResult] = useState<any>(null),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<any>(null),
    [asking, setAsking] = useState(false);
  async function replay(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      setResult(
        await request(base + "/research/backtest", {
          method: "POST",
          body: JSON.stringify({ coin }),
        }),
      );
      history.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function ask(e: FormEvent) {
    e.preventDefault();
    setAsking(true);
    setAnswer(null);
    try {
      setAnswer(
        await request(base + "/assistant", {
          method: "POST",
          body: JSON.stringify({ question }),
        }),
      );
    } catch (e) {
      setAnswer({ answer: (e as Error).message });
    } finally {
      setAsking(false);
    }
  }
  return (
    <>
      <PageHead
        eyebrow="RESEARCH & EVIDENCE"
        title="Test the assumptions."
        description="Historical replay and a visible evidence gate. A replay run does not certify a strategy or enable real-money execution."
      />
      <Resource resource={r}>
        <Panel
          title="Evidence gate"
          aside={<Badge tone="amber">Not approved for live trading</Badge>}
        >
          <div className="metric-grid">
            <Metric
              label="Symbols evaluated"
              value={number(r.data?.gate?.tested_symbols, 0)}
              note={
                "Required universe: " +
                (r.data?.gate?.required_symbols || "not recorded")
              }
            />
            <Metric
              label="Review complete"
              value={r.data?.gate?.research_complete_for_review ? "Yes" : "No"}
              note="Full research evidence gate"
            />
          </div>
          <div className="reading">
            <p>
              Preserve chronological holdouts, record fees and funding, compare
              multiple regimes, and validate paper-forward execution.
              Cached-candle replay below uses a simulated 1,000 USDT account and
              1× leverage.
            </p>
          </div>
        </Panel>
      </Resource>
      <Panel title="Run a cached-data replay">
        <form className="filters" onSubmit={replay}>
          <label>
            Configured instrument
            <select
              required
              value={coin}
              onChange={(e) => setCoin(e.target.value)}
            >
              <option value="">Choose instrument</option>
              {universe.data?.map((c: any) => (
                <option key={c.coin}>{c.coin}</option>
              ))}
            </select>
          </label>
          <Button disabled={pending || !coin} type="submit">
            <FlaskConical size={15} />
            {pending ? "Replaying…" : "Run research replay"}
          </Button>
        </form>
        {error && (
          <p className="error-text panel-note" role="alert">
            {error}
          </p>
        )}
        {result && (
          <dl className="facts">
            <Fact label="Status" value={words(result.status)} />
            <Fact
              label="Recorded trades"
              value={number(result.result?.total_trades, 0)}
            />
            <Fact
              label="Net P&L (simulation)"
              value={number(result.result?.total_pnl)}
            />
            <Fact
              label="Maximum drawdown"
              value={number(result.result?.max_drawdown)}
            />
          </dl>
        )}
      </Panel>
      <Panel title="Stored research runs">
        <Resource resource={history}>
          <DataTable
            rows={history.data || []}
            columns={[
              { key: "coin", label: "Instrument" },
              {
                key: "run_at",
                label: "Run time",
                render: (r) => time(r.run_at),
              },
              { key: "total_trades", label: "Trades" },
              {
                key: "win_rate",
                label: "Win rate",
                render: (r) => number(r.win_rate) + "%",
              },
              {
                key: "total_pnl",
                label: "Simulated P&L",
                render: (r) => number(r.total_pnl),
              },
              {
                key: "max_drawdown",
                label: "Drawdown",
                render: (r) => number(r.max_drawdown),
              },
            ]}
          />
        </Resource>
      </Panel>
      <Panel title="Private research assistant">
        <Resource resource={assistant}>
          {assistant.data?.configured ? (
            <form className="assistant-form" onSubmit={ask}>
              <p className="muted">
                Queries may send relevant private trade context to Groq.
                Generated answers require verification against source records.
              </p>
              <label className="field">
                Question
                <textarea
                  required
                  minLength={3}
                  maxLength={1000}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask about recorded trade history"
                />
              </label>
              <Button disabled={asking} type="submit">
                {asking ? "Retrieving context…" : "Ask assistant"}
              </Button>
              {answer && (
                <div className="assistant-answer">
                  {answer.answer ||
                    answer.response ||
                    answer.message ||
                    "No answer returned."}
                  {answer.sources && (
                    <small>
                      Sources:{" "}
                      {Array.isArray(answer.sources)
                        ? answer.sources.join(", ")
                        : String(answer.sources)}
                    </small>
                  )}
                </div>
              )}
            </form>
          ) : (
            <div className="reading">
              <p>
                The private research assistant is not configured. The retained
                RAG and ML modules remain research tools; no generated analysis
                is shown as a trading decision.
              </p>
            </div>
          )}
        </Resource>
      </Panel>
    </>
  );
}
