const Charts = {
    _instances: {},

    _baseOptions() {
        return {
            chart: {
                background:  'transparent',
                foreColor:   '#8888aa',
                fontFamily:  '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
                toolbar:     { show: false },
                animations:  { enabled: false },
                sparkline:   { enabled: false },
            },
            grid: {
                borderColor: '#2a2a3a',
                strokeDashArray: 3,
                xaxis: { lines: { show: false } },
                yaxis: { lines: { show: true  } },
                padding: { left: 8, right: 8 },
            },
            tooltip: {
                theme:  'dark',
                style:  { fontSize: '12px' },
                x:      { show: true },
            },
            legend: {
                labels: { colors: '#8888aa' },
                fontSize: '12px',
            },
            dataLabels: { enabled: false },
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

    equity(elId, trades = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !trades.length) return

        let equity = 0
        const series = trades.map(t => {
            equity += parseFloat(t.pnl || 0)
            return { x: new Date(t.date).getTime(), y: parseFloat(equity.toFixed(4)) }
        })

        const isPositive = equity >= 0
        const lineColor  = isPositive ? '#00d4aa' : '#ff4466'

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'area',
                height: 220,
            },
            series: [{ name: 'Equity', data: series }],
            stroke: { curve: 'smooth', width: 2, colors: [lineColor] },
            fill: {
                type:     'gradient',
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom:    0.3,
                    opacityTo:      0.0,
                    stops:          [0, 100],
                    colorStops: [{
                        offset:  0,
                        color:   lineColor,
                        opacity: 0.3,
                    }, {
                        offset:  100,
                        color:   lineColor,
                        opacity: 0,
                    }],
                },
            },
            xaxis: {
                type: 'datetime',
                labels: {
                    style:      { colors: '#55556a', fontSize: '11px' },
                    datetimeUTC: false,
                },
                axisBorder: { show: false },
                axisTicks:  { show: false },
            },
            yaxis: {
                labels: {
                    style:     { colors: '#55556a', fontSize: '11px' },
                    formatter: v => '$' + v.toFixed(2),
                },
            },
            tooltip: {
                ...this._baseOptions().tooltip,
                x: { format: 'dd MMM yyyy' },
                y: { formatter: v => '$' + v.toFixed(4) },
            },
            colors: [lineColor],
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
        this._instances[elId] = chart
        return chart
    },

    gradeDonut(elId, data = {}) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el) return

        const grades  = ['A+', 'A', 'B']
        const colors  = ['#aa66ff', '#4488ff', '#ff9500']
        const series  = grades.map(g => data[g]?.total || 0)
        const hasData = series.some(v => v > 0)

        if (!hasData) return

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'donut',
                height: 200,
            },
            series,
            labels:  grades,
            colors,
            plotOptions: {
                pie: {
                    donut: {
                        size: '65%',
                        labels: {
                            show: true,
                            total: {
                                show:      true,
                                label:     'Trades',
                                color:     '#8888aa',
                                fontSize:  '12px',
                                formatter: w => w.globals.seriesTotals.reduce((a, b) => a + b, 0),
                            },
                        },
                    },
                },
            },
            legend: {
                position: 'bottom',
                labels:   { colors: '#8888aa' },
                fontSize: '12px',
            },
            tooltip: {
                ...this._baseOptions().tooltip,
                y: { formatter: v => v + ' trades' },
            },
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
        this._instances[elId] = chart
        return chart
    },

    radarScores(elId, coins = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !coins.length) return

        const top     = coins.slice(0, 8)
        const labels  = top.map(c => c.coin)
        const scores  = top.map(c => parseFloat(c.score) || 0)
        const colors  = top.map(c => Utils.scoreBarColor(c.score))

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'bar',
                height: 240,
            },
            series: [{ name: 'Score', data: scores }],
            xaxis: {
                categories: labels,
                labels: {
                    style: { colors: '#8888aa', fontSize: '11px' },
                },
                axisBorder: { show: false },
                axisTicks:  { show: false },
            },
            yaxis: {
                min: 0,
                max: 100,
                labels: {
                    style:     { colors: '#55556a', fontSize: '11px' },
                    formatter: v => v,
                },
            },
            plotOptions: {
                bar: {
                    borderRadius:      4,
                    distributed:       true,
                    columnWidth:       '60%',
                    dataLabels:        { position: 'top' },
                },
            },
            dataLabels: {
                enabled:   true,
                formatter: v => v,
                style:     { fontSize: '11px', colors: ['#e8e8f0'] },
                offsetY:   -18,
            },
            colors,
            legend: { show: false },
            tooltip: {
                ...this._baseOptions().tooltip,
                y: { formatter: v => v + '/100' },
            },
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
        this._instances[elId] = chart
        return chart
    },

    pnlBar(elId, history = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !history.length) return

        const recent  = history.slice(-20)
        const labels  = recent.map(t => t.coin || '--')
        const values  = recent.map(t => parseFloat(t.pnl_raw || 0))
        const colors  = values.map(v => v >= 0 ? '#00d4aa' : '#ff4466')

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'bar',
                height: 180,
            },
            series: [{ name: 'PnL', data: values }],
            xaxis: {
                categories: labels,
                labels: {
                    style:  { colors: '#55556a', fontSize: '10px' },
                    rotate: -45,
                },
                axisBorder: { show: false },
                axisTicks:  { show: false },
            },
            yaxis: {
                labels: {
                    style:     { colors: '#55556a', fontSize: '11px' },
                    formatter: v => '$' + v.toFixed(2),
                },
            },
            plotOptions: {
                bar: {
                    borderRadius: 3,
                    distributed:  true,
                    columnWidth:  '70%',
                },
            },
            colors,
            legend: { show: false },
            tooltip: {
                ...this._baseOptions().tooltip,
                y: { formatter: v => (v >= 0 ? '+' : '') + '$' + v.toFixed(4) },
            },
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
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

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'bar',
                height: 320,
            },
            series: [{ name: 'Edge %', data: values }],
            xaxis: {
                categories: labels,
                labels: {
                    style: { colors: '#8888aa', fontSize: '11px' },
                },
                axisBorder: { show: false },
                axisTicks:  { show: false },
            },
            yaxis: {
                labels: {
                    style:     { colors: '#55556a', fontSize: '11px' },
                    formatter: v => v.toFixed(1) + '%',
                },
            },
            plotOptions: {
                bar: {
                    borderRadius: 4,
                    distributed:  true,
                    horizontal:   true,
                    barHeight:    '60%',
                },
            },
            colors,
            legend: { show: false },
            tooltip: {
                ...this._baseOptions().tooltip,
                y: { formatter: v => (v >= 0 ? '+' : '') + v.toFixed(1) + '% edge' },
            },
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
        this._instances[elId] = chart
        return chart
    },

    winRateGauge(elId, winRate = 0) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el) return

        const color =
            winRate >= 55 ? '#00d4aa' :
            winRate >= 45 ? '#ff9500' : '#ff4466'

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'radialBar',
                height: 200,
            },
            series: [parseFloat(winRate) || 0],
            plotOptions: {
                radialBar: {
                    startAngle: -135,
                    endAngle:    135,
                    hollow: {
                        size:   '60%',
                        margin: 0,
                    },
                    track: {
                        background: '#1a1a24',
                        strokeWidth: '100%',
                    },
                    dataLabels: {
                        name: {
                            show:     true,
                            label:    'Win Rate',
                            color:    '#8888aa',
                            fontSize: '12px',
                            offsetY:  20,
                        },
                        value: {
                            show:      true,
                            color,
                            fontSize:  '24px',
                            fontWeight: 700,
                            offsetY:   -10,
                            formatter: v => v + '%',
                        },
                    },
                },
            },
            colors: [color],
            labels: ['Win Rate'],
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
        this._instances[elId] = chart
        return chart
    },

    dailyPnl(elId, dailyData = []) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el || !dailyData.length) return

        const labels = dailyData.map(d => d.date)
        const values = dailyData.map(d => parseFloat(d.profit_abs || d.pnl || 0))
        const colors = values.map(v => v >= 0 ? '#00d4aa' : '#ff4466')

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'bar',
                height: 180,
            },
            series: [{ name: 'Daily PnL', data: values }],
            xaxis: {
                categories: labels,
                labels: {
                    style:  { colors: '#55556a', fontSize: '10px' },
                    rotate: -30,
                },
                axisBorder: { show: false },
                axisTicks:  { show: false },
            },
            yaxis: {
                labels: {
                    style:     { colors: '#55556a', fontSize: '11px' },
                    formatter: v => '$' + v.toFixed(2),
                },
            },
            plotOptions: {
                bar: {
                    borderRadius: 3,
                    distributed:  true,
                    columnWidth:  '70%',
                },
            },
            colors,
            legend: { show: false },
            tooltip: {
                ...this._baseOptions().tooltip,
                y: { formatter: v => (v >= 0 ? '+' : '') + '$' + v.toFixed(4) },
            },
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
        this._instances[elId] = chart
        return chart
    },

    mlProgress(elId, pct = 0) {
        this.destroy(elId)
        const el = document.getElementById(elId)
        if (!el) return

        const color = pct >= 100 ? '#00d4aa' : '#4488ff'

        const opts = {
            ...this._baseOptions(),
            chart: {
                ...this._baseOptions().chart,
                id:     elId,
                type:   'radialBar',
                height: 180,
            },
            series: [Math.min(100, parseFloat(pct) || 0)],
            plotOptions: {
                radialBar: {
                    hollow: { size: '55%' },
                    track:  { background: '#1a1a24' },
                    dataLabels: {
                        name:  { show: false },
                        value: {
                            color,
                            fontSize:   '20px',
                            fontWeight: 700,
                            formatter:  v => v + '%',
                        },
                    },
                },
            },
            colors: [color],
        }

        const chart = new ApexCharts(el, opts)
        chart.render()
        this._instances[elId] = chart
        return chart
    },
}

window.Charts = Charts