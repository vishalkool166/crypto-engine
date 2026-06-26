function coinsPage() {
    return `<div x-data="coinsData()" x-init="init()" @dashboard-update.window="onUpdate($event.detail)" @page-change.window="onPageChange($event.detail)">

        <div class="page-header flex justify-between items-center">
            <div>
                <div class="page-title">Coin Universe</div>
                <div
                    class="page-subtitle"
                    aria-live="polite"
                    x-text="enabled + ' enabled · ' + total + ' total'"
                ></div>
            </div>
            <button
                class="btn btn-ghost btn-sm"
                @click="load"
                :disabled="loading"
                :aria-busy="loading"
                aria-label="Refresh coin universe"
            >
                <span x-show="loading" class="spinner" aria-hidden="true"></span>
                <svg x-show="!loading" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                Refresh
            </button>
        </div>

        <div class="card mb-12">
            <div class="section-title mb-12">Add Coin</div>
            <div class="flex gap-8" style="flex-wrap:wrap;">
                <input
                    class="input"
                    style="max-width:180px;"
                    type="text"
                    placeholder="BTC, ETH, SOL..."
                    x-model="newCoin"
                    @input="newCoin = newCoin.toUpperCase().replace(/[^A-Z0-9]/g,'')"
                    @keydown.enter="addCoin"
                    :disabled="adding"
                    aria-label="Enter coin symbol to add"
                    autocomplete="off"
                    autocapitalize="characters"
                >
                <button
                    class="btn btn-primary"
                    @click="addCoin"
                    :disabled="adding || !newCoin || newCoin.length < 2"
                    :aria-busy="adding"
                    aria-label="Add coin to universe"
                >
                    <span x-show="adding" class="spinner" aria-hidden="true"></span>
                    <svg x-show="!adding" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    Add Coin
                </button>
            </div>

            <div
                x-show="validating"
                x-cloak
                style="font-size:12px;color:var(--text-secondary);margin-top:8px;display:flex;align-items:center;gap:6px;"
                role="status"
                aria-live="polite"
            >
                <span class="spinner" style="width:12px;height:12px;" aria-hidden="true"></span>
                Validating on Binance Futures...
            </div>

            <div
                x-show="addMsg"
                x-cloak
                class="alert mt-12"
                :class="addOk ? 'alert-success' : 'alert-error'"
                role="alert"
                aria-live="assertive"
                x-text="addMsg"
            ></div>
        </div>

        <div class="card">
            <div class="filter-bar mb-12" role="search" aria-label="Coin filters">
                <select
                    class="select"
                    style="width:130px;"
                    x-model="filterStatus"
                    @change="applyFilter()"
                    aria-label="Filter by status"
                >
                    <option value="">All Coins</option>
                    <option value="enabled">Enabled Only</option>
                    <option value="disabled">Disabled Only</option>
                </select>

                <input
                    class="input"
                    style="width:130px;"
                    type="text"
                    placeholder="Search coin..."
                    x-model="search"
                    @input="applyFilter()"
                    aria-label="Search coins by symbol"
                >

                <div class="flex-1"></div>

                <span
                    style="font-size:11px;color:var(--text-secondary);"
                    aria-live="polite"
                >
                    <span
                        style="font-family:var(--font-mono);color:var(--text-primary);"
                        x-text="filtered.length"
                    ></span>
                    coins
                </span>
            </div>

            <template x-if="loading">
                <div class="loading-skeleton">
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                    <div class="skeleton skeleton-row"></div>
                </div>
            </template>

            <div x-show="!loading" class="table-wrap" role="region" aria-label="Coin universe table" tabindex="0">
                <table aria-label="Coin universe">
                    <thead>
                        <tr>
                            <th scope="col">Coin</th>
                            <th scope="col">Status</th>
                            <th scope="col">Grade</th>
                            <th scope="col">Score</th>
                            <th scope="col">Direction</th>
                            <th scope="col">Price</th>
                            <th scope="col">24h</th>
                            <th scope="col">Funding</th>
                            <th scope="col">Source</th>
                            <th scope="col">Added</th>
                            <th scope="col">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template x-if="!filtered.length">
                            <tr>
                                <td colspan="11" x-html="Utils.emptyState('No coins found')"></td>
                            </tr>
                        </template>
                        <template x-for="coin in filtered" :key="coin.coin">
                            <tr>
                                <td>
                                    <div class="flex items-center gap-6">
                                        <span
                                            style="font-family:var(--font-mono);font-weight:800;font-size:13px;"
                                            x-text="coin.coin"
                                        ></span>
                                        <span
                                            style="font-size:10px;color:var(--text-muted);"
                                        >USDT</span>
                                    </div>
                                </td>
                                <td>
                                    <span
                                        class="badge"
                                        :class="coin.enabled ? 'badge-online' : 'badge-offline'"
                                        x-text="coin.enabled ? 'ON' : 'OFF'"
                                        :aria-label="coin.coin + ' is ' + (coin.enabled ? 'enabled' : 'disabled')"
                                    ></span>
                                </td>
                                <td>
                                    <template x-if="coin.grade && coin.grade !== '--'">
                                        <span :class="Utils.gradeBadgeClass(coin.grade)" x-text="coin.grade"></span>
                                    </template>
                                    <template x-if="!coin.grade || coin.grade === '--'">
                                        <span style="color:var(--text-muted);font-size:12px;">--</span>
                                    </template>
                                </td>
                                <td>
                                    <template x-if="coin.score">
                                        <div x-html="Utils.scoreBar(coin.score)"></div>
                                    </template>
                                    <template x-if="!coin.score">
                                        <span style="color:var(--text-muted);font-size:12px;">--</span>
                                    </template>
                                </td>
                                <td>
                                    <template x-if="coin.direction && coin.direction !== '--'">
                                        <span :class="Utils.dirBadgeClass(coin.direction)" x-text="coin.direction"></span>
                                    </template>
                                    <template x-if="!coin.direction || coin.direction === '--'">
                                        <span style="color:var(--text-muted);font-size:12px;">--</span>
                                    </template>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);"
                                        x-text="coin.price || '--'"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);"
                                        :style="{color: coin.change_color}"
                                        x-text="coin.change || '--'"
                                    ></span>
                                </td>
                                <td>
                                    <span
                                        style="font-family:var(--font-mono);font-size:11px;"
                                        :style="{
                                            color: Math.abs(coin.funding || 0) > 0.05
                                                ? 'var(--red)'
                                                : Math.abs(coin.funding || 0) > 0.03
                                                ? 'var(--orange)'
                                                : 'var(--text-secondary)'
                                        }"
                                        x-text="coin.funding != null ? coin.funding.toFixed(4) + '%' : '--'"
                                    ></span>
                                </td>
                                <td>
                                    <span class="tag" x-text="coin.source || 'manual'"></span>
                                </td>
                                <td>
                                    <span
                                        style="font-size:11px;color:var(--text-secondary);"
                                        x-text="Utils.fmtTimeAgo(coin.added_at)"
                                    ></span>
                                </td>
                                <td>
                                    <div class="flex gap-6">
                                        <button
                                            class="btn btn-sm"
                                            :class="coin.enabled ? 'btn-warning' : 'btn-success'"
                                            @click="toggleCoin(coin)"
                                            :disabled="toggling === coin.coin"
                                            :aria-busy="toggling === coin.coin"
                                            :aria-label="(coin.enabled ? 'Disable' : 'Enable') + ' ' + coin.coin"
                                        >
                                            <span x-show="toggling === coin.coin" class="spinner" aria-hidden="true"></span>
                                            <span x-text="coin.enabled ? 'Disable' : 'Enable'"></span>
                                        </button>
                                        <button
                                            class="btn btn-danger btn-sm btn-icon"
                                            @click="deleteCoin(coin.coin)"
                                            :disabled="deleting === coin.coin"
                                            :aria-busy="deleting === coin.coin"
                                            :aria-label="'Delete ' + coin.coin + ' from universe'"
                                        >
                                            <span x-show="deleting === coin.coin" class="spinner" aria-hidden="true"></span>
                                            <svg x-show="deleting !== coin.coin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>
        </div>

    </div>`
}

