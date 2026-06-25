function freqtradePage() {
    return `<div x-data="freqtradeData()" x-init="init()" @ft-update.window="onFtUpdate($event.detail)" @dashboard-update.window="onDashUpdate($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Freqtrade</div>
                <div class="page-subtitle" x-text="'Bot state: ' + (botState || '--')"></div>
            </div>
            <div class="flex gap-8">
                <button class="btn btn-success btn-sm" @click="startBot" :disabled="actionLoading || botState === 'running'">
                    <span x-show="actionLoading === 'start'" class="spinner"></span>
                    <svg x-show="actionLoading !== 'start'" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                    Start
                </button>
                <button class="btn btn-danger btn-sm" @click="stopBot" :disabled="actionLoading || botState === 'stopped'">
                    <span x-show="actionLoading === 'stop'" class="spinner"></span>
                    <svg x-show="actionLoading !== 'stop'" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18"/></svg>
                    Stop
                </button>
                <button class="btn btn-ghost btn-sm" @click="load" :disabled="loading">
                    <span x-show="loading" class="spinner"></span>
                    <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                    Refresh
                </button>
            </div>
        </div>

        <div class="grid-4">
            <div class="card">
                <div class="card-title">Bot State</div>
                <div class="card-value">
                    <span
                        class="badge"
                        :class="botState === 'running' ? 'badge-online' : 'badge-offline'"
                        x-text="(botState || 'unknown').toUpperCase()"
                    ></span>
                </div>
                <div class="card-sub" x-text="openTrades.length + ' / ' + maxTrades + ' trades open'"></div>
            </div>
            <div class="card">
                <div class="card-title">Balance</div>
                <div class="card-value mono" style="color:var(--blue)" x-text="balance.total ? '$' + parseFloat(balance.total).toFixed(2) : '--'"></div>
                <div class="card-sub mono" x-text="balance.free ? 'Free: $' + parseFloat(balance.free || 0).toFixed(2) : '--'"></div>
            </div>
            <div class="card">
                <div class="card-title">Total PnL</div>
                <div class="card-value mono" :style="{color: Utils.pnlColor(profit.profit_all_coin)}" x-text="profit.profit_all_coin != null ? Utils.fmtPnl(profit.profit_all_coin) : '--'"></div>
                <div class="card-sub" x-text="profit.trade_count ? profit.trade_count + ' total trades' : '--'"></div>
            </div>
            <div class="card">
                <div class="card-title">Win Rate</div>
                <div class="card-value mono" :style="{color: Utils.winRateColor((profit.winrate || 0) * 100)}" x-text="profit.winrate != null ? ((profit.winrate || 0) * 100).toFixed(1) + '%' : '--'"></div>
                <div class="card-sub" x-text="profit.profit_factor ? 'PF: ' + parseFloat(profit.profit_factor || 0).toFixed(2) : '--'"></div>
            </div>
        </div>

        <div class="grid-2 mt-12">
            <div class="card">
                <div class="card-title flex justify-between items-center">
                    <span>Open Trades</span>
                    <span class="tag" x-text="openTrades.length + ' open'"></span>
                </div>

                <template x-if="!openTrades.length">
                    <div x-html="Utils.emptyState('No open trades')"></div>
                </template>

                <template x-for="trade in openTrades" :key="trade.trade_id">
                    <div class="trade-card">
                        <div class="trade-card-header">
                            <div class="flex items-center gap-8">
                                <span class="mono" style="font-size:15px;font-weight:700;" x-text="trade.pair?.replace('/USDT:USDT','USDT')"></span>
                                <span :class="Utils.dirBadgeClass(trade.is_short ? 'SHORT' : 'LONG')" x-text="trade.is_short ? 'SHORT' : 'LONG'"></span>
                                <span class="tag" x-text="'#' + trade.trade_id"></span>
                            </div>
                            <div class="flex items-center gap-8">
                                <div>
                                    <div class="mono" style="font-size:14px;font-weight:700;" :style="{color: Utils.pnlColor(trade.profit_abs)}" x-text="Utils.fmtPnl(trade.profit_abs)"></div>
                                    <div class="mono" style="font-size:11px;text-align:right;" :style="{color: Utils.pnlColor(trade.profit_ratio)}" x-text="Utils.fmtPct((trade.profit_ratio || 0) * 100)"></div>
                                </div>
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
                                <div class="level-label">SL (Signal)</div>
                                <div class="level-value" style="color:var(--red)" x-text="trade.sl_signal ? Utils.fmtPrice(trade.sl_signal) : '--'"></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">TP1 (Signal)</div>
                                <div class="level-value" style="color:var(--green)" x-text="trade.tp1 ? Utils.fmtPrice(trade.tp1) : '--'"></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Open</div>
                                <div class="level-value" x-text="Utils.fmtDuration(trade.open_date)"></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Stake</div>
                                <div class="level-value" x-text="trade.stake_amount ? '$' + parseFloat(trade.stake_amount).toFixed(2) : '--'"></div>
                            </div>
                        </div>

                        <template x-if="trade.health">
                            <div :class="Utils.healthBarClass(trade.health.state)" style="margin-bottom:10px;">
                                <span x-text="Utils.healthEmoji(trade.health.state)"></span>
                                <span style="font-weight:600;" x-text="trade.health.state"></span>
                                <template x-if="trade.health.failures?.length">
                                    <span style="font-size:11px;opacity:0.8;" x-text="'— ' + trade.health.failures[0]"></span>
                                </template>
                                <template x-if="!trade.health.failures?.length && trade.health.warnings?.length">
                                    <span style="font-size:11px;opacity:0.8;" x-text="'— ' + trade.health.warnings[0]"></span>
                                </template>
                            </div>
                        </template>

                        <template x-if="trade.enter_tag">
                            <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px;">
                                Tag: <span class="mono" x-text="trade.enter_tag"></span>
                            </div>
                        </template>

                        <div class="flex justify-end">
                            <button
                                class="btn btn-danger btn-sm"
                                @click="forceSell(trade.trade_id, trade.pair)"
                                :disabled="forceSelling === trade.trade_id"
                            >
                                <span x-show="forceSelling === trade.trade_id" class="spinner"></span>
                                Force Sell
                            </button>
                        </div>
                    </div>
                </template>
            </div>

            <div class="card">
                <div class="card-title">Daily PnL (7 days)</div>
                <div id="ft-daily-chart"></div>

                <div class="divider"></div>

                <div class="card-title mt-12">Profit Summary</div>
                <div class="stat-row">
                    <span class="stat-label">Total PnL</span>
                    <span class="stat-value mono" :style="{color: Utils.pnlColor(profit.profit_all_coin)}" x-text="profit.profit_all_coin != null ? Utils.fmtPnl(profit.profit_all_coin) : '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Win Rate</span>
                    <span class="stat-value mono" x-text="profit.winrate != null ? ((profit.winrate || 0) * 100).toFixed(1) + '%' : '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Total Trades</span>
                    <span class="stat-value mono" x-text="profit.trade_count || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Best Pair</span>
                    <span class="stat-value mono" x-text="profit.best_pair || '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Best Profit</span>
                    <span class="stat-value mono" style="color:var(--green)" x-text="profit.best_pair_profit_ratio != null ? Utils.fmtPct((profit.best_pair_profit_ratio || 0) * 100) : '--'"></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Worst Profit</span>
                    <span class="stat-value mono" style="color:var(--red)" x-text="profit.worst_pair_profit_ratio != null ? Utils.fmtPct((profit.worst_pair_profit_ratio || 0) * 100) : '--'"></span>
                </div>
            </div>
        </div>

        <div class="card mt-12">
            <div class="card-title flex justify-between items-center">
                <span>Trade History</span>
                <span class="tag" x-text="tradeHistory.length + ' trades'"></span>
            </div>

            <div x-show="loading" x-html="Utils.loadingState()"></div>

            <div x-show="!loading" class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Pair</th>
                            <th>Dir</th>
                            <th>Open</th>
                            <th>Close</th>
                            <th>Entry</th>
                            <th>Exit</th>
                            <th>PnL</th>
                            <th>%</th>
                            <th>Duration</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template x-if="!tradeHistory.length">
                            <tr><td colspan="11" x-html="Utils.emptyState('No closed trades yet')"></td></tr>
                        </template>
                        <template x-for="t in tradeHistory" :key="t.trade_id">
                            <tr>
                                <td><span class="mono" style="color:var(--text-muted);font-size:11px;" x-text="t.trade_id"></span></td>
                                <td><span class="mono" style="font-weight:600;" x-text="t.pair?.replace('/USDT:USDT','USDT')"></span></td>
                                <td><span :class="Utils.dirBadgeClass(t.is_short ? 'SHORT' : 'LONG')" x-text="t.is_short ? 'SHORT' : 'LONG'"></span></td>
                                <td><span style="font-size:11px;color:var(--text-secondary)" x-text="Utils.fmtTimeAgo(t.open_date)"></span></td>
                                <td><span style="font-size:11px;color:var(--text-secondary)" x-text="Utils.fmtTimeAgo(t.close_date)"></span></td>
                                <td><span class="mono" x-text="Utils.fmtPrice(t.open_rate)"></span></td>
                                <td><span class="mono" x-text="Utils.fmtPrice(t.close_rate)"></span></td>
                                <td><span class="mono" style="font-weight:600;" :style="{color: Utils.pnlColor(t.profit_abs)}" x-text="Utils.fmtPnl(t.profit_abs)"></span></td>
                                <td><span class="mono" :style="{color: Utils.pnlColor(t.profit_ratio)}" x-text="Utils.fmtPct((t.profit_ratio || 0) * 100)"></span></td>
                                <td><span style="font-size:11px;color:var(--text-secondary)" x-text="Utils.fmtDuration(t.open_date)"></span></td>
                                <td><span style="font-size:11px;color:var(--text-muted)" x-text="t.exit_reason || '--'"></span></td>
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
        openTrades:   [],
        tradeHistory: [],
        profit:       {},
        balance:      {},
        daily:        [],
        botState:     '--',
        maxTrades:    3,
        loading:      false,
        actionLoading: null,
        forceSelling: null,

        async init() {
            await this.load()
            window.addEventListener('page-change', e => {
                if (e.detail.page === 'freqtrade') this.load()
            })
        },

        async load() {
            this.loading = true
            try {
                const [summary, trades] = await Promise.all([
                    API.ftSummary(),
                    API.get('/ft/trades?limit=50').catch(() => ({ trades: [] }))
                ])

                this.openTrades  = summary.status  || []
                this.profit      = summary.profit   || {}
                this.balance     = this._parseBalance(summary.balance || {})
                this.daily       = summary.daily    || []
                this.botState    = summary.bot_state || '--'
                this.tradeHistory = (trades.trades || []).filter(t => !t.is_open)

                this.$nextTick(() => this.renderCharts())
            } catch (e) {
                window._app?.showToast('Failed to load Freqtrade data: ' + e.message, 'error')
            } finally {
                this.loading = false
            }
        },

        _parseBalance(raw) {
            if (!raw) return {}
            const currencies = raw.currencies || []
            const usdt       = currencies.find(c => c.currency === 'USDT') || {}
            return {
                total: raw.total || 0,
                free:  usdt.free  || 0,
                used:  usdt.used  || 0,
            }
        },

        onFtUpdate(data) {
            this.openTrades = data.status   || this.openTrades
            this.profit     = data.profit   || this.profit
            this.balance    = this._parseBalance(data.balance || {})
            this.botState   = data.bot_state || this.botState
        },

        onDashUpdate(data) {},

        renderCharts() {
            if (window._app?.page !== 'freqtrade') return
            if (this.daily && this.daily.length) {
                const formatted = this.daily.map(d => ({
                    date:       d.date,
                    profit_abs: d.profit_abs || d.pnl || 0,
                }))
                Charts.dailyPnl('ft-daily-chart', formatted)
            }
        },

        async startBot() {
            this.actionLoading = 'start'
            try {
                await API.ftStart()
                window._app?.showToast('Freqtrade started', 'success')
                await this.load()
            } catch (e) {
                window._app?.showToast('Failed to start: ' + e.message, 'error')
            } finally {
                this.actionLoading = null
            }
        },

        async stopBot() {
            this.actionLoading = 'stop'
            try {
                await API.ftStop()
                window._app?.showToast('Freqtrade stopped', 'success')
                await this.load()
            } catch (e) {
                window._app?.showToast('Failed to stop: ' + e.message, 'error')
            } finally {
                this.actionLoading = null
            }
        },

        async forceSell(tradeId, pair) {
            const coin = (pair || '').replace('/USDT:USDT', '').replace('/USDT', '')

            const result = await TOTP.confirm(
                'Force Sell — ' + coin,
                'Enter TOTP to confirm force sell of ' + coin,
                async (code) => {
                    return await API.ftForceSell(tradeId, code)
                }
            )

            if (result.success) {
                window._app?.showToast('Force sell submitted for ' + coin, 'success')
                await this.load()
            } else if (result.reason !== 'Cancelled') {
                window._app?.showToast('Force sell failed: ' + result.reason, 'error')
            }
        },
    }
}