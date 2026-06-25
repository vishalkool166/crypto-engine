function auditPage() {
    return `<div x-data="auditData()" x-init="init()">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Audit Log</div>
                <div class="page-subtitle" x-text="logs.length + ' entries loaded'"></div>
            </div>
            <div class="flex gap-8">
                <select class="select" style="width:110px;" x-model="limit" @change="load()">
                    <option value="50">50 rows</option>
                    <option value="100">100 rows</option>
                    <option value="200">200 rows</option>
                    <option value="500">500 rows</option>
                </select>
                <button class="btn btn-ghost btn-sm" @click="load" :disabled="loading">
                    <span x-show="loading" class="spinner"></span>
                    <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    Refresh
                </button>
            </div>
        </div>

        <div class="card mb-12">
            <div class="filter-bar">
                <select class="select" style="width:160px;" x-model="filterAction" @change="applyFilter()">
                    <option value="">All Actions</option>
                    <option value="dashboard_login">Login</option>
                    <option value="mode_toggle">Mode Toggle</option>
                    <option value="coin_add">Coin Add</option>
                    <option value="coin_toggle">Coin Toggle</option>
                    <option value="coin_delete">Coin Delete</option>
                    <option value="password_reset">Password Reset</option>
                </select>

                <select class="select" style="width:130px;" x-model="filterSuccess" @change="applyFilter()">
                    <option value="">All Results</option>
                    <option value="true">Success</option>
                    <option value="false">Failed</option>
                </select>

                <input
                    class="input"
                    style="width:160px;"
                    type="text"
                    placeholder="Search detail..."
                    x-model="search"
                    @input.debounce.300ms="applyFilter()"
                >

                <button class="btn btn-ghost btn-sm" @click="clearFilters">Clear</button>

                <div class="flex-1"></div>

                <span style="font-size:11px;color:var(--text-secondary);">
                    <span class="mono" style="color:var(--text-primary)" x-text="filtered.length"></span> entries
                </span>
            </div>
        </div>

        <div class="card">
            <div x-show="loading" x-html="Utils.loadingState()"></div>

            <div x-show="!loading" class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Time</th>
                            <th>Action</th>
                            <th>Source</th>
                            <th>Detail</th>
                            <th>IP</th>
                            <th>Result</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template x-if="!filtered.length">
                            <tr>
                                <td colspan="7" x-html="Utils.emptyState('No audit entries found')"></td>
                            </tr>
                        </template>
                        <template x-for="log in paginated" :key="log.id">
                            <tr>
                                <td>
                                    <span
                                        class="mono"
                                        style="font-size:11px;color:var(--text-muted);"
                                        x-text="log.id"
                                    ></span>
                                </td>
                                <td>
                                    <div style="font-size:11px;">
                                        <div style="color:var(--text-primary);" x-text="Utils.fmtTimeAgo(log.timestamp)"></div>
                                        <div style="color:var(--text-muted);font-size:10px;" x-text="Utils.fmtTime(log.timestamp)"></div>
                                    </div>
                                </td>
                                <td>
                                    <span
                                        class="mono"
                                        style="font-size:12px;font-weight:600;"
                                        :style="{color: actionColor(log.action)}"
                                        x-text="log.action"
                                    ></span>
                                </td>
                                <td>
                                    <span class="tag" x-text="log.source || '--'"></span>
                                </td>
                                <td>
                                    <span
                                        style="font-size:12px;color:var(--text-secondary);"
                                        x-text="log.detail || '--'"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        class="mono"
                                        style="font-size:11px;color:var(--text-muted);"
                                        x-text="log.ip || '--'"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        class="badge"
                                        :class="log.success ? 'badge-win' : 'badge-loss'"
                                        x-text="log.success ? '✓ OK' : '✗ FAIL'"
                                    ></span>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>

            <div class="flex justify-between items-center mt-12" style="font-size:12px;color:var(--text-secondary);">
                <span x-text="'Page ' + currentPage + ' of ' + totalPages"></span>
                <div class="flex gap-8">
                    <button
                        class="btn btn-ghost btn-sm"
                        @click="currentPage--"
                        :disabled="currentPage <= 1"
                    >Prev</button>
                    <button
                        class="btn btn-ghost btn-sm"
                        @click="currentPage++"
                        :disabled="currentPage >= totalPages"
                    >Next</button>
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
        pageSize:      25,

        get totalPages() {
            return Math.max(1, Math.ceil(this.filtered.length / this.pageSize))
        },

        get paginated() {
            const start = (this.currentPage - 1) * this.pageSize
            return this.filtered.slice(start, start + this.pageSize)
        },

        async init() {
            await this.load()
            window.addEventListener('page-change', e => {
                if (e.detail.page === 'audit') this.load()
            })
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
            if (action.includes('login'))    return 'var(--blue)'
            if (action.includes('toggle'))   return 'var(--orange)'
            if (action.includes('delete'))   return 'var(--red)'
            if (action.includes('add'))      return 'var(--green)'
            if (action.includes('reset'))    return 'var(--orange)'
            if (action.includes('mode'))     return 'var(--purple)'
            return 'var(--text-secondary)'
        },
    }
}