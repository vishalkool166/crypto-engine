var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { useDashboard, useFtUpdate, showToast } = Store
var { GradeBadge, DirBadge, OutcomeBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton, TradeProgressBar, HealthBar, CoinDetailModal } = SE

function OverviewPage() {
    const data           = useDashboard()
    const ftData         = useFtUpdate()
    const [scanning,     setScanning]     = useState(false)
    const [history,      setHistory]      = useState([])
    const [activeTrades, setActiveTrades] = useState([])
    const [selectedCoin, setSelectedCoin] = useState(null)
    const [equityRange,  setEquityRange]  = useState('all')
    const chartDrawn     = useRef(false)
    const prevCurveKey   = useRef(null)

    const summary = data.summary     || {}
    const perf    = data.performance || {}
    const queue   = data.signals?.queue || []
    const radar   = data.signals?.radar || []

    useEffect(() => {
        if (data.history) setHistory(data.history)
    }, [data.history])

    useEffect(() => { fetchActiveTrades() }, [])

    useEffect(() => {
        if (ftData.trades?.length) setActiveTrades(ftData.trades)
    }, [ftData.trades])

    useEffect(() => {
        if (!perf.equity_curve?.length) return
        const filtered = filterCurve(perf.equity_curve, equityRange)
        if (!filtered.length) return
        const curveKey = equityRange + '_' + filtered.length + '_' + (filtered[filtered.length - 1]?.equity || 0)
        if (prevCurveKey.current === curveKey && chartDrawn.current) return
        prevCurveKey.current = curveKey
        setTimeout(() => {
            Charts.destroy('overview-equity')
            const el = document.getElementById('overview-equity')
            if (el && el.tagName === 'CANVAS') {
                Charts.equityFromCurve('overview-equity', filtered)
                chartDrawn.current = true
            }
        }, 100)
    }, [perf.equity_curve, equityRange])

    useEffect(() => {
        return () => {
            Charts.destroy('overview-equity')
            chartDrawn.current   = false
            prevCurveKey.current = null
        }
    }, [])

    async function fetchActiveTrades() {
        try {
            const res = await fetch('/api/ft/summary', { credentials: 'include' })
            if (!res.ok) return
            const d = await res.json().catch(() => null)
            if (d && Array.isArray(d.status)) setActiveTrades(d.status)
        } catch(e) {}
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

    function filterCurve(curve, range) {
        if (!curve?.length) return []
        if (range === 'all') return curve
        const days   = range === '7d' ? 7 : range === '30d' ? 30 : 90
        const cutoff = new Date(Date.now() - days * 86400000)
        return curve.filter(c => c.date && new Date(c.date) >= cutoff)
    }

    const equityCurveFiltered = filterCurve(perf.equity_curve || [], equityRange)

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Overview</div>
                    <div class="page-subtitle">Updated ${Utils.fmtTimeAgo(data.timestamp)}</div>
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

            <div class="grid-4 mb-24">
                <div class="stat-card">
                    <div class="stat-card-label">Today PnL</div>
                    <div class="stat-card-value" style="color:${Utils.pnlColor(summary.today_pnl_pos)};">
                        ${Utils.fmtPnl(summary.today_pnl, summary.today_pnl_pos)}
                    </div>
                    <div class="stat-card-sub">${summary.today_trades || 0} trades today</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-label">Win Rate</div>
                    <div class="stat-card-value" style="color:${Utils.winRateColor(summary.win_rate)};">
                        ${summary.win_rate != null ? summary.win_rate + '%' : '--'}
                    </div>
                    <div class="stat-card-sub">${perf.closed || 0} closed trades</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-label">Scanning</div>
                    <div class="stat-card-value" style="color:var(--blue);">
                        ${summary.coins_count || '--'}
                    </div>
                    <div class="stat-card-sub">${summary.tradeable_count || 0} tradeable now</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-label">Total PnL</div>
                    <div class="stat-card-value" style="color:${Utils.pnlColor(perf.total_pnl_pos)};">
                        ${Utils.fmtPnl(perf.total_pnl, perf.total_pnl_pos)}
                    </div>
                    <div class="stat-card-sub">${perf.wins || 0}W · ${perf.losses || 0}L</div>
                </div>
            </div>

            <div class="grid-2 mb-24">
                <div class="card">
                    <div class="section-header">
                        <div>
                            <div class="section-title">Signal Queue</div>
                            <div class="section-subtitle">${queue.length} tradeable signals</div>
                        </div>
                        <span class="tag">${queue.length}</span>
                    </div>
                    <div style="overflow-y:auto;max-height:480px;">
                        ${!queue.length
                            ? html`<${EmptyState} message="No tradeable signals — run scan"/>`
                            : queue.map(sig => html`
                                <div key=${sig.coin}
                                    class=${'signal-queue-card grade-' + (sig.grade === 'A+' ? 'aplus' : (sig.grade || '').toLowerCase())}>
                                    <div class="flex justify-between items-center mb-12">
                                        <div class="flex items-center gap-8">
                                            <span style="font-family:var(--font-mono);font-size:15px;font-weight:800;">${sig.coin}USDT</span>
                                            <${GradeBadge} grade=${sig.grade}/>
                                            <${DirBadge} dir=${sig.direction}/>
                                        </div>
                                        <span style="font-family:var(--font-mono);font-size:15px;font-weight:800;color:${Utils.scoreColor(sig.score)};">
                                            ${sig.score}/100
                                        </span>
                                    </div>
                                    <div class="trade-card-levels">
                                        <div class="level-item">
                                            <div class="level-label">Entry</div>
                                            <div class="level-value">${Utils.fmtPrice(sig.entry)}</div>
                                        </div>
                                        <div class="level-item">
                                            <div class="level-label">Stop Loss</div>
                                            <div class="level-value" style="color:var(--red);">${Utils.fmtPrice(sig.sl)}</div>
                                        </div>
                                        <div class="level-item">
                                            <div class="level-label">Take Profit</div>
                                            <div class="level-value" style="color:var(--green);">${Utils.fmtPrice(sig.tp1)}</div>
                                        </div>
                                    </div>
                                    <div class="flex justify-between items-center" style="font-size:11px;color:var(--text-muted);margin-top:8px;">
                                        <span>R:R <span style="font-family:var(--font-mono);color:var(--text-primary);font-weight:600;">1:${sig.actual_rr || '--'}</span></span>
                                        <span style="font-family:var(--font-mono);">${sig.regime || '--'}</span>
                                        <span>${sig.session || '--'}</span>
                                    </div>
                                    ${sig.stake && html`
                                        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
                                            Stake <span style="font-family:var(--font-mono);color:var(--blue);font-weight:600;">$${parseFloat(sig.stake).toFixed(2)}</span>
                                            <span style="font-family:var(--font-mono);color:var(--text-muted);margin-left:4px;">${sig.leverage}x</span>
                                        </div>
                                    `}
                                </div>
                            `)
                        }
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <div>
                            <div class="section-title">Active Trades</div>
                            <div class="section-subtitle">${activeTrades.length} open</div>
                        </div>
                        <span class="tag">${activeTrades.length}</span>
                    </div>
                    <div style="overflow-y:auto;max-height:480px;">
                        ${!activeTrades.length
                            ? html`<${EmptyState} message="No open trades"/>`
                            : activeTrades.map(trade => {
                                const pair   = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
                                const dir    = trade.is_short ? 'SHORT' : 'LONG'
                                const pnl    = parseFloat(trade.profit_abs || 0)
                                const pnlPos = pnl >= 0
                                return html`
                                    <div key=${trade.trade_id} class="trade-card">
                                        <div class="trade-card-header">
                                            <div class="flex items-center gap-8">
                                                <span style="font-family:var(--font-mono);font-size:14px;font-weight:800;">${pair}</span>
                                                <${DirBadge} dir=${dir}/>
                                                <span class="tag">#${trade.trade_id}</span>
                                            </div>
                                            <div style="text-align:right;">
                                                <div style="font-family:var(--font-mono);font-size:15px;font-weight:800;color:${Utils.pnlColor(pnlPos)};">
                                                    ${Utils.fmtPnl(pnl, pnlPos)}
                                                </div>
                                                <div style="font-family:var(--font-mono);font-size:11px;color:${Utils.pnlColor((trade.profit_ratio || 0) >= 0)};">
                                                    ${Utils.fmtPct((trade.profit_ratio || 0) * 100)}
                                                </div>
                                            </div>
                                        </div>
                                        <div class="trade-card-levels">
                                            <div class="level-item">
                                                <div class="level-label">Entry</div>
                                                <div class="level-value">${Utils.fmtPrice(trade.open_rate)}</div>
                                            </div>
                                            <div class="level-item">
                                                <div class="level-label">Current</div>
                                                <div class="level-value" style="color:${Utils.pnlColor(pnlPos)};">${Utils.fmtPrice(trade.current_rate)}</div>
                                            </div>
                                            <div class="level-item">
                                                <div class="level-label">Open</div>
                                                <div class="level-value">${Utils.fmtDuration(trade.open_date)}</div>
                                            </div>
                                            <div class="level-item">
                                                <div class="level-label">Stake</div>
                                                <div class="level-value">$${parseFloat(trade.stake_amount || 0).toFixed(2)}</div>
                                            </div>
                                            <div class="level-item">
                                                <div class="level-label">Leverage</div>
                                                <div class="level-value" style="color:var(--blue);">${trade.leverage || '--'}x</div>
                                            </div>
                                            <div class="level-item">
                                                <div class="level-label">Tag</div>
                                                <div class="level-value" style="font-size:10px;color:var(--text-muted);">${trade.enter_tag || '--'}</div>
                                            </div>
                                        </div>
                                        <${TradeProgressBar} trade=${trade}/>
                                        <${HealthBar} health=${trade.health}/>
                                    </div>
                                `
                            })
                        }
                    </div>
                </div>
            </div>

            <div class="grid-2-1 mb-24">
                <div class="card">
                    <div class="section-header">
                        <div>
                            <div class="section-title">Coin Radar</div>
                            <div class="section-subtitle">${radar.length} coins scanned</div>
                        </div>
                        <span class="tag">${radar.length}</span>
                    </div>
                    <div class="table-wrap" style="max-height:360px;overflow-y:auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Coin</th><th>Grade</th><th>Score</th>
                                    <th>Dir</th><th>Price</th><th>24h</th><th>Regime</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${!radar.length
                                    ? html`<tr><td colspan="7"><${EmptyState} message="Run scan to populate"/></td></tr>`
                                    : radar.map(r => html`
                                        <tr key=${r.coin} style="cursor:pointer;" onClick=${() => setSelectedCoin(r.coin)}>
                                            <td><span style="font-family:var(--font-mono);font-weight:700;color:var(--blue);">${r.coin}</span></td>
                                            <td><${GradeBadge} grade=${r.grade}/></td>
                                            <td><${ScoreBar} score=${r.score}/></td>
                                            <td><${DirBadge} dir=${r.direction}/></td>
                                            <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(r.price)}</span></td>
                                            <td><span style="font-family:var(--font-mono);color:${Utils.changeColor(r.change)};">${Utils.fmtPct(r.change)}</span></td>
                                            <td><span style="font-size:11px;color:var(--text-muted);">${r.regime || '--'}</span></td>
                                        </tr>
                                    `)
                                }
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="card">
                    <div class="section-title mb-16">Performance</div>
                    <div class="stat-row">
                        <span class="stat-label">Profit Factor</span>
                        <span class="stat-value">${perf.profit_factor || '--'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Best Trade</span>
                        <span class="stat-value" style="color:var(--green);">${Utils.fmtPnl(perf.best_trade, true)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Max Drawdown</span>
                        <span class="stat-value" style="color:${perf.max_drawdown > 15 ? 'var(--red)' : perf.max_drawdown > 8 ? 'var(--orange)' : 'var(--green)'};">
                            ${perf.max_drawdown != null ? perf.max_drawdown + '%' : '--'}
                        </span>
                    </div>
                    <div class="divider"></div>
                    ${[
                        { label: 'A+', data: perf.aplus, color: 'var(--gold)'   },
                        { label: 'A',  data: perf.a,     color: 'var(--blue)'   },
                        { label: 'B',  data: perf.b,     color: 'var(--orange)' },
                    ].map(g => g.data && html`
                        <div key=${g.label} style="margin-bottom:12px;">
                            <div class="flex justify-between items-center" style="margin-bottom:5px;">
                                <span style="color:${g.color};font-weight:700;font-size:13px;">
                                    Grade ${g.label}
                                    <span style="font-family:var(--font-mono);margin-left:6px;">${g.data.win_rate}%</span>
                                </span>
                                <span style="font-size:11px;color:var(--text-muted);">
                                    ${g.data.wins}W · ${g.data.total - g.data.wins}L · ${Utils.fmtPnl(g.data.pnl, g.data.pnl >= 0)}
                                </span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width:${g.data.win_rate}%;background:${g.color};"></div>
                            </div>
                        </div>
                    `)}
                </div>
            </div>

            <div class="card mb-24">
                <div class="section-header">
                    <div>
                        <div class="section-title">Equity Curve</div>
                        <div class="section-subtitle">${equityCurveFiltered.length} trades</div>
                    </div>
                    <select class="select" style="width:80px;font-size:12px;"
                        value=${equityRange}
                        onChange=${e => { chartDrawn.current = false; setEquityRange(e.target.value) }}>
                        <option value="7d">7d</option>
                        <option value="30d">30d</option>
                        <option value="90d">90d</option>
                        <option value="all">All</option>
                    </select>
                </div>
                ${!equityCurveFiltered.length
                    ? html`<${EmptyState} message="No closed trades in this range"/>`
                    : html`<div style="position:relative;height:200px;"><canvas id="overview-equity"></canvas></div>`
                }
            </div>

            <div class="card">
                <div class="section-header">
                    <div class="section-title">Recent Signals</div>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th><th>Time</th><th>Coin</th><th>Dir</th>
                                <th>Grade</th><th>Score</th><th>Entry</th>
                                <th>Exit</th><th>PnL</th><th>Result</th>
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
                                        <td><span style="font-family:var(--font-mono);font-weight:700;color:${Utils.pnlColor(s.pnl_pos)};">${Utils.fmtPnl(s.pnl, s.pnl_pos)}</span></td>
                                        <td><${OutcomeBadge} outcome=${s.outcome}/></td>
                                    </tr>
                                `)
                            }
                        </tbody>
                    </table>
                </div>
            </div>

            ${selectedCoin && html`
                <${CoinDetailModal} coin=${selectedCoin} onClose=${() => setSelectedCoin(null)}/>
            `}
        </div>
    `
}