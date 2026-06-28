const Charts = {
    _instances: {},

    _dark: {
        grid:    'rgba(84, 84, 88, 0.35)',
        text:    'rgba(235, 235, 245, 0.30)',
        tooltip: {
            bg:     '#2C2C2E',
            title:  'rgba(235, 235, 245, 0.30)',
            body:   '#FFFFFF',
            border: 'rgba(84, 84, 88, 0.65)',
        },
    },

    _light: {
        grid:    'rgba(60, 60, 67, 0.15)',
        text:    'rgba(60, 60, 67, 0.30)',
        tooltip: {
            bg:     '#FFFFFF',
            title:  'rgba(60, 60, 67, 0.30)',
            body:   '#000000',
            border: 'rgba(60, 60, 67, 0.29)',
        },
    },

    _theme() {
        const t = document.documentElement.getAttribute('data-theme')
        return t === 'light' ? this._light : this._dark
    },

    _font: {
        family: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', sans-serif",
        size:   11,
    },

    _baseOptions() {
        const th = this._theme()
        return {
            responsive:          true,
            maintainAspectRatio: false,
            animation:           { duration: 300, easing: 'easeOutQuart' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: th.tooltip.bg,
                    titleColor:      th.tooltip.title,
                    bodyColor:       th.tooltip.body,
                    borderColor:     th.tooltip.border,
                    borderWidth:     1,
                    padding:         10,
                    cornerRadius:    10,
                    displayColors:   false,
                    titleFont:       { ...this._font, size: 11 },
                    bodyFont:        { ...this._font, size: 13, weight: '700' },
                }
            },
            scales: {
                x: {
                    ticks: {
                        color:         th.text,
                        font:          this._font,
                        maxTicksLimit: 8,
                        maxRotation:   0,
                    },
                    grid:   { display: false },
                    border: { display: false }
                },
                y: {
                    ticks: {
                        color: th.text,
                        font:  this._font,
                    },
                    grid: {
                        color:     th.grid,
                        lineWidth: 0.5,
                    },
                    border: { display: false }
                }
            }
        }
    },

    destroy(id) {
        if (this._instances[id]) {
            try { this._instances[id].destroy() } catch(e) {}
            delete this._instances[id]
        }
    },

    destroyAll() {
        Object.keys(this._instances).forEach(id => this.destroy(id))
    },

    _getOrCreate(elId, config) {
        const el = document.getElementById(elId)
        if (!el || typeof el.getContext !== 'function') return null

        if (this._instances[elId]) {
            const chart = this._instances[elId]
            try {
                if (config.data.datasets) {
                    config.data.datasets.forEach((ds, i) => {
                        if (chart.data.datasets[i]) {
                            Object.assign(chart.data.datasets[i], ds)
                        }
                    })
                    chart.data.labels = config.data.labels
                    chart.update('none')
                    return chart
                }
            } catch(e) {
                this.destroy(elId)
            }
        }

        const ctx   = el.getContext('2d')
        const chart = new Chart(ctx, config)
        this._instances[elId] = chart
        return chart
    },

    _gradientLine(ctx, color, height = 200) {
        const gradient = ctx.createLinearGradient(0, 0, 0, height)
        gradient.addColorStop(0,   color + '28')
        gradient.addColorStop(0.6, color + '08')
        gradient.addColorStop(1,   color + '00')
        return gradient
    },

    equity(elId, curve = []) {
        const el = document.getElementById(elId)
        if (!el || !curve.length) return

        const labels = curve.map(c => c.date || '')
        const values = curve.map(c => parseFloat(c.equity || 0))
        const isUp   = values[values.length - 1] >= values[0]
        const color  = isUp ? '#34C759' : '#FF3B30'

        const ctx      = el.getContext('2d')
        const height   = el.offsetHeight || 200
        const gradient = this._gradientLine(ctx, color, height)
        const th       = this._theme()

        return this._getOrCreate(elId, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data:                      values,
                    borderColor:               color,
                    backgroundColor:           gradient,
                    borderWidth:               1.5,
                    pointRadius:               0,
                    pointHoverRadius:          4,
                    pointHoverBackgroundColor: color,
                    pointHoverBorderColor:     th.tooltip.bg,
                    pointHoverBorderWidth:     2,
                    fill:                      true,
                    tension:                   0.4,
                }]
            },
            options: {
                ...this._baseOptions(),
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            title: ctx => ctx[0].label,
                            label: ctx => {
                                const v = ctx.parsed.y
                                return (v >= 0 ? '+' : '') + '$' + Math.abs(v).toFixed(2)
                            }
                        }
                    }
                },
                scales: {
                    ...this._baseOptions().scales,
                    y: {
                        ...this._baseOptions().scales.y,
                        ticks: {
                            ...this._baseOptions().scales.y.ticks,
                            callback: v => '$' + v.toFixed(0)
                        }
                    }
                }
            }
        })
    },

    equityMini(elId, curve = []) {
        const el = document.getElementById(elId)
        if (!el || !curve.length) return

        const values = curve.map(c => parseFloat(c.equity || 0))
        const isUp   = values[values.length - 1] >= values[0]
        const color  = isUp ? '#34C759' : '#FF3B30'
        const ctx    = el.getContext('2d')
        const height = el.offsetHeight || 64
        const grad   = this._gradientLine(ctx, color, height)

        return this._getOrCreate(elId, {
            type: 'line',
            data: {
                labels:   curve.map(c => c.date || ''),
                datasets: [{
                    data:            values,
                    borderColor:     color,
                    backgroundColor: grad,
                    borderWidth:     1.5,
                    pointRadius:     0,
                    fill:            true,
                    tension:         0.4,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 200 },
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: { display: false }
                }
            }
        })
    },

    gradeDonut(elId, data = {}) {
        const el = document.getElementById(elId)
        if (!el) return

        const grades  = ['A+', 'A', 'B']
        const colors  = ['#FFCC00', '#007AFF', '#FF9500']
        const values  = grades.map(g => data[g]?.total || 0)
        const hasData = values.some(v => v > 0)
        if (!hasData) return

        const th = this._theme()

        return this._getOrCreate(elId, {
            type: 'doughnut',
            data: {
                labels:   grades,
                datasets: [{
                    data:             values,
                    backgroundColor:  colors.map(c => c + 'cc'),
                    borderColor:      colors,
                    borderWidth:      0,
                    hoverBorderWidth: 0,
                    hoverOffset:      4,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 400 },
                cutout:              '72%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color:           th.text,
                            font:            this._font,
                            padding:         16,
                            usePointStyle:   true,
                            pointStyleWidth: 8,
                        }
                    },
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => ` ${ctx.label}: ${ctx.parsed} trades`
                        }
                    }
                }
            }
        })
    },

    scoreBar(elId, coins = []) {
        const el = document.getElementById(elId)
        if (!el || !coins.length) return

        const top    = coins.slice(0, 12)
        const labels = top.map(c => c.coin)
        const scores = top.map(c => parseFloat(c.score) || 0)
        const colors = top.map(c => {
            const s = parseFloat(c.score) || 0
            if (s >= 85) return '#FFCC00'
            if (s >= 68) return '#007AFF'
            if (s >= 52) return '#FF9500'
            return 'rgba(235, 235, 245, 0.18)'
        })

        return this._getOrCreate(elId, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data:            scores,
                    backgroundColor: colors.map(c => c + 'cc'),
                    borderColor:     colors,
                    borderWidth:     0,
                    borderRadius:    6,
                    borderSkipped:   false,
                }]
            },
            options: {
                ...this._baseOptions(),
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => ` ${ctx.parsed.y}/100`
                        }
                    }
                },
                scales: {
                    ...this._baseOptions().scales,
                    y: {
                        ...this._baseOptions().scales.y,
                        min: 0,
                        max: 100,
                        ticks: {
                            ...this._baseOptions().scales.y.ticks,
                            callback: v => v
                        }
                    }
                }
            }
        })
    },

    pnlBar(elId, history = []) {
        const el = document.getElementById(elId)
        if (!el || !history.length) return

        const recent  = history.slice(-20)
        const labels  = recent.map(t => t.coin || '--')
        const values  = recent.map(t => parseFloat(t.pnl || 0))
        const colors  = values.map(v => v >= 0 ? '#34C759cc' : '#FF3B30cc')
        const borders = values.map(v => v >= 0 ? '#34C759'   : '#FF3B30')

        return this._getOrCreate(elId, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data:            values,
                    backgroundColor: colors,
                    borderColor:     borders,
                    borderWidth:     0,
                    borderRadius:    4,
                    borderSkipped:   false,
                }]
            },
            options: {
                ...this._baseOptions(),
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => {
                                const v = ctx.parsed.y
                                return (v >= 0 ? ' +$' : ' -$') + Math.abs(v).toFixed(4)
                            }
                        }
                    }
                },
                scales: {
                    ...this._baseOptions().scales,
                    x: {
                        ...this._baseOptions().scales.x,
                        ticks: {
                            ...this._baseOptions().scales.x.ticks,
                            maxRotation: 45,
                        }
                    },
                    y: {
                        ...this._baseOptions().scales.y,
                        ticks: {
                            ...this._baseOptions().scales.y.ticks,
                            callback: v => '$' + v.toFixed(2)
                        }
                    }
                }
            }
        })
    },

    factorBar(elId, factors = []) {
        const el = document.getElementById(elId)
        if (!el || !factors.length) return

        const sorted = [...factors]
            .filter(f => f.edge != null)
            .sort((a, b) => b.edge - a.edge)
            .slice(0, 12)

        const labels  = sorted.map(f => f.factor.replace(/_/g, ' '))
        const values  = sorted.map(f => parseFloat(f.edge) || 0)
        const colors  = values.map(v =>
            v > 10  ? '#34C759cc' :
            v > 0   ? '#007AFFcc' :
            v > -10 ? '#FF9500cc' : '#FF3B30cc'
        )
        const borders = values.map(v =>
            v > 10  ? '#34C759' :
            v > 0   ? '#007AFF' :
            v > -10 ? '#FF9500' : '#FF3B30'
        )

        const th = this._theme()

        return this._getOrCreate(elId, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data:            values,
                    backgroundColor: colors,
                    borderColor:     borders,
                    borderWidth:     0,
                    borderRadius:    4,
                    borderSkipped:   false,
                }]
            },
            options: {
                indexAxis:           'y',
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 400 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: th.tooltip.bg,
                        titleColor:      th.tooltip.title,
                        bodyColor:       th.tooltip.body,
                        borderColor:     th.tooltip.border,
                        borderWidth:     1,
                        cornerRadius:    10,
                        callbacks: {
                            label: ctx => {
                                const v = ctx.parsed.x
                                return (v >= 0 ? ' +' : ' ') + v.toFixed(1) + '% edge'
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color:    th.text,
                            font:     this._font,
                            callback: v => v.toFixed(0) + '%'
                        },
                        grid: {
                            color:     th.grid,
                            lineWidth: 0.5,
                        },
                        border: { display: false }
                    },
                    y: {
                        ticks: {
                            color: th.text,
                            font:  { ...this._font, size: 10 },
                        },
                        grid:   { display: false },
                        border: { display: false }
                    }
                }
            }
        })
    },

    winRateDonut(elId, wins = 0, losses = 0) {
        const el = document.getElementById(elId)
        if (!el) return

        const total = wins + losses
        if (!total) return

        const th = this._theme()

        return this._getOrCreate(elId, {
            type: 'doughnut',
            data: {
                labels:   ['Wins', 'Losses'],
                datasets: [{
                    data:             [wins, losses],
                    backgroundColor:  ['#34C759cc', '#FF3B30cc'],
                    borderColor:      ['#34C759',   '#FF3B30'],
                    borderWidth:      0,
                    hoverBorderWidth: 0,
                    hoverOffset:      4,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 400 },
                cutout:              '72%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => ` ${ctx.label}: ${ctx.parsed} (${((ctx.parsed / total) * 100).toFixed(1)}%)`
                        }
                    }
                }
            }
        })
    },

    scoreRing(elId, score, grade, size = 64) {
        const el = document.getElementById(elId)
        if (!el) return

        const radius      = (size / 2) - 5
        const circumf     = 2 * Math.PI * radius
        const pct         = Math.min(100, Math.max(0, parseFloat(score) || 0)) / 100
        const filled      = circumf * pct
        const empty       = circumf - filled
        const strokeWidth = size <= 48 ? 3 : 4

        const colorMap = {
            'A+': '#FFCC00',
            'A':  '#007AFF',
            'B':  '#FF9500',
            'C':  'rgba(235, 235, 245, 0.30)',
            'F':  'rgba(235, 235, 245, 0.18)',
        }
        const color    = colorMap[grade] || 'rgba(235, 235, 245, 0.18)'
        const fontSize = size <= 48 ? 13 : size <= 64 ? 16 : 20

        el.innerHTML = `
            <div class="score-ring" style="width:${size}px;height:${size}px;">
                <svg width="${size}" height="${size}" style="transform:rotate(-90deg);">
                    <circle
                        cx="${size/2}" cy="${size/2}" r="${radius}"
                        fill="none"
                        stroke="rgba(118,118,128,0.24)"
                        stroke-width="${strokeWidth}"
                    />
                    <circle
                        cx="${size/2}" cy="${size/2}" r="${radius}"
                        fill="none"
                        stroke="${color}"
                        stroke-width="${strokeWidth}"
                        stroke-linecap="round"
                        stroke-dasharray="${filled} ${empty}"
                        style="transition:stroke-dasharray 0.5s cubic-bezier(0.16,1,0.3,1);"
                    />
                </svg>
                <div class="score-ring-label">
                    <span class="score-ring-number" style="font-size:${fontSize}px;color:${color};">${Math.round(score)}</span>
                </div>
            </div>
        `
    },

    confidenceGauge(elId, value, size = 56) {
        const el = document.getElementById(elId)
        if (!el) return

        const radius      = (size / 2) - 5
        const circumf     = 2 * Math.PI * radius
        const pct         = Math.min(100, Math.max(0, parseFloat(value) || 0)) / 100
        const filled      = circumf * pct
        const empty       = circumf - filled
        const strokeWidth = 3.5

        const color = value >= 70 ? '#34C759' : value >= 40 ? '#007AFF' : value >= 20 ? '#FF9500' : '#FF3B30'

        el.innerHTML = `
            <div class="confidence-gauge" style="width:${size}px;height:${size}px;">
                <svg width="${size}" height="${size}" style="transform:rotate(-90deg);">
                    <circle
                        cx="${size/2}" cy="${size/2}" r="${radius}"
                        fill="none"
                        stroke="rgba(118,118,128,0.24)"
                        stroke-width="${strokeWidth}"
                        stroke-linecap="round"
                    />
                    <circle
                        cx="${size/2}" cy="${size/2}" r="${radius}"
                        fill="none"
                        stroke="${color}"
                        stroke-width="${strokeWidth}"
                        stroke-linecap="round"
                        stroke-dasharray="${filled} ${empty}"
                        style="transition:stroke-dasharray 0.5s cubic-bezier(0.16,1,0.3,1);"
                    />
                </svg>
                <div class="confidence-gauge-center">
                    <span class="confidence-gauge-value" style="font-size:14px;color:${color};">${Math.round(value)}</span>
                </div>
            </div>
        `
    },

    scanArc(elId, pct, mins, secs, scanning = false) {
        const el = document.getElementById(elId)
        if (!el) return

        const size        = 36
        const radius      = 13
        const circumf     = 2 * Math.PI * radius
        const filled      = circumf * Math.min(1, Math.max(0, pct))
        const empty       = circumf - filled
        const color       = scanning ? '#FF9500' : '#007AFF'
        const strokeWidth = 2.5

        el.innerHTML = `
            <div class="scan-arc-container" style="width:${size}px;height:${size}px;">
                <svg width="${size}" height="${size}" class="scan-arc-svg">
                    <circle
                        cx="${size/2}" cy="${size/2}" r="${radius}"
                        fill="none"
                        stroke="rgba(118,118,128,0.24)"
                        stroke-width="${strokeWidth}"
                    />
                    <circle
                        cx="${size/2}" cy="${size/2}" r="${radius}"
                        fill="none"
                        stroke="${color}"
                        stroke-width="${strokeWidth}"
                        stroke-linecap="round"
                        stroke-dasharray="${filled} ${empty}"
                        style="transition:stroke-dasharray 1s linear;"
                    />
                </svg>
                <div class="scan-arc-center">
                    <span class="scan-arc-time" style="font-size:8px;color:${color};">${mins}:${secs}</span>
                </div>
            </div>
        `
    },

    exists(elId) {
        return !!this._instances[elId]
    },

    updateData(elId, newData) {
        const chart = this._instances[elId]
        if (!chart) return false
        try {
            if (Array.isArray(newData.labels)) chart.data.labels = newData.labels
            if (Array.isArray(newData.datasets)) {
                newData.datasets.forEach((ds, i) => {
                    if (chart.data.datasets[i]) Object.assign(chart.data.datasets[i], ds)
                })
            }
            chart.update('none')
            return true
        } catch(e) { return false }
    },
}

window.Charts = Charts