var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { showToast } = Store
var { GradeBadge, DirBadge, OutcomeBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton } = SE

function BacktestPage() {
    const [coins,          setCoins]          = useState([])
    const [selectedCoin,   setSelectedCoin]   = useState('')
    const [result,         setResult]         = useState(null)
    const [history,        setHistory]        = useState([])
    const [running,        setRunning]        = useState(false)
    const [historyLoading, setHistoryLoading] = useState(false)
    const [error,          setError]          = useState('')
    const [tradePage,      setTradePage]      = useState(1)
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
            if (result.trades?.length) {
                const el = document.getElementById('bt-equity-chart')
                if (el && el.tagName === 'CANVAS') Charts.equity('bt-equity-chart', result.trades)
            }
            if (result.by_grade) {
                const el = document.getElementById('bt-grade-donut')
                if (el && el.tagName === 'CANVAS') Charts.gradeDonut('bt-grade-donut', result.by_grade)
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
        setHistoryLoading(true)
        try {
            const data = await API.backtestHistory()
            setHistory(data || [])
        } catch(e) {} finally { setHistoryLoading(false) }
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
        } finally { setRunning(false) }
    }

    return html`
        <div>
            <div class="page-header">
                <div class="page-title">Backtest</div>
                <div class="page-subtitle">Historical signal simulation on stored candle data</div>
            </div>

            <div class="card mb-16">
                <div class="section-title mb-12">Run Backtest</div>
                <div class="flex gap-8" style="flex-wrap:wrap;align-items:center;">
                    <select class="select" style="width:160px;" value=${selectedCoin}
                        onChange=${e => setSelectedCoin(e.target.value)}>
                        <option value="">Select Coin</option>
                        ${coins.map(c => html`<option key=${c} value=${c}>${c}USDT</option>`)}
                    </select>
                    <button class="btn btn-primary" onClick=${runBacktest}
                        disabled=${running || !selectedCoin}>
                        ${running ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="5 3 19 12 5 21 5 3"/>
                            </svg>
                        `}
                        ${running ? 'Running... (up to 2 min)' : 'Run Backtest'}
                    </button>
                    <button class="btn btn-ghost btn-sm" onClick=${loadHistory} disabled=${historyLoading}>
                        ${historyLoading ? html`<${Spinner}/>` : 'Refresh History'}
                    </button>
                </div>
                ${running && html`
                    <div class="alert alert-info mt-12">
                        ⏳ Running backtest for
                        <span style="font-family:var(--font-mono);font-weight:700;">${selectedCoin}USDT</span>
                        — this may take up to 2 minutes...
                    </div>
                `}
                ${error && html`<div class="alert alert-error mt-12">${error}</div>`}
            </div>

            ${result && html`
                <div>
                    <div class="grid-4 mb-16">
                        <div class="stat-card">
                            <div class="stat-card-label">Win Rate</div>
                            <div class="stat-card-value" style="color:${Utils.winRateColor(result.win_rate)};">
                                ${result.win_rate}%
                            </div>
                            <div class="stat-card-sub">${result.wins}W · ${result.losses}L · ${result.total_trades} trades</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-label">Total PnL</div>
                            <div class="stat-card-value" style="color:${Utils.pnlColor(result.total_pnl >= 0)};">
                                ${Utils.fmtPnl(result.total_pnl, result.total_pnl >= 0)}
                            </div>
                            <div class="stat-card-sub">Return: ${result.total_return}%</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-label">Max Drawdown</div>
                            <div class="stat-card-value" style="color:var(--red);">${result.max_drawdown}%</div>
                            <div class="stat-card-sub">Profit Factor: ${result.profit_factor}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-label">Signals</div>
                            <div class="stat-card-value" style="color:var(--purple);">${result.total_signals}</div>
                            <div class="stat-card-sub">A+: ${result.aplus_signals} · A: ${result.a_signals}</div>
                        </div>
                    </div>

                    <div class="grid-2 mb-16">
                        <div class="card">
                            <div class="section-title mb-12">Equity Curve</div>
                            <div style="position:relative;height:220px;">
                                <canvas id="bt-equity-chart"></canvas>
                            </div>
                        </div>
                        <div class="card">
                            <div class="section-title mb-12">By Grade</div>
                            <div style="position:relative;height:180px;" class="mb-12">
                                <canvas id="bt-grade-donut"></canvas>
                            </div>
                            ${Object.entries(result.by_grade || {}).map(([grade, data]) => html`
                                <div key=${grade} style="margin-bottom:12px;">
                                    <div class="flex justify-between items-center" style="margin-bottom:5px;">
                                        <div class="flex items-center gap-8">
                                            <${GradeBadge} grade=${grade}/>
                                            <span style="font-size:11px;color:var(--text-secondary);">${data.trades} trades</span>
                                        </div>
                                        <div class="flex items-center gap-8">
                                            <span style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:${Utils.winRateColor(data.win_rate)};">
                                                ${data.win_rate}%
                                            </span>
                                            <span style="font-family:var(--font-mono);font-size:11px;color:${Utils.pnlColor(data.pnl >= 0)};">
                                                ${Utils.fmtPnl(data.pnl, data.pnl >= 0)}
                                            </span>
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
                                { label: 'Best Trade',        val: Utils.fmtPnl(result.best_trade, true),  color: 'var(--green)' },
                                { label: 'Worst Trade',       val: Utils.fmtPnl(result.worst_trade, false), color: 'var(--red)' },
                                { label: 'Avg Trade',         val: Utils.fmtPnl(result.avg_trade, result.avg_trade >= 0), color: Utils.pnlColor(result.avg_trade >= 0) },
                                { label: 'Expectancy',        val: Utils.fmtPnl(result.expectancy, result.expectancy >= 0), color: Utils.pnlColor(result.expectancy >= 0) },
                                { label: 'Max Consec Wins',   val: result.max_consec_wins   || '--', color: 'var(--green)' },
                                { label: 'Max Consec Losses', val: result.max_consec_losses || '--', color: 'var(--red)'   },
                                { label: 'TP1 Hit Rate',      val: result.phase_breakdown?.tp1_hit_rate != null ? result.phase_breakdown.tp1_hit_rate + '%' : '--' },
                            ].map(row => html`
                                <div key=${row.label} class="stat-row">
                                    <span class="stat-label">${row.label}</span>
                                    <span class="stat-value" style="${row.color ? 'color:' + row.color : ''}">${row.val}</span>
                                </div>
                            `)}
                        </div>
                    </div>

                    <div class="card mb-16">
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
                                                <td><span style="font-family:var(--font-mono);font-weight:700;color:${Utils.pnlColor(t.pnl >= 0)};">${Utils.fmtPnl(t.pnl, t.pnl >= 0)}</span></td>
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
                                        <td><span style="font-family:var(--font-mono);color:${Utils.pnlColor(h.total_pnl >= 0)};">${Utils.fmtPnl(h.total_pnl, h.total_pnl >= 0)}</span></td>
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