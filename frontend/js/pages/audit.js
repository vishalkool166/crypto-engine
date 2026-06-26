function auditPage() {
    return `<div x-data="auditData()" x-init="init()" @page-change.window="onPageChange($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Audit Log</div>
                <div
                    class="page-subtitle"
                    aria-live="polite"
                    x-text="filtered.length + ' entries'"
                ></div>
            </div>
            <div class="flex gap-8">
                <select
                    class="select"
                    style="width:100px;"
                    x-model="limit"
                    @change="load()"
                    aria-label="Number of audit entries to load"
                >
                    <option value="50">50 rows</option>
                    <option value="100">100 rows</option>
                    <option value="200">200 rows</option>
                    <option value="500">500 rows</option>
                </select>
                <button
                    class="btn btn-ghost btn-sm"
                    @click="load"
                    :disabled="loading"
                    :aria-busy="loading"
                    aria-label="Refresh audit log"
                >
                    <span x-show="loading" class="spinner" aria-hidden="true"></span>
                    <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    Refresh
                </button>
            </div>
        </div>

        <div class="card mb-12">
            <div
                class="filter-bar"
                role="search"
                aria-label="Audit log filters"
            >
                <select
                    class="select"
                    style="width:150px;"
                    x-model="filterAction"
                    @change="applyFilter()"
                    aria-label="Filter by action type"
                >
                    <option value="">All Actions</option>
                    <option value="dashboard_login">Login</option>
                    <option value="mode_toggle">Mode Toggle</option>
                    <option value="coin_add">Coin Add</option>
                    <option value="coin_toggle">Coin Toggle</option>
                    <option value="coin_delete">Coin Delete</option>
                    <option value="password_reset">Password Reset</option>
                    <option value="docker_purge">Docker Purge</option>
                </select>

                <select
                    class="select"
                    style="width:120px;"
                    x-model="filterSuccess"
                    @change="applyFilter()"
                    aria-label="Filter by result"
                >
                    <option value="">All Results</option>
                    <option value="true">Success</option>
                    <option value="false">Failed</option>
                </select>

                <input
                    class="input"
                    style="width:150px;"
                    type="text"
                    placeholder="Search detail..."
                    x-model="search"
                    @input.debounce.300ms="applyFilter()"
                    aria-label="Search audit log entries"
                >

                <button
                    class="btn btn-ghost btn-sm"
                    @click="clearFilters"
                    aria-label="Clear all filters"
                >Clear</button>

                <div class="flex-1"></div>

                <span
                    style="font-size:11px;color:var(--text-secondary);"
                    aria-live="polite"
                >
                    <span
                        style="font-family:var(--font-mono);color:var(--text-primary);"
                        x-text="filtered.length"
                    ></span>
                    entries
                </span>
            </div>
        </div>

        <div class="card">
            <template x-if="loading">
                <div class="loading-skeleton">
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                </div>
            </template>

            <div x-show="!loading">
                <div
                    class="table-wrap"
                    role="region"
                    aria-label="Audit log entries"
                    tabindex="0"
                    style="max-height:600px;overflow-y:auto;"
                >
                    <table aria-label="Audit log">
                        <thead>
                            <tr>
                                <th scope="col">#</th>
                                <th scope="col">Time</th>
                                <th scope="col">Action</th>
                                <th scope="col">Source</th>
                                <th scope="col">Detail</th>
                                <th scope="col">IP</th>
                                <th scope="col">Result</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template x-if="!paginated.length">
                                <tr>
                                    <td colspan="7" x-html="Utils.emptyState('No audit entries found')"></td>
                                </tr>
                            </template>
                            <template x-for="log in paginated" :key="log.id">
                                <tr>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);"
                                            x-text="log.id"
                                        ></span>
                                    </td>
                                    <td>
                                        <div>
                                            <div
                                                style="font-size:11px;color:var(--text-primary);"
                                                x-text="Utils.fmtTimeAgo(log.timestamp)"
                                            ></div>
                                            <div
                                                style="font-size:10px;color:var(--text-muted);"
                                                x-text="Utils.fmtTime(log.timestamp)"
                                            ></div>
                                        </div>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);font-size:11px;font-weight:700;"
                                            :style="{color: actionColor(log.action)}"
                                            x-text="log.action"
                                        ></span>
                                    </td>
                                    <td>
                                        <span class="tag" x-text="log.source || '--'"></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-size:11px;color:var(--text-secondary);"
                                            x-text="log.detail || '--'"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);"
                                            x-text="log.ip || '--'"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            class="badge"
                                            :class="log.success ? 'badge-win' : 'badge-loss'"
                                            :aria-label="log.success ? 'Success' : 'Failed'"
                                            x-text="log.success ? '✓ OK' : '✗ FAIL'"
                                        ></span>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>

                <div
                    class="pagination"
                    role="navigation"
                    aria-label="Audit log pagination"
                >
                    <span
                        class="pagination-info"
                        aria-live="polite"
                        x-text="'Page ' + currentPage + ' of ' + totalPages"
                    ></span>
                    <div class="pagination-controls">
                        <button
                            class="btn btn-ghost btn-sm"
                            @click="currentPage--"
                            :disabled="currentPage <= 1"
                            aria-label="Previous page"
                        >Prev</button>
                        <span
                            style="padding:4px 10px;font-family:var(--font-mono);font-size:12px;color:var(--text-secondary);"
                            x-text="currentPage + ' / ' + totalPages"
                        ></span>
                        <button
                            class="btn btn-ghost btn-sm"
                            @click="currentPage++"
                            :disabled="currentPage >= totalPages"
                            aria-label="Next page"
                        >Next</button>
                    </div>
                </div>
            </div>
        </div>

    </div>`
}

