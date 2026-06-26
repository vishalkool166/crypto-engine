import { h, Fragment } from '/js/preact.min.js'
import { useState, useEffect, useRef } from '/js/preact-hooks.min.js'
import { html, GradeBadge, DirBadge, OutcomeBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton, TradesBanner } from '/js/components.js'
import { useDashboard, useFtUpdate, showToast } from '/js/store.js'

export function OverviewPage() {
    const data         = useDashboard()
    const ftData       = useFtUpdate()
    const [scanning,   setScanning]   = useState(false)
    const [histLoading,setHistLoading]= useState(false)
    const [history,    setHistory]    = useState([])
    const chartsDrawn  = useRef(false)
    const prevCurve    = useRef(null)

    const summary = data.summary     || {}
    const perf    = data.performance || {}
    const queue   = data.signals?.queue || []
    const radar   = data.signals?.radar || []

    useEffect(() => {
        if (data.history) setHistory(data.history)
    }, [data.history])

    useEffect(() => {
        if (!perf.equity_curve?.length) return
        const curveKey = perf.equity_curve.length + '_' + (perf.equity_curve[perf.equity_curve.length - 1]?.equity || 0)
        if (prevCurve.current === curveKey && chartsDrawn.current) return
        prevCurve.current = curveKey
        setTimeout(() => {
            const el = document.getElementById('overview-equity')
            if (el && el.tagName === 'CANVAS') {
                Charts.equityFromCurve('overview-equity', perf.equity_curve)
            }
            const hasGrade = (parseFloat(perf.aplus_bar) || 0) > 0
                          || (parseFloat(perf.a_bar)     || 0) > 0
                          || (parseFloat(perf.b_bar)     || 0) > 0
            if (hasGrade) {
                const donutEl = document.getElementById('overview-donut')
                if (donutEl && donutEl.tagName === 'CANVAS') {
                    Charts.gradeDonut('overview-donut', {
                        'A+': { total: parseFloat(perf.aplus_bar) || 0 },
                        'A':  { total: parseFloat(perf.a_bar)     || 0 },
                        'B':  { total: parseFloat(perf.b_bar)     || 0 },
                    })
                }
            }
            chartsDrawn.current = true
        }, 100)
    }, [perf.equity_curve])

    useEffect(() => {
        return () => {
            Charts.destroy('overview-equity')
            Charts.destroy('overview-donut')
            chartsDrawn.current = false
            prevCurve.current   = null
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
        } catch(e) {
        } finally {
            setHistLoading(false)
        }
    }

    return html`
        <div>
            <${TradesBanner} trades=${ftData.trades}/>

            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Overview</div>
                    <div class="page-subtitle">Updated ${Utils.fmtTimeAgo(data.timestamp)}</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${triggerScan} disabled=${scanning}>
                    ${scanning ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="11" cy="11" r="8"/>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
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
                                class=${'signal-queue-card grade-' + (sig.grade === 'A+' ? 'aplus' : (sig.grade || '').toLowerCase())}>
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
                                        <span>
                                            Stake <span style="font-family:var(--font-mono);color:var(--blue);font-weight:600;">$${parseFloat(sig.stake).toFixed(2)}</span>
                                            <span style="font-family:var(--font-mono);color:var(--text-muted);">${sig.leverage}x</span>
                                        </span>
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
                    <div class="divider"></div>
                    <div style="position:relative;height:180px;">
                        <canvas id="overview-donut"></canvas>
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <div class="section-title">Equity Curve</div>
                        <span class="tag">${perf.equity_curve?.length || 0} trades</span>
                    </div>
                    <div style="position:relative;height:200px;">
                        <canvas id="overview-equity"></canvas>
                    </div>
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