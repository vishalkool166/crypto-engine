function analysisPage() {
    return `<div x-data="analysisData()" x-init="init()">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Analysis</div>
                <div class="page-subtitle">Factor performance and ML model status</div>
            </div>
            <button class="btn btn-ghost btn-sm" @click="load" :disabled="loading" aria-label="Refresh analysis">
                <span x-show="loading" class="spinner" aria-hidden="true"></span>
                <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                Refresh
            </button>
        </div>

        <div class="grid-2 mb-12">
            <div class="card">
                <div class="card-title flex justify-between items-center">
                    <span>ML Model Status</span>
                    <span
                        class="badge"
                        :class="ml?.ml_enabled ? 'badge-online' : 'badge-pending'"
                        x-text="ml?.ml_enabled ? 'ACTIVE' : 'COLLECTING'"
                    ></span>
                </div>

                <div x-show="loading" x-html="Utils.loadingState()"></div>

                <template x-if="!loading">
                    <div>
                        <div class="flex justify-between items-center" style="margin-bottom:6px;margin-top:4px;">
                            <span style="font-size:12px;color:var(--text-secondary);">Training Progress</span>
                            <span style="font-size:12px;font-family:var(--font-mono);color:var(--text-primary);" x-text="(ml?.closed_trades || 0) + ' / ' + (ml?.required || 100) + ' trades'"></span>
                        </div>

                        <div id="ml-progress-chart"></div>

                        <div class="divider"></div>

                        <div class="stat-row">
                            <span class="stat-label">Status</span>
                            <span style="font-size:12px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" x-text="ml?.ml_enabled ? '✅ Active' : '⏳ Collecting data'"></span>
                        </div>

                        <template x-if="ml?.trained_at && ml.trained_at !== '--'">
                            <div class="stat-row">
                                <span class="stat-label">Trained</span>
                                <span style="font-size:12px;font-family:var(--font-mono);color:var(--text-secondary);" x-text="Utils.fmtTimeAgo(ml.trained_at)"></span>
                            </div>
                        </template>

                        <template x-if="ml?.cv_auc && ml.cv_auc !== '--'">
                            <div class="stat-row">
                                <span class="stat-label">CV AUC</span>
                                <span style="font-size:12px;font-family:var(--font-mono);color:var(--green);" x-text="ml.cv_auc"></span>
                            </div>
                        </template>

                        <template x-if="ml?.win_rate">
                            <div class="stat-row">
                                <span class="stat-label">Training WR</span>
                                <span style="font-size:12px;font-family:var(--font-mono);" :style="{color: Utils.winRateColor(ml.win_rate)}" x-text="ml.win_rate + '%'"></span>
                            </div>
                        </template>

                        <template x-if="ml?.message">
                            <div class="alert alert-info mt-12" style="font-size:12px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" x-text="ml.message"></div>
                        </template>

                        <template x-if="ml?.top_features && ml.top_features.length">
                            <div class="mt-12">
                                <div style="font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">Top Features</div>
                                <template x-for="f in ml.top_features.slice(0,5)" :key="f.feature">
                                    <div style="margin-bottom:8px;">
                                        <div class="flex justify-between" style="font-size:11px;margin-bottom:3px;">
                                            <span style="color:var(--text-secondary);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" x-text="f.feature.replace(/_/g,' ')"></span>
                                            <span style="font-family:var(--font-mono);color:var(--blue);" x-text="f.importance"></span>
                                        </div>
                                        <div class="progress-bar">
                                            <div
                                                class="progress-fill"
                                                :style="{
                                                    width: Math.min(100, (f.importance / (ml.top_features[0]?.importance || 1)) * 100) + '%',
                                                    background: 'var(--blue)'
                                                }"
                                            ></div>
                                        </div>
                                    </div>
                                </template>
                            </div>
                        </template>
                    </div>
                </template>
            </div>

            <div class="card">
                <div class="card-title">Overall Stats</div>

                <div x-show="loading" x-html="Utils.loadingState()"></div>

                <template x-if="!loading && factors">
                    <div>
                        <div class="grid-2" style="gap:8px;margin-bottom:16px;">
                            <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px;">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Total Trades</div>
                                <div style="font-size:20px;font-weight:700;font-family:var(--font-mono);" x-text="factors.total || 0"></div>
                            </div>
                            <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px;">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Overall Win Rate</div>
                                <div style="font-size:20px;font-weight:700;font-family:var(--font-mono);" :style="{color: Utils.winRateColor(factors.overall_wr)}" x-text="(factors.overall_wr || 0) + '%'"></div>
                            </div>
                            <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px;">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Wins</div>
                                <div style="font-size:20px;font-weight:700;font-family:var(--font-mono);color:var(--green);" x-text="factors.wins || 0"></div>
                            </div>
                            <div style="background:var(--bg-tertiary);border-radius:var(--radius-sm);padding:12px;">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">Losses</div>
                                <div style="font-size:20px;font-weight:700;font-family:var(--font-mono);color:var(--red);" x-text="factors.losses || 0"></div>
                            </div>
                        </div>

                        <div
                            class="alert"
                            :class="factors.reliable ? 'alert-success' : 'alert-warning'"
                            style="font-size:12px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
                            x-text="factors.reliability || '--'"
                        ></div>

                        <template x-if="factors.grade_stats && factors.grade_stats.length">
                            <div class="mt-12">
                                <div style="font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">By Grade</div>
                                <template x-for="g in factors.grade_stats" :key="g.grade">
                                    <div style="margin-bottom:10px;">
                                        <div class="flex justify-between items-center" style="margin-bottom:4px;">
                                            <div class="flex items-center gap-8">
                                                <span :class="Utils.gradeBadgeClass(g.grade)" x-text="g.grade"></span>
                                                <span style="font-size:11px;color:var(--text-secondary);" x-text="g.total + ' trades'"></span>
                                            </div>
                                            <div class="flex items-center gap-8">
                                                <span style="font-family:var(--font-mono);font-size:12px;font-weight:600;" :style="{color: Utils.winRateColor(g.win_rate)}" x-text="g.win_rate + '%'"></span>
                                                <span style="font-size:11px;color:var(--text-muted);" x-text="g.wins + 'W ' + g.losses + 'L'"></span>
                                            </div>
                                        </div>
                                        <div class="progress-bar">
                                            <div class="progress-fill" :style="{width: g.win_rate + '%', background: Utils.winRateColor(g.win_rate)}"></div>
                                        </div>
                                    </div>
                                </template>
                            </div>
                        </template>
                    </div>
                </template>

                <template x-if="!loading && !factors">
                    <div x-html="Utils.emptyState('No analysis data yet')"></div>
                </template>
            </div>
        </div>

        <div class="card mb-12">
            <div class="card-title">Factor Edge Analysis</div>
            <div style="font-size:12px;color:var(--text-secondary);margin-bottom:12px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
                Edge = win rate when factor present minus win rate when absent. Higher = more predictive.
            </div>

            <div x-show="loading" x-html="Utils.loadingState()"></div>

            <template x-if="!loading && factors && factors.table && factors.table.length">
                <div>
                    <div id="factor-bar-chart" class="mb-12"></div>

                    <div class="table-wrap" role="region" aria-label="Factor analysis table" tabindex="0">
                        <table aria-label="Factor edge analysis">
                            <thead>
                                <tr>
                                    <th scope="col">Factor</th>
                                    <th scope="col">Present WR</th>
                                    <th scope="col">Absent WR</th>
                                    <th scope="col">Edge</th>
                                    <th scope="col">Present</th>
                                    <th scope="col">Absent</th>
                                    <th scope="col">Observation</th>
                                </tr>
                            </thead>
                            <tbody>
                                <template x-for="f in factors.table" :key="f.factor">
                                    <tr>
                                        <td>
                                            <span style="font-family:var(--font-mono);font-size:12px;font-weight:600;" x-text="f.factor.replace(/_/g,' ')"></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-family:var(--font-mono);"
                                                :style="{color: f.win_rate_present != null ? Utils.winRateColor(f.win_rate_present) : 'var(--text-muted)'}"
                                                x-text="f.win_rate_present != null ? f.win_rate_present + '%' : '--'"
                                            ></span>
                                        </td>
                                        <td>
                                            <span style="font-family:var(--font-mono);color:var(--text-secondary);" x-text="f.win_rate_absent != null ? f.win_rate_absent + '%' : '--'"></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-family:var(--font-mono);font-weight:700;"
                                                :style="{color: Utils.edgeColor(f.edge)}"
                                                x-text="f.edge != null ? (f.edge >= 0 ? '+' : '') + f.edge + '%' : '--'"
                                            ></span>
                                        </td>
                                        <td><span style="font-family:var(--font-mono);color:var(--text-secondary);" x-text="f.present_total || 0"></span></td>
                                        <td><span style="font-family:var(--font-mono);color:var(--text-secondary);" x-text="f.absent_total || 0"></span></td>
                                        <td>
                                            <span
                                                style="font-size:11px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
                                                :style="{color: f.edge > 10 ? 'var(--green)' : f.edge > 0 ? 'var(--blue)' : f.edge > -10 ? 'var(--orange)' : 'var(--red)'}"
                                                x-text="f.observation || '--'"
                                            ></span>
                                        </td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>
                </div>
            </template>

            <template x-if="!loading && factors && factors.error">
                <div class="alert alert-warning" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" x-text="factors.error"></div>
            </template>

            <template x-if="!loading && (!factors || !factors.table || !factors.table.length) && !(factors && factors.error)">
                <div x-html="Utils.emptyState('No factor data yet — need closed trades with factor scores')"></div>
            </template>
        </div>

        <template x-if="!loading && factors && factors.top_factors && factors.top_factors.length">
            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="card-title" style="color:var(--green)">Top Factors — Strong Edge</div>
                    <template x-for="f in factors.top_factors" :key="f.factor">
                        <div class="stat-row">
                            <span class="stat-label" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" x-text="f.factor.replace(/_/g,' ')"></span>
                            <span style="font-family:var(--font-mono);font-weight:600;color:var(--green);" x-text="'+' + f.edge + '%'"></span>
                        </div>
                    </template>
                </div>
                <div class="card">
                    <div class="card-title" style="color:var(--orange)">Weak Factors — Review</div>
                    <template x-if="!factors.weak_factors || !factors.weak_factors.length">
                        <div style="font-size:12px;color:var(--text-muted);padding:8px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">No weak factors identified</div>
                    </template>
                    <template x-for="f in (factors.weak_factors || [])" :key="f.factor">
                        <div class="stat-row">
                            <span class="stat-label" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" x-text="f.factor.replace(/_/g,' ')"></span>
                            <span style="font-family:var(--font-mono);font-weight:600;" :style="{color: Utils.edgeColor(f.edge)}" x-text="(f.edge >= 0 ? '+' : '') + f.edge + '%'"></span>
                        </div>
                    </template>
                </div>
            </div>
        </template>

    </div>`
}

function analysisData() {
    return {
        factors: null,
        ml:      {},
        loading: false,

        async init() {
            await this.load()
            window.addEventListener('page-change', e => {
                if (e.detail.page === 'analysis') this.load()
            })
        },

        async load() {
            this.loading = true
            try {
                const [factors, health] = await Promise.all([
                    API.factorAnalysis(),
                    API.health(),
                ])
                this.factors = factors  || null
                this.ml      = health?.ml_status || {}
                this.$nextTick(() => this.renderCharts())
            } catch (e) {
                window._app?.showToast('Failed to load analysis: ' + e.message, 'error')
            } finally {
                this.loading = false
            }
        },

        renderCharts() {
            if (window._app?.page !== 'analysis') return

            const mlPct = this.ml
                ? Math.min(100, ((this.ml.closed_trades || 0) / (this.ml.required || 100)) * 100)
                : 0
            Charts.mlProgress('ml-progress-chart', mlPct)

            if (this.factors?.table?.length) {
                Charts.factorBar('factor-bar-chart', this.factors.table)
            }
        },
    }
}