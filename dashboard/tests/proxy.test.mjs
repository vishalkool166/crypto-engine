import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { proxy } from "../functions/_shared/proxy.js";

const env = {
  APP_TARGET: "public",
  BACKEND_ORIGIN: "https://api.vishalkool.top",
  ORIGIN_PROXY_SECRET: "x".repeat(48),
};

test("Pages routing is limited to proxy prefixes and has no root catch-all", async () => {
  const routes = JSON.parse(await readFile(new URL("../public/_routes.json", import.meta.url), "utf8"));
  assert.deepEqual(routes.include, ["/api/*", "/auth/*", "/ws/*", "/webhook/*"]);
  assert.deepEqual(routes.exclude, []);
  assert.equal(routes.version, 1);
});

test("scoped public API forwards method, path, query and trusted edge headers", async () => {
  const originalFetch = globalThis.fetch;
  let sent;
  globalThis.fetch = async (url, init) => {
    sent = { url: String(url), init };
    return Response.json({ status: "ok" });
  };
  try {
    const request = new Request("https://app.vishalkool.top/api/v1/public/status?view=full", {
      method: "GET",
      headers: { host: "app.vishalkool.top", "cf-connecting-ip": "198.51.100.9", "x-origin-verify": "forged" },
    });
    const response = await proxy(request, env, "api");
    assert.equal(response.status, 200);
    assert.equal(sent.url, "https://api.vishalkool.top/api/v1/public/status?view=full");
    assert.equal(sent.init.headers.get("x-origin-verify"), env.ORIGIN_PROXY_SECRET);
    assert.equal(sent.init.headers.get("x-forwarded-app-host"), "app.vishalkool.top");
    assert.equal(sent.init.headers.get("x-visitor-ip"), "198.51.100.9");
    assert.equal(sent.init.headers.get("host"), null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("public Pages target cannot reach admin APIs, auth, webhooks, or mutate public data", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("must not reach backend"); };
  try {
    for (const [path, kind, method, status] of [
      ["/api/v1/admin/overview", "api", "GET", 404],
      ["/api/v1/public/status", "api", "POST", 405],
      ["/auth/session", "auth", "GET", 404],
      ["/webhook/telegram", "webhook", "POST", 404],
      ["/ws/admin", "ws", "GET", 404],
    ]) {
      const request = new Request("https://app.vishalkool.top" + path, { method });
      const response = await proxy(request, env, kind);
      assert.equal(response.status, status, path);
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("OAuth response keeps redirect and session cookie intact", async () => {
  const originalFetch = globalThis.fetch;
  const adminEnv = { ...env, APP_TARGET: "admin" };
  globalThis.fetch = async () => new Response(null, {
    status: 303,
    headers: { location: "https://admin-app.vishalkool.top/", "set-cookie": "__Host-se_operator=opaque; Secure; HttpOnly; Path=/; SameSite=Lax" },
  });
  try {
    const response = await proxy(new Request("https://admin-app.vishalkool.top/auth/callback/google"), adminEnv, "auth");
    assert.equal(response.status, 303);
    assert.equal(response.headers.get("location"), "https://admin-app.vishalkool.top/");
    assert.match(response.headers.get("set-cookie"), /HttpOnly/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("WebSocket bridge connects both directions and strips browser handshake keys", async () => {
  const originalFetch = globalThis.fetch;
  const OriginalResponse = globalThis.Response;
  const OriginalPair = globalThis.WebSocketPair;
  const OriginalWebSocket = globalThis.WebSocket;
  const sockets = [];
  class FakeSocket {
    readyState = 1;
    listeners = {};
    addEventListener(type, callback) { this.listeners[type] = callback; }
    accept() { this.accepted = true; }
    send(data) { (this.sent ||= []).push(data); }
    close(code, reason) { this.closed = [code, reason]; this.readyState = 3; }
  }
  globalThis.WebSocket = Object.assign(class {}, { OPEN: 1 });
  globalThis.WebSocketPair = class {
    constructor() {
      this.client = new FakeSocket();
      this.server = new FakeSocket();
      sockets.push(this.client, this.server);
    }
  };
  globalThis.Response = class {
    constructor(body, options) { this.body = body; Object.assign(this, options); }
    static json(data, options) { return { status: options?.status || 200, data }; }
  };
  const upstream = new FakeSocket();
  globalThis.fetch = async (url, init) => {
    assert.equal(String(url), "https://api.vishalkool.top/ws/public");
    assert.equal(init.headers.get("cookie"), "se_operator=opaque");
    assert.equal(init.headers.get("origin"), "https://app.vishalkool.top");
    assert.equal(init.headers.get("sec-websocket-key"), null);
    assert.equal(init.headers.get("x-origin-verify"), env.ORIGIN_PROXY_SECRET);
    return { webSocket: upstream };
  };
  try {
    const request = new Request("https://app.vishalkool.top/ws/public", {
      headers: {
        upgrade: "websocket", connection: "Upgrade", "sec-websocket-key": "browser-key",
        cookie: "se_operator=opaque", origin: "https://app.vishalkool.top",
      },
    });
    const response = await proxy(request, env, "ws");
    assert.equal(response.status, 101);
    const [, server] = sockets;
    server.listeners.message({ data: "from-browser" });
    assert.deepEqual(upstream.sent, ["from-browser"]);
    upstream.listeners.message({ data: "from-backend" });
    assert.deepEqual(server.sent, ["from-backend"]);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.Response = OriginalResponse;
    globalThis.WebSocketPair = OriginalPair;
    globalThis.WebSocket = OriginalWebSocket;
  }
});
