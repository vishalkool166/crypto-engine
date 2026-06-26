import { h, render, Fragment } from '/js/preact.min.js'
import { useState, useEffect, useRef, useCallback } from '/js/preact-hooks.min.js'
import htm from '/js/htm.min.js'
import {
    init, navigate, getState,
    requireTotp, confirmTotp, closeTotp,
    showToast, logout,
    on, emit,
    usePage, useWsState, useTicker,
    useFtUpdate, useDashboard,
    useNextScan, useTotp, useToast, useMode,
} from '/js/store.js'

const html = htm.bind(h)

function GradeBadge({ grade }) {
    const cls = {
        'A+': 'badge badge-aplus',
        'A':  'badge badge-a',
        'B':  'badge badge-b',
        'C':  'badge badge-c',
        'F':  'badge badge-f',
    }[grade] || 'badge badge-f'
    return html`<span class=${cls}>${grade}</span>`
}

function DirBadge({ dir }) {
    const cls = {
        'LONG':     'badge badge-long',
        'SHORT':    'badge badge-short',
        'WATCH':    'badge badge-watch',
        'NO TRADE': 'badge badge-f',
    }[dir] || 'badge badge-f'
    return html`<span class=${cls}>${dir}</span>`
}

function OutcomeBadge({ outcome }) {
    const cls = {
        'win':     'badge badge-win',
        'loss':    'badge badge-loss',
        'pending': 'badge badge-pending',
        'timeout': 'badge badge-f',
    }[outcome] || 'badge badge-f'
    return html`<span class=${cls}>${outcome}</span>`
}

function HealthBar({ health }) {
    if (!health) return html`
        <div class="health-bar unknown">
            <span>⏳</span>
            <span style="font-size:12px;">Checking health...</span>
        </div>
    `
    const cls = {
        'HEALTHY':     'health-bar healthy',
        'WARNING':     'health-bar warning',
        'INVALIDATED': 'health-bar invalidated',
    }[health.state] || 'health-bar unknown'
    const emoji = { 'HEALTHY': '✅', 'WARNING': '⚠️', 'INVALIDATED': '🚨' }[health.state] || '⏳'
    const msg   = health.failures?.[0] || health.warnings?.[0] || ''
    return html`
        <div class=${cls}>
            <span>${emoji}</span>
            <span style="font-weight:700;">${health.state}</span>
            ${msg && html`<span style="font-size:11px;opacity:0.8;">— ${msg}</span>`}
        </div>
    `
}

function ScoreBar({ score }) {
    const s     = parseFloat(score) || 0
    const color = Utils.scoreBarColor(s)
    return html`
        <div class="score-bar">
            <span style="font-family:var(--font-mono);font-size:12px;font-weight:600;color:${color};min-width:32px;">
                ${Math.round(s)}
            </span>
            <div class="score-bar-track">
                <div class="score-bar-fill" style="width:${s}%;background:${color};"></div>
            </div>
        </div>
    `
}

function Spinner() {
    return html`<span class="spinner"></span>`
}

function EmptyState({ message }) {
    return html`
        <div class="empty-state">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="empty-state-text">${message || 'No data available'}</span>
        </div>
    `
}

function LoadingSkeleton({ rows = 4 }) {
    return html`
        <div class="loading-skeleton">
            ${Array.from({ length: rows }).map((_, i) =>
                html`<div key=${i} class="skeleton skeleton-row"></div>`
            )}
        </div>
    `
}

function TradesBanner({ trades }) {
    const [expanded, setExpanded] = useState(false)
    if (!trades || !trades.length) return null

    const states    = trades.map(t => t.health?.state || 'UNKNOWN')
    const hasInv    = states.includes('INVALIDATED')
    const hasWarn   = states.includes('WARNING')
    const bannerCls = hasInv ? 'trades-banner has-invalidated'
                    : hasWarn ? 'trades-banner has-warning'
                    : 'trades-banner has-healthy'
    const emoji     = hasInv ? '🚨' : hasWarn ? '⚠️' : '✅'

    return html`
        <div>
            <div class=${bannerCls} onClick=${() => setExpanded(p => !p)}>
                <span>${emoji}</span>
                <span style="font-weight:800;">${trades.length} Open Trade${trades.length > 1 ? 's' : ''}</span>
                ${hasInv  && html`<span class="badge badge-invalidated">INVALIDATED</span>`}
                ${hasWarn && !hasInv && html`<span class="badge badge-warning">WARNING</span>`}
                <span style="margin-left:auto;color:var(--text-muted);font-size:11px;">
                    ${expanded ? '▲ collapse' : '▼ expand'}
                </span>
            </div>
            ${expanded && trades.map(trade => html`
                <${MiniTradeCard} key=${trade.trade_id} trade=${trade}/>
            `)}
        </div>
    `
}

function MiniTradeCard({ trade }) {
    const pair = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir  = trade.is_short ? 'SHORT' : 'LONG'
    const pnl  = parseFloat(trade.profit_abs || 0)

    return html`
        <div class="trade-card">
            <div class="trade-card-header">
                <div class="flex items-center gap-8">
                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:800;">${pair}</span>
                    <${DirBadge} dir=${dir}/>
                    <span class="tag">#${trade.trade_id}</span>
                </div>
                <div class="flex items-center gap-8">
                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:800;color:${Utils.pnlColor(pnl)};">
                        ${Utils.fmtPnl(pnl)}
                    </span>
                    <span style="font-family:var(--font-mono);font-size:11px;color:${Utils.pnlColor(trade.profit_ratio)};">
                        ${Utils.fmtPct((trade.profit_ratio || 0) * 100)}
                    </span>
                </div>
            </div>
            <div class="trade-card-levels">
                <div class="level-item">
                    <div class="level-label">Entry</div>
                    <div class="level-value">${Utils.fmtPrice(trade.open_rate)}</div>
                </div>
                <div class="level-item">
                    <div class="level-label">Current</div>
                    <div class="level-value" style="color:${Utils.pnlColor(pnl)};">
                        ${Utils.fmtPrice(trade.current_rate)}
                    </div>
                </div>
                <div class="level-item">
                    <div class="level-label">Open</div>
                    <div class="level-value">${Utils.fmtDuration(trade.open_date)}</div>
                </div>
            </div>
            <${HealthBar} health=${trade.health}/>
        </div>
    `
}

