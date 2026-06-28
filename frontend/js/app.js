var { h, render, Fragment } = preact
var { useState, useEffect }  = preactHooks
var html  = window.html
var { init, usePage, navigate, useTopbarState, on } = Store
var {
    GradeBadge, DirBadge, OutcomeBadge, ScoreBar,
    Spinner, EmptyState, LoadingSkeleton,
    HealthDot, HealthRow, TradeProgressBar,
    TotpModal, Toast,
    Topbar, BottomNav,
    Panel, Modal, Alert, InfoRow, ConfluenceBar,
    RegimeBadge, SessionBadge, ScoreRing, ConfidenceGauge
} = SE

function App() {
    const page                        = usePage()
    const [ready,       setReady]     = useState(false)
    const [openTrade,   setOpenTrade] = useState(null)
    const [openSignal,  setOpenSignal]= useState(null)

    useEffect(() => {
        init().then(ok => { if (ok) setReady(true) })
    }, [])

    useEffect(() => {
        const unsub = on('topbar:open-trade', trade => {
            setOpenTrade(trade)
            navigate('positions')
        })
        return unsub
    }, [])

    useEffect(() => {
        const unsub = on('topbar:open-signal', signal => {
            setOpenSignal(signal)
            navigate('now')
        })
        return unsub
    }, [])

    function handleTopbarTap(topbarState) {
        if (!topbarState) return
        if (topbarState.trade) {
            Store.emit('topbar:open-trade', topbarState.trade)
        } else if (topbarState.signal) {
            Store.emit('topbar:open-signal', topbarState.signal)
        }
    }

    if (!ready) return html`
        <div style="display:flex;align-items:center;justify-content:center;height:100vh;height:100dvh;flex-direction:column;gap:20px;background:var(--bg);">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="#0a0a0f"/>
                <polygon points="18,3 8,18 15,18 14,29 24,14 17,14"
                    fill="#00C7BE" stroke="#00C7BE" stroke-width="0.5"
                    stroke-linejoin="round"/>
            </svg>
            <div style="display:flex;align-items:center;gap:10px;color:var(--text-3);font-size:var(--text-sm);">
                <span class="spinner spinner-sm spinner-identity"></span>
                <span>Loading Signal Engine...</span>
            </div>
        </div>
    `

    const pages = {
        now:         html`<${NowPage}        externalSignal=${openSignal} onSignalConsumed=${() => setOpenSignal(null)}/>`,
        positions:   html`<${PositionsPage}  externalTrade=${openTrade}  onTradeConsumed=${()  => setOpenTrade(null)}/>`,
        performance: html`<${PerformancePage}/>`,
        universe:    html`<${UniversePage}/>`,
        system:      html`<${SystemPage}/>`,
    }

    return html`
        <div class="app">
            <${Topbar} page=${page} onTopbarTap=${handleTopbarTap}/>
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