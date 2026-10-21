import { useState, type FormEvent } from "react";

import { FlaskConical, Bot, Database, Sparkles } from "lucide-react";
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
    [asking, setAsking] = useState(false),
    [indexing, setIndexing] = useState(false),
    [assistantError, setAssistantError] = useState("");
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
  async function updateIndex() {
    setIndexing(true);
    setAssistantError("");
    try {
      await request(base + "/assistant/index", { method: "POST" });
      assistant.refresh();
    } catch (e) {
      setAssistantError((e as Error).message);
    } finally {
      setIndexing(false);
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
      <Panel
        title="Private research assistant"
        aside={
          <Badge tone={assistant.data?.configured ? "green" : "amber"}>
            {assistant.data?.configured ? "Assistant ready" : "Needs Groq key"}
          </Badge>
        }
      >
        <Resource resource={assistant}>
          <div className="assistant-workspace">
            <div className="assistant-status-grid">
              <div className="assistant-status-item">
                <Database size={16} />
                <span>Indexed research</span>
                <strong>{number(assistant.data?.indexed_chunks, 0)} chunks</strong>
              </div>
              <div className="assistant-status-item">
                <Sparkles size={16} />
                <span>Retrieval mode</span>
                <strong>{assistant.data?.indexed_chunks ? "RAG enabled" : "Stored-record fallback"}</strong>
              </div>
              <Button variant="outline" disabled={indexing} onClick={() => void updateIndex()}>
                {indexing ? "Indexing…" : "Index stored research"}
              </Button>
            </div>
            <p className="assistant-disclosure">
              Answers use indexed trade, signal, performance, and documentation records when available. Relevant context is sent to Groq. Responses are research summaries, not trading instructions.
            </p>
            {!assistant.data?.configured && (
              <p className="notice" role="status">
                Add <code>GROQ_API_KEY</code> to the server environment to enable answers. You can prepare the local index first.
              </p>
            )}
            {assistantError && <p className="error-text" role="alert">{assistantError}</p>}
            <form className="assistant-form" onSubmit={ask}>
              <label className="field">
                Ask about the records
                <textarea
                  required
                  minLength={3}
                  maxLength={1000}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="For example: Which sessions have produced the most losses?"
                  disabled={!assistant.data?.configured || asking}
                />
              </label>
              <Button disabled={!assistant.data?.configured || asking || question.trim().length < 3} type="submit">
                <Bot size={15} />
                {asking ? "Searching records…" : "Ask research assistant"}
              </Button>
            </form>
            {answer && (
              <div className="assistant-answer" aria-live="polite">
                <div className="assistant-answer-heading">
                  <strong>Research response</strong>
                  <Badge tone={answer.rag_used ? "blue" : "neutral"}>
                    {answer.rag_used ? "RAG sources used" : "Record fallback"}
                  </Badge>
                </div>
                <p>{answer.answer || answer.response || answer.message || "No answer returned."}</p>
                {Array.isArray(answer.sources) && answer.sources.length > 0 && (
                  <div className="assistant-source-list">
                    {answer.sources.map((source: any, i: number) => (
                      <span key={`${source.type || source.collection || "source"}-${i}`}>
                        {source.label || source.type || source.collection || "Stored source"}
                        {source.coin ? ` · ${source.coin}` : ""}
                        {source.similarity != null ? ` · ${Math.round(source.similarity * 100)}% match` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </Resource>
      </Panel>
    </>
  );
}
