# Docker and Cloudflare operation

The complete domain, OAuth, Pages, secret, and DNS setup remains in
[DEPLOY.md](../DEPLOY.md). Apply the [2.1 upgrade guide](UPGRADE_2_1.md) when using
an existing database.

## Container startup

Use Docker Engine with the Compose plugin on Linux. The included stack runs Redis,
the API/engine, and Cloudflare Tunnel on the same private Docker network. Port 8000
is not published to the host. The tunnel's published hostname should route to
`http://signal-engine:8000`.

Configure `.env`, initialize directory ownership as described in DEPLOY.md, then:

```bash
docker compose config --quiet
docker compose pull redis cloudflared
docker compose up -d --build --remove-orphans
docker compose ps
docker compose logs --tail=100 cloudflared
```

The tunnel no longer waits on the engine healthcheck. A healthy connector does
not prove the engine is ready: check Admin → System health separately.
`TUNNEL_TOKEN` is required; Compose stops early with a readable error if missing.
HTTP/2 uses outbound TCP port 7844. If your network permits QUIC, you can set
`TUNNEL_PROTOCOL=auto`. Do not open inbound application ports to solve a tunnel
connection failure.

Cloudflared reconnects after network interruptions. Docker's `restart: always`
restarts an exited connector and restarts it when the daemon returns. A running
container marked unhealthy is not automatically restarted merely because it is
unhealthy. Logs and external uptime monitoring are still needed to detect a
persistent host/network/provider failure.

## Start after host reboot

On a systemd Linux host:

```bash
sudo systemctl enable --now docker
```

Use the supplied `deploy/signal-engine.service` if you also want systemd to run
Compose at boot. Put the repository at `/opt/signal-engine`, or edit WorkingDirectory
in the unit to your actual installation path. Then:

```bash
sudo cp deploy/signal-engine.service /etc/systemd/system/signal-engine.service
sudo systemctl daemon-reload
sudo systemctl enable --now signal-engine.service
sudo systemctl status signal-engine.service
```

The unit does not install Docker or copy secrets. Complete the configuration and
image build before enabling it. On Docker Desktop, enable Docker Desktop startup
in the operating system; Linux systemd instructions do not apply.

## Diagnose the tunnel

```bash
docker compose ps
docker compose logs --tail=100 cloudflared
docker compose logs --tail=100 signal-engine
```

- Token error: replace TUNNEL_TOKEN with the connector token for the intended tunnel.
- Connection refusal/502: verify `http://signal-engine:8000` in the tunnel route and
  inspect the engine logs. Do not use localhost as the service hostname there.
- Tunnel stays stopped after editing Compose: apply `docker compose up -d
  --force-recreate cloudflared`; `restart` does not recreate container settings.
- Host reboot: verify Docker is enabled and the containers exist. Compose must
  have created them at least once.
- Polling commands fail: inspect Telegram operations and Redis, not inbound tunnel
  routing. Polling only needs outbound Telegram HTTPS.

Keep BACKEND_ORIGIN and ORIGIN_PROXY_SECRET configured as server-side secrets in
both Pages projects. Backend requests require the trusted Pages proxy header;
normal browser calls to the tunnel origin are deliberately rejected.

## Backups

Back up the complete `database/` directory with the engine stopped or by using
SQLite's backup API for a consistent live backup. Preserve runtime_state.json and
the order journal with the trade data. Retain `.env` in a separate encrypted
secret backup. Do not delete Docker volumes during routine upgrades.

## Official references

- [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- [Compose service settings and restart policies](https://docs.docker.com/reference/compose-file/services/)
- [Tunnel run parameters](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/run-parameters/)
- [Cloudflared releases](https://github.com/cloudflare/cloudflared/releases)
