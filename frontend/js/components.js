import { h, Fragment } from '/js/preact.min.js'
import { useState, useEffect, useRef } from '/js/preact-hooks.min.js'
import htm from '/js/htm.min.js'
import {
    confirmTotp, closeTotp,
    useTotp, useToast, useWsState, useMode,
    useNextScan, useTicker, usePage, logout, navigate,
    getCoinDetail,
} from '/js/store.js'

export const html = htm.bind(h)

export function GradeBadge({ grade }) {
    const cls = {
        'A+': 'badge badge-aplus',
        'A':  'badge badge-a',
        'B':  'badge badge-b',
        'C':  'badge badge-c',
        'F':  'badge badge-f',
    }[grade] || 'badge badge-f'
    return html`<span class=${cls} aria-label=${'Grade ' + grade}>${grade}</span>`
}

export function DirBadge({ dir }) {
    const cls = {
        'LONG':     'badge badge-long',
        'SHORT':    'badge badge-short',
        'WATCH':    'badge badge-watch',
        'NO TRADE': 'badge badge-f',
    }[dir] || 'badge badge-f'
    return html`<span class=${cls} aria-label=${'Direction: ' + dir}>${dir}</span>`
}

export function OutcomeBadge({ outcome }) {
    const cls = {
        'win':     'badge badge-win',
        'loss':    'badge badge-loss',
        'pending': 'badge badge-pending',
        'timeout': 'badge badge-f',
    }[outcome] || 'badge badge-f'
    return html`<span class=${cls} aria-label=${'Outcome: ' + outcome}>${outcome}</span>`
}

export function HealthBar({ health }) {
    if (!health) return html`
        <div class="health-indicator unknown" role="status" aria-label="Health status: checking">
            <div class="health-dot unknown" aria-hidden="true"></div>
            <span>Checking health...</span>
        </div>
    `
    const stateMap = {
        'HEALTHY':     { cls: 'healthy',     label: 'Healthy'     },
        'WARNING':     { cls: 'warning',     label: 'Warning'     },
        'INVALIDATED': { cls: 'invalidated', label: 'Invalidated' },
    }
    const s   = stateMap[health.state] || { cls: 'unknown', label: 'Unknown' }
    const msg = health.failures?.[0] || health.warnings?.[0] || ''
    return html`
        <div class=${'health-indicator ' + s.cls} role="status"
            aria-label=${'Health: ' + s.label + (msg ? ' — ' + msg : '')}>
            <div class=${'health-dot ' + s.cls} aria-hidden="true"></div>
            <span style="font-weight:700;">${s.label}</span>
            ${msg && html`<span style="font-size:11px;opacity:0.8;">— ${msg}</span>`}
        </div>
    `
}

export function TradeProgressBar({ trade }) {
    const entry   = parseFloat(trade.open_rate    || 0)
    const current = parseFloat(trade.current_rate || 0)
    const sl      = parseFloat(trade.sl_signal    || trade.stop_loss_abs || 0)
    const tp      = parseFloat(trade.tp1          || 0)
    const isShort = trade.is_short

    if (!entry || !current || !sl || !tp) return null

    const rangeMin = Math.min(sl, tp, entry, current) * 0.999
    const rangeMax = Math.max(sl, tp, entry, current) * 1.001
    const range    = rangeMax - rangeMin
    if (range <= 0) return null

    const toPos    = val => Math.max(0, Math.min(100, ((val - rangeMin) / range) * 100))
    const slPos    = toPos(sl)
    const tpPos    = toPos(tp)
    const currPos  = toPos(current)

    const movingTowardTp = isShort ? current < entry : current > entry
    const currColor      = movingTowardTp ? 'var(--green)' : 'var(--red)'

    const slLeft  = Math.min(slPos, tpPos)
    const tpRight = 100 - Math.max(slPos, tpPos)

    const pctToTp = tp !== entry
        ? Math.abs((current - entry) / (tp - entry) * 100).toFixed(1)
        : '0'

    return html`
        <div style="margin:10px 0 4px;">
            <div class="trade-progress-bar"
                role="progressbar"
                aria-label=${'Trade progress: ' + pctToTp + '% toward TP'}
                aria-valuenow=${pctToTp}
                aria-valuemin="0"
                aria-valuemax="100">
                <div class="trade-progress-sl" style="width:${slLeft}%;"></div>
                <div class="trade-progress-tp" style="width:${tpRight}%;"></div>
                <div class="trade-progress-current"
                    style="left:${currPos}%;background:${currColor};color:${currColor};">
                </div>
            </div>
            <div class="flex justify-between" style="font-size:9px;color:var(--text-muted);margin-top:3px;">
                <span style="font-family:var(--font-mono);">SL ${Utils.fmtPrice(sl)}</span>
                <span style="font-family:var(--font-mono);color:${currColor};">${pctToTp}% to TP</span>
                <span style="font-family:var(--font-mono);">TP ${Utils.fmtPrice(tp)}</span>
            </div>
        </div>
    `
}

