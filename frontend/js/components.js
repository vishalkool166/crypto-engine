var { h, Fragment } = preact
var { useState, useEffect, useRef, useCallback } = preactHooks
var html = window.html
var {
    confirmTotp, closeTotp, useTotp, useToast, useWsState,
    useMode, useNextScan, usePage, logout,
    navigate, requireTotp, toggleTheme, useTheme,
    useRegime, useConfidence, hideToast, useTopbarState
} = Store

function GradeBadge({ grade, size }) {
    const cls = size === 'lg' ? Utils.gradeBadgeClass(grade) + ' badge-grade-lg'
              : size === 'xl' ? Utils.gradeBadgeClass(grade) + ' badge-grade-xl'
              : Utils.gradeBadgeClass(grade)
    return html`<span class=${cls}>${grade}</span>`
}

function DirBadge({ dir }) {
    const isLong  = dir === 'LONG'
    const isShort = dir === 'SHORT'
    return html`
        <span class=${Utils.dirBadgeClass(dir)}>
            ${isLong && html`
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2.5"
                    stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5"/>
                    <polyline points="5 12 12 5 19 12"/>
                </svg>
            `}
            ${isShort && html`
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2.5"
                    stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"/>
                    <polyline points="19 12 12 19 5 12"/>
                </svg>
            `}
            ${dir}
        </span>
    `
}

function OutcomeBadge({ outcome }) {
    return html`<span class=${Utils.outcomeBadgeClass(outcome)}>${outcome}</span>`
}

function RegimeBadge({ regime }) {
    if (!regime || regime === '--') return null
    return html`<span class=${Utils.regimeBadgeClass(regime)}>${regime}</span>`
}

function SessionBadge({ session }) {
    if (!session || session === '--') return null
    return html`<span class=${Utils.sessionBadgeClass(session)}>${Utils.sessionLabel(session)}</span>`
}

function HealthDot({ state, size = 'md' }) {
    const cls = size === 'sm'
        ? Utils.healthDotClass(state).replace('status-dot-md', 'status-dot-sm')
        : Utils.healthDotClass(state)
    return html`
        <div class=${cls}>
            <div class="status-dot-inner"></div>
        </div>
    `
}

function ScoreBar({ score, grade }) {
    const g   = grade || Utils.scoreGrade(score)
    const pct = Math.min(100, Math.max(0, parseFloat(score) || 0))
    return html`
        <div class="score-bar">
            <span class=${'score-bar-value ' + g}>${Math.round(pct)}</span>
            <div class="score-bar-track">
                <div class=${'score-bar-fill ' + g} style=${'width:' + pct + '%'}></div>
            </div>
        </div>
    `
}

function ScoreRing({ score, grade, size = 64 }) {
    const ref = useRef(null)
    const id  = useRef('score-ring-' + Math.random().toString(36).slice(2))
    useEffect(() => {
        if (ref.current) Charts.scoreRing(id.current, score, grade, size)
    }, [score, grade, size])
    return html`<div id=${id.current} ref=${ref}></div>`
}

function ConfidenceGauge({ value, size = 56 }) {
    const ref = useRef(null)
    const id  = useRef('conf-gauge-' + Math.random().toString(36).slice(2))
    useEffect(() => {
        if (ref.current) Charts.confidenceGauge(id.current, value, size)
    }, [value, size])
    return html`<div id=${id.current} ref=${ref}></div>`
}

function Spinner({ size = 'sm', color = 'identity' }) {
    return html`<span
        class=${'spinner spinner-' + size + ' spinner-' + color}
        role="status"
        aria-label="Loading">
    </span>`
}

function EmptyState({ icon, title, desc, action, size = 'md' }) {
    const cls = size === 'sm' ? 'empty-state empty-state-sm' : 'empty-state'
    return html`
        <div class=${cls} role="status">
            <div class="empty-state-icon">
                ${icon || html`
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                `}
            </div>
            ${title && html`<div class="empty-state-title">${title}</div>`}
            ${desc  && html`<div class="empty-state-desc">${desc}</div>`}
            ${action && html`<div class="empty-state-action">${action}</div>`}
        </div>
    `
}

