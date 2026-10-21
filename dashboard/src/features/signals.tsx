import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, ArrowLeft, FlaskConical, Search } from "lucide-react";
import { useResource, number, price, time, words } from "../api";
import { ADMIN, base } from "../lib/app";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Empty,
  Resource,
  Refresh,
  Fact,
  DataTable,
  signalColumns,
  Trace,
} from "../components/workspace";

export function SignalList() {
  const [coin, setCoin] = useState(
      () => new URLSearchParams(window.location.search).get("coin") || "",
    ),
    [grade, setGrade] = useState(""),
    [offset, setOffset] = useState(0),
    [filter, setFilter] = useState(
      () => new URLSearchParams(window.location.search).get("coin") || "",
    );
  const r = useResource(
    "/api/v1/public/signals?limit=20&offset=" +
      offset +
      "&coin=" +
      encodeURIComponent(filter) +
      "&grade=" +
      encodeURIComponent(grade),
  );
  const traces = useResource(ADMIN ? base + "/engine/traces?limit=20" : null);
  return (
    <>
      <PageHead
        eyebrow="SIGNAL LEDGER"
        title="Signal ledger"
        description="Timestamped model outputs with recorded levels and outcomes. These are paper-research signals, not execution instructions."
        action={
          <Refresh
            onClick={() => {
              r.refresh();
              traces.refresh();
            }}
          />
        }
      />
      <Panel>
        <form
          className="filters"
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            setFilter(coin.toUpperCase().trim());
          }}
        >
          <label>
            Instrument
            <input
              value={coin}
              maxLength={12}
              onChange={(e) => setCoin(e.target.value)}
              placeholder="Search symbol"
              aria-label="Filter by instrument"
            />
          </label>
          <label>
            Grade
            <select
              value={grade}
              onChange={(e) => {
                setGrade(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All grades</option>
              <option>A+</option>
              <option>A</option>
              <option>B</option>
              <option>F</option>
            </select>
          </label>
          <Button variant="outline" type="submit">
            Apply filter
          </Button>
          <span className="muted">
            {r.data ? number(r.data.total, 0) + " records" : ""}
          </span>
        </form>
        <Resource resource={r}>
          <DataTable rows={r.data?.items || []} columns={signalColumns} />
          <div className="pagination">
            <span>Page {offset / 20 + 1}</span>
            <div>
              <Button
                variant="ghost"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((v) => Math.max(0, v - 20))}
              >
                <ArrowLeft size={14} />
                Previous
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!r.data || offset + 20 >= r.data.total}
                onClick={() => setOffset((v) => v + 20)}
              >
                Next
                <ArrowRight size={14} />
              </Button>
            </div>
          </div>
        </Resource>
      </Panel>
      {ADMIN && (
        <Panel title="Recent decision traces">
          <Resource resource={traces}>
            {traces.data?.traces?.length ? (
              <div className="trace-list">
                {traces.data.traces.map((trace: any, i: number) => (
                  <details key={i}>
                    <summary>
                      <strong>{trace.coin}</strong>
                      <Badge>{words(trace.final_decision)}</Badge>
                      <span>
                        {trace.stopped_at
                          ? words(trace.stopped_at)
                          : trace.final_grade}
                      </span>
                      <small>{time(trace.datetime || trace.timestamp)}</small>
                    </summary>
                    <Trace steps={trace.steps || []} />
                  </details>
                ))}
              </div>
            ) : (
              <Empty title="No decision traces recorded">
                New scans will record approvals and rejections here.
              </Empty>
            )}
          </Resource>
        </Panel>
      )}
    </>
  );
}

export function SignalDetail() {
  const { id } = useParams(),
    r = useResource("/api/v1/public/signals/" + id),
    d = r.data;
  return (
    <>
      <Link className="text-link back-link" to="/signals">
        <ArrowLeft size={14} /> Signal ledger
      </Link>
      <PageHead
        eyebrow={"RECORD / " + id}
        title={d ? d.coin + " · " + d.direction : "Signal record"}
        description="Persisted model levels at generation time. Prices may have changed since this record was created."
        action={
          d && <Badge>{d.grade + " · " + number(d.score, 0) + "/100"}</Badge>
        }
      />
      <Resource resource={r}>
        <div className="two-column">
          <Panel title="Signal specification">
            <dl className="facts">
              <Fact label="Generated" value={time(d?.timestamp)} />
              <Fact label="Model entry" value={price(d?.entry)} />
              <Fact label="Stop level" value={price(d?.sl)} />
              <Fact label="Target 1" value={price(d?.tp1)} />
              <Fact label="Target 2" value={price(d?.tp2)} />
              <Fact
                label="Recorded outcome"
                value={<Badge>{words(d?.outcome)}</Badge>}
              />
              <Fact
                label="Strategy version"
                value={d?.system_version || "Not recorded"}
              />
            </dl>
          </Panel>
          <Panel title="Decision trace">
            {d?.trace?.length ? (
              <Trace steps={d.trace} />
            ) : (
              <Empty title="Trace not recorded">
                Earlier records may predate persisted decision traces. No
                reconstructed trace is substituted.
              </Empty>
            )}
          </Panel>
        </div>
        <div className="notice">
          <FlaskConical size={20} />
          <p>
            Grades represent a rule-based score. They are not a measured
            probability of a profitable trade. The strategy has not completed
            out-of-sample validation.
          </p>
        </div>
      </Resource>
    </>
  );
}