export function ScoreBar({ score }) {
    const s     = parseFloat(score) || 0
    const color = Utils.scoreBarColor(s)
    return html`
        <div class="score-bar"
            role="meter"
            aria-label=${'Score: ' + Math.round(s) + ' out of 100'}
            aria-valuenow=${Math.round(s)}
            aria-valuemin="0"
            aria-valuemax="100">
            <span style="font-family:var(--font-mono);font-size:12px;font-weight:600;color:${color};min-width:32px;">
                ${Math.round(s)}
            </span>
            <div class="score-bar-track" aria-hidden="true">
                <div class="score-bar-fill" style="width:${s}%;background:${color};"></div>
            </div>
        </div>
    `
}

export function Spinner() {
    return html`<span class="spinner" role="status" aria-label="Loading"></span>`
}

export function EmptyState({ message }) {
    return html`
        <div class="empty-state" role="status">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="empty-state-text">${message || 'No data available'}</span>
        </div>
    `
}

export function LoadingSkeleton({ rows = 4 }) {
    return html`
        <div class="loading-skeleton" role="status" aria-label="Loading content" aria-busy="true">
            ${Array.from({ length: rows }).map((_, i) =>
                html`<div key=${i} class="skeleton skeleton-row" aria-hidden="true"></div>`
            )}
        </div>
    `
}

