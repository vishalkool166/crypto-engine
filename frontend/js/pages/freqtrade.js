import { h, Fragment } from '/js/preact.min.js'
import { useState, useEffect, useRef } from '/js/preact-hooks.min.js'
import { html, GradeBadge, DirBadge, HealthBar, Spinner, EmptyState, LoadingSkeleton } from '/js/components.js'
import { useFtUpdate, showToast, requireTotp } from '/js/store.js'

export function FreqtradePage() {
    const ftData                              = useFtUpdate()
    const [loading,        setLoading]        = useState(false)
    const [openTrades,     setOpenTrades]     = useState([])
    const [profit,         setProfit]         = useState({})
    const [balance,        setBalance]        = useState({})
    const [botState,       setBotState]       = useState('unknown')
    const [daily,          setDaily]          = useState([])
    const [dailyDays,      setDailyDays]      = useState('7')
    const [dailyLoading,   setDailyLoading]   = useState(false)
    const [tradeHistory,   setTradeHistory]   = useState([])
    const [actionLoading,  setActionLoading]  = useState(null)
    const [forceSelling,   setForceSelling]   = useState(null)
    const [error,          setError]          = useState('')
    const chartRef = useRef(false)

    useEffect(() => {
        refresh()
        return () => {
            Charts.destroy('ft-daily-chart')
            chartRef.current = false
        }
    }, [])

    useEffect(() => {
        if (ftData.trades?.length)                    setOpenTrades(ftData.trades)
        if (ftData.profit?.trade_count != null)       setProfit(ftData.profit)
        if (ftData.balance?.total      != null)       setBalance(ftData.balance)
        if (ftData.botState && ftData.botState !== 'unknown') setBotState(ftData.botState)
    }, [ftData])

    useEffect(() => {
        if (!daily.length) return
        setTimeout(() => {
            const el = document.getElementById('ft-daily-chart')
            if (el && el.tagName === 'CANVAS' && el.offsetParent !== null) {
                Charts.dailyPnl('ft-daily-chart', daily)
                chartRef.current = true
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
            if (!res.ok) {
                setError('Freqtrade unavailable — check if container is running')
                return
            }
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
            if (data) {
                setTradeHistory(
                    Array.isArray(data.trades)
                        ? data.trades.filter(t => !t.is_open)
                        : []
                )
            }
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
            const arr = Array.isArray(raw) ? raw
                      : Array.isArray(raw.data) ? raw.data : []
            setDaily(arr.map(x => ({
                date:       x.date || x.day || '',
                profit_abs: parseFloat(x.profit_abs || x.profit || 0),
            })).filter(x => x.date))
        } catch(e) {
        } finally {
            setDailyLoading(false)
        }
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
        } finally {
            setActionLoading(null)
        }
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
        } finally {
            setActionLoading(null)
        }
    }

    async function forceSell(tradeId, pair) {
        const coin = (pair || '').replace('/USDT:USDT', '').replace('/USDT', '')
        const code = await requireTotp(
            'Force Sell — ' + coin,
            'Enter your TOTP code to confirm force sell of ' + coin
        )
        if (!code) return
        setForceSelling(tradeId)
        try {
            const res = await fetch('/api/ft/forcesell', {
                method:      'POST',
                credentials: 'include',
                headers:     { 'Content-Type': 'application/json' },
                body:        JSON.stringify({ tradeid: tradeId, totp_code: code })
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
                        <div class=${'ws-dot ' + (botState === 'running' ? '' : 'disconnected')}></div>
                        <span>Bot ${botState}</span>
                    </div>
                </div>
                <div class="flex gap-8">
                    <button class="btn btn-success btn-sm" onClick=${startBot}
                        disabled=${actionLoading === 'start' || botState === 'running'}>
                        ${actionLoading === 'start' ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="5 3 19 12 5 21 5 3"/>
                            </svg>
                        `}
                        Start
                    </button>
                    <button class="btn btn-danger btn-sm" onClick=${stopBot}
                        disabled=${actionLoading === 'stop' || botState === 'stopped'}>
                        ${actionLoading === 'stop' ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="3" width="18" height="18"/>
                            </svg>
                        `}
                        Stop
                    </button>
                    <button class="btn btn-ghost btn-sm" onClick=${refresh} disabled=${loading}>
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
                    <div class="card-sub">
                        ${profit.trade_count != null ? profit.trade_count + ' total trades' : '--'}
                    </div>
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
                                            ${forceSelling === trade.trade_id
                                                ? html`<${Spinner}/>`
                                                : 'Force Sell'
                                            }
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
                                        <div class="level-value" style="color:${Utils.pnlColor(pnl)};">
                                            ${Utils.fmtPrice(trade.current_rate)}
                                        </div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Stop Loss</div>
                                        <div class="level-value" style="color:var(--red);">
                                            ${trade.sl_signal ? Utils.fmtPrice(trade.sl_signal) : '--'}
                                        </div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Take Profit</div>
                                        <div class="level-value" style="color:var(--green);">
                                            ${trade.tp1 ? Utils.fmtPrice(trade.tp1) : '--'}
                                        </div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Open</div>
                                        <div class="level-value">${Utils.fmtDuration(trade.open_date)}</div>
                                    </div>
                                    <div class="level-item">
                                        <div class="level-label">Stake</div>
                                        <div class="level-value">
                                            ${trade.stake_amount ? '$' + parseFloat(trade.stake_amount).toFixed(2) : '--'}
                                        </div>
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
                        : html`<canvas id="ft-daily-chart" style="width:100%;height:160px;"></canvas>`
                    }
                </div>

                <div class="card">
                    <div class="section-title mb-12">Profit Summary</div>
                    ${[
                        { label: 'Total PnL',     val: profit.profit_all_coin != null ? Utils.fmtPnl(profit.profit_all_coin) : '--', color: Utils.pnlColor(profit.profit_all_coin) },
                        { label: 'Win Rate',      val: profit.winrate != null ? ((profit.winrate || 0) * 100).toFixed(1) + '%' : '--', color: Utils.winRateColor((profit.winrate || 0) * 100) },
                        { label: 'Total Trades',  val: profit.trade_count  != null ? profit.trade_count  : '--' },
                        { label: 'Profit Factor', val: profit.profit_factor != null ? parseFloat(profit.profit_factor).toFixed(2) : '--' },
                        { label: 'Best Pair',     val: profit.best_pair || '--' },
                        { label: 'Balance',       val: balance.total != null ? '$' + parseFloat(balance.total).toFixed(2) : '--', color: 'var(--blue)' },
                        { label: 'Free',          val: balance.free  != null ? '$' + parseFloat(balance.free).toFixed(2)  : '--' },
                    ].map(row => html`
                        <div key=${row.label} class="stat-row">
                            <span class="stat-label">${row.label}</span>
                            <span class="stat-value" style="font-family:var(--font-mono);${row.color ? 'color:' + row.color : ''}">
                                ${row.val}
                            </span>
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