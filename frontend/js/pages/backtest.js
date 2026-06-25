function backtestPage() {
    return `<div x-data="backtestData()" x-init="init()">

        <div class="page-header">
            <div class="page-title">Backtest</div>
            <div class="page-subtitle">Historical signal simulation on stored candle data</div>
        </div>

        <div class="card mb-12">
            <div class="card-title">Run Backtest</div>
            <div class="flex gap-8 mt-12" style="flex-wrap:wrap;">
                <select class="select" style="width:160px;" x-model="selectedCoin">
                    <option value="">Select Coin</option>
                    <template x-for="c in coins" :key="c">
                        <option :value="c" x-text="c + 'USDT'"></option>
                    </template>
                </select>

                <button
                    class="btn btn-primary"
                    @click="runBacktest"
                    :disabled="running || !selectedCoin"
                >
                    <span x-show="running" class="spinner"></span>
                    <svg x-show="!running" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                    <span x-text="running ? 'Running... (up to 2 min)' : 'Run Backtest'"></span>
                </button>

                <button
                    class="btn btn-ghost btn-sm"
                    @click="loadHistory"
                    :disabled="historyLoading"
                >
                    <span x-show="historyLoading" class="spinner"></span>
                    Load History
                </button>
            </div>

            <div x-show="running" x-cloak class="alert alert-info mt-12">
                ⏳ Running backtest for <span class="mono" x-text="selectedCoin + 'USDT'"></span> — this may take up to 2 minutes...
            </div>

            <div x-show="error" x-cloak class="alert alert-error mt-12" x-text="error"></div>
        </div>

        <template x-if="result">
            <div>
                <div class="grid-4 mb-12">
                    <div class="card">
                        <div class="card-title">Win Rate</div>
                        <div class="card-value mono" :style="{color: Utils.winRateColor(result.win_rate)}" x-text="result.win_rate + '%'"></div>
                        <div class="card-sub" x-text="result.wins + 'W · ' + result.losses + 'L · ' + result.total_trades + ' trades'"></div>
                    </div>
                    <div class="card">
                        <div class="card-title">Total PnL</div>
                        <div class="card-value mono" :style="{color: Utils.pnlColor(result.total_pnl)}" x-text="Utils.fmtPnl(result.total_pnl)"></div>
                        <div class="card-sub" x-text="'Return: ' + result.total_return + '%'"></div>
                    </div>
                    <div class="card">
                        <div class="card-title">Max Drawdown</div>
                        <div class="card-value mono" style="color:var(--red)" x-text="result.max_drawdown + '%'"></div>
                        <div class="card-sub" x-text="'Profit Factor: ' + result.profit_factor"></div>
                    </div>
                    <div class="card">
                        <div class="card-title">Signals</div>
                        <div class="card-value mono" style="color:var(--blue)" x-text="result.total_signals"></div>
                        <div class="card-sub" x-text="'A+: ' + result.aplus_signals + ' · A: ' + result.a_signals"></div>
                    </div>
                </div>

                <div class="grid-2 mb-12">
                    <div class="card">
                        <div class="card-title">Equity Curve</div>
                        <div id="bt-equity-chart"></div>
                    </div>

                    <div class="card">
                        <div class="card-title">By Grade</div>

                        <div id="bt-grade-donut" class="mb-12"></div>

                        <template x-for="[grade, data] in Object.entries(result.by_grade || {})" :key="grade">
                            <div style="margin-bottom:12px;">
                                <div class="flex justify-between items-center mb-12" style="margin-bottom:6px;">
                                    <div class="flex items-center gap-8">
                                        <span :class="Utils.gradeBadgeClass(grade)" x-text="grade"></span>
                                        <span style="font-size:12px;color:var(--text-secondary);" x-text="data.trades + ' trades'"></span>
                                    </div>
                                    <div class="flex items-center gap-8">
                                        <span class="mono" style="font-size:12px;font-weight:600;" :style="{color: Utils.winRateColor(data.win_rate)}" x-text="data.win_rate + '%'"></span>
                                        <span class="mono" style="font-size:11px;" :style="{color: Utils.pnlColor(data.pnl)}" x-text="Utils.fmtPnl(data.pnl)"></span>
                                    </div>
                                </div>
                                <div class="progress-bar">
                                    <div
                                        class="progress-fill"
                                        :style="{width: data.win_rate + '%', background: Utils.winRateColor(data.win_rate)}"
                                    ></div>
                                </div>
                            </div>
                        </template>

                        <div class="divider"></div>

                        <div class="stat-row">
                            <span class="stat-label">Period</span>
                            <span class="stat-value mono" style="font-size:11px;" x-text="result.period_start + ' → ' + result.period_end"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Best Trade</span>
                            <span class="stat-value mono" style="color:var(--green)" x-text="Utils.fmtPnl(result.best_trade)"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Worst Trade</span>
                            <span class="stat-value mono" style="color:var(--red)" x-text="Utils.fmtPnl(result.worst_trade)"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Avg Trade</span>
                            <span class="stat-value mono" :style="{color: Utils.pnlColor(result.avg_trade)}" x-text="Utils.fmtPnl(result.avg_trade)"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Expectancy</span>
                            <span class="stat-value mono" :style="{color: Utils.pnlColor(result.expectancy)}" x-text="Utils.fmtPnl(result.expectancy)"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Max Consec Wins</span>
                            <span class="stat-value mono" style="color:var(--green)" x-text="result.max_consec_wins || '--'"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Max Consec Losses</span>
                            <span class="stat-value mono" style="color:var(--red)" x-text="result.max_consec_losses || '--'"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">TP1 Hit Rate</span>
                            <span class="stat-value mono" x-text="result.phase_breakdown?.tp1_hit_rate + '%' || '--'"></span>
                        </div>
                    </div>
                </div>

                <div class="card mb-12">
                    <div class="card-title">Trade Log</div>
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Dir</th>
                                    <th>Grade</th>
                                    <th>Score</th>
                                    <th>Entry</th>
                                    <th>Exit</th>
                                    <th>PnL</th>
                                    <th>Outcome</th>
                                    <th>Reason</th>
                                    <th>Candles</th>
                                    <th>Regime</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template x-if="!paginatedTrades.length">
                                    <tr><td colspan="11" x-html="Utils.emptyState('No trades')"></td></tr>
                                </template>
                                <template x-for="(t, i) in paginatedTrades" :key="i">
                                    <tr>
                                        <td><span class="mono" style="font-size:11px;" x-text="t.date"></span></td>
                                        <td><span :class="Utils.dirBadgeClass(t.direction)" x-text="t.direction"></span></td>
                                        <td><span :class="Utils.gradeBadgeClass(t.grade)" x-text="t.grade"></span></td>
                                        <td x-html="Utils.scoreBar(t.score)"></td>
                                        <td><span class="mono" x-text="Utils.fmtPrice(t.entry)"></span></td>
                                        <td><span class="mono" x-text="Utils.fmtPrice(t.exit_price)"></span></td>
                                        <td><span class="mono" style="font-weight:600;" :style="{color: Utils.pnlColor(t.pnl)}" x-text="Utils.fmtPnl(t.pnl)"></span></td>
                                        <td><span :class="Utils.outcomeBadgeClass(t.outcome)" x-text="t.outcome"></span></td>
                                        <td><span style="font-size:11px;color:var(--text-muted)" x-text="t.reason || '--'"></span></td>
                                        <td><span class="mono" style="font-size:11px;" x-text="t.candles || '--'"></span></td>
                                        <td><span style="font-size:11px;color:var(--text-secondary)" x-text="t.regime || '--'"></span></td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>

                    <div class="flex justify-between items-center mt-12" style="font-size:12px;color:var(--text-secondary);">
                        <span x-text="'Page ' + tradePage + ' of ' + totalTradePages"></span>
                        <div class="flex gap-8">
                            <button class="btn btn-ghost btn-sm" @click="tradePage--" :disabled="tradePage <= 1">Prev</button>
                            <button class="btn btn-ghost btn-sm" @click="tradePage++" :disabled="tradePage >= totalTradePages">Next</button>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template x-if="history.length && !result">
            <div class="card">
                <div class="card-title">Backtest History</div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Coin</th>
                                <th>Run At</th>
                                <th>Period</th>
                                <th>Trades</th>
                                <th>Win Rate</th>
                                <th>PnL</th>
                                <th>Max DD</th>
                                <th>Notes</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template x-for="h in history" :key="h.id">
                                <tr>
                                    <td><span class="mono" style="font-weight:700;" x-text="h.coin"></span></td>
                                    <td><span style="font-size:11px;color:var(--text-secondary)" x-text="Utils.fmtTimeAgo(h.run_at)"></span></td>
                                    <td><span style="font-size:11px;color:var(--text-secondary)" x-text="h.period_start + ' → ' + h.period_end"></span></td>
                                    <td><span class="mono" x-text="h.total_trades"></span></td>
                                    <td><span class="mono" :style="{color: Utils.winRateColor(h.win_rate)}" x-text="h.win_rate + '%'"></span></td>
                                    <td><span class="mono" :style="{color: Utils.pnlColor(h.total_pnl)}" x-text="Utils.fmtPnl(h.total_pnl)"></span></td>
                                    <td><span class="mono" style="color:var(--red)" x-text="h.max_drawdown + '%'"></span></td>
                                    <td><span style="font-size:11px;color:var(--text-muted)" x-text="Utils.truncate(h.notes, 50)"></span></td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>
        </template>

    </div>`
}

