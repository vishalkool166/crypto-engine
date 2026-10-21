import { lazy, Suspense, useState, useEffect } from "react";
import {
  Routes,
  Route,
  NavLink,
  Link,
  useLocation,
  Navigate,
} from "react-router-dom";
import {
  ArrowUpRight,
  ArrowRight,
  Activity,
  Layers3,
  Radio,
  ShieldCheck,
  FlaskConical,
  Globe2,
  Settings2,
  Send,
  Menu,
  X,
  LogOut,
  Check,
  ChevronRight,
  Wallet,
  Database,
  ScrollText,
  Search,
} from "lucide-react";

import { ExecutionMode, ExecutionProvider } from "./components/ExecutionMode";
import { WorkspaceMotion } from "./components/WorkspaceMotion";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import { request, useResource, useConnection, ApiError } from "./api";
const PWA =
  __APP_TARGET__ === "public" ? lazy(() => import("./PWA")) : () => null;

import { ADMIN } from "./lib/app";
import { Brand, ThemeToggle, PageHead, Resource } from "./components/workspace";
import {
  PublicOverview,
  Methodology,
  PublicPerformance,
  PublicStatus,
} from "./features/public";
import { SignalList, SignalDetail } from "./features/signals";
import { AdminOverview } from "./features/overview";
import { PaperTrades } from "./features/trades";
import { AdminPerformance } from "./features/performance";
import { System } from "./features/system";
import { Markets, India } from "./features/markets";
import { Research } from "./features/research";
import { Telegram } from "./features/telegram";
import { StoredData, Audit, Settings } from "./features/data";

function Login() {
  const reason = new URLSearchParams(location.search).get("error");
  return (
    <main className="login-layout">
      <div className="login-theme">
        <ThemeToggle />
      </div>
      <aside className="login-art">
        <Brand admin />
        <div className="login-art-grid" />
        <div>
          <p className="eyebrow">YOUR PRIVATE WORKSPACE</p>
          <h2>
            Every decision.
            <br />A clearer view.
          </h2>
          <p>
            Research, execution, and the complete trade journey in one operator
            workspace.
          </p>
        </div>
        <small>Signal Engine / Private access</small>
      </aside>
      <section className="login-form">
        <div className="login-card">
          <Brand admin />
          <p className="eyebrow">OPERATOR ACCESS</p>
          <h1>Sign in to Signal Engine</h1>
          <p>
            Continue with the Google account on the administrator allowlist.
          </p>
          {reason && (
            <div className="notice" role="alert">
              {reason === "unauthorized"
                ? "This Google account is not an authorized administrator."
                : "Google sign-in could not be completed. Try again or check the server configuration."}
            </div>
          )}
          <Button asChild className="google-button">
            <a href="/auth/google">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  fill="currentColor"
                  d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.8 3-4.3 3-7.3ZM12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.9-1.8-5.7-4.2H3v2.6A10 10 0 0 0 12 22ZM6.3 13.9a6 6 0 0 1 0-3.8V7.5H3a10 10 0 0 0 0 9l3.3-2.6ZM12 5.9c1.5 0 2.8.5 3.8 1.5l2.9-2.8A9.5 9.5 0 0 0 12 2a10 10 0 0 0-9 5.5l3.3 2.6A6 6 0 0 1 12 5.9Z"
                />
              </svg>
              Continue with Google
              <ArrowUpRight size={16} />
            </a>
          </Button>
          <div className="login-security">
            <ShieldCheck size={14} /> Google verifies your identity
            <Check size={14} /> Access is checked by the server
          </div>
          <p className="login-fineprint">
            This application has no customer registration. Access is limited to
            the configured operator.
          </p>
        </div>
      </section>
    </main>
  );
}

function AdminGate() {
  const r = useResource("/auth/session", 60000);
  if (r.loading)
    return (
      <div className="screen-loading">
        <Brand admin />
        <span className="spinner" />
        Verifying operator session
      </div>
    );
  if (r.error) {
    if (r.error instanceof ApiError && r.error.status === 401) return <Login />;
    return (
      <div className="login-error">
        <Brand admin />
        <Resource resource={r}>{null}</Resource>
      </div>
    );
  }
  return (
    <ExecutionProvider>
      <AdminShell email={r.data.user.email} />
    </ExecutionProvider>
  );
}

const publicNav = [
  ["/", "Overview"],
  ["/signals", "Signals"],
  ["/performance", "Performance"],
  ["/methodology", "Methodology"],
  ["/status", "Status"],
];

const adminNav = [
  { path: "/", name: "Overview", icon: Layers3 },
  { path: "/signals", name: "Signals", icon: Radio },
  { path: "/trades", name: "Trades & journey", icon: Wallet },
  { path: "/performance", name: "Performance", icon: Activity },
  { path: "/markets", name: "Crypto universe", icon: Globe2 },
  { path: "/india", name: "Indian markets", icon: Activity },
  { path: "/research", name: "Research", icon: FlaskConical },
  { path: "/data", name: "Stored data", icon: Database },
  { path: "/system", name: "System health", icon: Activity },
  { path: "/telegram", name: "Telegram", icon: Send },
  { path: "/audit", name: "Audit trail", icon: ScrollText },
  { path: "/settings", name: "Settings", icon: Settings2 },
];

