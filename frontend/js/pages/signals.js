function signalsPage() {
    return `<div x-data="signalsData()" x-init="init()">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Signals</div>
                <div class="page-subtitle" x-text="total + ' signals loaded'"></div>
            </div>
            <button class="btn btn-ghost btn-sm" @click="load(true)" :disabled="loading">
                <span x-show="loading" class="spinner"></span>
                <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                Refresh
            </button>
        </div>

        <div class="card mb-12">
            <div class="filter-bar">
                <select class="select" style="width:130px;" x-model="filters.grade" @change="load(true)">
                    <option value="">All Grades</option>
                    <option value="A+">A+</option>
                    <option value="A">A</option>
                    <option value="B">B</option>
                    <option value="C">C</option>
                    <option value="F">F</option>
                </select>

                <select class="select" style="width:140px;" x-model="filters.outcome" @change="load(true)">
                    <option value="">All Outcomes</option>
                    <option value="win">Win</option>
                    <option value="loss">Loss</option>
                    <option value="pending">Pending</option>
                </select>

                <select class="select" style="width:130px;" x-model="filters.direction" @change="applyFilters()">
                    <option value="">All Directions</option>
                    <option value="LONG">Long</option>
                    <option value="SHORT">Short</option>
                </select>

                <input
                    class="input"
                    style="width:120px;"
                    type="text"
                    placeholder="Coin (BTC)"
                    x-model="filters.coin"
                    @input.debounce.400ms="load(true)"
                >

                <select class="select" style="width:110px;" x-model="filters.limit" @change="load(true)">
                    <option value="50">50 rows</option>
                    <option value="100">100 rows</option>
                    <option value="200">200 rows</option>
                    <option value="500">500 rows</option>
                </select>

                <button class="btn btn-ghost btn-sm" @click="clearFilters">Clear</button>

                <div class="flex-1"></div>

                <div style="font-size:11px;color:var(--text-secondary);">
                    Showing <span class="mono" style="color:var(--text-primary)" x-text="filtered.length"></span> of <span class="mono" x-text="signals.length"></span>
                </div>
            </div>
        </div>

        <div class="card">
            <div x-show="loading" x-html="Utils.loadingState()"></div>

            <div x-show="!loading">
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Time</th>
                                <th>Coin</th>
                                <th>Dir</th>
                                <th>Grade</th>
                                <th>Score</th>
                                <th>Entry</th>
                                <th>SL</th>
                                <th>TP</th>
                                <th>Exit</th>
                                <th>PnL</th>
                                <th>Outcome</th>
                                <th>Regime</th>
                                <th>Session</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template x-if="!filtered.length">
                                <tr>
                                    <td colspan="14" x-html="Utils.emptyState('No signals match filters')"></td>
                                </tr>
                            </template>
                            <template x-for="s in paginated" :key="s.id">
                                <tr
                                    style="cursor:pointer;"
                                    @click="toggleExpand(s.id)"
                                    :style="expanded === s.id ? 'background:var(--bg-tertiary)' : ''"
                                >
                                    <td><span class="mono" style="color:var(--text-muted);font-size:11px;" x-text="s.id"></span></td>
                                    <td><span style="font-size:11px;color:var(--text-secondary);" x-text="Utils.fmtTimeAgo(s.timestamp)"></span></td>
                                    <td><span class="mono" style="font-weight:700;" x-text="s.coin"></span></td>
                                    <td><span :class="Utils.dirBadgeClass(s.direction)" x-text="s.direction"></span></td>
                                    <td><span :class="Utils.gradeBadgeClass(s.grade)" x-text="s.grade"></span></td>
                                    <td x-html="Utils.scoreBar(s.score)"></td>
                                    <td><span class="mono" x-text="Utils.fmtPrice(s.entry)"></span></td>
                                    <td><span class="mono" style="color:var(--red)" x-text="Utils.fmtPrice(s.sl)"></span></td>
                                    <td><span class="mono" style="color:var(--green)" x-text="Utils.fmtPrice(s.tp1)"></span></td>
                                    <td><span class="mono" x-text="Utils.fmtPrice(s.exit_price)"></span></td>
                                    <td>
                                        <span
                                            class="mono"
                                            style="font-weight:600;"
                                            :style="{color: Utils.pnlColor(s.pnl)}"
                                            x-text="s.pnl != null ? Utils.fmtPnl(s.pnl) : '--'"
                                        ></span>
                                    </td>
                                    <td><span :class="Utils.outcomeBadgeClass(s.outcome)" x-text="s.outcome"></span></td>
                                    <td><span style="font-size:11px;color:var(--text-secondary)" x-text="s.regime || '--'"></span></td>
                                    <td><span style="font-size:11px;color:var(--text-secondary)" x-text="s.session || '--'"></span></td>
                                </tr>
                                <template x-if="expanded === s.id">
                                    <tr>
                                        <td colspan="14" style="padding:0;">
                                            <div style="padding:16px;background:var(--bg-tertiary);border-top:1px solid var(--bg-border);">
                                                <div class="grid-4" style="gap:8px;">
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Signal ID</div>
                                                        <div class="mono" style="font-size:13px;" x-text="s.id"></div>
                                                    </div>
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Risk Amount</div>
                                                        <div class="mono" style="font-size:13px;" x-text="s.risk_amt ? '$' + parseFloat(s.risk_amt).toFixed(2) : '--'"></div>
                                                    </div>
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Market Score</div>
                                                        <div class="mono" style="font-size:13px;" x-text="s.market_score != null ? s.market_score + '/100' : '--'"></div>
                                                    </div>
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Entry Score</div>
                                                        <div class="mono" style="font-size:13px;" x-text="s.entry_score != null ? s.entry_score + '/100' : '--'"></div>
                                                    </div>
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">BTC Score</div>
                                                        <div class="mono" style="font-size:13px;" x-text="s.btc_score != null ? s.btc_score + '/8' : '--'"></div>
                                                    </div>
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Signal Type</div>
                                                        <div class="mono" style="font-size:13px;" x-text="s.signal_type || '--'"></div>
                                                    </div>
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Timestamp</div>
                                                        <div style="font-size:12px;color:var(--text-secondary);" x-text="Utils.fmtTime(s.timestamp)"></div>
                                                    </div>
                                                    <div>
                                                        <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Outcome</div>
                                                        <span :class="Utils.outcomeBadgeClass(s.outcome)" x-text="s.outcome"></span>
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
        pageSize:    25,

        filters: {
            grade:     '',
            outcome:   '',
            direction: '',
            coin:      '',
            limit:     '100',
        },

        get total() {
            return this.signals.length
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

        async load(reset = false) {
            if (reset) this.currentPage = 1
            this.loading = true
            try {
                const params = {
                    limit: parseInt(this.filters.limit) || 100,
                }
                if (this.filters.grade)   params.grade   = this.filters.grade
                if (this.filters.coin)    params.coin    = this.filters.coin.toUpperCase()
                if (this.filters.outcome) params.outcome = this.filters.outcome

                this.signals = await API.signals(params) || []
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