var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { useDashboard, useFtUpdate, showToast, on } = Store
var {
    GradeBadge, DirBadge, HealthDot, HealthRow,
    ScoreBar, ScoreRing, TradeProgressBar,
    Spinner, EmptyState, LoadingSkeleton,
    Panel, ConfluenceBar, InfoRow, RegimeBadge, SessionBadge
} = SE

function ThesisBlock({ thesis }) {
    if (!thesis) return null

    const lines = thesis
        .split(/(?=[✔⚠✗])/)
        .map(s => s.trim())
        .filter(Boolean)

    if (lines.length <= 1) {
        return html`
            <div style="font-size:var(--text-subhead);color:var(--label-2);line-height:var(--leading-relaxed);font-style:italic;padding:12px 14px;background:var(--fill-4);border-radius:var(--r-lg);letter-spacing:var(--tracking-subhead);">
                ${thesis}
            </div>
        `
    }

    return html`
        <div style="display:flex;flex-direction:column;gap:5px;">
            ${lines.map((line, i) => {
                const isPass = line.startsWith('✔')
                const isWarn = line.startsWith('⚠')
                const isFail = line.startsWith('✗')
                const color  = isPass ? 'var(--profit)'
                             : isWarn ? 'var(--warning)'
                             : isFail ? 'var(--loss)'
                             : 'var(--label-2)'
                const bg     = isPass ? 'var(--profit-subtle)'
                             : isWarn ? 'var(--warning-subtle)'
                             : isFail ? 'var(--loss-subtle)'
                             : 'var(--fill-4)'
                const border = isPass ? '0.5px solid var(--profit-border)'
                             : isWarn ? '0.5px solid var(--warning-border)'
                             : isFail ? '0.5px solid var(--loss-border)'
                             : '0.5px solid var(--separator)'
                return html`
                    <div key=${i} style=${'display:flex;align-items:flex-start;gap:8px;padding:8px 12px;background:' + bg + ';border:' + border + ';border-radius:var(--r-md);'}>
                        <span style=${'font-size:var(--text-footnote);flex-shrink:0;margin-top:1px;color:' + color + ';'}>
                            ${line[0]}
                        </span>
                        <span style="font-size:var(--text-footnote);color:var(--label-2);line-height:var(--leading-snug);letter-spacing:var(--tracking-footnote);">
                            ${line.slice(1).trim()}
                        </span>
                    </div>
                `
            })}
        </div>
    `
}

