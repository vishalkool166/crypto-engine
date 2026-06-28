var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { useDashboard, showToast } = Store
var { GradeBadge, DirBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton, Panel, InfoRow, ConfluenceBar, RegimeBadge, SessionBadge } = SE

function UniversePage() {
    const data                              = useDashboard()
    const [coins,        setCoins]          = useState([])
    const [loading,      setLoading]        = useState(false)
    const [adding,       setAdding]         = useState(false)
    const [validating,   setValidating]     = useState(false)
    const [toggling,     setToggling]       = useState(null)
    const [deleting,     setDeleting]       = useState(null)
    const [newCoin,      setNewCoin]        = useState('')
    const [addMsg,       setAddMsg]         = useState('')
    const [addOk,        setAddOk]          = useState(false)
    const [filterStatus, setFilterStatus]   = useState('enabled')
    const [search,       setSearch]         = useState('')
    const [selectedCoin, setSelectedCoin]   = useState(null)
    const [viewMode,     setViewMode]       = useState('grid')

    const filtered = coins.filter(c => {
        if (filterStatus === 'enabled'  && !c.enabled) return false
        if (filterStatus === 'disabled' && c.enabled)  return false
        if (search && !c.coin.includes(search.toUpperCase())) return false
        return true
    })

    const enabledCount = coins.filter(c => c.enabled).length

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.coins()
            setCoins(data || [])
        } catch(e) {
            showToast('Failed to load coins: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    async function addCoin() {
        if (!newCoin || newCoin.length < 2) return
        setAdding(true)
        setAddMsg('')
        setValidating(true)
        try {
            const validation = await API.validateCoin(newCoin)
            setValidating(false)
            if (!validation.valid) {
                setAddOk(false)
                setAddMsg(validation.reason || 'Coin not found on Binance Futures')
                return
            }
            const result = await API.addCoin(newCoin)
            if (result.success) {
                setAddOk(true)
                setAddMsg(result.message || newCoin + ' added successfully')
                setNewCoin('')
                await load()
                showToast(result.message || newCoin + ' added', 'success')
            } else {
                setAddOk(false)
                setAddMsg(result.reason || 'Failed to add coin')
            }
        } catch(e) {
            setValidating(false)
            setAddOk(false)
            setAddMsg(e.message || 'Failed to add coin')
        } finally {
            setAdding(false)
            setValidating(false)
            setTimeout(() => setAddMsg(''), 5000)
        }
    }

    async function toggleCoin(coin) {
        setToggling(coin.coin)
        try {
            await API.toggleCoin(coin.coin, !coin.enabled)
            setCoins(coins.map(c =>
                c.coin === coin.coin ? { ...c, enabled: !c.enabled } : c
            ))
            showToast(coin.coin + (!coin.enabled ? ' enabled' : ' disabled'), 'success')
        } catch(e) {
            showToast('Failed to toggle ' + coin.coin + ': ' + e.message, 'error')
        } finally {
            setToggling(null)
        }
    }

    async function deleteCoin(coinName) {
        const code = await Store.requireTotp(
            'Remove ' + coinName,
            'This will permanently remove ' + coinName + ' from your universe.'
        )
        if (!code) return
        setDeleting(coinName)
        try {
            const res = await fetch('/api/coins/' + coinName, {
                method:      'DELETE',
                credentials: 'include',
                headers:     { 'Content-Type': 'application/json' },
                body:        JSON.stringify({ totp_code: code })
            })
            if (res.ok) {
                setCoins(coins.filter(c => c.coin !== coinName))
                showToast(coinName + ' removed', 'success')
            } else {
                const err = await res.json().catch(() => ({}))
                showToast('Delete failed: ' + (err.detail || 'Unknown error'), 'error')
            }
        } catch(e) {
            showToast('Delete failed: ' + e.message, 'error')
        } finally {
            setDeleting(null)
        }
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Universe</div>
                    <div class="page-subtitle">${enabledCount} enabled · ${coins.length} total</div>
                </div>
                <div class="flex gap-8">
                    <div class="tab-group">
                        <button class=${'tab-btn ' + (viewMode === 'grid'  ? 'active' : '')} onClick=${() => setViewMode('grid')}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                            Grid
                        </button>
                        <button class=${'tab-btn ' + (viewMode === 'table' ? 'active' : '')} onClick=${() => setViewMode('table')}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                            List
                        </button>
                    </div>
                    <button class="btn btn-secondary btn-sm" onClick=${load} disabled=${loading}>
                        ${loading ? html`<${Spinner} size="xs"/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                        `}
                        Refresh
                    </button>
                </div>
            </div>

            <div class="card card-pad mb-16">
                <div class="flex gap-8 items-end flex-wrap">
                    <div class="form-group" style="flex:1;min-width:160px;margin-bottom:0;">
                        <label class="form-label">Add Coin</label>
                        <div class="input-group">
                            <input
                                class="input"
                                type="text"
                                placeholder="BTC, ETH, SOL..."
                                value=${newCoin}
                                onInput=${e => setNewCoin(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                                onKeyDown=${e => e.key === 'Enter' && addCoin()}
                                disabled=${adding}
                                maxlength="10"
                            />
                            <button class="btn btn-primary"
                                onClick=${addCoin}
                                disabled=${adding || !newCoin || newCoin.length < 2}>
                                ${adding ? html`<${Spinner} size="xs" color="white"/>` : html`
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                                `}
                                Add
                            </button>
                        </div>
                    </div>
                </div>
                ${validating && html`
                    <div class="inline-spinner mt-8">
                        <${Spinner} size="xs"/>
                        <span>Validating on Binance Futures...</span>
                    </div>
                `}
                ${addMsg && html`
                    <div class=${'alert mt-12 ' + (addOk ? 'alert-success' : 'alert-error')}>
                        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${addOk
                                ? html`<polyline points="20 6 9 17 4 12"/>`
                                : html`<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>`
                            }
                        </svg>
                        <div class="alert-content"><div class="alert-desc">${addMsg}</div></div>
                    </div>
                `}
            </div>

            <div class="card mb-16">
                <div class="filter-bar">
                    <div class="tab-group">
                        ${[
                            { val: 'all',      label: 'All'      },
                            { val: 'enabled',  label: 'Enabled'  },
                            { val: 'disabled', label: 'Disabled' },
                        ].map(opt => html`
                            <button key=${opt.val}
                                class=${'tab-btn ' + (filterStatus === opt.val ? 'active' : '')}
                                onClick=${() => setFilterStatus(opt.val)}>
                                ${opt.label}
                            </button>
                        `)}
                    </div>
                    <div class="search-input" style="width:160px;">
                        <svg class="search-input-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        <input class="input input-sm" type="text"
                            placeholder="Search..."
                            value=${search}
                            onInput=${e => setSearch(e.target.value)}/>
                    </div>
                    <div class="filter-spacer"></div>
                    <span class="filter-count"><strong>${filtered.length}</strong> coins</span>
                </div>
            </div>

            ${loading
                ? html`
                    <div class="grid-4" style="gap:10px;">
                        ${Array.from({ length: 8 }).map((_, i) => html`
                            <div key=${i} class="skeleton skeleton-card" style="height:110px;border-radius:var(--r-2xl);"></div>
                        `)}
                    </div>
                `
                : !filtered.length
                ? html`
                    <div class="card">
                        <${EmptyState}
                            title="No coins found"
                            desc="Add coins using the form above or adjust your filters."
                        />
                    </div>
                `
                : viewMode === 'grid'
                ? html`
                    <div class="grid-4" style="gap:10px;">
                        ${filtered.map(coin => html`
                            <${CoinTile}
                                key=${coin.coin}
                                coin=${coin}
                                onOpen=${() => setSelectedCoin(coin)}
                                onToggle=${() => toggleCoin(coin)}
                                onDelete=${() => deleteCoin(coin.coin)}
                                toggling=${toggling === coin.coin}
                                deleting=${deleting === coin.coin}
                            />
                        `)}
                    </div>
                `
                : html`
                    <div class="card">
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Coin</th><th>Status</th><th>Grade</th>
                                        <th>Score</th><th>Direction</th><th>Price</th>
                                        <th>24h</th><th>Funding</th><th>Source</th>
                                        <th>Added</th><th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${filtered.map(coin => html`
                                        <tr key=${coin.coin} class="clickable"
                                            onClick=${() => setSelectedCoin(coin)}>
                                            <td>
                                                <div class="td-coin">
                                                    <span class="td-coin-name">${coin.coin}</span>
                                                    <span class="td-coin-suffix">USDT</span>
                                                </div>
                                            </td>
                                            <td>
                                                <span class=${'badge ' + (coin.enabled ? 'badge-online' : 'badge-offline')}>
                                                    ${coin.enabled ? 'ON' : 'OFF'}
                                                </span>
                                            </td>
                                            <td>
                                                ${coin.grade && coin.grade !== '--'
                                                    ? html`<${GradeBadge} grade=${coin.grade}/>`
                                                    : html`<span style="color:var(--label-4);">--</span>`
                                                }
                                            </td>
                                            <td>
                                                ${coin.score
                                                    ? html`<${ScoreBar} score=${coin.score} grade=${coin.grade}/>`
                                                    : html`<span style="color:var(--label-4);">--</span>`
                                                }
                                            </td>
                                            <td>
                                                ${coin.direction && coin.direction !== '--'
                                                    ? html`<${DirBadge} dir=${coin.direction}/>`
                                                    : html`<span style="color:var(--label-4);">--</span>`
                                                }
                                            </td>
                                            <td class="td-price">${Utils.fmtPrice(coin.price)}</td>
                                            <td>
                                                <span class=${'td-change ' + Utils.changeClass(coin.change)}>
                                                    ${Utils.fmtPct(coin.change)}
                                                </span>
                                            </td>
                                            <td>
                                                <span style=${'font-family:var(--font-mono);font-size:var(--text-caption1);color:' + (Math.abs(coin.funding || 0) > 0.05 ? 'var(--loss)' : Math.abs(coin.funding || 0) > 0.03 ? 'var(--warning)' : 'var(--label-3)') + ';'}>
                                                    ${coin.funding != null ? coin.funding.toFixed(4) + '%' : '--'}
                                                </span>
                                            </td>
                                            <td><span class="tag">${coin.source || 'manual'}</span></td>
                                            <td style="color:var(--label-3);font-size:var(--text-caption1);">
                                                ${Utils.fmtTimeAgo(coin.added_at)}
                                            </td>
                                            <td onClick=${e => e.stopPropagation()}>
                                                <div class="flex gap-6">
                                                    <button
                                                        class=${'btn btn-sm ' + (coin.enabled ? 'btn-warning' : 'btn-success')}
                                                        onClick=${() => toggleCoin(coin)}
                                                        disabled=${toggling === coin.coin}>
                                                        ${toggling === coin.coin
                                                            ? html`<${Spinner} size="xs"/>`
                                                            : coin.enabled ? 'Disable' : 'Enable'
                                                        }
                                                    </button>
                                                    <button class="btn btn-danger btn-sm btn-icon"
                                                        onClick=${() => deleteCoin(coin.coin)}
                                                        disabled=${deleting === coin.coin}>
                                                        ${deleting === coin.coin
                                                            ? html`<${Spinner} size="xs"/>`
                                                            : html`<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>`
                                                        }
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    `)}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `
            }

            ${selectedCoin && html`
                <${CoinDetailPanel}
                    coin=${selectedCoin}
                    onClose=${() => setSelectedCoin(null)}
                    onToggle=${() => { toggleCoin(selectedCoin); setSelectedCoin(null) }}
                    onDelete=${() => { deleteCoin(selectedCoin.coin); setSelectedCoin(null) }}
                />
            `}
        </div>
    `
}

function CoinTile({ coin, onOpen, onToggle, onDelete, toggling, deleting }) {
    const grade = coin.grade && coin.grade !== '--' ? coin.grade : null

    return html`
        <div class=${Utils.gradeTileClass(grade) + (coin.enabled ? '' : ' coin-tile-disabled')}
            onClick=${onOpen}
            role="button" tabindex="0"
            onKeyDown=${e => e.key === 'Enter' && onOpen()}>

            <div class="coin-tile-header">
                <div>
                    <div class="coin-tile-name">${coin.coin}</div>
                    <div style="font-size:10px;color:var(--label-4);margin-top:1px;">USDT</div>
                </div>
                <div style="text-align:right;">
                    <div class="coin-tile-price">${Utils.fmtPrice(coin.price)}</div>
                    <div class=${'coin-tile-change ' + Utils.changeClass(coin.change)}>
                        ${Utils.fmtPct(coin.change)}
                    </div>
                </div>
            </div>

            <div class="coin-tile-meta">
                ${grade
                    ? html`<${GradeBadge} grade=${grade}/>`
                    : html`<span class="tag">No signal</span>`
                }
                ${coin.direction && coin.direction !== '--'
                    ? html`<${DirBadge} dir=${coin.direction}/>`
                    : null
                }
                <span class=${'badge ' + (coin.enabled ? 'badge-online' : 'badge-offline')} style="font-size:9px;">
                    ${coin.enabled ? 'ON' : 'OFF'}
                </span>
            </div>

            ${coin.score > 0 && html`
                <${ScoreBar} score=${coin.score} grade=${grade}/>
            `}

            <div class="coin-tile-actions" onClick=${e => e.stopPropagation()}>
                <button class="btn btn-ghost btn-icon-sm"
                    onClick=${onToggle}
                    disabled=${toggling}
                    title=${coin.enabled ? 'Disable' : 'Enable'}>
                    ${toggling
                        ? html`<${Spinner} size="xs"/>`
                        : html`<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>`
                    }
                </button>
                <button class="btn btn-ghost btn-icon-sm icon-btn-danger"
                    onClick=${onDelete}
                    disabled=${deleting}
                    title="Remove coin">
                    ${deleting
                        ? html`<${Spinner} size="xs"/>`
                        : html`<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>`
                    }
                </button>
            </div>
        </div>
    `
}

function CoinDetailPanel({ coin, onClose, onToggle, onDelete }) {
    const [detail,  setDetail]  = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!coin?.coin) return
        setLoading(true)
        API.dashboardCoin(coin.coin).then(d => {
            setDetail(d)
            setLoading(false)
        }).catch(() => setLoading(false))
    }, [coin?.coin])

    const d         = detail || {}
    const grade     = d.grade     || coin.grade     || '--'
    const direction = d.direction || coin.direction || '--'
    const score     = d.score     || coin.score     || 0
    const regime    = d.regime    || '--'
    const session   = d.session   || '--'
    const market    = d.market    || {}
    const sig       = d.signal    || {}
    const factors   = d.factors   || []
    const thesis    = d.thesis    || ''
    const mlProb    = d.ml_probability
    const actualRr  = d.actual_rr || 0

    return html`
        <${Panel}
            show=${true}
            onClose=${onClose}
            title=${coin.coin + 'USDT'}
            subtitle="Coin Detail"
            footer=${html`
                <div class="flex gap-8 w-full">
                    <button class=${'btn btn-full ' + (coin.enabled ? 'btn-warning' : 'btn-success')}
                        onClick=${onToggle}>
                        ${coin.enabled ? 'Disable Coin' : 'Enable Coin'}
                    </button>
                    <button class="btn btn-danger btn-icon" onClick=${onDelete}
                        title="Remove coin">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                    </button>
                </div>
            `}
        >
            <div class="panel-section">
                <div class="flex items-center gap-8 flex-wrap">
                    <${GradeBadge} grade=${grade} size="lg"/>
                    <${DirBadge} dir=${direction}/>
                    <span class=${'badge ' + (coin.enabled ? 'badge-online' : 'badge-offline')}>
                        ${coin.enabled ? 'ENABLED' : 'DISABLED'}
                    </span>
                </div>

                ${score > 0 && html`
                    <div style="display:flex;align-items:center;justify-content:space-between;padding:14px;background:var(--fill-4);border-radius:var(--r-xl);">
                        <div>
                            <div class="label-uppercase mb-4">Confluence Score</div>
                            <div style=${'font-family:var(--font-mono);font-size:var(--text-largetitle);font-weight:var(--weight-black);color:' + Utils.scoreColor(score) + ';letter-spacing:var(--tracking-title1);'}>
                                ${score}<span style="font-size:var(--text-title3);color:var(--label-4);">/100</span>
                            </div>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            ${regime  && regime  !== '--' && html`<${RegimeBadge}  regime=${regime}/>`}
                            ${session && session !== '--' && html`<${SessionBadge} session=${session}/>`}
                        </div>
                    </div>
                `}
            </div>

            ${thesis && html`
                <div class="panel-section">
                    <div class="panel-section-title">Thesis</div>
                    <div style="font-size:var(--text-subhead);color:var(--label-2);line-height:var(--leading-relaxed);font-style:italic;padding:12px 14px;background:var(--fill-4);border-radius:var(--r-lg);border-left:3px solid var(--brand);">
                        "${thesis}"
                    </div>
                </div>
            `}

            ${sig.entry && sig.sl && sig.tp1 && html`
                <div class="panel-section">
                    <div class="panel-section-title">Signal Levels</div>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;">
                        ${[
                            { label: 'Entry',       val: Utils.fmtPrice(sig.entry), color: 'var(--label-1)' },
                            { label: 'Stop Loss',   val: Utils.fmtPrice(sig.sl),    color: 'var(--loss)'    },
                            { label: 'Take Profit', val: Utils.fmtPrice(sig.tp1),   color: 'var(--profit)'  },
                        ].map(l => html`
                            <div key=${l.label} style="background:var(--fill-4);border-radius:var(--r-md);padding:10px 12px;">
                                <div class="label-uppercase mb-4">${l.label}</div>
                                <div style=${'font-family:var(--font-mono);font-size:var(--text-callout);font-weight:var(--weight-heavy);color:' + l.color + ';'}>
                                    ${l.val}
                                </div>
                            </div>
                        `)}
                    </div>
                    <div class="flex justify-between" style="font-size:10px;color:var(--label-3);padding:0 2px;">
                        <span style="font-family:var(--font-mono);">
                            SL ${sig.sl_pct ? sig.sl_pct.toFixed(2) + '%' : '--'}
                        </span>
                        <span style="font-family:var(--font-mono);color:var(--label-2);">R:R 1:${actualRr}</span>
                        ${mlProb != null && html`
                            <span class=${Utils.mlBadgeClass(mlProb)}>ML ${(mlProb * 100).toFixed(0)}%</span>
                        `}
                    </div>
                </div>
            `}

            <div class="panel-section">
                <div class="panel-section-title">Market</div>
                ${loading
                    ? html`<${LoadingSkeleton} rows=${4}/>`
                    : html`
                        ${[
                            { label: 'Price',       val: Utils.fmtPrice(market.price || coin.price) },
                            { label: '24h Change',  val: Utils.fmtPct(market.change || coin.change), color: Utils.changeColor(market.change || coin.change) },
                            { label: 'Funding',     val: (market.funding || coin.funding) != null ? (market.funding || coin.funding).toFixed(4) + '%' : '--', color: Math.abs(market.funding || coin.funding || 0) > 0.05 ? 'var(--loss)' : null },
                            { label: 'Long Ratio',  val: market.long_ratio  != null ? market.long_ratio  + '%' : '--', color: (market.long_ratio  || 0) > 65 ? 'var(--loss)' : null },
                            { label: 'Short Ratio', val: market.short_ratio != null ? market.short_ratio + '%' : '--' },
                            { label: 'OI Change',   val: market.oi_change   != null ? market.oi_change   + '%' : '--' },
                            { label: 'Source',      val: coin.source || 'manual' },
                            { label: 'Added',       val: Utils.fmtTimeAgo(coin.added_at) },
                        ].map(row => html`
                            <${InfoRow} key=${row.label} label=${row.label} value=${row.val}
                                mono=${true} color=${row.color}/>
                        `)}
                    `
                }
            </div>

            ${!loading && factors.length > 0 && html`
                <div class="panel-section">
                    <div class="panel-section-title">Confluence — ${score}/100</div>
                    ${factors.map(f => html`
                        <${ConfluenceBar} key=${f.key} factor=${f}/>
                    `)}
                </div>
            `}
        </${Panel}>
    `
}