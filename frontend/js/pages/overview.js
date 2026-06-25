function overviewPage() {
    return `<div x-data="overviewData()" x-init="init()" @dashboard-update.window="onUpdate($event.detail)" @ft-update.window="onFtUpdate($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Overview</div>
                <div class="page-subtitle" x-text="'Last updated: ' + lastUpdated"></div>
            </div>
            <button class="btn btn-ghost btn-sm" @click="triggerScan" :disabled="scanning" aria-label="Trigger scan">
                <span x-show="scanning" class="spinner" aria-hidden="true"></span>
                <svg x-show="!scanning" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                <span x-text="scanning ? 'Scanning...' : 'Scan Now'"></span>
            </button>
        </div>

        <div class="grid-4">
            <div class="card">
                <div class="card-title">Today PnL</div>
                <div class="card-value" style="font-family:var(--font-mono);" :style="{color: Utils.pnlColor(header.today_pnl_raw)}" x-text="header.today_pnl || '--'"></div>
                <div class="card-sub" x-text="(header.today_trades || 0) + ' trades today'"></div>
            </div>
            <div class="card">
                <div class="card-title">Win Rate</div>
                <div class="card-value" style="font-family:var(--font-mono);" :style="{color: Utils.winRateColor(header.win_rate_raw)}" x-text="header.win_rate || '--'"></div>
                <div class="card-sub" x-text="perf.win_rate_sub || '0 closed'"></div>
            </div>
            <div class="card">
                <div class="card-title">Coins Scanning</div>
                <div class="card-value" style="font-family:var(--font-mono);color:var(--blue)" x-text="header.coins_count || '--'"></div>
                <div class="card-sub">Next: <span style="font-family:var(--font-mono);" x-text="nextScan"></span></div>
            </div>
            <div class="card">
                <div class="card-title">Trading Mode</div>
                <div class="card-value" style="margin-top:4px;">
                    <span class="badge" :class="header.mode==='live'?'badge-live':'badge-paper'" x-text="(header.mode||'paper').toUpperCase()"></span>
                </div>
                <div class="card-sub" x-text="'Grades: ' + (header.grades_str || '--')"></div>
            </div>
        </div>

        <div class="grid-2 mt-12">
            <div class="card">
                <div class="card-title flex justify-between items-center">
                    <span>Signal Queue</span>
                    <div class="flex items-center gap-8">
                        <span class="tag" x-text="queue.length + ' signals'"></span>
                        <button
                            x-show="queue.length > 3"
                            class="btn btn-ghost btn-sm"
                            style="padding:2px 8px;font-size:11px;"
                            @click="showAllQueue = !showAllQueue"
                            x-text="showAllQueue ? 'Show less' : 'Show all ' + queue.length"
                        ></button>
                    </div>
                </div>

                <template x-if="!queue.length">
                    <div x-html="Utils.emptyState('No tradeable signals — run scan')"></div>
                </template>

                <div
                    x-show="queue.length > 0"
                    :style="!showAllQueue && queue.length > 3 ? 'max-height:420px;overflow-y:auto;' : ''"
                >
                    <template x-for="sig in (showAllQueue ? queue : queue.slice(0,3))" :key="sig.coin">
                        <div class="trade-card" style="margin-bottom:8px;">
                            <div class="trade-card-header">
                                <div class="flex items-center gap-8">
                                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:700;" x-text="sig.coin + 'USDT'"></span>
                                    <span :class="Utils.gradeBadgeClass(sig.grade)" x-text="sig.grade"></span>
                                    <span :class="Utils.dirBadgeClass(sig.direction)" x-text="sig.direction"></span>
                                </div>
                                <div class="flex items-center gap-8">
                                    <span style="font-size:11px;color:var(--text-muted)">Score</span>
                                    <span style="font-family:var(--font-mono);font-size:12px;font-weight:600;" :style="{color: Utils.scoreBarColor(sig.score)}" x-text="sig.score + '/100'"></span>
                                </div>
                            </div>

                            <div class="trade-card-levels">
                                <div class="level-item">
                                    <div class="level-label">Entry</div>
                                    <div class="level-value" x-text="sig.entry || '--'"></div>
                                </div>
                                <div class="level-item">
                                    <div class="level-label">Stop Loss</div>
                                    <div class="level-value" style="color:var(--red)" x-text="sig.sl || '--'"></div>
                                </div>
                                <div class="level-item">
                                    <div class="level-label">Take Profit</div>
                                    <div class="level-value" style="color:var(--green)" x-text="sig.tp1 || '--'"></div>
                                </div>
                            </div>

                            <div class="flex justify-between items-center" style="font-size:11px;color:var(--text-secondary);">
                                <span>R:R <span style="font-family:var(--font-mono);color:var(--text-primary)" x-text="'1:' + (sig.actual_rr || '--')"></span></span>
                                <span x-text="sig.regime || '--'"></span>
                                <span x-text="sig.session || '--'"></span>
                                <template x-if="sig.ml_probability != null">
                                    <span>ML <span style="font-family:var(--font-mono);" :style="{color: sig.ml_probability >= 0.65 ? 'var(--green)' : 'var(--red)'}" x-text="(sig.ml_probability * 100).toFixed(0) + '%'"></span></span>
                                </template>
                            </div>

                            <template x-if="sig.thesis">
                                <div style="margin-top:8px;font-size:11px;color:var(--text-secondary);line-height:1.6;border-top:1px solid var(--bg-border);padding-top:8px;white-space:pre-line;" x-text="sig.thesis"></div>
                            </template>
                        </div>
                    </template>
                </div>
            </div>

            <div class="card">
                <div class="card-title flex justify-between items-center">
                    <span>Active Trades</span>
                    <div class="flex items-center gap-8">
                        <span class="tag" x-text="activeTrades.length + ' open'"></span>
                        <button
                            x-show="activeTrades.length > 3"
                            class="btn btn-ghost btn-sm"
                            style="padding:2px 8px;font-size:11px;"
                            @click="showAllTrades = !showAllTrades"
                            x-text="showAllTrades ? 'Show less' : 'Show all ' + activeTrades.length"
                        ></button>
                    </div>
                </div>

                <template x-if="tradesLoading && !activeTrades.length">
                    <div x-html="Utils.loadingState()"></div>
                </template>

                <template x-if="!tradesLoading && !activeTrades.length">
                    <div x-html="Utils.emptyState('No open trades')"></div>
                </template>

                <div
                    x-show="activeTrades.length > 0"
                    :style="!showAllTrades && activeTrades.length > 3 ? 'max-height:420px;overflow-y:auto;' : ''"
                >
                    <template x-for="trade in (showAllTrades ? activeTrades : activeTrades.slice(0,3))" :key="trade.trade_id">
                        <div class="trade-card" style="margin-bottom:8px;">
                            <div class="trade-card-header">
                                <div class="flex items-center gap-8">
                                    <span style="font-family:var(--font-mono);font-size:14px;font-weight:700;" x-text="(trade.pair||'').replace('/USDT:USDT','USDT').replace('/USDT','USDT')"></span>
                                    <span :class="Utils.dirBadgeClass(trade.is_short ? 'SHORT' : 'LONG')" x-text="trade.is_short ? 'SHORT' : 'LONG'"></span>
                                </div>
                                <div class="flex items-center gap-8">
                                    <span style="font-family:var(--font-mono);font-size:13px;font-weight:700;" :style="{color: Utils.pnlColor(trade.profit_abs)}" x-text="Utils.fmtPnl(trade.profit_abs)"></span>
                                    <span style="font-family:var(--font-mono);font-size:11px;" :style="{color: Utils.pnlColor(trade.profit_ratio)}" x-text="Utils.fmtPct((trade.profit_ratio||0)*100)"></span>
                                </div>
                            </div>

                            <div class="trade-card-levels">
                                <div class="level-item">
                                    <div class="level-label">Entry</div>
                                    <div class="level-value" x-text="Utils.fmtPrice(trade.open_rate)"></div>
                                </div>
                                <div class="level-item">
                                    <div class="level-label">Current</div>
                                    <div class="level-value" x-text="Utils.fmtPrice(trade.current_rate)"></div>
                                </div>
                                <div class="level-item">
                                    <div class="level-label">Open</div>
                                    <div class="level-value" x-text="Utils.fmtDuration(trade.open_date)"></div>
                                </div>
                            </div>

                            <template x-if="trade.health">
                                <div :class="Utils.healthBarClass(trade.health.state)" style="margin-top:8px;">
                                    <span x-text="Utils.healthEmoji(trade.health.state)"></span>
                                    <span style="font-size:12px;font-weight:600;" x-text="trade.health.state || 'Checking...'"></span>
                                    <template x-if="trade.health.failures && trade.health.failures.length">
                                        <span style="font-size:11px;opacity:0.8;" x-text="'— ' + trade.health.failures[0]"></span>
                                    </template>
                                </div>
                            </template>

                            <template x-if="!trade.health">
                                <div class="health-bar" style="margin-top:8px;background:var(--bg-tertiary);color:var(--text-muted);">
                                    <span>⏳</span>
                                    <span style="font-size:12px;">Checking health...</span>
                                </div>
                            </template>
                        </div>
                    </template>
                </div>
            </div>
        </div>

        <div class="grid-2-1 mt-12">
            <div class="card">
                <div class="card-title">Coin Radar</div>
                <div class="table-wrap" role="region" aria-label="Coin radar table" tabindex="0">
                    <table aria-label="Coin signals radar">
                        <thead>
                            <tr>
                                <th scope="col">Coin</th>
                                <th scope="col">Grade</th>
                                <th scope="col">Score</th>
                                <th scope="col">Direction</th>
                                <th scope="col">Price</th>
                                <th scope="col">24h</th>
                                <th scope="col">Confidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template x-if="!radar.length">
                                <tr><td colspan="7" x-html="Utils.emptyState('Run scan to populate radar')"></td></tr>
                            </template>
                            <template x-for="r in radar" :key="r.coin">
                                <tr>
                                    <td><span style="font-family:var(--font-mono);font-weight:600;" x-text="r.coin"></span></td>
                                    <td><span :class="Utils.gradeBadgeClass(r.grade)" x-text="r.grade"></span></td>
                                    <td x-html="Utils.scoreBar(r.score)"></td>
                                    <td><span :class="Utils.dirBadgeClass(r.direction)" x-text="r.direction"></span></td>
                                    <td><span style="font-family:var(--font-mono);" x-text="r.price"></span></td>
                                    <td><span style="font-family:var(--font-mono);" :style="{color: Utils.changeColor(r.change_raw ?? r.change)}" x-text="r.change"></span></td>
                                    <td><span style="font-size:11px;color:var(--text-secondary)" x-text="r.confidence || '--'"></span></td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Performance</div>
                <div class="stat-row">
                    <span class="stat-label">Total PnL</span>
                    <span class="stat-value" style="font-family:var(--font-mono);" :style="{color: Utils.pnlColor(perf.total_pnl_raw)}" x-text="perf.total_pnl || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Win Rate</span>
                    <span class="stat-value" style="font-family:var(--font-mono);" :style="{color: Utils.winRateColor(perf.win_rate_raw)}" x-text="perf.win_rate || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Profit Factor</span>
                    <span class="stat-value" style="font-family:var(--font-mono);" x-text="perf.profit_factor || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Best Trade</span>
                    <span class="stat-value" style="font-family:var(--font-mono);color:var(--green)" x-text="perf.best_trade || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Max Drawdown</span>
                    <span class="stat-value" style="font-family:var(--font-mono);" :style="{color: perf.dd_color || 'var(--text-muted)'}" x-text="perf.max_drawdown || '--'"></span>
                </div>

                <div class="divider"></div>

                <div style="margin-bottom:8px;">
                    <div class="flex justify-between" style="font-size:11px;margin-bottom:4px;">
                        <span style="color:var(--purple);font-weight:600;">A+ <span style="font-family:var(--font-mono);" x-text="perf.aplus_wr"></span></span>
                        <span style="color:var(--text-muted);font-size:10px;" x-text="perf.aplus_detail"></span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" :style="{width:(perf.aplus_bar||0)+'%',background:'var(--purple)'}"></div>
                    </div>
                </div>

                <div style="margin-bottom:8px;">
                    <div class="flex justify-between" style="font-size:11px;margin-bottom:4px;">
                        <span style="color:var(--blue);font-weight:600;">A <span style="font-family:var(--font-mono);" x-text="perf.a_wr"></span></span>
                        <span style="color:var(--text-muted);font-size:10px;" x-text="perf.a_detail"></span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" :style="{width:(perf.a_bar||0)+'%',background:'var(--blue)'}"></div>
                    </div>
                </div>

                <div>
                    <div class="flex justify-between" style="font-size:11px;margin-bottom:4px;">
                        <span style="color:var(--orange);font-weight:600;">B <span style="font-family:var(--font-mono);" x-text="perf.b_wr"></span></span>
                        <span style="color:var(--text-muted);font-size:10px;" x-text="perf.b_detail"></span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" :style="{width:(perf.b_bar||0)+'%',background:'var(--orange)'}"></div>
                    </div>
                </div>

                <div id="overview-donut" class="mt-12"></div>
            </div>
        </div>

        <div class="card mt-12">
            <div class="card-title">Recent Signals</div>
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
                            <tr><td colspan="10" x-html="Utils.emptyState('No closed signals yet')"></td></tr>
                        </template>
                        <template x-for="s in history" :key="s.id">
                            <tr>
                                <td><span style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;" x-text="s.id"></span></td>
                                <td><span style="font-size:11px;color:var(--text-secondary)" x-text="Utils.fmtTimeAgo(s.opened_at)"></span></td>
                                <td><span style="font-family:var(--font-mono);font-weight:600;" x-text="s.coin"></span></td>
                                <td><span :class="Utils.dirBadgeClass(s.direction)" x-text="s.direction"></span></td>
                                <td><span :class="Utils.gradeBadgeClass(s.grade)" x-text="s.grade"></span></td>
                                <td x-html="Utils.scoreBar(s.score_at_entry)"></td>
                                <td><span style="font-family:var(--font-mono);" x-text="Utils.fmtPrice(s.entry_price)"></span></td>
                                <td><span style="font-family:var(--font-mono);" x-text="Utils.fmtPrice(s.exit_price)"></span></td>
                                <td><span style="font-family:var(--font-mono);font-weight:600;" :style="{color: Utils.pnlColor(s.pnl_raw)}" x-text="s.pnl"></span></td>
                                <td><span :class="Utils.outcomeBadgeClass(s.outcome)" x-text="s.outcome"></span></td>
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
        header:        {},
        perf:          {},
        queue:         [],
        radar:         [],
        history:       [],
        activeTrades:  [],
        nextScan:      '--',
        lastUpdated:   '--',
        scanning:      false,
        showAllQueue:  false,
        showAllTrades: false,
        tradesLoading: true,
        _chartRendered: false,

        init() {
            const data = window._app?.dashboardData
            if (data && data.type === 'dashboard') {
                this.onUpdate(data)
            }

            this._loadActiveTrades()

            window.addEventListener('dashboard-update', e => this.onUpdate(e.detail))
            window.addEventListener('ft-update',        e => this.onFtUpdate(e.detail))
            window.addEventListener('page-change',      e => {
                if (e.detail.page === 'overview') {
                    this._chartRendered = false
                    this.$nextTick(() => this.renderCharts())
                }
            })

            this.$nextTick(() => this.renderCharts())
        },

        async _loadActiveTrades() {
            this.tradesLoading = true
            try {
                const controller = new AbortController()
                const timeout    = setTimeout(() => controller.abort(), 10000)
                const res = await fetch('/api/ft/summary', {
                    credentials: 'include',
                    signal:      controller.signal,
                })
                clearTimeout(timeout)
                if (!res.ok) return
                const data = await res.json().catch(() => ({}))
                if (Array.isArray(data.status)) {
                    this.activeTrades = data.status
                }
            } catch (e) {
            } finally {
                this.tradesLoading = false
            }
        },

        onUpdate(data) {
            this.header      = data.header      || {}
            this.perf        = data.performance || {}
            this.queue       = data.queue       || []
            this.radar       = data.radar       || []
            this.history     = data.history     || []
            this.lastUpdated = Utils.fmtTimeAgo(data.timestamp)

            if (data.next_scan_epoch) {
                const diff = Math.max(0, data.next_scan_epoch - Date.now())
                const mins = Math.floor(diff / 60000)
                const secs = Math.floor((diff % 60000) / 1000)
                this.nextScan = `${mins}m ${secs}s`
            }

            if (!this._chartRendered) {
                this.$nextTick(() => this.renderCharts())
            }
        },

        onFtUpdate(data) {
            if (data && Array.isArray(data.status)) {
                this.activeTrades  = data.status
                this.tradesLoading = false
            }
        },

        renderCharts() {
            if (window._app?.page !== 'overview') return
            if (this._chartRendered) return
            const el = document.getElementById('overview-donut')
            if (!el) return

            const hasData = (
                (parseFloat(this.perf.aplus_bar) || 0) > 0 ||
                (parseFloat(this.perf.a_bar)     || 0) > 0 ||
                (parseFloat(this.perf.b_bar)     || 0) > 0
            )

            if (!hasData) return

            Charts.gradeDonut('overview-donut', {
                'A+': { total: parseFloat(this.perf.aplus_bar) || 0 },
                'A':  { total: parseFloat(this.perf.a_bar)     || 0 },
                'B':  { total: parseFloat(this.perf.b_bar)     || 0 },
            })

            this._chartRendered = true
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