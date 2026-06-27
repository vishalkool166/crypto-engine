const {
    confirmTotp, closeTotp, useTotp, useToast, useWsState,
    useMode, useNextScan, useTicker, usePage, logout, navigate,
    requireTotp, toggleTheme, useTheme,
} = Store

function GradeBadge({ grade }) {
    return html`<span class=${Utils.gradeBadgeClass(grade)}>${grade}</span>`
}

function DirBadge({ dir }) {
    return html`<span class=${Utils.dirBadgeClass(dir)}>${dir}</span>`
}

function OutcomeBadge({ outcome }) {
    return html`<span class=${Utils.outcomeBadgeClass(outcome)}>${outcome}</span>`
}

function ScoreBar({ score }) {
    const s     = parseFloat(score) || 0
    const color = Utils.scoreColor(s)
    return html`
        <div class="score-bar">
            <span style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:${color};min-width:28px;">
                ${Math.round(s)}
            </span>
            <div class="score-bar-track">
                <div class="score-bar-fill" style="width:${s}%;background:${color};"></div>
            </div>
        </div>
    `
}

function Spinner() {
    return html`<span class="spinner"></span>`
}

function EmptyState({ message }) {
    return html`
        <div class="empty-state">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="empty-state-text">${message || 'No data available'}</span>
        </div>
    `
}

function LoadingSkeleton({ rows = 4 }) {
    return html`
        <div class="loading-skeleton">
            ${Array.from({ length: rows }).map((_, i) =>
                html`<div key=${i} class="skeleton skeleton-row"></div>`
            )}
        </div>
    `
}

function HealthBar({ health }) {
    if (!health) return html`
        <div class="health-indicator unknown">
            <div class="health-dot unknown"></div>
            <span>Checking...</span>
        </div>
    `
    const cls = Utils.healthClass(health.state)
    const msg = health.failures?.[0] || health.warnings?.[0] || ''
    return html`
        <div class=${'health-indicator ' + cls}>
            <div class=${'health-dot ' + cls}></div>
            <span style="font-weight:700;">${health.state}</span>
            ${msg && html`<span style="font-size:11px;opacity:0.8;">— ${msg}</span>`}
        </div>
    `
}

function TradeProgressBar({ trade }) {
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

    const toPos   = val => Math.max(0, Math.min(100, ((val - rangeMin) / range) * 100))
    const slPos   = toPos(sl)
    const tpPos   = toPos(tp)
    const currPos = toPos(current)

    const movingTowardTp = isShort ? current < entry : current > entry
    const currColor      = movingTowardTp ? 'var(--green)' : 'var(--red)'
    const slLeft         = Math.min(slPos, tpPos)
    const tpRight        = 100 - Math.max(slPos, tpPos)
    const pctToTp        = tp !== entry
        ? Math.abs((current - entry) / (tp - entry) * 100).toFixed(1)
        : '0'

    return html`
        <div style="margin:10px 0 4px;">
            <div class="trade-progress-bar">
                <div class="trade-progress-sl" style="width:${slLeft}%;"></div>
                <div class="trade-progress-tp" style="width:${tpRight}%;"></div>
                <div class="trade-progress-current" style="left:${currPos}%;background:${currColor};color:${currColor};"></div>
            </div>
            <div class="flex justify-between" style="font-size:10px;color:var(--text-muted);margin-top:3px;">
                <span style="font-family:var(--font-mono);">SL ${Utils.fmtPrice(sl)}</span>
                <span style="font-family:var(--font-mono);color:${currColor};">${pctToTp}% to TP</span>
                <span style="font-family:var(--font-mono);">TP ${Utils.fmtPrice(tp)}</span>
            </div>
        </div>
    `
}