function backtestData() {
    return {
        coins:          [],
        selectedCoin:   '',
        result:         null,
        history:        [],
        running:        false,
        historyLoading: false,
        error:          '',
        tradePage:      1,
        tradePageSize:  20,

        get paginatedTrades() {
            if (!this.result?.trades) return []
            const start = (this.tradePage - 1) * this.tradePageSize
            return this.result.trades.slice(start, start + this.tradePageSize)
        },

        get totalTradePages() {
            if (!this.result?.trades) return 1
            return Math.max(1, Math.ceil(this.result.trades.length / this.tradePageSize))
        },

        async init() {
            await this.loadCoins()
            await this.loadHistory()
            window.addEventListener('page-change', e => {
                if (e.detail.page === 'backtest') this.loadCoins()
            })
        },

        async loadCoins() {
            try {
                const data   = await API.coins()
                this.coins   = (data || []).filter(c => c.enabled).map(c => c.coin)
                if (this.coins.length && !this.selectedCoin) {
                    this.selectedCoin = this.coins[0]
                }
            } catch (e) {}
        },

        async loadHistory() {
            this.historyLoading = true
            try {
                this.history = await API.backtestHistory() || []
            } catch (e) {} finally {
                this.historyLoading = false
            }
        },

        async runBacktest() {
            if (!this.selectedCoin) return
            this.running   = true
            this.error     = ''
            this.result    = null
            this.tradePage = 1

            Charts.destroy('bt-equity-chart')
            Charts.destroy('bt-grade-donut')

            try {
                const data = await API.backtest(this.selectedCoin)
                this.result = data
                this.$nextTick(() => this.renderCharts())
                window._app?.showToast('Backtest complete — ' + data.total_trades + ' trades', 'success')
            } catch (e) {
                this.error = e.message || 'Backtest failed'
                window._app?.showToast('Backtest failed: ' + e.message, 'error')
            } finally {
                this.running = false
            }
        },

        renderCharts() {
            if (window._app?.page !== 'backtest' || !this.result) return

            if (this.result.trades?.length) {
                Charts.equity('bt-equity-chart', this.result.trades)
            }

            if (this.result.by_grade) {
                Charts.gradeDonut('bt-grade-donut', this.result.by_grade)
            }
        },
    }
}