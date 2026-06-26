const Charts = {
    _instances: {},

    _theme: {
        grid:    '#1e1e30',
        text:    '#6e6e99',
        tooltip: {
            bg:     '#111120',
            title:  '#9999cc',
            body:   '#f0f0ff',
            border: '#1e1e30',
        },
        font: {
            family: "-apple-system, BlinkMacSystemFont, 'Inter', sans-serif",
            size:   11,
        },
    },

    _baseOptions(height = 200) {
        return {
            responsive:          true,
            maintainAspectRatio: false,
            animation:           { duration: 400, easing: 'easeOutQuart' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: this._theme.tooltip.bg,
                    titleColor:      this._theme.tooltip.title,
                    bodyColor:       this._theme.tooltip.body,
                    borderColor:     this._theme.tooltip.border,
                    borderWidth:     1,
                    padding:         10,
                    cornerRadius:    6,
                    displayColors:   false,
                }
            },
            scales: {
                x: {
                    ticks: {
                        color:         this._theme.text,
                        font:          this._theme.font,
                        maxTicksLimit: 8,
                        maxRotation:   0,
                    },
                    grid:   { display: false },
                    border: { display: false }
                },
                y: {
                    ticks: {
                        color: this._theme.text,
                        font:  this._theme.font,
                    },
                    grid: {
                        color:     this._theme.grid,
                        lineWidth: 1,
                    },
                    border: { display: false }
                }
            }
        }
    },

    destroy(id) {
        if (this._instances[id]) {
            try { this._instances[id].destroy() } catch (e) {}
            delete this._instances[id]
        }
    },

    destroyAll() {
        Object.keys(this._instances).forEach(id => this.destroy(id))
    },

    _getOrCreate(elId, config) {
        const el = document.getElementById(elId)
        if (!el) return null
        if (typeof el.getContext !== 'function') return null

        if (this._instances[elId]) {
            const chart = this._instances[elId]
            try {
                if (config.data.datasets) {
                    config.data.datasets.forEach((ds, i) => {
                        if (chart.data.datasets[i]) {
                            chart.data.datasets[i].data            = ds.data
                            chart.data.datasets[i].backgroundColor = ds.backgroundColor || chart.data.datasets[i].backgroundColor
                            chart.data.datasets[i].borderColor     = ds.borderColor     || chart.data.datasets[i].borderColor
                        }
                    })
                    chart.data.labels = config.data.labels
                    chart.update('none')
                    return chart
                }
            } catch (e) {
                this.destroy(elId)
            }
        }

        const ctx   = el.getContext('2d')
        const chart = new Chart(ctx, config)
        this._instances[elId] = chart
        return chart
    },

    equity(elId, trades = []) {
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

        const lineColor = '#3d8bff'
        const ctx       = el.getContext('2d')

        const gradient = ctx.createLinearGradient(0, 0, 0, 220)
        gradient.addColorStop(0,   lineColor + '30')
        gradient.addColorStop(0.7, lineColor + '08')
        gradient.addColorStop(1,   lineColor + '00')

        return this._getOrCreate(elId, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label:                'Equity',
                    data:                 values,
                    borderColor:          lineColor,
                    backgroundColor:      gradient,
                    borderWidth:          2,
                    pointRadius:          0,
                    pointHoverRadius:     4,
                    pointHoverBackgroundColor: lineColor,
                    fill:                 true,
                    tension:              0.4,
                }]
            },
            options: {
                ...this._baseOptions(220),
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => (ctx.parsed.y >= 0 ? '+' : '') + '$' + ctx.parsed.y.toFixed(4)
                        }
                    }
                },
                scales: {
                    ...this._baseOptions().scales,
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

    equityFromCurve(elId, curve = []) {
        const el = document.getElementById(elId)
        if (!el || !curve.length) return

        const labels    = curve.map(c => c.date || '')
        const values    = curve.map(c => parseFloat(c.equity || 0))
        const lineColor = '#3d8bff'
        const ctx       = el.getContext('2d')

        const gradient = ctx.createLinearGradient(0, 0, 0, 200)
        gradient.addColorStop(0,   lineColor + '25')
        gradient.addColorStop(0.6, lineColor + '08')
        gradient.addColorStop(1,   lineColor + '00')

        return this._getOrCreate(elId, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data:                 values,
                    borderColor:          lineColor,
                    backgroundColor:      gradient,
                    borderWidth:          2,
                    pointRadius:          0,
                    pointHoverRadius:     4,
                    pointHoverBackgroundColor: lineColor,
                    fill:                 true,
                    tension:              0.4,
                }]
            },
            options: {
                ...this._baseOptions(200),
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => (ctx.parsed.y >= 0 ? '+' : '') + '$' + ctx.parsed.y.toFixed(4)
                        }
                    }
                },
                scales: {
                    ...this._baseOptions().scales,
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

    gradeDonut(elId, data = {}) {
        const el = document.getElementById(elId)
        if (!el) return

        const grades  = ['A+', 'A', 'B']
        const colors  = ['#f59e0b', '#3d8bff', '#ff9500']
        const values  = grades.map(g => data[g]?.total || 0)
        const hasData = values.some(v => v > 0)

        if (!hasData) return

        return this._getOrCreate(elId, {
            type: 'doughnut',
            data: {
                labels:   grades,
                datasets: [{
                    data:             values,
                    backgroundColor:  colors.map(c => c + 'cc'),
                    borderColor:      colors,
                    borderWidth:      2,
                    hoverBorderWidth: 3,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 400 },
                cutout:              '68%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color:           '#9999cc',
                            font:            this._theme.font,
                            padding:         12,
                            usePointStyle:   true,
                            pointStyleWidth: 8,
                        }
                    },
                    tooltip: {
                        backgroundColor: this._theme.tooltip.bg,
                        titleColor:      this._theme.tooltip.title,
                        bodyColor:       this._theme.tooltip.body,
                        borderColor:     this._theme.tooltip.border,
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => ctx.label + ': ' + ctx.parsed + ' trades'
                        }
                    }
                }
            }
        })
    },

    radarScores(elId, coins = []) {
        const el = document.getElementById(elId)
        if (!el || !coins.length) return

        const top    = coins.slice(0, 10)
        const labels = top.map(c => c.coin)
        const scores = top.map(c => parseFloat(c.score) || 0)
        const colors = top.map(c => {
            const s = parseFloat(c.score) || 0
            if (s >= 85) return '#f59e0b'
            if (s >= 68) return '#3d8bff'
            if (s >= 52) return '#ff9500'
            if (s >= 38) return '#fbbf24'
            return '#6e6e99'
        })

        return this._getOrCreate(elId, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'Score',
                    data:            scores,
                    backgroundColor: colors.map(c => c + 'cc'),
                    borderColor:     colors,
                    borderWidth:     1,
                    borderRadius:    4,
                }]
            },
            options: {
                ...this._baseOptions(220),
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => ctx.parsed.y + '/100'
                        }
                    }
                },
                scales: {
                    ...this._baseOptions().scales,
                    y: {
                        ...this._baseOptions().scales.y,
                        min: 0,
                        max: 100,
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
        const values  = recent.map(t => parseFloat(t.pnl_raw || 0))
        const colors  = values.map(v => v >= 0 ? '#00e5b8cc' : '#ff3d5acc')
        const borders = values.map(v => v >= 0 ? '#00e5b8' : '#ff3d5a')

        return this._getOrCreate(elId, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'PnL',
                    data:            values,
                    backgroundColor: colors,
                    borderColor:     borders,
                    borderWidth:     1,
                    borderRadius:    3,
                }]
            },
            options: {
                ...this._baseOptions(160),
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => (ctx.parsed.y >= 0 ? '+' : '') + '$' + ctx.parsed.y.toFixed(4)
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
            v > 10  ? '#00e5b8cc' :
            v > 0   ? '#3d8bffcc' :
            v > -10 ? '#ff9500cc' : '#ff3d5acc'
        )
        const borders = values.map(v =>
            v > 10  ? '#00e5b8' :
            v > 0   ? '#3d8bff' :
            v > -10 ? '#ff9500' : '#ff3d5a'
        )

        return this._getOrCreate(elId, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'Edge %',
                    data:            values,
                    backgroundColor: colors,
                    borderColor:     borders,
                    borderWidth:     1,
                    borderRadius:    3,
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
                        backgroundColor: this._theme.tooltip.bg,
                        titleColor:      this._theme.tooltip.title,
                        bodyColor:       this._theme.tooltip.body,
                        borderColor:     this._theme.tooltip.border,
                        borderWidth:     1,
                        callbacks: {
                            label: ctx => (ctx.parsed.x >= 0 ? '+' : '') + ctx.parsed.x.toFixed(1) + '% edge'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color:    this._theme.text,
                            font:     this._theme.font,
                            callback: v => v.toFixed(1) + '%'
                        },
                        grid: {
                            color:     this._theme.grid,
                            lineWidth: 1,
                        },
                        border: { display: false }
                    },
                    y: {
                        ticks: {
                            color: this._theme.text,
                            font:  { ...this._theme.font, size: 10 },
                        },
                        grid:   { display: false },
                        border: { display: false }
                    }
                }
            }
        })
    },

    dailyPnl(elId, dailyData = []) {
        const el = document.getElementById(elId)
        if (!el || !dailyData.length) return

        const labels  = dailyData.map(d => d.date)
        const values  = dailyData.map(d => parseFloat(d.profit_abs || 0))
        const colors  = values.map(v => v >= 0 ? '#00e5b8cc' : '#ff3d5acc')
        const borders = values.map(v => v >= 0 ? '#00e5b8' : '#ff3d5a')

        return this._getOrCreate(elId, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'Daily PnL',
                    data:            values,
                    backgroundColor: colors,
                    borderColor:     borders,
                    borderWidth:     1,
                    borderRadius:    3,
                }]
            },
            options: {
                ...this._baseOptions(160),
                plugins: {
                    ...this._baseOptions().plugins,
                    tooltip: {
                        ...this._baseOptions().plugins.tooltip,
                        callbacks: {
                            label: ctx => (ctx.parsed.y >= 0 ? '+' : '') + '$' + ctx.parsed.y.toFixed(4)
                        }
                    }
                },
                scales: {
                    ...this._baseOptions().scales,
                    x: {
                        ...this._baseOptions().scales.x,
                        ticks: {
                            ...this._baseOptions().scales.x.ticks,
                            maxTicksLimit: 10,
                            maxRotation:   30,
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

    mlProgress(elId, pct = 0) {
        const el = document.getElementById(elId)
        if (!el) return

        const p     = Math.min(100, parseFloat(pct) || 0)
        const color = p >= 100 ? '#00e5b8' : '#3d8bff'

        el.innerHTML = `
            <div style="padding:4px 0;">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:11px;">
                    <span style="color:var(--text-secondary);">Training Progress</span>
                    <span style="font-family:var(--font-mono);font-weight:700;color:${color};">${p.toFixed(0)}%</span>
                </div>
                <div style="height:6px;background:var(--bg-tertiary);border-radius:3px;overflow:hidden;">
                    <div style="height:100%;width:${p}%;background:${color};border-radius:3px;transition:width 0.5s ease;"></div>
                </div>
            </div>
        `
    },

    updateData(elId, newData) {
        const chart = this._instances[elId]
        if (!chart) return false
        try {
            if (Array.isArray(newData.labels)) {
                chart.data.labels = newData.labels
            }
            if (Array.isArray(newData.datasets)) {
                newData.datasets.forEach((ds, i) => {
                    if (chart.data.datasets[i]) {
                        Object.assign(chart.data.datasets[i], ds)
                    }
                })
            }
            chart.update('none')
            return true
        } catch (e) {
            return false
        }
    },

    exists(elId) {
        return !!this._instances[elId]
    },
}

window.Charts = Charts