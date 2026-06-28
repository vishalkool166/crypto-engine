var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { useDashboard, showToast } = Store
var { GradeBadge, DirBadge, OutcomeBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton, Panel, InfoRow } = SE

function PerformancePage() {
    const data                           = useDashboard()
    const [signals,     setSignals]      = useState([])
    const [sigLoading,  setSigLoading]   = useState(false)
    const [selectedSig, setSelectedSig]  = useState(null)
    const [filters,     setFilters]      = useState({ grade: '', outcome: '', direction: '', coin: '', limit: '100' })
    const [currentPage, setCurrentPage]  = useState(1)
    const [showSignals, setShowSignals]  = useState(false)
    const [equityRange, setEquityRange]  = useState('all')
    const chartDrawn                     = useRef(false)
    const prevCurveKey                   = useRef(null)
    const pageSize                       = 30

    const perf    = data.performance || {}
    const summary = data.summary     || {}

    const totalPages = Math.max(1, Math.ceil(signals.length / pageSize))
    const paginated  = signals.slice((currentPage - 1) * pageSize, currentPage * pageSize)

    useEffect(() => {
        return () => {
            Charts.destroy('perf-equity-chart')
            Charts.destroy('perf-grade-donut')
            Charts.destroy('perf-pnl-bar')
            chartDrawn.current   = false
            prevCurveKey.current = null
        }
    }, [])

    useEffect(() => {
        if (!perf.equity_curve?.length) return
        const filtered = filterCurve(perf.equity_curve, equityRange)
        if (!filtered.length) return
        const key = equityRange + '_' + filtered.length + '_' + (filtered[filtered.length - 1]?.equity || 0)
        if (prevCurveKey.current === key && chartDrawn.current) return
        prevCurveKey.current = key
        setTimeout(() => {
            Charts.destroy('perf-equity-chart')
            const el = document.getElementById('perf-equity-chart')
            if (el && el.tagName === 'CANVAS') {
                Charts.equity('perf-equity-chart', filtered)
                chartDrawn.current = true
            }
        }, 100)
    }, [perf.equity_curve, equityRange])

    useEffect(() => {
        if (!perf.aplus && !perf.a && !perf.b) return
        setTimeout(() => {
            const el = document.getElementById('perf-grade-donut')
            if (el && el.tagName === 'CANVAS') {
                Charts.gradeDonut('perf-grade-donut', {
                    'A+': perf.aplus || {},
                    'A':  perf.a     || {},
                    'B':  perf.b     || {},
                })
            }
        }, 100)
    }, [perf.aplus, perf.a, perf.b])

    function filterCurve(curve, range) {
        if (!curve?.length) return []
        if (range === 'all') return curve
        const days   = range === '7d' ? 7 : range === '30d' ? 30 : 90
        const cutoff = new Date(Date.now() - days * 86400000)
        return curve.filter(c => c.date && new Date(c.date) >= cutoff)
    }

    async function loadSignals(f) {
        setSigLoading(true)
        try {
            const q = new URLSearchParams()
            q.set('limit', parseInt(f.limit) || 100)
            if (f.grade)   q.set('grade',   f.grade)
            if (f.coin)    q.set('coin',     f.coin.toUpperCase().trim())
            if (f.outcome) q.set('outcome',  f.outcome)
            const res  = await fetch('/api/signals?' + q.toString(), { credentials: 'include' })
            if (res.status === 401) { window.location.href = '/login.html'; return }
            let result = await res.json() || []
            if (f.direction) result = result.filter(s => s.direction === f.direction)
            setSignals(result)
            setCurrentPage(1)
        } catch(e) {
            showToast('Failed to load signals: ' + e.message, 'error')
        } finally {
            setSigLoading(false)
        }
    }

    function handleFilterChange(key, val) {
        const next = { ...filters, [key]: val }
        setFilters(next)
        if (key === 'direction') {
            let result = [...signals]
            if (val) result = result.filter(s => s.direction === val)
            setSignals(result)
            setCurrentPage(1)
        } else {
            loadSignals(next)
        }
    }

    function toggleSignals() {
        if (!showSignals) {
            setShowSignals(true)
            loadSignals(filters)
        } else {
            setShowSignals(false)
        }
    }

    const equityCurveFiltered = filterCurve(perf.equity_curve || [], equityRange)
    const totalReturn         = perf.total_return || ((perf.total_pnl || 0) / 1000 * 100).toFixed(2)

    return html`
        <div>
            <div class="page-header">
                <div>
                    <div class="page-title">Performance</div>
                    <div class="page-subtitle">${perf.closed || 0} closed trades · All time</div>
                </div>
            </div>

            <div class="card mb-24">
                <div style="padding:20px 20px 14px;">
                    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
                        <div style="display:flex;flex-direction:column;gap:4px;">
                            <div class="label-uppercase">Total Equity</div>
                            <div style="font-family:var(--font-mono);font-size:var(--text-title1);font-weight:var(--weight-heavy);color:var(--label-1);letter-spacing:var(--tracking-title1);">
                                ${Utils.fmtPnl(perf.total_pnl, perf.total_pnl_pos)}
                            </div>
                            <div style=${'font-family:var(--font-mono);font-size:var(--text-footnote);font-weight:var(--weight-semibold);color:' + (perf.total_pnl_pos ? 'var(--profit)' : 'var(--loss)') + ';'}>
                                ${totalReturn > 0 ? '+' : ''}${totalReturn}% all time
                            </div>
                        </div>
                        <div class="chart-range-selector">
                            ${['7d', '30d', '90d', 'all'].map(r => html`
                                <button key=${r}
                                    class=${'chart-range-btn ' + (equityRange === r ? 'active' : '')}
                                    onClick=${() => {
                                        chartDrawn.current   = false
                                        prevCurveKey.current = null
                                        setEquityRange(r)
                                    }}>
                                    ${r === 'all' ? 'All' : r.toUpperCase()}
                                </button>
                            `)}
                        </div>
                    </div>
                    ${!equityCurveFiltered.length
                        ? html`
                            <div class="chart-empty" style="height:240px;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/></svg>
                                <span class="chart-empty-text">No closed trades in this range</span>
                            </div>
                        `
                        : html`
                            <div class="chart-wrap chart-h-240">
                                <canvas id="perf-equity-chart"></canvas>
                            </div>
                        `
                    }
                </div>
            </div>

            <div class="grid-4 mb-24">
                ${[
                    {
                        label: 'Total Return',
                        val:   (totalReturn > 0 ? '+' : '') + totalReturn + '%',
                        sub:   Utils.fmtPnl(perf.total_pnl, perf.total_pnl_pos),
                        color: perf.total_pnl_pos ? 'var(--profit)' : 'var(--loss)',
                    },
                    {
                        label: 'Win Rate',
                        val:   (perf.win_rate || 0) + '%',
                        sub:   (perf.wins || 0) + 'W · ' + (perf.losses || 0) + 'L',
                        color: Utils.winRateColor(perf.win_rate),
                    },
                    {
                        label: 'Max Drawdown',
                        val:   (perf.max_drawdown || 0) + '%',
                        sub:   'Peak: ' + Utils.fmtPnl(perf.peak_equity, true),
                        color: perf.max_drawdown > 15 ? 'var(--loss)' : perf.max_drawdown > 8 ? 'var(--warning)' : 'var(--profit)',
                    },
                    {
                        label: 'Profit Factor',
                        val:   perf.profit_factor || '--',
                        sub:   (perf.closed || 0) + ' closed trades',
                        color: perf.profit_factor >= 1.5 ? 'var(--profit)' : perf.profit_factor >= 1 ? 'var(--warning)' : 'var(--loss)',
                    },
                ].map(item => html`
                    <div key=${item.label} class="stat-card">
                        <div class="stat-card-label">${item.label}</div>
                        <div class="stat-card-value" style=${'color:' + item.color + ';'}>
                            ${item.val}
                        </div>
                        <div class="stat-card-sub">${item.sub}</div>
                    </div>
                `)}
            </div>

            <div class="grid-2 mb-24">
                <div class="card card-pad">
                    <div class="section-title mb-16">By Grade</div>
                    <div style="position:relative;height:160px;margin-bottom:16px;">
                        <canvas id="perf-grade-donut"></canvas>
                    </div>
                    ${[
                        { grade: 'A+', data: perf.aplus, color: 'var(--grade-aplus)' },
                        { grade: 'A',  data: perf.a,     color: 'var(--grade-a)'     },
                        { grade: 'B',  data: perf.b,     color: 'var(--grade-b)'     },
                    ].filter(g => g.data).map(g => html`
                        <div key=${g.grade} style="margin-bottom:12px;">
                            <div class="flex justify-between items-center mb-6">
                                <div class="flex items-center gap-8">
                                    <${GradeBadge} grade=${g.grade}/>
                                    <span style="font-size:var(--text-caption1);color:var(--label-3);">
                                        ${g.data.total || 0} trades
                                    </span>
                                </div>
                                <div class="flex items-center gap-10">
                                    <span style=${'font-family:var(--font-mono);font-size:var(--text-footnote);font-weight:var(--weight-bold);color:' + Utils.winRateColor(g.data.win_rate) + ';'}>
                                        ${g.data.win_rate || 0}%
                                    </span>
                                    <span style=${'font-family:var(--font-mono);font-size:var(--text-caption1);color:' + Utils.pnlColor((g.data.pnl || 0) >= 0) + ';'}>
                                        ${Utils.fmtPnl(g.data.pnl, (g.data.pnl || 0) >= 0)}
                                    </span>
                                </div>
                            </div>
                            <div class="win-rate-track">
                                <div class="win-rate-fill" style=${'width:' + (g.data.win_rate || 0) + '%;background:' + g.color + ';'}></div>
                            </div>
                        </div>
                    `)}
                </div>

                <div class="card card-pad">
                    <div class="section-title mb-16">Statistics</div>
                    ${[
                        { label: 'Total Signals',  val: summary.total_signals  || 0 },
                        { label: 'Closed',         val: perf.closed            || 0 },
                        { label: 'Pending',        val: summary.pending_signals || 0 },
                        { label: 'Wins',           val: perf.wins              || 0, color: 'var(--profit)' },
                        { label: 'Losses',         val: perf.losses            || 0, color: 'var(--loss)'   },
                        { label: 'Best Trade',     val: Utils.fmtPnl(perf.best_trade, true), color: 'var(--profit)' },
                        { label: 'Best Coin',      val: perf.best_trade_coin   || '--' },
                        { label: 'Gross Profit',   val: Utils.fmtPnl(perf.gross_profit, true),  color: 'var(--profit)' },
                        { label: 'Gross Loss',     val: Utils.fmtPnl(perf.gross_loss,   false), color: 'var(--loss)'   },
                    ].map(row => html`
                        <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                            mono=${true} color=${row.color}/>
                    `)}
                </div>
            </div>

            <div class="card">
                <div class="filter-bar">
                    <div class="section-title" style="font-size:var(--text-subhead);">Signal History</div>
                    <div class="filter-spacer"></div>
                    <button class="btn btn-ghost btn-sm" onClick=${toggleSignals}>
                        ${showSignals ? 'Hide' : 'View All Signals'}
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points=${showSignals ? '18 15 12 9 6 15' : '6 9 12 15 18 9'}/>
                        </svg>
                    </button>
                </div>

                ${showSignals && html`
                    <div>
                        <div class="filter-bar" style="border-top:0.5px solid var(--separator);">
                            <select class="select select-sm" style="width:110px;" value=${filters.grade}
                                onChange=${e => handleFilterChange('grade', e.target.value)}>
                                <option value="">All Grades</option>
                                <option value="A+">A+</option>
                                <option value="A">A</option>
                                <option value="B">B</option>
                                <option value="C">C</option>
                                <option value="F">F</option>
                            </select>
                            <select class="select select-sm" style="width:120px;" value=${filters.outcome}
                                onChange=${e => handleFilterChange('outcome', e.target.value)}>
                                <option value="">All Outcomes</option>
                                <option value="win">Win</option>
                                <option value="loss">Loss</option>
                                <option value="pending">Pending</option>
                            </select>
                            <select class="select select-sm" style="width:110px;" value=${filters.direction}
                                onChange=${e => handleFilterChange('direction', e.target.value)}>
                                <option value="">All Dirs</option>
                                <option value="LONG">Long</option>
                                <option value="SHORT">Short</option>
                            </select>
                            <input class="input input-sm" style="width:100px;" type="text"
                                placeholder="Coin..."
                                value=${filters.coin}
                                onInput=${e => setFilters(f => ({ ...f, coin: e.target.value }))}
                                onKeyDown=${e => e.key === 'Enter' && handleFilterChange('coin', e.target.value)}/>
                            <select class="select select-sm" style="width:80px;" value=${filters.limit}
                                onChange=${e => handleFilterChange('limit', e.target.value)}>
                                <option value="50">50</option>
                                <option value="100">100</option>
                                <option value="200">200</option>
                                <option value="500">500</option>
                            </select>
                            <button class="btn btn-ghost btn-sm" onClick=${() => {
                                const f = { grade: '', outcome: '', direction: '', coin: '', limit: '100' }
                                setFilters(f)
                                loadSignals(f)
                            }}>Clear</button>
                            <div class="filter-spacer"></div>
                            <span class="filter-count"><strong>${signals.length}</strong> signals</span>
                        </div>

                        ${sigLoading
                            ? html`<div style="padding:16px;"><${LoadingSkeleton} rows=${5}/></div>`
                            : html`
                                <div class="table-wrap" style="max-height:500px;overflow-y:auto;">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>#</th><th>Time</th><th>Coin</th>
                                                <th>Dir</th><th>Grade</th><th>Score</th>
                                                <th>Entry</th><th>SL</th><th>TP</th>
                                                <th>Exit</th><th>PnL</th><th>Result</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${!paginated.length
                                                ? html`
                                                    <tr><td colspan="12">
                                                        <${EmptyState} size="sm" title="No signals match filters"/>
                                                    </td></tr>
                                                `
                                                : paginated.map(s => html`
                                                    <tr key=${s.id} class="clickable"
                                                        onClick=${() => setSelectedSig(s)}>
                                                        <td class="td-id">${s.id}</td>
                                                        <td>
                                                            <div class="td-time">
                                                                <span class="td-time-primary">${Utils.fmtTimeAgo(s.timestamp)}</span>
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <span style="font-family:var(--font-mono);font-weight:var(--weight-bold);color:var(--label-1);">
                                                                ${s.coin}
                                                            </span>
                                                        </td>
                                                        <td><${DirBadge} dir=${s.direction}/></td>
                                                        <td><${GradeBadge} grade=${s.grade}/></td>
                                                        <td><${ScoreBar} score=${s.score} grade=${s.grade}/></td>
                                                        <td class="td-price">${Utils.fmtPrice(s.entry)}</td>
                                                        <td>
                                                            <span style="font-family:var(--font-mono);font-size:var(--text-footnote);color:var(--loss);">
                                                                ${Utils.fmtPrice(s.sl)}
                                                            </span>
                                                        </td>
                                                        <td>
                                                            <span style="font-family:var(--font-mono);font-size:var(--text-footnote);color:var(--profit);">
                                                                ${Utils.fmtPrice(s.tp1)}
                                                            </span>
                                                        </td>
                                                        <td class="td-price">${Utils.fmtPrice(s.exit_price)}</td>
                                                        <td>
                                                            <div class="td-pnl">
                                                                <div class=${'td-pnl-fill ' + Utils.pnlClass(s.pnl_pos)}></div>
                                                                <span class=${'td-pnl-value ' + Utils.pnlClass(s.pnl_pos)}>
                                                                    ${s.pnl != null ? Utils.fmtPnl(s.pnl, s.pnl_pos) : '--'}
                                                                </span>
                                                            </div>
                                                        </td>
                                                        <td><${OutcomeBadge} outcome=${s.outcome}/></td>
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
                                            onClick=${() => setCurrentPage(1)}
                                            disabled=${currentPage <= 1}>
                                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>
                                        </button>
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
                                        <button class="pagination-btn"
                                            onClick=${() => setCurrentPage(totalPages)}
                                            disabled=${currentPage >= totalPages}>
                                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>
                                        </button>
                                    </div>
                                </div>
                            `
                        }
                    </div>
                `}

                ${!showSignals && html`
                    <div style="padding:16px;text-align:center;">
                        <span style="font-size:var(--text-subhead);color:var(--label-4);">
                            Click "View All Signals" to browse the full signal history
                        </span>
                    </div>
                `}
            </div>

            ${selectedSig && html`
                <${SignalHistoryPanel}
                    signal=${selectedSig}
                    onClose=${() => setSelectedSig(null)}
                />
            `}
        </div>
    `
}

function SignalHistoryPanel({ signal, onClose }) {
    const s = signal
    return html`
        <${Panel}
            show=${true}
            onClose=${onClose}
            title=${s.coin + 'USDT'}
            subtitle=${'Signal #' + s.id}
        >
            <div class="panel-section">
                <div class="flex items-center gap-8 flex-wrap">
                    <${GradeBadge} grade=${s.grade} size="lg"/>
                    <${DirBadge} dir=${s.direction}/>
                    <${OutcomeBadge} outcome=${s.outcome}/>
                </div>
            </div>

            <div class="panel-section">
                <div class="panel-section-title">Signal Levels</div>
                ${[
                    { label: 'Entry',       val: Utils.fmtPrice(s.entry),      color: 'var(--label-1)'  },
                    { label: 'Stop Loss',   val: Utils.fmtPrice(s.sl),         color: 'var(--loss)'     },
                    { label: 'Take Profit', val: Utils.fmtPrice(s.tp1),        color: 'var(--profit)'   },
                    { label: 'Exit Price',  val: Utils.fmtPrice(s.exit_price)  },
                    { label: 'PnL',         val: s.pnl != null ? Utils.fmtPnl(s.pnl, s.pnl_pos) : '--', color: Utils.pnlColor(s.pnl_pos) },
                    { label: 'Risk',        val: s.risk_amt ? '$' + parseFloat(s.risk_amt).toFixed(2) : '--' },
                ].map(row => html`
                    <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                        mono=${true} color=${row.color}/>
                `)}
            </div>

            <div class="panel-section">
                <div class="panel-section-title">Context</div>
                ${[
                    { label: 'Score',        val: (s.score || 0) + '/100',     color: Utils.scoreColor(s.score) },
                    { label: 'Market Score', val: s.market_score != null ? s.market_score + '/100' : '--' },
                    { label: 'Entry Score',  val: s.entry_score  != null ? s.entry_score  + '/100' : '--' },
                    { label: 'BTC Score',    val: s.btc_score    != null ? s.btc_score    + '/8'   : '--' },
                    { label: 'Regime',       val: s.regime   || '--' },
                    { label: 'Session',      val: s.session  || '--' },
                    { label: 'Signal Type',  val: s.signal_type || '--' },
                    { label: 'Generated',    val: Utils.fmtTime(s.timestamp) },
                ].map(row => html`
                    <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                        mono=${true} color=${row.color}/>
                `)}
            </div>
        </${Panel}>
    `
}