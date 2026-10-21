import { useCallback, useEffect, useState } from "react";
let csrf = "";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...options.headers,
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : null;
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof data?.detail === "string"
        ? data.detail
        : typeof data?.reason === "string"
          ? data.reason
          : "The service could not complete this request.",
    );
  if (data === null || typeof data !== "object")
    throw new ApiError(
      response.status || 502,
      "The API returned an invalid response. Check the Pages proxy and backend health.",
    );
  if (path === "/auth/session" && data?.csrf) csrf = data.csrf;
  if (data?.success === false)
    throw new ApiError(409, data.reason || "Operation declined");
  return data;
}
export function useResource(path: string | null, interval = 30000) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState<Error | null>(null),
    [loading, setLoading] = useState(true),
    [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    let active = true;
    const controller = new AbortController();
    setData(null);
    setLoading(true);
    setError(null);
    const load = () =>
      request(path, { signal: controller.signal })
        .then((value) => {
          if (active) {
            setData(value);
            setError(null);
          }
        })
        .catch((e) => {
          if (active && e.name !== "AbortError") setError(e);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    void load();
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, interval);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, [path, version, interval]);
  return { data, error, loading, refresh };
}
export function useConnection(privateApp: boolean) {
  const [state, setState] = useState("connecting");
  useEffect(() => {
    let stopped = false,
      socket: WebSocket | undefined,
      timer: number,
      attempt = 0;
    function connect() {
      if (stopped) return;
      socket = new WebSocket(
        (location.protocol === "https:" ? "wss:" : "ws:") +
          "//" +
          location.host +
          (privateApp ? "/ws/admin" : "/ws/public"),
      );
      socket.onopen = () => {
        attempt = 0;
        setState("connected");
      };
      socket.onmessage = (event) => {
        setState("connected");
        if (privateApp) {
          try {
            const payload = JSON.parse(event.data);
            if (payload?.mark_prices && typeof payload.mark_prices === "object") {
              window.dispatchEvent(new CustomEvent("signal-engine-stream", { detail: payload }));
            }
          } catch {
            // The stream can carry non-JSON control frames; connection state still updates.
          }
        }
      };
      socket.onerror = () => setState("reconnecting");
      socket.onclose = () => {
        if (!stopped) {
          setState("reconnecting");
          timer = window.setTimeout(
            connect,
            Math.min(30000, 1000 * 2 ** attempt++) + Math.random() * 1000,
          );
        }
      };
    }
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [privateApp]);
  return state;
}
export const number = (value: any, digits = 2) =>
  value === null || value === undefined || value === ""
    ? "—"
    : Number.isFinite(Number(value))
      ? Number(value).toLocaleString(undefined, {
          maximumFractionDigits: digits,
        })
      : "—";
export const price = (value: any) =>
  value === null || value === undefined
    ? "—"
    : number(value, Number(value) < 1 ? 6 : 4);
export const time = (value: any) =>
  !value
    ? "Not recorded"
    : new Date(typeof value === "number" ? value * 1000 : value).toLocaleString(
        undefined,
        { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" },
      );
export const words = (value: any) =>
  String(value ?? "unknown").replaceAll("_", " ");
