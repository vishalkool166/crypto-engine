import { h } from '/js/preact.min.js'
import { useState, useEffect } from '/js/preact-hooks.min.js'
import { html, Spinner, EmptyState, LoadingSkeleton } from '/js/components.js'
import { showToast, requireTotp, useMode } from '/js/store.js'

export function SettingsPage() {
    const [health,        setHealth]       = useState(null)
    const [system,        setSystem]       = useState(null)
    const [loading,       setLoading]      = useState(false)
    const [modeLoading,   setModeLoading]  = useState(null)
    const [modeMsg,       setModeMsg]      = useState('')
    const [modeOk,        setModeOk]       = useState(false)
    const [actionLoading, setActionLoading]= useState(null)
    const [actionMsg,     setActionMsg]    = useState('')
    const [actionOk,      setActionOk]     = useState(false)
    const [purgeLoading,  setPurgeLoading] = useState(false)
    const [purgeResult,   setPurgeResult]  = useState(null)
    const mode = useMode()

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.health()
            setHealth(data || null)
            setSystem(data?.system || null)
        } catch(e) {
            showToast('Failed to load settings: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    async function switchMode(newMode) {
        setModeMsg('')
        const code = await requireTotp(
            'Switch to ' + newMode.toUpperCase() + ' mode',
            newMode === 'live'
                ? '⚠️ This enables REAL trading with real money. Enter TOTP to confirm.'
                : 'Switch back to paper trading. Enter TOTP to confirm.'
        )
        if (!code) return
        setModeLoading(newMode)
        try {
            const result = await API.modeToggle(newMode, code)
            if (result.success) {
                setModeOk(true)
                setModeMsg(result.message || 'Mode switched to ' + newMode)
                showToast(result.message || 'Mode switched', 'success')
                await load()
            } else {
                setModeOk(false)
                setModeMsg(result.reason || 'Mode switch failed')
                showToast(result.reason || 'Mode switch failed', 'error')
            }
        } catch(e) {
            setModeOk(false)
            setModeMsg(e.message)
            showToast(e.message, 'error')
        } finally {
            setModeLoading(null)
            setTimeout(() => setModeMsg(''), 5000)
        }
    }

    async function triggerScan() {
        setActionLoading('scan')
        setActionMsg('')
        try {
            await API.scan()
            setActionOk(true)
            setActionMsg('Scan triggered — results in 1-2 minutes')
            showToast('Scan triggered', 'success')
        } catch(e) {
            setActionOk(false)
            setActionMsg('Scan failed: ' + e.message)
            showToast('Scan failed', 'error')
        } finally {
            setActionLoading(null)
            setTimeout(() => setActionMsg(''), 5000)
        }
    }

    async function syncOutcomes() {
        setActionLoading('sync')
        setActionMsg('')
        try {
            const result = await API.syncOutcomes()
            setActionOk(true)
            setActionMsg(`Sync complete — ${result.synced || 0} synced · ${result.unmatched || 0} unmatched`)
            showToast('Sync complete', 'success')
        } catch(e) {
            setActionOk(false)
            setActionMsg('Sync failed: ' + e.message)
            showToast('Sync failed', 'error')
        } finally {
            setActionLoading(null)
            setTimeout(() => setActionMsg(''), 5000)
        }
    }

    async function dockerPurge() {
        setPurgeResult(null)
        const code = await requireTotp(
            'Docker System Purge',
            '⚠️ This will remove all unused Docker images, containers and volumes. Enter TOTP to confirm.'
        )
        if (!code) return
        setPurgeLoading(true)
        try {
            const result = await API.dockerPurge(code)
            setPurgeResult(result)
            if (result.success) {
                showToast(result.message || 'Docker purge complete', 'success')
                await load()
            } else {
                showToast('Purge failed: ' + (result.reason || 'Unknown error'), 'error')
            }
        } catch(e) {
            setPurgeResult({ success: false, reason: e.message })
            showToast('Purge failed: ' + e.message, 'error')
        } finally {
            setPurgeLoading(false)
        }
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Settings</div>
                    <div class="page-subtitle">System configuration and server health</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${load} disabled=${loading}>
                    ${loading ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="23 4 23 10 17 10"/>
                            <polyline points="1 20 1 14 7 14"/>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                    `}
                    Refresh
                </button>
            </div>

            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="section-title mb-12">Trading Mode</div>
                    <div class="flex items-center gap-12" style="margin-bottom:16px;">
                        <div style="font-size:28px;font-weight:900;letter-spacing:-1px;color:${mode === 'live' ? 'var(--red)' : 'var(--blue)'};">
                            ${mode === 'live' ? '🔴 LIVE' : '🔵 PAPER'}
                        </div>
                    </div>
                    <div class=${'alert mb-12 ' + (mode === 'live' ? 'alert-error' : 'alert-info')} style="font-size:12px;">
                        ${mode === 'live'
                            ? '🔴 LIVE MODE — Real money at risk. All trades execute on Binance.'
                            : '🔵 PAPER MODE — Simulated trading. No real money at risk.'
                        }
                    </div>
                    ${modeMsg && html`
                        <div class=${'alert mb-12 ' + (modeOk ? 'alert-success' : 'alert-error')}>
                            ${modeMsg}
                        </div>
                    `}
                    <div class="flex gap-8">
                        <button class="btn btn-success" onClick=${() => switchMode('paper')}
                            disabled=${!!modeLoading || mode === 'paper'}>
                            ${modeLoading === 'paper' ? html`<${Spinner}/>` : ''}
                            Switch to Paper
                        </button>
                        <button class="btn btn-danger" onClick=${() => switchMode('live')}
                            disabled=${!!modeLoading || mode === 'live'}>
                            ${modeLoading === 'live' ? html`<${Spinner}/>` : ''}
                            Switch to Live
                        </button>
                    </div>
                    <div class="divider"></div>
                    <div class="section-title mb-12">Quick Actions</div>
                    <div class="flex gap-8" style="flex-wrap:wrap;">
                        <button class="btn btn-ghost" onClick=${triggerScan}
                            disabled=${actionLoading === 'scan'}>
                            ${actionLoading === 'scan' ? html`<${Spinner}/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="11" cy="11" r="8"/>
                                    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                                </svg>
                            `}
                            Trigger Scan
                        </button>
                        <button class="btn btn-ghost" onClick=${syncOutcomes}
                            disabled=${actionLoading === 'sync'}>
                            ${actionLoading === 'sync' ? html`<${Spinner}/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="23 4 23 10 17 10"/>
                                    <polyline points="1 20 1 14 7 14"/>
                                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                                </svg>
                            `}
                            Sync Outcomes
                        </button>
                    </div>
                    ${actionMsg && html`
                        <div class=${'alert mt-12 ' + (actionOk ? 'alert-success' : 'alert-error')} style="font-size:12px;">
                            ${actionMsg}
                        </div>
                    `}
                </div>

                <div class="card">
                    <div class="section-title mb-12">System Status</div>
                    ${loading
                        ? html`<${LoadingSkeleton} rows=${5}/>`
                        : html`
                            <div>
                                ${[
                                    { label: 'API Status',      val: html`<span class="badge badge-online">✓ Online</span>` },
                                    { label: 'Redis',           val: html`<span class=${'badge ' + (health?.redis_connected ? 'badge-online' : 'badge-offline')}>${health?.redis_connected ? '✓ Connected' : '✗ Disconnected'}</span>` },
                                    { label: 'Trading Mode',    val: html`<span class=${'badge ' + (health?.trading_mode === 'live' ? 'badge-live' : 'badge-paper')}>${(health?.trading_mode || '--').toUpperCase()}</span>` },
                                    { label: 'Coins Active',    val: health?.coins_count || '--' },
                                    { label: 'Min Grades',      val: (health?.grades || []).join(', ') || '--' },
                                    { label: 'ML Status',       val: html`<span class=${'badge ' + (health?.ml_status?.ml_enabled ? 'badge-online' : 'badge-pending')}>${health?.ml_status?.ml_enabled ? 'Active' : 'Collecting'}</span>` },
                                    { label: 'ML Progress',     val: (health?.ml_status?.closed_trades || 0) + ' / ' + (health?.ml_status?.required || 100) },
                                    { label: 'Pending Signals', val: health?.sync_status?.pending_signals || 0 },
                                    { label: 'Win Rate',        val: (health?.sync_status?.win_rate || 0) + '%', color: Utils.winRateColor(health?.sync_status?.win_rate || 0) },
                                    { label: 'Last Check',      val: Utils.fmtTime(health?.timestamp), small: true },
                                ].map(row => html`
                                    <div key=${row.label} class="stat-row">
                                        <span class="stat-label">${row.label}</span>
                                        ${typeof row.val === 'object' && row.val !== null && !Array.isArray(row.val)
                                            ? row.val
                                            : html`<span class="stat-value" style="font-family:var(--font-mono);${row.color ? 'color:' + row.color + ';' : ''}${row.small ? 'font-size:11px;' : ''}">${row.val}</span>`
                                        }
                                    </div>
                                `)}
                            </div>
                        `
                    }
                </div>
            </div>

            <div class="card mb-12">
                <div class="section-title mb-12">Server Performance</div>
                ${loading
                    ? html`<${LoadingSkeleton} rows=${2}/>`
                    : system
                    ? html`
                        <div>
                            <div class="grid-3 mb-12" style="gap:12px;">
                                ${[
                                    { label: 'RAM Usage',  pct: system.ram_pct,  color: Utils.ramColor(system.ram_pct),   detail: system.ram_used_mb + 'MB / ' + system.ram_total_mb + 'MB · Free: ' + system.ram_available + 'MB' },
                                    { label: 'CPU Usage',  pct: system.cpu_pct,  color: Utils.cpuColor(system.cpu_pct),   detail: 't2.small · 1 vCPU · burstable' },
                                    { label: 'Disk Usage', pct: system.disk_pct, color: Utils.diskColor(system.disk_pct), detail: system.disk_used_gb + 'GB / ' + system.disk_total_gb + 'GB' },
                                ].map(item => html`
                                    <div key=${item.label} class="level-item">
                                        <div class="server-stat">
                                            <div class="server-stat-header">
                                                <span class="server-stat-label">${item.label}</span>
                                                <span class="server-stat-value" style="color:${item.color};">${item.pct}%</span>
                                            </div>
                                            <div class="progress-bar-thick" style="margin:6px 0;">
                                                <div class="progress-fill" style="width:${item.pct}%;background:${item.color};"></div>
                                            </div>
                                            <div style="font-size:11px;color:var(--text-muted);">${item.detail}</div>
                                        </div>
                                    </div>
                                `)}
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">Uptime</span>
                                <span style="font-family:var(--font-mono);font-weight:700;color:var(--green);">
                                    ${Utils.fmtUptime(system.uptime_secs)}
                                </span>
                            </div>
                            ${system.containers?.length
                                ? html`
                                    <div class="mt-12">
                                        <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">
                                            Containers
                                        </div>
                                        ${system.containers.map(c => html`
                                            <div key=${c.name} class="container-row">
                                                <div class="flex items-center gap-8">
                                                    <div class=${'ws-dot ' + (c.status === 'running' ? '' : 'disconnected')}></div>
                                                    <span class="container-name">${c.name}</span>
                                                </div>
                                                <div class="container-stats">
                                                    <span>RAM: <span style="font-family:var(--font-mono);color:${Utils.ramColor(c.mem_pct)};">${c.mem_mb}MB (${c.mem_pct}%)</span></span>
                                                    <span>CPU: <span style="font-family:var(--font-mono);color:${Utils.cpuColor(c.cpu_pct)};">${c.cpu_pct}%</span></span>
                                                    <span class=${'badge ' + (c.status === 'running' ? 'badge-online' : 'badge-offline')}>${c.status}</span>
                                                </div>
                                            </div>
                                        `)}
                                    </div>
                                `
                                : html`
                                    <div class="alert alert-warning mt-12" style="font-size:12px;">
                                        Container stats unavailable — Docker socket may not be mounted
                                    </div>
                                `
                            }
                        </div>
                    `
                    : html`<${EmptyState} message="Server stats unavailable"/>`
                }
            </div>

            <div class="card mb-12">
                <div class="section-title mb-12" style="color:var(--red);">Docker Maintenance</div>
                <div class="docker-purge-card">
                    <div class="flex justify-between items-center mb-12">
                        <div>
                            <div style="font-size:13px;font-weight:700;color:var(--red);">
                                Purge Unused Docker Images
                            </div>
                            <div style="font-size:12px;color:var(--text-secondary);margin-top:3px;">
                                Runs <span style="font-family:var(--font-mono);color:var(--text-primary);">docker system prune -f --volumes</span> on the host.
                                Requires TOTP confirmation.
                            </div>
                        </div>
                        <button class="btn btn-danger" onClick=${dockerPurge} disabled=${purgeLoading}>
                            ${purgeLoading ? html`<${Spinner}/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3 6 5 6 21 6"/>
                                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                                </svg>
                            `}
                            Purge Docker
                        </button>
                    </div>
                    <div class="grid-3" style="gap:8px;margin-bottom:12px;">
                        <div class="level-item">
                            <div class="level-label">Disk Used</div>
                            <div style="font-family:var(--font-mono);font-size:14px;font-weight:700;color:${Utils.diskColor(system?.disk_pct || 0)};">
                                ${system ? system.disk_used_gb + 'GB' : '--'}
                            </div>
                        </div>
                        <div class="level-item">
                            <div class="level-label">Disk Free</div>
                            <div style="font-family:var(--font-mono);font-size:14px;font-weight:700;color:var(--green);">
                                ${system ? (system.disk_total_gb - system.disk_used_gb).toFixed(1) + 'GB' : '--'}
                            </div>
                        </div>
                        <div class="level-item">
                            <div class="level-label">Disk Usage</div>
                            <div style="font-family:var(--font-mono);font-size:14px;font-weight:700;color:${Utils.diskColor(system?.disk_pct || 0)};">
                                ${system ? system.disk_pct + '%' : '--'}
                            </div>
                        </div>
                    </div>
                    ${purgeResult && html`
                        <div>
                            <div class=${'alert ' + (purgeResult.success ? 'alert-success' : 'alert-error')}>
                                ${purgeResult.message || purgeResult.reason}
                                ${purgeResult.freed_mb > 0 && html`
                                    <span style="font-family:var(--font-mono);font-weight:700;margin-left:8px;">
                                        Freed: ${purgeResult.freed_mb}MB
                                    </span>
                                `}
                            </div>
                            ${purgeResult.output && html`
                                <div class="docker-purge-output">${purgeResult.output}</div>
                            `}
                        </div>
                    `}
                </div>
            </div>

            <div class="card">
                <div class="section-title mb-12">ML Configuration</div>
                ${!loading && health && html`
                    <div class="grid-2" style="gap:12px;">
                        <div>
                            ${[
                                { label: 'ML Enabled',    val: html`<span class=${'badge ' + (health?.ml_status?.ml_enabled ? 'badge-online' : 'badge-pending')}>${health?.ml_status?.ml_enabled ? 'Yes' : 'No'}</span>` },
                                { label: 'Closed Trades', val: health?.ml_status?.closed_trades || 0 },
                                { label: 'Required',      val: health?.ml_status?.required || 100 },
                            ].map(row => html`
                                <div key=${row.label} class="stat-row">
                                    <span class="stat-label">${row.label}</span>
                                    ${typeof row.val === 'object' && row.val !== null
                                        ? row.val
                                        : html`<span class="stat-value" style="font-family:var(--font-mono);">${row.val}</span>`
                                    }
                                </div>
                            `)}
                            <div class="stat-row">
                                <span class="stat-label">Progress</span>
                                <div style="flex:1;margin-left:12px;">
                                    <div class="progress-bar-thick">
                                        <div class="progress-fill" style="width:${Math.min(100, ((health?.ml_status?.closed_trades || 0) / (health?.ml_status?.required || 100)) * 100)}%;background:${health?.ml_status?.ml_enabled ? 'var(--green)' : 'var(--blue)'};"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div>
                            ${[
                                { label: 'CV AUC',       val: health?.ml_status?.cv_auc || '--', color: 'var(--green)' },
                                { label: 'Win Rate',     val: (health?.ml_status?.win_rate || 0) + '%', color: Utils.winRateColor(health?.ml_status?.win_rate || 0) },
                                { label: 'Last Trained', val: health?.ml_status?.trained_at && health.ml_status.trained_at !== '--' ? Utils.fmtTimeAgo(health.ml_status.trained_at) : '--', small: true },
                                { label: 'Message',      val: Utils.truncate(health?.ml_status?.message || '--', 50), small: true },
                            ].map(row => html`
                                <div key=${row.label} class="stat-row">
                                    <span class="stat-label">${row.label}</span>
                                    <span class="stat-value" style="font-family:var(--font-mono);${row.color ? 'color:' + row.color + ';' : ''}${row.small ? 'font-size:11px;' : ''}">
                                        ${row.val}
                                    </span>
                                </div>
                            `)}
                        </div>
                    </div>
                `}
            </div>
        </div>
    `
}