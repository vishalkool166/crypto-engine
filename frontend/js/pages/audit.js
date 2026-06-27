const { h } = preact
const { useState, useEffect } = preactHooks
const html = htm.bind(h)
const { showToast } = Store
const { Spinner, EmptyState, LoadingSkeleton } = Components

function AuditPage() {
    const [logs,          setLogs]          = useState([])
    const [filtered,      setFiltered]      = useState([])
    const [loading,       setLoading]       = useState(false)
    const [limit,         setLimit]         = useState('100')
    const [filterAction,  setFilterAction]  = useState('')
    const [filterSuccess, setFilterSuccess] = useState('')
    const [search,        setSearch]        = useState('')
    const [currentPage,   setCurrentPage]   = useState(1)

    const pageSize   = 30
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
    const paginated  = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)

    useEffect(() => { load() }, [])

    async function load() {
        setLoading(true)
        try {
            const data = await API.auditLog(parseInt(limit) || 100)
            setLogs(data || [])
            applyFilter(data || [], filterAction, filterSuccess, search)
        } catch(e) {
            showToast('Failed to load audit log: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    function applyFilter(l, action, success, s) {
        let result = [...(l || logs)]
        if (action)    result = result.filter(x => x.action === action)
        if (success !== '') {
            const ok = success === 'true'
            result   = result.filter(x => x.success === ok)
        }
        if (s) {
            const q = s.toLowerCase()
            result  = result.filter(x =>
                (x.detail || '').toLowerCase().includes(q) ||
                (x.action || '').toLowerCase().includes(q) ||
                (x.source || '').toLowerCase().includes(q) ||
                (x.ip     || '').toLowerCase().includes(q)
            )
        }
        setFiltered(result)
        setCurrentPage(1)
    }

    function actionColor(action) {
        if (!action) return 'var(--text-muted)'
        if (action.includes('login'))  return 'var(--blue)'
        if (action.includes('toggle')) return 'var(--orange)'
        if (action.includes('delete')) return 'var(--red)'
        if (action.includes('add'))    return 'var(--green)'
        if (action.includes('reset'))  return 'var(--orange)'
        if (action.includes('mode'))   return 'var(--purple)'
        if (action.includes('docker')) return 'var(--red)'
        return 'var(--text-secondary)'
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Audit Log</div>
                    <div class="page-subtitle">${filtered.length} entries</div>
                </div>
                <div class="flex gap-8">
                    <select class="select" style="width:100px;" value=${limit}
                        onChange=${e => { setLimit(e.target.value); load() }}>
                        <option value="50">50 rows</option>
                        <option value="100">100 rows</option>
                        <option value="200">200 rows</option>
                        <option value="500">500 rows</option>
                    </select>
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
            </div>

            <div class="card mb-16">
                <div class="filter-bar">
                    <select class="select" style="width:160px;" value=${filterAction}
                        onChange=${e => { setFilterAction(e.target.value); applyFilter(logs, e.target.value, filterSuccess, search) }}>
                        <option value="">All Actions</option>
                        <option value="dashboard_login">Login</option>
                        <option value="mode_toggle">Mode Toggle</option>
                        <option value="coin_add">Coin Add</option>
                        <option value="coin_toggle">Coin Toggle</option>
                        <option value="coin_delete">Coin Delete</option>
                        <option value="password_reset">Password Reset</option>
                        <option value="docker_purge">Docker Purge</option>
                    </select>
                    <select class="select" style="width:120px;" value=${filterSuccess}
                        onChange=${e => { setFilterSuccess(e.target.value); applyFilter(logs, filterAction, e.target.value, search) }}>
                        <option value="">All Results</option>
                        <option value="true">Success</option>
                        <option value="false">Failed</option>
                    </select>
                    <input class="input" style="width:160px;" type="text"
                        placeholder="Search..."
                        value=${search}
                        onInput=${e => { setSearch(e.target.value); applyFilter(logs, filterAction, filterSuccess, e.target.value) }}/>
                    <button class="btn btn-ghost btn-sm" onClick=${() => {
                        setFilterAction('')
                        setFilterSuccess('')
                        setSearch('')
                        applyFilter(logs, '', '', '')
                    }}>Clear</button>
                    <div class="flex-1"></div>
                    <span style="font-size:12px;color:var(--text-secondary);">
                        <span style="font-family:var(--font-mono);color:var(--text-primary);">${filtered.length}</span> entries
                    </span>
                </div>
            </div>

            <div class="card">
                ${loading
                    ? html`<${LoadingSkeleton} rows=${5}/>`
                    : html`
                        <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>#</th><th>Time</th><th>Action</th>
                                        <th>Source</th><th>Detail</th><th>IP</th><th>Result</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${!paginated.length
                                        ? html`<tr><td colspan="7"><${EmptyState} message="No audit entries found"/></td></tr>`
                                        : paginated.map(log => html`
                                            <tr key=${log.id}>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${log.id}</span></td>
                                                <td>
                                                    <div style="font-size:12px;">${Utils.fmtTimeAgo(log.timestamp)}</div>
                                                    <div style="font-size:10px;color:var(--text-muted);">${Utils.fmtTime(log.timestamp)}</div>
                                                </td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);font-size:11px;font-weight:700;color:${actionColor(log.action)};">
                                                        ${log.action}
                                                    </span>
                                                </td>
                                                <td><span class="tag">${log.source || '--'}</span></td>
                                                <td><span style="font-size:11px;color:var(--text-secondary);">${log.detail || '--'}</span></td>
                                                <td><span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${log.ip || '--'}</span></td>
                                                <td>
                                                    <span class=${'badge ' + (log.success ? 'badge-win' : 'badge-loss')}>
                                                        ${log.success ? '✓ OK' : '✗ FAIL'}
                                                    </span>
                                                </td>
                                            </tr>
                                        `)
                                    }
                                </tbody>
                            </table>
                        </div>
                        <div class="pagination">
                            <span class="pagination-info">Page ${currentPage} of ${totalPages}</span>
                            <div class="pagination-controls">
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(p => p - 1)} disabled=${currentPage <= 1}>Prev</button>
                                <span style="padding:4px 10px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);">${currentPage} / ${totalPages}</span>
                                <button class="btn btn-ghost btn-sm" onClick=${() => setCurrentPage(p => p + 1)} disabled=${currentPage >= totalPages}>Next</button>
                            </div>
                        </div>
                    `
                }
            </div>
        </div>
    `
}