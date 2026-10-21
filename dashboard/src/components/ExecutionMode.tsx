import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { ArrowLeftRight, Check, LockKeyhole, AlertCircle } from "lucide-react";
import { request, useResource } from "../api";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
const path = "/api/v1/admin/execution/mode";
type Mode = "paper" | "live";
const ExecutionContext = createContext<ReturnType<typeof useResource> | null>(
  null,
);
export function ExecutionProvider({ children }: { children: ReactNode }) {
  const resource = useResource(path, 10000);
  return (
    <ExecutionContext.Provider value={resource}>
      {children}
    </ExecutionContext.Provider>
  );
}
export function useExecution() {
  return useContext(ExecutionContext);
}
export function ExecutionMode() {
  const resource = useExecution();
  const [open, setOpen] = useState(false),
    [target, setTarget] = useState<Mode>("live"),
    [totp, setTotp] = useState(""),
    [confirmation, setConfirmation] = useState(""),
    [busy, setBusy] = useState(false),
    [waiting, setWaiting] = useState(false),
    [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const current: Mode | undefined = resource?.data?.mode;
  const phrase = target === "live" ? "ENABLE LIVE TRADING" : "RETURN TO PAPER";
  const checks = [
    [Boolean(resource?.data?.totp_configured), "Authenticator configured"],
    [
      Boolean(
        resource?.data?.restart_enabled && resource?.data?.engine_enabled,
      ),
      "Managed engine restart enabled",
    ],
    [
      Boolean(
        target === "live"
          ? resource?.data?.live_available
          : resource?.data?.paper_available,
      ),
      target === "live"
        ? "Live credentials and server opt-in"
        : "Paper exchange credentials",
    ],
  ] as const;
  useEffect(() => {
    if (!waiting) return;
    const started = Date.now();
    const timer = setInterval(async () => {
      try {
        const status = await request(path);
        if (status.mode === target && !status.transitioning) {
          window.location.reload();
          return;
        }
      } catch {
        /* The API is briefly unavailable during the managed restart. */
      }
      if (mounted.current && Date.now() - started > 120000) {
        clearInterval(timer);
        setWaiting(false);
        setError(
          "Restart has not completed. Check Docker logs and System health before retrying.",
        );
        resource?.refresh();
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [waiting, target]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      await request(path, {
        method: "POST",
        body: JSON.stringify({
          target,
          expected_mode: current,
          confirmation,
          totp_code: totp,
        }),
      });
      setWaiting(true);
      setTotp("");
    } catch (e) {
      setError((e as Error).message);
      setTotp("");
      resource?.refresh();
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        className="mode-trigger"
        data-live={current === "live"}
        onClick={() => {
          setOpen(true);
          setTarget(current === "live" ? "paper" : "live");
          setError("");
          setTotp("");
          setConfirmation("");
          resource?.refresh();
        }}
        aria-label="Change execution mode"
      >
        <span className={current === "live" ? "live-dot" : "paper-dot"} />
        {current ? current.toUpperCase() : "MODE"}
        <small>Change</small>
        <ArrowLeftRight size={12} />
      </button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!busy && !waiting) setOpen(next);
        }}
        title="Execution environment"
        description="Switch the engine account with your authenticator. Positions and orders must be resolved before switching."
      >
        {waiting ? (
          <div className="mode-wait" role="status">
            <span className="spinner" /> Restarting the engine in {target} mode.
            This view will reconnect automatically.
          </div>
        ) : (
          <form onSubmit={submit}>
            {resource?.error && (
              <div className="error-state" role="alert">
                {resource.error.message}
                <Button
                  type="button"
                  variant="outline"
                  onClick={resource.refresh}
                >
                  Retry
                </Button>
              </div>
            )}
            <Tabs.Root
              value={target}
              onValueChange={(v) => {
                setTarget(v as Mode);
                setConfirmation("");
              }}
            >
              <Tabs.List
                className="mode-options"
                aria-label="Target environment"
              >
                <Tabs.Trigger
                  value="paper"
                  disabled={current === "paper" || busy}
                >
                  Paper / demo
                </Tabs.Trigger>
                <Tabs.Trigger
                  value="live"
                  disabled={current === "live" || busy}
                >
                  Live account
                </Tabs.Trigger>
              </Tabs.List>
            </Tabs.Root>
            <div className="notice">
              <LockKeyhole size={18} />
              <div>
                {target === "live"
                  ? "Live mode can place orders using real account funds."
                  : "Paper mode uses your Binance demo account."}
                <br />
                Switching restarts the engine; it does not transfer balances or
                close trades.
              </div>
            </div>
            <ul className="mode-checks">
              {checks.map(([ok, label]) => (
                <li key={label} className={ok ? "positive" : "muted"}>
                  {ok ? <Check size={15} /> : <AlertCircle size={15} />}
                  {label}
                </li>
              ))}
            </ul>
            <label className="field">
              Type {phrase}
              <input
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                autoComplete="off"
                required
                disabled={busy}
              />
            </label>
            <label className="field">
              Six-digit authenticator code
              <input
                className="totp-input"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                autoComplete="one-time-code"
                value={totp}
                onChange={(e) => setTotp(e.target.value.replace(/\D/g, ""))}
                required
                disabled={busy}
              />
            </label>
            {error && (
              <p role="alert" className="error-text">
                {error}
              </p>
            )}
            <div className="mode-actions">
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={busy}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={
                  busy ||
                  !current ||
                  !checks.every((c) => c[0]) ||
                  confirmation !== phrase ||
                  totp.length !== 6
                }
                variant={target === "live" ? "destructive" : "default"}
              >
                {busy ? "Verifying accounts…" : `Confirm ${target} mode`}
              </Button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  );
}
