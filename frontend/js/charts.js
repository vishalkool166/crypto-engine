const Charts = {
    _instances: {},

    _defaultFont() {
        return {
            family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            size:   11,
        }
    },

    _gridColor()   { return '#2a2a3a' },
    _textColor()   { return '#7777aa' },
    _mutedColor()  { return '#55556a' },

    destroy(id) {
        if (this._instances[id]) {
            try { this._instances[id].destroy() } catch (e) {}
            delete this._instances[id]
        }
    },

    destroyAll() {
        Object.keys(this._instances).forEach(id => this.destroy(id))
    },

    equity(elId, trades = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !trades.length) return

        let equity = 0
        const labels = []
        const values = []

        trades.forEach(t => {
            equity += parseFloat(t.pnl || 0)
            labels.push(t.date || '')
            values.push(parseFloat(equity.toFixed(4)))
        })

        const isPositive = equity >= 0
        const lineColor  = isPositive ? '#00d4aa' : '#ff4466'

        const ctx = el.getContext('2d')

        const gradient = ctx.createLinearGradient(0, 0, 0, 220)
        gradient.addColorStop(0,   lineColor + '40')
        gradient.addColorStop(1,   lineColor + '00')

        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label:           'Equity',
                    data:            values,
                    borderColor:     lineColor,
                    backgroundColor: gradient,
                    borderWidth:     2,
                    pointRadius:     0,
                    pointHoverRadius: 4,
                    pointHoverBackgroundColor: lineColor,
                    fill:            true,
                    tension:         0.4,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 0 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1a24',
                        titleColor:      '#9999bb',
                        bodyColor:       '#e8e8f0',
                        borderColor:     '#2a2a3a',
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => '$' + ctx.parsed.y.toFixed(4)
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color:    this._textColor(),
                            font:     this._defaultFont(),
                            maxTicksLimit: 8,
                        },
                        grid: {
                            color:   this._gridColor(),
                            display: false,
                        },
                        border: { display: false }
                    },
                    y: {
                        ticks: {
                            color:    this._textColor(),
                            font:     this._defaultFont(),
                            callback: v => '$' + v.toFixed(2)
                        },
                        grid: {
                            color: this._gridColor(),
                        },
                        border: { display: false }
                    }
                }
            }
        })

        el.style.height = '220px'
        this._instances[elId] = chart
        return chart
    },

    gradeDonut(elId, data = {}) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el) return

        const grades  = ['A+', 'A', 'B']
        const colors  = ['#aa66ff', '#4488ff', '#ff9500']
        const values  = grades.map(g => data[g]?.total || 0)
        const hasData = values.some(v => v > 0)

        if (!hasData) return

        const ctx = el.getContext('2d')

        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels:   grades,
                datasets: [{
                    data:             values,
                    backgroundColor:  colors,
                    borderColor:      '#111118',
                    borderWidth:      3,
                    hoverBorderWidth: 3,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 300 },
                cutout:              '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color:     '#9999bb',
                            font:      this._defaultFont(),
                            padding:   12,
                            usePointStyle: true,
                            pointStyleWidth: 8,
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1a1a24',
                        titleColor:      '#9999bb',
                        bodyColor:       '#e8e8f0',
                        borderColor:     '#2a2a3a',
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => ctx.label + ': ' + ctx.parsed + ' trades'
                        }
                    }
                }
            }
        })

        el.style.height = '200px'
        this._instances[elId] = chart
        return chart
    },

    radarScores(elId, coins = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !coins.length) return

        const top    = coins.slice(0, 8)
        const labels = top.map(c => c.coin)
        const scores = top.map(c => parseFloat(c.score) || 0)
        const colors = top.map(c => {
            const s = parseFloat(c.score) || 0
            if (s >= 85) return '#aa66ff'
            if (s >= 68) return '#4488ff'
            if (s >= 52) return '#ff9500'
            if (s >= 38) return '#ffcc00'
            return '#7777aa'
        })

        const ctx = el.getContext('2d')

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'Score',
                    data:            scores,
                    backgroundColor: colors,
                    borderRadius:    4,
                    borderWidth:     0,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 0 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1a24',
                        titleColor:      '#9999bb',
                        bodyColor:       '#e8e8f0',
                        borderColor:     '#2a2a3a',
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => ctx.parsed.y + '/100'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: this._textColor(),
                            font:  this._defaultFont(),
                        },
                        grid:   { display: false },
                        border: { display: false }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        ticks: {
                            color: this._textColor(),
                            font:  this._defaultFont(),
                        },
                        grid: {
                            color: this._gridColor(),
                        },
                        border: { display: false }
                    }
                }
            }
        })

        el.style.height = '240px'
        this._instances[elId] = chart
        return chart
    },

    pnlBar(elId, history = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !history.length) return

        const recent = history.slice(-20)
        const labels = recent.map(t => t.coin || '--')
        const values = recent.map(t => parseFloat(t.pnl_raw || 0))
        const colors = values.map(v => v >= 0 ? '#00d4aa' : '#ff4466')

        const ctx = el.getContext('2d')

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'PnL',
                    data:            values,
                    backgroundColor: colors,
                    borderRadius:    3,
                    borderWidth:     0,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 0 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1a24',
                        titleColor:      '#9999bb',
                        bodyColor:       '#e8e8f0',
                        borderColor:     '#2a2a3a',
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => (ctx.parsed.y >= 0 ? '+' : '') + '$' + ctx.parsed.y.toFixed(4)
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color:    this._textColor(),
                            font:     this._defaultFont(),
                            maxRotation: 45,
                        },
                        grid:   { display: false },
                        border: { display: false }
                    },
                    y: {
                        ticks: {
                            color:    this._textColor(),
                            font:     this._defaultFont(),
                            callback: v => '$' + v.toFixed(2)
                        },
                        grid: {
                            color: this._gridColor(),
                        },
                        border: { display: false }
                    }
                }
            }
        })

        el.style.height = '180px'
        this._instances[elId] = chart
        return chart
    },

    factorBar(elId, factors = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !factors.length) return

        const sorted = [...factors]
            .filter(f => f.edge != null)
            .sort((a, b) => b.edge - a.edge)
            .slice(0, 12)

        const labels = sorted.map(f => f.factor.replace(/_/g, ' '))
        const values = sorted.map(f => parseFloat(f.edge) || 0)
        const colors = values.map(v =>
            v > 10  ? '#00d4aa' :
            v > 0   ? '#4488ff' :
            v > -10 ? '#ff9500' : '#ff4466'
        )

        const ctx = el.getContext('2d')

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'Edge %',
                    data:            values,
                    backgroundColor: colors,
                    borderRadius:    4,
                    borderWidth:     0,
                }]
            },
            options: {
                indexAxis:           'y',
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 0 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1a24',
                        titleColor:      '#9999bb',
                        bodyColor:       '#e8e8f0',
                        borderColor:     '#2a2a3a',
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => (ctx.parsed.x >= 0 ? '+' : '') + ctx.parsed.x.toFixed(1) + '% edge'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color:    this._textColor(),
                            font:     this._defaultFont(),
                            callback: v => v.toFixed(1) + '%'
                        },
                        grid: {
                            color: this._gridColor(),
                        },
                        border: { display: false }
                    },
                    y: {
                        ticks: {
                            color: this._textColor(),
                            font:  this._defaultFont(),
                        },
                        grid:   { display: false },
                        border: { display: false }
                    }
                }
            }
        })

        el.style.height = '320px'
        this._instances[elId] = chart
        return chart
    },

    dailyPnl(elId, dailyData = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !dailyData.length) return

        const labels = dailyData.map(d => d.date)
        const values = dailyData.map(d => parseFloat(d.profit_abs || 0))
        const colors = values.map(v => v >= 0 ? '#00d4aa' : '#ff4466')

        const ctx = el.getContext('2d')

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'Daily PnL',
                    data:            values,
                    backgroundColor: colors,
                    borderRadius:    3,
                    borderWidth:     0,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 0 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1a24',
                        titleColor:      '#9999bb',
                        bodyColor:       '#e8e8f0',
                        borderColor:     '#2a2a3a',
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => (ctx.parsed.y >= 0 ? '+' : '') + '$' + ctx.parsed.y.toFixed(4)
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color:       this._textColor(),
                            font:        this._defaultFont(),
                            maxRotation: 30,
                            maxTicksLimit: 10,
                        },
                        grid:   { display: false },
                        border: { display: false }
                    },
                    y: {
                        ticks: {
                            color:    this._textColor(),
                            font:     this._defaultFont(),
                            callback: v => '$' + v.toFixed(2)
                        },
                        grid: {
                            color: this._gridColor(),
                        },
                        border: { display: false }
                    }
                }
            }
        })

        el.style.height = '180px'
        this._instances[elId] = chart
        return chart
    },

    winRateGauge(elId, winRate = 0) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el) return

        const wr    = parseFloat(winRate) || 0
        const color = wr >= 55 ? '#00d4aa' : wr >= 40 ? '#ff9500' : '#ff4466'
        const ctx   = el.getContext('2d')

        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data:            [wr, 100 - wr],
                    backgroundColor: [color, '#1a1a24'],
                    borderWidth:     0,
                    circumference:   270,
                    rotation:        225,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 300 },
                cutout:              '75%',
                plugins: {
                    legend:  { display: false },
                    tooltip: { enabled: false },
                }
            },
            plugins: [{
                id: 'centerText',
                afterDraw(chart) {
                    const { ctx, chartArea: { width, height, left, top } } = chart
                    ctx.save()
                    ctx.font         = `700 24px var(--font-mono, monospace)`
                    ctx.fillStyle    = color
                    ctx.textAlign    = 'center'
                    ctx.textBaseline = 'middle'
                    ctx.fillText(wr.toFixed(1) + '%', left + width / 2, top + height / 2)
                    ctx.restore()
                }
            }]
        })

        el.style.height = '200px'
        this._instances[elId] = chart
        return chart
    },

    mlProgress(elId, pct = 0) {
        const el = document.getElementById(elId)
        if (!el) return

        const p     = Math.min(100, parseFloat(pct) || 0)
        const color = p >= 100 ? '#00d4aa' : '#4488ff'

        el.innerHTML = `
            <div style="padding:8px 0;">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                    <span style="font-size:12px;color:var(--text-secondary);">Progress</span>
                    <span style="font-family:var(--font-mono);font-size:13px;font-weight:700;color:${color};">${p.toFixed(0)}%</span>
                </div>
                <div style="height:8px;background:var(--bg-tertiary);border-radius:4px;overflow:hidden;">
                    <div style="height:100%;width:${p}%;background:${color};border-radius:4px;transition:width 0.3s ease;"></div>
                </div>
            </div>
        `
    },
}

window.Charts = Charts