function OverviewPage() {
    const data         = useDashboard()
    const ftData       = useFtUpdate()
    const [scanning, setScanning] = useState(false)
    const [histLoading, setHistLoading] = useState(false)
    const [history, setHistory] = useState([])
    const chartDone    = useRef(false)

    const summary = data.summary     || {}
    const perf    = data.performance || {}
    const queue   = data.signals?.queue || []
    const radar   = data.signals?.radar || []

    useEffect(() => {
        if (data.history) setHistory(data.history)
    }, [data.history])

    useEffect(() => {
        if (!perf.equity_curve?.length) return
        setTimeout(() => {
            Charts.equityFromCurve('overview-equity', perf.equity_curve)
            const hasGrade = (parseFloat(perf.aplus_bar) || 0) > 0
                          || (parseFloat(perf.a_bar)     || 0) > 0
                          || (parseFloat(perf.b_bar)     || 0) > 0
            if (hasGrade) {
                Charts.gradeDonut('overview-donut', {
                    'A+': { total: parseFloat(perf.aplus_bar) || 0 },
                    'A':  { total: parseFloat(perf.a_bar)     || 0 },
                    'B':  { total: parseFloat(perf.b_bar)     || 0 },
                })
            }
            chartDone.current = true
        }, 50)
    }, [perf.equity_curve])

    useEffect(() => {
        return () => {
            Charts.destroy('overview-equity')
            Charts.destroy('overview-donut')
            chartDone.current = false
        }
    }, [])

    async function triggerScan() {
        setScanning(true)
        try {
            await API.scan()
            showToast('Scan triggered — results in 1-2 minutes', 'success')
        } catch(e) {
            showToast('Scan failed: ' + e.message, 'error')
        } finally {
            setScanning(false)
        }
    }

    async function loadHistory() {
        setHistLoading(true)
        try {
            const h = await API.dashboardHistory(10)
            if (h) setHistory(h)
        } catch(e) {} finally {
            setHistLoading(false)
        }
    }

    const lastUpdated = Utils.fmtTimeAgo(data.timestamp)

    return html`
        <div>
            <${TradesBanner} trades=${ftData.trades}/>

            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Overview</div>
                    <div class="page-subtitle">Updated ${lastUpdated}</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${triggerScan} disabled=${scanning}>
                    ${scanning ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                        </svg>
                    `}
                    ${scanning ? 'Scanning...' : 'Scan Now'}
                </button>
            </div>

            <div class="grid-4 mb-12">
                <div class="stat-card stat-card-green">
                    <div class="card-title">Today PnL</div>
                    <div class="card-value" style="color:${summary.today_pnl_color || 'var(--text-muted)'};">
                        ${summary.today_pnl || '--'}
                    </div>
                    <div class="card-sub">${summary.today_trades || 0} trades today</div>
                </div>
                <div class="stat-card stat-card-blue">
                    <div class="card-title">Win Rate</div>
                    <div class="card-value" style="color:${perf.win_rate_color || 'var(--text-muted)'};">
                        ${perf.win_rate || '--'}
                    </div>
                    <div class="card-sub">${perf.win_rate_sub || '0 closed'}</div>
                </div>
                <div class="stat-card stat-card-purple">
                    <div class="card-title">Scanning</div>
                    <div class="card-value" style="color:var(--purple);">${summary.coins_count || '--'}</div>
                    <div class="card-sub">${summary.tradeable_count || 0} tradeable now</div>
                </div>
                <div class="stat-card stat-card-gold">
                    <div class="card-title">Total PnL</div>
                    <div class="card-value" style="color:${perf.pnl_color || 'var(--text-muted)'};">
                        ${perf.total_pnl || '--'}
                    </div>
                    <div class="card-sub">${perf.pnl_sub || '0W · 0L'}</div>
                </div>
            </div>

            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Signal Queue</div>
                        <span class="tag">${queue.length} signals</span>
                    </div>
                    ${!queue.length
                        ? html`<${EmptyState} message="No tradeable signals — run scan"/>`
                        : queue.map(sig => html`
                            <div key=${sig.coin}
                                class=${'signal-queue-card grade-' + (sig.grade === 'A+' ? 'aplus' : sig.grade?.toLowerCase())}>
                                <div class="flex justify-between items-center mb-8">
                                    <div class="flex items-center gap-8">
                                        <span style="font-family:var(--font-mono);font-size:15px;font-weight:800;">
                                            ${sig.coin}USDT
                                        </span>
                                        <${GradeBadge} grade=${sig.grade}/>
                                        <${DirBadge} dir=${sig.direction}/>
                                    </div>
                                    <div class="flex items-center gap-8">
                                        <span style="font-size:11px;color:var(--text-muted);">Score</span>
                                        <span style="font-family:var(--font-mono);font-size:13px;font-weight:700;color:${Utils.scoreBarColor(sig.score)};">
                                            ${sig.score}/100
                                        </span>
                                    </div>
                                </div>
                                <div class="trade-card-levels" style="grid-template-columns:repeat(3,1fr);">
                                    <div class="level-item">
                                        <div class="level-label">Entry</div>
                                        <div class="level-value">${sig.entry || '--'}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Stop Loss</div>
                                        <div class="level-value" style="color:var(--red);">${sig.sl || '--'}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Take Profit</div>
                                        <div class="level-value" style="color:var(--green);">${sig.tp1 || '--'}</div>
                                    </div>
                                </div>
                                <div class="flex justify-between items-center" style="font-size:11px;color:var(--text-muted);margin-top:6px;">
                                    <span>R:R <span style="font-family:var(--font-mono);color:var(--text-primary);font-weight:600;">1:${sig.actual_rr || '--'}</span></span>
                                    <span>${sig.regime || '--'}</span>
                                    <span>${sig.session || '--'}</span>
                                    ${sig.stake && html`
                                        <span>Stake <span style="font-family:var(--font-mono);color:var(--blue);font-weight:600;">$${parseFloat(sig.stake).toFixed(2)}</span>
                                        <span style="font-family:var(--font-mono);color:var(--text-muted);">${sig.leverage}x</span></span>
                                    `}
                                </div>
                                ${sig.thesis && html`
                                    <div class="thesis-block">${sig.thesis}</div>
                                `}
                            </div>
                        `)
                    }
                </div>

                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Coin Radar</div>
                        <span class="tag">${radar.length} coins</span>
                    </div>
                    <div class="table-wrap" style="max-height:400px;overflow-y:auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Coin</th><th>Grade</th><th>Score</th>
                                    <th>Direction</th><th>Price</th><th>24h</th><th>Regime</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${!radar.length
                                    ? html`<tr><td colspan="7"><${EmptyState} message="Run scan to populate radar"/></td></tr>`
                                    : radar.map(r => html`
                                        <tr key=${r.coin}>
                                            <td><span style="font-family:var(--font-mono);font-weight:700;">${r.coin}</span></td>
                                            <td><${GradeBadge} grade=${r.grade}/></td>
                                            <td><${ScoreBar} score=${r.score}/></td>
                                            <td><${DirBadge} dir=${r.direction}/></td>
                                            <td><span style="font-family:var(--font-mono);">${r.price}</span></td>
                                            <td><span style="font-family:var(--font-mono);color:${r.change_color};">${r.change}</span></td>
                                            <td><span style="font-size:11px;color:var(--text-muted);">${r.regime || '--'}</span></td>
                                        </tr>
                                    `)
                                }
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="grid-2-1 mb-12">
                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Performance</div>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Profit Factor</span>
                        <span class="stat-value" style="font-family:var(--font-mono);">${perf.profit_factor || '--'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Best Trade</span>
                        <span class="stat-value" style="font-family:var(--font-mono);color:var(--green);">${perf.best_trade || '--'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Max Drawdown</span>
                        <span class="stat-value" style="font-family:var(--font-mono);color:${perf.dd_color || 'var(--text-muted)'};">${perf.max_drawdown || '--'}</span>
                    </div>
                    <div class="divider"></div>
                    ${[
                        { label: 'A+', wr: perf.aplus_wr, bar: perf.aplus_bar, detail: perf.aplus_detail, color: 'var(--gold)' },
                        { label: 'A',  wr: perf.a_wr,     bar: perf.a_bar,     detail: perf.a_detail,     color: 'var(--blue)' },
                        { label: 'B',  wr: perf.b_wr,     bar: perf.b_bar,     detail: perf.b_detail,     color: 'var(--orange)' },
                    ].map(g => html`
                        <div key=${g.label} style="margin-bottom:10px;">
                            <div class="flex justify-between items-center" style="font-size:11px;margin-bottom:5px;">
                                <span style="color:${g.color};font-weight:700;">${g.label} <span style="font-family:var(--font-mono);">${g.wr}</span></span>
                                <span style="font-size:10px;color:var(--text-muted);">${g.detail}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width:${g.bar || 0}%;background:${g.color};"></div>
                            </div>
                        </div>
                    `)}
                    <div class="divider"></div>
                    <div id="overview-donut" style="height:180px;"></div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Equity Curve</div>
                        <span class="tag">${perf.equity_curve?.length || 0} trades</span>
                    </div>
                    <div id="overview-equity" style="height:200px;"></div>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <div class="section-title">Recent Signals</div>
                    <button class="btn btn-ghost btn-sm" onClick=${loadHistory} disabled=${histLoading}>
                        ${histLoading ? html`<${Spinner}/>` : 'Refresh'}
                    </button>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th><th>Time</th><th>Coin</th><th>Direction</th>
                                <th>Grade</th><th>Score</th><th>Entry</th><th>Exit</th>
                                <th>PnL</th><th>Result</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${!history.length
                                ? html`<tr><td colspan="10"><${EmptyState} message="No closed signals yet"/></td></tr>`
                                : history.map(s => html`
                                    <tr key=${s.id}>
                                        <td><span style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;">${s.id}</span></td>
                                        <td><span style="font-size:11px;color:var(--text-secondary);">${Utils.fmtTimeAgo(s.timestamp)}</span></td>
                                        <td><span style="font-family:var(--font-mono);font-weight:700;">${s.coin}</span></td>
                                        <td><${DirBadge} dir=${s.direction}/></td>
                                        <td><${GradeBadge} grade=${s.grade}/></td>
                                        <td><${ScoreBar} score=${s.score}/></td>
                                        <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(s.entry_price)}</span></td>
                                        <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(s.exit_price)}</span></td>
                                        <td><span style="font-family:var(--font-mono);font-weight:700;color:${s.pnl_color};">${s.pnl}</span></td>
                                        <td><${OutcomeBadge} outcome=${s.outcome}/></td>
                                    </tr>
                                `)
                            }
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `
}

function SignalsPage() {
    const [signals,     setSignals]     = useState([])
    const [filtered,    setFiltered]    = useState([])
    const [loading,     setLoading]     = useState(false)
    const [expanded,    setExpanded]    = useState(null)
    const [currentPage, setCurrentPage] = useState(1)
    const [filters,     setFilters]     = useState({
        grade: '', outcome: '', direction: '', coin: '', limit: '100'
    })
    const pageSize   = 30
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
    const paginated  = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)

    useEffect(() => { load() }, [])

    async function load(reset = false) {
        if (reset) { setCurrentPage(1); setExpanded(null) }
        setLoading(true)
        try {
            const q = new URLSearchParams()
            q.set('limit', parseInt(filters.limit) || 100)
            if (filters.grade)   q.set('grade',   filters.grade)
            if (filters.coin)    q.set('coin',     filters.coin.toUpperCase().trim())
            if (filters.outcome) q.set('outcome',  filters.outcome)
            const res = await fetch('/api/signals?' + q.toString(), { credentials: 'include' })
            if (res.status === 401) { window.location.href = '/login.html'; return }
            const data = await res.json()
            setSignals(data || [])
            applyFilters(data || [], filters)
        } catch(e) {
            showToast('Failed to load signals: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    function applyFilters(sigs, f) {
        let result = [...(sigs || signals)]
        if (f.direction) result = result.filter(s => s.direction === f.direction)
        setFiltered(result)
        setCurrentPage(1)
    }

    function updateFilter(key, val) {
        const next = { ...filters, [key]: val }
        setFilters(next)
        if (key === 'direction') applyFilters(signals, next)
    }

    function clearFilters() {
        const f = { grade: '', outcome: '', direction: '', coin: '', limit: '100' }
        setFilters(f)
        load(true)
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Signals</div>
                    <div class="page-subtitle">${filtered.length} signals</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${() => load(true)} disabled=${loading}>
                    ${loading ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                    `}
                    Refresh
                </button>
            </div>

            <div class="card mb-12">
                <div class="filter-bar">
                    <select class="select" style="width:120px;" value=${filters.grade}
                        onChange=${e => { updateFilter('grade', e.target.value); load(true) }}>
                        <option value="">All Grades</option>
                        <option value="A+">A+</option>
                        <option value="A">A</option>
                        <option value="B">B</option>
                        <option value="C">C</option>
                        <option value="F">F</option>
                    </select>
                    <select class="select" style="width:130px;" value=${filters.outcome}
                        onChange=${e => { updateFilter('outcome', e.target.value); load(true) }}>
                        <option value="">All Outcomes</option>
                        <option value="win">Win</option>
                        <option value="loss">Loss</option>
                        <option value="pending">Pending</option>
                    </select>
                    <select class="select" style="width:120px;" value=${filters.direction}
                        onChange=${e => updateFilter('direction', e.target.value)}>
                        <option value="">All Directions</option>
                        <option value="LONG">Long</option>
                        <option value="SHORT">Short</option>
                    </select>
                    <input class="input" style="width:110px;" type="text" placeholder="Coin..."
                        value=${filters.coin}
                        onInput=${e => updateFilter('coin', e.target.value)}
                        onKeyDown=${e => e.key === 'Enter' && load(true)}/>
                    <select class="select" style="width:100px;" value=${filters.limit}
                        onChange=${e => { updateFilter('limit', e.target.value); load(true) }}>
                        <option value="50">50 rows</option>
                        <option value="100">100 rows</option>
                        <option value="200">200 rows</option>
                        <option value="500">500 rows</option>
                    </select>
                    <button class="btn btn-ghost btn-sm" onClick=${clearFilters}>Clear</button>
                    <div class="flex-1"></div>
                    <span style="font-size:11px;color:var(--text-secondary);">
                        <span style="font-family:var(--font-mono);color:var(--text-primary);">${filtered.length}</span>
                        ${' '}of${' '}
                        <span style="font-family:var(--font-mono);">${signals.length}</span>
                    </span>
                </div>
            </div>

            <div class="card">
                ${loading
                    ? html`<${LoadingSkeleton} rows=${5}/>`
                    : html`
                        <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>#</th><th>Time</th><th>Coin</th><th>Dir</th>
                                        <th>Grade</th><th>Score</th><th>Entry</th><th>SL</th>
                                        <th>TP</th><th>Exit</th><th>PnL</th><th>Result</th><th>Regime</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!paginated.length
                                        ? html`<tr><td colspan="13"><${EmptyState} message="No signals match filters"/></td></tr>`
                                        : paginated.map(s => html`
                                            <${Fragment} key=${s.id}>
                                                <tr style="cursor:pointer;background:${expanded === s.id ? 'var(--bg-tertiary)' : ''};"
                                                    onClick=${() => setExpanded(expanded === s.id ? null : s.id)}>
                                                    <td><span style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;">${s.id}</span></td>
                                                    <td><span style="font-size:11px;color:var(--text-secondary);">${Utils.fmtTimeAgo(s.timestamp)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);font-weight:700;">${s.coin}</span></td>
                                                    <td><${DirBadge} dir=${s.direction}/></td>
                                                    <td><${GradeBadge} grade=${s.grade}/></td>
                                                    <td><${ScoreBar} score=${s.score}/></td>
                                                    <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(s.entry)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);color:var(--red);">${Utils.fmtPrice(s.sl)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);color:var(--green);">${Utils.fmtPrice(s.tp1)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(s.exit_price)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);font-weight:700;color:${Utils.pnlColor(s.pnl)};">${s.pnl != null ? Utils.fmtPnl(s.pnl) : '--'}</span></td>
                                                    <td><${OutcomeBadge} outcome=${s.outcome}/></td>
                                                    <td><span style="font-size:11px;color:var(--text-muted);">${s.regime || '--'}</span></td>
                                                </tr>
                                                ${expanded === s.id && html`
                                                    <tr>
                                                        <td colspan="13" style="padding:0;background:var(--bg-tertiary);">
                                                            <div style="padding:16px;">
                                                                <div class="grid-4" style="gap:8px;">
                                                                    <div class="level-item">
                                                                        <div class="level-label">Signal ID</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">${s.id}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Risk Amount</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">${s.risk_amt ? '$' + parseFloat(s.risk_amt).toFixed(2) : '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Market Score</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">${s.market_score != null ? s.market_score + '/100' : '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Entry Score</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">${s.entry_score != null ? s.entry_score + '/100' : '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">BTC Score</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">${s.btc_score != null ? s.btc_score + '/8' : '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Session</div>
                                                                        <div style="font-size:12px;">${s.session || '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Signal Type</div>
                                                                        <div style="font-family:var(--font-mono);font-size:12px;">${s.signal_type || '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Timestamp</div>
                                                                        <div style="font-size:11px;color:var(--text-secondary);">${Utils.fmtTime(s.timestamp)}</div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                `}
                                            </${Fragment}>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                        <div class="pagination">
                            <span class="pagination-info">Page ${currentPage} of ${totalPages} · ${filtered.length} signals</span>
                            <div class="pagination-controls">
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(1)} disabled=${currentPage <= 1}>First</button>
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(p => p - 1)} disabled=${currentPage <= 1}>Prev</button>
                                <span style="padding:4px 10px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);">${currentPage} / ${totalPages}</span>
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(p => p + 1)} disabled=${currentPage >= totalPages}>Next</button>
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(totalPages)} disabled=${currentPage >= totalPages}>Last</button>
                            </div>
                        </div>
                    `}
            </div>
        </div>
    `
}

