var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { showToast, requireTotp } = Store
var { GradeBadge, Spinner, EmptyState, LoadingSkeleton, InfoRow } = SE

function SystemPage() {
    const [activeTab, setActiveTab] = useState('health')

    const tabs = [
        { id: 'health',   label: 'Health'   },
        { id: 'backtest', label: 'Backtest' },
        { id: 'analysis', label: 'Analysis' },
        { id: 'audit',    label: 'Audit'    },
    ]

    return html`
        <div>
            <div class="page-header">
                <div>
                    <div class="page-title">System</div>
                    <div class="page-subtitle">Health, backtest, analysis and audit</div>
                </div>
            </div>

            <div class="tab-group mb-24" style="width:fit-content;">
                ${tabs.map(tab => html`
                    <button key=${tab.id}
                        class=${'tab-btn ' + (activeTab === tab.id ? 'active' : '')}
                        onClick=${() => setActiveTab(tab.id)}>
                        ${tab.label}
                    </button>
                `)}
            </div>

            ${activeTab === 'health'   && html`<${HealthTab}/>`}
            ${activeTab === 'backtest' && html`<${BacktestTab}/>`}
            ${activeTab === 'analysis' && html`<${AnalysisTab}/>`}
            ${activeTab === 'audit'    && html`<${AuditTab}/>`}
        </div>
    `
}

