var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { useFtUpdate, showToast, requireTotp } = Store
var {
    DirBadge, GradeBadge, HealthDot, HealthRow,
    TradeProgressBar, Spinner, EmptyState,
    LoadingSkeleton, Panel, InfoRow
} = SE

function PositionsPage() {
    const ftData                              = useFtUpdate()
    const [loading,       setLoading]         = useState(false)
    const [openTrades,    setOpenTrades]       = useState([])
    const [profit,        setProfit]           = useState({})
    const [balance,       setBalance]          = useState({})
    const [botState,      setBotState]         = useState('unknown')
    const [daily,         setDaily]            = useState([])
    const [tradeHistory,  setTradeHistory]     = useState([])
    const [selectedTrade, setSelectedTrade]    = useState(null)
    const [actionLoading, setActionLoading]    = useState(null)
    const [error,         setError]            = useState('')
    const [histPage,      setHistPage]         = useState(1)
    const histPageSize = 20
    const chartDrawn   = useRef(false)

    useEffect(() => {
        refresh()
        return () => {
            Charts.destroy('positions-daily-chart')
            chartDrawn.current = false
        }
    }, [])

    useEffect(() => {
        if (ftData.trades?.length) {
            setOpenTrades(prev => {
                if (!prev.length) return ftData.trades
                return ftData.trades.map(t => {
                    const ex = prev.find(p => p.trade_id === t.trade_id)
                    return {
                        ...t,
                        sl_signal: t.sl_signal ?? ex?.sl_signal,
                        tp1:       t.tp1       ?? ex?.tp1,
                        health:    t.health    ?? ex?.health,
                    }
                })
            })
        }
        if (ftData.profit?.trade_count != null) setProfit(ftData.profit)
        if (ftData.balance?.total      != null) setBalance(ftData.balance)
        if (ftData.botState && ftData.botState !== 'unknown') setBotState(ftData.botState)
    }, [ftData])

    useEffect(() => {
        if (!daily.length || chartDrawn.current) return
        setTimeout(() => {
            const el = document.getElementById('positions-daily-chart')
            if (el && el.tagName === 'CANVAS') {
                Charts.dailyPnl('positions-daily-chart', daily)
                chartDrawn.current = true
            }
        }, 100)
    }, [daily])

    async function refresh() {
        if (loading) return
        setLoading(true)
        setError('')
        try {
            const controller = new AbortController()
            const timeout    = setTimeout(() => controller.abort(), 12000)
            const res        = await fetch('/api/ft/summary', {
                credentials: 'include',
                signal:      controller.signal
            })
            clearTimeout(timeout)
            if (res.status === 401) { window.location.href = '/login.html'; return }
            if (!res.ok) { setError('Freqtrade unavailable — check if container is running'); return }
            const data = await res.json().catch(() => null)
            if (!data) return
            if (data.bot_state)                        setBotState(data.bot_state)
            if (Array.isArray(data.status))            setOpenTrades(data.status)
            if (data.profit  && !data.profit.detail)   setProfit(data.profit)
            if (data.balance && !data.balance.detail) {
                const currencies = data.balance.currencies || []
                const usdt       = currencies.find(c => c.currency === 'USDT') || {}
                setBalance({
                    total: data.balance.total != null ? parseFloat(data.balance.total) : null,
                    free:  usdt.free           != null ? parseFloat(usdt.free)          : null,
                })
            }
            if (data.daily) {
                const arr = Array.isArray(data.daily) ? data.daily
                          : Array.isArray(data.daily.data) ? data.daily.data : []
                setDaily(arr.map(x => ({
                    date:       x.date || x.day || '',
                    profit_abs: parseFloat(x.profit_abs || x.profit || 0)
                })).filter(x => x.date))
            }
            loadHistory()
        } catch(e) {
            if (e.name === 'AbortError') setError('Freqtrade request timed out')
            else setError('Freqtrade unavailable: ' + e.message)
        } finally {
            setLoading(false)
        }
    }

    async function loadHistory() {
        try {
            const res  = await fetch('/api/ft/trades?limit=100', { credentials: 'include' })
            if (!res.ok) return
            const data = await res.json().catch(() => null)
            if (data) {
                setTradeHistory(
                    Array.isArray(data.trades)
                        ? data.trades.filter(t => !t.is_open)
                        : []
                )
            }
        } catch(e) {}
    }

    async function startBot() {
        setActionLoading('start')
        try {
            const res  = await fetch('/api/ft/start', {
                method:      'POST',
                credentials: 'include',
                headers:     { 'Content-Type': 'application/json' }
            })
            const data = await res.json().catch(() => ({}))
            showToast('Bot: ' + (data.status || 'start command sent'), 'success')
            setTimeout(() => refresh(), 2000)
        } catch(e) {
            showToast('Start failed: ' + e.message, 'error')
        } finally { setActionLoading(null) }
    }

    async function stopBot() {
        setActionLoading('stop')
        try {
            const res  = await fetch('/api/ft/stop', {
                method:      'POST',
                credentials: 'include',
                headers:     { 'Content-Type': 'application/json' }
            })
            const data = await res.json().catch(() => ({}))
            showToast('Bot: ' + (data.status || 'stop command sent'), 'success')
            setTimeout(() => refresh(), 2000)
        } catch(e) {
            showToast('Stop failed: ' + e.message, 'error')
        } finally { setActionLoading(null) }
    }

    const totalPnl    = parseFloat(profit.profit_all_coin || 0)
    const winRate     = parseFloat(profit.winrate || 0) * 100
    const tradeCount  = profit.trade_count || 0
    const totalExposure = openTrades.reduce((s, t) => s + parseFloat(t.stake_amount || 0), 0)

    const histTotal = tradeHistory.length
    const histPages = Math.max(1, Math.ceil(histTotal / histPageSize))
    const histSlice = tradeHistory.slice((histPage - 1) * histPageSize, histPage * histPageSize)

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Positions</div>
                    <div class="page-subtitle flex items-center gap-8">
                        <div class=${'topbar-ws-dot ' + (botState === 'running' ? 'connected' : 'disconnected')}></div>
                        <span>Bot ${botState}</span>
                    </div>
                </div>
                <div class="flex gap-8">
                    <button class="btn btn-success btn-sm" onClick=${startBot}
                        disabled=${!!actionLoading || botState === 'running'}>
                        ${actionLoading === 'start' ? html`<${Spinner} size="xs"/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        `}
                        Start
                    </button>
                    <button class="btn btn-danger btn-sm" onClick=${stopBot}
                        disabled=${!!actionLoading || botState === 'stopped'}>
                        ${actionLoading === 'stop' ? html`<${Spinner} size="xs"/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18"/></svg>
                        `}
                        Stop
                    </button>
                    <button class="btn btn-secondary btn-sm" onClick=${refresh} disabled=${loading}>
                        ${loading ? html`<${Spinner} size="xs"/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                        `}
                        Refresh
                    </button>
                </div>
            </div>

            ${error && html`
                <div class="alert alert-error mb-16">
                    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <div class="alert-content"><div class="alert-desc">${error}</div></div>
                </div>
            `}

            <div class="grid-4 mb-24">
                <div class="stat-card ${botState === 'running' ? 'stat-card-brand' : ''}">
                    <div class="stat-card-label">Bot State</div>
                    <div style="margin-top:8px;">
                        <span class=${'badge ' + (botState === 'running' ? 'badge-online' : 'badge-offline')}>
                            ${botState.toUpperCase()}
                        </span>
                    </div>
                    <div class="stat-card-sub">${openTrades.length} open · $${totalExposure.toFixed(2)} deployed</div>
                </div>
                <div class="stat-card stat-card-brand">
                    <div class="stat-card-label">Balance</div>
                    <div class="stat-card-value" style="color:var(--brand);">
                        ${balance.total != null ? '$' + parseFloat(balance.total).toFixed(2) : '--'}
                    </div>
                    <div class="stat-card-sub">
                        ${balance.free != null ? 'Free: $' + parseFloat(balance.free).toFixed(2) : '--'}
                    </div>
                </div>
                <div class=${'stat-card ' + (totalPnl >= 0 ? 'stat-card-profit' : 'stat-card-loss')}>
                    <div class="stat-card-label">Total PnL</div>
                    <div class=${'stat-card-value pnl-value ' + (totalPnl >= 0 ? 'positive' : 'negative')}>
                        ${Utils.fmtPnl(totalPnl, totalPnl >= 0)}
                    </div>
                    <div class="stat-card-sub">${tradeCount} total trades</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-label">Win Rate</div>
                    <div class="stat-card-value" style=${'color:' + Utils.winRateColor(winRate) + ';'}>
                        ${profit.winrate != null ? winRate.toFixed(1) + '%' : '--'}
                    </div>
                    <div class="stat-card-sub">
                        ${profit.profit_factor != null ? 'PF: ' + parseFloat(profit.profit_factor).toFixed(2) : '--'}
                    </div>
                </div>
            </div>

            ${openTrades.length > 0 && html`
                <div class="mb-24">
                    <div class="section-header">
                        <div>
                            <div class="section-title">Open Positions</div>
                            <div class="section-subtitle">$${totalExposure.toFixed(2)} total exposure</div>
                        </div>
                        <span class="tag">${openTrades.length}</span>
                    </div>

                    <div class="exposure-progress mb-16">
                        <div class="exposure-track">
                            ${openTrades.map((t, i) => {
                                const stake = parseFloat(t.stake_amount || 0)
                                const pct   = totalExposure > 0 ? (stake / totalExposure) * 100 : 0
                                return html`
                                    <div key=${t.trade_id} class="exposure-segment"
                                        style=${'width:' + pct + '%;background:' + Utils.segmentColors(i) + ';'}
                                        title=${t.pair + ' $' + stake.toFixed(2)}>
                                    </div>
                                `
                            })}
                        </div>
                        <div class="exposure-legend">
                            ${openTrades.map((t, i) => html`
                                <div key=${t.trade_id} class="exposure-legend-item">
                                    <div class="exposure-legend-dot"
                                        style=${'background:' + Utils.segmentColors(i) + ';'}></div>
                                    <span>${(t.pair || '').replace('/USDT:USDT', '').replace('/USDT', '')}</span>
                                    <span class="exposure-legend-value">
                                        $${parseFloat(t.stake_amount || 0).toFixed(0)}
                                    </span>
                                </div>
                            `)}
                        </div>
                    </div>

                    ${loading && !openTrades.length
                        ? html`<${LoadingSkeleton} rows=${2} type="card"/>`
                        : openTrades.map(trade => html`
                            <${PositionCard}
                                key=${trade.trade_id}
                                trade=${trade}
                                onClick=${() => setSelectedTrade(trade)}
                                onRefresh=${refresh}
                            />
                        `)
                    }
                </div>
            `}

            ${!openTrades.length && !loading && html`
                <div class="card mb-24">
                    <${EmptyState}
                        title="No Open Positions"
                        desc="The bot is scanning for opportunities. Signals will execute automatically."
                    />
                </div>
            `}

            <div class="grid-2 mb-24">
                <div class="card card-pad">
                    <div class="section-title mb-16">Daily PnL</div>
                    ${!daily.length
                        ? html`<${EmptyState} size="sm" title="No daily data yet"/>`
                        : html`
                            <div class="chart-wrap chart-h-160">
                                <canvas id="positions-daily-chart"></canvas>
                            </div>
                        `
                    }
                </div>
                <div class="card card-pad">
                    <div class="section-title mb-16">Summary</div>
                    ${[
                        { label: 'Total PnL',     val: Utils.fmtPnl(totalPnl, totalPnl >= 0), color: Utils.pnlColor(totalPnl >= 0) },
                        { label: 'Win Rate',      val: profit.winrate != null ? winRate.toFixed(1) + '%' : '--', color: Utils.winRateColor(winRate) },
                        { label: 'Total Trades',  val: tradeCount || '--' },
                        { label: 'Profit Factor', val: profit.profit_factor != null ? parseFloat(profit.profit_factor).toFixed(2) : '--' },
                        { label: 'Best Pair',     val: profit.best_pair || '--' },
                        { label: 'Balance',       val: balance.total != null ? '$' + parseFloat(balance.total).toFixed(2) : '--', color: 'var(--brand)' },
                        { label: 'Free Capital',  val: balance.free  != null ? '$' + parseFloat(balance.free).toFixed(2)  : '--' },
                    ].map(row => html`
                        <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                            mono=${true} color=${row.color}/>
                    `)}
                </div>
            </div>

            <div class="card">
                <div class="filter-bar">
                    <div class="section-title" style="font-size:var(--text-base);">Trade History</div>
                    <div class="filter-spacer"></div>
                    <span class="filter-count">
                        <strong>${histTotal}</strong> closed trades
                    </span>
                </div>
                <div class="table-wrap" style="max-height:480px;overflow-y:auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th><th>Pair</th><th>Dir</th>
                                <th>Entry</th><th>Exit</th>
                                <th>PnL</th><th>%</th>
                                <th>Duration</th><th>Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${!histSlice.length
                                ? html`
                                    <tr>
                                        <td colspan="9">
                                            <${EmptyState} size="sm" title="No closed trades yet"/>
                                        </td>
                                    </tr>
                                `
                                : histSlice.map(t => {
                                    const pnlPos = (t.profit_abs || 0) >= 0
                                    return html`
                                        <tr key=${t.trade_id}>
                                            <td class="td-id">${t.trade_id}</td>
                                            <td>
                                                <span style="font-family:var(--font-mono);font-weight:var(--weight-bold);color:var(--text-1);">
                                                    ${(t.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')}
                                                </span>
                                            </td>
                                            <td><${DirBadge} dir=${t.is_short ? 'SHORT' : 'LONG'}/></td>
                                            <td class="td-price">${Utils.fmtPrice(t.open_rate)}</td>
                                            <td class="td-price">${Utils.fmtPrice(t.close_rate)}</td>
                                            <td>
                                                <div class="td-pnl">
                                                    <div class=${'td-pnl-fill ' + (pnlPos ? 'positive' : 'negative')}></div>
                                                    <span class=${'td-pnl-value ' + (pnlPos ? 'positive' : 'negative')}>
                                                        ${Utils.fmtPnl(t.profit_abs, pnlPos)}
                                                    </span>
                                                </div>
                                            </td>
                                            <td>
                                                <span class=${'td-change ' + (pnlPos ? 'positive' : 'negative')}>
                                                    ${Utils.fmtPct((t.profit_ratio || 0) * 100)}
                                                </span>
                                            </td>
                                            <td style="color:var(--text-3);font-size:var(--text-xs);">
                                                ${Utils.fmtDuration(t.open_date)}
                                            </td>
                                            <td style="color:var(--text-4);font-size:var(--text-xs);">
                                                ${t.exit_reason || '--'}
                                            </td>
                                        </tr>
                                    `
                                })
                            }
                        </tbody>
                    </table>
                </div>
                <div class="table-footer">
                    <span class="table-footer-info">
                        Page <strong>${histPage}</strong> of <strong>${histPages}</strong>
                    </span>
                    <div class="pagination">
                        <button class="pagination-btn" onClick=${() => setHistPage(1)}
                            disabled=${histPage <= 1}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>
                        </button>
                        <button class="pagination-btn" onClick=${() => setHistPage(p => p - 1)}
                            disabled=${histPage <= 1}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
                        </button>
                        <span style="padding:4px 8px;font-family:var(--font-mono);font-size:var(--text-xs);color:var(--text-3);">
                            ${histPage} / ${histPages}
                        </span>
                        <button class="pagination-btn" onClick=${() => setHistPage(p => p + 1)}
                            disabled=${histPage >= histPages}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                        </button>
                        <button class="pagination-btn" onClick=${() => setHistPage(histPages)}
                            disabled=${histPage >= histPages}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>
                        </button>
                    </div>
                </div>
            </div>

            ${selectedTrade && html`
                <${PositionDetailPanel}
                    trade=${selectedTrade}
                    onClose=${() => setSelectedTrade(null)}
                    onRefresh=${refresh}
                />
            `}
        </div>
    `
}

function PositionCard({ trade, onClick, onRefresh }) {
    const pair    = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir     = trade.is_short ? 'SHORT' : 'LONG'
    const pnl     = parseFloat(trade.profit_abs || 0)
    const pnlPos  = pnl >= 0
    const pnlPct  = parseFloat(trade.profit_ratio || 0) * 100
    const health  = trade.health
    const state   = health?.state || 'UNKNOWN'

    const healthBorderColors = {
        'HEALTHY':     'var(--profit)',
        'WARNING':     'var(--warning)',
        'INVALIDATED': 'var(--loss)',
    }
    const borderColor = healthBorderColors[state] || 'var(--border)'

    return html`
        <div class="trade-card trade-card-${Utils.healthClass(state)} mb-12"
            onClick=${onClick}
            role="button" tabindex="0"
            onKeyDown=${e => e.key === 'Enter' && onClick()}>
            <div class="trade-card-body">
                <div class="trade-card-header">
                    <div class="trade-card-header-left">
                        <span class="trade-card-coin">${pair}</span>
                        <${DirBadge} dir=${dir}/>
                        <span class="tag">#${trade.trade_id}</span>
                        <${HealthDot} state=${state}/>
                    </div>
                    <div class="trade-card-header-right">
                        <div class=${'trade-card-pnl ' + (pnlPos ? 'positive' : 'negative')}>
                            ${Utils.fmtPnl(pnl, pnlPos)}
                        </div>
                        <div class=${'trade-card-pnl-pct ' + (pnlPos ? 'positive' : 'negative')}>
                            ${Utils.fmtPct(pnlPct)}
                        </div>
                    </div>
                </div>

                <div class="trade-card-levels">
                    <div class="trade-card-level">
                        <div class="trade-card-level-label">Entry</div>
                        <div class="trade-card-level-value">${Utils.fmtPrice(trade.open_rate)}</div>
                    </div>
                    <div class="trade-card-level">
                        <div class="trade-card-level-label">Current</div>
                        <div class="trade-card-level-value" style=${'color:' + (pnlPos ? 'var(--profit)' : 'var(--loss)') + ';'}>
                            ${Utils.fmtPrice(trade.current_rate)}
                        </div>
                    </div>
                    <div class="trade-card-level">
                        <div class="trade-card-level-label">Open</div>
                        <div class="trade-card-level-value">${Utils.fmtDuration(trade.open_date)}</div>
                    </div>
                    <div class="trade-card-level">
                        <div class="trade-card-level-label">Stake</div>
                        <div class="trade-card-level-value">$${parseFloat(trade.stake_amount || 0).toFixed(2)}</div>
                    </div>
                    <div class="trade-card-level">
                        <div class="trade-card-level-label">Leverage</div>
                        <div class="trade-card-level-value" style="color:var(--brand);">${trade.leverage || '--'}x</div>
                    </div>
                    <div class="trade-card-level">
                        <div class="trade-card-level-label">Tag</div>
                        <div class="trade-card-level-value" style="font-size:10px;color:var(--text-4);">
                            ${trade.enter_tag || '--'}
                        </div>
                    </div>
                </div>

                <${TradeProgressBar} trade=${trade}/>
                <${HealthRow} health=${health}/>
            </div>
        </div>
    `
}

function PositionDetailPanel({ trade, onClose, onRefresh }) {
    const [forceSelling, setForceSelling] = useState(false)

    const pair   = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir    = trade.is_short ? 'SHORT' : 'LONG'
    const pnl    = parseFloat(trade.profit_abs || 0)
    const pnlPos = pnl >= 0
    const pnlPct = parseFloat(trade.profit_ratio || 0) * 100
    const health = trade.health
    const state  = health?.state || 'UNKNOWN'

    async function handleForceSell() {
        const code = await requireTotp(
            'Force Sell — ' + pair,
            'This will immediately close your ' + pair + ' position at market price. This action cannot be undone.'
        )
        if (!code) return
        setForceSelling(true)
        try {
            const res  = await fetch('/api/ft/forcesell', {
                method:      'POST',
                credentials: 'include',
                headers:     { 'Content-Type': 'application/json' },
                body:        JSON.stringify({ tradeid: trade.trade_id, totp_code: code })
            })
            const data = await res.json()
            if (data.success === false) {
                Store.showToast('Force sell failed: ' + (data.reason || 'Unknown'), 'error')
            } else {
                Store.showToast('Force sell submitted for ' + pair, 'success')
                onClose()
                setTimeout(onRefresh, 2000)
            }
        } catch(e) {
            Store.showToast('Force sell failed: ' + e.message, 'error')
        } finally {
            setForceSelling(false)
        }
    }

    return html`
        <${Panel}
            show=${true}
            onClose=${onClose}
            title=${pair}
            subtitle=${'Trade #' + trade.trade_id + ' · ' + Utils.fmtDuration(trade.open_date) + ' open'}
            footer=${html`
                <button class="btn btn-danger-solid btn-full"
                    onClick=${handleForceSell}
                    disabled=${forceSelling}>
                    ${forceSelling ? html`<${Spinner} size="xs" color="white"/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    `}
                    ${forceSelling ? 'Closing Position...' : 'Force Sell — Requires TOTP'}
                </button>
            `}
        >
            <div class="panel-section">
                <div class="flex items-center gap-10 flex-wrap">
                    <${DirBadge} dir=${dir}/>
                    <${HealthRow} health=${health}/>
                </div>

                <div style="padding:20px;background:var(--surface-3);border-radius:var(--r-lg);border:1px solid var(--border);text-align:center;">
                    <div style="font-size:var(--text-xs);color:var(--text-3);text-transform:uppercase;letter-spacing:var(--tracking-widest);font-weight:var(--weight-semibold);margin-bottom:8px;">
                        Unrealized PnL
                    </div>
                    <div class=${'pnl-value ' + (pnlPos ? 'positive' : 'negative')}
                        style="font-size:var(--text-4xl);">
                        ${Utils.fmtPnl(pnl, pnlPos)}
                    </div>
                    <div style=${'font-family:var(--font-mono);font-size:var(--text-md);color:' + (pnlPos ? 'var(--profit)' : 'var(--loss)') + ';margin-top:4px;'}>
                        ${Utils.fmtPct(pnlPct)}
                    </div>
                </div>

                <${TradeProgressBar} trade=${trade}/>
            </div>

            <div class="panel-section">
                <div class="panel-section-title">Position Details</div>
                ${[
                    { label: 'Entry Price',   val: Utils.fmtPrice(trade.open_rate)    },
                    { label: 'Current Price', val: Utils.fmtPrice(trade.current_rate), color: pnlPos ? 'var(--profit)' : 'var(--loss)' },
                    { label: 'Stop Loss',     val: Utils.fmtPrice(trade.sl_signal || trade.stop_loss_abs), color: 'var(--loss)'   },
                    { label: 'Take Profit',   val: Utils.fmtPrice(trade.tp1),          color: 'var(--profit)' },
                    { label: 'Stake',         val: '$' + parseFloat(trade.stake_amount || 0).toFixed(2) },
                    { label: 'Leverage',      val: (trade.leverage || '--') + 'x',     color: 'var(--brand)'  },
                    { label: 'Open Date',     val: Utils.fmtTime(trade.open_date)      },
                    { label: 'Duration',      val: Utils.fmtDuration(trade.open_date)  },
                    { label: 'Enter Tag',     val: trade.enter_tag || '--'             },
                ].map(row => html`
                    <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                        mono=${true} color=${row.color}/>
                `)}
            </div>

            ${health && html`
                <div class="panel-section">
                    <div class="panel-section-title">Health — ${state}</div>

                    ${health.failures?.length > 0 && html`
                        <div style="margin-bottom:12px;">
                            <div style="font-size:var(--text-xs);font-weight:var(--weight-semibold);color:var(--loss);text-transform:uppercase;letter-spacing:var(--tracking-widest);margin-bottom:8px;">
                                Invalidation Reasons
                            </div>
                            ${health.failures.map((f, i) => html`
                                <div key=${i} style="display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);font-size:var(--text-sm);">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--loss)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;">
                                        <line x1="18" y1="6" x2="6" y2="18"/>
                                        <line x1="6" y1="6" x2="18" y2="18"/>
                                    </svg>
                                    <span style="color:var(--text-2);">${f}</span>
                                </div>
                            `)}
                        </div>
                    `}

                    ${health.warnings?.length > 0 && html`
                        <div style="margin-bottom:12px;">
                            <div style="font-size:var(--text-xs);font-weight:var(--weight-semibold);color:var(--warning);text-transform:uppercase;letter-spacing:var(--tracking-widest);margin-bottom:8px;">
                                Warnings
                            </div>
                            ${health.warnings.map((w, i) => html`
                                <div key=${i} style="display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);font-size:var(--text-sm);">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;">
                                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                                        <line x1="12" y1="9" x2="12" y2="13"/>
                                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                                    </svg>
                                    <span style="color:var(--text-2);">${w}</span>
                                </div>
                            `)}
                        </div>
                    `}

                    ${health.checks?.length > 0 && html`
                        <div>
                            <div style="font-size:var(--text-xs);font-weight:var(--weight-semibold);color:var(--profit);text-transform:uppercase;letter-spacing:var(--tracking-widest);margin-bottom:8px;">
                                Passing Checks
                            </div>
                            ${health.checks.map((c, i) => html`
                                <div key=${i} style="display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);font-size:var(--text-sm);">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--profit)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;">
                                        <polyline points="20 6 9 17 4 12"/>
                                    </svg>
                                    <span style="color:var(--text-2);">${c}</span>
                                </div>
                            `)}
                        </div>
                    `}
                </div>
            `}

            ${state === 'INVALIDATED' && html`
                <div class="alert alert-error">
                    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    <div class="alert-content">
                        <div class="alert-title">Thesis Invalidated</div>
                        <div class="alert-desc">
                            The original trade thesis no longer holds. Consider closing this position using Force Sell below.
                        </div>
                    </div>
                </div>
            `}

            ${state === 'WARNING' && html`
                <div class="alert alert-warning">
                    <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    <div class="alert-content">
                        <div class="alert-title">Thesis Weakening</div>
                        <div class="alert-desc">
                            Some conditions have changed. Monitor this position closely. No action required yet.
                        </div>
                    </div>
                </div>
            `}
        </${Panel}>
    `
}