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
        description="Read-only runtime configuration. Secret changes are made in your private server or hosting-provider configuration, then applied through a controlled restart."
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
