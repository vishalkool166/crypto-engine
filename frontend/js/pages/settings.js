function settingsPage() {
    return `<div x-data="settingsData()" x-init="init()" @page-change.window="onPageChange($event.detail)" @dashboard-update.window="onDashboardUpdate($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Settings</div>
                <div class="page-subtitle">System configuration and server health</div>
            </div>
            <button
                class="btn btn-ghost btn-sm"
                @click="load"
                :disabled="loading"
                :aria-busy="loading"
                aria-label="Refresh settings"
            >
                <span x-show="loading" class="spinner" aria-hidden="true"></span>
                <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                Refresh
            </button>
        </div>

        <div class="grid-2 mb-12">
            <div class="card">
                <div class="section-title mb-12">Trading Mode</div>

                <div class="flex items-center gap-12" style="margin-bottom:16px;">
                    <div>
                        <div
                            style="font-size:28px;font-weight:900;letter-spacing:-1px;"
                            :style="{color: mode === 'live' ? 'var(--red)' : 'var(--blue)'}"
                        >
                            <span x-text="mode === 'live' ? '🔴 LIVE' : '🔵 PAPER'"></span>
                        </div>
                        <div
                            style="font-size:12px;color:var(--text-secondary);margin-top:4px;"
                            x-text="'Grades: ' + grades"
                        ></div>
                    </div>
                </div>

                <div
                    class="alert mb-12"
                    :class="mode === 'live' ? 'alert-error' : 'alert-info'"
                    style="font-size:12px;"
                    role="status"
                >
                    <template x-if="mode === 'live'">
                        <span>🔴 LIVE MODE — Real money at risk. All trades execute on Binance.</span>
                    </template>
                    <template x-if="mode !== 'live'">
                        <span>🔵 PAPER MODE — Simulated trading. No real money at risk.</span>
                    </template>
                </div>

                <div
                    x-show="modeMsg"
                    x-cloak
                    class="alert mb-12"
                    :class="modeOk ? 'alert-success' : 'alert-error'"
                    role="alert"
                    aria-live="assertive"
                    x-text="modeMsg"
                ></div>

                <div class="flex gap-8">
                    <button
                        class="btn btn-success"
                        @click="switchMode('paper')"
                        :disabled="!!modeLoading || mode === 'paper'"
                        :aria-busy="modeLoading === 'paper'"
                        aria-label="Switch to paper trading mode"
                    >
                        <span x-show="modeLoading === 'paper'" class="spinner" aria-hidden="true"></span>
                        Switch to Paper
                    </button>
                    <button
                        class="btn btn-danger"
                        @click="switchMode('live')"
                        :disabled="!!modeLoading || mode === 'live'"
                        :aria-busy="modeLoading === 'live'"
                        aria-label="Switch to live trading mode — real money"
                    >
                        <span x-show="modeLoading === 'live'" class="spinner" aria-hidden="true"></span>
                        Switch to Live
                    </button>
                </div>

                <div class="divider"></div>

                <div class="section-title mb-12">Quick Actions</div>

                <div class="flex gap-8" style="flex-wrap:wrap;">
                    <button
                        class="btn btn-ghost"
                        @click="triggerScan"
                        :disabled="actionLoading === 'scan'"
                        :aria-busy="actionLoading === 'scan'"
                        aria-label="Trigger market scan"
                    >
                        <span x-show="actionLoading === 'scan'" class="spinner" aria-hidden="true"></span>
                        <svg x-show="actionLoading !== 'scan'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        Trigger Scan
                    </button>

                    <button
                        class="btn btn-ghost"
                        @click="syncOutcomes"
                        :disabled="actionLoading === 'sync'"
                        :aria-busy="actionLoading === 'sync'"
                        aria-label="Sync Freqtrade outcomes"
                    >
                        <span x-show="actionLoading === 'sync'" class="spinner" aria-hidden="true"></span>
                        <svg x-show="actionLoading !== 'sync'" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                        Sync Outcomes
                    </button>
                </div>

                <div
                    x-show="actionMsg"
                    x-cloak
                    class="alert mt-12"
                    :class="actionOk ? 'alert-success' : 'alert-error'"
                    role="status"
                    aria-live="polite"
                    style="font-size:12px;"
                    x-text="actionMsg"
                ></div>
            </div>

            <div class="card">
                <div class="section-title mb-12">System Status</div>

                <template x-if="loading">
                    <div class="loading-skeleton">
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                        <div class="skeleton skeleton-row"></div>
                    </div>
                </template>

                <template x-if="!loading">
                    <div>
                        <div class="stat-row">
                            <span class="stat-label">API Status</span>
                            <span class="badge badge-online" role="status" aria-label="API online">✓ Online</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Redis</span>
                            <span
                                class="badge"
                                :class="health?.redis_connected ? 'badge-online' : 'badge-offline'"
                                role="status"
                                :aria-label="'Redis ' + (health?.redis_connected ? 'connected' : 'disconnected')"
                                x-text="health?.redis_connected ? '✓ Connected' : '✗ Disconnected'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Trading Mode</span>
                            <span
                                class="badge"
                                :class="health?.trading_mode === 'live' ? 'badge-live' : 'badge-paper'"
                                x-text="(health?.trading_mode || '--').toUpperCase()"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Coins Active</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);"
                                x-text="health?.coins_count || '--'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Min Grades</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);"
                                x-text="(health?.grades || []).join(', ') || '--'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">ML Status</span>
                            <span
                                class="badge"
                                :class="health?.ml_status?.ml_enabled ? 'badge-online' : 'badge-pending'"
                                x-text="health?.ml_status?.ml_enabled ? 'Active' : 'Collecting'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">ML Progress</span>
                            <span
                                style="font-family:var(--font-mono);font-size:12px;"
                                x-text="(health?.ml_status?.closed_trades || 0) + ' / ' + (health?.ml_status?.required || 100)"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Pending Signals</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);"
                                x-text="health?.sync_status?.pending_signals || 0"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Win Rate</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);"
                                :style="{color: Utils.winRateColor(health?.sync_status?.win_rate || 0)}"
                                x-text="(health?.sync_status?.win_rate || 0) + '%'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Last Check</span>
                            <span
                                style="font-size:11px;color:var(--text-secondary);"
                                x-text="Utils.fmtTime(health?.timestamp)"
                            ></span>
                        </div>
                    </div>
                </template>
            </div>
        </div>

        <div class="card mb-12">
            <div class="section-title mb-12">Server Performance</div>

            <template x-if="loading">
                <div class="loading-skeleton">
                    <div class="skeleton" style="height:80px;border-radius:var(--radius-sm);"></div>
                </div>
            </template>

            <template x-if="!loading && system">
                <div>
                    <div class="grid-3 mb-12" style="gap:12px;">
                        <div class="level-item" role="region" aria-label="RAM usage">
                            <div class="server-stat">
                                <div class="server-stat-header">
                                    <span class="server-stat-label">RAM Usage</span>
                                    <span
                                        class="server-stat-value"
                                        style="font-family:var(--font-mono);"
                                        :style="{color: Utils.ramColor(system.ram_pct)}"
                                        x-text="system.ram_pct + '%'"
                                    ></span>
                                </div>
                                <div class="progress-bar-thick" style="margin:6px 0;">
                                    <div
                                        class="progress-fill"
                                        :style="{width: system.ram_pct + '%', background: Utils.ramColor(system.ram_pct)}"
                                    ></div>
                                </div>
                                <div style="font-size:11px;color:var(--text-muted);">
                                    <span style="font-family:var(--font-mono);" x-text="system.ram_used_mb + 'MB'"></span>
                                    /
                                    <span style="font-family:var(--font-mono);" x-text="system.ram_total_mb + 'MB'"></span>
                                    · Free:
                                    <span style="font-family:var(--font-mono);" x-text="system.ram_available + 'MB'"></span>
                                </div>
                            </div>
                        </div>

                        <div class="level-item" role="region" aria-label="CPU usage">
                            <div class="server-stat">
                                <div class="server-stat-header">
                                    <span class="server-stat-label">CPU Usage</span>
                                    <span
                                        class="server-stat-value"
                                        style="font-family:var(--font-mono);"
                                        :style="{color: Utils.cpuColor(system.cpu_pct)}"
                                        x-text="system.cpu_pct + '%'"
                                    ></span>
                                </div>
                                <div class="progress-bar-thick" style="margin:6px 0;">
                                    <div
                                        class="progress-fill"
                                        :style="{width: Math.min(100, system.cpu_pct) + '%', background: Utils.cpuColor(system.cpu_pct)}"
                                    ></div>
                                </div>
                                <div style="font-size:11px;color:var(--text-muted);">
                                    t2.small · 1 vCPU · burstable
                                </div>
                            </div>
                        </div>

                        <div class="level-item" role="region" aria-label="Disk usage">
                            <div class="server-stat">
                                <div class="server-stat-header">
                                    <span class="server-stat-label">Disk Usage</span>
                                    <span
                                        class="server-stat-value"
                                        style="font-family:var(--font-mono);"
                                        :style="{color: Utils.diskColor(system.disk_pct)}"
                                        x-text="system.disk_pct + '%'"
                                    ></span>
                                </div>
                                <div class="progress-bar-thick" style="margin:6px 0;">
                                    <div
                                        class="progress-fill"
                                        :style="{width: system.disk_pct + '%', background: Utils.diskColor(system.disk_pct)}"
                                    ></div>
                                </div>
                                <div style="font-size:11px;color:var(--text-muted);">
                                    <span style="font-family:var(--font-mono);" x-text="system.disk_used_gb + 'GB'"></span>
                                    /
                                    <span style="font-family:var(--font-mono);" x-text="system.disk_total_gb + 'GB'"></span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="stat-row">
                        <span class="stat-label">Uptime</span>
                        <span
                            style="font-family:var(--font-mono);font-weight:700;color:var(--green);"
                            x-text="Utils.fmtUptime(system.uptime_secs)"
                        ></span>
                    </div>

                    <template x-if="system.containers && system.containers.length">
                        <div class="mt-12">
                            <div
                                style="font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;"
                            >Containers</div>
                            <template x-for="c in system.containers" :key="c.name">
                                <div
                                    class="container-row"
                                    role="listitem"
                                    :aria-label="c.name + ' container ' + c.status"
                                >
                                    <div class="flex items-center gap-8">
                                        <div
                                            class="ws-dot"
                                            :class="c.status === 'running' ? '' : 'disconnected'"
                                            aria-hidden="true"
                                        ></div>
                                        <span class="container-name" x-text="c.name"></span>
                                    </div>
                                    <div class="container-stats">
                                        <span>
                                            RAM:
                                            <span
                                                style="font-family:var(--font-mono);"
                                                :style="{color: Utils.ramColor(c.mem_pct)}"
                                                x-text="c.mem_mb + 'MB (' + c.mem_pct + '%)'"
                                            ></span>
                                        </span>
                                        <span>
                                            CPU:
                                            <span
                                                style="font-family:var(--font-mono);"
                                                :style="{color: Utils.cpuColor(c.cpu_pct)}"
                                                x-text="c.cpu_pct + '%'"
                                            ></span>
                                        </span>
                                        <span
                                            class="badge"
                                            :class="c.status === 'running' ? 'badge-online' : 'badge-offline'"
                                            x-text="c.status"
                                        ></span>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </template>

                    <template x-if="!system.containers || !system.containers.length">
                        <div class="alert alert-warning mt-12" style="font-size:12px;" role="status">
                            Container stats unavailable — Docker socket may not be mounted
                        </div>
                    </template>
                </div>
            </template>

            <template x-if="!loading && !system">
                <div x-html="Utils.emptyState('Server stats unavailable')"></div>
            </template>
        </div>

        <div class="card mb-12">
            <div class="section-title mb-12" style="color:var(--red);">Docker Maintenance</div>

            <div class="docker-purge-card" role="region" aria-label="Docker purge tool">
                <div class="flex justify-between items-center mb-12">
                    <div>
                        <div style="font-size:13px;font-weight:700;color:var(--red);">Purge Unused Docker Images</div>
                        <div style="font-size:12px;color:var(--text-secondary);margin-top:3px;">
                            Runs <span style="font-family:var(--font-mono);color:var(--text-primary);">docker system prune -f --volumes</span> on the host.
                            Requires TOTP confirmation.
                        </div>
                    </div>
                    <button
                        class="btn btn-danger"
                        @click="dockerPurge"
                        :disabled="purgeLoading"
                        :aria-busy="purgeLoading"
                        aria-label="Purge unused Docker images and volumes — requires TOTP"
                    >
                        <span x-show="purgeLoading" class="spinner" aria-hidden="true"></span>
                        <svg x-show="!purgeLoading" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                        Purge Docker
                    </button>
                </div>

                <div class="grid-3" style="gap:8px;margin-bottom:12px;">
                    <div class="level-item">
                        <div class="level-label">Disk Used</div>
                        <div
                            style="font-family:var(--font-mono);font-size:14px;font-weight:700;"
                            :style="{color: Utils.diskColor(system?.disk_pct || 0)}"
                            x-text="system ? system.disk_used_gb + 'GB' : '--'"
                        ></div>
                    </div>
                    <div class="level-item">
                        <div class="level-label">Disk Free</div>
                        <div
                            style="font-family:var(--font-mono);font-size:14px;font-weight:700;color:var(--green);"
                            x-text="system ? (system.disk_total_gb - system.disk_used_gb).toFixed(1) + 'GB' : '--'"
                        ></div>
                    </div>
                    <div class="level-item">
                        <div class="level-label">Disk Usage</div>
                        <div
                            style="font-family:var(--font-mono);font-size:14px;font-weight:700;"
                            :style="{color: Utils.diskColor(system?.disk_pct || 0)}"
                            x-text="system ? system.disk_pct + '%' : '--'"
                        ></div>
                    </div>
                </div>

                <template x-if="purgeResult">
                    <div>
                        <div
                            class="alert"
                            :class="purgeResult.success ? 'alert-success' : 'alert-error'"
                            role="status"
                            aria-live="polite"
                        >
                            <span x-text="purgeResult.message || purgeResult.reason"></span>
                            <template x-if="purgeResult.freed_mb > 0">
                                <span
                                    style="font-family:var(--font-mono);font-weight:700;margin-left:8px;"
                                    x-text="'Freed: ' + purgeResult.freed_mb + 'MB'"
                                ></span>
                            </template>
                        </div>
                        <template x-if="purgeResult.output">
                            <div
                                class="docker-purge-output"
                                role="log"
                                aria-label="Docker purge output"
                                x-text="purgeResult.output"
                            ></div>
                        </template>
                    </div>
                </template>
            </div>
        </div>

        <div class="card">
            <div class="section-title mb-12">ML Configuration</div>

            <template x-if="!loading && health">
                <div class="grid-2" style="gap:12px;">
                    <div>
                        <div class="stat-row">
                            <span class="stat-label">ML Enabled</span>
                            <span
                                class="badge"
                                :class="health?.ml_status?.ml_enabled ? 'badge-online' : 'badge-pending'"
                                x-text="health?.ml_status?.ml_enabled ? 'Yes' : 'No'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Closed Trades</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);"
                                x-text="health?.ml_status?.closed_trades || 0"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Required</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);"
                                x-text="health?.ml_status?.required || 100"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Progress</span>
                            <div style="flex:1;margin-left:12px;">
                                <div class="progress-bar-thick">
                                    <div
                                        class="progress-fill"
                                        :style="{
                                            width: Math.min(100, ((health?.ml_status?.closed_trades || 0) / (health?.ml_status?.required || 100)) * 100) + '%',
                                            background: health?.ml_status?.ml_enabled ? 'var(--green)' : 'var(--blue)'
                                        }"
                                    ></div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div>
                        <div class="stat-row">
                            <span class="stat-label">CV AUC</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);color:var(--green);"
                                x-text="health?.ml_status?.cv_auc || '--'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Win Rate</span>
                            <span
                                class="stat-value"
                                style="font-family:var(--font-mono);"
                                :style="{color: Utils.winRateColor(health?.ml_status?.win_rate || 0)}"
                                x-text="(health?.ml_status?.win_rate || 0) + '%'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Last Trained</span>
                            <span
                                style="font-size:11px;color:var(--text-secondary);"
                                x-text="health?.ml_status?.trained_at && health.ml_status.trained_at !== '--' ? Utils.fmtTimeAgo(health.ml_status.trained_at) : '--'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Message</span>
                            <span
                                style="font-size:11px;color:var(--text-secondary);max-width:200px;text-align:right;"
                                x-text="Utils.truncate(health?.ml_status?.message || '--', 50)"
                            ></span>
                        </div>
                    </div>
                </div>
            </template>
        </div>

    </div>`
}

