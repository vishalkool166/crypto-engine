function overviewPage() {
    return `<div x-data="overviewData()" x-init="init()" @dashboard-update.window="onUpdate($event.detail)" @ft-update.window="onFtUpdate($event.detail)" @page-change.window="onPageChange($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Overview</div>
                <div class="page-subtitle" x-text="'Updated ' + lastUpdated"></div>
            </div>
            <button
                class="btn btn-ghost btn-sm"
                @click="triggerScan"
                :disabled="scanning"
                :aria-busy="scanning"
                aria-label="Trigger market scan now"
            >
                <span x-show="scanning" class="spinner" aria-hidden="true"></span>
                <svg x-show="!scanning" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <span x-text="scanning ? 'Scanning...' : 'Scan Now'"></span>
            </button>
        </div>

        <div class="grid-4 mb-12">
            <div class="stat-card stat-card-green" role="region" aria-label="Today PnL">
                <div class="card-title">Today PnL</div>
                <div
                    class="card-value"
                    style="font-family:var(--font-mono);"
                    :style="{color: summary.today_pnl_color || 'var(--text-muted)'}"
                    x-text="summary.today_pnl || '--'"
                    aria-live="polite"
                ></div>
                <div class="card-sub" x-text="(summary.today_trades || 0) + ' trades today'"></div>
            </div>

            <div class="stat-card stat-card-blue" role="region" aria-label="Win Rate">
                <div class="card-title">Win Rate</div>
                <div
                    class="card-value"
                    style="font-family:var(--font-mono);"
                    :style="{color: perf.win_rate_color || 'var(--text-muted)'}"
                    x-text="perf.win_rate || '--'"
                    aria-live="polite"
                ></div>
                <div class="card-sub" x-text="perf.win_rate_sub || '0 closed'"></div>
            </div>

            <div class="stat-card stat-card-purple" role="region" aria-label="Coins scanning">
                <div class="card-title">Scanning</div>
                <div
                    class="card-value"
                    style="font-family:var(--font-mono);color:var(--purple);"
                    x-text="summary.coins_count || '--'"
                    aria-live="polite"
                ></div>
                <div class="card-sub" x-text="(summary.tradeable_count || 0) + ' tradeable now'"></div>
            </div>

            <div class="stat-card stat-card-gold" role="region" aria-label="Total PnL">
                <div class="card-title">Total PnL</div>
                <div
                    class="card-value"
                    style="font-family:var(--font-mono);"
                    :style="{color: perf.pnl_color || 'var(--text-muted)'}"
                    x-text="perf.total_pnl || '--'"
                    aria-live="polite"
                ></div>
                <div class="card-sub" x-text="perf.pnl_sub || '0W · 0L'"></div>
            </div>
        </div>

        <div class="grid-2 mb-12">
            <div class="card">
                <div class="section-header">
                    <div class="section-title">Signal Queue</div>
                    <span
                        class="tag"
                        aria-label="Number of signals in queue"
                        x-text="queue.length + ' signals'"
                    ></span>
                </div>

                <template x-if="!queue.length">
                    <div x-html="Utils.emptyState('No tradeable signals — run scan')"></div>
                </template>

                <template x-for="sig in queue" :key="sig.coin">
                    <div
                        class="signal-queue-card"
                        :class="'grade-' + (sig.grade === 'A+' ? 'aplus' : sig.grade.toLowerCase())"
                        role="article"
                        :aria-label="sig.coin + ' ' + sig.direction + ' Grade ' + sig.grade"
                    >
                        <div class="flex justify-between items-center mb-8">
                            <div class="flex items-center gap-8">
                                <span
                                    style="font-family:var(--font-mono);font-size:15px;font-weight:800;"
                                    x-text="sig.coin + 'USDT'"
                                ></span>
                                <span :class="Utils.gradeBadgeClass(sig.grade)" x-text="sig.grade"></span>
                                <span :class="Utils.dirBadgeClass(sig.direction)" x-text="sig.direction"></span>
                            </div>
                            <div class="flex items-center gap-8">
                                <span
                                    style="font-size:11px;color:var(--text-muted);"
                                >Score</span>
                                <span
                                    style="font-family:var(--font-mono);font-size:13px;font-weight:700;"
                                    :style="{color: Utils.scoreBarColor(sig.score)}"
                                    x-text="sig.score + '/100'"
                                ></span>
                            </div>
                        </div>

                        <div class="trade-card-levels" style="grid-template-columns:repeat(3,1fr);">
                            <div class="level-item">
                                <div class="level-label">Entry</div>
                                <div class="level-value" x-text="sig.entry || '--'"></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Stop Loss</div>
                                <div class="level-value" style="color:var(--red);" x-text="sig.sl || '--'"></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Take Profit</div>
                                <div class="level-value" style="color:var(--green);" x-text="sig.tp1 || '--'"></div>
                            </div>
                        </div>

                        <div class="flex justify-between items-center" style="font-size:11px;color:var(--text-muted);margin-top:6px;">
                            <span>
                                R:R
                                <span
                                    style="font-family:var(--font-mono);color:var(--text-primary);font-weight:600;"
                                    x-text="'1:' + (sig.actual_rr || '--')"
                                ></span>
                            </span>
                            <span x-text="sig.regime || '--'"></span>
                            <span x-text="sig.session || '--'"></span>
                            <template x-if="sig.stake">
                                <span>
                                    Stake
                                    <span
                                        style="font-family:var(--font-mono);color:var(--blue);font-weight:600;"
                                        x-text="'$' + parseFloat(sig.stake).toFixed(2)"
                                    ></span>
                                    <span
                                        style="font-family:var(--font-mono);color:var(--text-muted);"
                                        x-text="sig.leverage + 'x'"
                                    ></span>
                                </span>
                            </template>
                        </div>

                        <template x-if="sig.thesis">
                            <div
                                class="thesis-block"
                                x-text="sig.thesis"
                                aria-label="Trade thesis"
                            ></div>
                        </template>
                    </div>
                </template>
            </div>

            <div class="card">
                <div class="section-header">
                    <div class="section-title">Active Trades</div>
                    <span
                        class="tag"
                        aria-label="Number of open trades"
                        x-text="activeTrades.length + ' open'"
                    ></span>
                </div>

                <template x-if="tradesLoading && !activeTrades.length">
                    <div>
                        <div class="loading-skeleton">
                            <div class="skeleton skeleton-row"></div>
                            <div class="skeleton skeleton-row"></div>
                        </div>
                    </div>
                </template>

                <template x-if="!tradesLoading && !activeTrades.length">
                    <div x-html="Utils.emptyState('No open trades')"></div>
                </template>

                <template x-for="trade in activeTrades" :key="trade.trade_id">
                    <div
                        class="trade-card"
                        role="article"
                        :aria-label="trade.pair + ' trade'"
                    >
                        <div class="trade-card-header">
                            <div class="flex items-center gap-8">
                                <span
                                    style="font-family:var(--font-mono);font-size:14px;font-weight:800;"
                                    x-text="(trade.pair||'').replace('/USDT:USDT','USDT').replace('/USDT','USDT')"
                                ></span>
                                <span
                                    :class="Utils.dirBadgeClass(trade.is_short ? 'SHORT' : 'LONG')"
                                    x-text="trade.is_short ? 'SHORT' : 'LONG'"
                                ></span>
                            </div>
                            <div class="flex items-center gap-8">
                                <span
                                    style="font-family:var(--font-mono);font-size:14px;font-weight:800;"
                                    :style="{color: Utils.pnlColor(trade.profit_abs)}"
                                    x-text="Utils.fmtPnl(trade.profit_abs)"
                                    aria-live="polite"
                                ></span>
                                <span
                                    style="font-family:var(--font-mono);font-size:11px;"
                                    :style="{color: Utils.pnlColor(trade.profit_ratio)}"
                                    x-text="Utils.fmtPct((trade.profit_ratio||0)*100)"
                                ></span>
                            </div>
                        </div>

                        <div class="trade-card-levels">
                            <div class="level-item">
                                <div class="level-label">Entry</div>
                                <div class="level-value" x-text="Utils.fmtPrice(trade.open_rate)"></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Current</div>
                                <div
                                    class="level-value"
                                    :style="{color: Utils.pnlColor(trade.profit_abs)}"
                                    x-text="Utils.fmtPrice(trade.current_rate)"
                                ></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Open</div>
                                <div class="level-value" x-text="Utils.fmtDuration(trade.open_date)"></div>
                            </div>
                        </div>

                        <template x-if="trade.health">
                            <div
                                :class="Utils.healthBarClass(trade.health.state)"
                                style="margin-top:4px;"
                                role="status"
                                :aria-label="'Trade health: ' + trade.health.state"
                            >
                                <span aria-hidden="true" x-text="Utils.healthEmoji(trade.health.state)"></span>
                                <span style="font-size:12px;font-weight:700;" x-text="trade.health.state"></span>
                                <template x-if="trade.health.failures && trade.health.failures.length">
                                    <span style="font-size:11px;opacity:0.8;" x-text="'— ' + trade.health.failures[0]"></span>
                                </template>
                            </div>
                        </template>

                        <template x-if="!trade.health">
                            <div class="health-bar unknown" style="margin-top:4px;" role="status" aria-label="Checking trade health">
                                <span aria-hidden="true">⏳</span>
                                <span style="font-size:12px;">Checking health...</span>
                            </div>
                        </template>
                    </div>
                </template>
            </div>
        </div>

        <div class="grid-2-1 mb-12">
            <div class="card">
                <div class="section-header">
                    <div class="section-title">Coin Radar</div>
                    <span class="tag" x-text="radar.length + ' coins'"></span>
                </div>

                <div class="table-wrap" role="region" aria-label="Coin radar" tabindex="0">
                    <table aria-label="Coin signals radar">
                        <thead>
                            <tr>
                                <th scope="col">Coin</th>
                                <th scope="col">Grade</th>
                                <th scope="col">Score</th>
                                <th scope="col">Direction</th>
                                <th scope="col">Price</th>
                                <th scope="col">24h</th>
                                <th scope="col">Regime</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template x-if="!radar.length">
                                <tr>
                                    <td colspan="7" x-html="Utils.emptyState('Run scan to populate radar')"></td>
                                </tr>
                            </template>
                            <template x-for="r in radar" :key="r.coin">
                                <tr>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);font-weight:700;"
                                            x-text="r.coin"
                                        ></span>
                                    </td>
                                    <td>
                                        <span :class="Utils.gradeBadgeClass(r.grade)" x-text="r.grade"></span>
                                    </td>
                                    <td x-html="Utils.scoreBar(r.score)"></td>
                                    <td>
                                        <span :class="Utils.dirBadgeClass(r.direction)" x-text="r.direction"></span>
                                    </td>
                                    <td>
                                        <span style="font-family:var(--font-mono);" x-text="r.price"></span>
                                    </td>
                                    <td>
                                        <span
                                            style="font-family:var(--font-mono);"
                                            :style="{color: r.change_color}"
                                            x-text="r.change"
                                        ></span>
                                    </td>
                                    <td>
                                        <span style="font-size:11px;color:var(--text-muted);" x-text="r.regime || '--'"></span>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <div class="section-title">Performance</div>
                </div>

                <div class="stat-row">
                    <span class="stat-label">Profit Factor</span>
                    <span class="stat-value" style="font-family:var(--font-mono);" x-text="perf.profit_factor || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Best Trade</span>
                    <span class="stat-value" style="font-family:var(--font-mono);color:var(--green);" x-text="perf.best_trade || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Max Drawdown</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);"
                        :style="{color: perf.dd_color || 'var(--text-muted)'}"
                        x-text="perf.max_drawdown || '--'"
                    ></span>
                </div>

                <div class="divider"></div>

                <div style="margin-bottom:10px;">
                    <div class="flex justify-between items-center" style="font-size:11px;margin-bottom:5px;">
                        <span style="color:var(--gold);font-weight:700;">
                            A+
                            <span style="font-family:var(--font-mono);" x-text="perf.aplus_wr"></span>
                        </span>
                        <span style="font-size:10px;color:var(--text-muted);" x-text="perf.aplus_detail"></span>
                    </div>
                    <div class="progress-bar">
                        <div
                            class="progress-fill"
                            :style="{width:(perf.aplus_bar||0)+'%',background:'var(--gold)'}"
                        ></div>
                    </div>
                </div>

                <div style="margin-bottom:10px;">
                    <div class="flex justify-between items-center" style="font-size:11px;margin-bottom:5px;">
                        <span style="color:var(--blue);font-weight:700;">
                            A
                            <span style="font-family:var(--font-mono);" x-text="perf.a_wr"></span>
                        </span>
                        <span style="font-size:10px;color:var(--text-muted);" x-text="perf.a_detail"></span>
                    </div>
                    <div class="progress-bar">
                        <div
                            class="progress-fill"
                            :style="{width:(perf.a_bar||0)+'%',background:'var(--blue)'}"
                        ></div>
                    </div>
                </div>

                <div>
                    <div class="flex justify-between items-center" style="font-size:11px;margin-bottom:5px;">
                        <span style="color:var(--orange);font-weight:700;">
                            B
                            <span style="font-family:var(--font-mono);" x-text="perf.b_wr"></span>
                        </span>
                        <span style="font-size:10px;color:var(--text-muted);" x-text="perf.b_detail"></span>
                    </div>
                    <div class="progress-bar">
                        <div
                            class="progress-fill"
                            :style="{width:(perf.b_bar||0)+'%',background:'var(--orange)'}"
                        ></div>
                    </div>
                </div>

                <div class="divider"></div>

                <div id="overview-donut" style="height:180px;"></div>
            </div>
        </div>

        <div class="card mb-12">
            <div class="section-header">
                <div class="section-title">Equity Curve</div>
                <span
                    class="tag"
                    x-text="perf.equity_curve ? perf.equity_curve.length + ' trades' : '0 trades'"
                ></span>
            </div>
            <div id="overview-equity" style="height:200px;"></div>
        </div>

        <div class="card">
            <div class="section-header">
                <div class="section-title">Recent Signals</div>
                <button
                    class="btn btn-ghost btn-sm"
                    @click="loadHistory"
                    :disabled="historyLoading"
                    aria-label="Refresh signal history"
                >
                    <span x-show="historyLoading" class="spinner" aria-hidden="true"></span>
                    Refresh
                </button>
            </div>

            <div class="table-wrap" role="region" aria-label="Recent signals" tabindex="0">
                <table aria-label="Recent closed signals">
                    <thead>
                        <tr>
                            <th scope="col">#</th>
                            <th scope="col">Time</th>
                            <th scope="col">Coin</th>
                            <th scope="col">Direction</th>
                            <th scope="col">Grade</th>
                            <th scope="col">Score</th>
                            <th scope="col">Entry</th>
                            <th scope="col">Exit</th>
                            <th scope="col">PnL</th>
                            <th scope="col">Result</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template x-if="!history.length">
                            <tr>
                                <td colspan="10" x-html="Utils.emptyState('No closed signals yet')"></td>
                            </tr>
                        </template>
                        <template x-for="s in history" :key="s.id">
                            <tr>
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
                                        x-text="Utils.fmtPrice(s.entry_price)"
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
                                        :style="{color: s.pnl_color}"
                                        x-text="s.pnl"
                                    ></span>
                                </td>
                                <td>
                                    <span :class="Utils.outcomeBadgeClass(s.outcome)" x-text="s.outcome"></span>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
        </div>

    </div>`
}

