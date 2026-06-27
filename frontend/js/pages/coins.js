var { h, Fragment } = preact
var { useState, useEffect, useRef } = preactHooks
var html = window.html
var { showToast, requireTotp } = Store
var { GradeBadge, DirBadge, ScoreBar, Spinner, EmptyState, LoadingSkeleton } = Components


function CoinsPage() {
    const [coins,        setCoins]        = useState([])
    const [filtered,     setFiltered]     = useState([])
    const [loading,      setLoading]      = useState(false)
    const [adding,       setAdding]       = useState(false)
    const [validating,   setValidating]   = useState(false)
    const [toggling,     setToggling]     = useState(null)
    const [deleting,     setDeleting]     = useState(null)
    const [newCoin,      setNewCoin]      = useState('')
    const [addMsg,       setAddMsg]       = useState('')
    const [addOk,        setAddOk]        = useState(false)
    const [filterStatus, setFilterStatus] = useState('')
    const [search,       setSearch]       = useState('')

    const total   = coins.length
    const enabled = coins.filter(c => c.enabled).length

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.coins()
            setCoins(data || [])
            applyFilter(data || [], filterStatus, search)
        } catch(e) {
            showToast('Failed to load coins: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    function applyFilter(c, status, s) {
        let result = [...(c || coins)]
        if (status === 'enabled')  result = result.filter(x => x.enabled)
        if (status === 'disabled') result = result.filter(x => !x.enabled)
        if (s) result = result.filter(x => x.coin.includes(s.toUpperCase()))
        setFiltered(result)
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
            const updated = coins.map(c => c.coin === coin.coin ? { ...c, enabled: !c.enabled } : c)
            setCoins(updated)
            applyFilter(updated, filterStatus, search)
            showToast(coin.coin + (!coin.enabled ? ' enabled' : ' disabled'), 'success')
        } catch(e) {
            showToast('Failed to toggle ' + coin.coin + ': ' + e.message, 'error')
        } finally {
            setToggling(null)
        }
    }

    async function deleteCoin(coinName) {
        const code = await requireTotp('Delete ' + coinName, 'Enter your TOTP code to permanently remove ' + coinName)
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
                const updated = coins.filter(c => c.coin !== coinName)
                setCoins(updated)
                applyFilter(updated, filterStatus, search)
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
                    <div class="page-title">Coin Universe</div>
                    <div class="page-subtitle">${enabled} enabled · ${total} total</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${load} disabled=${loading}>
                    ${loading ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="23 4 23 10 17 10"/>
                            <polyline points="1 20 1 14 7 14"/>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                    `}
                    Refresh
                </button>
            </div>

            <div class="card mb-16">
                <div class="section-title mb-12">Add Coin</div>
                <div class="flex gap-8" style="flex-wrap:wrap;">
                    <input class="input" style="max-width:180px;" type="text"
                        placeholder="BTC, ETH, SOL..."
                        value=${newCoin}
                        onInput=${e => setNewCoin(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                        onKeyDown=${e => e.key === 'Enter' && addCoin()}
                        disabled=${adding}/>
                    <button class="btn btn-primary" onClick=${addCoin}
                        disabled=${adding || !newCoin || newCoin.length < 2}>
                        ${adding ? html`<${Spinner}/>` : html`
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="12" y1="5" x2="12" y2="19"/>
                                <line x1="5" y1="12" x2="19" y2="12"/>
                            </svg>
                        `}
                        Add Coin
                    </button>
                </div>
                ${validating && html`
                    <div style="font-size:12px;color:var(--text-secondary);margin-top:8px;display:flex;align-items:center;gap:6px;">
                        <${Spinner}/> Validating on Binance Futures...
                    </div>
                `}
                ${addMsg && html`<div class=${'alert mt-12 ' + (addOk ? 'alert-success' : 'alert-error')}>${addMsg}</div>`}
            </div>

            <div class="card">
                <div class="filter-bar mb-12">
                    <select class="select" style="width:130px;" value=${filterStatus}
                        onChange=${e => { setFilterStatus(e.target.value); applyFilter(coins, e.target.value, search) }}>
                        <option value="">All Coins</option>
                        <option value="enabled">Enabled Only</option>
                        <option value="disabled">Disabled Only</option>
                    </select>
                    <input class="input" style="width:130px;" type="text"
                        placeholder="Search coin..."
                        value=${search}
                        onInput=${e => { setSearch(e.target.value); applyFilter(coins, filterStatus, e.target.value) }}/>
                    <div class="flex-1"></div>
                    <span style="font-size:12px;color:var(--text-secondary);">
                        <span style="font-family:var(--font-mono);color:var(--text-primary);">${filtered.length}</span> coins
                    </span>
                </div>

                ${loading
                    ? html`<${LoadingSkeleton} rows=${4}/>`
                    : html`
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Coin</th><th>Status</th><th>Grade</th><th>Score</th>
                                        <th>Direction</th><th>Price</th><th>24h</th><th>Funding</th>
                                        <th>Source</th><th>Added</th><th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!filtered.length
                                        ? html`<tr><td colspan="11"><${EmptyState} message="No coins found"/></td></tr>`
                                        : filtered.map(coin => html`
                                            <tr key=${coin.coin}>
                                                <td>
                                                    <div class="flex items-center gap-6">
                                                        <span style="font-family:var(--font-mono);font-weight:800;font-size:13px;">${coin.coin}</span>
                                                        <span style="font-size:10px;color:var(--text-muted);">USDT</span>
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
                                                        : html`<span style="color:var(--text-muted);">--</span>`
                                                    }
                                                </td>
                                                <td>
                                                    ${coin.score
                                                        ? html`<${ScoreBar} score=${coin.score}/>`
                                                        : html`<span style="color:var(--text-muted);">--</span>`
                                                    }
                                                </td>
                                                <td>
                                                    ${coin.direction && coin.direction !== '--'
                                                        ? html`<${DirBadge} dir=${coin.direction}/>`
                                                        : html`<span style="color:var(--text-muted);">--</span>`
                                                    }
                                                </td>
                                                <td><span style="font-family:var(--font-mono);">${Utils.fmtPrice(coin.price)}</span></td>
                                                <td><span style="font-family:var(--font-mono);color:${Utils.changeColor(coin.change)};">${Utils.fmtPct(coin.change)}</span></td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);font-size:11px;color:${Math.abs(coin.funding || 0) > 0.05 ? 'var(--red)' : Math.abs(coin.funding || 0) > 0.03 ? 'var(--orange)' : 'var(--text-secondary)'};">
                                                        ${coin.funding != null ? coin.funding.toFixed(4) + '%' : '--'}
                                                    </span>
                                                </td>
                                                <td><span class="tag">${coin.source || 'manual'}</span></td>
                                                <td><span style="font-size:11px;color:var(--text-secondary);">${Utils.fmtTimeAgo(coin.added_at)}</span></td>
                                                <td>
                                                    <div class="flex gap-6">
                                                        <button class=${'btn btn-sm ' + (coin.enabled ? 'btn-warning' : 'btn-success')}
                                                            onClick=${() => toggleCoin(coin)}
                                                            disabled=${toggling === coin.coin}>
                                                            ${toggling === coin.coin ? html`<${Spinner}/>` : (coin.enabled ? 'Disable' : 'Enable')}
                                                        </button>
                                                        <button class="btn btn-danger btn-sm btn-icon"
                                                            onClick=${() => deleteCoin(coin.coin)}
                                                            disabled=${deleting === coin.coin}>
                                                            ${deleting === coin.coin ? html`<${Spinner}/>` : html`
                                                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                                    <polyline points="3 6 5 6 21 6"/>
                                                                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                                                                    <path d="M10 11v6M14 11v6"/>
                                                                </svg>
                                                            `}
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                    `
                }
            </div>
        </div>
    `
}