function error(status, detail) {
  return Response.json({ detail }, { status, headers: {
    "Cache-Control": "no-store",
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
  } });
}

function backendUrl(request, env) {
  let origin;
  try { origin = new URL(env.BACKEND_ORIGIN); }
  catch { throw new Error("BACKEND_ORIGIN is missing or invalid"); }
  if (origin.protocol !== "https:" || origin.username || origin.password || origin.pathname !== "/" || origin.search || origin.hash) {
    throw new Error("BACKEND_ORIGIN must be an HTTPS origin");
  }
  const incoming = new URL(request.url);
  if (!incoming.hostname) throw new Error("A valid app host is required");
  const target = new URL(incoming.pathname + incoming.search, origin);
  if (!env.ORIGIN_PROXY_SECRET || env.ORIGIN_PROXY_SECRET.length < 32) {
    throw new Error("ORIGIN_PROXY_SECRET is not configured");
  }
  return { incoming, target };
}

function forwardedHeaders(request, env, incoming) {
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("x-origin-verify");
  headers.delete("x-forwarded-app-host");
  headers.delete("x-visitor-ip");
  headers.set("x-origin-verify", env.ORIGIN_PROXY_SECRET);
  headers.set("x-forwarded-app-host", incoming.host);
  const ip = request.headers.get("cf-connecting-ip");
  if (ip) headers.set("x-visitor-ip", ip);
  return headers;
}

function withResponseHeaders(response) {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", "no-store");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("Strict-Transport-Security", "max-age=31536000");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

function relay(from, to) {
  from.addEventListener("message", (event) => {
    if (to.readyState === WebSocket.OPEN) to.send(event.data);
  });
  from.addEventListener("close", (event) => {
    if (to.readyState === WebSocket.OPEN) {
      const reserved = new Set([1004, 1005, 1006, 1015]);
      const code = event.code >= 1000 && event.code <= 4999 && !reserved.has(event.code)
        ? event.code
        : 1000;
      to.close(code, event.reason || "");
    }
  });
  from.addEventListener("error", () => {
    if (to.readyState === WebSocket.OPEN) to.close(1011, "WebSocket proxy error");
  });
}

async function proxyWebSocket(request, env, target, headers) {
  if (request.method !== "GET" || request.headers.get("upgrade")?.toLowerCase() !== "websocket") {
    return error(426, "A WebSocket upgrade is required");
  }
  headers.delete("connection");
  headers.delete("sec-websocket-key");
  headers.delete("sec-websocket-version");
  headers.delete("sec-websocket-extensions");
  const upstream = await fetch(target, { method: "GET", headers, redirect: "manual" });
  if (!upstream.webSocket) {
    return new Response(upstream.body, { status: upstream.status, headers: upstream.headers });
  }
  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair);
  const originSocket = upstream.webSocket;
  server.accept();
  originSocket.accept();
  relay(server, originSocket);
  relay(originSocket, server);
  return new Response(null, { status: 101, webSocket: client });
}

export async function proxy(request, env, kind) {
  const appTarget = env.APP_TARGET;
  if (appTarget !== "public" && appTarget !== "admin") return error(503, "Pages APP_TARGET must be public or admin");
  const url = new URL(request.url);
  const isPublicApi = url.pathname.startsWith("/api/v1/public/");
  const isPublicSocket = url.pathname === "/ws/public";
  const isAdminSocket = url.pathname === "/ws/admin";
  if (appTarget === "public" && kind === "auth") return error(404, "Not found");
  if (appTarget === "public" && kind === "api" && !isPublicApi) return error(404, "Not found");
  if (appTarget === "public" && kind === "api" && !["GET", "HEAD"].includes(request.method)) return error(405, "Method not allowed");
  if (kind === "ws" && !(isPublicSocket || (appTarget === "admin" && isAdminSocket))) return error(404, "Not found");
  try {
    const { incoming, target } = backendUrl(request, env);
    const headers = forwardedHeaders(request, env, incoming);
    if (kind === "ws") return await proxyWebSocket(request, env, target, headers);
    const init = { method: request.method, headers, redirect: "manual" };
    if (request.method !== "GET" && request.method !== "HEAD") init.body = request.body;
    const response = await fetch(target, init);
    return withResponseHeaders(response);
  } catch (e) {
    // Do not echo origin configuration, credentials, or exception text to callers.
    return error(502, "The application service could not be reached");
  }
}