export function CoinDetailModal({ coin, onClose }) {
    const [data,    setData]    = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!coin) return
        setLoading(true)
        getCoinDetail(coin).then(d => {
            setData(d)
            setLoading(false)
        })
    }, [coin])

    useEffect(() => {
        const handler = e => e.key === 'Escape' && onClose()
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [])

    if (!coin) return null

    return html`
        <div class="modal-overlay"
            role="dialog"
            aria-modal="true"
            aria-labelledby="coin-modal-title"
            onClick=${e => e.target === e.currentTarget && onClose()}>
            <div class="modal" style="max-width:600px;max-height:85vh;overflow-y:auto;">
                <div class="flex justify-between items-center" style="margin-bottom:16px;">
                    <div class="flex items-center gap-8">
                        <span id="coin-modal-title" style="font-size:18px;font-weight:800;font-family:var(--font-mono);">
                            ${coin}USDT
                        </span>
                        ${data && html`
                            <${GradeBadge} grade=${data.grade}/>
                            <${DirBadge} dir=${data.direction}/>
                        `}
                    </div>
                    <button class="btn btn-ghost btn-sm btn-icon" onClick=${onClose} aria-label="Close">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>

                ${loading && html`<${LoadingSkeleton} rows=${6}/>`}

                ${!loading && !data && html`
                    <div class="alert alert-warning">
                        No cached data for ${coin} — run a scan first.
                    </div>
                `}

                ${!loading && data && html`
                    <div>
                        <div class="grid-3 mb-12" style="gap:8px;">
                            <div class="level-item">
                                <div class="level-label">Score</div>
                                <div style="font-family:var(--font-mono);font-size:18px;font-weight:800;color:${Utils.scoreBarColor(data.score)};">
                                    ${data.score}/100
                                </div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Regime</div>
                                <div style="font-size:12px;font-weight:600;">${data.regime || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Session</div>
                                <div style="font-size:12px;font-weight:600;">${data.session || '--'}</div>
                            </div>
                        </div>

                        <div class="section-title mb-8">Signal Levels</div>
                        <div class="grid-3 mb-12" style="gap:8px;">
                            <div class="level-item">
                                <div class="level-label">Entry</div>
                                <div class="level-value">${data.signal?.entry || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Stop Loss</div>
                                <div class="level-value" style="color:var(--red);">${data.signal?.sl || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Take Profit</div>
                                <div class="level-value" style="color:var(--green);">${data.signal?.tp1 || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">R:R</div>
                                <div class="level-value">1:${data.actual_rr || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Leverage</div>
                                <div class="level-value">${data.signal?.leverage || '--'}x</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Risk</div>
                                <div class="level-value">${data.signal?.risk_amt || '--'}</div>
                            </div>
                        </div>

                        <div class="section-title mb-8">Market Data</div>
                        <div class="grid-3 mb-12" style="gap:8px;">
                            <div class="level-item">
                                <div class="level-label">Price</div>
                                <div class="level-value">${data.market?.price || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">24h Change</div>
                                <div class="level-value" style="color:${data.market?.change_color};">
                                    ${data.market?.change || '--'}
                                </div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Funding</div>
                                <div class="level-value" style="color:${Math.abs(data.market?.funding || 0) > 0.05 ? 'var(--red)' : 'var(--text-secondary)'};">
                                    ${data.market?.funding != null ? data.market.funding.toFixed(4) + '%' : '--'}
                                </div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">OI Change</div>
                                <div class="level-value">${data.market?.oi_change != null ? data.market.oi_change + '%' : '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Long Ratio</div>
                                <div class="level-value" style="color:${(data.market?.long_ratio || 0) > 65 ? 'var(--red)' : 'var(--text-secondary)'};">
                                    ${data.market?.long_ratio != null ? data.market.long_ratio + '%' : '--'}
                                </div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Short Ratio</div>
                                <div class="level-value" style="color:${(data.market?.short_ratio || 0) > 65 ? 'var(--red)' : 'var(--text-secondary)'};">
                                    ${data.market?.short_ratio != null ? data.market.short_ratio + '%' : '--'}
                                </div>
                            </div>
                        </div>

                        <div class="section-title mb-8">Confluence Scores</div>
                        <div class="grid-3 mb-8" style="gap:6px;">
                            ${[
                                { label: 'Market Score', val: data.market_score, max: 100 },
                                { label: 'Entry Score',  val: data.entry_score,  max: 100 },
                                { label: 'BTC Score',    val: data.btc_score,    max: 8   },
                            ].map(item => html`
                                <div key=${item.label} class="level-item">
                                    <div class="level-label">${item.label}</div>
                                    <div style="font-family:var(--font-mono);font-size:13px;font-weight:700;color:${Utils.scoreBarColor((item.val || 0) / item.max * 100)};">
                                        ${item.val != null ? item.val + '/' + item.max : '--'}
                                    </div>
                                </div>
                            `)}
                        </div>

                        ${data.factors?.length && html`
                            <div style="margin-bottom:12px;">
                                ${data.factors.map(f => html`
                                    <div key=${f.key} style="margin-bottom:8px;">
                                        <div class="flex justify-between items-center" style="margin-bottom:3px;">
                                            <span style="font-size:11px;color:var(--text-secondary);font-family:var(--font-mono);">
                                                ${f.label}
                                            </span>
                                            <span style="font-family:var(--font-mono);font-size:11px;font-weight:700;color:${f.color};">
                                                ${f.earned}/${f.max}
                                            </span>
                                        </div>
                                        <div class="progress-bar">
                                            <div class="progress-fill" style="width:${f.pct}%;background:${f.color};"></div>
                                        </div>
                                    </div>
                                `)}
                            </div>
                        `}

                        ${data.ml_probability != null && html`
                            <div class="stat-row">
                                <span class="stat-label">ML Probability</span>
                                <span style="font-family:var(--font-mono);font-weight:700;color:${Utils.winRateColor(data.ml_probability * 100)};">
                                    ${(data.ml_probability * 100).toFixed(1)}%
                                </span>
                            </div>
                        `}

                        ${data.confidence && html`
                            <div class="stat-row">
                                <span class="stat-label">Confidence</span>
                                <span style="font-size:12px;color:var(--text-secondary);">${data.confidence}</span>
                            </div>
                        `}

                        ${data.thesis && html`
                            <div class="mt-12">
                                <div class="section-title mb-8">Thesis</div>
                                <div class="thesis-block">${data.thesis}</div>
                            </div>
                        `}
                    </div>
                `}
            </div>
        </div>
    `
}

export function MiniTradeCard({ trade }) {
    const pair = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir  = trade.is_short ? 'SHORT' : 'LONG'
    const pnl  = parseFloat(trade.profit_abs || 0)
    return html`
        <div class="trade-card" role="article" aria-label=${pair + ' ' + dir + ' trade'}>
            <div class="trade-card-header">
                <div class="flex items-center gap-8">
                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:800;">${pair}</span>
                    <${DirBadge} dir=${dir}/>
                    <span class="tag">#${trade.trade_id}</span>
                </div>
                <div class="flex items-center gap-8">
                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:800;color:${Utils.pnlColor(pnl)};"
                        aria-live="polite">
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
            <${TradeProgressBar} trade=${trade}/>
            <${HealthBar} health=${trade.health}/>
        </div>
    `
}

export function TradesBanner({ trades }) {
    const [expanded, setExpanded] = useState(false)
    if (!trades || !trades.length) return null

    const states    = trades.map(t => t.health?.state || 'UNKNOWN')
    const hasInv    = states.includes('INVALIDATED')
    const hasWarn   = states.includes('WARNING')
    const bannerCls = hasInv  ? 'trades-banner has-invalidated'
                    : hasWarn ? 'trades-banner has-warning'
                    : 'trades-banner has-healthy'
    const statusLabel = hasInv ? 'Invalidated' : hasWarn ? 'Warning' : 'Healthy'

    return html`
        <div>
            <div class=${bannerCls}
                onClick=${() => setExpanded(p => !p)}
                role="button"
                tabindex="0"
                aria-expanded=${expanded}
                aria-label=${'Open trades: ' + trades.length + ' — Status: ' + statusLabel}
                onKeyDown=${e => (e.key === 'Enter' || e.key === ' ') && setExpanded(p => !p)}>
                <div class=${'health-dot ' + (hasInv ? 'invalidated' : hasWarn ? 'warning' : 'healthy')} aria-hidden="true"></div>
                <span style="font-weight:800;">${trades.length} Open Trade${trades.length > 1 ? 's' : ''}</span>
                ${hasInv  && html`<span class="badge badge-invalidated" aria-hidden="true">INVALIDATED</span>`}
                ${hasWarn && !hasInv && html`<span class="badge badge-warning" aria-hidden="true">WARNING</span>`}
                <span style="margin-left:auto;color:var(--text-muted);font-size:11px;" aria-hidden="true">
                    ${expanded ? '▲' : '▼'}
                </span>
            </div>
            ${expanded && trades.map(trade => html`
                <${MiniTradeCard} key=${trade.trade_id} trade=${trade}/>
            `)}
        </div>
    `
}

export function TotpModal() {
    const totp     = useTotp()
    const [code,   setCode]  = useState('')
    const [error,  setError] = useState('')
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
        <div class="modal-overlay"
            role="dialog"
            aria-modal="true"
            aria-labelledby="totp-modal-title"
            aria-describedby="totp-modal-desc"
            onClick=${e => e.target === e.currentTarget && handleClose()}
            onKeyDown=${e => e.key === 'Escape' && handleClose()}>
            <div class="modal">
                <div id="totp-modal-title" class="modal-title">${totp.title || 'Confirm Action'}</div>
                <div id="totp-modal-desc"  class="modal-sub">${totp.subtitle || 'Enter your TOTP code to continue'}</div>
                ${error && html`<div class="alert alert-error" role="alert">${error}</div>`}
                <label for="totp-code-input"
                    style="display:block;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
                    TOTP Code
                </label>
                <input
                    id="totp-code-input"
                    ref=${inputRef}
                    class="totp-input"
                    type="text"
                    inputmode="numeric"
                    maxlength="6"
                    value=${code}
                    placeholder="000000"
                    autocomplete="one-time-code"
                    aria-label="6-digit TOTP verification code"
                    aria-required="true"
                    onInput=${e => setCode(e.target.value.replace(/\D/g, ''))}
                    onKeyDown=${e => e.key === 'Enter' && code.length === 6 && handleConfirm()}
                />
                <div class="modal-actions">
                    <button class="btn btn-ghost" onClick=${handleClose} aria-label="Cancel">Cancel</button>
                    <button class="btn btn-primary" onClick=${handleConfirm}
                        disabled=${code.length < 6}
                        aria-label="Confirm with TOTP code">
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    `
}

export function Toast() {
    const toast = useToast()
    if (!toast.show) return null
    return html`
        <div style="position:fixed;bottom:calc(24px + var(--safe-bottom));right:calc(24px + var(--safe-right));z-index:2000;min-width:280px;max-width:380px;"
            role="status"
            aria-live="polite"
            aria-atomic="true">
            <div class=${'alert alert-' + toast.type}>${toast.message}</div>
        </div>
    `
}

export function Ticker() {
    const ticker = useTicker()
    if (!ticker.length) return null
    const items = [...ticker, ...ticker]
    return html`
        <div class="ticker-bar" role="marquee" aria-label="Live price ticker" aria-live="off">
            <div class="ticker-track">
                ${items.map((item, i) => html`
                    <div key=${item.coin + '_' + i} class="ticker-item"
                        aria-hidden=${i >= ticker.length ? 'true' : 'false'}>
                        <span class="ticker-coin">${item.coin}</span>
                        <span class="ticker-price">${item.price}</span>
                        <span class="ticker-change" style="color:${item.change_color};">${item.change}</span>
                    </div>
                `)}
            </div>
        </div>
    `
}

export function Topbar({ page }) {
    const wsState  = useWsState()
    const mode     = useMode()
    const nextScan = useNextScan()

    const titles = {
        overview:  'Overview',
        freqtrade: 'Freqtrade',
        signals:   'Signals',
        coins:     'Coin Universe',
        backtest:  'Backtest',
        analysis:  'Analysis',
        audit:     'Audit Log',
        settings:  'Settings',
    }

    const wsLabel = wsState === 'connected'  ? 'Live'
                  : wsState === 'connecting' ? 'Connecting'
                  : 'Offline'

    return html`
        <header class="topbar" role="banner">
            <div class="topbar-left">
                <span class="topbar-title">${titles[page] || ''}</span>
                <div class="topbar-divider" aria-hidden="true"></div>
                <div class=${'mode-indicator ' + mode}
                    role="status"
                    aria-label=${'Trading mode: ' + mode.toUpperCase()}>
                    <div class="live-dot" style=${mode === 'live' ? 'background:var(--red)' : ''} aria-hidden="true"></div>
                    <span>${mode.toUpperCase()}</span>
                </div>
            </div>
            <div class="topbar-right">
                <div class="next-scan-badge" aria-label=${'Next scan in ' + nextScan}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <span aria-hidden="true">Next scan</span>
                    <span aria-hidden="true">${nextScan}</span>
                </div>
                <div class="topbar-divider" aria-hidden="true"></div>
                <div class="ws-status-bar" role="status" aria-label=${'Connection: ' + wsLabel}>
                    <div class=${'ws-dot ' + (wsState === 'connected' ? '' : wsState === 'connecting' ? 'connecting' : 'disconnected')} aria-hidden="true"></div>
                    <span>${wsLabel}</span>
                </div>
                <div class="topbar-divider" aria-hidden="true"></div>
                <button class="btn btn-ghost btn-sm" onClick=${logout} aria-label="Log out of Signal Engine">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <polyline points="16 17 21 12 16 7"/>
                        <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                    <span>Logout</span>
                </button>
            </div>
        </header>
    `
}

export function Sidebar({ page, expanded, onToggle }) {
    const navItems = [
        {
            section: 'Trading',
            items: [
                { id: 'overview',  label: 'Overview',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>` },
                { id: 'freqtrade', label: 'Freqtrade', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>` },
                { id: 'signals',   label: 'Signals',   icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
            ]
        },
        {
            section: 'Research',
            items: [
                { id: 'coins',    label: 'Coins',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>` },
                { id: 'backtest', label: 'Backtest', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>` },
                { id: 'analysis', label: 'Analysis', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>` },
            ]
        },
        {
            section: 'System',
            items: [
                { id: 'audit',    label: 'Audit Log', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>` },
                { id: 'settings', label: 'Settings',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>` },
            ]
        }
    ]

    return html`
        <aside class=${'sidebar ' + (expanded ? 'expanded' : '')}
            role="navigation"
            aria-label="Main navigation"
            aria-expanded=${expanded}>
            <div class="sidebar-logo" aria-label="Signal Engine v5">
                <svg class="sidebar-logo-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none" aria-hidden="true">
                    <rect width="32" height="32" rx="8" fill="#0e0e1a"/>
                    <polygon points="18,3 8,18 15,18 14,29 24,14 17,14" fill="#00e5b8" stroke="#00e5b8" stroke-width="0.5" stroke-linejoin="round"/>
                </svg>
                <div class="sidebar-logo-text" aria-hidden="true">
                    <div class="sidebar-logo-title">Signal Engine</div>
                    <div class="sidebar-logo-sub">v5.0.0</div>
                </div>
            </div>
            <nav role="menubar" aria-label="Navigation menu">
                ${navItems.map(section => html`
                    <div key=${section.section}>
                        <div class="nav-section-label" aria-hidden="true">${section.section}</div>
                        ${section.items.map(item => html`
                            <div key=${item.id}
                                class=${'nav-item ' + (page === item.id ? 'active' : '')}
                                onClick=${() => navigate(item.id)}
                                role="menuitem"
                                tabindex="0"
                                aria-current=${page === item.id ? 'page' : 'false'}
                                aria-label=${item.label}
                                onKeyDown=${e => (e.key === 'Enter' || e.key === ' ') && navigate(item.id)}>
                                ${item.icon}
                                <span class="nav-item-label" aria-hidden="true">${item.label}</span>
                                <span class="nav-tooltip" role="tooltip">${item.label}</span>
                            </div>
                        `)}
                    </div>
                `)}
            </nav>
            <button class="sidebar-toggle"
                onClick=${onToggle}
                aria-label=${expanded ? 'Collapse sidebar' : 'Expand sidebar'}
                aria-expanded=${expanded}>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    ${expanded
                        ? html`<polyline points="15 18 9 12 15 6"/>`
                        : html`<polyline points="9 18 15 12 9 6"/>`
                    }
                </svg>
            </button>
        </aside>
    `
}

export function BottomNav({ page }) {
    const items = [
        { id: 'overview',  label: 'Overview', icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>` },
        { id: 'freqtrade', label: 'Trades',   icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>` },
        { id: 'signals',   label: 'Signals',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
        { id: 'coins',     label: 'Coins',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>` },
        { id: 'settings',  label: 'Settings', icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>` },
    ]
    return html`
        <nav class="bottom-nav" aria-label="Mobile navigation">
            ${items.map(item => html`
                <button key=${item.id}
                    class=${'bottom-nav-item ' + (page === item.id ? 'active' : '')}
                    onClick=${() => navigate(item.id)}
                    aria-label=${item.label}
                    aria-current=${page === item.id ? 'page' : 'false'}>
                    ${item.icon}
                    <span aria-hidden="true">${item.label}</span>
                </button>
            `)}
        </nav>
    `
}