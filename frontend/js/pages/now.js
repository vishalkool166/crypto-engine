var { h, Fragment } = preact
var { useState, useEffect, useRef, useCallback } = preactHooks
var html = window.html
var { useDashboard, useFtUpdate, showToast, navigate } = Store
var {
    GradeBadge, DirBadge, HealthDot, HealthRow,
    ScoreBar, ScoreRing, TradeProgressBar,
    Spinner, EmptyState, LoadingSkeleton,
    Panel, ConfluenceBar, InfoRow, RegimeBadge, SessionBadge
} = SE

function NowPage() {
    const data                          = useDashboard()
    const ftData                        = useFtUpdate()
    const [scanning,     setScanning]   = useState(false)
    const [activeTrades, setActiveTrades] = useState([])
    const [selectedSignal, setSelectedSignal] = useState(null)
    const [selectedTrade,  setSelectedTrade]  = useState(null)

    const summary = data.summary     || {}
    const queue   = data.signals?.queue || []
    const radar   = data.signals?.radar || []
    const history = data.history     || []

    const hero    = queue[0]    || null
    const rest    = queue.slice(1, 5)

    useEffect(() => {
        fetchTrades()
    }, [])

    useEffect(() => {
        if (ftData.trades?.length) setActiveTrades(ftData.trades)
    }, [ftData.trades])

    async function fetchTrades() {
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

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Now</div>
                    <div class="page-subtitle">
                        ${queue.length
                            ? queue.length + ' tradeable signal' + (queue.length > 1 ? 's' : '')
                            : 'Scanning market conditions'
                        }
                    </div>
                </div>
                <button class="btn btn-secondary btn-sm" onClick=${triggerScan}
                    disabled=${scanning}>
                    ${scanning
                        ? html`<${Spinner} size="xs"/>`
                        : html`<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`
                    }
                    ${scanning ? 'Scanning...' : 'Scan Now'}
                </button>
            </div>

            <div class="grid-3-2 mb-24" style="gap:20px;">
                <div style="display:flex;flex-direction:column;gap:16px;">
                    <${HeroSignal}
                        signal=${hero}
                        onOpen=${() => setSelectedSignal(hero)}
                    />
                    ${rest.length > 0 && html`
                        <div style="display:flex;flex-direction:column;gap:8px;">
                            <div class="section-header" style="margin-bottom:8px;">
                                <div class="section-title" style="font-size:var(--text-base);">
                                    Other Signals
                                </div>
                                <span class="tag">${rest.length}</span>
                            </div>
                            ${rest.map(sig => html`
                                <${SignalRow}
                                    key=${sig.coin}
                                    signal=${sig}
                                    onClick=${() => setSelectedSignal(sig)}
                                />
                            `)}
                        </div>
                    `}
                    <${ActivityFeed} history=${history}/>
                </div>

                <div style="display:flex;flex-direction:column;gap:16px;">
                    <${LivePositions}
                        trades=${activeTrades}
                        onOpen=${t => setSelectedTrade(t)}
                    />
                    <${MarketPulse} summary=${summary} radar=${radar}/>
                </div>
            </div>

            ${selectedSignal && html`
                <${SignalDetailPanel}
                    signal=${selectedSignal}
                    onClose=${() => setSelectedSignal(null)}
                />
            `}

            ${selectedTrade && html`
                <${TradeDetailPanel}
                    trade=${selectedTrade}
                    onClose=${() => setSelectedTrade(null)}
                    onRefresh=${fetchTrades}
                />
            `}
        </div>
    `
}

function HeroSignal({ signal, onOpen }) {
    if (!signal) return html`<${WatchingCard}/>`

    const grade     = signal.grade     || 'F'
    const coin      = signal.coin      || '--'
    const direction = signal.direction || '--'
    const score     = signal.score     || 0
    const thesis    = signal.thesis    || signal.confidence_label || ''
    const entry     = signal.entry
    const sl        = signal.sl
    const tp1       = signal.tp1
    const actualRr  = signal.actual_rr || 0
    const regime    = signal.regime    || ''
    const session   = signal.session   || ''
    const mlProb    = signal.ml_probability

    const slDist = entry && sl  ? Math.abs(entry - sl)  / entry * 100 : 0
    const tpDist = entry && tp1 ? Math.abs(tp1 - entry) / entry * 100 : 0
    const rrPct  = slDist > 0 ? Math.min(100, (tpDist / (slDist + tpDist)) * 100) : 50

    return html`
        <div class=${Utils.gradeHeroClass(grade)} onClick=${onOpen}
            role="button" tabindex="0"
            onKeyDown=${e => e.key === 'Enter' && onOpen()}
            aria-label=${'Open signal detail for ' + coin + 'USDT'}>
            <div class="signal-hero-body">
                <div class="signal-hero-top">
                    <div>
                        <div class="signal-hero-coin-row">
                            <span class="signal-hero-coin">${coin}USDT</span>
                            <${DirBadge} dir=${direction}/>
                            <${GradeBadge} grade=${grade} size="lg"/>
                        </div>
                        ${thesis && html`
                            <div class="signal-hero-thesis mt-8">"${thesis}"</div>
                        `}
                    </div>
                    <div style="flex-shrink:0;">
                        <${ScoreRing} score=${score} grade=${grade} size=${72}/>
                    </div>
                </div>

                ${entry && sl && tp1 && html`
                    <div class="signal-hero-levels">
                        <div class="signal-hero-level">
                            <div class="signal-hero-level-label">Entry</div>
                            <div class="signal-hero-level-value entry">
                                ${Utils.fmtPrice(entry)}
                            </div>
                        </div>
                        <div class="signal-hero-level">
                            <div class="signal-hero-level-label">Stop Loss</div>
                            <div class="signal-hero-level-value sl">
                                ${Utils.fmtPrice(sl)}
                            </div>
                        </div>
                        <div class="signal-hero-level">
                            <div class="signal-hero-level-label">Take Profit</div>
                            <div class="signal-hero-level-value tp">
                                ${Utils.fmtPrice(tp1)}
                            </div>
                        </div>
                    </div>
                `}

                ${entry && sl && tp1 && html`
                    <div>
                        <div class="rr-bar" style="height:5px;background:var(--surface-4);border-radius:var(--r-full);overflow:hidden;">
                            <div style=${'position:absolute;left:0;top:0;height:100%;width:' + (100 - rrPct) + '%;background:var(--loss-dim);border-radius:var(--r-full) 0 0 var(--r-full);'}></div>
                            <div style=${'position:absolute;right:0;top:0;height:100%;width:' + rrPct + '%;background:var(--profit-dim);border-radius:0 var(--r-full) var(--r-full) 0;'}></div>
                        </div>
                        <div class="flex justify-between mt-4" style="font-size:10px;">
                            <span style="color:var(--loss);font-family:var(--font-mono);">
                                SL ${slDist.toFixed(1)}%
                            </span>
                            <span style="color:var(--text-3);font-family:var(--font-mono);">
                                R:R 1:${actualRr}
                            </span>
                            <span style="color:var(--profit);font-family:var(--font-mono);">
                                TP ${tpDist.toFixed(1)}%
                            </span>
                        </div>
                    </div>
                `}

                <div class="signal-hero-footer">
                    <div class="signal-hero-factors">
                        ${regime  && html`<${RegimeBadge}  regime=${regime}/>`}
                        ${session && html`<${SessionBadge} session=${session}/>`}
                        ${mlProb != null && html`
                            <span class=${Utils.mlBadgeClass(mlProb)}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                                ${(mlProb * 100).toFixed(0)}%
                            </span>
                        `}
                    </div>
                    <div style="display:flex;align-items:center;gap:5px;font-size:var(--text-xs);color:var(--text-3);">
                        <span>Tap for details</span>
                        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                    </div>
                </div>
            </div>
        </div>
    `
}

function WatchingCard() {
    return html`
        <div class="signal-hero-card signal-hero-card-watching"
            style="cursor:default;">
            <div class="signal-hero-body" style="align-items:center;text-align:center;padding:40px 28px;">
                <div style="width:48px;height:48px;border-radius:var(--r-xl);background:var(--surface-3);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;color:var(--text-4);margin:0 auto;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                </div>
                <div style="font-size:var(--text-lg);font-weight:var(--weight-semibold);color:var(--text-2);margin-top:12px;">
                    No Tradeable Signals
                </div>
                <div style="font-size:var(--text-sm);color:var(--text-3);line-height:var(--leading-relaxed);max-width:280px;">
                    The bot is scanning every 15 minutes. Setups are building.
                </div>
            </div>
        </div>
    `
}

function SignalRow({ signal, onClick }) {
    const grade     = signal.grade     || 'F'
    const coin      = signal.coin      || '--'
    const direction = signal.direction || '--'
    const score     = signal.score     || 0
    const thesis    = signal.thesis    || ''
    const actualRr  = signal.actual_rr || 0

    const barColors = {
        'A+': 'var(--gold)',
        'A':  'var(--brand)',
        'B':  'var(--warning)',
        'C':  'var(--text-4)',
        'F':  'var(--surface-5)',
    }
    const barWidths = { 'A+': 4, 'A': 3, 'B': 2, 'C': 1, 'F': 1 }
    const barColor  = barColors[grade] || 'var(--surface-5)'
    const barWidth  = barWidths[grade] || 1

    return html`
        <div
            style=${'display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--surface-2);border-radius:var(--r-lg);border:1px solid var(--border);border-left:' + barWidth + 'px solid ' + barColor + ';cursor:pointer;transition:all var(--dur-fast) var(--ease-out);'}
            onClick=${onClick}
            role="button" tabindex="0"
            onKeyDown=${e => e.key === 'Enter' && onClick()}
            onMouseEnter=${e => e.currentTarget.style.background = 'var(--surface-3)'}
            onMouseLeave=${e => e.currentTarget.style.background = 'var(--surface-2)'}
        >
            <div style="flex:1;min-width:0;">
                <div class="flex items-center gap-8 mb-4">
                    <span style=${'font-family:var(--font-mono);font-size:var(--text-md);font-weight:var(--weight-heavy);color:var(--text-1);'}>
                        ${coin}USDT
                    </span>
                    <${DirBadge} dir=${direction}/>
                    <${GradeBadge} grade=${grade}/>
                </div>
                ${thesis && html`
                    <div style="font-size:var(--text-xs);color:var(--text-3);font-style:italic;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                        "${thesis}"
                    </div>
                `}
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0;">
                <span style=${'font-family:var(--font-mono);font-size:var(--text-sm);font-weight:var(--weight-heavy);color:' + Utils.scoreColor(score) + ';'}>
                    ${score}/100
                </span>
                <span style="font-family:var(--font-mono);font-size:10px;color:var(--text-4);">
                    R:R 1:${actualRr}
                </span>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--text-4);flex-shrink:0;"><polyline points="9 18 15 12 9 6"/></svg>
        </div>
    `
}

function LivePositions({ trades, onOpen }) {
    return html`
        <div class="card card-pad">
            <div class="section-header" style="margin-bottom:14px;">
                <div>
                    <div class="section-title">Live Positions</div>
                    <div class="section-subtitle">${trades.length} open</div>
                </div>
                ${trades.length > 0 && html`<span class="tag">${trades.length}</span>`}
            </div>

            ${!trades.length
                ? html`
                    <div style="padding:24px 0;text-align:center;">
                        <div style="font-size:var(--text-sm);color:var(--text-4);">No open positions</div>
                    </div>
                `
                : trades.map(trade => html`
                    <${LiveTradeRow}
                        key=${trade.trade_id}
                        trade=${trade}
                        onClick=${() => onOpen(trade)}
                    />
                `)
            }
        </div>
    `
}

function LiveTradeRow({ trade, onClick }) {
    const pair    = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir     = trade.is_short ? 'SHORT' : 'LONG'
    const pnl     = parseFloat(trade.profit_abs || 0)
    const pnlPos  = pnl >= 0
    const pnlPct  = parseFloat(trade.profit_ratio || 0) * 100
    const health  = trade.health
    const state   = health?.state || 'UNKNOWN'

    const healthColors = {
        'HEALTHY':     'var(--profit)',
        'WARNING':     'var(--warning)',
        'INVALIDATED': 'var(--loss)',
    }
    const borderColor = healthColors[state] || 'var(--border)'

    return html`
        <div
            style=${'display:flex;flex-direction:column;gap:8px;padding:12px 0;border-bottom:1px solid var(--border);cursor:pointer;'}
            onClick=${onClick}
            onMouseEnter=${e => e.currentTarget.style.background = 'var(--surface-3)'}
            onMouseLeave=${e => e.currentTarget.style.background = ''}
            role="button" tabindex="0"
            onKeyDown=${e => e.key === 'Enter' && onClick()}
        >
            <div class="flex justify-between items-center">
                <div class="flex items-center gap-8">
                    <div style=${'width:3px;height:32px;border-radius:var(--r-full);background:' + borderColor + ';flex-shrink:0;'}></div>
                    <div>
                        <div class="flex items-center gap-6">
                            <span style="font-family:var(--font-mono);font-size:var(--text-base);font-weight:var(--weight-heavy);color:var(--text-1);">
                                ${pair}
                            </span>
                            <${DirBadge} dir=${dir}/>
                        </div>
                        <div style="font-size:var(--text-xs);color:var(--text-4);margin-top:2px;">
                            ${Utils.fmtDuration(trade.open_date)} open
                        </div>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div class=${'pnl-value ' + (pnlPos ? 'positive' : 'negative')}
                        style="font-size:var(--text-lg);">
                        ${Utils.fmtPnl(pnl, pnlPos)}
                    </div>
                    <div style=${'font-family:var(--font-mono);font-size:var(--text-xs);color:' + (pnlPos ? 'var(--profit)' : 'var(--loss)') + ';'}>
                        ${Utils.fmtPct(pnlPct)}
                    </div>
                </div>
            </div>
            <${TradeProgressBar} trade=${trade}/>
        </div>
    `
}

function MarketPulse({ summary, radar }) {
    const topCoins = radar.slice(0, 5)

    return html`
        <div class="card card-pad">
            <div class="section-title mb-12">Market Pulse</div>
            ${[
                { label: 'Win Rate',    val: (summary.win_rate || 0) + '%',    color: Utils.winRateColor(summary.win_rate) },
                { label: 'Today PnL',  val: Utils.fmtPnl(summary.today_pnl, summary.today_pnl_pos), color: Utils.pnlColor(summary.today_pnl_pos) },
                { label: 'Scanning',   val: (summary.coins_count || 0) + ' coins' },
                { label: 'Tradeable',  val: (summary.tradeable_count || 0) + ' now', color: summary.tradeable_count > 0 ? 'var(--profit)' : 'var(--text-3)' },
            ].map(row => html`
                <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                    mono=${true} color=${row.color}/>
            `)}
            ${topCoins.length > 0 && html`
                <div class="divider"></div>
                <div style="font-size:var(--text-xs);font-weight:var(--weight-semibold);color:var(--text-3);text-transform:uppercase;letter-spacing:var(--tracking-widest);margin-bottom:10px;">
                    Top Coins
                </div>
                ${topCoins.map(coin => html`
                    <div key=${coin.coin} class="flex justify-between items-center"
                        style="padding:6px 0;border-bottom:1px solid var(--border);">
                        <div class="flex items-center gap-8">
                            <span style="font-family:var(--font-mono);font-size:var(--text-sm);font-weight:var(--weight-bold);color:var(--text-1);">
                                ${coin.coin}
                            </span>
                            <${GradeBadge} grade=${coin.grade}/>
                        </div>
                        <div class="flex items-center gap-8">
                            <${ScoreBar} score=${coin.score} grade=${coin.grade}/>
                            <span style=${'font-family:var(--font-mono);font-size:10px;color:' + Utils.changeColor(coin.change) + ';'}>
                                ${Utils.fmtPct(coin.change)}
                            </span>
                        </div>
                    </div>
                `)}
            `}
        </div>
    `
}

function ActivityFeed({ history }) {
    if (!history.length) return null

    return html`
        <div class="card card-pad">
            <div class="section-title mb-12">Recent Activity</div>
            ${history.slice(0, 8).map(s => html`
                <div key=${s.id} class="activity-item">
                    <div class=${'activity-dot activity-dot-' + (s.outcome === 'win' ? 'trade' : s.outcome === 'loss' ? 'error' : 'scan')}></div>
                    <div class="activity-content">
                        <div class="activity-text">
                            <span style="font-family:var(--font-mono);font-weight:var(--weight-bold);color:var(--text-1);">
                                ${s.coin}USDT
                            </span>
                            ${' '}${s.direction}
                            ${' '}Grade ${s.grade}
                            ${s.pnl != null && html`
                                ${' '}—${' '}
                                <span style=${'color:' + Utils.pnlColor(s.pnl_pos) + ';font-family:var(--font-mono);font-weight:var(--weight-bold);'}>
                                    ${Utils.fmtPnl(s.pnl, s.pnl_pos)}
                                </span>
                            `}
                        </div>
                        <div class="activity-time">${Utils.fmtTimeAgo(s.timestamp)}</div>
                    </div>
                </div>
            `)}
        </div>
    `
}

function SignalDetailPanel({ signal, onClose }) {
    const [detail,  setDetail]  = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!signal?.coin) return
        setLoading(true)
        API.dashboardCoin(signal.coin).then(d => {
            setDetail(d)
            setLoading(false)
        }).catch(() => setLoading(false))
    }, [signal?.coin])

    const coin      = signal?.coin      || '--'
    const grade     = signal?.grade     || detail?.grade     || '--'
    const direction = signal?.direction || detail?.direction || '--'
    const score     = signal?.score     || detail?.score     || 0
    const thesis    = detail?.thesis    || signal?.thesis    || ''
    const factors   = detail?.factors   || []
    const sig       = detail?.signal    || {}
    const market    = detail?.market    || {}
    const mlProb    = detail?.ml_probability ?? signal?.ml_probability
    const actualRr  = detail?.actual_rr ?? signal?.actual_rr ?? 0
    const regime    = detail?.regime    || signal?.regime    || ''
    const session   = detail?.session   || signal?.session   || ''

    const entry  = sig.entry  || signal?.entry
    const sl     = sig.sl     || signal?.sl
    const tp1    = sig.tp1    || signal?.tp1
    const slPct  = sig.sl_pct || 0
    const stake  = sig.stake  || signal?.stake  || 0
    const lev    = sig.leverage || signal?.leverage || 10
    const risk   = sig.risk_amt || signal?.risk_amt || 0

    return html`
        <${Panel}
            show=${true}
            onClose=${onClose}
            title=${coin + 'USDT'}
            subtitle=${'Signal Detail'}
        >
            <div class="panel-section">
                <div class="flex items-center gap-10 flex-wrap">
                    <${GradeBadge} grade=${grade} size="lg"/>
                    <${DirBadge} dir=${direction}/>
                    ${regime  && html`<${RegimeBadge}  regime=${regime}/>`}
                    ${session && html`<${SessionBadge} session=${session}/>`}
                </div>

                <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px;background:var(--surface-3);border-radius:var(--r-lg);border:1px solid var(--border);">
                    <div>
                        <div style="font-size:var(--text-xs);color:var(--text-3);text-transform:uppercase;letter-spacing:var(--tracking-widest);font-weight:var(--weight-semibold);margin-bottom:4px;">
                            Confluence Score
                        </div>
                        <div style=${'font-family:var(--font-mono);font-size:var(--text-3xl);font-weight:var(--weight-black);color:' + Utils.scoreColor(score) + ';letter-spacing:var(--tracking-snug);'}>
                            ${score}<span style="font-size:var(--text-lg);color:var(--text-4);">/100</span>
                        </div>
                    </div>
                    <${ScoreRing} score=${score} grade=${grade} size=${72}/>
                </div>
            </div>

            ${thesis && html`
                <div class="panel-section">
                    <div class="panel-section-title">Thesis</div>
                    <div style="font-size:var(--text-sm);color:var(--text-2);line-height:var(--leading-relaxed);font-style:italic;padding:14px 16px;background:var(--surface-3);border-radius:var(--r-lg);border-left:3px solid var(--brand);">
                        "${thesis}"
                    </div>
                </div>
            `}

            ${entry && sl && tp1 && html`
                <div class="panel-section">
                    <div class="panel-section-title">Levels</div>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;">
                        ${[
                            { label: 'Entry',       val: Utils.fmtPrice(entry), color: 'var(--text-1)'  },
                            { label: 'Stop Loss',   val: Utils.fmtPrice(sl),    color: 'var(--loss)'    },
                            { label: 'Take Profit', val: Utils.fmtPrice(tp1),   color: 'var(--profit)'  },
                        ].map(l => html`
                            <div key=${l.label} style="background:var(--surface-3);border-radius:var(--r-md);padding:12px;border:1px solid var(--border);">
                                <div style="font-size:10px;color:var(--text-4);text-transform:uppercase;letter-spacing:var(--tracking-widest);font-weight:var(--weight-semibold);margin-bottom:5px;">
                                    ${l.label}
                                </div>
                                <div style=${'font-family:var(--font-mono);font-size:var(--text-md);font-weight:var(--weight-heavy);color:' + l.color + ';'}>
                                    ${l.val}
                                </div>
                            </div>
                        `)}
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:var(--text-xs);color:var(--text-3);padding:0 2px;">
                        <span style="font-family:var(--font-mono);">SL ${slPct.toFixed(2)}%</span>
                        <span style="font-family:var(--font-mono);color:var(--text-2);">R:R 1:${actualRr}</span>
                    </div>
                </div>
            `}

            <div class="panel-section">
                <div class="panel-section-title">Execution</div>
                ${[
                    { label: 'Stake',      val: stake ? '$' + parseFloat(stake).toFixed(2) : '--' },
                    { label: 'Leverage',   val: lev + 'x',  color: 'var(--brand)' },
                    { label: 'Risk',       val: risk ? '$' + parseFloat(risk).toFixed(2) : '--' },
                    { label: 'ML Gate',    val: mlProb != null ? (mlProb * 100).toFixed(1) + '%' : 'N/A', color: mlProb != null ? (mlProb >= 0.65 ? 'var(--profit)' : 'var(--loss)') : null },
                ].map(row => html`
                    <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                        mono=${true} color=${row.color}/>
                `)}
            </div>

            ${loading && html`<${LoadingSkeleton} rows=${4}/>`}

            ${!loading && factors.length > 0 && html`
                <div class="panel-section">
                    <div class="panel-section-title">
                        Confluence — ${score}/100
                    </div>
                    ${factors.map(f => html`
                        <${ConfluenceBar} key=${f.key} factor=${f}/>
                    `)}
                </div>
            `}

            ${!loading && market && html`
                <div class="panel-section">
                    <div class="panel-section-title">Market</div>
                    ${[
                        { label: 'Price',       val: Utils.fmtPrice(market.price) },
                        { label: '24h Change',  val: Utils.fmtPct(market.change), color: Utils.changeColor(market.change) },
                        { label: 'Funding',     val: market.funding != null ? market.funding.toFixed(4) + '%' : '--', color: Math.abs(market.funding || 0) > 0.05 ? 'var(--loss)' : null },
                        { label: 'Long Ratio',  val: market.long_ratio  != null ? market.long_ratio  + '%' : '--', color: (market.long_ratio  || 0) > 65 ? 'var(--loss)' : null },
                        { label: 'Short Ratio', val: market.short_ratio != null ? market.short_ratio + '%' : '--' },
                        { label: 'OI Change',   val: market.oi_change   != null ? market.oi_change   + '%' : '--' },
                    ].map(row => html`
                        <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                            mono=${true} color=${row.color}/>
                    `)}
                </div>
            `}
        </${Panel}>
    `
}

function TradeDetailPanel({ trade, onClose, onRefresh }) {
    const [loading,      setLoading]      = useState(false)
    const [forceSelling, setForceSelling] = useState(false)

    const pair    = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const coin    = (trade.pair || '').replace('/USDT:USDT', '').replace('/USDT', '')
    const dir     = trade.is_short ? 'SHORT' : 'LONG'
    const pnl     = parseFloat(trade.profit_abs || 0)
    const pnlPos  = pnl >= 0
    const pnlPct  = parseFloat(trade.profit_ratio || 0) * 100
    const health  = trade.health
    const state   = health?.state || 'UNKNOWN'

    async function handleForceSell() {
        const code = await Store.requireTotp(
            'Force Sell — ' + pair,
            'This will immediately close your ' + pair + ' position at market price.'
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
            subtitle=${'Trade #' + trade.trade_id}
            footer=${html`
                <button class="btn btn-danger-solid btn-full"
                    onClick=${handleForceSell}
                    disabled=${forceSelling}>
                    ${forceSelling ? html`<${Spinner} size="xs" color="white"/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    `}
                    ${forceSelling ? 'Closing...' : 'Force Sell — Requires TOTP'}
                </button>
            `}
        >
            <div class="panel-section">
                <div class="flex items-center gap-10 flex-wrap">
                    <${DirBadge} dir=${dir}/>
                    <${HealthRow} health=${health}/>
                </div>

                <div style="display:flex;align-items:center;justify-content:space-between;padding:16px;background:var(--surface-3);border-radius:var(--r-lg);border:1px solid var(--border);">
                    <div>
                        <div style="font-size:var(--text-xs);color:var(--text-3);text-transform:uppercase;letter-spacing:var(--tracking-widest);font-weight:var(--weight-semibold);margin-bottom:4px;">
                            Unrealized PnL
                        </div>
                        <div class=${'pnl-value ' + (pnlPos ? 'positive' : 'negative')}
                            style="font-size:var(--text-3xl);">
                            ${Utils.fmtPnl(pnl, pnlPos)}
                        </div>
                        <div style=${'font-family:var(--font-mono);font-size:var(--text-sm);color:' + (pnlPos ? 'var(--profit)' : 'var(--loss)') + ';margin-top:2px;'}>
                            ${Utils.fmtPct(pnlPct)}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:var(--text-xs);color:var(--text-3);margin-bottom:4px;">Open</div>
                        <div style="font-family:var(--font-mono);font-size:var(--text-md);font-weight:var(--weight-bold);color:var(--text-1);">
                            ${Utils.fmtDuration(trade.open_date)}
                        </div>
                    </div>
                </div>

                <${TradeProgressBar} trade=${trade}/>
            </div>

            <div class="panel-section">
                <div class="panel-section-title">Levels</div>
                ${[
                    { label: 'Entry',        val: Utils.fmtPrice(trade.open_rate)  },
                    { label: 'Current',      val: Utils.fmtPrice(trade.current_rate), color: pnlPos ? 'var(--profit)' : 'var(--loss)' },
                    { label: 'Stop Loss',    val: Utils.fmtPrice(trade.sl_signal || trade.stop_loss_abs), color: 'var(--loss)'   },
                    { label: 'Take Profit',  val: Utils.fmtPrice(trade.tp1),        color: 'var(--profit)' },
                    { label: 'Stake',        val: '$' + parseFloat(trade.stake_amount || 0).toFixed(2) },
                    { label: 'Leverage',     val: (trade.leverage || '--') + 'x',   color: 'var(--brand)'  },
                    { label: 'Tag',          val: trade.enter_tag || '--' },
                ].map(row => html`
                    <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                        mono=${true} color=${row.color}/>
                `)}
            </div>

            ${health && html`
                <div class="panel-section">
                    <div class="panel-section-title">Health Checks</div>
                    ${health.checks?.map((c, i) => html`
                        <div key=${i} style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);font-size:var(--text-sm);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--profit)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;"><polyline points="20 6 9 17 4 12"/></svg>
                            <span style="color:var(--text-2);">${c}</span>
                        </div>
                    `)}
                    ${health.warnings?.map((w, i) => html`
                        <div key=${'w' + i} style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);font-size:var(--text-sm);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                            <span style="color:var(--text-2);">${w}</span>
                        </div>
                    `)}
                    ${health.failures?.map((f, i) => html`
                        <div key=${'f' + i} style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);font-size:var(--text-sm);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--loss)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                            <span style="color:var(--text-2);">${f}</span>
                        </div>
                    `)}
                </div>
            `}
        </${Panel}>
    `
}