function NowPage({ externalSignal, onSignalConsumed }) {
    const data                                = useDashboard()
    const ftData                              = useFtUpdate()
    const [scanning,      setScanning]        = useState(false)
    const [activeTrades,  setActiveTrades]    = useState([])
    const [selectedSignal,setSelectedSignal]  = useState(null)
    const [selectedTrade, setSelectedTrade]   = useState(null)

    const summary = data.summary        || {}
    const queue   = data.signals?.queue || []
    const radar   = data.signals?.radar || []
    const history = data.history        || []
    const hero    = queue[0]            || null
    const rest    = queue.slice(1, 5)

    useEffect(() => { fetchTrades() }, [])

    useEffect(() => {
        if (ftData.trades?.length) setActiveTrades(ftData.trades)
    }, [ftData.trades])

    useEffect(() => {
        if (externalSignal) {
            setSelectedSignal(externalSignal)
            if (onSignalConsumed) onSignalConsumed()
        }
    }, [externalSignal])

    useEffect(() => {
        const unsub = on('topbar:open-signal', signal => {
            setSelectedSignal(signal)
        })
        return unsub
    }, [])

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
                        : html`<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`
                    }
                    ${scanning ? 'Scanning...' : 'Scan Now'}
                </button>
            </div>

            <div class="grid-3-2 mb-24" style="gap:16px;">
                <div style="display:flex;flex-direction:column;gap:12px;">
                    <${HeroSignal}
                        signal=${hero}
                        onOpen=${() => setSelectedSignal(hero)}
                    />
                    ${rest.length > 0 && html`
                        <div style="display:flex;flex-direction:column;gap:8px;">
                            <div class="section-header" style="margin-bottom:4px;">
                                <div class="section-title">Other Signals</div>
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

                <div style="display:flex;flex-direction:column;gap:12px;">
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
                            <div class="signal-hero-level-value entry">${Utils.fmtPrice(entry)}</div>
                        </div>
                        <div class="signal-hero-level">
                            <div class="signal-hero-level-label">Stop Loss</div>
                            <div class="signal-hero-level-value sl">${Utils.fmtPrice(sl)}</div>
                        </div>
                        <div class="signal-hero-level">
                            <div class="signal-hero-level-label">Take Profit</div>
                            <div class="signal-hero-level-value tp">${Utils.fmtPrice(tp1)}</div>
                        </div>
                    </div>
                `}

                ${entry && sl && tp1 && html`
                    <div>
                        <div style="position:relative;height:5px;background:var(--fill-3);border-radius:var(--r-full);overflow:hidden;">
                            <div style=${'position:absolute;left:0;top:0;height:100%;width:' + (100 - rrPct) + '%;background:var(--loss-dim);border-radius:var(--r-full) 0 0 var(--r-full);'}></div>
                            <div style=${'position:absolute;right:0;top:0;height:100%;width:' + rrPct + '%;background:var(--profit-dim);border-radius:0 var(--r-full) var(--r-full) 0;'}></div>
                        </div>
                        <div class="flex justify-between mt-4" style="font-size:10px;">
                            <span style="color:var(--loss);font-family:var(--font-mono);">SL ${slDist.toFixed(1)}%</span>
                            <span style="color:var(--label-3);font-family:var(--font-mono);">R:R 1:${actualRr}</span>
                            <span style="color:var(--profit);font-family:var(--font-mono);">TP ${tpDist.toFixed(1)}%</span>
                        </div>
                    </div>
                `}

                <div class="signal-hero-footer">
                    <div class="signal-hero-factors">
                        ${regime  && regime  !== '--' && html`<${RegimeBadge}  regime=${regime}/>`}
                        ${session && session !== '--' && html`<${SessionBadge} session=${session}/>`}
                        ${mlProb != null && html`
                            <span class=${Utils.mlBadgeClass(mlProb)}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                                ${(mlProb * 100).toFixed(0)}%
                            </span>
                        `}
                    </div>
                    <div style="display:flex;align-items:center;gap:4px;font-size:var(--text-caption1);color:var(--label-3);">
                        <span>Details</span>
                        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                    </div>
                </div>
            </div>
        </div>
    `
}

function WatchingCard() {
    return html`
        <div class="signal-hero-card signal-hero-card-watching" style="cursor:default;">
            <div class="signal-hero-body" style="align-items:center;text-align:center;padding:40px 20px;">
                <div style="width:44px;height:44px;border-radius:var(--r-xl);background:var(--fill-3);display:flex;align-items:center;justify-content:center;color:var(--label-4);margin:0 auto;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                </div>
                <div style="font-size:var(--text-title3);font-weight:var(--weight-semibold);color:var(--label-2);margin-top:12px;letter-spacing:var(--tracking-title3);">
                    No Tradeable Signals
                </div>
                <div style="font-size:var(--text-subhead);color:var(--label-3);line-height:var(--leading-relaxed);max-width:260px;margin-top:6px;letter-spacing:var(--tracking-subhead);">
                    Scanning every 15 minutes. Setups are building.
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
    const session   = signal.session   || ''

    const accentColors = {
        'A+': 'var(--grade-aplus)',
        'A':  'var(--grade-a)',
        'B':  'var(--grade-b)',
        'C':  'var(--fill-1)',
        'F':  'var(--fill-2)',
    }
    const accent = accentColors[grade] || 'var(--fill-2)'

    return html`
        <div
            style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:rgba(28,28,30,0.60);border:0.5px solid rgba(255,255,255,0.06);border-radius:var(--r-2xl);cursor:pointer;transition:opacity var(--dur-fast) var(--ease-out),transform var(--dur-fast) var(--ease-spring);position:relative;overflow:hidden;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);"
            onClick=${onClick}
            role="button" tabindex="0"
            onKeyDown=${e => e.key === 'Enter' && onClick()}
            onMouseEnter=${e => { e.currentTarget.style.opacity = '0.92'; e.currentTarget.style.transform = 'translateY(-1px)' }}
            onMouseLeave=${e => { e.currentTarget.style.opacity = '1';    e.currentTarget.style.transform = 'translateY(0)'    }}
        >
            <div style=${'position:absolute;top:0;left:0;right:0;height:2px;background:' + accent + ';border-radius:var(--r-2xl) var(--r-2xl) 0 0;opacity:0.8;'}></div>
            <div style="flex:1;min-width:0;margin-top:4px;">
                <div class="flex items-center gap-8 mb-4">
                    <span style="font-family:var(--font-mono);font-size:var(--text-title3);font-weight:var(--weight-heavy);color:var(--label-1);letter-spacing:-0.025em;">
                        ${coin}USDT
                    </span>
                    <${DirBadge} dir=${direction}/>
                    <${GradeBadge} grade=${grade}/>
                    ${session && session !== '--' && html`<${SessionBadge} session=${session}/>`}
                </div>
                ${thesis && html`
                    <div style="font-size:var(--text-caption1);color:var(--label-3);font-style:italic;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;letter-spacing:var(--tracking-caption1);">
                        "${thesis}"
                    </div>
                `}
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0;">
                <span style=${'font-family:var(--font-mono);font-size:var(--text-subhead);font-weight:var(--weight-heavy);color:' + Utils.scoreColor(score) + ';letter-spacing:var(--tracking-mono);'}>
                    ${score}/100
                </span>
                <span style="font-family:var(--font-mono);font-size:10px;color:var(--label-4);">
                    R:R 1:${actualRr}
                </span>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--label-4);flex-shrink:0;"><polyline points="9 18 15 12 9 6"/></svg>
        </div>
    `
}

