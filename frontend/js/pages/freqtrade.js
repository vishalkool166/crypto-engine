function freqtradePage() {
    return `<div
        x-data="freqtradeData()"
        x-init="init()"
        @ft-update.window="_applyFtUpdate($event.detail)"
        @page-change.window="onPageChange($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Freqtrade</div>
                <div class="page-subtitle flex items-center gap-8">
                    <div
                        class="ws-dot"
                        :class="botState === 'running' ? '' : 'disconnected'"
                        aria-hidden="true"
                    ></div>
                    <span
                        role="status"
                        :aria-label="'Bot state: ' + botState"
                        x-text="'Bot ' + botState"
                    ></span>
                </div>
            </div>
            <div class="flex gap-8">
                <button
                    class="btn btn-success btn-sm"
                    @click="startBot"
                    :disabled="actionLoading === 'start' || botState === 'running'"
                    :aria-busy="actionLoading === 'start'"
                    aria-label="Start Freqtrade bot"
                >
                    <span x-show="actionLoading === 'start'" class="spinner" aria-hidden="true"></span>
                    <svg x-show="actionLoading !== 'start'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                    Start
                </button>
                <button
                    class="btn btn-danger btn-sm"
                    @click="stopBot"
                    :disabled="actionLoading === 'stop' || botState === 'stopped'"
                    :aria-busy="actionLoading === 'stop'"
                    aria-label="Stop Freqtrade bot"
                >
                    <span x-show="actionLoading === 'stop'" class="spinner" aria-hidden="true"></span>
                    <svg x-show="actionLoading !== 'stop'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18"/></svg>
                    Stop
                </button>
                <button
                    class="btn btn-ghost btn-sm"
                    @click="refresh"
                    :disabled="loading"
                    :aria-busy="loading"
                    aria-label="Refresh Freqtrade data"
                >
                    <span x-show="loading" class="spinner" aria-hidden="true"></span>
                    <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    Refresh
                </button>
            </div>
        </div>

        <div x-show="error" x-cloak class="alert alert-error mb-12" role="alert" x-text="error"></div>

        <div class="grid-4 mb-12">
            <div class="stat-card stat-card-blue" role="region" aria-label="Bot state">
                <div class="card-title">Bot State</div>
                <div style="margin-top:6px;">
                    <span
                        class="badge"
                        :class="botState === 'running' ? 'badge-online' : 'badge-offline'"
                        x-text="botState.toUpperCase()"
                    ></span>
                </div>
                <div
                    class="card-sub"
                    style="font-family:var(--font-mono);"
                    x-text="openTrades.length + ' open trades'"
                ></div>
            </div>

            <div class="stat-card stat-card-green" role="region" aria-label="Balance">
                <div class="card-title">Balance</div>
                <div
                    class="card-value"
                    style="font-family:var(--font-mono);color:var(--green);"
                    x-text="balance.total != null ? '$' + parseFloat(balance.total).toFixed(2) : '--'"
                    aria-live="polite"
                ></div>
                <div
                    class="card-sub"
                    style="font-family:var(--font-mono);"
                    x-text="balance.free != null ? 'Free: $' + parseFloat(balance.free).toFixed(2) : '--'"
                ></div>
            </div>

            <div class="stat-card" :class="profit.profit_all_coin >= 0 ? 'stat-card-green' : 'stat-card-red'" role="region" aria-label="Total PnL">
                <div class="card-title">Total PnL</div>
                <div
                    class="card-value"
                    style="font-family:var(--font-mono);"
                    :style="{color: Utils.pnlColor(profit.profit_all_coin)}"
                    x-text="profit.profit_all_coin != null ? Utils.fmtPnl(profit.profit_all_coin) : '--'"
                    aria-live="polite"
                ></div>
                <div
                    class="card-sub"
                    x-text="profit.trade_count != null ? profit.trade_count + ' total trades' : '--'"
                ></div>
            </div>

            <div class="stat-card stat-card-purple" role="region" aria-label="Win Rate">
                <div class="card-title">Win Rate</div>
                <div
                    class="card-value"
                    style="font-family:var(--font-mono);"
                    :style="{color: Utils.winRateColor((profit.winrate||0)*100)}"
                    x-text="profit.winrate != null ? ((profit.winrate||0)*100).toFixed(1) + '%' : '--'"
                    aria-live="polite"
                ></div>
                <div
                    class="card-sub"
                    x-text="profit.profit_factor != null ? 'PF: ' + parseFloat(profit.profit_factor||0).toFixed(2) : '--'"
                ></div>
            </div>
        </div>

        <div class="mb-12">
            <div class="section-header">
                <div class="section-title">Open Trades</div>
                <span class="tag" x-text="openTrades.length + ' open'"></span>
            </div>

            <template x-if="loading && !openTrades.length">
                <div class="card">
                    <div class="loading-skeleton">
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                    </div>
                </div>
            </template>

            <template x-if="!loading && !openTrades.length">
                <div class="card" x-html="Utils.emptyState('No open trades')"></div>
            </template>

            <template x-for="trade in openTrades" :key="trade.trade_id">
                <div
                    class="trade-card"
                    role="article"
                    :aria-label="trade.pair + ' open trade'"
                >
                    <div class="trade-card-header">
                        <div class="flex items-center gap-8">
                            <span
                                style="font-family:var(--font-mono);font-size:15px;font-weight:800;"
                                x-text="(trade.pair||'').replace('/USDT:USDT','USDT').replace('/USDT','USDT')"
                            ></span>
                            <span
                                :class="Utils.dirBadgeClass(trade.is_short ? 'SHORT' : 'LONG')"
                                x-text="trade.is_short ? 'SHORT' : 'LONG'"
                            ></span>
                            <span
                                class="tag"
                                style="font-family:var(--font-mono);"
                                x-text="'#' + trade.trade_id"
                            ></span>
                        </div>
                        <div class="flex items-center gap-12">
                            <div style="text-align:right;">
                                <div
                                    style="font-family:var(--font-mono);font-size:16px;font-weight:800;"
                                    :style="{color: Utils.pnlColor(trade.profit_abs)}"
                                    x-text="Utils.fmtPnl(trade.profit_abs)"
                                    aria-live="polite"
                                ></div>
                                <div
                                    style="font-family:var(--font-mono);font-size:11px;"
                                    :style="{color: Utils.pnlColor(trade.profit_ratio)}"
                                    x-text="Utils.fmtPct((trade.profit_ratio||0)*100)"
                                ></div>
                            </div>
                            <button
                                class="btn btn-danger btn-sm"
                                @click.stop="forceSell(trade.trade_id, trade.pair)"
                                :disabled="forceSelling === trade.trade_id"
                                :aria-busy="forceSelling === trade.trade_id"
                                :aria-label="'Force sell ' + trade.pair"
                            >
                                <span x-show="forceSelling === trade.trade_id" class="spinner" aria-hidden="true"></span>
                                <span x-show="forceSelling !== trade.trade_id">Force Sell</span>
                            </button>
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
                            <div class="level-label">Stop Loss</div>
                            <div
                                class="level-value"
                                style="color:var(--red);"
                                x-text="trade.sl_signal ? Utils.fmtPrice(trade.sl_signal) : '--'"
                            ></div>
                        </div>
                        <div class="level-item">
                            <div class="level-label">Take Profit</div>
                            <div
                                class="level-value"
                                style="color:var(--green);"
                                x-text="trade.tp1 ? Utils.fmtPrice(trade.tp1) : '--'"
                            ></div>
                        </div>
                        <div class="level-item">
                            <div class="level-label">Open</div>
                            <div class="level-value" x-text="Utils.fmtDuration(trade.open_date)"></div>
                        </div>
                        <div class="level-item">
                            <div class="level-label">Stake</div>
                            <div
                                class="level-value"
                                x-text="trade.stake_amount ? '$' + parseFloat(trade.stake_amount).toFixed(2) : '--'"
                            ></div>
                        </div>
                    </div>

                    <template x-if="trade.health">
                        <div
                            :class="Utils.healthBarClass(trade.health.state)"
                            style="margin-bottom:8px;"
                            role="status"
                            :aria-label="'Health: ' + trade.health.state"
                        >
                            <span aria-hidden="true" x-text="Utils.healthEmoji(trade.health.state)"></span>
                            <span style="font-weight:700;" x-text="trade.health.state"></span>
                            <template x-if="trade.health.failures && trade.health.failures.length">
                                <span style="font-size:11px;opacity:0.8;" x-text="'— ' + trade.health.failures[0]"></span>
                            </template>
                            <template x-if="!trade.health.failures?.length && trade.health.warnings?.length">
                                <span style="font-size:11px;opacity:0.8;" x-text="'— ' + trade.health.warnings[0]"></span>
                            </template>
                        </div>
                    </template>

                    <template x-if="!trade.health">
                        <div class="health-bar unknown" style="margin-bottom:8px;" role="status" aria-label="Checking health">
                            <span aria-hidden="true">⏳</span>
                            <span style="font-size:12px;">Checking health...</span>
                        </div>
                    </template>

                    <template x-if="trade.enter_tag">
                        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
                            Tag:
                            <span
                                style="font-family:var(--font-mono);"
                                x-text="trade.enter_tag"
                            ></span>
                        </div>
                    </template>
                </div>
            </template>
        </div>

        <div class="grid-2 mb-12">
            <div class="card">
                <div class="flex justify-between items-center mb-12">
                    <div class="section-title">Daily PnL</div>
                    <select
                        class="select"
                        style="width:100px;"
                        x-model="dailyDays"
                        @change="loadDaily"
                        aria-label="Select daily PnL period"
                    >
                        <option value="7">7 days</option>
                        <option value="14">14 days</option>
                        <option value="30">30 days</option>
                        <option value="60">60 days</option>
                        <option value="90">90 days</option>
                    </select>
                </div>

                <template x-if="dailyLoading">
                    <div class="loading-skeleton">
                        <div class="skeleton" style="height:160px;border-radius:var(--radius-sm);"></div>
                    </div>
                </template>

                <template x-if="!dailyLoading && !daily.length">
                    <div x-html="Utils.emptyState('No daily data for this period')"></div>
                </template>

                <div id="ft-daily-chart" x-show="daily.length > 0 && !dailyLoading"></div>
            </div>

            <div class="card">
                <div class="section-title mb-12">Profit Summary</div>
                <div class="stat-row">
                    <span class="stat-label">Total PnL</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);"
                        :style="{color: Utils.pnlColor(profit.profit_all_coin)}"
                        x-text="profit.profit_all_coin != null ? Utils.fmtPnl(profit.profit_all_coin) : '--'"
                    ></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Win Rate</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);"
                        :style="{color: Utils.winRateColor((profit.winrate||0)*100)}"
                        x-text="profit.winrate != null ? ((profit.winrate||0)*100).toFixed(1) + '%' : '--'"
                    ></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Total Trades</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);"
                        x-text="profit.trade_count != null ? profit.trade_count : '--'"
                    ></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Profit Factor</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);"
                        x-text="profit.profit_factor != null ? parseFloat(profit.profit_factor).toFixed(2) : '--'"
                    ></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Best Pair</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);font-size:11px;"
                        x-text="profit.best_pair || '--'"
                    ></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Balance</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);color:var(--blue);"
                        x-text="balance.total != null ? '$' + parseFloat(balance.total).toFixed(2) : '--'"
                    ></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Free</span>
                    <span
                        class="stat-value"
                        style="font-family:var(--font-mono);"
                        x-text="balance.free != null ? '$' + parseFloat(balance.free).toFixed(2) : '--'"
                    ></span>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="section-header">
                <div class="section-title">Trade History</div>
                <span class="tag" x-text="tradeHistory.length + ' trades'"></span>
            </div>

            <div class="table-wrap" role="region" aria-label="Freqtrade trade history" tabindex="0">
                <table aria-label="Closed trades">
                    <thead>
                        <tr>
                            <th scope="col">#</th>
                            <th scope="col">Pair</th>
                            <th scope="col">Dir</th>
                            <th scope="col">Entry</th>
                            <th scope="col">Exit</th>
                            <th scope="col">PnL</th>
                            <th scope="col">%</th>
                            <th scope="col">Duration</th>
                            <th scope="col">Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template x-if="!tradeHistory.length">
                            <tr>
                                <td colspan="9" x-html="Utils.emptyState('No closed trades yet')"></td>
                            </tr>
                        </template>
                        <template x-for="t in tradeHistory" :key="t.trade_id">
                            <tr>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);color:var(--text-muted);font-size:11px;"
                                        x-text="t.trade_id"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);font-weight:700;"
                                        x-text="(t.pair||'').replace('/USDT:USDT','USDT').replace('/USDT','USDT')"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        :class="Utils.dirBadgeClass(t.is_short ? 'SHORT' : 'LONG')"
                                        x-text="t.is_short ? 'SHORT' : 'LONG'"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);"
                                        x-text="Utils.fmtPrice(t.open_rate)"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);"
                                        x-text="Utils.fmtPrice(t.close_rate)"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);font-weight:700;"
                                        :style="{color: Utils.pnlColor(t.profit_abs)}"
                                        x-text="Utils.fmtPnl(t.profit_abs)"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);"
                                        :style="{color: Utils.pnlColor(t.profit_ratio)}"
                                        x-text="Utils.fmtPct((t.profit_ratio||0)*100)"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-size:11px;color:var(--text-secondary);"
                                        x-text="Utils.fmtDuration(t.open_date)"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-size:11px;color:var(--text-muted);"
                                        x-text="t.exit_reason || '--'"
                                    ></span>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
        </div>

    </div>`
}

