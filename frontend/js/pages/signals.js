import { h, Fragment } from '/js/preact.min.js'
import { useState, useEffect, useCallback } from '/js/preact-hooks.min.js'
import { html, GradeBadge, DirBadge, OutcomeBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton } from '/js/components.js'
import { showToast } from '/js/store.js'

export function SignalsPage() {
    const [signals,     setSignals]     = useState([])
    const [filtered,    setFiltered]    = useState([])
    const [loading,     setLoading]     = useState(false)
    const [expanded,    setExpanded]    = useState(null)
    const [currentPage, setCurrentPage] = useState(1)
    const [filters,     setFilters]     = useState({
        grade: '', outcome: '', direction: '', coin: '', limit: '100'
    })

    const pageSize   = 30
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
    const paginated  = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)

    useEffect(() => { load(filters) }, [])

    async function load(f, reset = false) {
        if (reset) { setCurrentPage(1); setExpanded(null) }
        setLoading(true)
        try {
            const q = new URLSearchParams()
            q.set('limit', parseInt(f.limit) || 100)
            if (f.grade)   q.set('grade',   f.grade)
            if (f.coin)    q.set('coin',     f.coin.toUpperCase().trim())
            if (f.outcome) q.set('outcome',  f.outcome)
            const res = await fetch('/api/signals?' + q.toString(), { credentials: 'include' })
            if (res.status === 401) { window.location.href = '/login.html'; return }
            const data = await res.json()
            const sigs = data || []
            setSignals(sigs)
            applyClientFilters(sigs, f)
        } catch(e) {
            showToast('Failed to load signals: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    function applyClientFilters(sigs, f) {
        let result = [...(sigs || signals)]
        if (f.direction) result = result.filter(s => s.direction === f.direction)
        setFiltered(result)
        setCurrentPage(1)
    }

    function handleFilterChange(key, val) {
        const next = { ...filters, [key]: val }
        setFilters(next)
        if (key === 'direction') {
            applyClientFilters(signals, next)
        } else {
            load(next, true)
        }
    }

    function clearFilters() {
        const f = { grade: '', outcome: '', direction: '', coin: '', limit: '100' }
        setFilters(f)
        load(f, true)
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Signals</div>
                    <div class="page-subtitle" aria-live="polite">${filtered.length} signals</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${() => load(filters, true)}
                    disabled=${loading} aria-label="Refresh signals">
                    ${loading ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                            <polyline points="23 4 23 10 17 10"/>
                            <polyline points="1 20 1 14 7 14"/>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                    `}
                    Refresh
                </button>
            </div>

            <div class="card mb-12">
                <div class="filter-bar" role="search" aria-label="Signal filters">
                    <select class="select" style="width:120px;" value=${filters.grade}
                        aria-label="Filter by grade"
                        onChange=${e => handleFilterChange('grade', e.target.value)}>
                        <option value="">All Grades</option>
                        <option value="A+">A+</option>
                        <option value="A">A</option>
                        <option value="B">B</option>
                        <option value="C">C</option>
                        <option value="F">F</option>
                    </select>
                    <select class="select" style="width:130px;" value=${filters.outcome}
                        aria-label="Filter by outcome"
                        onChange=${e => handleFilterChange('outcome', e.target.value)}>
                        <option value="">All Outcomes</option>
                        <option value="win">Win</option>
                        <option value="loss">Loss</option>
                        <option value="pending">Pending</option>
                    </select>
                    <select class="select" style="width:120px;" value=${filters.direction}
                        aria-label="Filter by direction"
                        onChange=${e => handleFilterChange('direction', e.target.value)}>
                        <option value="">All Directions</option>
                        <option value="LONG">Long</option>
                        <option value="SHORT">Short</option>
                    </select>
                    <input class="input" style="width:110px;" type="text"
                        placeholder="Coin..."
                        aria-label="Filter by coin symbol"
                        value=${filters.coin}
                        onInput=${e => setFilters(f => ({ ...f, coin: e.target.value }))}
                        onKeyDown=${e => e.key === 'Enter' && handleFilterChange('coin', e.target.value)}/>
                    <select class="select" style="width:100px;" value=${filters.limit}
                        aria-label="Number of rows to show"
                        onChange=${e => handleFilterChange('limit', e.target.value)}>
                        <option value="50">50 rows</option>
                        <option value="100">100 rows</option>
                        <option value="200">200 rows</option>
                        <option value="500">500 rows</option>
                    </select>
                    <button class="btn btn-ghost btn-sm" onClick=${clearFilters}
                        aria-label="Clear all filters">Clear</button>
                    <div class="flex-1"></div>
                    <span style="font-size:11px;color:var(--text-secondary);" aria-live="polite">
                        <span style="font-family:var(--font-mono);color:var(--text-primary);">${filtered.length}</span>
                        ${' '}of${' '}
                        <span style="font-family:var(--font-mono);">${signals.length}</span>
                    </span>
                </div>
            </div>

            <div class="card">
                ${loading
                    ? html`<${LoadingSkeleton} rows=${5}/>`
                    : html`
                        <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
                            <table aria-label="Trading signals">
                                <thead>
                                    <tr>
                                        <th scope="col">#</th>
                                        <th scope="col">Time</th>
                                        <th scope="col">Coin</th>
                                        <th scope="col">Dir</th>
                                        <th scope="col">Grade</th>
                                        <th scope="col">Score</th>
                                        <th scope="col">Entry</th>
                                        <th scope="col">SL</th>
                                        <th scope="col">TP</th>
                                        <th scope="col">Exit</th>
                                        <th scope="col">PnL</th>
                                        <th scope="col">Result</th>
                                        <th scope="col">Regime</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!paginated.length
                                        ? html`<tr><td colspan="13"><${EmptyState} message="No signals match filters"/></td></tr>`
                                        : paginated.map(s => html`
                                            <${Fragment} key=${s.id}>
                                                <tr style="cursor:pointer;background:${expanded === s.id ? 'var(--bg-tertiary)' : ''};"
                                                    onClick=${() => setExpanded(expanded === s.id ? null : s.id)}
                                                    role="button"
                                                    tabindex="0"
                                                    aria-expanded=${expanded === s.id}
                                                    aria-label=${'Signal ' + s.id + ' ' + s.coin + ' ' + s.direction}
                                                    onKeyDown=${e => (e.key === 'Enter' || e.key === ' ') && setExpanded(expanded === s.id ? null : s.id)}>
                                                    <td><span style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;">${s.id}</span></td>
                                                    <td><span style="font-size:11px;color:var(--text-secondary);">${Utils.fmtTimeAgo(s.timestamp)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);font-weight:700;">${s.coin}</span></td>
                                                    <td><${DirBadge} dir=${s.direction}/></td>
                                                    <td><${GradeBadge} grade=${s.grade}/></td>
                                                    <td><${ScoreBar} score=${s.score}/></td>
                                                    <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(s.entry)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);color:var(--red);">${Utils.fmtPrice(s.sl)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);color:var(--green);">${Utils.fmtPrice(s.tp1)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(s.exit_price)}</span></td>
                                                    <td><span style="font-family:var(--font-mono);font-weight:700;color:${Utils.pnlColor(s.pnl)};">${s.pnl != null ? Utils.fmtPnl(s.pnl) : '--'}</span></td>
                                                    <td><${OutcomeBadge} outcome=${s.outcome}/></td>
                                                    <td><span style="font-size:11px;color:var(--text-muted);">${s.regime || '--'}</span></td>
                                                </tr>
                                                ${expanded === s.id && html`
                                                    <tr>
                                                        <td colspan="13" style="padding:0;background:var(--bg-tertiary);">
                                                            <div style="padding:16px;" role="region"
                                                                aria-label=${'Details for signal ' + s.id}>
                                                                <div class="grid-4" style="gap:8px;">
                                                                    <div class="level-item">
                                                                        <div class="level-label">Signal ID</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">${s.id}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Risk Amount</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">
                                                                            ${s.risk_amt ? '$' + parseFloat(s.risk_amt).toFixed(2) : '--'}
                                                                        </div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Market Score</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">
                                                                            ${s.market_score != null ? s.market_score + '/100' : '--'}
                                                                        </div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Entry Score</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">
                                                                            ${s.entry_score != null ? s.entry_score + '/100' : '--'}
                                                                        </div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">BTC Score</div>
                                                                        <div style="font-family:var(--font-mono);font-size:13px;">
                                                                            ${s.btc_score != null ? s.btc_score + '/8' : '--'}
                                                                        </div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Session</div>
                                                                        <div style="font-size:12px;">${s.session || '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Signal Type</div>
                                                                        <div style="font-family:var(--font-mono);font-size:12px;">${s.signal_type || '--'}</div>
                                                                    </div>
                                                                    <div class="level-item">
                                                                        <div class="level-label">Timestamp</div>
                                                                        <div style="font-size:11px;color:var(--text-secondary);">
                                                                            ${Utils.fmtTime(s.timestamp)}
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                `}
                                            </${Fragment}>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                        <div class="pagination" role="navigation" aria-label="Signal pagination">
                            <span class="pagination-info" aria-live="polite">
                                Page ${currentPage} of ${totalPages} · ${filtered.length} signals
                            </span>
                            <div class="pagination-controls">
                                <button class="btn btn-ghost btn-sm"
                                    onClick=${() => setCurrentPage(1)}
                                    disabled=${currentPage <= 1}
                                    aria-label="First page">First</button>
                                <button class="btn btn-ghost btn-sm"
                                    onClick=${() => setCurrentPage(p => p - 1)}
                                    disabled=${currentPage <= 1}
                                    aria-label="Previous page">Prev</button>
                                <span style="padding:4px 10px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);">
                                    ${currentPage} / ${totalPages}
                                </span>
                                <button class="btn btn-ghost btn-sm"
                                    onClick=${() => setCurrentPage(p => p + 1)}
                                    disabled=${currentPage >= totalPages}
                                    aria-label="Next page">Next</button>
                                <button class="btn btn-ghost btn-sm"
                                    onClick=${() => setCurrentPage(totalPages)}
                                    disabled=${currentPage >= totalPages}
                                    aria-label="Last page">Last</button>
                            </div>
                        </div>
                    `}
            </div>
        </div>
    `
}