'use strict'

let _chartEquity = null
let _chartDaily  = null

Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, Inter, sans-serif'
Chart.defaults.font.size   = 10
Chart.defaults.color       = '#6e6e73'
Chart.defaults.borderColor = 'rgba(0,0,0,0.06)'

const _tooltipDefaults = {
  backgroundColor: 'rgba(255,255,255,0.95)',
  titleColor:      '#1d1d1f',
  bodyColor:       '#6e6e73',
  borderColor:     'rgba(0,0,0,0.08)',
  borderWidth:     1,
  padding:         10,
  cornerRadius:    10,
}

const _scaleDefaults = {
  x: {
    ticks: { maxTicksLimit: 6, color: '#6e6e73', font: { size: 9 } },
    grid:  { color: 'rgba(0,0,0,0.04)' }
  },
  y: {
    ticks: { color: '#6e6e73', font: { size: 9 }, callback: v => '$' + parseFloat(v).toFixed(2) },
    grid:  { color: 'rgba(0,0,0,0.04)' }
  }
}

function renderCharts(history) {
  if (!history) return
  const closed = history.filter(h => h.outcome !== 'pending')
  const sorted = [...closed].reverse()
  _renderEquityChart(sorted)
  _renderDailyChart(sorted)
}

function _renderEquityChart(sorted) {
  const ctx = $id('chart-equity')
  if (!ctx) return

  if (!sorted.length) {
    ctx.parentElement.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#6e6e73;font-size:12px">
        No closed trades yet
      </div>`
    return
  }

  let equity = 0
  const labels   = []
  const values   = []
  const ptColors = []

  sorted.forEach((t, i) => {
    const pnl = typeof t.pnl_raw === 'number' ? t.pnl_raw : 0
    equity += pnl
    labels.push(t.coin || `#${i + 1}`)
    values.push(parseFloat(equity.toFixed(4)))
    ptColors.push(equity >= 0 ? '#34c759' : '#ff3b30')
  })

  if (_chartEquity) {
    _chartEquity.data.labels                            = labels
    _chartEquity.data.datasets[0].data                 = values
    _chartEquity.data.datasets[0].pointBackgroundColor = ptColors
    _chartEquity.update('none')
    return
  }

  _chartEquity = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data:                 values,
        borderColor:          '#0071e3',
        backgroundColor:      'rgba(0,113,227,0.08)',
        borderWidth:          2,
        fill:                 true,
        tension:              0.4,
        pointRadius:          3,
        pointHoverRadius:     5,
        pointBackgroundColor: ptColors,
        pointBorderWidth:     0
      }]
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      interaction:         { intersect: false, mode: 'index' },
      plugins: {
        legend:  { display: false },
        tooltip: {
          ..._tooltipDefaults,
          callbacks: { label: ctx => ' Equity: $' + ctx.parsed.y.toFixed(4) }
        }
      },
      scales:    _scaleDefaults,
      animation: false
    }
  })
}

function _renderDailyChart(sorted) {
  const ctx = $id('chart-daily')
  if (!ctx) return

  if (!sorted.length) {
    ctx.parentElement.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#6e6e73;font-size:12px">
        No data yet
      </div>`
    return
  }

  const recent  = sorted.slice(-12)
  const labels  = recent.map(t => t.coin || '--')
  const values  = recent.map(t => typeof t.pnl_raw === 'number' ? parseFloat(t.pnl_raw.toFixed(4)) : 0)
  const colors  = values.map(v => v >= 0 ? 'rgba(52,199,89,0.8)'  : 'rgba(255,59,48,0.8)')
  const borders = values.map(v => v >= 0 ? '#34c759' : '#ff3b30')

  if (_chartDaily) {
    _chartDaily.data.labels                      = labels
    _chartDaily.data.datasets[0].data            = values
    _chartDaily.data.datasets[0].backgroundColor = colors
    _chartDaily.data.datasets[0].borderColor     = borders
    _chartDaily.update('none')
    return
  }

  _chartDaily = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data:            values,
        backgroundColor: colors,
        borderColor:     borders,
        borderWidth:     1,
        borderRadius:    4,
        borderSkipped:   false
      }]
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      plugins: {
        legend:  { display: false },
        tooltip: {
          ..._tooltipDefaults,
          callbacks: { label: ctx => ' PnL: $' + ctx.parsed.y.toFixed(4) }
        }
      },
      scales: {
        x: { ..._scaleDefaults.x, grid: { display: false } },
        y: _scaleDefaults.y
      },
      animation: false
    }
  })
}