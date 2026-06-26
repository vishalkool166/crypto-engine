import { h, Fragment } from '/js/preact.min.js'
import { useState, useEffect, useRef } from '/js/preact-hooks.min.js'
import { html, GradeBadge, DirBadge, OutcomeBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton, TradesBanner, CoinDetailModal } from '/js/components.js'
import { useDashboard, useFtUpdate, showToast } from '/js/store.js'

export function OverviewPage() {
    const data          = useDashboard()
    const ftData        = useFtUpdate()
    const [scanning,    setScanning]    = useState(false)
    const [histLoading, setHistLoading] = useState(false)
    const [history,     setHistory]     = useState([])
    const [activeTrades,setActiveTrades]= useState([])
    const [equityRange, setEquityRange] = useState('all')
    const [selectedCoin,setSelectedCoin]= useState(null)
    const chartsDrawn   = useRef(false)
    const prevCurveKey  = useRef(null)

    const summary = data.summary     || {}
    const perf    = data.performance || {}
    const queue   = data.signals?.queue || []
    const radar   = data.signals?.radar || []

    useEffect(() => {
        if (data.history) setHistory(data.history)
    }, [data.history])

    useEffect(() => {
        fetchActiveTrades()
    }, [])

    useEffect(() => {
        if (ftData.trades?.length) setActiveTrades(ftData.trades)
    }, [ftData.trades])

    async function fetchActiveTrades() {
        try {
            const res  = await fetch('/api/ft/summary', { credentials: 'include' })
            if (!res.ok) return
            const data = await res.json().catch(() => null)
            if (data && Array.isArray(data.status)) {
                setActiveTrades(data.status)
            }
        } catch(e) {}
    }

    useEffect(() => {
        if (!perf.equity_curve?.length) return
        const filtered  = filterEquityCurve(perf.equity_curve, equityRange)
        if (!filtered.length) return
        const curveKey  = equityRange + '_' + filtered.length + '_' + (filtered[filtered.length - 1]?.equity || 0)
        if (prevCurveKey.current === curveKey && chartsDrawn.current) return
        prevCurveKey.current = curveKey
        setTimeout(() => {
            const el = document.getElementById('overview-equity')
            if (el && el.tagName === 'CANVAS') {
                Charts.destroy('overview-equity')
                Charts.equityFromCurve('overview-equity', filtered)
            }
            chartsDrawn.current = true
        }, 100)
    }, [perf.equity_curve, equityRange])

    useEffect(() => {
        return () => {
            Charts.destroy('overview-equity')
            chartsDrawn.current  = false
            prevCurveKey.current = null
        }
    }, [])

    function filterEquityCurve(curve, range) {
        if (!curve?.length) return []
        if (range === 'all') return curve
        const now  = new Date()
        const days = range === '7d' ? 7 : range === '30d' ? 30 : 90
        const cutoff = new Date(now.getTime() - days * 86400000)
        return curve.filter(c => {
            if (!c.date) return false
            return new Date(c.date) >= cutoff
        })
    }

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
        } catch(e) {
        } finally {
            setHistLoading(false)
        }
    }

    const equityCurveFiltered = filterEquityCurve(perf.equity_curve || [], equityRange)

    return html`
        <div>
            <${TradesBanner} trades=${activeTrades}/>

            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Overview</div>
                    <div class="page-subtitle">Updated ${Utils.fmtTimeAgo(data.timestamp)}</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${triggerScan} disabled=${scanning}
                    aria-label="Trigger market scan">
                    ${scanning ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                            <circle cx="11" cy="11" r="8"/>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                        </svg>
                    `}
                    ${scanning ? 'Scanning...' : 'Scan Now'}
                </button>
            </div>

            <div class="grid-4 mb-12">
                <div class="stat-card stat-card-green" role="region" aria-label="Today PnL">
                    <div class="card-title">Today PnL</div>
                    <div class="card-value" style="color:${summary.today_pnl_color || 'var(--text-muted)'};"
                        aria-live="polite">
                        ${summary.today_pnl || '--'}
                    </div>
                    <div class="card-sub">${summary.today_trades || 0} trades today</div>
                </div>
                <div class="stat-card stat-card-blue" role="region" aria-label="Win Rate">
                    <div class="card-title">Win Rate</div>
                    <div class="card-value" style="color:${perf.win_rate_color || 'var(--text-muted)'};"
                        aria-live="polite">
                        ${perf.win_rate || '--'}
                    </div>
                    <div class="card-sub">${perf.win_rate_sub || '0 closed'}</div>
                </div>
                <div class="stat-card stat-card-purple" role="region" aria-label="Coins scanning">
                    <div class="card-title">Scanning</div>
                    <div class="card-value" style="color:var(--purple);" aria-live="polite">
                        ${summary.coins_count || '--'}
                    </div>
                    <div class="card-sub">${summary.tradeable_count || 0} tradeable now</div>
                </div>
                <div class="stat-card stat-card-gold" role="region" aria-label="Total PnL">
                    <div class="card-title">Total PnL</div>
                    <div class="card-value" style="color:${perf.pnl_color || 'var(--text-muted)'};"
                        aria-live="polite">
                        ${perf.total_pnl || '--'}
                    </div>
                    <div class="card-sub">${perf.pnl_sub || '0W · 0L'}</div>
                </div>
            </div>

            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Signal Queue</div>
                        <span class="tag" aria-label=${queue.length + ' signals in queue'}>
                            ${queue.length} signals
                        </span>
                    </div>
                    ${!queue.length
                        ? html`<${EmptyState} message="No tradeable signals — run scan"/>`
                        : html`
                            <div class="signal-grid">
                                ${queue.map(sig => html`
                                    <div key=${sig.coin}
                                        class=${'signal-queue-card grade-' + (sig.grade === 'A+' ? 'aplus' : (sig.grade || '').toLowerCase())}
                                        role="article"
                                        aria-label=${sig.coin + ' ' + sig.direction + ' Grade ' + sig.grade}>
                                        <div class="flex justify-between items-center mb-8">
                                            <div class="flex items-center gap-8">
                                                <span style="font-family:var(--font-mono);font-size:13px;font-weight:800;">
                                                    ${sig.coin}
                                                </span>
                                                <${GradeBadge} grade=${sig.grade}/>
                                            </div>
                                            <${DirBadge} dir=${sig.direction}/>
                                        </div>
                                        <div style="font-family:var(--font-mono);font-size:18px;font-weight:800;color:${Utils.scoreBarColor(sig.score)};margin-bottom:8px;">
                                            ${sig.score}/100
                                        </div>
                                        <div class="trade-card-levels" style="grid-template-columns:repeat(3,1fr);">
                                            <div class="level-item">
                                                <div class="level-label">Entry</div>
                                                <div class="level-value">${sig.entry || '--'}</div>
                                            </div>
                                            <div class="level-item">
                                                <div class="level-label">SL</div>
                                                <div class="level-value" style="color:var(--red);">${sig.sl || '--'}</div>
                                            </div>
                                            <div class="level-item">
                                                <div class="level-label">TP</div>
                                                <div class="level-value" style="color:var(--green);">${sig.tp1 || '--'}</div>
                                            </div>
                                        </div>
                                        <div class="flex justify-between items-center" style="font-size:10px;color:var(--text-muted);margin-top:6px;">
                                            <span>R:R <span style="font-family:var(--font-mono);color:var(--text-primary);font-weight:600;">1:${sig.actual_rr || '--'}</span></span>
                                            <span style="font-family:var(--font-mono);">${sig.regime || '--'}</span>
                                        </div>
                                        ${sig.stake && html`
                                            <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">
                                                Stake <span style="font-family:var(--font-mono);color:var(--blue);font-weight:600;">$${parseFloat(sig.stake).toFixed(2)}</span>
                                                <span style="font-family:var(--font-mono);color:var(--text-muted);">${sig.leverage}x</span>
                                            </div>
                                        `}
                                    </div>
                                `)}
                            </div>
                        `
                    }
                </div>

                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Coin Radar</div>
                        <span class="tag">${radar.length} coins</span>
                    </div>
                    <div class="table-wrap" style="max-height:400px;overflow-y:auto;">
                        <table aria-label="Coin radar">
                            <thead>
                                <tr>
                                    <th scope="col">Coin</th>
                                    <th scope="col">Grade</th>
                                    <th scope="col">Score</th>
                                    <th scope="col">Dir</th>
                                    <th scope="col">Price</th>
                                    <th scope="col">24h</th>
                                    <th scope="col">Regime</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${!radar.length
                                    ? html`<tr><td colspan="7"><${EmptyState} message="Run scan to populate radar"/></td></tr>`
                                    : radar.map(r => html`
                                        <tr key=${r.coin}
                                            style="cursor:pointer;"
                                            onClick=${() => setSelectedCoin(r.coin)}
                                            tabindex="0"
                                            role="button"
                                            aria-label=${'View details for ' + r.coin}
                                            onKeyDown=${e => (e.key === 'Enter' || e.key === ' ') && setSelectedCoin(r.coin)}>
                                            <td>
                                                <span style="font-family:var(--font-mono);font-weight:700;color:var(--blue);">
                                                    ${r.coin}
                                                </span>
                                            </td>
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
                        { label: 'A+', wr: perf.aplus_wr, bar: perf.aplus_bar, detail: perf.aplus_detail, color: 'var(--gold)'   },
                        { label: 'A',  wr: perf.a_wr,     bar: perf.a_bar,     detail: perf.a_detail,     color: 'var(--blue)'   },
                        { label: 'B',  wr: perf.b_wr,     bar: perf.b_bar,     detail: perf.b_detail,     color: 'var(--orange)' },
                    ].map(g => html`
                        <div key=${g.label} style="margin-bottom:10px;">
                            <div class="flex justify-between items-center" style="font-size:11px;margin-bottom:5px;">
                                <span style="color:${g.color};font-weight:700;">
                                    ${g.label} <span style="font-family:var(--font-mono);">${g.wr}</span>
                                </span>
                                <span style="font-size:10px;color:var(--text-muted);">${g.detail}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width:${g.bar || 0}%;background:${g.color};"></div>
                            </div>
                        </div>
                    `)}
                </div>

                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Equity Curve</div>
                        <div class="flex items-center gap-6">
                            <span class="tag">${equityCurveFiltered.length} trades</span>
                            <select class="select" style="width:80px;font-size:11px;padding:3px 24px 3px 8px;"
                                value=${equityRange}
                                onChange=${e => {
                                    chartsDrawn.current = false
                                    setEquityRange(e.target.value)
                                }}
                                aria-label="Equity curve date range">
                                <option value="7d">7d</option>
                                <option value="30d">30d</option>
                                <option value="90d">90d</option>
                                <option value="all">All</option>
                            </select>
                        </div>
                    </div>
                    ${!equityCurveFiltered.length
                        ? html`<${EmptyState} message="No closed trades in this range"/>`
                        : html`
                            <div style="position:relative;height:200px;">
                                <canvas id="overview-equity"></canvas>
                            </div>
                        `
                    }
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <div class="section-title">Recent Signals</div>
                    <button class="btn btn-ghost btn-sm" onClick=${loadHistory}
                        disabled=${histLoading} aria-label="Refresh signal history">
                        ${histLoading ? html`<${Spinner}/>` : 'Refresh'}
                    </button>
                </div>
                <div class="table-wrap">
                    <table aria-label="Recent closed signals">
                        <thead>
                            <tr>
                                <th scope="col">#</th>
                                <th scope="col">Time</th>
                                <th scope="col">Coin</th>
                                <th scope="col">Direction</th>
                                <th scope="col">Grade</th>
                                <th scope="col">Score</th>
                                <th scope="col">Entry</th>
                                <th scope="col">Exit</th>
                                <th scope="col">PnL</th>
                                <th scope="col">Result</th>
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

            ${selectedCoin && html`
                <${CoinDetailModal}
                    coin=${selectedCoin}
                    onClose=${() => setSelectedCoin(null)}
                />
            `}
        </div>
    `
}