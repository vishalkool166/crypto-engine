const { h, render } = preact
const { useState, useEffect } = preactHooks
const html = htm.bind(h)

const { init, usePage, navigate } = Store
const {
    GradeBadge, DirBadge, OutcomeBadge, ScoreBar,
    Spinner, EmptyState, LoadingSkeleton,
    HealthBar, TradeProgressBar, CoinDetailModal,
    TotpModal, Toast, Ticker, Topbar, BottomNav,
} = Components

function App() {
    const page            = usePage()
    const [ready, setReady] = useState(false)

    useEffect(() => {
        init().then(ok => { if (ok) setReady(true) })
    }, [])

    if (!ready) return html`
        <div style="display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;background:var(--bg-primary);">
            <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="var(--bg-secondary)"/>
                <polygon points="18,3 8,18 15,18 14,29 24,14 17,14" fill="var(--blue)" stroke="var(--blue)" stroke-width="0.5" stroke-linejoin="round"/>
            </svg>
            <div class="spinner" style="width:20px;height:20px;border-width:2px;"></div>
        </div>
    `

    const pages = {
        overview:  html`<${OverviewPage}/>`,
        signals:   html`<${SignalsPage}/>`,
        freqtrade: html`<${FreqtradePage}/>`,
        coins:     html`<${CoinsPage}/>`,
        backtest:  html`<${BacktestPage}/>`,
        analysis:  html`<${AnalysisPage}/>`,
        audit:     html`<${AuditPage}/>`,
        settings:  html`<${SettingsPage}/>`,
    }

    return html`
        <div class="app-layout">
            <${Topbar} page=${page}/>
            <${Ticker}/>
            <main class="page-content">
                ${pages[page] || pages.overview}
            </main>
            <${BottomNav} page=${page}/>
            <${TotpModal}/>
            <${Toast}/>
        </div>
    `
}

render(html`<${App}/>`, document.getElementById('root'))