function CoinDetailModal({ coin, onClose }) {
    const [data,    setData]    = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!coin) return
        setLoading(true)
        API.dashboardCoin(coin).then(d => { setData(d); setLoading(false) })
    }, [coin])

    useEffect(() => {
        const handler = e => e.key === 'Escape' && onClose()
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [])

    if (!coin) return null

    return html`
        <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && onClose()}>
            <div class="modal" style="max-width:580px;max-height:85vh;overflow-y:auto;">
                <div class="flex justify-between items-center" style="margin-bottom:20px;">
                    <div class="flex items-center gap-8">
                        <span style="font-size:20px;font-weight:800;font-family:var(--font-mono);">${coin}USDT</span>
                        ${data && html`<${GradeBadge} grade=${data.grade}/><${DirBadge} dir=${data.direction}/>`}
                    </div>
                    <button class="btn btn-ghost btn-sm btn-icon" onClick=${onClose}>
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>

                ${loading && html`<${LoadingSkeleton} rows=${6}/>`}
                ${!loading && !data && html`<div class="alert alert-warning">No cached data for ${coin} — run scan first.</div>`}
                ${!loading && data && html`
                    <div>
                        <div class="grid-3 mb-16" style="gap:8px;">
                            <div class="level-item">
                                <div class="level-label">Score</div>
                                <div style="font-size:24px;font-weight:800;color:${Utils.scoreColor(data.score)};">${data.score}/100</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Regime</div>
                                <div style="font-size:13px;font-weight:600;">${data.regime || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Session</div>
                                <div style="font-size:13px;font-weight:600;">${data.session || '--'}</div>
                            </div>
                        </div>

                        <div style="font-size:12px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Signal Levels</div>
                        <div class="grid-3 mb-16" style="gap:8px;">
                            <div class="level-item">
                                <div class="level-label">Entry</div>
                                <div class="level-value">${Utils.fmtPrice(data.signal?.entry)}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Stop Loss</div>
                                <div class="level-value" style="color:var(--red);">${Utils.fmtPrice(data.signal?.sl)}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Take Profit</div>
                                <div class="level-value" style="color:var(--green);">${Utils.fmtPrice(data.signal?.tp1)}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">R:R</div>
                                <div class="level-value">1:${data.actual_rr || '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Leverage</div>
                                <div class="level-value" style="color:var(--blue);">${data.signal?.leverage || '--'}x</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Risk</div>
                                <div class="level-value">${data.signal?.risk_amt ? '$' + parseFloat(data.signal.risk_amt).toFixed(2) : '--'}</div>
                            </div>
                        </div>

                        <div style="font-size:12px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Market</div>
                        <div class="grid-3 mb-16" style="gap:8px;">
                            <div class="level-item">
                                <div class="level-label">Price</div>
                                <div class="level-value">${Utils.fmtPrice(data.market?.price)}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">24h</div>
                                <div class="level-value" style="color:${Utils.pnlColor(data.market?.change_pos)};">
                                    ${Utils.fmtPct(data.market?.change)}
                                </div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Funding</div>
                                <div class="level-value" style="color:${Math.abs(data.market?.funding || 0) > 0.05 ? 'var(--red)' : 'var(--text-secondary)'};">
                                    ${data.market?.funding != null ? data.market.funding.toFixed(4) + '%' : '--'}
                                </div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Long Ratio</div>
                                <div class="level-value" style="color:${(data.market?.long_ratio || 0) > 65 ? 'var(--red)' : 'var(--text-secondary)'};">
                                    ${data.market?.long_ratio != null ? data.market.long_ratio + '%' : '--'}
                                </div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Short Ratio</div>
                                <div class="level-value">${data.market?.short_ratio != null ? data.market.short_ratio + '%' : '--'}</div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">OI Change</div>
                                <div class="level-value">${data.market?.oi_change != null ? data.market.oi_change + '%' : '--'}</div>
                            </div>
                        </div>

                        ${data.factors?.length && html`
                            <div style="font-size:12px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;">Confluence</div>
                            ${data.factors.map(f => html`
                                <div key=${f.key} style="margin-bottom:10px;">
                                    <div class="flex justify-between items-center" style="margin-bottom:4px;">
                                        <span style="font-size:12px;color:var(--text-secondary);">${f.label}</span>
                                        <span style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:${Utils.scoreColor(f.pct)};">
                                            ${f.earned}/${f.max}
                                        </span>
                                    </div>
                                    <div class="progress-bar">
                                        <div class="progress-fill" style="width:${f.pct}%;background:${Utils.scoreColor(f.pct)};"></div>
                                    </div>
                                </div>
                            `)}
                        `}

                        ${data.ml_probability != null && html`
                            <div class="stat-row">
                                <span class="stat-label">ML Probability</span>
                                <span style="font-family:var(--font-mono);font-weight:700;color:${Utils.winRateColor(data.ml_probability * 100)};">
                                    ${(data.ml_probability * 100).toFixed(1)}%
                                </span>
                            </div>
                        `}

                        ${data.thesis && html`
                            <div class="thesis-block mt-16">${data.thesis}</div>
                        `}
                    </div>
                `}
            </div>
        </div>
    `
}

function TotpModal() {
    const totp     = useTotp()
    const [code,   setCode]  = useState('')
    const inputRef = useRef(null)

    useEffect(() => {
        if (totp.show) { setCode(''); setTimeout(() => inputRef.current?.focus(), 50) }
    }, [totp.show])

    if (!totp.show) return null

    return html`
        <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && closeTotp()}>
            <div class="modal">
                <div class="modal-title">${totp.title}</div>
                <div class="modal-sub">${totp.subtitle}</div>
                <input
                    ref=${inputRef}
                    class="totp-input"
                    type="text"
                    inputmode="numeric"
                    maxlength="6"
                    value=${code}
                    placeholder="000000"
                    autocomplete="one-time-code"
                    onInput=${e => setCode(e.target.value.replace(/\D/g, ''))}
                    onKeyDown=${e => e.key === 'Enter' && code.length === 6 && confirmTotp(code)}
                />
                <div class="modal-actions">
                    <button class="btn btn-ghost" onClick=${closeTotp}>Cancel</button>
                    <button class="btn btn-primary" onClick=${() => confirmTotp(code)} disabled=${code.length < 6}>
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    `
}

function Toast() {
    const toast = useToast()
    if (!toast.show) return null
    return html`
        <div style="position:fixed;bottom:calc(24px + var(--safe-bottom));right:calc(24px + var(--safe-right));z-index:2000;min-width:280px;max-width:380px;">
            <div class=${'alert alert-' + toast.type}>${toast.message}</div>
        </div>
    `
}

function Ticker() {
    const ticker = useTicker()
    if (!ticker.length) return null
    const items = [...ticker, ...ticker]
    return html`
        <div style="height:32px;min-height:32px;background:var(--bg-secondary);border-bottom:1px solid var(--bg-border);display:flex;align-items:center;overflow:hidden;">
            <div style="display:flex;align-items:center;animation:ticker-scroll 60s linear infinite;white-space:nowrap;">
                ${items.map((item, i) => html`
                    <div key=${item.coin + '_' + i} style="display:inline-flex;align-items:center;gap:6px;padding:0 16px;border-right:1px solid var(--bg-border);font-size:11px;">
                        <span style="font-family:var(--font-mono);font-weight:700;color:var(--text-secondary);">${item.coin}</span>
                        <span style="font-family:var(--font-mono);font-weight:600;">${Utils.fmtPrice(item.price)}</span>
                        <span style="font-family:var(--font-mono);font-size:10px;color:${Utils.changeColor(item.change)};">${Utils.fmtPct(item.change)}</span>
                    </div>
                `)}
            </div>
        </div>
    `
}

function Topbar({ page }) {
    const wsState  = useWsState()
    const mode     = useMode()
    const nextScan = useNextScan()
    const theme    = useTheme()

    const navItems = [
        { id: 'overview',  label: 'Overview'  },
        { id: 'freqtrade', label: 'Trades'    },
        { id: 'signals',   label: 'Signals'   },
        { id: 'coins',     label: 'Coins'     },
        { id: 'backtest',  label: 'Backtest'  },
        { id: 'analysis',  label: 'Analysis'  },
        { id: 'audit',     label: 'Audit'     },
        { id: 'settings',  label: 'Settings'  },
    ]

    const wsLabel = wsState === 'connected' ? 'Live' : wsState === 'connecting' ? 'Connecting' : 'Offline'

    return html`
        <header class="topbar">
            <div class="topbar-brand">
                <svg class="topbar-brand-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
                    <rect width="32" height="32" rx="8" fill="${theme === 'light' ? '#f5f5f7' : '#1c1c1e'}"/>
                    <polygon points="18,3 8,18 15,18 14,29 24,14 17,14" fill="var(--blue)" stroke="var(--blue)" stroke-width="0.5" stroke-linejoin="round"/>
                </svg>
                <span class="topbar-brand-name">Signal Engine</span>
            </div>

            <nav class="topbar-nav">
                ${navItems.map(item => html`
                    <button key=${item.id}
                        class=${'topbar-nav-item ' + (page === item.id ? 'active' : '')}
                        onClick=${() => navigate(item.id)}>
                        ${item.label}
                    </button>
                `)}
            </nav>

            <div class="topbar-right">
                <div class="next-scan-badge">
                    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <span>${nextScan}</span>
                </div>

                <div class="topbar-divider"></div>

                <div class=${'mode-indicator ' + mode}>${mode.toUpperCase()}</div>

                <div class="topbar-divider"></div>

                <div class="ws-status-bar">
                    <div class=${'ws-dot ' + (wsState === 'connected' ? '' : wsState === 'connecting' ? 'connecting' : 'disconnected')}></div>
                    <span>${wsLabel}</span>
                </div>

                <div class="topbar-divider"></div>

                <button class="theme-toggle" onClick=${toggleTheme} title="Toggle theme">
                    ${theme === 'light'
                        ? html`<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`
                        : html`<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
                    }
                </button>

                <button class="btn btn-ghost btn-sm" onClick=${logout}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <polyline points="16 17 21 12 16 7"/>
                        <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                    Logout
                </button>
            </div>
        </header>
    `
}

function BottomNav({ page }) {
    const items = [
        { id: 'overview',  label: 'Overview', icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>` },
        { id: 'freqtrade', label: 'Trades',   icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
        { id: 'signals',   label: 'Signals',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>` },
        { id: 'coins',     label: 'Coins',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>` },
        { id: 'settings',  label: 'Settings', icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>` },
    ]
    return html`
        <nav class="bottom-nav">
            ${items.map(item => html`
                <button key=${item.id}
                    class=${'bottom-nav-item ' + (page === item.id ? 'active' : '')}
                    onClick=${() => navigate(item.id)}>
                    ${item.icon}
                    <span>${item.label}</span>
                </button>
            `)}
        </nav>
    `
}

window.Components = {
    GradeBadge, DirBadge, OutcomeBadge, ScoreBar,
    Spinner, EmptyState, LoadingSkeleton,
    HealthBar, TradeProgressBar, CoinDetailModal,
    TotpModal, Toast, Ticker, Topbar, BottomNav,
}