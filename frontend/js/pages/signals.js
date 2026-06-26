function signalsPage() {
    return `<div x-data="signalsData()" x-init="init()" @page-change.window="onPageChange($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Signals</div>
                <div
                    class="page-subtitle"
                    aria-live="polite"
                    x-text="filtered.length + ' signals'"
                ></div>
            </div>
            <button
                class="btn btn-ghost btn-sm"
                @click="load(true)"
                :disabled="loading"
                :aria-busy="loading"
                aria-label="Refresh signals"
            >
                <span x-show="loading" class="spinner" aria-hidden="true"></span>
                <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                Refresh
            </button>
        </div>

        <div class="card mb-12">
            <div class="filter-bar" role="search" aria-label="Signal filters">
                <select
                    class="select"
                    style="width:120px;"
                    x-model="filters.grade"
                    @change="load(true)"
                    aria-label="Filter by grade"
                >
                    <option value="">All Grades</option>
                    <option value="A+">A+</option>
                    <option value="A">A</option>
                    <option value="B">B</option>
                    <option value="C">C</option>
                    <option value="F">F</option>
                </select>

                <select
                    class="select"
                    style="width:130px;"
                    x-model="filters.outcome"
                    @change="load(true)"
                    aria-label="Filter by outcome"
                >
                    <option value="">All Outcomes</option>
                    <option value="win">Win</option>
                    <option value="loss">Loss</option>
                    <option value="pending">Pending</option>
                </select>

                <select
                    class="select"
                    style="width:120px;"
                    x-model="filters.direction"
                    @change="applyFilters()"
                    aria-label="Filter by direction"
                >
                    <option value="">All Directions</option>
                    <option value="LONG">Long</option>
                    <option value="SHORT">Short</option>
                </select>

                <input
                    class="input"
                    style="width:110px;"
                    type="text"
                    placeholder="Coin..."
                    x-model="filters.coin"
                    @input.debounce.400ms="load(true)"
                    aria-label="Filter by coin symbol"
                >

                <select
                    class="select"
                    style="width:100px;"
                    x-model="filters.limit"
                    @change="load(true)"
                    aria-label="Number of rows to show"
                >
                    <option value="50">50 rows</option>
                    <option value="100">100 rows</option>
                    <option value="200">200 rows</option>
                    <option value="500">500 rows</option>
                </select>

                <button
                    class="btn btn-ghost btn-sm"
                    @click="clearFilters"
                    aria-label="Clear all filters"
                >Clear</button>

                <div class="flex-1"></div>

                <div
                    style="font-size:11px;color:var(--text-secondary);"
                    aria-live="polite"
                    aria-atomic="true"
                >
                    <span style="font-family:var(--font-mono);color:var(--text-primary);" x-text="filtered.length"></span>
                    of
                    <span style="font-family:var(--font-mono);" x-text="signals.length"></span>
                </div>
            </div>
        </div>

        <div class="card">
            <template x-if="loading">
                <div>
                    <div class="loading-skeleton">
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                    </div>
                </div>
            </template>

            <div x-show="!loading">
                <div
                    class="table-wrap"
                    role="region"
                    aria-label="Signals table"
                    tabindex="0"
                    style="max-height:600px;overflow-y:auto;"
                >
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
                            <template x-if="!paginated.length">
                                <tr>
                                    <td colspan="13" x-html="Utils.emptyState('No signals match filters')"></td>
                                </tr>
                            </template>

                            <template x-for="s in paginated" :key="s.id">
                                <tr
                                    style="cursor:pointer;"
                                    @click="toggleExpand(s.id)"
                                    :style="expanded === s.id ? 'background:var(--bg-tertiary)' : ''"
                                    :aria-expanded="String(expanded === s.id)"
                                    role="button"
                                    tabindex="0"
                                    @keydown.enter="toggleExpand(s.id)"
                                    @keydown.space.prevent="toggleExpand(s.id)"
                                    :aria-label="'Signal ' + s.id + ' ' + s.coin + ' ' + s.direction + ' — click to expand'"
                                >
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;"
                                            x-text="s.id"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-size:11px;color:var(--text-secondary);"
                                            x-text="Utils.fmtTimeAgo(s.timestamp)"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);font-weight:700;"
                                            x-text="s.coin"
                                        ></span>
                                    </td>
                                    <td>
                                        <span :class="Utils.dirBadgeClass(s.direction)" x-text="s.direction"></span>
                                    </td>
                                    <td>
                                        <span :class="Utils.gradeBadgeClass(s.grade)" x-text="s.grade"></span>
                                    </td>
                                    <td x-html="Utils.scoreBar(s.score)"></td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);"
                                            x-text="Utils.fmtPrice(s.entry)"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);color:var(--red);"
                                            x-text="Utils.fmtPrice(s.sl)"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);color:var(--green);"
                                            x-text="Utils.fmtPrice(s.tp1)"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);"
                                            x-text="Utils.fmtPrice(s.exit_price)"
                                        ></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);font-weight:700;"
                                            :style="{color: Utils.pnlColor(s.pnl)}"
                                            x-text="s.pnl != null ? Utils.fmtPnl(s.pnl) : '--'"
                                        ></span>
                                    </td>
                                    <td>
                                        <span :class="Utils.outcomeBadgeClass(s.outcome)" x-text="s.outcome"></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-size:11px;color:var(--text-muted);"
                                            x-text="s.regime || '--'"
                                        ></span>
                                    </td>
                                </tr>

                                <template x-if="expanded === s.id">
                                    <tr>
                                        <td
                                            colspan="13"
                                            style="padding:0;background:var(--bg-tertiary);"
                                        >
                                            <div
                                                style="padding:16px;"
                                                role="region"
                                                :aria-label="'Details for signal ' + s.id"
                                            >
                                                <div class="grid-4" style="gap:8px;">
                                                    <div class="level-item">
                                                        <div class="level-label">Signal ID</div>
                                                        <div
                                                            style="font-family:var(--font-mono);font-size:13px;"
                                                            x-text="s.id"
                                                        ></div>
                                                    </div>
                                                    <div class="level-item">
                                                        <div class="level-label">Risk Amount</div>
                                                        <div
                                                            style="font-family:var(--font-mono);font-size:13px;"
                                                            x-text="s.risk_amt ? '$' + parseFloat(s.risk_amt).toFixed(2) : '--'"
                                                        ></div>
                                                    </div>
                                                    <div class="level-item">
                                                        <div class="level-label">Market Score</div>
                                                        <div
                                                            style="font-family:var(--font-mono);font-size:13px;"
                                                            x-text="s.market_score != null ? s.market_score + '/100' : '--'"
                                                        ></div>
                                                    </div>
                                                    <div class="level-item">
                                                        <div class="level-label">Entry Score</div>
                                                        <div
                                                            style="font-family:var(--font-mono);font-size:13px;"
                                                            x-text="s.entry_score != null ? s.entry_score + '/100' : '--'"
                                                        ></div>
                                                    </div>
                                                    <div class="level-item">
                                                        <div class="level-label">BTC Score</div>
                                                        <div
                                                            style="font-family:var(--font-mono);font-size:13px;"
                                                            x-text="s.btc_score != null ? s.btc_score + '/8' : '--'"
                                                        ></div>
                                                    </div>
                                                    <div class="level-item">
                                                        <div class="level-label">Session</div>
                                                        <div
                                                            style="font-size:12px;"
                                                            x-text="s.session || '--'"
                                                        ></div>
                                                    </div>
                                                    <div class="level-item">
                                                        <div class="level-label">Signal Type</div>
                                                        <div
                                                            style="font-family:var(--font-mono);font-size:12px;"
                                                            x-text="s.signal_type || '--'"
                                                        ></div>
                                                    </div>
                                                    <div class="level-item">
                                                        <div class="level-label">Timestamp</div>
                                                        <div
                                                            style="font-size:11px;color:var(--text-secondary);"
                                                            x-text="Utils.fmtTime(s.timestamp)"
                                                        ></div>
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                </template>
                            </template>
                        </tbody>
                    </table>
                </div>

                <div class="pagination" role="navigation" aria-label="Signal pagination">
                    <span
                        class="pagination-info"
                        aria-live="polite"
                        x-text="'Page ' + currentPage + ' of ' + totalPages + ' · ' + filtered.length + ' signals'"
                    ></span>
                    <div class="pagination-controls">
                        <button
                            class="btn btn-ghost btn-sm"
                            @click="currentPage = 1"
                            :disabled="currentPage <= 1"
                            aria-label="First page"
                        >First</button>
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
                        <button
                            class="btn btn-ghost btn-sm"
                            @click="currentPage = totalPages"
                            :disabled="currentPage >= totalPages"
                            aria-label="Last page"
                        >Last</button>
                    </div>
                </div>
            </div>
        </div>

    </div>`
}

