var { h, render, Fragment } = preact
var { useState, useEffect } = preactHooks
var html = window.html
var { init, usePage, navigate } = Store
var {
    GradeBadge, DirBadge, OutcomeBadge, ScoreBar,
    Spinner, EmptyState, LoadingSkeleton,
    HealthDot, HealthRow, TradeProgressBar,
    TotpModal, Toast, Ticker, Topbar, BottomNav,
    Panel, Modal, Alert, InfoRow, ConfluenceBar,
    RegimeBadge, SessionBadge, ScoreRing, ConfidenceGauge
} = SE

function App() {
    const page              = usePage()
    const [ready, setReady] = useState(false)

    useEffect(() => {
        init().then(ok => { if (ok) setReady(true) })
    }, [])

    if (!ready) return html`
        <div style="display:flex;align-items:center;justify-content:center;height:100vh;height:100dvh;flex-direction:column;gap:20px;background:var(--bg);">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="#0a0a0f"/>
                <polygon points="18,3 8,18 15,18 14,29 24,14 17,14"
                    fill="#00d4aa" stroke="#00d4aa" stroke-width="0.5"
                    stroke-linejoin="round"/>
            </svg>
            <div style="display:flex;align-items:center;gap:10px;color:var(--text-3);font-size:var(--text-sm);">
                <span class="spinner spinner-sm spinner-brand"></span>
                <span>Loading Signal Engine...</span>
            </div>
        </div>
    `

    const pages = {
        now:         html`<${NowPage}/>`,
        positions:   html`<${PositionsPage}/>`,
        performance: html`<${PerformancePage}/>`,
        universe:    html`<${UniversePage}/>`,
        system:      html`<${SystemPage}/>`,
    }

    return html`
        <div class="app">
            <${Topbar} page=${page}/>
            <${Ticker}/>
            <main id="main-content" class="page-content" role="main">
                ${pages[page] || pages.now}
            </main>
            <${BottomNav} page=${page}/>
            <${TotpModal}/>
            <${Toast}/>
        </div>
    `
}

render(html`<${App}/>`, document.getElementById('root'))