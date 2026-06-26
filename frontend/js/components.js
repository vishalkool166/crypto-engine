import { h, Fragment } from '/js/preact.min.js'
import { useState, useEffect, useRef } from '/js/preact-hooks.min.js'
import htm from '/js/htm.min.js'
import { confirmTotp, closeTotp, useTotp, useToast, useWsState, useMode, useNextScan, useTicker, usePage, logout, navigate } from '/js/store.js'

export const html = htm.bind(h)

export function GradeBadge({ grade }) {
    const cls = {
        'A+': 'badge badge-aplus',
        'A':  'badge badge-a',
        'B':  'badge badge-b',
        'C':  'badge badge-c',
        'F':  'badge badge-f',
    }[grade] || 'badge badge-f'
    return html`<span class=${cls}>${grade}</span>`
}

export function DirBadge({ dir }) {
    const cls = {
        'LONG':     'badge badge-long',
        'SHORT':    'badge badge-short',
        'WATCH':    'badge badge-watch',
        'NO TRADE': 'badge badge-f',
    }[dir] || 'badge badge-f'
    return html`<span class=${cls}>${dir}</span>`
}

export function OutcomeBadge({ outcome }) {
    const cls = {
        'win':     'badge badge-win',
        'loss':    'badge badge-loss',
        'pending': 'badge badge-pending',
        'timeout': 'badge badge-f',
    }[outcome] || 'badge badge-f'
    return html`<span class=${cls}>${outcome}</span>`
}

export function HealthBar({ health }) {
    if (!health) return html`
        <div class="health-bar unknown">
            <span>⏳</span>
            <span style="font-size:12px;">Checking health...</span>
        </div>
    `
    const cls = {
        'HEALTHY':     'health-bar healthy',
        'WARNING':     'health-bar warning',
        'INVALIDATED': 'health-bar invalidated',
    }[health.state] || 'health-bar unknown'
    const emoji = { 'HEALTHY': '✅', 'WARNING': '⚠️', 'INVALIDATED': '🚨' }[health.state] || '⏳'
    const msg   = health.failures?.[0] || health.warnings?.[0] || ''
    return html`
        <div class=${cls}>
            <span>${emoji}</span>
            <span style="font-weight:700;">${health.state}</span>
            ${msg && html`<span style="font-size:11px;opacity:0.8;">— ${msg}</span>`}
        </div>
    `
}

export function ScoreBar({ score }) {
    const s     = parseFloat(score) || 0
    const color = Utils.scoreBarColor(s)
    return html`
        <div class="score-bar">
            <span style="font-family:var(--font-mono);font-size:12px;font-weight:600;color:${color};min-width:32px;">
                ${Math.round(s)}
            </span>
            <div class="score-bar-track">
                <div class="score-bar-fill" style="width:${s}%;background:${color};"></div>
            </div>
        </div>
    `
}

export function Spinner() {
    return html`<span class="spinner"></span>`
}