function HealthTab() {
    const [health,        setHealth]        = useState(null)
    const [loading,       setLoading]       = useState(false)
    const [modeLoading,   setModeLoading]   = useState(null)
    const [modeMsg,       setModeMsg]       = useState('')
    const [modeOk,        setModeOk]        = useState(false)
    const [actionLoading, setActionLoading] = useState(null)
    const [actionMsg,     setActionMsg]     = useState('')
    const [actionOk,      setActionOk]      = useState(false)

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.health()
            setHealth(data || null)
        } catch(e) {
            showToast('Failed to load health: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    async function switchMode(newMode) {
        setModeMsg('')
        const code = await requireTotp(
            'Switch to ' + newMode.toUpperCase() + ' mode',
            newMode === 'live'
                ? 'This enables REAL trading with real money. All trades will execute on Binance.'
                : 'Switch back to paper trading. No real money at risk.'
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
            setTimeout(() => setModeMsg(''), 6000)
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
            setActionMsg('Sync complete — ' + (result.synced || 0) + ' synced · ' + (result.unmatched || 0) + ' unmatched')
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

    const mode   = health?.trading_mode || 'paper'
    const system = health?.system       || null
    const ml     = health?.ml_status    || {}
    const sync   = health?.sync_status  || {}

    return html`
        <div>
            <div class="grid-2 mb-16">
                <div class="card card-pad">
                    <div class="section-title mb-16">Trading Mode</div>
                    <div style=${'font-size:var(--text-largetitle);font-weight:var(--weight-black);letter-spacing:var(--tracking-largetitle);color:' + (mode === 'live' ? 'var(--loss)' : 'var(--brand)') + ';margin-bottom:12px;'}>
                        ${mode === 'live' ? 'LIVE' : 'PAPER'}
                    </div>
                    <div class=${'alert mb-16 ' + (mode === 'live' ? 'alert-error' : 'alert-info')}>
                        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                        <div class="alert-content">
                            <div class="alert-desc">
                                ${mode === 'live'
                                    ? 'LIVE MODE — Real money at risk. All trades execute on Binance.'
                                    : 'PAPER MODE — Simulated trading. No real money at risk.'
                                }
                            </div>
                        </div>
                    </div>
                    ${modeMsg && html`
                        <div class=${'alert mb-16 ' + (modeOk ? 'alert-success' : 'alert-error')}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                ${modeOk
                                    ? html`<polyline points="20 6 9 17 4 12"/>`
                                    : html`<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>`
                                }
                            </svg>
                            <div class="alert-content"><div class="alert-desc">${modeMsg}</div></div>
                        </div>
                    `}
                    <div class="flex gap-8">
                        <button class="btn btn-success btn-full"
                            onClick=${() => switchMode('paper')}
                            disabled=${!!modeLoading || mode === 'paper'}>
                            ${modeLoading === 'paper' ? html`<${Spinner} size="xs"/>` : ''}
                            Paper Mode
                        </button>
                        <button class="btn btn-danger btn-full"
                            onClick=${() => switchMode('live')}
                            disabled=${!!modeLoading || mode === 'live'}>
                            ${modeLoading === 'live' ? html`<${Spinner} size="xs"/>` : ''}
                            Live Mode
                        </button>
                    </div>

                    <div class="divider"></div>

                    <div class="section-title mb-12" style="font-size:var(--text-subhead);">Quick Actions</div>
                    <div class="flex gap-8 flex-wrap">
                        <button class="btn btn-secondary btn-sm"
                            onClick=${triggerScan}
                            disabled=${actionLoading === 'scan'}>
                            ${actionLoading === 'scan' ? html`<${Spinner} size="xs"/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                            `}
                            Trigger Scan
                        </button>
                        <button class="btn btn-secondary btn-sm"
                            onClick=${syncOutcomes}
                            disabled=${actionLoading === 'sync'}>
                            ${actionLoading === 'sync' ? html`<${Spinner} size="xs"/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                            `}
                            Sync Outcomes
                        </button>
                        <button class="btn btn-secondary btn-sm" onClick=${load} disabled=${loading}>
                            ${loading ? html`<${Spinner} size="xs"/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                            `}
                            Refresh
                        </button>
                    </div>
                    ${actionMsg && html`
                        <div class=${'alert mt-12 ' + (actionOk ? 'alert-success' : 'alert-error')}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                ${actionOk
                                    ? html`<polyline points="20 6 9 17 4 12"/>`
                                    : html`<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>`
                                }
                            </svg>
                            <div class="alert-content"><div class="alert-desc">${actionMsg}</div></div>
                        </div>
                    `}
                </div>

                <div class="card card-pad">
                    <div class="section-title mb-16">System Status</div>
                    ${loading
                        ? html`<${LoadingSkeleton} rows=${6}/>`
                        : html`
                            ${[
                                { label: 'API Status',      val: html`<span class="badge badge-online">Online</span>` },
                                { label: 'Redis',           val: html`<span class=${'badge ' + (health?.redis_connected ? 'badge-online' : 'badge-offline')}>${health?.redis_connected ? 'Connected' : 'Disconnected'}</span>` },
                                { label: 'Trading Mode',    val: html`<span class=${'badge ' + (mode === 'live' ? 'badge-live' : 'badge-paper')}>${mode.toUpperCase()}</span>` },
                                { label: 'Coins Active',    val: health?.coins_count || '--' },
                                { label: 'Min Grades',      val: (health?.grades || []).join(', ') || '--' },
                                { label: 'ML Status',       val: html`<span class=${'badge ' + (ml?.ml_enabled ? 'badge-online' : 'badge-pending')}>${ml?.ml_enabled ? 'Active' : 'Collecting'}</span>` },
                                { label: 'ML Progress',     val: (ml?.closed_trades || 0) + ' / ' + (ml?.required || 100) },
                                { label: 'Pending Signals', val: sync?.pending_signals || 0 },
                                { label: 'Win Rate',        val: (sync?.win_rate || 0) + '%', color: Utils.winRateColor(sync?.win_rate || 0) },
                                { label: 'Last Check',      val: Utils.fmtTimeAgo(health?.timestamp) },
                            ].map(row => html`
                                <div key=${row.label} class="info-row">
                                    <span class="info-row-label">${row.label}</span>
                                    ${typeof row.val === 'object' && row.val !== null
                                        ? row.val
                                        : html`<span class="info-row-value text-mono" style=${row.color ? 'color:' + row.color : ''}>${row.val}</span>`
                                    }
                                </div>
                            `)}
                        `
                    }
                </div>
            </div>

            ${system && html`
                <div class="card card-pad mb-16">
                    <div class="section-title mb-16">Server Performance</div>
                    <div class="grid-3 mb-16" style="gap:10px;">
                        ${[
                            { label: 'RAM',  pct: system.ram_pct,  val: system.ram_used_mb + 'MB / ' + system.ram_total_mb + 'MB',   cls: Utils.ramColor(system.ram_pct)  },
                            { label: 'CPU',  pct: system.cpu_pct,  val: system.cpu_pct + '%',                                         cls: Utils.cpuColor(system.cpu_pct)  },
                            { label: 'Disk', pct: system.disk_pct, val: system.disk_used_gb + 'GB / ' + system.disk_total_gb + 'GB', cls: Utils.diskColor(system.disk_pct) },
                        ].map(item => html`
                            <div key=${item.label} class="card card-pad-sm">
                                <div class="server-stat">
                                    <div class="server-stat-header">
                                        <span class="server-stat-label">${item.label}</span>
                                        <span class=${'server-stat-value ' + item.cls}>${item.pct}%</span>
                                    </div>
                                    <div class="server-stat-track">
                                        <div class=${'server-stat-fill ' + item.cls}
                                            style=${'width:' + Math.min(100, item.pct) + '%'}></div>
                                    </div>
                                    <div class="server-stat-detail">${item.val}</div>
                                </div>
                            </div>
                        `)}
                    </div>
                    <${InfoRow} label="Uptime" value=${Utils.fmtUptime(system.uptime_secs)} mono=${true} color="var(--profit)"/>
                    ${system.containers?.length > 0 && html`
                        <div class="mt-16">
                            <div class="label-uppercase mb-10">Containers</div>
                            ${system.containers.map(c => html`
                                <div key=${c.name} style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;background:var(--fill-4);border-radius:var(--r-lg);margin-bottom:6px;flex-wrap:wrap;gap:8px;">
                                    <div class="flex items-center gap-8">
                                        <div class=${'topbar-ws-dot ' + (c.status === 'running' ? 'connected' : 'disconnected')}></div>
                                        <span style="font-family:var(--font-mono);font-weight:var(--weight-bold);font-size:var(--text-footnote);">${c.name}</span>
                                    </div>
                                    <div class="flex gap-16" style="font-size:var(--text-caption1);color:var(--label-3);">
                                        <span>RAM: <span style=${'font-family:var(--font-mono);color:' + (c.mem_pct > 80 ? 'var(--loss)' : c.mem_pct > 60 ? 'var(--warning)' : 'var(--profit)') + ';'}>${c.mem_mb}MB (${c.mem_pct}%)</span></span>
                                        <span>CPU: <span style=${'font-family:var(--font-mono);color:' + (c.cpu_pct > 80 ? 'var(--loss)' : c.cpu_pct > 60 ? 'var(--warning)' : 'var(--profit)') + ';'}>${c.cpu_pct}%</span></span>
                                        <span class=${'badge ' + (c.status === 'running' ? 'badge-online' : 'badge-offline')} style="font-size:9px;">${c.status}</span>
                                    </div>
                                </div>
                            `)}
                        </div>
                    `}
                </div>
            `}

            <div class="card card-pad">
                <div class="section-title mb-4">ML Model</div>
                ${loading
                    ? html`<${LoadingSkeleton} rows=${3}/>`
                    : html`
                        <div class="grid-2" style="gap:12px;">
                            <div>
                                <div class="ml-progress mb-16">
                                    <div class="ml-progress-header">
                                        <span class="ml-progress-label">Training Progress</span>
                                        <span class="ml-progress-value">
                                            ${Math.min(100, Math.round(((ml?.closed_trades || 0) / (ml?.required || 100)) * 100))}%
                                        </span>
                                    </div>
                                    <div class="ml-progress-track">
                                        <div class=${'ml-progress-fill ' + ((ml?.closed_trades || 0) >= (ml?.required || 100) ? 'complete' : '')}
                                            style=${'width:' + Math.min(100, ((ml?.closed_trades || 0) / (ml?.required || 100)) * 100) + '%'}>
                                        </div>
                                    </div>
                                    <div class="ml-progress-counts">
                                        <span class="ml-progress-current">${ml?.closed_trades || 0} trades</span>
                                        <span class="ml-progress-target">Target: ${ml?.required || 100}</span>
                                    </div>
                                </div>
                                ${[
                                    { label: 'Status',       val: html`<span class=${'badge ' + (ml?.ml_enabled ? 'badge-online' : 'badge-pending')}>${ml?.ml_enabled ? 'Active' : 'Collecting'}</span>` },
                                    { label: 'CV AUC',       val: ml?.cv_auc || '--', color: ml?.cv_auc ? 'var(--profit)' : null },
                                    { label: 'Win Rate',     val: (ml?.win_rate || 0) + '%', color: Utils.winRateColor(ml?.win_rate || 0) },
                                    { label: 'Last Trained', val: ml?.trained_at && ml.trained_at !== '--' ? Utils.fmtTimeAgo(ml.trained_at) : '--' },
                                ].map(row => html`
                                    <div key=${row.label} class="info-row">
                                        <span class="info-row-label">${row.label}</span>
                                        ${typeof row.val === 'object' && row.val !== null
                                            ? row.val
                                            : html`<span class="info-row-value text-mono" style=${row.color ? 'color:' + row.color : ''}>${row.val}</span>`
                                        }
                                    </div>
                                `)}
                            </div>
                            <div>
                                ${ml?.message && html`
                                    <div class="alert alert-info mb-12">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                                        <div class="alert-content"><div class="alert-desc">${ml.message}</div></div>
                                    </div>
                                `}
                                ${ml?.top_features?.length > 0 && html`
                                    <div class="label-uppercase mb-10">Top Features</div>
                                    ${ml.top_features.slice(0, 5).map(f => html`
                                        <div key=${f.feature} style="margin-bottom:10px;">
                                            <div class="flex justify-between mb-4" style="font-size:var(--text-caption1);">
                                                <span style="color:var(--label-2);">${f.feature.replace(/_/g, ' ')}</span>
                                                <span style="font-family:var(--font-mono);color:var(--brand);font-weight:var(--weight-bold);">${f.importance}</span>
                                            </div>
                                            <div class="progress progress-sm">
                                                <div class="progress-fill progress-fill-brand"
                                                    style=${'width:' + Math.min(100, (f.importance / (ml.top_features[0]?.importance || 1)) * 100) + '%'}>
                                                </div>
                                            </div>
                                        </div>
                                    `)}
                                `}
                            </div>
                        </div>
                    `
                }
            </div>
        </div>
    `
}

function BacktestTab() {
    const [coins,        setCoins]        = useState([])
    const [selectedCoin, setSelectedCoin] = useState('')
    const [result,       setResult]       = useState(null)
    const [history,      setHistory]      = useState([])
    const [running,      setRunning]      = useState(false)
    const [histLoading,  setHistLoading]  = useState(false)
    const [error,        setError]        = useState('')

    useEffect(() => {
        loadCoins()
        loadHistory()
        return () => {
            Charts.destroy('bt-equity-chart')
            Charts.destroy('bt-grade-donut')
        }
    }, [])

    useEffect(() => {
        if (!result) return
        setTimeout(() => {
            if (result.trades?.length) {
                const el = document.getElementById('bt-equity-chart')
                if (el && el.tagName === 'CANVAS') {
                    Charts.equity('bt-equity-chart', result.trades.map((t, i) => ({
                        date:   t.date,
                        equity: result.trades.slice(0, i + 1).reduce((s, x) => s + (x.pnl || 0), 1000)
                    })))
                }
            }
            if (result.by_grade) {
                const el = document.getElementById('bt-grade-donut')
                if (el && el.tagName === 'CANVAS') {
                    Charts.gradeDonut('bt-grade-donut', {
                        'A+': { total: result.by_grade['A+']?.trades || 0 },
                        'A':  { total: result.by_grade['A']?.trades  || 0 },
                        'B':  { total: result.by_grade['B']?.trades  || 0 },
                    })
                }
            }
        }, 100)
    }, [result])

    async function loadCoins() {
        try {
            const data    = await API.coins()
            const enabled = (data || []).filter(c => c.enabled).map(c => c.coin)
            setCoins(enabled)
            if (enabled.length && !selectedCoin) setSelectedCoin(enabled[0])
        } catch(e) {}
    }

    async function loadHistory() {
        setHistLoading(true)
        try {
            const data = await API.backtestHistory()
            setHistory(data || [])
        } catch(e) {}
        setHistLoading(false)
    }

    async function runBacktest() {
        if (!selectedCoin) return
        setRunning(true)
        setError('')
        setResult(null)
        Charts.destroy('bt-equity-chart')
        Charts.destroy('bt-grade-donut')
        try {
            const data = await API.backtest(selectedCoin)
            setResult(data)
            showToast('Backtest complete — ' + data.total_trades + ' trades', 'success')
        } catch(e) {
            setError(e.message || 'Backtest failed')
            showToast('Backtest failed: ' + e.message, 'error')
        } finally {
            setRunning(false)
        }
    }

    return html`
        <div>
            <div class="card card-pad mb-16">
                <div class="section-title mb-12">Run Backtest</div>
                <div class="flex gap-8 flex-wrap items-center">
                    <select class="select select-sm" style="width:160px;" value=${selectedCoin}
                        onChange=${e => setSelectedCoin(e.target.value)}>
                        <option value="">Select Coin</option>
                        ${coins.map(c => html`<option key=${c} value=${c}>${c}USDT</option>`)}
                    </select>
                    <button class="btn btn-primary"
                        onClick=${runBacktest}
                        disabled=${running || !selectedCoin}>
                        ${running ? html`<${Spinner} size="xs" color="white"/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        `}
                        ${running ? 'Running...' : 'Run Backtest'}
                    </button>
                </div>
                ${running && html`
                    <div class="alert alert-info mt-12">
                        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                        <div class="alert-content">
                            <div class="alert-desc">Running backtest for <strong>${selectedCoin}USDT</strong> — up to 2 minutes...</div>
                        </div>
                    </div>
                `}
                ${error && html`
                    <div class="alert alert-error mt-12">
                        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                        <div class="alert-content"><div class="alert-desc">${error}</div></div>
                    </div>
                `}
            </div>

            ${result && html`
                <div>
                    <div class="grid-4 mb-16">
                        ${[
                            { label: 'Win Rate',     val: result.win_rate + '%',                                  color: Utils.winRateColor(result.win_rate) },
                            { label: 'Total PnL',    val: Utils.fmtPnl(result.total_pnl, result.total_pnl >= 0), color: Utils.pnlColor(result.total_pnl >= 0) },
                            { label: 'Max Drawdown', val: result.max_drawdown + '%',                              color: 'var(--loss)' },
                            { label: 'Trades',       val: result.total_trades,                                    color: 'var(--brand)' },
                        ].map(item => html`
                            <div key=${item.label} class="stat-card">
                                <div class="stat-card-label">${item.label}</div>
                                <div class="stat-card-value" style=${'color:' + item.color + ';'}>${item.val}</div>
                                <div class="stat-card-sub">${result.period_start} → ${result.period_end}</div>
                            </div>
                        `)}
                    </div>

                    <div class="grid-2 mb-16">
                        <div class="card card-pad">
                            <div class="section-title mb-12">Equity Curve</div>
                            <div class="chart-wrap chart-h-200">
                                <canvas id="bt-equity-chart"></canvas>
                            </div>
                        </div>
                        <div class="card card-pad">
                            <div class="section-title mb-12">By Grade</div>
                            <div style="position:relative;height:140px;margin-bottom:12px;">
                                <canvas id="bt-grade-donut"></canvas>
                            </div>
                            ${Object.entries(result.by_grade || {}).map(([grade, data]) => html`
                                <div key=${grade} style="margin-bottom:10px;">
                                    <div class="flex justify-between items-center mb-5">
                                        <div class="flex items-center gap-8">
                                            <${GradeBadge} grade=${grade}/>
                                            <span style="font-size:var(--text-caption1);color:var(--label-3);">${data.trades || 0} trades</span>
                                        </div>
                                        <div class="flex items-center gap-10">
                                            <span style=${'font-family:var(--font-mono);font-size:var(--text-footnote);font-weight:var(--weight-bold);color:' + Utils.winRateColor(data.win_rate) + ';'}>
                                                ${data.win_rate || 0}%
                                            </span>
                                            <span style=${'font-family:var(--font-mono);font-size:var(--text-caption1);color:' + Utils.pnlColor((data.pnl || 0) >= 0) + ';'}>
                                                ${Utils.fmtPnl(data.pnl, (data.pnl || 0) >= 0)}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="progress progress-sm">
                                        <div class="progress-fill"
                                            style=${'width:' + (data.win_rate || 0) + '%;background:' + Utils.gradeColor(grade) + ';'}>
                                        </div>
                                    </div>
                                </div>
                            `)}
                            <div class="divider"></div>
                            ${[
                                { label: 'Profit Factor', val: result.profit_factor || '--' },
                                { label: 'Expectancy',    val: Utils.fmtPnl(result.expectancy, (result.expectancy || 0) >= 0), color: Utils.pnlColor((result.expectancy || 0) >= 0) },
                                { label: 'Best Trade',    val: Utils.fmtPnl(result.best_trade,  true),  color: 'var(--profit)' },
                                { label: 'Worst Trade',   val: Utils.fmtPnl(result.worst_trade, false), color: 'var(--loss)'   },
                                { label: 'TP1 Hit Rate',  val: result.phase_breakdown?.tp1_hit_rate != null ? result.phase_breakdown.tp1_hit_rate + '%' : '--' },
                            ].map(row => html`
                                <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                                    mono=${true} color=${row.color}/>
                            `)}
                        </div>
                    </div>
                </div>
            `}

            ${!result && history.length > 0 && html`
                <div class="card">
                    <div class="filter-bar">
                        <div class="section-title" style="font-size:var(--text-subhead);">Backtest History</div>
                        <div class="filter-spacer"></div>
                        <button class="btn btn-ghost btn-sm" onClick=${loadHistory} disabled=${histLoading}>
                            ${histLoading ? html`<${Spinner} size="xs"/>` : 'Refresh'}
                        </button>
                    </div>
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Coin</th><th>Run At</th><th>Period</th>
                                    <th>Trades</th><th>Win Rate</th><th>PnL</th>
                                    <th>Max DD</th><th>Notes</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${history.map(h => html`
                                    <tr key=${h.id}>
                                        <td>
                                            <span style="font-family:var(--font-mono);font-weight:var(--weight-bold);">${h.coin}</span>
                                        </td>
                                        <td style="color:var(--label-3);font-size:var(--text-caption1);">${Utils.fmtTimeAgo(h.run_at)}</td>
                                        <td style="color:var(--label-3);font-size:var(--text-caption1);">${h.period_start} → ${h.period_end}</td>
                                        <td><span style="font-family:var(--font-mono);">${h.total_trades}</span></td>
                                        <td>
                                            <span style=${'font-family:var(--font-mono);color:' + Utils.winRateColor(h.win_rate) + ';'}>
                                                ${h.win_rate}%
                                            </span>
                                        </td>
                                        <td>
                                            <span style=${'font-family:var(--font-mono);color:' + Utils.pnlColor((h.total_pnl || 0) >= 0) + ';'}>
                                                ${Utils.fmtPnl(h.total_pnl, (h.total_pnl || 0) >= 0)}
                                            </span>
                                        </td>
                                        <td><span style="font-family:var(--font-mono);color:var(--loss);">${h.max_drawdown}%</span></td>
                                        <td style="color:var(--label-4);font-size:var(--text-caption1);">${Utils.truncate(h.notes, 50)}</td>
                                    </tr>
                                `)}
                            </tbody>
                        </table>
                    </div>
                </div>
            `}
        </div>
    `
}

function AnalysisTab() {
    const [factors, setFactors] = useState(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        load()
        return () => Charts.destroy('factor-bar-chart')
    }, [])

    useEffect(() => {
        if (!factors?.table?.length) return
        setTimeout(() => {
            const el = document.getElementById('factor-bar-chart')
            if (el && el.tagName === 'CANVAS') {
                Charts.factorBar('factor-bar-chart', factors.table)
            }
        }, 100)
    }, [factors])

    async function load() {
        setLoading(true)
        try {
            const [f, health] = await Promise.all([API.factorAnalysis(), API.health()])
            setFactors(f || null)
        } catch(e) {
            showToast('Failed to load analysis: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    return html`
        <div>
            <div class="flex justify-between items-center mb-16">
                <div class="section-title">Factor Edge Analysis</div>
                <button class="btn btn-secondary btn-sm" onClick=${load} disabled=${loading}>
                    ${loading ? html`<${Spinner} size="xs"/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    `}
                    Refresh
                </button>
            </div>

            ${loading
                ? html`<${LoadingSkeleton} rows=${4}/>`
                : factors?.table?.length
                ? html`
                    <div class="card card-pad mb-16">
                        <div style="font-size:var(--text-subhead);color:var(--label-3);margin-bottom:14px;line-height:var(--leading-relaxed);">
                            Edge = win rate when factor present minus win rate when absent.
                            Higher edge = more predictive of winning trades.
                        </div>
                        <div class=${'alert mb-16 ' + (factors.reliable ? 'alert-success' : 'alert-warning')}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                            <div class="alert-content">
                                <div class="alert-desc">${factors.reliability}</div>
                            </div>
                        </div>
                        <div class="chart-wrap" style="height:300px;margin-bottom:20px;">
                            <canvas id="factor-bar-chart"></canvas>
                        </div>
                        <div class="table-wrap" style="max-height:400px;overflow-y:auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Factor</th><th>Present WR</th><th>Absent WR</th>
                                        <th>Edge</th><th>Samples</th><th>Observation</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${factors.table.map(f => html`
                                        <tr key=${f.factor}>
                                            <td>
                                                <span style="font-family:var(--font-mono);font-size:var(--text-caption1);font-weight:var(--weight-bold);">
                                                    ${f.factor.replace(/_/g, ' ')}
                                                </span>
                                            </td>
                                            <td>
                                                <span style=${'font-family:var(--font-mono);color:' + (f.win_rate_present != null ? Utils.winRateColor(f.win_rate_present) : 'var(--label-4)') + ';'}>
                                                    ${f.win_rate_present != null ? f.win_rate_present + '%' : '--'}
                                                </span>
                                            </td>
                                            <td>
                                                <span style="font-family:var(--font-mono);color:var(--label-3);">
                                                    ${f.win_rate_absent != null ? f.win_rate_absent + '%' : '--'}
                                                </span>
                                            </td>
                                            <td>
                                                <span style=${'font-family:var(--font-mono);font-weight:var(--weight-bold);color:' + Utils.edgeColor(f.edge) + ';'}>
                                                    ${f.edge != null ? (f.edge >= 0 ? '+' : '') + f.edge + '%' : '--'}
                                                </span>
                                            </td>
                                            <td>
                                                <span style="font-family:var(--font-mono);font-size:var(--text-caption1);color:var(--label-3);">
                                                    ${f.present_total || 0}
                                                </span>
                                            </td>
                                            <td>
                                                <span style=${'font-size:var(--text-caption1);color:' + Utils.edgeColor(f.edge) + ';'}>
                                                    ${f.observation || '--'}
                                                </span>
                                            </td>
                                        </tr>
                                    `)}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `
                : factors?.error
                ? html`
                    <div class="alert alert-warning">
                        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                        <div class="alert-content"><div class="alert-desc">${factors.error}</div></div>
                    </div>
                `
                : html`
                    <div class="card">
                        <${EmptyState}
                            title="No Factor Data Yet"
                            desc="Need closed trades with factor scores to run analysis. Keep trading and check back later."
                        />
                    </div>
                `
            }
        </div>
    `
}

function AuditTab() {
    const [logs,         setLogs]         = useState([])
    const [filtered,     setFiltered]     = useState([])
    const [loading,      setLoading]      = useState(false)
    const [limit,        setLimit]        = useState('100')
    const [filterAction, setFilterAction] = useState('')
    const [filterResult, setFilterResult] = useState('')
    const [search,       setSearch]       = useState('')
    const [currentPage,  setCurrentPage]  = useState(1)
    const pageSize   = 30
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
    const paginated  = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.auditLog(parseInt(limit) || 100)
            setLogs(data || [])
            applyFilter(data || [], filterAction, filterResult, search)
        } catch(e) {
            showToast('Failed to load audit log: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    function applyFilter(l, action, result, s) {
        let res = [...(l || logs)]
        if (action) res = res.filter(x => x.action === action)
        if (result !== '') {
            const ok = result === 'true'
            res = res.filter(x => x.success === ok)
        }
        if (s) {
            const q = s.toLowerCase()
            res = res.filter(x =>
                (x.detail || '').toLowerCase().includes(q) ||
                (x.action || '').toLowerCase().includes(q) ||
                (x.source || '').toLowerCase().includes(q) ||
                (x.ip     || '').toLowerCase().includes(q)
            )
        }
        setFiltered(res)
        setCurrentPage(1)
    }

    function actionColor(action) {
        if (!action) return 'var(--label-4)'
        if (action.includes('login'))  return 'var(--brand)'
        if (action.includes('toggle')) return 'var(--warning)'
        if (action.includes('delete') || action.includes('purge')) return 'var(--loss)'
        if (action.includes('add'))    return 'var(--profit)'
        if (action.includes('reset'))  return 'var(--warning)'
        if (action.includes('mode'))   return 'var(--purple)'
        return 'var(--label-3)'
    }

    return html`
        <div>
            <div class="card">
                <div class="filter-bar">
                    <select class="select select-sm" style="width:150px;" value=${filterAction}
                        onChange=${e => { setFilterAction(e.target.value); applyFilter(logs, e.target.value, filterResult, search) }}>
                        <option value="">All Actions</option>
                        <option value="dashboard_login">Login</option>
                        <option value="mode_toggle">Mode Toggle</option>
                        <option value="coin_add">Coin Add</option>
                        <option value="coin_toggle">Coin Toggle</option>
                        <option value="coin_delete">Coin Delete</option>
                        <option value="password_reset">Password Reset</option>
                        <option value="docker_purge">Docker Purge</option>
                    </select>
                    <select class="select select-sm" style="width:110px;" value=${filterResult}
                        onChange=${e => { setFilterResult(e.target.value); applyFilter(logs, filterAction, e.target.value, search) }}>
                        <option value="">All Results</option>
                        <option value="true">Success</option>
                        <option value="false">Failed</option>
                    </select>
                    <div class="search-input" style="width:150px;">
                        <svg class="search-input-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        <input class="input input-sm" type="text"
                            placeholder="Search..."
                            value=${search}
                            onInput=${e => { setSearch(e.target.value); applyFilter(logs, filterAction, filterResult, e.target.value) }}/>
                    </div>
                    <select class="select select-sm" style="width:80px;" value=${limit}
                        onChange=${e => { setLimit(e.target.value); load() }}>
                        <option value="50">50</option>
                        <option value="100">100</option>
                        <option value="200">200</option>
                        <option value="500">500</option>
                    </select>
                    <button class="btn btn-ghost btn-sm" onClick=${() => {
                        setFilterAction('')
                        setFilterResult('')
                        setSearch('')
                        applyFilter(logs, '', '', '')
                    }}>Clear</button>
                    <div class="filter-spacer"></div>
                    <span class="filter-count"><strong>${filtered.length}</strong> entries</span>
                </div>

                ${loading
                    ? html`<div style="padding:16px;"><${LoadingSkeleton} rows=${5}/></div>`
                    : html`
                        <div class="table-wrap" style="max-height:560px;overflow-y:auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>#</th><th>Time</th><th>Action</th>
                                        <th>Source</th><th>Detail</th><th>IP</th><th>Result</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!paginated.length
                                        ? html`
                                            <tr><td colspan="7">
                                                <${EmptyState} size="sm" title="No audit entries found"/>
                                            </td></tr>
                                        `
                                        : paginated.map(log => html`
                                            <tr key=${log.id}>
                                                <td class="td-id">${log.id}</td>
                                                <td>
                                                    <div class="td-time">
                                                        <span class="td-time-primary">${Utils.fmtTimeAgo(log.timestamp)}</span>
                                                        <span class="td-time-secondary">${Utils.fmtTime(log.timestamp)}</span>
                                                    </div>
                                                </td>
                                                <td>
                                                    <span style=${'font-family:var(--font-mono);font-size:var(--text-caption1);font-weight:var(--weight-bold);color:' + actionColor(log.action) + ';'}>
                                                        ${log.action}
                                                    </span>
                                                </td>
                                                <td><span class="tag">${log.source || '--'}</span></td>
                                                <td style="color:var(--label-3);font-size:var(--text-caption1);max-width:200px;">
                                                    ${Utils.truncate(log.detail, 60)}
                                                </td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);font-size:var(--text-caption1);color:var(--label-4);">
                                                        ${log.ip || '--'}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span class=${'badge ' + (log.success ? 'badge-win' : 'badge-loss')}>
                                                        ${log.success ? 'OK' : 'FAIL'}
                                                    </span>
                                                </td>
                                            </tr>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                        <div class="table-footer">
                            <span class="table-footer-info">
                                Page <strong>${currentPage}</strong> of <strong>${totalPages}</strong>
                            </span>
                            <div class="pagination">
                                <button class="pagination-btn"
                                    onClick=${() => setCurrentPage(p => p - 1)}
                                    disabled=${currentPage <= 1}>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                                </button>
                                <span style="padding:4px 8px;font-family:var(--font-mono);font-size:var(--text-caption1);color:var(--label-3);">
                                    ${currentPage} / ${totalPages}
                                </span>
                                <button class="pagination-btn"
                                    onClick=${() => setCurrentPage(p => p + 1)}
                                    disabled=${currentPage >= totalPages}>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                                </button>
                            </div>
                        </div>
                    `
                }
            </div>
        </div>
    `
}