function freqtradeData() {
    return {
        openTrades:    [],
        tradeHistory:  [],
        profit:        {},
        balance:       { total: null, free: null },
        daily:         [],
        dailyDays:     '7',
        dailyLoading:  false,
        botState:      'unknown',
        loading:       false,
        actionLoading: null,
        forceSelling:  null,
        error:         '',

        async init() {
            await this.refresh()
            window.addEventListener('page-change', e => {
                if (e.detail.page === 'freqtrade') {
                    Charts.destroy('ft-daily-chart')
                    this.refresh()
                }
            })
        },

        onPageChange(detail) {
            if (detail.page === 'freqtrade') {
                this.refresh()
            }
        },

        async refresh() {
            if (this.loading) return
            this.loading = true
            this.error   = ''

            try {
                const controller = new AbortController()
                const timeout    = setTimeout(() => controller.abort(), 12000)

                const res = await fetch('/api/ft/summary', {
                    credentials: 'include',
                    signal:      controller.signal,
                })

                clearTimeout(timeout)

                if (res.status === 401) {
                    window.location.href = '/login.html'
                    return
                }

                if (!res.ok) {
                    this.error = 'Freqtrade unavailable — check if container is running'
                    return
                }

                const data = await res.json().catch(() => null)
                if (data) {
                    this._applySummary(data)
                    this.$nextTick(() => this._renderChart())
                }

                this._loadTrades()

            } catch (e) {
                if (e.name === 'AbortError') {
                    this.error = 'Freqtrade request timed out — container may be starting'
                } else {
                    this.error = 'Freqtrade unavailable: ' + e.message
                }
            } finally {
                this.loading = false
            }
        },

        async _loadTrades() {
            try {
                const res = await fetch('/api/ft/trades?limit=50', {
                    credentials: 'include',
                })
                if (!res.ok) return
                const data = await res.json().catch(() => null)
                if (data) {
                    this.tradeHistory = Array.isArray(data.trades)
                        ? data.trades.filter(t => !t.is_open)
                        : []
                }
            } catch (e) {}
        },

        async loadDaily() {
            this.dailyLoading = true
            Charts.destroy('ft-daily-chart')
            try {
                const res = await fetch(`/api/ft/daily?days=${this.dailyDays}`, {
                    credentials: 'include',
                })
                if (!res.ok) return
                const raw = await res.json().catch(() => null)
                if (!raw) return

                const arr = Array.isArray(raw) ? raw
                          : Array.isArray(raw.data) ? raw.data : []

                this.daily = arr
                    .map(x => ({
                        date:        x.date || x.day || '',
                        profit_abs:  parseFloat(x.profit_abs || x.profit || 0),
                        trade_count: x.trade_count || x.trades || 0,
                    }))
                    .filter(x => x.date)

                this.$nextTick(() => this._renderChart())
            } catch (e) {
            } finally {
                this.dailyLoading = false
            }
        },

        _applySummary(d) {
            if (!d) return

            if (d.bot_state) this.botState = d.bot_state

            if (Array.isArray(d.status)) {
                this.openTrades = d.status
            }

            if (d.profit && typeof d.profit === 'object' && !d.profit.detail) {
                this.profit = d.profit
            }

            if (d.balance && typeof d.balance === 'object' && !d.balance.detail) {
                const currencies = d.balance.currencies || []
                const usdt       = currencies.find(c => c.currency === 'USDT') || {}
                this.balance = {
                    total: d.balance.total != null ? parseFloat(d.balance.total) : null,
                    free:  usdt.free       != null ? parseFloat(usdt.free)       : null,
                }
            }

            if (d.daily) {
                const arr = Array.isArray(d.daily) ? d.daily
                          : Array.isArray(d.daily.data) ? d.daily.data : []
                if (arr.length) {
                    this.daily = arr
                        .map(x => ({
                            date:        x.date || x.day || '',
                            profit_abs:  parseFloat(x.profit_abs || x.profit || 0),
                            trade_count: x.trade_count || x.trades || 0,
                        }))
                        .filter(x => x.date)
                }
            }
        },

        _applyFtUpdate(d) {
            if (!d) return
            this._applySummary(d)
            this.$nextTick(() => this._renderChart())
        },

        _renderChart() {
            if (window._app?.page !== 'freqtrade') return
            if (!this.daily.length) return
            const el = document.getElementById('ft-daily-chart')
            if (!el || el.offsetParent === null) return
            Charts.dailyPnl('ft-daily-chart', this.daily)
        },

        async startBot() {
            this.actionLoading = 'start'
            try {
                const res  = await fetch('/api/ft/start', {
                    method:      'POST',
                    credentials: 'include',
                    headers:     { 'Content-Type': 'application/json' },
                })
                const data = await res.json().catch(() => ({}))
                window._app?.showToast('Bot: ' + (data.status || 'start command sent'), 'success')
                setTimeout(() => this.refresh(), 2000)
            } catch (e) {
                window._app?.showToast('Start failed: ' + e.message, 'error')
            } finally {
                this.actionLoading = null
            }
        },

        async stopBot() {
            this.actionLoading = 'stop'
            try {
                const res  = await fetch('/api/ft/stop', {
                    method:      'POST',
                    credentials: 'include',
                    headers:     { 'Content-Type': 'application/json' },
                })
                const data = await res.json().catch(() => ({}))
                window._app?.showToast('Bot: ' + (data.status || 'stop command sent'), 'success')
                setTimeout(() => this.refresh(), 2000)
            } catch (e) {
                window._app?.showToast('Stop failed: ' + e.message, 'error')
            } finally {
                this.actionLoading = null
            }
        },

        async forceSell(tradeId, pair) {
            const coin   = (pair || '').replace('/USDT:USDT', '').replace('/USDT', '')
            const result = await TOTP.confirm(
                'Force Sell — ' + coin,
                'Enter your TOTP code to confirm force sell of ' + coin,
                async (code) => {
                    const res = await fetch('/api/ft/forcesell', {
                        method:      'POST',
                        credentials: 'include',
                        headers:     { 'Content-Type': 'application/json' },
                        body:        JSON.stringify({ tradeid: tradeId, totp_code: code })
                    })
                    return await res.json()
                }
            )

            if (result.success) {
                window._app?.showToast('Force sell submitted for ' + coin, 'success')
                setTimeout(() => this.refresh(), 2000)
            } else if (result.reason !== 'Cancelled') {
                window._app?.showToast('Force sell failed: ' + result.reason, 'error')
            }
        },
    }
}