function settingsData() {
    return {
        health:       null,
        system:       null,
        mode:         'paper',
        grades:       '--',
        loading:      false,
        modeLoading:  null,
        modeMsg:      '',
        modeOk:       false,
        actionLoading: null,
        actionMsg:    '',
        actionOk:     false,
        purgeLoading: false,
        purgeResult:  null,

        async init() {
            await this.load()
        },

        onPageChange(detail) {
            if (detail.page === 'settings') this.load()
        },

        onDashboardUpdate(data) {
            if (data?.summary?.mode) {
                this.mode = data.summary.mode
            }
        },

        async load() {
            this.loading = true
            try {
                const data  = await API.health()
                this.health = data         || null
                this.system = data?.system || null
                this.mode   = data?.trading_mode || 'paper'
                this.grades = (data?.grades || []).join(', ') || '--'
            } catch (e) {
                window._app?.showToast('Failed to load settings: ' + e.message, 'error')
            } finally {
                this.loading = false
            }
        },

        async switchMode(newMode) {
            this.modeMsg = ''

            const result = await TOTP.confirm(
                'Switch to ' + newMode.toUpperCase() + ' mode',
                newMode === 'live'
                    ? '⚠️ This enables REAL trading with real money. Enter TOTP to confirm.'
                    : 'Switch back to paper trading. Enter TOTP to confirm.',
                async (code) => {
                    return await API.modeToggle(newMode, code)
                }
            )

            if (result.success) {
                this.modeOk      = true
                this.modeMsg     = result.data?.message || 'Mode switched to ' + newMode
                this.mode        = newMode
                this.modeLoading = null
                window._app?.showToast(this.modeMsg, 'success')
                await this.load()
            } else if (result.reason !== 'Cancelled') {
                this.modeOk      = false
                this.modeMsg     = result.reason || 'Mode switch failed'
                this.modeLoading = null
                window._app?.showToast(this.modeMsg, 'error')
            }

            setTimeout(() => { this.modeMsg = '' }, 5000)
        },

        async triggerScan() {
            this.actionLoading = 'scan'
            this.actionMsg     = ''
            try {
                await API.scan()
                this.actionOk  = true
                this.actionMsg = 'Scan triggered — results in 1-2 minutes'
                window._app?.showToast(this.actionMsg, 'success')
            } catch (e) {
                this.actionOk  = false
                this.actionMsg = 'Scan failed: ' + e.message
                window._app?.showToast(this.actionMsg, 'error')
            } finally {
                this.actionLoading = null
                setTimeout(() => { this.actionMsg = '' }, 5000)
            }
        },

        async syncOutcomes() {
            this.actionLoading = 'sync'
            this.actionMsg     = ''
            try {
                const result   = await API.syncOutcomes()
                this.actionOk  = true
                this.actionMsg = `Sync complete — ${result.synced || 0} synced · ${result.unmatched || 0} unmatched`
                window._app?.showToast(this.actionMsg, 'success')
            } catch (e) {
                this.actionOk  = false
                this.actionMsg = 'Sync failed: ' + e.message
                window._app?.showToast(this.actionMsg, 'error')
            } finally {
                this.actionLoading = null
                setTimeout(() => { this.actionMsg = '' }, 5000)
            }
        },

        async dockerPurge() {
            this.purgeResult = null

            const result = await TOTP.confirm(
                'Docker System Purge',
                '⚠️ This will remove all unused Docker images, containers and volumes. Enter TOTP to confirm.',
                async (code) => {
                    return await API.dockerPurge(code)
                }
            )

            if (result.success) {
                this.purgeResult = result.data
                window._app?.showToast(
                    result.data?.message || 'Docker purge complete',
                    'success'
                )
                await this.load()
            } else if (result.reason !== 'Cancelled') {
                this.purgeResult = { success: false, reason: result.reason }
                window._app?.showToast('Purge failed: ' + result.reason, 'error')
            }
        },
    }
}