function LivePositions({ trades, onOpen }) {
    return html`
        <div class="card card-pad">
            <div class="section-header" style="margin-bottom:12px;">
                <div>
                    <div class="section-title">Live Positions</div>
                    <div class="section-subtitle">${trades.length} open</div>
                </div>
                ${trades.length > 0 && html`<span class="tag">${trades.length}</span>`}
            </div>

            ${!trades.length
                ? html`
                    <div style="padding:20px 0;text-align:center;">
                        <div style="font-size:var(--text-subhead);color:var(--label-4);letter-spacing:var(--tracking-subhead);">No open positions</div>
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
    const pair   = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir    = trade.is_short ? 'SHORT' : 'LONG'
    const pnl    = parseFloat(trade.profit_abs || 0)
    const pnlPos = pnl >= 0
    const pnlPct = parseFloat(trade.profit_ratio || 0) * 100
    const health = trade.health
    const state  = health?.state || 'UNKNOWN'

    const accentColors = {
        'HEALTHY':     'var(--profit)',
        'WARNING':     'var(--warning)',
        'INVALIDATED': 'var(--loss)',
    }
    const accent = accentColors[state] || 'var(--fill-1)'

    return html`
        <div
            style="display:flex;flex-direction:column;gap:8px;padding:12px 8px;border-bottom:0.5px solid var(--separator);cursor:pointer;transition:background var(--dur-fast) var(--ease-out);border-radius:var(--r-md);"
            onClick=${onClick}
            onMouseEnter=${e => e.currentTarget.style.background = 'var(--fill-5)'}
            onMouseLeave=${e => e.currentTarget.style.background = ''}
            role="button" tabindex="0"
            onKeyDown=${e => e.key === 'Enter' && onClick()}
        >
            <div class="flex justify-between items-center">
                <div class="flex items-center gap-8">
                    <div style=${'width:3px;height:32px;border-radius:var(--r-full);background:' + accent + ';flex-shrink:0;'}></div>
                    <div>
                        <div class="flex items-center gap-6">
                            <span style="font-family:var(--font-mono);font-size:var(--text-subhead);font-weight:var(--weight-heavy);color:var(--label-1);letter-spacing:-0.02em;">
                                ${pair}
                            </span>
                            <${DirBadge} dir=${dir}/>
                        </div>
                        <div style="font-size:var(--text-caption2);color:var(--label-4);margin-top:2px;letter-spacing:var(--tracking-caption2);">
                            ${Utils.fmtDuration(trade.open_date)} open
                        </div>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div class=${'pnl-value ' + (pnlPos ? 'positive' : 'negative')}
                        style="font-size:var(--text-title3);">
                        ${Utils.fmtPnl(pnl, pnlPos)}
                    </div>
                    <div style=${'font-family:var(--font-mono);font-size:var(--text-caption1);color:' + (pnlPos ? 'var(--profit)' : 'var(--loss)') + ';font-variant-numeric:tabular-nums;'}>
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
    const session  = Utils.currentSession()

    const sessionColor = session.quality === 'best'    ? 'var(--session-london-ny)'
                       : session.quality === 'good'    ? 'var(--session-ny)'
                       : session.quality === 'caution' ? 'var(--session-asian)'
                       : 'var(--label-4)'

    return html`
        <div class="card card-pad">
            <div class="section-title mb-12">Market Pulse</div>
            ${[
                { label: 'Session',   val: session.label,                                                         color: sessionColor },
                { label: 'Win Rate',  val: (summary.win_rate || 0) + '%',                                         color: Utils.winRateColor(summary.win_rate) },
                { label: 'Today PnL', val: Utils.fmtPnl(summary.today_pnl, summary.today_pnl_pos),               color: Utils.pnlColor(summary.today_pnl_pos) },
                { label: 'Scanning',  val: (summary.coins_count || 0) + ' coins' },
                { label: 'Tradeable', val: (summary.tradeable_count || 0) + ' now',                               color: summary.tradeable_count > 0 ? 'var(--profit)' : 'var(--label-3)' },
            ].map(row => html`
                <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                    mono=${true} color=${row.color}/>
            `)}
            ${topCoins.length > 0 && html`
                <div class="divider"></div>
                <div class="label-uppercase mb-10">Top Coins</div>
                ${topCoins.map(coin => html`
                    <div key=${coin.coin} class="flex justify-between items-center"
                        style="padding:6px 0;border-bottom:0.5px solid var(--separator);">
                        <div class="flex items-center gap-8">
                            <span style="font-family:var(--font-mono);font-size:var(--text-subhead);font-weight:var(--weight-bold);color:var(--label-1);letter-spacing:-0.02em;">
                                ${coin.coin}
                            </span>
                            <${GradeBadge} grade=${coin.grade}/>
                        </div>
                        <div class="flex items-center gap-8">
                            <${ScoreBar} score=${coin.score} grade=${coin.grade}/>
                            <span style=${'font-family:var(--font-mono);font-size:10px;color:' + Utils.changeColor(coin.change) + ';font-variant-numeric:tabular-nums;'}>
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
                            <span style="font-family:var(--font-mono);font-weight:var(--weight-bold);color:var(--label-1);">
                                ${s.coin}USDT
                            </span>
                            ${' '}${s.direction}
                            ${' '}Grade ${s.grade}
                            ${s.pnl != null && html`
                                ${' '}—${' '}
                                <span style=${'color:' + Utils.pnlColor(s.pnl_pos) + ';font-family:var(--font-mono);font-weight:var(--weight-bold);font-variant-numeric:tabular-nums;'}>
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
            subtitle="Signal Detail"
        >
            <div class="panel-section">
                <div class="flex items-center gap-8 flex-wrap">
                    <${GradeBadge} grade=${grade} size="lg"/>
                    <${DirBadge} dir=${direction}/>
                    ${regime  && regime  !== '--' && html`<${RegimeBadge}  regime=${regime}/>`}
                    ${session && session !== '--' && html`<${SessionBadge} session=${session}/>`}
                </div>

                <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px;background:var(--fill-4);border-radius:var(--r-xl);border:0.5px solid var(--separator);">
                    <div>
                        <div class="label-uppercase mb-4">Confluence Score</div>
                        <div style=${'font-family:var(--font-mono);font-size:var(--text-largetitle);font-weight:var(--weight-black);color:' + Utils.scoreColor(score) + ';letter-spacing:-0.03em;font-variant-numeric:tabular-nums;'}>
                            ${score}<span style="font-size:var(--text-title3);color:var(--label-4);">/100</span>
                        </div>
                    </div>
                    <${ScoreRing} score=${score} grade=${grade} size=${72}/>
                </div>
            </div>

            ${thesis && html`
                <div class="panel-section">
                    <div class="panel-section-title">Thesis</div>
                    <${ThesisBlock} thesis=${thesis}/>
                </div>
            `}

            ${entry && sl && tp1 && html`
                <div class="panel-section">
                    <div class="panel-section-title">Levels</div>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;">
                        ${[
                            { label: 'Entry',       val: Utils.fmtPrice(entry), color: 'var(--label-1)'  },
                            { label: 'Stop Loss',   val: Utils.fmtPrice(sl),    color: 'var(--loss)'     },
                            { label: 'Take Profit', val: Utils.fmtPrice(tp1),   color: 'var(--profit)'   },
                        ].map(l => html`
                            <div key=${l.label} style="background:var(--fill-4);border:0.5px solid var(--separator);border-radius:var(--r-md);padding:10px 12px;">
                                <div class="label-uppercase mb-4">${l.label}</div>
                                <div style=${'font-family:var(--font-mono);font-size:var(--text-callout);font-weight:var(--weight-heavy);color:' + l.color + ';letter-spacing:var(--tracking-mono);font-variant-numeric:tabular-nums;'}>
                                    ${l.val}
                                </div>
                            </div>
                        `)}
                    </div>
                    <div class="flex justify-between" style="font-size:10px;color:var(--label-3);padding:0 2px;">
                        <span style="font-family:var(--font-mono);">SL ${slPct.toFixed(2)}%</span>
                        <span style="font-family:var(--font-mono);color:var(--label-2);">R:R 1:${actualRr}</span>
                    </div>
                </div>
            `}

            <div class="panel-section">
                <div class="panel-section-title">Execution</div>
                ${[
                    { label: 'Stake',    val: stake ? '$' + parseFloat(stake).toFixed(2) : '--' },
                    { label: 'Leverage', val: lev + 'x',  color: 'var(--brand)' },
                    { label: 'Risk',     val: risk ? '$' + parseFloat(risk).toFixed(2) : '--' },
                    { label: 'ML Gate',  val: mlProb != null ? (mlProb * 100).toFixed(1) + '%' : 'N/A', color: mlProb != null ? (mlProb >= 0.65 ? 'var(--profit)' : 'var(--loss)') : null },
                ].map(row => html`
                    <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                        mono=${true} color=${row.color}/>
                `)}
            </div>

            ${loading && html`<${LoadingSkeleton} rows=${4}/>`}

            ${!loading && factors.length > 0 && html`
                <div class="panel-section">
                    <div class="panel-section-title">Confluence — ${score}/100</div>
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
    const [forceSelling, setForceSelling] = useState(false)

    const pair   = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir    = trade.is_short ? 'SHORT' : 'LONG'
    const pnl    = parseFloat(trade.profit_abs || 0)
    const pnlPos = pnl >= 0
    const pnlPct = parseFloat(trade.profit_ratio || 0) * 100
    const health = trade.health
    const state  = health?.state || 'UNKNOWN'

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
                    ${forceSelling
                        ? html`<${Spinner} size="xs" color="white"/>`
                        : html`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`
                    }
                    ${forceSelling ? 'Closing...' : 'Force Sell — Requires TOTP'}
                </button>
            `}
        >
            <div class="panel-section">
                <div class="flex items-center gap-10 flex-wrap">
                    <${DirBadge} dir=${dir}/>
                    <${HealthRow} health=${health}/>
                </div>

                <div style="padding:18px;background:var(--fill-4);border:0.5px solid var(--separator);border-radius:var(--r-xl);text-align:center;">
                    <div class="label-uppercase mb-6">Unrealized PnL</div>
                    <div class=${'pnl-value ' + (pnlPos ? 'positive' : 'negative')}
                        style="font-size:var(--text-largetitle);">
                        ${Utils.fmtPnl(pnl, pnlPos)}
                    </div>
                    <div style=${'font-family:var(--font-mono);font-size:var(--text-subhead);color:' + (pnlPos ? 'var(--profit)' : 'var(--loss)') + ';margin-top:4px;font-variant-numeric:tabular-nums;'}>
                        ${Utils.fmtPct(pnlPct)}
                    </div>
                </div>

                <${TradeProgressBar} trade=${trade}/>
            </div>

            <div class="panel-section">
                <div class="panel-section-title">Levels</div>
                ${[
                    { label: 'Entry',        val: Utils.fmtPrice(trade.open_rate)   },
                    { label: 'Current',      val: Utils.fmtPrice(trade.current_rate), color: pnlPos ? 'var(--profit)' : 'var(--loss)' },
                    { label: 'Stop Loss',    val: Utils.fmtPrice(trade.sl_signal || trade.stop_loss_abs), color: 'var(--loss)'   },
                    { label: 'Take Profit',  val: Utils.fmtPrice(trade.tp1),          color: 'var(--profit)' },
                    { label: 'Stake',        val: '$' + parseFloat(trade.stake_amount || 0).toFixed(2) },
                    { label: 'Leverage',     val: (trade.leverage || '--') + 'x',     color: 'var(--brand)'  },
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
                        <div key=${i} style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:0.5px solid var(--separator);font-size:var(--text-subhead);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--profit)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;"><polyline points="20 6 9 17 4 12"/></svg>
                            <span style="color:var(--label-2);letter-spacing:var(--tracking-subhead);">${c}</span>
                        </div>
                    `)}
                    ${health.warnings?.map((w, i) => html`
                        <div key=${'w' + i} style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:0.5px solid var(--separator);font-size:var(--text-subhead);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                            <span style="color:var(--label-2);letter-spacing:var(--tracking-subhead);">${w}</span>
                        </div>
                    `)}
                    ${health.failures?.map((f, i) => html`
                        <div key=${'f' + i} style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:0.5px solid var(--separator);font-size:var(--text-subhead);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--loss)" stroke-width="2.5" style="flex-shrink:0;margin-top:2px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                            <span style="color:var(--label-2);letter-spacing:var(--tracking-subhead);">${f}</span>
                        </div>
                    `)}
                </div>
            `}
        </${Panel}>
    `
}