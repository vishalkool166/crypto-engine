export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const backend = "https://signal-engine-v5.vishalkool.top";
  const target = backend + url.pathname + url.search;

  const headers = new Headers(request.headers);
  headers.set("x-origin-verify", env.ORIGIN_PROXY_SECRET || "");
  headers.set("x-forwarded-app-host", url.host);

  const init = {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    redirect: "manual",
  };

  return fetch(target, init);
}