function signalsData() {
    return {
        signals:     [],
        filtered:    [],
        loading:     false,
        expanded:    null,
        currentPage: 1,
        pageSize:    30,

        filters: {
            grade:     '',
            outcome:   '',
            direction: '',
            coin:      '',
            limit:     '100',
        },

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
                if (e.detail.page === 'signals') this.load()
            })
        },

        onPageChange(detail) {
            if (detail.page === 'signals') this.load()
        },

        async load(reset = false) {
            if (reset) {
                this.currentPage = 1
                this.expanded    = null
            }

            this.loading = true

            try {
                const q = new URLSearchParams()
                q.set('limit', parseInt(this.filters.limit) || 100)
                if (this.filters.grade)   q.set('grade',   this.filters.grade)
                if (this.filters.coin)    q.set('coin',    this.filters.coin.toUpperCase().trim())
                if (this.filters.outcome) q.set('outcome', this.filters.outcome)

                const res = await fetch('/api/signals?' + q.toString(), {
                    credentials: 'include'
                })

                if (res.status === 401) {
                    window.location.href = '/login.html'
                    return
                }

                if (!res.ok) throw new Error('Failed to load signals')

                this.signals = await res.json() || []
                this.applyFilters()

            } catch (e) {
                window._app?.showToast('Failed to load signals: ' + e.message, 'error')
            } finally {
                this.loading = false
            }
        },

        applyFilters() {
            let result = [...this.signals]

            if (this.filters.direction) {
                result = result.filter(s => s.direction === this.filters.direction)
            }

            this.filtered    = result
            this.currentPage = 1
        },

        toggleExpand(id) {
            this.expanded = this.expanded === id ? null : id
        },

        clearFilters() {
            this.filters = {
                grade:     '',
                outcome:   '',
                direction: '',
                coin:      '',
                limit:     '100',
            }
            this.load(true)
        },
    }
}