function overviewData() {
    return {
        summary:        {},
        perf:           {},
        queue:          [],
        radar:          [],
        history:        [],
        activeTrades:   [],
        lastUpdated:    '--',
        scanning:       false,
        tradesLoading:  true,
        historyLoading: false,
        _chartsDone:    false,

        init() {
            const data = window._app?.dashboardData
            if (data) this.onUpdate(data)

            window.addEventListener('dashboard-update', e => this.onUpdate(e.detail))
            window.addEventListener('ft-update',        e => this.onFtUpdate(e.detail))

            this.$nextTick(() => this.renderCharts())
        },

        onPageChange(detail) {
            if (detail.page === 'overview') {
                this._chartsDone = false
                this.$nextTick(() => this.renderCharts())
            }
        },

        onUpdate(data) {
            if (!data) return

            this.summary     = data.summary     || {}
            this.perf        = data.performance || {}
            this.queue       = data.signals?.queue  || []
            this.radar       = data.signals?.radar  || []
            this.history     = data.history     || []
            this.lastUpdated = Utils.fmtTimeAgo(data.timestamp)

            if (!this._chartsDone) {
                this.$nextTick(() => this.renderCharts())
            } else {
                this.$nextTick(() => this.updateCharts())
            }
        },

        onFtUpdate(data) {
            if (data && Array.isArray(data.status)) {
                this.activeTrades  = data.status
                this.tradesLoading = false
            }
        },

        async loadHistory() {
            this.historyLoading = true
            try {
                this.history = await API.dashboardHistory(10) || []
            } catch (e) {
            } finally {
                this.historyLoading = false
            }
        },

        renderCharts() {
            if (window._app?.page !== 'overview') return

            if (this.perf.equity_curve && this.perf.equity_curve.length) {
                Charts.equityFromCurve('overview-equity', this.perf.equity_curve)
            }

            const hasGradeData = (
                (parseFloat(this.perf.aplus_bar) || 0) > 0 ||
                (parseFloat(this.perf.a_bar)     || 0) > 0 ||
                (parseFloat(this.perf.b_bar)     || 0) > 0
            )

            if (hasGradeData) {
                Charts.gradeDonut('overview-donut', {
                    'A+': { total: parseFloat(this.perf.aplus_bar) || 0 },
                    'A':  { total: parseFloat(this.perf.a_bar)     || 0 },
                    'B':  { total: parseFloat(this.perf.b_bar)     || 0 },
                })
            }

            this._chartsDone = true
        },

        updateCharts() {
            if (window._app?.page !== 'overview') return
            if (this.perf.equity_curve && this.perf.equity_curve.length) {
                if (!Charts.exists('overview-equity')) {
                    Charts.equityFromCurve('overview-equity', this.perf.equity_curve)
                }
            }
        },

        async triggerScan() {
            this.scanning = true
            try {
                await API.scan()
                window._app?.showToast('Scan triggered — results in 1-2 minutes', 'success')
            } catch (e) {
                window._app?.showToast('Scan failed: ' + e.message, 'error')
            } finally {
                this.scanning = false
            }
        },
    }
}