function NavigationSearch() {
  const [open, setOpen] = useState(false),
    [query, setQuery] = useState("");
  const location = useLocation();
  useEffect(() => {
    setOpen(false);
    setQuery("");
  }, [location.pathname]);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, []);
  return (
    <>
      <button className="nav-search" onClick={() => setOpen(true)}>
        <Search size={14} />
        Find a page<kbd>Ctrl K</kbd>
      </button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Navigate workspace"
        description="Find an admin page by name."
      >
        <label className="field">
          Search pages
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Performance, trade journey, Telegram…"
          />
        </label>
        <ul className="command-results">
          {adminNav
            .filter((n) => n.name.toLowerCase().includes(query.toLowerCase()))
            .map(({ path, name, icon: Icon }) => (
              <li key={path}>
                <Link to={path} onClick={() => setOpen(false)}>
                  <Icon size={15} />
                  {name}
                  <ArrowRight size={13} />
                </Link>
              </li>
            ))}
        </ul>
      </Dialog>
    </>
  );
}

function MobileNavigation({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="sheet-overlay" />
        <DialogPrimitive.Content className="sheet-content">
          <DialogPrimitive.Title className="sr-only">
            Operator navigation
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Pages in your private workspace
          </DialogPrimitive.Description>
          <Brand admin />
          <DialogPrimitive.Close
            className="dialog-close"
            aria-label="Close navigation"
          >
            <X size={20} />
          </DialogPrimitive.Close>
          <nav className="sheet-nav" aria-label="Mobile operator navigation">
            {adminNav.map(({ path, name, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                end={path === "/"}
                onClick={() => setOpen(false)}
              >
                <Icon size={17} />
                {name}
              </NavLink>
            ))}
          </nav>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function AdminShell({ email }: { email: string }) {
  const [open, setOpen] = useState(false),
    [logoutError, setLogoutError] = useState(""),
    conn = useConnection(true),
    location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  async function logout() {
    try {
      await request("/auth/logout", { method: "POST" });
      window.location.assign("/login");
    } catch (e) {
      setLogoutError((e as Error).message);
    }
  }
  return (
    <div className="admin-shell">
      <MobileNavigation open={open} setOpen={setOpen} />
      <aside className={"sidebar " + (open ? "is-open" : "")}>
        <Brand admin />
        <button
          className="mobile-close"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X />
        </button>
        <NavigationSearch />
        <div className="sidebar-section">Workspace</div>
        <nav aria-label="Operator navigation">
          {adminNav.map(({ path, name, icon: Icon }, index) => (
            <div key={path}>
              {index === 4 && (
                <div className="nav-group-label">Markets & research</div>
              )}
              {index === 8 && <div className="nav-group-label">Operations</div>}
              <NavLink to={path} end={path === "/"}>
                <Icon size={17} />
                {name}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="avatar">{email.charAt(0).toUpperCase()}</span>
          <div>
            <strong>Administrator</strong>
            <small title={email}>{email}</small>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Sign out"
            onClick={logout}
          >
            <LogOut size={16} />
          </Button>
        </div>
      </aside>
      <div className="admin-content">
        <WorkspaceMotion />
        <header className="operator-bar">
          <button
            className="mobile-menu"
            aria-label="Open navigation"
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <Menu size={22} />
          </button>
          <span className="operator-breadcrumb">
            Workspace <ChevronRight size={13} />
            <strong>
              {adminNav.find((item) => item.path === location.pathname)?.name ||
                "Signal detail"}
            </strong>
          </span>
          <div>
            <ThemeToggle />
            <ExecutionMode />
            <span
              className={"connection " + (conn === "connected" ? "online" : "")}
            >
              <span />
              {conn === "connected" ? "Stream connected" : "Polling fallback"}
            </span>
          </div>
        </header>
        <main className="workspace">
          {logoutError && (
            <div className="notice" role="alert">
              {logoutError}
            </div>
          )}
          <Routes>
            <Route path="/" element={<AdminOverview />} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/signals" element={<SignalList />} />
            <Route path="/signals/:id" element={<SignalDetail />} />
            <Route path="/trades" element={<PaperTrades />} />
            <Route path="/performance" element={<AdminPerformance />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/india" element={<India />} />
            <Route path="/research" element={<Research />} />
            <Route path="/data" element={<StoredData />} />
            <Route path="/system" element={<System />} />
            <Route path="/telegram" element={<Telegram />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="operator-footer">
          Private operator workspace{" "}
          <span>Signal Engine · Operator release</span>
        </footer>
      </div>
    </div>
  );
}

function NotFound() {
  return (
    <>
      <PageHead
        eyebrow="404"
        title="This view does not exist."
        description="Use the navigation to return to the workspace."
      />
      <Button asChild variant="outline">
        <Link to="/">Return to overview</Link>
      </Button>
    </>
  );
}

function PublicShell() {
  const [open, setOpen] = useState(false),
    conn = useConnection(false),
    location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  return (
    <div className="public-shell">
      <WorkspaceMotion />
      <header className="public-header">
        <Brand />
        <nav className={open ? "open" : ""} aria-label="Public navigation">
          {publicNav.map(([path, label]) => (
            <NavLink key={path} end={path === "/"} to={path}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="header-status">
          <ThemeToggle />
          <span
            className={"connection " + (conn === "connected" ? "online" : "")}
          >
            <span />
            {conn === "connected" ? "Connected" : "Reconnecting"}
          </span>
          <button
            className="mobile-menu"
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </header>
      <main className="public-main">
        <Routes>
          <Route path="/" element={<PublicOverview />} />
          <Route path="/signals" element={<SignalList />} />
          <Route path="/signals/:id" element={<SignalDetail />} />
          <Route path="/performance" element={<PublicPerformance />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/status" element={<PublicStatus />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="public-footer">
        <Brand />
        <p>
          Open research. Recorded decisions.
          <small>
            Signals are experimental model outputs. No validated trading edge is
            claimed.
          </small>
        </p>
        <Link to="/methodology">
          Method & limitations <ArrowUpRight size={14} />
        </Link>
      </footer>
      <Suspense fallback={null}>
        <PWA />
      </Suspense>
    </div>
  );
}

export default function App() {
  return ADMIN ? <AdminGate /> : <PublicShell />;
}