function auditData() {
    return {
        logs:          [],
        filtered:      [],
        loading:       false,
        limit:         '100',
        filterAction:  '',
        filterSuccess: '',
        search:        '',
        currentPage:   1,
        pageSize:      30,

        get totalPages() {
            return Math.max(1, Math.ceil(this.filtered.length / this.pageSize))
        },

        get paginated() {
            const start = (this.currentPage - 1) * this.pageSize
            return this.filtered.slice(start, start + this.pageSize)
        },

        async init() {
            await this.load()
        },

        onPageChange(detail) {
            if (detail.page === 'audit') this.load()
        },

        async load() {
            this.loading = true
            try {
                this.logs = await API.auditLog(parseInt(this.limit) || 100) || []
                this.applyFilter()
            } catch (e) {
                window._app?.showToast('Failed to load audit log: ' + e.message, 'error')
            } finally {
                this.loading = false
            }
        },

        applyFilter() {
            let result = [...this.logs]

            if (this.filterAction) {
                result = result.filter(l => l.action === this.filterAction)
            }

            if (this.filterSuccess !== '') {
                const success = this.filterSuccess === 'true'
                result        = result.filter(l => l.success === success)
            }

            if (this.search) {
                const s = this.search.toLowerCase()
                result  = result.filter(l =>
                    (l.detail  || '').toLowerCase().includes(s) ||
                    (l.action  || '').toLowerCase().includes(s) ||
                    (l.source  || '').toLowerCase().includes(s) ||
                    (l.ip      || '').toLowerCase().includes(s)
                )
            }

            this.filtered    = result
            this.currentPage = 1
        },

        clearFilters() {
            this.filterAction  = ''
            this.filterSuccess = ''
            this.search        = ''
            this.applyFilter()
        },

        actionColor(action) {
            if (!action) return 'var(--text-muted)'
            if (action.includes('login'))  return 'var(--blue)'
            if (action.includes('toggle')) return 'var(--orange)'
            if (action.includes('delete')) return 'var(--red)'
            if (action.includes('add'))    return 'var(--green)'
            if (action.includes('reset'))  return 'var(--orange)'
            if (action.includes('mode'))   return 'var(--purple)'
            if (action.includes('docker')) return 'var(--red)'
            return 'var(--text-secondary)'
        },
    }
}