export function EmptyState({ message }) {
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

export function LoadingSkeleton({ rows = 4 }) {
    return html`
        <div class="loading-skeleton">
            ${Array.from({ length: rows }).map((_, i) =>
                html`<div key=${i} class="skeleton skeleton-row"></div>`
            )}
        </div>
    `
}

export function MiniTradeCard({ trade }) {
    const pair = (trade.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
    const dir  = trade.is_short ? 'SHORT' : 'LONG'
    const pnl  = parseFloat(trade.profit_abs || 0)
    return html`
        <div class="trade-card">
            <div class="trade-card-header">
                <div class="flex items-center gap-8">
                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:800;">${pair}</span>
                    <${DirBadge} dir=${dir}/>
                    <span class="tag">#${trade.trade_id}</span>
                </div>
                <div class="flex items-center gap-8">
                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:800;color:${Utils.pnlColor(pnl)};">
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
    const bannerCls = hasInv   ? 'trades-banner has-invalidated'
                    : hasWarn  ? 'trades-banner has-warning'
                    : 'trades-banner has-healthy'
    const emoji     = hasInv ? '🚨' : hasWarn ? '⚠️' : '✅'
    return html`
        <div>
            <div class=${bannerCls} onClick=${() => setExpanded(p => !p)}>
                <span>${emoji}</span>
                <span style="font-weight:800;">${trades.length} Open Trade${trades.length > 1 ? 's' : ''}</span>
                ${hasInv  && html`<span class="badge badge-invalidated">INVALIDATED</span>`}
                ${hasWarn && !hasInv && html`<span class="badge badge-warning">WARNING</span>`}
                <span style="margin-left:auto;color:var(--text-muted);font-size:11px;">
                    ${expanded ? '▲ collapse' : '▼ expand'}
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
        <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && handleClose()}>
            <div class="modal">
                <div class="modal-title">${totp.title || 'Confirm Action'}</div>
                <div class="modal-sub">${totp.subtitle || 'Enter your TOTP code to continue'}</div>
                ${error && html`<div class="alert alert-error">${error}</div>`}
                <label style="display:block;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
                    TOTP Code
                </label>
                <input
                    ref=${inputRef}
                    class="totp-input"
                    type="text"
                    inputmode="numeric"
                    maxlength="6"
                    value=${code}
                    placeholder="000000"
                    onInput=${e => setCode(e.target.value.replace(/\D/g, ''))}
                    onKeyDown=${e => e.key === 'Enter' && code.length === 6 && handleConfirm()}
                />
                <div class="modal-actions">
                    <button class="btn btn-ghost" onClick=${handleClose}>Cancel</button>
                    <button class="btn btn-primary" onClick=${handleConfirm} disabled=${code.length < 6}>
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
        <div style="position:fixed;bottom:24px;right:24px;z-index:2000;min-width:280px;max-width:380px;">
            <div class=${'alert alert-' + toast.type}>${toast.message}</div>
        </div>
    `
}

export function Ticker() {
    const ticker = useTicker()
    if (!ticker.length) return null
    const items = [...ticker, ...ticker]
    return html`
        <div class="ticker-bar">
            <div class="ticker-track">
                ${items.map((item, i) => html`
                    <div key=${item.coin + '_' + i} class="ticker-item">
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
        signals:   'Signals',
        freqtrade: 'Freqtrade',
        coins:     'Coin Universe',
        backtest:  'Backtest',
        analysis:  'Analysis',
        audit:     'Audit Log',
        settings:  'Settings',
    }

    return html`
        <header class="topbar">
            <div class="topbar-left">
                <span class="topbar-title">${titles[page] || ''}</span>
                <div class="topbar-divider"></div>
                <div class=${'mode-indicator ' + mode}>
                    <div class="live-dot" style=${mode === 'live' ? 'background:var(--red)' : ''}></div>
                    <span>${mode.toUpperCase()}</span>
                </div>
            </div>
            <div class="topbar-right">
                <div class="next-scan-badge">
                    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <span>Next scan</span>
                    <span>${nextScan}</span>
                </div>
                <div class="topbar-divider"></div>
                <div class="ws-status-bar">
                    <div class=${'ws-dot ' + (wsState === 'connected' ? '' : wsState === 'connecting' ? 'connecting' : 'disconnected')}></div>
                    <span>${wsState === 'connected' ? 'Live' : wsState === 'connecting' ? 'Connecting' : 'Offline'}</span>
                </div>
                <div class="topbar-divider"></div>
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

export function Sidebar({ page, expanded, onToggle }) {
    const navItems = [
        {
            section: 'Trading',
            items: [
                { id: 'overview',  label: 'Overview',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>` },
                { id: 'signals',   label: 'Signals',   icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
                { id: 'freqtrade', label: 'Freqtrade', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>` },
            ]
        },
        {
            section: 'Research',
            items: [
                { id: 'coins',    label: 'Coins',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>` },
                { id: 'backtest', label: 'Backtest', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>` },
                { id: 'analysis', label: 'Analysis', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>` },
            ]
        },
        {
            section: 'System',
            items: [
                { id: 'audit',    label: 'Audit Log', icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>` },
                { id: 'settings', label: 'Settings',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>` },
            ]
        }
    ]

    return html`
        <aside class=${'sidebar ' + (expanded ? 'expanded' : '')}>
            <div class="sidebar-logo">
                <svg class="sidebar-logo-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
                    <rect width="32" height="32" rx="8" fill="#0e0e1a"/>
                    <polygon points="18,3 8,18 15,18 14,29 24,14 17,14" fill="#00e5b8" stroke="#00e5b8" stroke-width="0.5" stroke-linejoin="round"/>
                </svg>
                <div class="sidebar-logo-text">
                    <div class="sidebar-logo-title">Signal Engine</div>
                    <div class="sidebar-logo-sub">v5.0.0</div>
                </div>
            </div>
            <nav class="sidebar-nav">
                ${navItems.map(section => html`
                    <div key=${section.section}>
                        <div class="nav-section-label">${section.section}</div>
                        ${section.items.map(item => html`
                            <div key=${item.id}
                                class=${'nav-item ' + (page === item.id ? 'active' : '')}
                                onClick=${() => navigate(item.id)}
                                tabindex="0"
                                onKeyDown=${e => (e.key === 'Enter' || e.key === ' ') && navigate(item.id)}>
                                ${item.icon}
                                <span class="nav-item-label">${item.label}</span>
                                <span class="nav-tooltip">${item.label}</span>
                            </div>
                        `)}
                    </div>
                `)}
            </nav>
            <button class="sidebar-toggle" onClick=${onToggle}>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
        { id: 'overview',  label: 'Overview', icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>` },
        { id: 'signals',   label: 'Signals',  icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>` },
        { id: 'freqtrade', label: 'Trades',   icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>` },
        { id: 'coins',     label: 'Coins',    icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>` },
        { id: 'settings',  label: 'Settings', icon: html`<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>` },
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