function LoadingSkeleton({ rows = 4, type = 'row' }) {
    return html`
        <div class="skeleton-list" role="status" aria-label="Loading" aria-busy="true">
            ${Array.from({ length: rows }).map((_, i) => html`
                <div key=${i} class=${'skeleton skeleton-' + type} aria-hidden="true"></div>
            `)}
        </div>
    `
}

function Alert({ type = 'info', title, children }) {
    const icons = {
        error:   html`<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
        success: html`<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`,
        warning: html`<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
        info:    html`<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    }
    return html`
        <div class=${'alert alert-' + type}>
            ${icons[type]}
            <div class="alert-content">
                ${title && html`<div class="alert-title">${title}</div>`}
                <div class="alert-desc">${children}</div>
            </div>
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

    const totalRange = Math.abs(tp - sl)
    if (totalRange <= 0) return null

    const entryPct   = (Math.abs(entry - sl) / totalRange) * 100
    const currentPct = Utils.clamp((Math.abs(current - sl) / totalRange) * 100, 0, 100)

    const movingTowardTp = isShort ? current < entry : current > entry
    const dotClass       = movingTowardTp ? 'profit' : 'loss'

    const remaining = movingTowardTp
        ? Math.max(0, 100 - ((Math.abs(current - entry) / Math.abs(tp - entry)) * 100)).toFixed(1)
        : Math.max(0, 100 - ((Math.abs(current - entry) / Math.abs(sl - entry)) * 100)).toFixed(1)

    const label = movingTowardTp
        ? remaining + '% to TP'
        : remaining + '% to SL'

    return html`
        <div class="trade-progress">
            <div class="trade-progress-track">
                <div class="trade-progress-sl-fill"
                    style=${'width:' + entryPct + '%'}></div>
                <div class="trade-progress-tp-fill"
                    style=${'width:' + (100 - entryPct) + '%'}></div>
                <div class="trade-progress-entry"
                    style=${'left:' + entryPct + '%'}></div>
                <div class=${'trade-progress-current ' + dotClass}
                    style=${'left:' + currentPct + '%'}></div>
            </div>
            <div class="trade-progress-labels">
                <span class="trade-progress-label sl">${Utils.fmtPrice(sl)}</span>
                <span class="trade-progress-label center">${label}</span>
                <span class="trade-progress-label tp">${Utils.fmtPrice(tp)}</span>
            </div>
        </div>
    `
}

function HealthRow({ health }) {
    if (!health) return html`
        <div class="health-row health-row-unknown">
            <${HealthDot} state="unknown"/>
            <span>Checking...</span>
        </div>
    `
    const state = health.state || 'UNKNOWN'
    const msg   = health.failures?.[0] || health.warnings?.[0] || ''
    return html`
        <div class=${Utils.healthRowClass(state)}>
            <${HealthDot} state=${state}/>
            <span style="font-weight:var(--weight-bold);">${state}</span>
            ${msg && html`<span class="health-row-message">— ${msg}</span>`}
        </div>
    `
}

function ConfluenceBar({ factor }) {
    const pct     = factor.max > 0 ? (factor.earned / factor.max) * 100 : 0
    const passing = factor.earned >= factor.max * 0.6
    const cls     = passing ? 'pass' : factor.earned > 0 ? 'partial' : 'fail'
    return html`
        <div class="confluence-bar">
            <div class="confluence-bar-header">
                <span class="confluence-bar-label">
                    ${(factor.key || '').replace(/_/g, ' ')}
                </span>
                <span class=${'confluence-bar-score ' + cls}>
                    ${factor.earned}/${factor.max}
                </span>
            </div>
            <div class="confluence-bar-track">
                <div class=${'confluence-bar-fill ' + cls}
                    style=${'width:' + pct + '%'}></div>
            </div>
        </div>
    `
}

function InfoRow({ label, value, mono, color, children }) {
    return html`
        <div class="info-row">
            <span class="info-row-label">${label}</span>
            <span class=${'info-row-value' + (mono ? ' text-mono' : '')}
                style=${color ? 'color:' + color : ''}>
                ${children || value}
            </span>
        </div>
    `
}

function Panel({ show, onClose, title, subtitle, children, footer, width }) {
    useEffect(() => {
        if (!show) return
        const handler = e => e.key === 'Escape' && onClose()
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [show])

    useEffect(() => {
        document.body.style.overflow = show ? 'hidden' : ''
        return () => { document.body.style.overflow = '' }
    }, [show])

    if (!show) return null

    return html`
        <div>
            <div class="panel-overlay" onClick=${onClose}></div>
            <div class="panel"
                style=${width ? 'width:' + width : ''}
                role="dialog"
                aria-modal="true"
                aria-label=${title}>
                <div class="panel-header">
                    <div style="min-width:0;">
                        <div class="panel-title">${title}</div>
                        ${subtitle && html`
                            <div style="font-size:var(--text-caption1);color:var(--label-3);margin-top:3px;letter-spacing:var(--tracking-caption1);">
                                ${subtitle}
                            </div>
                        `}
                    </div>
                    <button class="panel-close" onClick=${onClose} aria-label="Close panel">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                            viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
                <div class="panel-body">${children}</div>
                ${footer && html`<div class="panel-footer">${footer}</div>`}
            </div>
        </div>
    `
}

function Modal({ show, onClose, title, subtitle, icon, iconType, danger, children, footer, size }) {
    useEffect(() => {
        if (!show) return
        const handler = e => e.key === 'Escape' && onClose()
        document.addEventListener('keydown', handler)
        return () => document.removeEventListener('keydown', handler)
    }, [show])

    useEffect(() => {
        document.body.style.overflow = show ? 'hidden' : ''
        return () => { document.body.style.overflow = '' }
    }, [show])

    if (!show) return null

    const modalCls = [
        'modal',
        size === 'sm' ? 'modal-sm' : size === 'lg' ? 'modal-lg' : size === 'xl' ? 'modal-xl' : '',
        danger ? 'modal-danger' : ''
    ].filter(Boolean).join(' ')

    return html`
        <div class="modal-overlay"
            role="dialog"
            aria-modal="true"
            aria-label=${title}
            onClick=${e => e.target === e.currentTarget && onClose()}>
            <div class=${modalCls}>
                <div class="modal-handle"></div>
                <div class="modal-header">
                    <div class="modal-header-left">
                        ${icon && html`
                            <div class=${'modal-icon modal-icon-' + (iconType || 'identity')}>
                                ${icon}
                            </div>
                        `}
                        <div class="modal-title">${title}</div>
                        ${subtitle && html`
                            <div class="modal-subtitle">${subtitle}</div>
                        `}
                    </div>
                    <button class="modal-close" onClick=${onClose} aria-label="Close">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                            viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
                <div class="modal-body">${children}</div>
                ${footer && html`
                    <div>
                        <div class="modal-divider"></div>
                        <div class="modal-footer">${footer}</div>
                    </div>
                `}
            </div>
        </div>
    `
}

function TotpModal() {
    const totp                    = useTotp()
    const [code,    setCode]      = useState('')
    const [sent,    setSent]      = useState(false)
    const [sending, setSending]   = useState(false)
    const inputRef                = useRef(null)

    useEffect(() => {
        if (totp.show) {
            setCode('')
            setSent(false)
            setTimeout(() => inputRef.current?.focus(), 80)
        }
    }, [totp.show])

    async function sendViaTelegram() {
        setSending(true)
        try {
            const res  = await fetch('/auth/request-totp', { method: 'POST' })
            const data = await res.json()
            if (data.success) {
                setSent(true)
                setTimeout(() => setSent(false), 35000)
            }
        } catch(e) {}
        setSending(false)
    }

    if (!totp.show) return null

    return html`
        <div class="modal-overlay totp-modal"
            role="dialog"
            aria-modal="true"
            aria-label=${totp.title}
            onClick=${e => e.target === e.currentTarget && closeTotp()}>
            <div class="modal modal-sm">
                <div class="modal-handle"></div>
                <div class="modal-header">
                    <div class="modal-header-left">
                        <div class="modal-icon modal-icon-identity">
                            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"
                                viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                            </svg>
                        </div>
                        <div class="modal-title">${totp.title}</div>
                        <div class="modal-subtitle">${totp.subtitle}</div>
                    </div>
                    <button class="modal-close" onClick=${closeTotp} aria-label="Close">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
                <div class="modal-body" style="align-items:center;text-align:center;gap:16px;">
                    <label for="totp-modal-input" class="sr-only">6-digit TOTP code</label>
                    <input
                        id="totp-modal-input"
                        ref=${inputRef}
                        class=${'totp-input' + (code.length === 6 ? ' totp-input-success' : '')}
                        type="text"
                        inputmode="numeric"
                        maxlength="6"
                        value=${code}
                        placeholder="000000"
                        autocomplete="one-time-code"
                        aria-required="true"
                        onInput=${e => setCode(e.target.value.replace(/\D/g, ''))}
                        onKeyDown=${e => e.key === 'Enter' && code.length === 6 && confirmTotp(code)}
                    />
                    <button class="totp-modal-telegram"
                        onClick=${sendViaTelegram}
                        disabled=${sending || sent}>
                        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15"
                            viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"/>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                        </svg>
                        ${sent
                            ? 'Code sent — check Telegram'
                            : sending
                            ? 'Sending...'
                            : 'Send code via Telegram'
                        }
                    </button>
                    ${sent && html`
                        <div style="font-size:var(--text-caption1);color:var(--profit);letter-spacing:var(--tracking-caption1);">
                            Valid for 30 seconds
                        </div>
                    `}
                </div>
                <div class="modal-divider"></div>
                <div class="modal-footer">
                    <button class="btn btn-ghost btn-sm" onClick=${closeTotp}>Cancel</button>
                    <button class="btn btn-primary"
                        onClick=${() => confirmTotp(code)}
                        disabled=${code.length < 6}
                        aria-label="Confirm">
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

    const icons = {
        success: html`<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`,
        error:   html`<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
        warning: html`<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
        info:    html`<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
        signal:  html`<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    }

    return html`
        <div class="toast-container" role="status" aria-live="polite" aria-atomic="true">
            <div class=${'toast toast-' + (toast.type || 'info')}>
                <div class="toast-icon">
                    ${icons[toast.type] || icons.info}
                </div>
                <div class="toast-content">
                    <div class="toast-title">${toast.message}</div>
                </div>
                <button class="toast-close" onClick=${hideToast} aria-label="Dismiss">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        </div>
    `
}

function MobileTopbarCenter({ topbarState, onTap }) {
    const prevType  = useRef(null)
    const [visible, setVisible] = useState(true)

    useEffect(() => {
        if (prevType.current && prevType.current !== topbarState.type) {
            setVisible(false)
            setTimeout(() => {
                setVisible(true)
                prevType.current = topbarState.type
            }, 160)
        } else {
            prevType.current = topbarState.type
        }
    }, [topbarState.type])

    const canTap = topbarState.type !== 'watching'

    return html`
        <div
            class=${'mobile-topbar-center ' + topbarState.color}
            onClick=${canTap ? onTap : undefined}
            role=${canTap ? 'button' : undefined}
            aria-label=${canTap ? topbarState.primary : undefined}
            style=${'opacity:' + (visible ? '1' : '0') + ';transition:opacity 160ms var(--ease-out);'}
        >
            <div class="mobile-topbar-primary"
                style="animation:topbar-state-in 200ms var(--ease-out);">
                ${topbarState.primary}
            </div>
            <div class="mobile-topbar-secondary"
                style="animation:topbar-state-in 200ms var(--ease-out) 40ms both;">
                ${topbarState.secondary}
            </div>
        </div>
    `
}

function Topbar({ page, onTopbarTap }) {
    const wsState     = useWsState()
    const mode        = useMode()
    const regime      = useRegime()
    const conf        = useConfidence()
    const theme       = useTheme()
    const arc         = useNextScan()
    const topbarState = useTopbarState()
    const [scanning,  setScanning] = useState(false)
    const mobile      = Utils.isMobile()

    const navItems = [
        { id: 'now',         label: 'Now'         },
        { id: 'positions',   label: 'Positions'   },
        { id: 'performance', label: 'Performance' },
        { id: 'universe',    label: 'Universe'    },
        { id: 'system',      label: 'System'      },
    ]

    const wsLabel = wsState === 'connected'  ? 'Live'
                  : wsState === 'connecting' ? 'Connecting'
                  : 'Offline'

    async function handleScanTap() {
        if (scanning) return
        setScanning(true)
        try {
            await fetch('/api/scan', { credentials: 'include' })
            Store.showToast('Scan triggered', 'success')
        } catch(e) {
            Store.showToast('Scan failed', 'error')
        } finally {
            setTimeout(() => setScanning(false), 3000)
        }
    }

    function handleCenterTap() {
        if (onTopbarTap) onTopbarTap(topbarState)
    }

    if (mobile) return html`
        <header class="topbar" role="banner">
            <div class=${'topbar-mode ' + mode}
                role="status"
                aria-label=${'Trading mode: ' + mode}
                style="flex-shrink:0;"
                onClick=${() => navigate('system')}>
                <div class="topbar-mode-dot" aria-hidden="true"></div>
                <span>${mode.toUpperCase()}</span>
            </div>

            <${MobileTopbarCenter}
                topbarState=${topbarState}
                onTap=${handleCenterTap}
            />

            <button
                class="mobile-topbar-scan-btn"
                onClick=${handleScanTap}
                disabled=${scanning}
                aria-label="Scan now"
                style="flex-shrink:0;">
                ${scanning
                    ? html`<${Spinner} size="xs" color="identity"/>`
                    : html`
                        <svg viewBox="0 0 28 28" style="transform:rotate(-90deg);width:28px;height:28px;">
                            <circle cx="14" cy="14" r="11"
                                fill="none"
                                stroke="rgba(255,255,255,0.08)"
                                stroke-width="2.5"/>
                            <circle cx="14" cy="14" r="11"
                                fill="none"
                                stroke="var(--brand-identity)"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                stroke-dasharray=${(() => {
                                    const c = 2 * Math.PI * 11
                                    const f = c * (arc.pct || 0)
                                    return f + ' ' + (c - f)
                                })()}
                                style="transition:stroke-dasharray 1s linear;"
                            />
                        </svg>
                        <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:7px;font-family:var(--font-mono);font-weight:var(--weight-bold);color:var(--label-3);">
                            ${arc.mins}m
                        </div>
                    `
                }
            </button>
        </header>
    `

    return html`
        <header class="topbar" role="banner">
            <a class="topbar-brand" href="#"
                onClick=${e => { e.preventDefault(); navigate('now') }}
                aria-label="Signal Engine v5">
                <svg class="topbar-brand-icon"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 32 32" fill="none" aria-hidden="true">
                    <rect width="32" height="32" rx="8" fill="#0a0a0f"/>
                    <polygon points="18,3 8,18 15,18 14,29 24,14 17,14"
                        fill="#00C7BE" stroke="#00C7BE" stroke-width="0.5"
                        stroke-linejoin="round"/>
                </svg>
                <div>
                    <div class="topbar-brand-name">Signal Engine</div>
                </div>
            </a>

            <nav class="topbar-nav" role="navigation" aria-label="Main navigation">
                ${navItems.map(item => html`
                    <button key=${item.id}
                        class=${'topbar-nav-item ' + (page === item.id ? 'active' : '')}
                        onClick=${() => navigate(item.id)}
                        aria-current=${page === item.id ? 'page' : 'false'}>
                        ${item.label}
                    </button>
                `)}
            </nav>

            <div class="topbar-right">
                ${regime && regime !== '--' && html`
                    <div class=${Utils.regimeTopbarClass(regime)}
                        aria-label=${'Market regime: ' + regime}>
                        <span>${regime}</span>
                    </div>
                `}

                <div class="topbar-confidence"
                    aria-label=${'Bot confidence: ' + conf}>
                    <span>Conf</span>
                    <span class="topbar-confidence-value">${conf}</span>
                </div>

                <div class="topbar-divider" aria-hidden="true"></div>

                <div class=${'topbar-mode ' + mode}
                    role="status"
                    aria-label=${'Trading mode: ' + mode}>
                    <div class="topbar-mode-dot" aria-hidden="true"></div>
                    <span>${mode.toUpperCase()}</span>
                </div>

                <div class="topbar-divider" aria-hidden="true"></div>

                <div class="topbar-ws"
                    role="status"
                    aria-label=${'Connection: ' + wsLabel}>
                    <div class=${'topbar-ws-dot ' + wsState} aria-hidden="true"></div>
                    <span>${wsLabel}</span>
                </div>

                <div class="topbar-divider" aria-hidden="true"></div>

                <div class="topbar-scan-arc"
                    aria-label=${'Next scan in ' + arc.mins + ':' + arc.secs}>
                    <svg viewBox="0 0 28 28" style="transform:rotate(-90deg);">
                        <circle cx="14" cy="14" r="11"
                            fill="none"
                            stroke="rgba(255,255,255,0.06)"
                            stroke-width="2.5"/>
                        <circle cx="14" cy="14" r="11"
                            fill="none"
                            stroke="var(--brand-identity)"
                            stroke-width="2.5"
                            stroke-linecap="round"
                            stroke-dasharray=${(() => {
                                const c = 2 * Math.PI * 11
                                const f = c * (arc.pct || 0)
                                return f + ' ' + (c - f)
                            })()}
                            style="transition:stroke-dasharray 1s linear;"
                        />
                    </svg>
                    <div class="topbar-scan-arc-label">${arc.mins}m</div>
                </div>

                <button class="topbar-theme-btn"
                    onClick=${toggleTheme}
                    aria-label=${theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
                    ${theme === 'dark'
                        ? html`<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
                        : html`<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`
                    }
                </button>

                <button class="topbar-logout-btn" onClick=${logout} aria-label="Log out">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                        aria-hidden="true">
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
        {
            id:    'now',
            label: 'Now',
            icon:  html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`
        },
        {
            id:    'positions',
            label: 'Positions',
            icon:  html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`
        },
        {
            id:    'performance',
            label: 'Perf',
            icon:  html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`
        },
        {
            id:    'universe',
            label: 'Universe',
            icon:  html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`
        },
        {
            id:    'system',
            label: 'System',
            icon:  html`<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`
        },
    ]

    return html`
        <nav class="bottom-nav" role="navigation" aria-label="Mobile navigation">
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

window.SE = {
    GradeBadge, DirBadge, OutcomeBadge, RegimeBadge, SessionBadge,
    HealthDot, HealthRow, ScoreBar, ScoreRing, ConfidenceGauge,
    Spinner, EmptyState, LoadingSkeleton, Alert,
    TradeProgressBar, ConfluenceBar, InfoRow,
    Panel, Modal, TotpModal, Toast,
    Topbar, BottomNav,
    MobileTopbarCenter,
}