function FreqtradePage() {
    const ftData                          = useFtUpdate()
    const [loading,       setLoading]     = useState(false)
    const [daily,         setDaily]       = useState([])
    const [dailyDays,     setDailyDays]   = useState('7')
    const [dailyLoading,  setDailyLoading]= useState(false)
    const [tradeHistory,  setTradeHistory]= useState([])
    const [actionLoading, setActionLoading] = useState(null)
    const [forceSelling,  setForceSelling]= useState(null)
    const [error,         setError]       = useState('')
    const chartRef = useRef(false)

    const openTrades = ftData.trades  || []
    const profit     = ftData.profit  || {}
    const balance    = ftData.balance || {}
    const botState   = ftData.botState || 'unknown'

    useEffect(() => {
        refresh()
        return () => {
            Charts.destroy('ft-daily-chart')
            chartRef.current = false
        }
    }, [])

    useEffect(() => {
        if (!daily.length) return
        setTimeout(() => {
            const el = document.getElementById('ft-daily-chart')
            if (el && el.offsetParent !== null) {
                Charts.dailyPnl('ft-daily-chart', daily)
                chartRef.current = true
            }
        }, 50)
    }, [daily])

    async function refresh() {
        if (loading) return
        setLoading(true)
        setError('')
        try {
            const controller = new AbortController()
            const timeout    = setTimeout(() => controller.abort(), 12000)
            const res        = await fetch('/api/ft/summary', { credentials: 'include', signal: controller.signal })
            clearTimeout(timeout)
            if (res.status === 401) { window.location.href = '/login.html'; return }
            if (!res.ok) { setError('Freqtrade unavailable — check if container is running'); return }
            const data = await res.json().catch(() => null)
            if (data?.daily) {
                const arr = Array.isArray(data.daily) ? data.daily
                          : Array.isArray(data.daily.data) ? data.daily.data : []
                setDaily(arr.map(x => ({
                    date:       x.date || x.day || '',
                    profit_abs: parseFloat(x.profit_abs || x.profit || 0),
                })).filter(x => x.date))
            }
            loadTrades()
        } catch(e) {
            if (e.name === 'AbortError') setError('Freqtrade request timed out')
            else setError('Freqtrade unavailable: ' + e.message)
        } finally {
            setLoading(false)
        }
    }

    async function loadTrades() {
        try {
            const res  = await fetch('/api/ft/trades?limit=50', { credentials: 'include' })
            if (!res.ok) return
            const data = await res.json().catch(() => null)
            if (data) setTradeHistory(Array.isArray(data.trades) ? data.trades.filter(t => !t.is_open) : [])
        } catch(e) {}
    }

    async function loadDaily() {
        setDailyLoading(true)
        Charts.destroy('ft-daily-chart')
        chartRef.current = false
        try {
            const res = await fetch(`/api/ft/daily?days=${dailyDays}`, { credentials: 'include' })
            if (!res.ok) return
            const raw = await res.json().catch(() => null)
            if (!raw) return
            const arr = Array.isArray(raw) ? raw : Array.isArray(raw.data) ? raw.data : []
            setDaily(arr.map(x => ({
                date:       x.date || x.day || '',
                profit_abs: parseFloat(x.profit_abs || x.profit || 0),
            })).filter(x => x.date))
        } catch(e) {} finally {
            setDailyLoading(false)
        }
    }

    async function startBot() {
        setActionLoading('start')
        try {
            const res  = await fetch('/api/ft/start', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' } })
            const data = await res.json().catch(() => ({}))
            showToast('Bot: ' + (data.status || 'start command sent'), 'success')
            setTimeout(() => refresh(), 2000)
        } catch(e) {
            showToast('Start failed: ' + e.message, 'error')
        } finally {
            setActionLoading(null)
        }
    }

    async function stopBot() {
        setActionLoading('stop')
        try {
            const res  = await fetch('/api/ft/stop', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' } })
            const data = await res.json().catch(() => ({}))
            showToast('Bot: ' + (data.status || 'stop command sent'), 'success')
            setTimeout(() => refresh(), 2000)
        } catch(e) {
            showToast('Stop failed: ' + e.message, 'error')
        } finally {
            setActionLoading(null)
        }
    }

    async function forceSell(tradeId, pair) {
        const coin = (pair || '').replace('/USDT:USDT', '').replace('/USDT', '')
        const code = await requireTotp('Force Sell — ' + coin, 'Enter your TOTP code to confirm force sell of ' + coin)
        if (!code) return
        setForceSelling(tradeId)
        try {
            const res = await fetch('/api/ft/forcesell', {
                method:  'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ tradeid: tradeId, totp_code: code })
            })
            const data = await res.json()
            if (data.success === false) {
                showToast('Force sell failed: ' + (data.reason || 'Unknown error'), 'error')
            } else {
                showToast('Force sell submitted for ' + coin, 'success')
                setTimeout(() => refresh(), 2000)
            }
        } catch(e) {
            showToast('Force sell failed: ' + e.message, 'error')
        } finally {
            setForceSelling(null)
        }
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Freqtrade</div>
                    <div class="page-subtitle flex items-center gap-8">
                        <div class="ws-dot ${botState === 'running' ? '' : 'disconnected'}"></div>
                        <span>Bot ${botState}</span>
                    </div>
                </div>
                <div class="flex gap-8">
                    <button class="btn btn-success btn-sm" onClick=${startBot}
                        disabled=${actionLoading === 'start' || botState === 'running'}>
                        ${actionLoading === 'start' ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        `}
                        Start
                    </button>
                    <button class="btn btn-danger btn-sm" onClick=${stopBot}
                        disabled=${actionLoading === 'stop' || botState === 'stopped'}>
                        ${actionLoading === 'stop' ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18"/></svg>
                        `}
                        Stop
                    </button>
                    <button class="btn btn-ghost btn-sm" onClick=${refresh} disabled=${loading}>
                        ${loading ? html`<${Spinner}/>` : 'Refresh'}
                    </button>
                </div>
            </div>

            ${error && html`<div class="alert alert-error mb-12">${error}</div>`}

            <div class="grid-4 mb-12">
                <div class="stat-card stat-card-blue">
                    <div class="card-title">Bot State</div>
                    <div style="margin-top:6px;">
                        <span class=${'badge ' + (botState === 'running' ? 'badge-online' : 'badge-offline')}>
                            ${botState.toUpperCase()}
                        </span>
                    </div>
                    <div class="card-sub" style="font-family:var(--font-mono);">${openTrades.length} open trades</div>
                </div>
                <div class="stat-card stat-card-green">
                    <div class="card-title">Balance</div>
                    <div class="card-value" style="color:var(--green);">
                        ${balance.total != null ? '$' + parseFloat(balance.total).toFixed(2) : '--'}
                    </div>
                    <div class="card-sub" style="font-family:var(--font-mono);">
                        ${balance.free != null ? 'Free: $' + parseFloat(balance.free).toFixed(2) : '--'}
                    </div>
                </div>
                <div class=${'stat-card ' + ((profit.profit_all_coin || 0) >= 0 ? 'stat-card-green' : 'stat-card-red')}>
                    <div class="card-title">Total PnL</div>
                    <div class="card-value" style="color:${Utils.pnlColor(profit.profit_all_coin)};">
                        ${profit.profit_all_coin != null ? Utils.fmtPnl(profit.profit_all_coin) : '--'}
                    </div>
                    <div class="card-sub">${profit.trade_count != null ? profit.trade_count + ' total trades' : '--'}</div>
                </div>
                <div class="stat-card stat-card-purple">
                    <div class="card-title">Win Rate</div>
                    <div class="card-value" style="color:${Utils.winRateColor((profit.winrate || 0) * 100)};">
                        ${profit.winrate != null ? ((profit.winrate || 0) * 100).toFixed(1) + '%' : '--'}
                    </div>
                    <div class="card-sub">
                        ${profit.profit_factor != null ? 'PF: ' + parseFloat(profit.profit_factor || 0).toFixed(2) : '--'}
                    </div>
                </div>
            </div>

            <div class="mb-12">
                <div class="section-header">
                    <div class="section-title">Open Trades</div>
                    <span class="tag">${openTrades.length} open</span>
                </div>
                ${loading && !openTrades.length
                    ? html`<div class="card"><${LoadingSkeleton} rows=${3}/></div>`
                    : !openTrades.length
                    ? html`<div class="card"><${EmptyState} message="No open trades"/></div>`
                    : openTrades.map(trade => {
                        const pair = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
                        const dir  = trade.is_short ? 'SHORT' : 'LONG'
                        const pnl  = parseFloat(trade.profit_abs || 0)
                        return html`
                            <div key=${trade.trade_id} class="trade-card">
                                <div class="trade-card-header">
                                    <div class="flex items-center gap-8">
                                        <span style="font-family:var(--font-mono);font-size:15px;font-weight:800;">${pair}</span>
                                        <${DirBadge} dir=${dir}/>
                                        <span class="tag">#${trade.trade_id}</span>
                                    </div>
                                    <div class="flex items-center gap-12">
                                        <div style="text-align:right;">
                                            <div style="font-family:var(--font-mono);font-size:16px;font-weight:800;color:${Utils.pnlColor(pnl)};">
                                                ${Utils.fmtPnl(pnl)}
                                            </div>
                                            <div style="font-family:var(--font-mono);font-size:11px;color:${Utils.pnlColor(trade.profit_ratio)};">
                                                ${Utils.fmtPct((trade.profit_ratio || 0) * 100)}
                                            </div>
                                        </div>
                                        <button class="btn btn-danger btn-sm"
                                            onClick=${() => forceSell(trade.trade_id, trade.pair)}
                                            disabled=${forceSelling === trade.trade_id}>
                                            ${forceSelling === trade.trade_id ? html`<${Spinner}/>` : 'Force Sell'}
                                        </button>
                                    </div>
                                </div>
                                <div class="trade-card-levels">
                                    <div class="level-item">
                                        <div class="level-label">Entry</div>
                                        <div class="level-value">${Utils.fmtPrice(trade.open_rate)}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Current</div>
                                        <div class="level-value" style="color:${Utils.pnlColor(pnl)};">${Utils.fmtPrice(trade.current_rate)}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Stop Loss</div>
                                        <div class="level-value" style="color:var(--red);">${trade.sl_signal ? Utils.fmtPrice(trade.sl_signal) : '--'}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Take Profit</div>
                                        <div class="level-value" style="color:var(--green);">${trade.tp1 ? Utils.fmtPrice(trade.tp1) : '--'}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Open</div>
                                        <div class="level-value">${Utils.fmtDuration(trade.open_date)}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Stake</div>
                                        <div class="level-value">${trade.stake_amount ? '$' + parseFloat(trade.stake_amount).toFixed(2) : '--'}</div>
                                    </div>
                                </div>
                                <${HealthBar} health=${trade.health}/>
                                ${trade.enter_tag && html`
                                    <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
                                        Tag: <span style="font-family:var(--font-mono);">${trade.enter_tag}</span>
                                    </div>
                                `}
                            </div>
                        `
                    })
                }
            </div>

            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="flex justify-between items-center mb-12">
                        <div class="section-title">Daily PnL</div>
                        <select class="select" style="width:100px;" value=${dailyDays}
                            onChange=${e => { setDailyDays(e.target.value); loadDaily() }}>
                            <option value="7">7 days</option>
                            <option value="14">14 days</option>
                            <option value="30">30 days</option>
                            <option value="60">60 days</option>
                            <option value="90">90 days</option>
                        </select>
                    </div>
                    ${dailyLoading
                        ? html`<${LoadingSkeleton} rows=${2}/>`
                        : !daily.length
                        ? html`<${EmptyState} message="No daily data"/>`
                        : html`<div id="ft-daily-chart"></div>`
                    }
                </div>
                <div class="card">
                    <div class="section-title mb-12">Profit Summary</div>
                    ${[
                        { label: 'Total PnL',     val: profit.profit_all_coin != null ? Utils.fmtPnl(profit.profit_all_coin) : '--', color: Utils.pnlColor(profit.profit_all_coin) },
                        { label: 'Win Rate',      val: profit.winrate != null ? ((profit.winrate || 0) * 100).toFixed(1) + '%' : '--', color: Utils.winRateColor((profit.winrate || 0) * 100) },
                        { label: 'Total Trades',  val: profit.trade_count != null ? profit.trade_count : '--' },
                        { label: 'Profit Factor', val: profit.profit_factor != null ? parseFloat(profit.profit_factor).toFixed(2) : '--' },
                        { label: 'Best Pair',     val: profit.best_pair || '--' },
                        { label: 'Balance',       val: balance.total != null ? '$' + parseFloat(balance.total).toFixed(2) : '--', color: 'var(--blue)' },
                        { label: 'Free',          val: balance.free  != null ? '$' + parseFloat(balance.free).toFixed(2)  : '--' },
                    ].map(row => html`
                        <div key=${row.label} class="stat-row">
                            <span class="stat-label">${row.label}</span>
                            <span class="stat-value" style="font-family:var(--font-mono);${row.color ? 'color:' + row.color : ''}">${row.val}</span>
                        </div>
                    `)}
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <div class="section-title">Trade History</div>
                    <span class="tag">${tradeHistory.length} trades</span>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th><th>Pair</th><th>Dir</th><th>Entry</th>
                                <th>Exit</th><th>PnL</th><th>%</th><th>Duration</th><th>Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${!tradeHistory.length
                                ? html`<tr><td colspan="9"><${EmptyState} message="No closed trades yet"/></td></tr>`
                                : tradeHistory.map(t => html`
                                    <tr key=${t.trade_id}>
                                        <td><span style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;">${t.trade_id}</span></td>
                                        <td><span style="font-family:var(--font-mono);font-weight:700;">${(t.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')}</span></td>
                                        <td><${DirBadge} dir=${t.is_short ? 'SHORT' : 'LONG'}/></td>
                                        <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(t.open_rate)}</span></td>
                                        <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(t.close_rate)}</span></td>
                                        <td><span style="font-family:var(--font-mono);font-weight:700;color:${Utils.pnlColor(t.profit_abs)};">${Utils.fmtPnl(t.profit_abs)}</span></td>
                                        <td><span style="font-family:var(--font-mono);color:${Utils.pnlColor(t.profit_ratio)};">${Utils.fmtPct((t.profit_ratio || 0) * 100)}</span></td>
                                        <td><span style="font-size:11px;color:var(--text-secondary);">${Utils.fmtDuration(t.open_date)}</span></td>
                                        <td><span style="font-size:11px;color:var(--text-muted);">${t.exit_reason || '--'}</span></td>
                                    </tr>
                                `)
                            }
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `
}

function CoinsPage() {
    const [coins,        setCoins]       = useState([])
    const [filtered,     setFiltered]    = useState([])
    const [loading,      setLoading]     = useState(false)
    const [adding,       setAdding]      = useState(false)
    const [validating,   setValidating]  = useState(false)
    const [toggling,     setToggling]    = useState(null)
    const [deleting,     setDeleting]    = useState(null)
    const [newCoin,      setNewCoin]     = useState('')
    const [addMsg,       setAddMsg]      = useState('')
    const [addOk,        setAddOk]       = useState(false)
    const [filterStatus, setFilterStatus]= useState('')
    const [search,       setSearch]      = useState('')

    const total   = coins.length
    const enabled = coins.filter(c => c.enabled).length

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.coins()
            setCoins(data || [])
            applyFilter(data || [], filterStatus, search)
        } catch(e) {
            showToast('Failed to load coins: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    function applyFilter(c, status, s) {
        let result = [...(c || coins)]
        if (status === 'enabled')  result = result.filter(x => x.enabled)
        if (status === 'disabled') result = result.filter(x => !x.enabled)
        if (s) result = result.filter(x => x.coin.includes(s.toUpperCase()))
        setFiltered(result)
    }

    async function addCoin() {
        if (!newCoin || newCoin.length < 2) return
        setAdding(true)
        setAddMsg('')
        setValidating(true)
        try {
            const validation = await API.validateCoin(newCoin)
            setValidating(false)
            if (!validation.valid) {
                setAddOk(false)
                setAddMsg(validation.reason || 'Coin not found on Binance Futures')
                return
            }
            const result = await API.addCoin(newCoin)
            if (result.success) {
                setAddOk(true)
                setAddMsg(result.message || newCoin + ' added successfully')
                setNewCoin('')
                await load()
                showToast(result.message || newCoin + ' added', 'success')
            } else {
                setAddOk(false)
                setAddMsg(result.reason || 'Failed to add coin')
            }
        } catch(e) {
            setValidating(false)
            setAddOk(false)
            setAddMsg(e.message || 'Failed to add coin')
        } finally {
            setAdding(false)
            setValidating(false)
            setTimeout(() => setAddMsg(''), 5000)
        }
    }

    async function toggleCoin(coin) {
        setToggling(coin.coin)
        try {
            await API.toggleCoin(coin.coin, !coin.enabled)
            const updated = coins.map(c => c.coin === coin.coin ? { ...c, enabled: !c.enabled } : c)
            setCoins(updated)
            applyFilter(updated, filterStatus, search)
            showToast(coin.coin + (!coin.enabled ? ' enabled' : ' disabled'), 'success')
        } catch(e) {
            showToast('Failed to toggle ' + coin.coin + ': ' + e.message, 'error')
        } finally {
            setToggling(null)
        }
    }

    async function deleteCoin(coinName) {
        const code = await requireTotp('Delete ' + coinName, 'Enter your TOTP code to permanently remove ' + coinName)
        if (!code) return
        setDeleting(coinName)
        try {
            const res = await fetch('/api/coins/' + coinName, {
                method: 'DELETE', credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ totp_code: code })
            })
            if (res.ok) {
                const updated = coins.filter(c => c.coin !== coinName)
                setCoins(updated)
                applyFilter(updated, filterStatus, search)
                showToast(coinName + ' removed', 'success')
            } else {
                const err = await res.json().catch(() => ({}))
                showToast('Delete failed: ' + (err.detail || 'Unknown error'), 'error')
            }
        } catch(e) {
            showToast('Delete failed: ' + e.message, 'error')
        } finally {
            setDeleting(null)
        }
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Coin Universe</div>
                    <div class="page-subtitle">${enabled} enabled · ${total} total</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${load} disabled=${loading}>
                    ${loading ? html`<${Spinner}/>` : 'Refresh'}
                </button>
            </div>

            <div class="card mb-12">
                <div class="section-title mb-12">Add Coin</div>
                <div class="flex gap-8" style="flex-wrap:wrap;">
                    <input class="input" style="max-width:180px;" type="text" placeholder="BTC, ETH, SOL..."
                        value=${newCoin}
                        onInput=${e => setNewCoin(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                        onKeyDown=${e => e.key === 'Enter' && addCoin()}
                        disabled=${adding}/>
                    <button class="btn btn-primary" onClick=${addCoin}
                        disabled=${adding || !newCoin || newCoin.length < 2}>
                        ${adding ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                            </svg>
                        `}
                        Add Coin
                    </button>
                </div>
                ${validating && html`
                    <div style="font-size:12px;color:var(--text-secondary);margin-top:8px;display:flex;align-items:center;gap:6px;">
                        <${Spinner}/> Validating on Binance Futures...
                    </div>
                `}
                ${addMsg && html`
                    <div class=${'alert mt-12 ' + (addOk ? 'alert-success' : 'alert-error')}>${addMsg}</div>
                `}
            </div>

            <div class="card">
                <div class="filter-bar mb-12">
                    <select class="select" style="width:130px;" value=${filterStatus}
                        onChange=${e => { setFilterStatus(e.target.value); applyFilter(coins, e.target.value, search) }}>
                        <option value="">All Coins</option>
                        <option value="enabled">Enabled Only</option>
                        <option value="disabled">Disabled Only</option>
                    </select>
                    <input class="input" style="width:130px;" type="text" placeholder="Search coin..."
                        value=${search}
                        onInput=${e => { setSearch(e.target.value); applyFilter(coins, filterStatus, e.target.value) }}/>
                    <div class="flex-1"></div>
                    <span style="font-size:11px;color:var(--text-secondary);">
                        <span style="font-family:var(--font-mono);color:var(--text-primary);">${filtered.length}</span> coins
                    </span>
                </div>

                ${loading
                    ? html`<${LoadingSkeleton} rows=${4}/>`
                    : html`
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Coin</th><th>Status</th><th>Grade</th><th>Score</th>
                                        <th>Direction</th><th>Price</th><th>24h</th><th>Funding</th>
                                        <th>Source</th><th>Added</th><th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!filtered.length
                                        ? html`<tr><td colspan="11"><${EmptyState} message="No coins found"/></td></tr>`
                                        : filtered.map(coin => html`
                                            <tr key=${coin.coin}>
                                                <td>
                                                    <div class="flex items-center gap-6">
                                                        <span style="font-family:var(--font-mono);font-weight:800;font-size:13px;">${coin.coin}</span>
                                                        <span style="font-size:10px;color:var(--text-muted);">USDT</span>
                                                    </div>
                                                </td>
                                                <td><span class=${'badge ' + (coin.enabled ? 'badge-online' : 'badge-offline')}>${coin.enabled ? 'ON' : 'OFF'}</span></td>
                                                <td>${coin.grade && coin.grade !== '--' ? html`<${GradeBadge} grade=${coin.grade}/>` : html`<span style="color:var(--text-muted);">--</span>`}</td>
                                                <td>${coin.score ? html`<${ScoreBar} score=${coin.score}/>` : html`<span style="color:var(--text-muted);">--</span>`}</td>
                                                <td>${coin.direction && coin.direction !== '--' ? html`<${DirBadge} dir=${coin.direction}/>` : html`<span style="color:var(--text-muted);">--</span>`}</td>
                                                <td><span style="font-family:var(--font-mono);">${coin.price || '--'}</span></td>
                                                <td><span style="font-family:var(--font-mono);color:${coin.change_color};">${coin.change || '--'}</span></td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);font-size:11px;color:${Math.abs(coin.funding || 0) > 0.05 ? 'var(--red)' : Math.abs(coin.funding || 0) > 0.03 ? 'var(--orange)' : 'var(--text-secondary)'};">
                                                        ${coin.funding != null ? coin.funding.toFixed(4) + '%' : '--'}
                                                    </span>
                                                </td>
                                                <td><span class="tag">${coin.source || 'manual'}</span></td>
                                                <td><span style="font-size:11px;color:var(--text-secondary);">${Utils.fmtTimeAgo(coin.added_at)}</span></td>
                                                <td>
                                                    <div class="flex gap-6">
                                                        <button class=${'btn btn-sm ' + (coin.enabled ? 'btn-warning' : 'btn-success')}
                                                            onClick=${() => toggleCoin(coin)}
                                                            disabled=${toggling === coin.coin}>
                                                            ${toggling === coin.coin ? html`<${Spinner}/>` : (coin.enabled ? 'Disable' : 'Enable')}
                                                        </button>
                                                        <button class="btn btn-danger btn-sm btn-icon"
                                                            onClick=${() => deleteCoin(coin.coin)}
                                                            disabled=${deleting === coin.coin}>
                                                            ${deleting === coin.coin ? html`<${Spinner}/>` : html`
                                                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                                    <polyline points="3 6 5 6 21 6"/>
                                                                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                                                                </svg>
                                                            `}
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                    `}
            </div>
        </div>
    `
}

function BacktestPage() {
    const [coins,          setCoins]         = useState([])
    const [selectedCoin,   setSelectedCoin]  = useState('')
    const [result,         setResult]        = useState(null)
    const [history,        setHistory]       = useState([])
    const [running,        setRunning]       = useState(false)
    const [historyLoading, setHistoryLoading]= useState(false)
    const [error,          setError]         = useState('')
    const [tradePage,      setTradePage]     = useState(1)
    const tradePageSize = 25

    const paginatedTrades = result?.trades
        ? result.trades.slice((tradePage - 1) * tradePageSize, tradePage * tradePageSize)
        : []
    const totalTradePages = result?.trades
        ? Math.max(1, Math.ceil(result.trades.length / tradePageSize))
        : 1

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
            if (result.trades?.length)  Charts.equity('bt-equity-chart', result.trades)
            if (result.by_grade)        Charts.gradeDonut('bt-grade-donut', result.by_grade)
        }, 50)
    }, [result])

    async function loadCoins() {
        try {
            const data = await API.coins()
            const enabled = (data || []).filter(c => c.enabled).map(c => c.coin)
            setCoins(enabled)
            if (enabled.length && !selectedCoin) setSelectedCoin(enabled[0])
        } catch(e) {}
    }

    async function loadHistory() {
        setHistoryLoading(true)
        try {
            const data = await API.backtestHistory()
            setHistory(data || [])
        } catch(e) {} finally {
            setHistoryLoading(false)
        }
    }

    async function runBacktest() {
        if (!selectedCoin) return
        setRunning(true)
        setError('')
        setResult(null)
        setTradePage(1)
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
            <div class="page-header">
                <div class="page-title">Backtest</div>
                <div class="page-subtitle">Historical signal simulation on stored candle data</div>
            </div>

            <div class="card mb-12">
                <div class="section-title mb-12">Run Backtest</div>
                <div class="flex gap-8" style="flex-wrap:wrap;align-items:center;">
                    <select class="select" style="width:160px;" value=${selectedCoin}
                        onChange=${e => setSelectedCoin(e.target.value)}>
                        <option value="">Select Coin</option>
                        ${coins.map(c => html`<option key=${c} value=${c}>${c}USDT</option>`)}
                    </select>
                    <button class="btn btn-primary" onClick=${runBacktest} disabled=${running || !selectedCoin}>
                        ${running ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="5 3 19 12 5 21 5 3"/>
                            </svg>
                        `}
                        ${running ? 'Running... (up to 2 min)' : 'Run Backtest'}
                    </button>
                    <button class="btn btn-ghost btn-sm" onClick=${loadHistory} disabled=${historyLoading}>
                        ${historyLoading ? html`<${Spinner}/>` : 'History'}
                    </button>
                </div>
                ${running && html`
                    <div class="alert alert-info mt-12">
                        ⏳ Running backtest for <span style="font-family:var(--font-mono);font-weight:700;">${selectedCoin}USDT</span> — this may take up to 2 minutes...
                    </div>
                `}
                ${error && html`<div class="alert alert-error mt-12">${error}</div>`}
            </div>

            ${result && html`
                <div>
                    <div class="grid-4 mb-12">
                        <div class="stat-card stat-card-blue">
                            <div class="card-title">Win Rate</div>
                            <div class="card-value" style="color:${Utils.winRateColor(result.win_rate)};">${result.win_rate}%</div>
                            <div class="card-sub">${result.wins}W · ${result.losses}L · ${result.total_trades} trades</div>
                        </div>
                        <div class=${'stat-card ' + (result.total_pnl >= 0 ? 'stat-card-green' : 'stat-card-red')}>
                            <div class="card-title">Total PnL</div>
                            <div class="card-value" style="color:${Utils.pnlColor(result.total_pnl)};">${Utils.fmtPnl(result.total_pnl)}</div>
                            <div class="card-sub">Return: ${result.total_return}%</div>
                        </div>
                        <div class="stat-card stat-card-red">
                            <div class="card-title">Max Drawdown</div>
                            <div class="card-value" style="color:var(--red);">${result.max_drawdown}%</div>
                            <div class="card-sub">Profit Factor: ${result.profit_factor}</div>
                        </div>
                        <div class="stat-card stat-card-purple">
                            <div class="card-title">Signals</div>
                            <div class="card-value" style="color:var(--purple);">${result.total_signals}</div>
                            <div class="card-sub">A+: ${result.aplus_signals} · A: ${result.a_signals}</div>
                        </div>
                    </div>

                    <div class="grid-2 mb-12">
                        <div class="card">
                            <div class="section-title mb-12">Equity Curve</div>
                            <div id="bt-equity-chart"></div>
                        </div>
                        <div class="card">
                            <div class="section-title mb-12">By Grade</div>
                            <div id="bt-grade-donut" class="mb-12"></div>
                            ${Object.entries(result.by_grade || {}).map(([grade, data]) => html`
                                <div key=${grade} style="margin-bottom:12px;">
                                    <div class="flex justify-between items-center" style="margin-bottom:5px;">
                                        <div class="flex items-center gap-8">
                                            <${GradeBadge} grade=${grade}/>
                                            <span style="font-size:11px;color:var(--text-secondary);">${data.trades} trades</span>
                                        </div>
                                        <div class="flex items-center gap-8">
                                            <span style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:${Utils.winRateColor(data.win_rate)};">${data.win_rate}%</span>
                                            <span style="font-family:var(--font-mono);font-size:11px;color:${Utils.pnlColor(data.pnl)};">${Utils.fmtPnl(data.pnl)}</span>
                                        </div>
                                    </div>
                                    <div class="progress-bar">
                                        <div class="progress-fill" style="width:${data.win_rate}%;background:${Utils.winRateColor(data.win_rate)};"></div>
                                    </div>
                                </div>
                            `)}
                            <div class="divider"></div>
                            ${[
                                { label: 'Period',            val: result.period_start + ' → ' + result.period_end },
                                { label: 'Best Trade',        val: Utils.fmtPnl(result.best_trade),  color: 'var(--green)' },
                                { label: 'Worst Trade',       val: Utils.fmtPnl(result.worst_trade), color: 'var(--red)' },
                                { label: 'Avg Trade',         val: Utils.fmtPnl(result.avg_trade),   color: Utils.pnlColor(result.avg_trade) },
                                { label: 'Expectancy',        val: Utils.fmtPnl(result.expectancy),  color: Utils.pnlColor(result.expectancy) },
                                { label: 'Max Consec Wins',   val: result.max_consec_wins   || '--', color: 'var(--green)' },
                                { label: 'Max Consec Losses', val: result.max_consec_losses || '--', color: 'var(--red)' },
                                { label: 'TP1 Hit Rate',      val: result.phase_breakdown?.tp1_hit_rate + '%' || '--' },
                            ].map(row => html`
                                <div key=${row.label} class="stat-row">
                                    <span class="stat-label">${row.label}</span>
                                    <span class="stat-value" style="font-family:var(--font-mono);${row.color ? 'color:' + row.color : ''}">${row.val}</span>
                                </div>
                            `)}
                        </div>
                    </div>

                    <div class="card mb-12">
                        <div class="section-header">
                            <div class="section-title">Trade Log</div>
                            <span class="tag">${result.trades?.length} trades</span>
                        </div>
                        <div class="table-wrap" style="max-height:400px;overflow-y:auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Date</th><th>Dir</th><th>Grade</th><th>Score</th>
                                        <th>Entry</th><th>Exit</th><th>PnL</th><th>Result</th>
                                        <th>Reason</th><th>Candles</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!paginatedTrades.length
                                        ? html`<tr><td colspan="10"><${EmptyState} message="No trades"/></td></tr>`
                                        : paginatedTrades.map((t, i) => html`
                                            <tr key=${i}>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;">${t.date}</span></td>
                                                <td><${DirBadge} dir=${t.direction}/></td>
                                                <td><${GradeBadge} grade=${t.grade}/></td>
                                                <td><${ScoreBar} score=${t.score}/></td>
                                                <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(t.entry)}</span></td>
                                                <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(t.exit_price)}</span></td>
                                                <td><span style="font-family:var(--font-mono);font-weight:700;color:${Utils.pnlColor(t.pnl)};">${Utils.fmtPnl(t.pnl)}</span></td>
                                                <td><${OutcomeBadge} outcome=${t.outcome}/></td>
                                                <td><span style="font-size:11px;color:var(--text-muted);">${t.reason || '--'}</span></td>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;">${t.candles || '--'}</span></td>
                                            </tr>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                        <div class="pagination">
                            <span class="pagination-info">Page ${tradePage} of ${totalTradePages}</span>
                            <div class="pagination-controls">
                                <button class="btn btn-ghost btn-sm" onClick=${() => setTradePage(p => p - 1)} disabled=${tradePage <= 1}>Prev</button>
                                <button class="btn btn-ghost btn-sm" onClick=${() => setTradePage(p => p + 1)} disabled=${tradePage >= totalTradePages}>Next</button>
                            </div>
                        </div>
                    </div>
                </div>
            `}

            ${!result && history.length && html`
                <div class="card">
                    <div class="section-title mb-12">Backtest History</div>
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Coin</th><th>Run At</th><th>Period</th><th>Trades</th>
                                    <th>Win Rate</th><th>PnL</th><th>Max DD</th><th>Notes</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${history.map(h => html`
                                    <tr key=${h.id}>
                                        <td><span style="font-family:var(--font-mono);font-weight:700;">${h.coin}</span></td>
                                        <td><span style="font-size:11px;color:var(--text-secondary);">${Utils.fmtTimeAgo(h.run_at)}</span></td>
                                        <td><span style="font-size:11px;color:var(--text-secondary);">${h.period_start} → ${h.period_end}</span></td>
                                        <td><span style="font-family:var(--font-mono);">${h.total_trades}</span></td>
                                        <td><span style="font-family:var(--font-mono);color:${Utils.winRateColor(h.win_rate)};">${h.win_rate}%</span></td>
                                        <td><span style="font-family:var(--font-mono);color:${Utils.pnlColor(h.total_pnl)};">${Utils.fmtPnl(h.total_pnl)}</span></td>
                                        <td><span style="font-family:var(--font-mono);color:var(--red);">${h.max_drawdown}%</span></td>
                                        <td><span style="font-size:11px;color:var(--text-muted);">${Utils.truncate(h.notes, 50)}</span></td>
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

function AnalysisPage() {
    const [factors, setFactors] = useState(null)
    const [ml,      setMl]      = useState({})
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        load()
        return () => {
            Charts.destroy('factor-bar-chart')
        }
    }, [])

    useEffect(() => {
        if (!factors) return
        const mlPct = ml ? Math.min(100, ((ml.closed_trades || 0) / (ml.required || 100)) * 100) : 0
        Charts.mlProgress('ml-progress-chart', mlPct)
        if (factors?.table?.length) {
            setTimeout(() => Charts.factorBar('factor-bar-chart', factors.table), 50)
        }
    }, [factors, ml])

    async function load() {
        setLoading(true)
        try {
            const [f, health] = await Promise.all([API.factorAnalysis(), API.health()])
            setFactors(f || null)
            setMl(health?.ml_status || {})
        } catch(e) {
            showToast('Failed to load analysis: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Analysis</div>
                    <div class="page-subtitle">Factor performance and ML model status</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${load} disabled=${loading}>
                    ${loading ? html`<${Spinner}/>` : 'Refresh'}
                </button>
            </div>

            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="section-header">
                        <div class="section-title">ML Model</div>
                        <span class=${'badge ' + (ml?.ml_enabled ? 'badge-online' : 'badge-pending')}>
                            ${ml?.ml_enabled ? 'ACTIVE' : 'COLLECTING'}
                        </span>
                    </div>
                    ${loading
                        ? html`<${LoadingSkeleton} rows=${3}/>`
                        : html`
                            <div>
                                <div id="ml-progress-chart"></div>
                                <div class="divider"></div>
                                <div class="stat-row">
                                    <span class="stat-label">Status</span>
                                    <span style="font-size:12px;">${ml?.ml_enabled ? '✅ Active' : '⏳ Collecting data'}</span>
                                </div>
                                <div class="stat-row">
                                    <span class="stat-label">Progress</span>
                                    <span style="font-family:var(--font-mono);font-size:12px;">${ml?.closed_trades || 0} / ${ml?.required || 100} trades</span>
                                </div>
                                ${ml?.trained_at && ml.trained_at !== '--' && html`
                                    <div class="stat-row">
                                        <span class="stat-label">Last Trained</span>
                                        <span style="font-size:12px;color:var(--text-secondary);">${Utils.fmtTimeAgo(ml.trained_at)}</span>
                                    </div>
                                `}
                                ${ml?.cv_auc && ml.cv_auc !== '--' && html`
                                    <div class="stat-row">
                                        <span class="stat-label">CV AUC</span>
                                        <span style="font-family:var(--font-mono);font-weight:700;color:var(--green);">${ml.cv_auc}</span>
                                    </div>
                                `}
                                ${ml?.win_rate && html`
                                    <div class="stat-row">
                                        <span class="stat-label">Training WR</span>
                                        <span style="font-family:var(--font-mono);font-weight:700;color:${Utils.winRateColor(ml.win_rate)};">${ml.win_rate}%</span>
                                    </div>
                                `}
                                ${ml?.message && html`
                                    <div class="alert alert-info mt-12" style="font-size:12px;">${ml.message}</div>
                                `}
                                ${ml?.top_features?.length && html`
                                    <div class="mt-12">
                                        <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">Top Features</div>
                                        ${ml.top_features.slice(0, 5).map(f => html`
                                            <div key=${f.feature} style="margin-bottom:10px;">
                                                <div class="flex justify-between" style="font-size:11px;margin-bottom:4px;">
                                                    <span style="color:var(--text-secondary);">${f.feature.replace(/_/g, ' ')}</span>
                                                    <span style="font-family:var(--font-mono);color:var(--blue);font-weight:700;">${f.importance}</span>
                                                </div>
                                                <div class="progress-bar">
                                                    <div class="progress-fill" style="width:${Math.min(100, (f.importance / (ml.top_features[0]?.importance || 1)) * 100)}%;background:var(--blue);"></div>
                                                </div>
                                            </div>
                                        `)}
                                    </div>
                                `}
                            </div>
                        `
                    }
                </div>

                <div class="card">
                    <div class="section-title mb-12">Overall Stats</div>
                    ${loading
                        ? html`<${LoadingSkeleton} rows=${4}/>`
                        : factors
                        ? html`
                            <div>
                                <div class="grid-2" style="gap:8px;margin-bottom:16px;">
                                    ${[
                                        { label: 'Total Trades',    val: factors.total || 0 },
                                        { label: 'Overall Win Rate', val: (factors.overall_wr || 0) + '%', color: Utils.winRateColor(factors.overall_wr) },
                                        { label: 'Wins',   val: factors.wins   || 0, color: 'var(--green)' },
                                        { label: 'Losses', val: factors.losses || 0, color: 'var(--red)' },
                                    ].map(item => html`
                                        <div key=${item.label} class="level-item">
                                            <div class="level-label">${item.label}</div>
                                            <div style="font-size:22px;font-weight:800;font-family:var(--font-mono);${item.color ? 'color:' + item.color : ''}">${item.val}</div>
                                        </div>
                                    `)}
                                </div>
                                <div class=${'alert ' + (factors.reliable ? 'alert-success' : 'alert-warning')} style="font-size:12px;">
                                    ${factors.reliability || '--'}
                                </div>
                                ${factors.grade_stats?.length && html`
                                    <div class="mt-12">
                                        <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">By Grade</div>
                                        ${factors.grade_stats.map(g => html`
                                            <div key=${g.grade} style="margin-bottom:12px;">
                                                <div class="flex justify-between items-center" style="margin-bottom:5px;">
                                                    <div class="flex items-center gap-8">
                                                        <${GradeBadge} grade=${g.grade}/>
                                                        <span style="font-size:11px;color:var(--text-secondary);">${g.total} trades</span>
                                                    </div>
                                                    <div class="flex items-center gap-8">
                                                        <span style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:${Utils.winRateColor(g.win_rate)};">${g.win_rate}%</span>
                                                        <span style="font-size:11px;color:var(--text-muted);">${g.wins}W ${g.losses}L</span>
                                                    </div>
                                                </div>
                                                <div class="progress-bar">
                                                    <div class="progress-fill" style="width:${g.win_rate}%;background:${Utils.winRateColor(g.win_rate)};"></div>
                                                </div>
                                            </div>
                                        `)}
                                    </div>
                                `}
                            </div>
                        `
                        : html`<${EmptyState} message="No analysis data yet"/>`
                    }
                </div>
            </div>

            <div class="card mb-12">
                <div class="section-header">
                    <div class="section-title">Factor Edge Analysis</div>
                    ${factors?.table?.length && html`<span class="tag">${factors.table.length} factors</span>`}
                </div>
                <div style="font-size:12px;color:var(--text-secondary);margin-bottom:14px;">
                    Edge = win rate when factor present minus win rate when absent. Higher = more predictive.
                </div>
                ${loading
                    ? html`<${LoadingSkeleton} rows=${3}/>`
                    : factors?.table?.length
                    ? html`
                        <div>
                            <div id="factor-bar-chart" class="mb-12"></div>
                            <div class="table-wrap" style="max-height:400px;overflow-y:auto;">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Factor</th><th>Present WR</th><th>Absent WR</th>
                                            <th>Edge</th><th>Present</th><th>Absent</th><th>Observation</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${factors.table.map(f => html`
                                            <tr key=${f.factor}>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;font-weight:700;">${f.factor.replace(/_/g, ' ')}</span></td>
                                                <td><span style="font-family:var(--font-mono);color:${f.win_rate_present != null ? Utils.winRateColor(f.win_rate_present) : 'var(--text-muted)'};">${f.win_rate_present != null ? f.win_rate_present + '%' : '--'}</span></td>
                                                <td><span style="font-family:var(--font-mono);color:var(--text-secondary);">${f.win_rate_absent != null ? f.win_rate_absent + '%' : '--'}</span></td>
                                                <td><span style="font-family:var(--font-mono);font-weight:800;color:${Utils.edgeColor(f.edge)};">${f.edge != null ? (f.edge >= 0 ? '+' : '') + f.edge + '%' : '--'}</span></td>
                                                <td><span style="font-family:var(--font-mono);color:var(--text-secondary);">${f.present_total || 0}</span></td>
                                                <td><span style="font-family:var(--font-mono);color:var(--text-secondary);">${f.absent_total || 0}</span></td>
                                                <td><span style="font-size:11px;color:${f.edge > 10 ? 'var(--green)' : f.edge > 0 ? 'var(--blue)' : f.edge > -10 ? 'var(--orange)' : 'var(--red)'};">${f.observation || '--'}</span></td>
                                            </tr>
                                        `)}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `
                    : factors?.error
                    ? html`<div class="alert alert-warning">${factors.error}</div>`
                    : html`<${EmptyState} message="No factor data yet — need closed trades with factor scores"/>`
                }
            </div>
        </div>
    `
}

function AuditPage() {
    const [logs,          setLogs]         = useState([])
    const [filtered,      setFiltered]     = useState([])
    const [loading,       setLoading]      = useState(false)
    const [limit,         setLimit]        = useState('100')
    const [filterAction,  setFilterAction] = useState('')
    const [filterSuccess, setFilterSuccess]= useState('')
    const [search,        setSearch]       = useState('')
    const [currentPage,   setCurrentPage]  = useState(1)
    const pageSize   = 30
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
    const paginated  = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.auditLog(parseInt(limit) || 100)
            setLogs(data || [])
            applyFilter(data || [], filterAction, filterSuccess, search)
        } catch(e) {
            showToast('Failed to load audit log: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    function applyFilter(l, action, success, s) {
        let result = [...(l || logs)]
        if (action)  result = result.filter(x => x.action === action)
        if (success !== '') {
            const ok = success === 'true'
            result   = result.filter(x => x.success === ok)
        }
        if (s) {
            const q = s.toLowerCase()
            result  = result.filter(x =>
                (x.detail || '').toLowerCase().includes(q) ||
                (x.action || '').toLowerCase().includes(q) ||
                (x.source || '').toLowerCase().includes(q) ||
                (x.ip     || '').toLowerCase().includes(q)
            )
        }
        setFiltered(result)
        setCurrentPage(1)
    }

    function actionColor(action) {
        if (!action) return 'var(--text-muted)'
        if (action.includes('login'))  return 'var(--blue)'
        if (action.includes('toggle')) return 'var(--orange)'
        if (action.includes('delete')) return 'var(--red)'
        if (action.includes('add'))    return 'var(--green)'
        if (action.includes('reset'))  return 'var(--orange)'
        if (action.includes('mode'))   return 'var(--purple)'
        if (action.includes('docker')) return 'var(--red)'
        return 'var(--text-secondary)'
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Audit Log</div>
                    <div class="page-subtitle">${filtered.length} entries</div>
                </div>
                <div class="flex gap-8">
                    <select class="select" style="width:100px;" value=${limit}
                        onChange=${e => { setLimit(e.target.value); load() }}>
                        <option value="50">50 rows</option>
                        <option value="100">100 rows</option>
                        <option value="200">200 rows</option>
                        <option value="500">500 rows</option>
                    </select>
                    <button class="btn btn-ghost btn-sm" onClick=${load} disabled=${loading}>
                        ${loading ? html`<${Spinner}/>` : 'Refresh'}
                    </button>
                </div>
            </div>

            <div class="card mb-12">
                <div class="filter-bar">
                    <select class="select" style="width:150px;" value=${filterAction}
                        onChange=${e => { setFilterAction(e.target.value); applyFilter(logs, e.target.value, filterSuccess, search) }}>
                        <option value="">All Actions</option>
                        <option value="dashboard_login">Login</option>
                        <option value="mode_toggle">Mode Toggle</option>
                        <option value="coin_add">Coin Add</option>
                        <option value="coin_toggle">Coin Toggle</option>
                        <option value="coin_delete">Coin Delete</option>
                        <option value="password_reset">Password Reset</option>
                        <option value="docker_purge">Docker Purge</option>
                    </select>
                    <select class="select" style="width:120px;" value=${filterSuccess}
                        onChange=${e => { setFilterSuccess(e.target.value); applyFilter(logs, filterAction, e.target.value, search) }}>
                        <option value="">All Results</option>
                        <option value="true">Success</option>
                        <option value="false">Failed</option>
                    </select>
                    <input class="input" style="width:150px;" type="text" placeholder="Search detail..."
                        value=${search}
                        onInput=${e => { setSearch(e.target.value); applyFilter(logs, filterAction, filterSuccess, e.target.value) }}/>
                    <button class="btn btn-ghost btn-sm" onClick=${() => {
                        setFilterAction(''); setFilterSuccess(''); setSearch('')
                        applyFilter(logs, '', '', '')
                    }}>Clear</button>
                    <div class="flex-1"></div>
                    <span style="font-size:11px;color:var(--text-secondary);">
                        <span style="font-family:var(--font-mono);color:var(--text-primary);">${filtered.length}</span> entries
                    </span>
                </div>
            </div>

            <div class="card">
                ${loading
                    ? html`<${LoadingSkeleton} rows=${5}/>`
                    : html`
                        <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>#</th><th>Time</th><th>Action</th>
                                        <th>Source</th><th>Detail</th><th>IP</th><th>Result</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!paginated.length
                                        ? html`<tr><td colspan="7"><${EmptyState} message="No audit entries found"/></td></tr>`
                                        : paginated.map(log => html`
                                            <tr key=${log.id}>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${log.id}</span></td>
                                                <td>
                                                    <div style="font-size:11px;color:var(--text-primary);">${Utils.fmtTimeAgo(log.timestamp)}</div>
                                                    <div style="font-size:10px;color:var(--text-muted);">${Utils.fmtTime(log.timestamp)}</div>
                                                </td>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;font-weight:700;color:${actionColor(log.action)};">${log.action}</span></td>
                                                <td><span class="tag">${log.source || '--'}</span></td>
                                                <td><span style="font-size:11px;color:var(--text-secondary);">${log.detail || '--'}</span></td>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${log.ip || '--'}</span></td>
                                                <td><span class=${'badge ' + (log.success ? 'badge-win' : 'badge-loss')}>${log.success ? '✓ OK' : '✗ FAIL'}</span></td>
                                            </tr>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                        <div class="pagination">
                            <span class="pagination-info">Page ${currentPage} of ${totalPages}</span>
                            <div class="pagination-controls">
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(p => p - 1)} disabled=${currentPage <= 1}>Prev</button>
                                <span style="padding:4px 10px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);">${currentPage} / ${totalPages}</span>
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(p => p + 1)} disabled=${currentPage >= totalPages}>Next</button>
                            </div>
                        </div>
                    `}
            </div>
        </div>
    `
}

function SettingsPage() {
    const [health,       setHealth]      = useState(null)
    const [system,       setSystem]      = useState(null)
    const [loading,      setLoading]     = useState(false)
    const [modeLoading,  setModeLoading] = useState(null)
    const [modeMsg,      setModeMsg]     = useState('')
    const [modeOk,       setModeOk]      = useState(false)
    const [actionLoading,setActionLoading]=useState(null)
    const [actionMsg,    setActionMsg]   = useState('')
    const [actionOk,     setActionOk]    = useState(false)
    const [purgeLoading, setPurgeLoading]= useState(false)
    const [purgeResult,  setPurgeResult] = useState(null)
    const mode   = useMode()

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
                    ${loading ? html`<${Spinner}/>` : 'Refresh'}
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
                        <div class=${'alert mb-12 ' + (modeOk ? 'alert-success' : 'alert-error')}>${modeMsg}</div>
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
                        <button class="btn btn-ghost" onClick=${triggerScan} disabled=${actionLoading === 'scan'}>
                            ${actionLoading === 'scan' ? html`<${Spinner}/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                                </svg>
                            `}
                            Trigger Scan
                        </button>
                        <button class="btn btn-ghost" onClick=${syncOutcomes} disabled=${actionLoading === 'sync'}>
                            ${actionLoading === 'sync' ? html`<${Spinner}/>` : html`
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
                                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                                </svg>
                            `}
                            Sync Outcomes
                        </button>
                    </div>
                    ${actionMsg && html`
                        <div class=${'alert mt-12 ' + (actionOk ? 'alert-success' : 'alert-error')} style="font-size:12px;">${actionMsg}</div>
                    `}
                </div>

                <div class="card">
                    <div class="section-title mb-12">System Status</div>
                    ${loading
                        ? html`<${LoadingSkeleton} rows=${5}/>`
                        : html`
                            <div>
                                ${[
                                    { label: 'API Status',       val: html`<span class="badge badge-online">✓ Online</span>` },
                                    { label: 'Redis',            val: html`<span class=${'badge ' + (health?.redis_connected ? 'badge-online' : 'badge-offline')}>${health?.redis_connected ? '✓ Connected' : '✗ Disconnected'}</span>` },
                                    { label: 'Trading Mode',     val: html`<span class=${'badge ' + (health?.trading_mode === 'live' ? 'badge-live' : 'badge-paper')}>${(health?.trading_mode || '--').toUpperCase()}</span>` },
                                    { label: 'Coins Active',     val: health?.coins_count || '--' },
                                    { label: 'Min Grades',       val: (health?.grades || []).join(', ') || '--' },
                                    { label: 'ML Status',        val: html`<span class=${'badge ' + (health?.ml_status?.ml_enabled ? 'badge-online' : 'badge-pending')}>${health?.ml_status?.ml_enabled ? 'Active' : 'Collecting'}</span>` },
                                    { label: 'ML Progress',      val: (health?.ml_status?.closed_trades || 0) + ' / ' + (health?.ml_status?.required || 100) },
                                    { label: 'Pending Signals',  val: health?.sync_status?.pending_signals || 0 },
                                    { label: 'Win Rate',         val: (health?.sync_status?.win_rate || 0) + '%', color: Utils.winRateColor(health?.sync_status?.win_rate || 0) },
                                    { label: 'Last Check',       val: Utils.fmtTime(health?.timestamp), small: true },
                                ].map(row => html`
                                    <div key=${row.label} class="stat-row">
                                        <span class="stat-label">${row.label}</span>
                                        ${typeof row.val === 'string' || typeof row.val === 'number'
                                            ? html`<span class="stat-value" style="font-family:var(--font-mono);${row.color ? 'color:' + row.color : ''}${row.small ? ';font-size:11px;' : ''}">${row.val}</span>`
                                            : row.val
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
                                    { label: 'RAM Usage', pct: system.ram_pct,  color: Utils.ramColor(system.ram_pct),  detail: system.ram_used_mb + 'MB / ' + system.ram_total_mb + 'MB · Free: ' + system.ram_available + 'MB' },
                                    { label: 'CPU Usage', pct: system.cpu_pct,  color: Utils.cpuColor(system.cpu_pct),  detail: 't2.small · 1 vCPU · burstable' },
                                    { label: 'Disk Usage',pct: system.disk_pct, color: Utils.diskColor(system.disk_pct),detail: system.disk_used_gb + 'GB / ' + system.disk_total_gb + 'GB' },
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
                                <span style="font-family:var(--font-mono);font-weight:700;color:var(--green);">${Utils.fmtUptime(system.uptime_secs)}</span>
                            </div>
                            ${system.containers?.length
                                ? html`
                                    <div class="mt-12">
                                        <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">Containers</div>
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
                            <div style="font-size:13px;font-weight:700;color:var(--red);">Purge Unused Docker Images</div>
                            <div style="font-size:12px;color:var(--text-secondary);margin-top:3px;">
                                Runs <span style="font-family:var(--font-mono);color:var(--text-primary);">docker system prune -f --volumes</span> on the host. Requires TOTP confirmation.
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
                                    <span style="font-family:var(--font-mono);font-weight:700;margin-left:8px;">Freed: ${purgeResult.freed_mb}MB</span>
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
                                    ${typeof row.val === 'object'
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
                                { label: 'CV AUC',      val: health?.ml_status?.cv_auc || '--', color: 'var(--green)' },
                                { label: 'Win Rate',    val: (health?.ml_status?.win_rate || 0) + '%', color: Utils.winRateColor(health?.ml_status?.win_rate || 0) },
                                { label: 'Last Trained',val: health?.ml_status?.trained_at && health.ml_status.trained_at !== '--' ? Utils.fmtTimeAgo(health.ml_status.trained_at) : '--', small: true },
                                { label: 'Message',     val: Utils.truncate(health?.ml_status?.message || '--', 50), small: true },
                            ].map(row => html`
                                <div key=${row.label} class="stat-row">
                                    <span class="stat-label">${row.label}</span>
                                    <span class="stat-value" style="font-family:var(--font-mono);${row.color ? 'color:' + row.color + ';' : ''}${row.small ? 'font-size:11px;' : ''}">${row.val}</span>
                                </div>
                            `)}
                        </div>
                    </div>
                `}
            </div>
        </div>
    `
}

function TotpModal() {
    const totp    = useTotp()
    const [code,  setCode]  = useState('')
    const [error, setError] = useState('')
    const inputRef = useRef(null)

    useEffect(() => {
        if (totp.show) {
            setCode('')
            setError('')
            setTimeout(() => inputRef.current?.focus(), 50)
        }
    }, [totp.show])

    function handleConfirm() {
        if (code.length < 6) return
        confirmTotp(code)
    }

    function handleClose() {
        closeTotp()
        setCode('')
        setError('')
    }

    if (!totp.show) return null

    return html`
        <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && handleClose()}>
            <div class="modal">
                <div class="modal-title">${totp.title || 'Confirm Action'}</div>
                <div class="modal-sub">${totp.subtitle || 'Enter your TOTP code to continue'}</div>
                ${error && html`<div class="alert alert-error">${error}</div>`}
                <label style="display:block;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
                    TOTP Code
                </label>
                <input
                    ref=${inputRef}
                    class="totp-input"
                    type="text"
                    inputmode="numeric"
                    maxlength="6"
                    value=${code}
                    placeholder="000000"
                    onInput=${e => setCode(e.target.value.replace(/\D/g, ''))}
                    onKeyDown=${e => e.key === 'Enter' && code.length === 6 && handleConfirm()}
                />
                <div class="modal-actions">
                    <button class="btn btn-ghost" onClick=${handleClose}>Cancel</button>
                    <button class="btn btn-primary" onClick=${handleConfirm} disabled=${code.length < 6}>
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    `
}

function Toast() {
    const toast = useToast()
    if (!toast.show) return null
    return html`
        <div style="position:fixed;bottom:24px;right:24px;z-index:2000;min-width:280px;max-width:380px;">
            <div class=${'alert alert-' + toast.type}>${toast.message}</div>
        </div>
    `
}

function Ticker() {
    const ticker = useTicker()
    if (!ticker.length) return null
    const items = [...ticker, ...ticker]
    return html`
        <div class="ticker-bar">
            <div class="ticker-track">
                ${items.map((item, i) => html`
                    <div key=${item.coin + '_' + i} class="ticker-item">
                        <span class="ticker-coin">${item.coin}</span>
                        <span class="ticker-price">${item.price}</span>
                        <span class="ticker-change" style="color:${item.change_color};">${item.change}</span>
                    </div>
                `)}
            </div>
        </div>
    `
}

function Topbar({ page }) {
    const wsState  = useWsState()
    const mode     = useMode()
    const nextScan = useNextScan()

    const titles = {
        overview:  'Overview',
        signals:   'Signals',
        freqtrade: 'Freqtrade',
        coins:     'Coin Universe',
        backtest:  'Backtest',
        analysis:  'Analysis',
        audit:     'Audit Log',
        settings:  'Settings',
    }

    return html`
        <header class="topbar">
            <div class="topbar-left">
                <span class="topbar-title">${titles[page] || ''}</span>
                <div class="topbar-divider"></div>
                <div class=${'mode-indicator ' + mode}>
                    <div class="live-dot" style=${mode === 'live' ? 'background:var(--red)' : ''}></div>
                    <span>${mode.toUpperCase()}</span>
                </div>
            </div>
            <div class="topbar-right">
                <div class="next-scan-badge">
                    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <span>Next scan</span>
                    <span>${nextScan}</span>
                </div>
                <div class="topbar-divider"></div>
                <div class="ws-status-bar">
                    <div class=${'ws-dot ' + (wsState === 'connected' ? '' : wsState === 'connecting' ? 'connecting' : 'disconnected')}></div>
                    <span>${wsState === 'connected' ? 'Live' : wsState === 'connecting' ? 'Connecting' : 'Offline'}</span>
                </div>
                <div class="topbar-divider"></div>
                <button class="btn btn-ghost btn-sm" onClick=${logout}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <polyline points="16 17 21 12 16 7"/>
                        <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                    Logout
                </button>
            </div>
        </header>
    `
}

function Sidebar({ page, expanded, onToggle }) {
    const navItems = [
        {
            section: 'Trading',
            items: [
                { id: 'overview',  label: 'Overview',   icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>` },
                { id: 'signals',   label: 'Signals',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
                { id: 'freqtrade', label: 'Freqtrade',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>` },
            ]
        },
        {
            section: 'Research',
            items: [
                { id: 'coins',    label: 'Coins',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>` },
                { id: 'backtest', label: 'Backtest', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>` },
                { id: 'analysis', label: 'Analysis', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>` },
            ]
        },
        {
            section: 'System',
            items: [
                { id: 'audit',    label: 'Audit Log', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>` },
                { id: 'settings', label: 'Settings',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>` },
            ]
        }
    ]

    return html`
        <aside class=${'sidebar ' + (expanded ? 'expanded' : '')}>
            <div class="sidebar-logo">
                <svg class="sidebar-logo-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
                    <rect width="32" height="32" rx="8" fill="#0e0e1a"/>
                    <polygon points="18,3 8,18 15,18 14,29 24,14 17,14" fill="#00e5b8" stroke="#00e5b8" stroke-width="0.5" stroke-linejoin="round"/>
                </svg>
                <div class="sidebar-logo-text">
                    <div class="sidebar-logo-title">Signal Engine</div>
                    <div class="sidebar-logo-sub">v5.0.0</div>
                </div>
            </div>
            <nav class="sidebar-nav">
                ${navItems.map(section => html`
                    <div key=${section.section}>
                        <div class="nav-section-label">${section.section}</div>
                        ${section.items.map(item => html`
                            <div key=${item.id}
                                class=${'nav-item ' + (page === item.id ? 'active' : '')}
                                onClick=${() => navigate(item.id)}
                                tabindex="0"
                                onKeyDown=${e => (e.key === 'Enter' || e.key === ' ') && navigate(item.id)}>
                                ${item.icon}
                                <span class="nav-item-label">${item.label}</span>
                                <span class="nav-tooltip">${item.label}</span>
                            </div>
                        `)}
                    </div>
                `)}
            </nav>
            <button class="sidebar-toggle" onClick=${onToggle}>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${expanded
                        ? html`<polyline points="15 18 9 12 15 6"/>`
                        : html`<polyline points="9 18 15 12 9 6"/>`
                    }
                </svg>
            </button>
        </aside>
    `
}

function BottomNav({ page }) {
    const items = [
        { id: 'overview',  label: 'Overview',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>` },
        { id: 'signals',   label: 'Signals',   icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
        { id: 'freqtrade', label: 'Trades',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>` },
        { id: 'coins',     label: 'Coins',     icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>` },
        { id: 'settings',  label: 'Settings',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>` },
    ]

    return html`
        <nav class="bottom-nav">
            ${items.map(item => html`
                <button key=${item.id}
                    class=${'bottom-nav-item ' + (page === item.id ? 'active' : '')}
                    onClick=${() => navigate(item.id)}>
                    ${item.icon}
                    <span>${item.label}</span>
                </button>
            `)}
        </nav>
    `
}

function App() {
    const page                      = usePage()
    const [expanded, setExpanded]   = useState(false)
    const [ready,    setReady]      = useState(false)

    useEffect(() => {
        init().then(ok => {
            if (ok) setReady(true)
        })
    }, [])

    if (!ready) return html`
        <div style="display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;">
            <div class="spinner" style="width:24px;height:24px;border-width:3px;"></div>
            <span style="color:var(--text-muted);font-size:13px;">Loading Signal Engine...</span>
        </div>
    `

    const pages = {
        overview:  html`<${OverviewPage}/>`,
        signals:   html`<${SignalsPage}/>`,
        freqtrade: html`<${FreqtradePage}/>`,
        coins:     html`<${CoinsPage}/>`,
        backtest:  html`<${BacktestPage}/>`,
        analysis:  html`<${AnalysisPage}/>`,
        audit:     html`<${AuditPage}/>`,
        settings:  html`<${SettingsPage}/>`,
    }

    return html`
        <div class="app-layout">
            <${Sidebar}
                page=${page}
                expanded=${expanded}
                onToggle=${() => setExpanded(p => !p)}
            />
            <div class="main-area">
                <${Topbar} page=${page}/>
                <${Ticker}/>
                <main class="page-content">
                    ${pages[page] || pages.overview}
                </main>
            </div>
            <${BottomNav} page=${page}/>
            <${TotpModal}/>
            <${Toast}/>
        </div>
    `
}

render(html`<${App}/>`, document.getElementById('root'))