function coinsData() {
    return {
        coins:        [],
        filtered:     [],
        newCoin:      '',
        adding:       false,
        validating:   false,
        addMsg:       '',
        addOk:        false,
        toggling:     null,
        deleting:     null,
        loading:      false,
        filterStatus: '',
        search:       '',

        get total() {
            return this.coins.length
        },

        get enabled() {
            return this.coins.filter(c => c.enabled).length
        },

        async init() {
            await this.load()
            window.addEventListener('page-change', e => {
                if (e.detail.page === 'coins') this.load()
            })
        },

        onPageChange(detail) {
            if (detail.page === 'coins') this.load()
        },

        async load() {
            this.loading = true
            try {
                this.coins = await API.coins() || []
                this.applyFilter()
            } catch (e) {
                window._app?.showToast('Failed to load coins: ' + e.message, 'error')
            } finally {
                this.loading = false
            }
        },

        onUpdate(data) {
            if (data?.universe && data.universe.length) {
                this.coins = data.universe
                this.applyFilter()
            }
        },

        applyFilter() {
            let result = [...this.coins]

            if (this.filterStatus === 'enabled') {
                result = result.filter(c => c.enabled)
            } else if (this.filterStatus === 'disabled') {
                result = result.filter(c => !c.enabled)
            }

            if (this.search) {
                const s = this.search.toUpperCase()
                result  = result.filter(c => c.coin.includes(s))
            }

            this.filtered = result
        },

        async addCoin() {
            if (!this.newCoin || this.newCoin.length < 2) return

            this.adding     = true
            this.addMsg     = ''
            this.validating = true

            try {
                const validation = await API.validateCoin(this.newCoin)
                this.validating  = false

                if (!validation.valid) {
                    this.addOk  = false
                    this.addMsg = validation.reason || 'Coin not found on Binance Futures'
                    return
                }

                const result = await API.addCoin(this.newCoin)

                if (result.success) {
                    this.addOk  = true
                    this.addMsg = result.message || this.newCoin + ' added successfully'
                    this.newCoin = ''
                    await this.load()
                    window._app?.showToast(this.addMsg, 'success')
                } else {
                    this.addOk  = false
                    this.addMsg = result.reason || 'Failed to add coin'
                }
            } catch (e) {
                this.validating = false
                this.addOk      = false
                this.addMsg     = e.message || 'Failed to add coin'
            } finally {
                this.adding     = false
                this.validating = false
                setTimeout(() => { this.addMsg = '' }, 5000)
            }
        },

        async toggleCoin(coin) {
            this.toggling = coin.coin
            try {
                await API.toggleCoin(coin.coin, !coin.enabled)
                coin.enabled = !coin.enabled
                this.applyFilter()
                window._app?.showToast(
                    coin.coin + (coin.enabled ? ' enabled' : ' disabled'),
                    'success'
                )
            } catch (e) {
                window._app?.showToast('Failed to toggle ' + coin.coin + ': ' + e.message, 'error')
            } finally {
                this.toggling = null
            }
        },

        async deleteCoin(coinName) {
            const result = await TOTP.confirm(
                'Delete ' + coinName,
                'Enter your TOTP code to permanently remove ' + coinName + ' from the universe',
                async (code) => {
                    const res = await fetch('/api/coins/' + coinName, {
                        method:      'DELETE',
                        credentials: 'include',
                    })
                    if (!res.ok) {
                        const err = await res.json().catch(() => ({}))
                        return { success: false, reason: err.detail || 'Delete failed' }
                    }
                    return { success: true }
                }
            )

            if (result.success) {
                this.coins    = this.coins.filter(c => c.coin !== coinName)
                this.applyFilter()
                window._app?.showToast(coinName + ' removed', 'success')
            } else if (result.reason !== 'Cancelled') {
                window._app?.showToast('Delete failed: ' + result.reason, 'error')
            }
        },
    }
}