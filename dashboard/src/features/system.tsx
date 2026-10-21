import { useResource, number, time, words } from "../api";
import { base } from "../lib/app";

import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Metric,
  Resource,
  Refresh,
  Fact,
  DataTable,
} from "../components/workspace";

export function System() {
  const r = useResource(base + "/health"),
    reject = useResource(base + "/engine/rejections"),
    engine = useResource(base + "/engine/health"),
    traces = useResource(base + "/engine/traces?limit=50"),
    filters = useResource(base + "/engine/filter-analysis"),
    strength = useResource(base + "/engine/relative-strength");
  return (
    <>
      <PageHead
        eyebrow="SYSTEM HEALTH"
        title="System health"
        description="Readiness checks and scanner telemetry. A reachable API alone does not establish engine readiness."
        action={
          <Refresh
            onClick={() => {
              r.refresh();
              reject.refresh();
              engine.refresh();
              traces.refresh();
              filters.refresh();
              strength.refresh();
            }}
          />
        }
      />
      <Resource resource={r}>
        <div className="two-column">
          <Panel title="Dependencies">
            <dl className="facts">
              {Object.entries(r.data?.checks || {}).map(([key, v]) => (
                <Fact
                  key={key}
                  label={words(key)}
                  value={
                    <Badge tone={v === "connected" ? "green" : "red"}>
                      {String(v)}
                    </Badge>
                  }
                />
              ))}
              <Fact label="Runtime" value={words(r.data?.runtime)} />
              <Fact label="Observed" value={time(r.data?.timestamp)} />
            </dl>
          </Panel>
          <Panel title="Scan telemetry">
            <dl className="facts">
              <Fact
                label="Last completed scan"
                value={time(r.data?.scan?.last_scan_at)}
              />
              <Fact
                label="Scan duration"
                value={number(r.data?.scan?.last_scan_ms, 0) + " ms"}
              />
              <Fact
                label="Instruments analyzed"
                value={number(r.data?.scan?.last_scan_count, 0)}
              />
              <Fact
                label="Total scans"
                value={number(r.data?.scan?.total_scans, 0)}
              />
            </dl>
          </Panel>
        </div>
      </Resource>
      <Panel title="Rejection reasons">
        <Resource resource={reject}>
          <DataTable
            rows={Array.isArray(reject.data?.top) ? reject.data.top : []}
            columns={[
              {
                key: "reason",
                label: "Reason",
                render: (r) => words(r.reason || r.filter),
              },
              {
                key: "count",
                label: "Count",
                render: (r) => number(r.count, 0),
              },
            ]}
            empty="No rejection summary available"
          />
        </Resource>
      </Panel>
      <div className="two-column">
        <Panel title="Engine diagnostics">
          <Resource resource={engine}>
            <dl className="facts">
              {Object.entries(engine.data || {})
                .filter(
                  ([, value]) =>
                    value === null ||
                    ["string", "number", "boolean"].includes(typeof value),
                )
                .map(([key, value]) => (
                  <Fact
                    key={key}
                    label={words(key)}
                    value={String(value ?? "—")}
                  />
                ))}
              {engine.data?.scan_stats && (
                <Fact
                  label="Scan statistics"
                  value={<code>{JSON.stringify(engine.data.scan_stats)}</code>}
                />
              )}
            </dl>
          </Resource>
        </Panel>
        <Panel title="Relative strength ranking">
          <Resource resource={strength}>
            <dl className="facts">
              <Fact
                label="Ranked instruments"
                value={number(strength.data?.total, 0)}
              />
              <Fact
                label="High tier"
                value={number(strength.data?.high_tier, 0)}
              />
              <Fact
                label="Medium tier"
                value={number(strength.data?.medium_tier, 0)}
              />
              <Fact
                label="Low tier"
                value={number(strength.data?.low_tier, 0)}
              />
            </dl>
            <DataTable
              rows={strength.data?.top_5 || []}
              columns={[
                { key: "rank", label: "Rank" },
                { key: "coin", label: "Instrument" },
                {
                  key: "total_score",
                  label: "Score",
                  render: (row) => number(row.total_score, 2),
                },
                {
                  key: "rs",
                  label: "Relative strength",
                  render: (row) => number(row.rs, 2) + "%",
                },
                {
                  key: "tier",
                  label: "Tier",
                  render: (row) => words(row.tier),
                },
              ]}
              empty="Relative strength data is not available yet"
            />
          </Resource>
        </Panel>
      </div>
      <Panel title="Decision traces">
        <Resource resource={traces}>
          <DataTable
            rows={traces.data?.traces || []}
            columns={[
              {
                key: "datetime",
                label: "Time",
                render: (row) => time(row.datetime || row.timestamp),
              },
              {
                key: "coin",
                label: "Instrument",
                render: (row) => <strong>{row.coin}</strong>,
              },
              { key: "direction", label: "Direction" },
              {
                key: "final_decision",
                label: "Decision",
                render: (row) => words(row.final_decision),
              },
              { key: "final_grade", label: "Grade" },
              {
                key: "final_score",
                label: "Score",
                render: (row) => number(row.final_score, 1),
              },
              {
                key: "stopped_at",
                label: "Stopped at",
                render: (row) => words(row.stopped_at || "Completed"),
              },
              {
                key: "steps",
                label: "Filter steps",
                render: (row) =>
                  Array.isArray(row.steps)
                    ? row.steps
                        .map((step: any) => `${step.name}: ${step.result}`)
                        .join(" · ")
                    : "—",
              },
            ]}
            empty="No decision traces have been recorded in the active trace window"
          />
        </Resource>
      </Panel>
      <Panel title="Filter analysis">
        <Resource resource={filters}>
          <div className="metric-grid">
            <Metric
              label="Scans evaluated"
              value={number(filters.data?.total_scans, 0)}
              note="Recent filter telemetry"
            />
            <Metric
              label="Signals produced"
              value={number(filters.data?.total_signals, 0)}
              note="Signals recorded by the scanner"
            />
            <Metric
              label="Signal rate"
              value={number(filters.data?.signal_rate, 0) + "%"}
              note="Recorded signals per scan"
            />
          </div>
          <DataTable
            rows={filters.data?.filter_analysis || []}
            columns={[
              { key: "filter", label: "Filter" },
              {
                key: "total_count",
                label: "Rejections",
                render: (row) => number(row.total_count, 0),
              },
              {
                key: "pct_of_scans",
                label: "Share",
                render: (row) => number(row.pct_of_scans, 1) + "%",
              },
              {
                key: "impact",
                label: "Impact",
                render: (row) => words(row.impact),
              },
            ]}
            empty="No filter analysis is available yet"
          />
        </Resource>
      </Panel>
    </>
  );
}
