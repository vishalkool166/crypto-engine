function analysisPage() {
    return `<div x-data="analysisData()" x-init="init()" @page-change.window="onPageChange($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Analysis</div>
                <div class="page-subtitle">Factor performance and ML model status</div>
            </div>
            <button
                class="btn btn-ghost btn-sm"
                @click="load"
                :disabled="loading"
                :aria-busy="loading"
                aria-label="Refresh analysis data"
            >
                <span x-show="loading" class="spinner" aria-hidden="true"></span>
                <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                Refresh
            </button>
        </div>

        <div class="grid-2 mb-12">
            <div class="card">
                <div class="section-header">
                    <div class="section-title">ML Model</div>
                    <span
                        class="badge"
                        :class="ml?.ml_enabled ? 'badge-online' : 'badge-pending'"
                        x-text="ml?.ml_enabled ? 'ACTIVE' : 'COLLECTING'"
                        role="status"
                        :aria-label="'ML status: ' + (ml?.ml_enabled ? 'Active' : 'Collecting data')"
                    ></span>
                </div>

                <template x-if="loading">
                    <div class="loading-skeleton">
                        <div class="skeleton" style="height:40px;border-radius:var(--radius-sm);"></div>
                        <div class="skeleton skeleton-row" style="margin-top:8px;"></div>
                        <div class="skeleton skeleton-row"></div>
                    </div>
                </template>

                <template x-if="!loading">
                    <div>
                        <div id="ml-progress-chart"></div>

                        <div class="divider"></div>

                        <div class="stat-row">
                            <span class="stat-label">Status</span>
                            <span
                                style="font-size:12px;"
                                x-text="ml?.ml_enabled ? '✅ Active' : '⏳ Collecting data'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Progress</span>
                            <span
                                style="font-family:var(--font-mono);font-size:12px;"
                                x-text="(ml?.closed_trades || 0) + ' / ' + (ml?.required || 100) + ' trades'"
                            ></span>
                        </div>

                        <template x-if="ml?.trained_at && ml.trained_at !== '--'">
                            <div class="stat-row">
                                <span class="stat-label">Last Trained</span>
                                <span
                                    style="font-size:12px;color:var(--text-secondary);"
                                    x-text="Utils.fmtTimeAgo(ml.trained_at)"
                                ></span>
                            </div>
                        </template>

                        <template x-if="ml?.cv_auc && ml.cv_auc !== '--'">
                            <div class="stat-row">
                                <span class="stat-label">CV AUC</span>
                                <span
                                    style="font-family:var(--font-mono);font-weight:700;color:var(--green);"
                                    x-text="ml.cv_auc"
                                ></span>
                            </div>
                        </template>

                        <template x-if="ml?.win_rate">
                            <div class="stat-row">
                                <span class="stat-label">Training WR</span>
                                <span
                                    style="font-family:var(--font-mono);font-weight:700;"
                                    :style="{color: Utils.winRateColor(ml.win_rate)}"
                                    x-text="ml.win_rate + '%'"
                                ></span>
                            </div>
                        </template>

                        <template x-if="ml?.message">
                            <div
                                class="alert alert-info mt-12"
                                style="font-size:12px;"
                                x-text="ml.message"
                            ></div>
                        </template>

                        <template x-if="ml?.top_features && ml.top_features.length">
                            <div class="mt-12">
                                <div
                                    style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;"
                                >Top Features</div>
                                <template x-for="f in ml.top_features.slice(0,5)" :key="f.feature">
                                    <div style="margin-bottom:10px;">
                                        <div
                                            class="flex justify-between"
                                            style="font-size:11px;margin-bottom:4px;"
                                        >
                                            <span
                                                style="color:var(--text-secondary);"
                                                x-text="f.feature.replace(/_/g,' ')"
                                            ></span>
                                            <span
                                                style="font-family:var(--font-mono);color:var(--blue);font-weight:700;"
                                                x-text="f.importance"
                                            ></span>
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
                <div class="section-title mb-12">Overall Stats</div>

                <template x-if="loading">
                    <div class="loading-skeleton">
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                    </div>
                </template>

                <template x-if="!loading && factors">
                    <div>
                        <div class="grid-2" style="gap:8px;margin-bottom:16px;">
                            <div class="level-item">
                                <div class="level-label">Total Trades</div>
                                <div
                                    style="font-size:22px;font-weight:800;font-family:var(--font-mono);"
                                    x-text="factors.total || 0"
                                ></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Overall Win Rate</div>
                                <div
                                    style="font-size:22px;font-weight:800;font-family:var(--font-mono);"
                                    :style="{color: Utils.winRateColor(factors.overall_wr)}"
                                    x-text="(factors.overall_wr || 0) + '%'"
                                ></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Wins</div>
                                <div
                                    style="font-size:22px;font-weight:800;font-family:var(--font-mono);color:var(--green);"
                                    x-text="factors.wins || 0"
                                ></div>
                            </div>
                            <div class="level-item">
                                <div class="level-label">Losses</div>
                                <div
                                    style="font-size:22px;font-weight:800;font-family:var(--font-mono);color:var(--red);"
                                    x-text="factors.losses || 0"
                                ></div>
                            </div>
                        </div>

                        <div
                            class="alert"
                            :class="factors.reliable ? 'alert-success' : 'alert-warning'"
                            style="font-size:12px;"
                            role="status"
                            x-text="factors.reliability || '--'"
                        ></div>

                        <template x-if="factors.grade_stats && factors.grade_stats.length">
                            <div class="mt-12">
                                <div
                                    style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;"
                                >By Grade</div>
                                <template x-for="g in factors.grade_stats" :key="g.grade">
                                    <div style="margin-bottom:12px;">
                                        <div
                                            class="flex justify-between items-center"
                                            style="margin-bottom:5px;"
                                        >
                                            <div class="flex items-center gap-8">
                                                <span :class="Utils.gradeBadgeClass(g.grade)" x-text="g.grade"></span>
                                                <span
                                                    style="font-size:11px;color:var(--text-secondary);"
                                                    x-text="g.total + ' trades'"
                                                ></span>
                                            </div>
                                            <div class="flex items-center gap-8">
                                                <span
                                                    style="font-family:var(--font-mono);font-size:12px;font-weight:700;"
                                                    :style="{color: Utils.winRateColor(g.win_rate)}"
                                                    x-text="g.win_rate + '%'"
                                                ></span>
                                                <span
                                                    style="font-size:11px;color:var(--text-muted);"
                                                    x-text="g.wins + 'W ' + g.losses + 'L'"
                                                ></span>
                                            </div>
                                        </div>
                                        <div class="progress-bar">
                                            <div
                                                class="progress-fill"
                                                :style="{width: g.win_rate + '%', background: Utils.winRateColor(g.win_rate)}"
                                            ></div>
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
            <div class="section-header">
                <div class="section-title">Factor Edge Analysis</div>
                <span
                    class="tag"
                    x-show="factors?.table?.length"
                    x-text="factors?.table?.length + ' factors'"
                ></span>
            </div>
            <div
                style="font-size:12px;color:var(--text-secondary);margin-bottom:14px;"
            >
                Edge = win rate when factor present minus win rate when absent. Higher = more predictive.
            </div>

            <template x-if="loading">
                <div class="loading-skeleton">
                    <div class="skeleton" style="height:300px;border-radius:var(--radius-sm);"></div>
                </div>
            </template>

            <template x-if="!loading && factors && factors.table && factors.table.length">
                <div>
                    <div id="factor-bar-chart" class="mb-12"></div>

                    <div
                        class="table-wrap"
                        role="region"
                        aria-label="Factor analysis table"
                        tabindex="0"
                        style="max-height:400px;overflow-y:auto;"
                    >
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
                                            <span
                                                style="font-family:var(--font-mono);font-size:11px;font-weight:700;"
                                                x-text="f.factor.replace(/_/g,' ')"
                                            ></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-family:var(--font-mono);"
                                                :style="{color: f.win_rate_present != null ? Utils.winRateColor(f.win_rate_present) : 'var(--text-muted)'}"
                                                x-text="f.win_rate_present != null ? f.win_rate_present + '%' : '--'"
                                            ></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-family:var(--font-mono);color:var(--text-secondary);"
                                                x-text="f.win_rate_absent != null ? f.win_rate_absent + '%' : '--'"
                                            ></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-family:var(--font-mono);font-weight:800;"
                                                :style="{color: Utils.edgeColor(f.edge)}"
                                                x-text="f.edge != null ? (f.edge >= 0 ? '+' : '') + f.edge + '%' : '--'"
                                            ></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-family:var(--font-mono);color:var(--text-secondary);"
                                                x-text="f.present_total || 0"
                                            ></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-family:var(--font-mono);color:var(--text-secondary);"
                                                x-text="f.absent_total || 0"
                                            ></span>
                                        </td>
                                        <td>
                                            <span
                                                style="font-size:11px;"
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
                <div
                    class="alert alert-warning"
                    role="alert"
                    x-text="factors.error"
                ></div>
            </template>

            <template x-if="!loading && (!factors || !factors.table || !factors.table.length) && !(factors && factors.error)">
                <div x-html="Utils.emptyState('No factor data yet — need closed trades with factor scores')"></div>
            </template>
        </div>

        <template x-if="!loading && factors && factors.top_factors && factors.top_factors.length">
            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="section-title mb-12" style="color:var(--green);">Top Factors — Strong Edge</div>
                    <template x-for="f in factors.top_factors" :key="f.factor">
                        <div class="stat-row">
                            <span
                                class="stat-label"
                                style="font-family:var(--font-mono);font-size:11px;"
                                x-text="f.factor.replace(/_/g,' ')"
                            ></span>
                            <span
                                style="font-family:var(--font-mono);font-weight:700;color:var(--green);"
                                x-text="'+' + f.edge + '%'"
                            ></span>
                        </div>
                    </template>
                </div>
                <div class="card">
                    <div class="section-title mb-12" style="color:var(--orange);">Weak Factors — Review</div>
                    <template x-if="!factors.weak_factors || !factors.weak_factors.length">
                        <div
                            style="font-size:12px;color:var(--text-muted);padding:8px 0;"
                        >No weak factors identified</div>
                    </template>
                    <template x-for="f in (factors.weak_factors || [])" :key="f.factor">
                        <div class="stat-row">
                            <span
                                class="stat-label"
                                style="font-family:var(--font-mono);font-size:11px;"
                                x-text="f.factor.replace(/_/g,' ')"
                            ></span>
                            <span
                                style="font-family:var(--font-mono);font-weight:700;"
                                :style="{color: Utils.edgeColor(f.edge)}"
                                x-text="(f.edge >= 0 ? '+' : '') + f.edge + '%'"
                            ></span>
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
        },

        onPageChange(detail) {
            if (detail.page === 'analysis') this.load()
        },

        async load() {
            this.loading = true
            try {
                const [factors, health] = await Promise.all([
                    API.factorAnalysis(),
                    API.health(),
                ])
                this.factors = factors || null
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