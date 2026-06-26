import { h, render } from '/js/preact.min.js'
import { useState, useEffect } from '/js/preact-hooks.min.js'
import htm from '/js/htm.min.js'
import { init, usePage } from '/js/store.js'
import { Sidebar, BottomNav, Topbar, Ticker, TotpModal, Toast } from '/js/components.js'
import { OverviewPage }  from '/js/pages/overview.js'
import { SignalsPage }   from '/js/pages/signals.js'
import { FreqtradePage } from '/js/pages/freqtrade.js'
import { CoinsPage }     from '/js/pages/coins.js'
import { BacktestPage }  from '/js/pages/backtest.js'
import { AnalysisPage }  from '/js/pages/analysis.js'
import { AuditPage }     from '/js/pages/audit.js'
import { SettingsPage }  from '/js/pages/settings.js'

const html = htm.bind(h)

function App() {
    const page                    = usePage()
    const [expanded, setExpanded] = useState(false)
    const [ready,    setReady]    = useState(false)

    useEffect(() => {
        init().then(ok => {
            if (ok) setReady(true)
        })
    }, [])

    if (!ready) return html`
        <div style="display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column;gap:16px;">
            <div class="spinner" style="width:24px;height:24px;border-width:3px;"></div>
            <span style="color:var(--text-muted);font-size:13px;">Loading Signal Engine...</span>
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
            <${Sidebar}
                page=${page}
                expanded=${expanded}
                onToggle=${() => setExpanded(p => !p)}
            />
            <div class="main-area">
                <${Topbar} page=${page}/>
                <${Ticker}/>
                <main class="page-content">
                    ${pages[page] || pages.overview}
                </main>
            </div>
            <${BottomNav} page=${page}/>
            <${TotpModal}/>
            <${Toast}/>
        </div>
    `
}

render(html`<${App}/>`, document.getElementById('root'))