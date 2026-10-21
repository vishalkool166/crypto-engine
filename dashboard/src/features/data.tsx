import { useState, useEffect } from "react";

import { Database, Search } from "lucide-react";
import { useResource, number, time, words } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";
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

export function StoredData() {
  const catalog = useResource(base + "/data/catalog"),
    [table, setTable] = useState(""),
    [offset, setOffset] = useState(0),
    [query, setQuery] = useState(""),
    [appliedQuery, setAppliedQuery] = useState("");
  useEffect(() => {
    if (!table && catalog.data?.tables?.length)
      setTable(catalog.data.tables[0].name);
  }, [table, catalog.data]);
  const params = new URLSearchParams({ limit: "50", offset: String(offset) });
  if (appliedQuery) params.set("q", appliedQuery);
  const rows = useResource(
    table ? `${base}/data/${encodeURIComponent(table)}?${params}` : null,
  );
  const tables = catalog.data?.tables || [],
    active = tables.find((item: any) => item.name === table),
    columns = (rows.data?.columns || []).map((column: any) => ({
      key: column.name,
      label: `${column.name}${column.redacted ? " · redacted" : ""}`,
      render: (row: any) => {
        const value = row[column.name];
        if (value === null || value === undefined || value === "") return "—";
        const display =
          typeof value === "object" ? JSON.stringify(value) : String(value);
        return display.length > 240 ? display.slice(0, 237) + "…" : display;
      },
    }));
  function exportCurrentPage() {
    const data = rows.data;
    if (!data?.rows?.length) return;
    const fields = data.columns.map((column: any) => column.name);
    const escape = (value: any) =>
      `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [
      fields.map(escape).join(","),
      ...data.rows.map((row: any) =>
        fields
          .map((field: string) =>
            escape(
              typeof row[field] === "object"
                ? JSON.stringify(row[field])
                : row[field],
            ),
          )
          .join(","),
      ),
    ].join("\r\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${table}-${offset + 1}-${offset + data.rows.length}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <PageHead
        eyebrow="PERSISTED RECORDS"
        title="Inspect what this installation stores."
        description="Read-only, paginated access to the application tables. Sensitive credentials and session material are redacted."
        action={
          <Refresh
            onClick={() => {
              catalog.refresh();
              rows.refresh();
            }}
          />
        }
      />
      <Panel title="Database inventory">
        <Resource resource={catalog}>
          <div className="metric-grid">
            <Metric
              label="Application tables"
              value={number(catalog.data?.total_tables, 0)}
              note="SQLite application tables, excluding SQLite internals"
            />
            <Metric
              label="Selected records"
              value={number(active?.rows, 0)}
              note={active?.name || "Choose a table"}
            />
            <Metric
              label="Table purpose"
              value={active?.purpose || "—"}
              note={
                active?.sensitive
                  ? "Contains redacted fields"
                  : "No credential fields detected"
              }
            />
          </div>
          <form
            className="filters data-filters"
            onSubmit={(event) => {
              event.preventDefault();
              setOffset(0);
              setAppliedQuery(query.trim());
            }}
          >
            <label>
              Stored table
              <select
                value={table}
                onChange={(event) => {
                  setOffset(0);
                  setTable(event.target.value);
                }}
              >
                {tables.map((item: any) => (
                  <option key={item.name} value={item.name}>
                    {item.name} · {number(item.rows ?? 0, 0)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Search records
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                maxLength={100}
                placeholder="Instrument, outcome, status…"
              />
            </label>
            <Button type="submit">Apply search</Button>
            <Button
              type="button"
              variant="outline"
              disabled={!rows.data?.rows?.length}
              onClick={exportCurrentPage}
            >
              Export page CSV
            </Button>
          </form>
          {active && (
            <p className="panel-note">
              {active.purpose}.{" "}
              {active.sensitive
                ? "Credential-like values are redacted in the table and exports."
                : "Rows are read-only; no database writes are available from this view."}
            </p>
          )}
        </Resource>
      </Panel>
      <Panel
        title={table ? `Records · ${table}` : "Records"}
        aside={
          <span className="panel-note">
            {number(rows.data?.total ?? active?.rows, 0)} total
          </span>
        }
      >
        <Resource resource={rows}>
          <DataTable
            rows={rows.data?.rows || []}
            columns={columns}
            empty="No rows match this view"
          />
          <div className="data-pagination">
            <Button
              variant="outline"
              size="sm"
              disabled={offset <= 0}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous 50
            </Button>
            <span>
              Rows {rows.data?.total ? offset + 1 : 0}–
              {Math.min(offset + 50, rows.data?.total || 0)} of{" "}
              {number(rows.data?.total, 0)}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + 50 >= (rows.data?.total || 0)}
              onClick={() => setOffset(offset + 50)}
            >
              Next 50
            </Button>
          </div>
        </Resource>
      </Panel>
      <Panel title="Legacy account and plan records">
        <p className="panel-note">
          Customer signup, subscriptions, API-key access, and billing workflows
          are disabled. Historical rows remain in the database for review or
          export. Credential and session secrets are always redacted.
        </p>
      </Panel>
    </>
  );
}

export function Audit() {
  const r = useResource(base + "/audit/log?limit=100");
  return (
    <>
      <PageHead
        eyebrow="OPERATOR AUDIT"
        title="Audit trail"
        description="Security and operator events from this installation. Account-level data is restricted to the administrator."
        action={<Refresh onClick={r.refresh} />}
      />
      <Panel>
        <Resource resource={r}>
          <DataTable
            rows={r.data || []}
            columns={[
              {
                key: "timestamp",
                label: "Time",
                render: (r) => time(r.timestamp),
              },
              {
                key: "action",
                label: "Event",
                render: (r) => <strong>{words(r.action)}</strong>,
              },
              { key: "source", label: "Source" },
              {
                key: "success",
                label: "Result",
                render: (r) => (
                  <Badge tone={r.success ? "green" : "red"}>
                    {r.success ? "Success" : "Denied / failed"}
                  </Badge>
                ),
              },
              { key: "detail", label: "Detail" },
            ]}
          />
        </Resource>
      </Panel>
    </>
  );
}

export function Settings() {
  const r = useResource(base + "/settings");
  return (
    <>
      <PageHead
        eyebrow="DEPLOYMENT CONFIGURATION"
        title="Workspace settings"
        description="Read-only runtime configuration. Secret changes are made on AWS and Cloudflare, then applied through a controlled restart."
      />
      <Resource resource={r}>
        <div className="two-column">
          <Panel title="Canonical origins">
            <dl className="facts">
              <Fact label="Public application" value={r.data?.public_origin} />
              <Fact label="Operator application" value={r.data?.admin_origin} />
              <Fact
                label="Allowed administrator"
                value={r.data?.admin_emails?.join(", ")}
              />
              <Fact
                label="Session lifetime"
                value={r.data?.session_hours + " hours"}
              />
              <Fact label="Strategy version" value={r.data?.strategy_version} />
              <Fact label="Execution mode" value={words(r.data?.mode)} />
            </dl>
          </Panel>
          <Panel title="Credential presence">
            <dl className="facts">
              {Object.entries(r.data?.credentials || {}).map(([key, v]) => (
                <Fact
                  key={key}
                  label={words(key)}
                  value={
                    <Badge tone={v ? "green" : "amber"}>
                      {v ? "Configured" : "Not configured"}
                    </Badge>
                  }
                />
              ))}
            </dl>
            <p className="panel-note">
              Secret values are never returned to this application.
            </p>
          </Panel>
        </div>
      </Resource>
    </>
  );
}
