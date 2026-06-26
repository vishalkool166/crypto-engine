import { h } from '/js/preact.min.js'
import { useState, useEffect } from '/js/preact-hooks.min.js'
import { html, GradeBadge, Spinner, EmptyState, LoadingSkeleton } from '/js/components.js'
import { showToast } from '/js/store.js'

export function AnalysisPage() {
    const [factors, setFactors] = useState(null)
    const [ml,      setMl]      = useState({})
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        load()
        return () => {
            Charts.destroy('factor-bar-chart')
        }
    }, [])

    useEffect(() => {
        if (!factors && !ml) return
        const mlPct = ml
            ? Math.min(100, ((ml.closed_trades || 0) / (ml.required || 100)) * 100)
            : 0
        const mlEl = document.getElementById('ml-progress-chart')
        if (mlEl) Charts.mlProgress('ml-progress-chart', mlPct)

        if (factors?.table?.length) {
            setTimeout(() => {
                const el = document.getElementById('factor-bar-chart')
                if (el && el.tagName === 'CANVAS') {
                    Charts.factorBar('factor-bar-chart', factors.table)
                }
            }, 100)
        }
    }, [factors, ml])

    async function load() {
        setLoading(true)
        try {
            const [f, health] = await Promise.all([
                API.factorAnalysis(),
                API.health(),
            ])
            setFactors(f || null)
            setMl(health?.ml_status || {})
        } catch(e) {
            showToast('Failed to load analysis: ' + e.message, 'error')
        } finally {
            setLoading(false)
        }
    }

    return html`
        <div>
            <div class="page-header flex justify-between items-center">
                <div>
                    <div class="page-title">Analysis</div>
                    <div class="page-subtitle">Factor performance and ML model status</div>
                </div>
                <button class="btn btn-ghost btn-sm" onClick=${load} disabled=${loading}>
                    ${loading ? html`<${Spinner}/>` : html`
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="23 4 23 10 17 10"/>
                            <polyline points="1 20 1 14 7 14"/>
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                        </svg>
                    `}
                    Refresh
                </button>
            </div>

            <div class="grid-2 mb-12">
                <div class="card">
                    <div class="section-header">
                        <div class="section-title">ML Model</div>
                        <span class=${'badge ' + (ml?.ml_enabled ? 'badge-online' : 'badge-pending')}>
                            ${ml?.ml_enabled ? 'ACTIVE' : 'COLLECTING'}
                        </span>
                    </div>
                    ${loading
                        ? html`<${LoadingSkeleton} rows=${3}/>`
                        : html`
                            <div>
                                <div id="ml-progress-chart"></div>
                                <div class="divider"></div>
                                <div class="stat-row">
                                    <span class="stat-label">Status</span>
                                    <span style="font-size:12px;">
                                        ${ml?.ml_enabled ? '✅ Active' : '⏳ Collecting data'}
                                    </span>
                                </div>
                                <div class="stat-row">
                                    <span class="stat-label">Progress</span>
                                    <span style="font-family:var(--font-mono);font-size:12px;">
                                        ${ml?.closed_trades || 0} / ${ml?.required || 100} trades
                                    </span>
                                </div>
                                ${ml?.trained_at && ml.trained_at !== '--' && html`
                                    <div class="stat-row">
                                        <span class="stat-label">Last Trained</span>
                                        <span style="font-size:12px;color:var(--text-secondary);">
                                            ${Utils.fmtTimeAgo(ml.trained_at)}
                                        </span>
                                    </div>
                                `}
                                ${ml?.cv_auc && ml.cv_auc !== '--' && html`
                                    <div class="stat-row">
                                        <span class="stat-label">CV AUC</span>
                                        <span style="font-family:var(--font-mono);font-weight:700;color:var(--green);">
                                            ${ml.cv_auc}
                                        </span>
                                    </div>
                                `}
                                ${ml?.win_rate && html`
                                    <div class="stat-row">
                                        <span class="stat-label">Training WR</span>
                                        <span style="font-family:var(--font-mono);font-weight:700;color:${Utils.winRateColor(ml.win_rate)};">
                                            ${ml.win_rate}%
                                        </span>
                                    </div>
                                `}
                                ${ml?.message && html`
                                    <div class="alert alert-info mt-12" style="font-size:12px;">
                                        ${ml.message}
                                    </div>
                                `}
                                ${ml?.top_features?.length && html`
                                    <div class="mt-12">
                                        <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">
                                            Top Features
                                        </div>
                                        ${ml.top_features.slice(0, 5).map(f => html`
                                            <div key=${f.feature} style="margin-bottom:10px;">
                                                <div class="flex justify-between" style="font-size:11px;margin-bottom:4px;">
                                                    <span style="color:var(--text-secondary);">
                                                        ${f.feature.replace(/_/g, ' ')}
                                                    </span>
                                                    <span style="font-family:var(--font-mono);color:var(--blue);font-weight:700;">
                                                        ${f.importance}
                                                    </span>
                                                </div>
                                                <div class="progress-bar">
                                                    <div class="progress-fill" style="width:${Math.min(100, (f.importance / (ml.top_features[0]?.importance || 1)) * 100)}%;background:var(--blue);"></div>
                                                </div>
                                            </div>
                                        `)}
                                    </div>
                                `}
                            </div>
                        `
                    }
                </div>

                <div class="card">
                    <div class="section-title mb-12">Overall Stats</div>
                    ${loading
                        ? html`<${LoadingSkeleton} rows=${4}/>`
                        : factors
                        ? html`
                            <div>
                                <div class="grid-2" style="gap:8px;margin-bottom:16px;">
                                    ${[
                                        { label: 'Total Trades',     val: factors.total || 0 },
                                        { label: 'Overall Win Rate', val: (factors.overall_wr || 0) + '%', color: Utils.winRateColor(factors.overall_wr) },
                                        { label: 'Wins',   val: factors.wins   || 0, color: 'var(--green)' },
                                        { label: 'Losses', val: factors.losses || 0, color: 'var(--red)'   },
                                    ].map(item => html`
                                        <div key=${item.label} class="level-item">
                                            <div class="level-label">${item.label}</div>
                                            <div style="font-size:22px;font-weight:800;font-family:var(--font-mono);${item.color ? 'color:' + item.color : ''}">
                                                ${item.val}
                                            </div>
                                        </div>
                                    `)}
                                </div>
                                <div class=${'alert ' + (factors.reliable ? 'alert-success' : 'alert-warning')} style="font-size:12px;">
                                    ${factors.reliability || '--'}
                                </div>
                                ${factors.grade_stats?.length && html`
                                    <div class="mt-12">
                                        <div style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">
                                            By Grade
                                        </div>
                                        ${factors.grade_stats.map(g => html`
                                            <div key=${g.grade} style="margin-bottom:12px;">
                                                <div class="flex justify-between items-center" style="margin-bottom:5px;">
                                                    <div class="flex items-center gap-8">
                                                        <${GradeBadge} grade=${g.grade}/>
                                                        <span style="font-size:11px;color:var(--text-secondary);">
                                                            ${g.total} trades
                                                        </span>
                                                    </div>
                                                    <div class="flex items-center gap-8">
                                                        <span style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:${Utils.winRateColor(g.win_rate)};">
                                                            ${g.win_rate}%
                                                        </span>
                                                        <span style="font-size:11px;color:var(--text-muted);">
                                                            ${g.wins}W ${g.losses}L
                                                        </span>
                                                    </div>
                                                </div>
                                                <div class="progress-bar">
                                                    <div class="progress-fill" style="width:${g.win_rate}%;background:${Utils.winRateColor(g.win_rate)};"></div>
                                                </div>
                                            </div>
                                        `)}
                                    </div>
                                `}
                            </div>
                        `
                        : html`<${EmptyState} message="No analysis data yet"/>`
                    }
                </div>
            </div>

            <div class="card mb-12">
                <div class="section-header">
                    <div class="section-title">Factor Edge Analysis</div>
                    ${factors?.table?.length && html`
                        <span class="tag">${factors.table.length} factors</span>
                    `}
                </div>
                <div style="font-size:12px;color:var(--text-secondary);margin-bottom:14px;">
                    Edge = win rate when factor present minus win rate when absent. Higher = more predictive.
                </div>
                ${loading
                    ? html`<${LoadingSkeleton} rows=${3}/>`
                    : factors?.table?.length
                    ? html`
                        <div>
                            <div style="position:relative;height:300px;" class="mb-12">
                                <canvas id="factor-bar-chart"></canvas>
                            </div>
                            <div class="table-wrap" style="max-height:400px;overflow-y:auto;">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Factor</th><th>Present WR</th><th>Absent WR</th>
                                            <th>Edge</th><th>Present</th><th>Absent</th><th>Observation</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${factors.table.map(f => html`
                                            <tr key=${f.factor}>
                                                <td>
                                                    <span style="font-family:var(--font-mono);font-size:11px;font-weight:700;">
                                                        ${f.factor.replace(/_/g, ' ')}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);color:${f.win_rate_present != null ? Utils.winRateColor(f.win_rate_present) : 'var(--text-muted)'};">
                                                        ${f.win_rate_present != null ? f.win_rate_present + '%' : '--'}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);color:var(--text-secondary);">
                                                        ${f.win_rate_absent != null ? f.win_rate_absent + '%' : '--'}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);font-weight:800;color:${Utils.edgeColor(f.edge)};">
                                                        ${f.edge != null ? (f.edge >= 0 ? '+' : '') + f.edge + '%' : '--'}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);color:var(--text-secondary);">
                                                        ${f.present_total || 0}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span style="font-family:var(--font-mono);color:var(--text-secondary);">
                                                        ${f.absent_total || 0}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span style="font-size:11px;color:${f.edge > 10 ? 'var(--green)' : f.edge > 0 ? 'var(--blue)' : f.edge > -10 ? 'var(--orange)' : 'var(--red)'};">
                                                        ${f.observation || '--'}
                                                    </span>
                                                </td>
                                            </tr>
                                        `)}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `
                    : factors?.error
                    ? html`<div class="alert alert-warning">${factors.error}</div>`
                    : html`<${EmptyState} message="No factor data yet — need closed trades with factor scores"/>`
                }
            </div>

            ${!loading && factors?.top_factors?.length && html`
                <div class="grid-2 mb-12">
                    <div class="card">
                        <div class="section-title mb-12" style="color:var(--green);">Top Factors — Strong Edge</div>
                        ${factors.top_factors.map(f => html`
                            <div key=${f.factor} class="stat-row">
                                <span class="stat-label" style="font-family:var(--font-mono);font-size:11px;">
                                    ${f.factor.replace(/_/g, ' ')}
                                </span>
                                <span style="font-family:var(--font-mono);font-weight:700;color:var(--green);">
                                    +${f.edge}%
                                </span>
                            </div>
                        `)}
                    </div>
                    <div class="card">
                        <div class="section-title mb-12" style="color:var(--orange);">Weak Factors — Review</div>
                        ${!factors.weak_factors?.length
                            ? html`<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No weak factors identified</div>`
                            : factors.weak_factors.map(f => html`
                                <div key=${f.factor} class="stat-row">
                                    <span class="stat-label" style="font-family:var(--font-mono);font-size:11px;">
                                        ${f.factor.replace(/_/g, ' ')}
                                    </span>
                                    <span style="font-family:var(--font-mono);font-weight:700;color:${Utils.edgeColor(f.edge)};">
                                        ${(f.edge >= 0 ? '+' : '') + f.edge}%
                                    </span>
                                </div>
                            `)
                        }
                    </div>
                </div>
            `}
        </div>
    `
}