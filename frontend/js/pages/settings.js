function settingsPage() {
    return `<div x-data="settingsData()" x-init="init()">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Settings</div>
                <div class="page-subtitle">System configuration and server health</div>
            </div>
            <button class="btn btn-ghost btn-sm" @click="load" :disabled="loading" aria-label="Refresh settings">
                <span x-show="loading" class="spinner" aria-hidden="true"></span>
                <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                Refresh
            </button>
        </div>

        <div class="grid-2 mb-12">
            <div class="card">
                <div class="card-title">Trading Mode</div>

                <div class="flex items-center gap-12" style="margin-bottom:16px;margin-top:8px;">
                    <div>
                        <div style="font-size:24px;font-weight:800;" :style="{color: mode === 'live' ? 'var(--red)' : 'var(--blue)'}">
                            <span x-text="mode === 'live' ? '🔴 LIVE' : '🔵 PAPER'"></span>
                        </div>
                        <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;" x-text="'Grades: ' + grades"></div>
                    </div>
                </div>

                <div
                    class="alert mb-12"
                    :class="mode === 'live' ? 'alert-error' : 'alert-info'"
                    style="font-size:12px;"
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
                    x-text="modeMsg"
                ></div>

                <div class="flex gap-8">
                    <button
                        class="btn btn-success"
                        @click="switchMode('paper')"
                        :disabled="modeLoading || mode === 'paper'"
                        :aria-busy="!!modeLoading"
                        aria-label="Switch to paper trading mode"
                    >
                        <span x-show="modeLoading === 'paper'" class="spinner" aria-hidden="true"></span>
                        Switch to Paper
                    </button>
                    <button
                        class="btn btn-danger"
                        @click="switchMode('live')"
                        :disabled="modeLoading || mode === 'live'"
                        :aria-busy="!!modeLoading"
                        aria-label="Switch to live trading mode"
                    >
                        <span x-show="modeLoading === 'live'" class="spinner" aria-hidden="true"></span>
                        Switch to Live
                    </button>
                </div>

                <div class="divider"></div>

                <div class="card-title">Quick Actions</div>

                <div class="flex gap-8 mt-12" style="flex-wrap:wrap;">
                    <button
                        class="btn btn-ghost"
                        @click="triggerScan"
                        :disabled="actionLoading === 'scan'"
                        :aria-busy="actionLoading === 'scan'"
                        aria-label="Trigger market scan"
                    >
                        <span x-show="actionLoading === 'scan'" class="spinner" aria-hidden="true"></span>
                        <svg x-show="actionLoading !== 'scan'" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
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
                        <svg x-show="actionLoading !== 'sync'" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
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
                <div class="card-title">System Status</div>

                <div x-show="loading" x-html="Utils.loadingState()"></div>

                <template x-if="!loading">
                    <div>
                        <div class="stat-row">
                            <span class="stat-label">API Status</span>
                            <span class="badge badge-online">✓ Online</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Redis</span>
                            <span
                                class="badge"
                                :class="health?.redis_connected ? 'badge-online' : 'badge-offline'"
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
                            <span style="font-family:var(--font-mono);font-weight:600;" x-text="health?.coins_count || '--'"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Min Grades</span>
                            <span style="font-family:var(--font-mono);font-weight:600;" x-text="(health?.grades || []).join(', ') || '--'"></span>
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
                            <span style="font-family:var(--font-mono);font-size:12px;" x-text="(health?.ml_status?.closed_trades || 0) + ' / ' + (health?.ml_status?.required || 100)"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Sync Needed</span>
                            <span
                                class="badge"
                                :class="health?.sync_status?.sync_needed ? 'badge-warning' : 'badge-online'"
                                x-text="health?.sync_status?.sync_needed ? 'Yes' : 'No'"
                            ></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Pending Signals</span>
                            <span style="font-family:var(--font-mono);font-weight:600;" x-text="health?.sync_status?.pending_signals || 0"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Total Signals</span>
                            <span style="font-family:var(--font-mono);font-weight:600;" x-text="health?.sync_status?.total_signals || 0"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Win Rate</span>
                            <span
                                style="font-family:var(--font-mono);font-weight:600;"
                                :style="{color: Utils.winRateColor(health?.sync_status?.win_rate || 0)}"
                                x-text="(health?.sync_status?.win_rate || 0) + '%'"
                            ></span>
                        </div>
                    </div>
                </template>
            </div>
        </div>

        <div class="card mb-12">
            <div class="card-title">Server Performance</div>

            <div x-show="loading" x-html="Utils.loadingState()"></div>

            <template x-if="!loading && system">
                <div>
                    <div class="grid-3 mb-12" style="gap:12px;">
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
                            <div class="progress-bar" style="margin:6px 0;">
                                <div
                                    class="progress-fill"
                                    :style="{width: system.ram_pct + '%', background: Utils.ramColor(system.ram_pct)}"
                                ></div>
                            </div>
                            <div style="font-size:11px;color:var(--text-muted);">
                                <span style="font-family:var(--font-mono);" x-text="system.ram_used_mb + 'MB'"></span>
                                <span> / </span>
                                <span style="font-family:var(--font-mono);" x-text="system.ram_total_mb + 'MB'"></span>
                                <span style="color:var(--text-muted);"> · Free: </span>
                                <span style="font-family:var(--font-mono);" x-text="system.ram_available + 'MB'"></span>
                            </div>
                        </div>

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
                            <div class="progress-bar" style="margin:6px 0;">
                                <div
                                    class="progress-fill"
                                    :style="{width: Math.min(100, system.cpu_pct) + '%', background: Utils.cpuColor(system.cpu_pct)}"
                                ></div>
                            </div>
                            <div style="font-size:11px;color:var(--text-muted);">
                                t2.small · 1 vCPU · burstable
                            </div>
                        </div>

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
                            <div class="progress-bar" style="margin:6px 0;">
                                <div
                                    class="progress-fill"
                                    :style="{width: system.disk_pct + '%', background: Utils.diskColor(system.disk_pct)}"
                                ></div>
                            </div>
                            <div style="font-size:11px;color:var(--text-muted);">
                                <span style="font-family:var(--font-mono);" x-text="system.disk_used_gb + 'GB'"></span>
                                <span> / </span>
                                <span style="font-family:var(--font-mono);" x-text="system.disk_total_gb + 'GB'"></span>
                            </div>
                        </div>
                    </div>

                    <div class="stat-row">
                        <span class="stat-label">Uptime</span>
                        <span style="font-family:var(--font-mono);font-weight:600;color:var(--green);" x-text="Utils.fmtUptime(system.uptime_secs)"></span>
                    </div>

                    <div class="stat-row">
                        <span class="stat-label">Last Health Check</span>
                        <span style="font-size:11px;color:var(--text-secondary);" x-text="Utils.fmtTime(health?.timestamp)"></span>
                    </div>

                    <template x-if="system.containers && system.containers.length">
                        <div class="mt-12">
                            <div style="font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;">Containers</div>
                            <template x-for="c in system.containers" :key="c.name">
                                <div class="container-row">
                                    <div class="flex items-center gap-8">
                                        <div
                                            class="ws-dot"
                                            :class="c.status === 'running' ? '' : 'disconnected'"
                                            :aria-label="c.name + ' ' + c.status"
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
                        <div class="alert alert-warning mt-12" style="font-size:12px;">
                            Container stats unavailable — Docker socket may not be mounted
                        </div>
                    </template>
                </div>
            </template>

            <template x-if="!loading && !system">
                <div x-html="Utils.emptyState('Server stats unavailable')"></div>
            </template>
        </div>

        <div class="card">
            <div class="card-title">ML Configuration</div>

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
                            <span style="font-family:var(--font-mono);font-weight:600;" x-text="health?.ml_status?.closed_trades || 0"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Required</span>
                            <span style="font-family:var(--font-mono);font-weight:600;" x-text="health?.ml_status?.required || 100"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Progress</span>
                            <div style="flex:1;margin-left:12px;">
                                <div class="progress-bar">
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
                            <span style="font-family:var(--font-mono);font-weight:600;color:var(--green);" x-text="health?.ml_status?.cv_auc || '--'"></span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Win Rate</span>
                            <span
                                style="font-family:var(--font-mono);font-weight:600;"
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
                            <span style="font-size:11px;color:var(--text-secondary);max-width:200px;text-align:right;" x-text="Utils.truncate(health?.ml_status?.message || '--', 50)"></span>
                        </div>
                    </div>
                </div>
            </template>
        </div>

    </div>`
}

function settingsData() {
    return {
        health:        null,
        system:        null,
        mode:          'paper',
        grades:        '--',
        loading:       false,
        modeLoading:   null,
        modeMsg:       '',
        modeOk:        false,
        actionLoading: null,
        actionMsg:     '',
        actionOk:      false,

        async init() {
            await this.load()

            window.addEventListener('page-change', e => {
                if (e.detail.page === 'settings') this.load()
            })

            window.addEventListener('dashboard-update', e => {
                const data = e.detail
                if (data?.header?.mode) {
                    this.mode = data.header.mode
                }
            })
        },

        async load() {
            this.loading = true
            try {
                const data    = await API.health()
                this.health   = data         || null
                this.system   = data?.system || null
                this.mode     = data?.trading_mode || 'paper'
                this.grades   = (data?.grades || []).join(', ') || '--'
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
                    ? '⚠️ This will enable REAL trading with real money. Enter TOTP to confirm.'
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
    }
}