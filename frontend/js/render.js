'use strict'

function renderAll() {
  const d = S.data
  if (!d) return
  renderHeader(d.header)
  renderStatusBar(d)
  renderRadar(d.radar)
  renderSignalQueue(d.queue)
  renderPerformance(d.performance)
  renderHistory(d.history)
  renderCoinUniverse(d.coin_universe)
  renderCharts(d.history)
}

function renderHeader(h) {
  if (!h) return
  $set('h-today-pnl',   { text: h.today_pnl,    color: h.today_pnl_color })
  $set('h-winrate',     { text: h.win_rate,      color: h.win_rate_color })
  $set('h-coins-count', { text: h.coins_count })
}

function renderFtHeader(balance, profit) {
  if (balance) {
    const total = parseFloat(balance.total || 0)
    $set('h-balance', { text: '$' + total.toFixed(2) })
  }
  if (profit) {
    const trades = profit.trade_count || 0
    $set('h-open-trades', { text: trades })
  }
}

function renderFtBotStatus(status, botState) {
  const badge = document.getElementById('ft-status-badge')
  const btn   = document.getElementById('ft-start-btn')
  if (!badge) return

  const isRunning = botState === 'running'

  if (isRunning) {
    badge.textContent       = '▶ Running'
    badge.style.background  = 'rgba(52,199,89,0.1)'
    badge.style.color       = '#248a3d'
    badge.style.borderColor = 'rgba(52,199,89,0.2)'
    badge.dataset.running   = 'true'
    if (btn) {
      btn.textContent      = '⏹ Stop Bot'
      btn.style.background = 'rgba(255,59,48,0.1)'
      btn.style.color      = '#ff3b30'
      btn.style.border     = '1px solid rgba(255,59,48,0.3)'
    }
  } else {
    badge.textContent       = '⏹ Stopped'
    badge.style.background  = 'rgba(255,59,48,0.1)'
    badge.style.color       = '#ff3b30'
    badge.style.borderColor = 'rgba(255,59,48,0.2)'
    badge.dataset.running   = 'false'
    if (btn) {
      btn.textContent      = '▶ Start Bot'
      btn.style.background = 'rgba(52,199,89,0.15)'
      btn.style.color      = '#248a3d'
      btn.style.border     = '1px solid rgba(52,199,89,0.3)'
    }
  }
}

function renderModeToggle(mode) {
  const btn = document.getElementById('mode-toggle-btn')
  if (!btn) return

  const isLive          = mode === 'live'
  btn.dataset.mode      = mode
  btn.textContent       = isLive ? '🔴 LIVE' : '🔵 PAPER'
  btn.style.background  = isLive ? 'rgba(255,59,48,0.1)'  : 'rgba(0,113,227,0.1)'
  btn.style.color       = isLive ? '#ff3b30'               : '#0071e3'
  btn.style.borderColor = isLive ? 'rgba(255,59,48,0.2)'  : 'rgba(0,113,227,0.2)'
}


function _parseOpenDate(dateStr) {
  if (!dateStr) return null
  try {
    const str = dateStr.toString().trim()
    let dt

    if (str.includes('T')) {
      dt = new Date(str.endsWith('Z') ? str : str + '+00:00')
    } else if (str.includes(' ')) {
      dt = new Date(str.replace(' ', 'T') + '+00:00')
    } else {
      dt = new Date(str)
    }

    return isNaN(dt.getTime()) ? null : dt
  } catch(e) {
    return null
  }
}


function _formatIST(dt) {
  if (!dt) return '--'
  try {
    return dt.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour12:   true,
      day:      '2-digit',
      month:    'short',
      hour:     '2-digit',
      minute:   '2-digit'
    }) + ' IST'
  } catch(e) {
    return '--'
  }
}


function _formatDuration(dt) {
  if (!dt) return '--'
  try {
    const diffMs   = Date.now() - dt.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1)   return 'Just opened'
    if (diffMins < 60)  return `${diffMins}m`
    const hrs  = Math.floor(diffMins / 60)
    const mins = diffMins % 60
    if (hrs < 24) return `${hrs}h ${mins}m`
    const days = Math.floor(hrs / 24)
    const remH = hrs % 24
    return `${days}d ${remH}h`
  } catch(e) {
    return '--'
  }
}


function _fmtPrice(v) {
  if (v === null || v === undefined || v === 0) return '--'
  try {
    const n = parseFloat(v)
    if (isNaN(n)) return '--'
    if (n >= 10000)  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    if (n >= 1000)   return '$' + n.toFixed(2)
    if (n >= 100)    return '$' + n.toFixed(3)
    if (n >= 1)      return '$' + n.toFixed(4)
    if (n >= 0.1)    return '$' + n.toFixed(5)
    if (n >= 0.01)   return '$' + n.toFixed(6)
    if (n >= 0.001)  return '$' + n.toFixed(7)
    return '$' + n.toFixed(8)
  } catch(e) {
    return '--'
  }
}


function _buildSparkline(symbol) {
  const history = getPriceHistory(symbol)
  if (history.length < 2) {
    return `<svg width="80" height="24" viewBox="0 0 80 24">
      <line x1="0" y1="12" x2="80" y2="12" stroke="rgba(110,110,115,0.3)" stroke-width="1" stroke-dasharray="2,2"/>
    </svg>`
  }

  const prices  = history.map(h => h.price)
  const minP    = Math.min(...prices)
  const maxP    = Math.max(...prices)
  const range   = maxP - minP || 1
  const w       = 80
  const h       = 24
  const pad     = 2

  const points = prices.map((p, i) => {
    const x = pad + (i / (prices.length - 1)) * (w - pad * 2)
    const y = h - pad - ((p - minP) / range) * (h - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  const first = prices[0]
  const last  = prices[prices.length - 1]
  const color = last >= first ? '#34c759' : '#ff3b30'

  const firstX = pad
  const firstY = h - pad - ((first - minP) / range) * (h - pad * 2)
  const lastX  = w - pad
  const lastY  = h - pad - ((last - minP) / range) * (h - pad * 2)

  const areaPoints = `${firstX},${h - pad} ${points} ${lastX},${h - pad}`

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <defs>
      <linearGradient id="sg-${symbol}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0.05"/>
      </linearGradient>
    </defs>
    <polygon points="${areaPoints}" fill="url(#sg-${symbol})"/>
    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${lastX}" cy="${lastY}" r="2.5" fill="${color}">
      <animate attributeName="r" values="2;3.5;2" dur="1.5s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="1;0.6;1" dur="1.5s" repeatCount="indefinite"/>
    </circle>
  </svg>`
}


function _buildPriceLadder(entry, sl, tp, currentPrice, isLong) {
  if (!entry || !sl || !tp) return ''

  const allPrices  = [sl, entry, currentPrice || entry, tp]
  const minPrice   = Math.min(...allPrices)
  const maxPrice   = Math.max(...allPrices)
  const priceRange = maxPrice - minPrice || 1

  function priceToPct(price) {
    return ((price - minPrice) / priceRange * 100).toFixed(2)
  }

  const tpPct      = parseFloat(priceToPct(tp))
  const entryPct   = parseFloat(priceToPct(entry))
  const slPct      = parseFloat(priceToPct(sl))
  const currentPct = parseFloat(priceToPct(currentPrice || entry))

  const inProfit   = currentPrice ? (isLong ? currentPrice > entry : currentPrice < entry) : false
  const fillColor  = inProfit ? 'rgba(52,199,89,0.15)' : 'rgba(255,59,48,0.15)'
  const fillBorder = inProfit ? 'rgba(52,199,89,0.4)'  : 'rgba(255,59,48,0.4)'

  const slDist  = currentPrice ? Math.abs(currentPrice - sl)  : Math.abs(entry - sl)
  const tpDist  = currentPrice ? Math.abs(tp - currentPrice)  : Math.abs(tp - entry)
  const slDistPct = currentPrice ? (Math.abs(currentPrice - sl)  / currentPrice * 100).toFixed(2) : '0'
  const tpDistPct = currentPrice ? (Math.abs(tp - currentPrice)  / currentPrice * 100).toFixed(2) : '0'

  const totalRange    = Math.abs(tp - entry)
  const currentMove   = currentPrice ? Math.abs(currentPrice - entry) : 0
  const progressToTp  = totalRange > 0 ? Math.min(100, (currentMove / totalRange * 100)).toFixed(0) : 0
  const progressColor = inProfit ? '#34c759' : '#ff3b30'

  const movePct    = currentPrice && entry ? ((isLong ? currentPrice - entry : entry - currentPrice) / entry * 100) : 0
  const movePctStr = (movePct >= 0 ? '+' : '') + movePct.toFixed(2) + '%'
  const moveColor  = movePct >= 0 ? '#248a3d' : '#c0392b'

  return `
    <div class="price-ladder">

      <div class="price-ladder-row" style="top:${100 - tpPct}%">
        <div class="price-ladder-label tp">
          <span class="price-ladder-tag" style="background:rgba(52,199,89,0.15);color:#34c759;border-color:rgba(52,199,89,0.3)">🎯 TP</span>
          <span class="price-ladder-value" style="color:#34c759">${_fmtPrice(tp)}</span>
        </div>
        <div class="price-ladder-line" style="background:#34c759"></div>
        <div class="price-ladder-dist" style="color:#34c759">$${tpDist.toFixed(4)} away · ${tpDistPct}%</div>
      </div>

      <div class="price-ladder-fill" style="
        top:${100 - Math.max(currentPct, entryPct)}%;
        height:${Math.abs(currentPct - entryPct)}%;
        background:${fillColor};
        border-left:2px solid ${fillBorder};
        border-right:2px solid ${fillBorder};
      "></div>

      <div class="price-ladder-row price-ladder-current" id="ladder-current" style="top:${100 - currentPct}%">
        <div class="price-ladder-label current">
          <span class="price-ladder-tag" style="background:rgba(255,149,0,0.15);color:#ff9500;border-color:rgba(255,149,0,0.3)">
            ● NOW
          </span>
          <span class="price-ladder-value" style="color:#ff9500" data-current-price>${_fmtPrice(currentPrice || entry)}</span>
          <span style="font-size:10px;font-weight:600;color:${moveColor};margin-left:4px" data-move-pct>${movePctStr}</span>
        </div>
        <div class="price-ladder-line price-ladder-line-current" style="background:#ff9500"></div>
      </div>

      <div class="price-ladder-row" style="top:${100 - entryPct}%">
        <div class="price-ladder-label entry">
          <span class="price-ladder-tag" style="background:rgba(0,113,227,0.15);color:#0071e3;border-color:rgba(0,113,227,0.3)">⚡ ENTRY</span>
          <span class="price-ladder-value" style="color:#0071e3">${_fmtPrice(entry)}</span>
        </div>
        <div class="price-ladder-line" style="background:#0071e3;opacity:0.6;border-top:1px dashed #0071e3"></div>
      </div>

      <div class="price-ladder-row" style="top:${100 - slPct}%">
        <div class="price-ladder-label sl">
          <span class="price-ladder-tag" style="background:rgba(255,59,48,0.15);color:#ff3b30;border-color:rgba(255,59,48,0.3)">🛡 SL</span>
          <span class="price-ladder-value" style="color:#ff3b30">${_fmtPrice(sl)}</span>
        </div>
        <div class="price-ladder-line" style="background:#ff3b30"></div>
        <div class="price-ladder-dist" style="color:#ff3b30">$${slDist.toFixed(4)} away · ${slDistPct}%</div>
      </div>

      <div class="price-ladder-progress">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <span style="font-size:10px;color:#6e6e73">Progress to TP</span>
          <span style="font-size:10px;font-weight:700;color:${progressColor}">${progressToTp}%</span>
        </div>
        <div style="height:4px;background:rgba(0,0,0,0.08);border-radius:100px;overflow:hidden">
          <div style="height:100%;width:${progressToTp}%;background:${progressColor};border-radius:100px;transition:width 0.5s ease"></div>
        </div>
      </div>

    </div>
  `
}


function _buildTradeCardHTML(t) {
  const isLong    = !t.is_short
  const dirColor  = isLong ? '#248a3d' : '#c0392b'
  const dirEmoji  = isLong ? '📈' : '📉'
  const pnl       = parseFloat(t.profit_abs || 0)
  const pnlPct    = parseFloat(t.profit_ratio || 0) * 100
  const pnlColor  = pnl >= 0 ? '#248a3d' : '#c0392b'
  const pnlStr    = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(4)
  const pnlPctStr = (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%'
  const pair      = t.pair || '--'
  const coin      = pair.replace('/USDT:USDT', '').replace('/USDT', '')
  const symbol    = coin + 'USDT'
  const entry     = parseFloat(t.open_rate || 0)
  const current   = parseFloat(t.current_rate || entry)
  const sl        = t.sl_signal ? parseFloat(t.sl_signal) : parseFloat(t.stop_loss_abs || 0)
  const stake     = parseFloat(t.stake_amount || 0)
  const leverage  = t.leverage || 1
  const tp        = (t.tp1 !== undefined && t.tp1 !== null && t.tp1 !== 0) ? parseFloat(t.tp1) : null

  const openDt   = _parseOpenDate(t.open_date)
  const openIST  = _formatIST(openDt)
  const duration = _formatDuration(openDt)

  const health         = t.health || null
  const healthState    = health ? health.state : null
  const healthColor    = { 'HEALTHY': '#248a3d', 'WARNING': '#e8820c', 'INVALIDATED': '#ff3b30' }[healthState] || '#6e6e73'
  const healthEmoji    = { 'HEALTHY': '✅', 'WARNING': '⚠️', 'INVALIDATED': '🚨' }[healthState] || '⏳'
  const healthLabel    = healthState || 'Checking...'
  const healthFailures = health ? (health.failures || []) : []
  const healthWarnings = health ? (health.warnings || []) : []
  const healthDetail   = healthState === 'INVALIDATED' && healthFailures.length
    ? healthFailures[0]
    : healthState === 'WARNING' && healthWarnings.length
    ? healthWarnings[0]
    : ''

  const priceLadder = tp ? _buildPriceLadder(entry, sl, tp, current, isLong) : ''
  const sparkline   = _buildSparkline(symbol)

  return `
    <div class="trade-card glass-strong rounded-apple overflow-hidden" id="ft-trade-${t.trade_id}" data-symbol="${symbol}" data-entry="${entry}" data-sl="${sl}" data-tp="${tp || 0}" data-islong="${isLong}">

      <div style="padding:14px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
          <div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">
              <span style="font-size:20px;font-weight:700;color:${dirColor}">${coin}</span>
              <span style="padding:3px 10px;border-radius:100px;font-size:12px;font-weight:600;color:${dirColor};background:${dirColor}15;border:1px solid ${dirColor}40">
                ${dirEmoji} ${isLong ? 'LONG' : 'SHORT'}
              </span>
              <span style="padding:3px 10px;border-radius:100px;font-size:11px;font-weight:500;background:rgba(0,0,0,0.05);color:#6e6e73">
                #${t.trade_id} · ${leverage}x
              </span>
              <span style="padding:3px 10px;border-radius:100px;font-size:11px;font-weight:600;color:${healthColor};background:${healthColor}15;border:1px solid ${healthColor}40">
                ${healthEmoji} ${healthLabel}
              </span>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
              <div>
                <div data-pnl style="font-size:22px;font-weight:700;font-family:monospace;color:${pnlColor}">${pnlStr}</div>
                <div data-pnl-pct style="font-size:11px;font-family:monospace;color:${pnlColor}">${pnlPctStr}</div>
              </div>
              <div style="font-size:11px;color:#6e6e73;line-height:1.8">
                <div>Open <strong style="color:#1d1d1f">${duration}</strong></div>
                <div style="font-size:10px">${openIST}</div>
              </div>
            </div>
          </div>
          <div style="flex-shrink:0;opacity:0.9" id="sparkline-${t.trade_id}">
            ${sparkline}
          </div>
        </div>

        ${healthDetail ? `
        <div style="margin-top:8px;padding:6px 10px;border-radius:8px;background:${healthColor}10;border:1px solid ${healthColor}25;font-size:11px;color:${healthColor}">
          ${healthState === 'INVALIDATED' ? '✘' : '⚠'} ${healthDetail}
        </div>` : ''}
      </div>

      ${priceLadder ? `
      <div style="padding:16px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
        ${priceLadder}
      </div>` : `
      <div style="padding:12px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
          <div style="background:rgba(0,0,0,0.04);border-radius:8px;padding:10px">
            <div class="section-label" style="margin-bottom:4px">Entry</div>
            <div style="font-family:monospace;font-weight:600;font-size:12px;color:#0071e3">${_fmtPrice(entry)}</div>
          </div>
          <div style="background:rgba(0,0,0,0.04);border-radius:8px;padding:10px">
            <div class="section-label" style="margin-bottom:4px">Current</div>
            <div data-current-price style="font-family:monospace;font-weight:600;font-size:12px;color:${pnlColor}">${_fmtPrice(current)}</div>
          </div>
          <div style="background:rgba(0,0,0,0.04);border-radius:8px;padding:10px">
            <div class="section-label" style="margin-bottom:4px">Stop</div>
            <div style="font-family:monospace;font-weight:600;font-size:12px;color:#ff3b30">${_fmtPrice(sl)}</div>
          </div>
        </div>
      </div>`}

      ${health && (healthFailures.length > 1 || healthWarnings.length > 0) ? `
      <div style="padding:10px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:6px">Health Detail</div>
        <div style="font-size:11px;line-height:1.8">
          ${healthFailures.map(f => `<div style="color:#ff3b30">✘ ${f}</div>`).join('')}
          ${healthWarnings.slice(0,3).map(w => `<div style="color:#e8820c">⚠ ${w}</div>`).join('')}
          ${health.checks ? health.checks.slice(0,2).map(c => `<div style="color:#248a3d">✔ ${c}</div>`).join('') : ''}
        </div>
      </div>` : ''}

      <div style="padding:10px 18px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div style="font-size:11px;color:#6e6e73">
          Stake: <strong style="color:#1d1d1f">$${stake.toFixed(2)}</strong>
          · Leverage: <strong style="color:#1d1d1f">${leverage}x</strong>
        </div>
        <button
          onclick="ftForceSell(${t.trade_id})"
          style="padding:6px 14px;border-radius:10px;border:1px solid rgba(255,59,48,0.2);background:rgba(255,59,48,0.06);color:#ff3b30;font-size:12px;font-weight:600;cursor:pointer">
          🔴 Force Sell
        </button>
      </div>

    </div>
  `
}


function updateTradeCardPrice(symbol, price) {
  const cards = document.querySelectorAll(`[data-symbol="${symbol}"]`)
  cards.forEach(card => {
    const entry  = parseFloat(card.dataset.entry || 0)
    const sl     = parseFloat(card.dataset.sl || 0)
    const tp     = parseFloat(card.dataset.tp || 0)
    const isLong = card.dataset.islong === 'true'

    const inProfit   = isLong ? price > entry : price < entry
    const priceColor = inProfit ? '#248a3d' : '#c0392b'
    const movePct    = entry > 0 ? ((isLong ? price - entry : entry - price) / entry * 100) : 0
    const movePctStr = (movePct >= 0 ? '+' : '') + movePct.toFixed(2) + '%'
    const moveColor  = movePct >= 0 ? '#248a3d' : '#c0392b'

    const priceEls = card.querySelectorAll('[data-current-price]')
    priceEls.forEach(el => {
      el.textContent = _fmtPrice(price)
      el.style.color = priceColor
    })

    const moveEls = card.querySelectorAll('[data-move-pct]')
    moveEls.forEach(el => {
      el.textContent = movePctStr
      el.style.color = moveColor
    })

    const tradeId   = card.id.replace('ft-trade-', '')
    const sparkEl   = document.getElementById(`sparkline-${tradeId}`)
    if (sparkEl) sparkEl.innerHTML = _buildSparkline(symbol)

    if (tp) {
      const totalRange   = Math.abs(tp - entry)
      const currentMove  = Math.abs(price - entry)
      const progressToTp = totalRange > 0 ? Math.min(100, (currentMove / totalRange * 100)).toFixed(0) : 0
      const progColor    = inProfit ? '#34c759' : '#ff3b30'

      const progBar = card.querySelector('.price-ladder-progress div div')
      if (progBar) {
        progBar.style.width      = progressToTp + '%'
        progBar.style.background = progColor
      }

      const progPct = card.querySelector('.price-ladder-progress span:last-child')
      if (progPct) {
        progPct.textContent = progressToTp + '%'
        progPct.style.color = progColor
      }

      const fillEl = card.querySelector('.price-ladder-fill')
      if (fillEl) {
        const allPrices  = [sl, entry, price, tp]
        const minPrice   = Math.min(...allPrices)
        const maxPrice   = Math.max(...allPrices)
        const priceRange = maxPrice - minPrice || 1

        const entryPct   = (entry   - minPrice) / priceRange * 100
        const currentPct = (price   - minPrice) / priceRange * 100
        const fillColor  = inProfit ? 'rgba(52,199,89,0.15)'  : 'rgba(255,59,48,0.15)'
        const fillBorder = inProfit ? 'rgba(52,199,89,0.4)'   : 'rgba(255,59,48,0.4)'

        fillEl.style.top        = (100 - Math.max(currentPct, entryPct)) + '%'
        fillEl.style.height     = Math.abs(currentPct - entryPct) + '%'
        fillEl.style.background = fillColor
        fillEl.style.borderLeft = `2px solid ${fillBorder}`
        fillEl.style.borderRight= `2px solid ${fillBorder}`
      }

      const currentRow = card.querySelector('.price-ladder-current')
      if (currentRow) {
        const allPrices  = [sl, entry, price, tp]
        const minPrice   = Math.min(...allPrices)
        const maxPrice   = Math.max(...allPrices)
        const priceRange = maxPrice - minPrice || 1
        const currentPct = (price - minPrice) / priceRange * 100
        currentRow.style.top = (100 - currentPct) + '%'
      }
    }
  })
}


function renderFtTrades(trades) {
  const empty = document.getElementById('ft-trades-empty')
  const grid  = document.getElementById('ft-trades-grid')
  const count = document.getElementById('ft-trade-count')
  if (!grid) return

  if (!trades || !Array.isArray(trades) || trades.length === 0) {
    if (empty) empty.classList.remove('hidden')
    grid.classList.add('hidden')
    grid.innerHTML = ''
    if (count) count.textContent = 'via Freqtrade · 0 open'
    stopAllBinanceWs()
    return
  }

  if (empty) empty.classList.add('hidden')
  grid.classList.remove('hidden')
  if (count) count.textContent = `via Freqtrade · ${trades.length} open`

  const newIds      = trades.map(t => t.trade_id).sort().join(',')
  const existingIds = [...grid.querySelectorAll('[id^="ft-trade-"]')]
    .map(el => el.id.replace('ft-trade-', '')).sort().join(',')

  const activeSymbols = trades.map(t =>
    (t.pair || '').replace('/USDT:USDT', '').replace('/USDT', '') + 'USDT'
  )

  Object.keys(window._binanceWsSockets || {}).forEach(key => {
    const sym = key.replace('usdt', 'USDT').toUpperCase()
    if (!activeSymbols.includes(sym)) stopBinanceTickerWs(sym)
  })

  if (newIds !== existingIds) {
    grid.innerHTML = trades.map(t => _buildTradeCardHTML(t)).join('')
  }

  trades.forEach(t => {
    const coin   = (t.pair || '').replace('/USDT:USDT', '').replace('/USDT', '')
    const symbol = coin + 'USDT'
    startBinanceTickerWs(symbol)
  })
}


function renderFtProfit(profit) {
  if (!profit) return

  const total    = parseFloat(profit.profit_all_coin || 0)
  const totalStr = (total >= 0 ? '+$' : '-$') + Math.abs(total).toFixed(4)
  const color    = total >= 0 ? '#248a3d' : '#c0392b'

  $set('ft-total-profit', { text: totalStr, color })
  $set('ft-win-rate',     { text: (parseFloat(profit.winrate || 0) * 100).toFixed(1) + '%' })
  $set('ft-total-trades', { text: profit.trade_count || 0 })

  const pf = profit.profit_factor ? profit.profit_factor.toFixed(2) + 'x' : '--'
  $set('ft-avg-duration', { text: pf })

  const best  = parseFloat(profit.best_pair_profit_ratio || 0) * 100
  const worst = parseFloat(profit.worst_pair_profit_ratio || 0) * 100
  $set('ft-best-trade',  { text: '+' + best.toFixed(2) + '%',  color: '#248a3d' })
  $set('ft-worst-trade', { text: worst.toFixed(2) + '%',        color: '#c0392b' })
}


function renderStatusBar(d) {
  const dot  = document.getElementById('status-dot')
  const text = document.getElementById('status-text')
  const sub  = document.getElementById('status-sub')
  const lst  = document.getElementById('last-scan-time')

  if (S.scanning) {
    if (dot)  dot.style.background = '#0071e3'
    if (text) text.textContent = '🔍 Scanning all coins...'
    if (sub)  sub.textContent  = 'Analyzing — takes 1-2 min'
    return
  }

  if (!d) return

  const cached_count = (d.radar || []).length
  const tradeable    = (d.queue || []).length

  if (dot)  dot.style.background = '#34c759'
  if (text) text.textContent = 'RUNNING — Signal Engine Active'
  if (sub)  sub.textContent  = `${cached_count} coins cached · ${tradeable} tradeable signal${tradeable !== 1 ? 's' : ''}`

  if (d.last_scan && d.last_scan !== '--') {
    if (lst) lst.textContent = d.last_scan
  }
}


function renderRadar(radar) {
  const grid = document.getElementById('radar-grid')
  if (!grid) return

  if (!radar || !radar.length) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:40px 0;color:#6e6e73;font-size:12px">
        No scan data yet.<br>
        <button onclick="triggerScan()" style="margin-top:8px;color:#0071e3;background:none;border:none;cursor:pointer;font-weight:600">Click Scan Now</button>
      </div>`
    return
  }

  const sorted = [...radar].sort((a, b) => b.score - a.score)

  sorted.forEach(r => {
    const prev = S.prevGrades[r.coin]
    if (prev && prev !== r.grade && r.tradeable) {
      toast(`🎯 Grade ${r.grade} Signal`, `${r.coin} ${r.direction} — Score ${r.score}`, r.grade === 'A+' ? 'success' : 'info')
    }
    S.prevGrades[r.coin] = r.grade
  })

  grid.innerHTML = ''
  sorted.forEach(r => {
    const card = _createRadarCard(r)
    grid.appendChild(card)
  })

  const upd = document.getElementById('radar-updated')
  if (upd) upd.textContent = 'Updated ' + _nowIST()
}


function _createRadarCard(r) {
  const div = document.createElement('div')
  div.id        = `radar-${r.coin}`
  div.className = 'radar-card glass rounded-apple-sm'
  div.style.cssText = `padding:12px;position:relative;overflow:hidden;border-top:3px solid ${r.grade_color};cursor:pointer`
  div.onclick   = () => showCoinDetail(r.coin)
  _updateRadarCard(div, r)
  return div
}


function _updateRadarCard(el, r) {
  el.style.borderTopColor = r.grade_color
  const ml = r.ml_probability !== null && r.ml_probability !== undefined
    ? `<div style="font-size:9px;margin-top:3px;color:${r.ml_probability >= 0.65 ? '#248a3d' : '#ff3b30'};font-weight:600">ML ${(r.ml_probability*100).toFixed(0)}%</div>`
    : ''

  el.innerHTML = `
    <div style="font-weight:600;font-size:12px;color:#1d1d1f;margin-bottom:4px">${r.coin}</div>
    <div style="font-size:11px;font-weight:600;margin-bottom:8px;color:${r.dir_color}">${r.dir_emoji} ${r.direction}</div>
    <div class="progress-track" style="height:4px;margin-bottom:8px">
      <div class="bar" style="height:100%;border-radius:100px;width:${r.score_pct}%;background:${r.grade_color}"></div>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between">
      <span style="font-size:10px;font-weight:700;color:${r.grade_color}">${r.grade} · ${r.score}</span>
            <span style="font-size:10px;font-family:monospace;color:${r.change_color}">${r.change}</span>
    </div>
    <div style="font-size:10px;font-family:monospace;color:#6e6e73;margin-top:2px">${r.price}</div>
    ${r.confidence ? `<div style="font-size:10px;margin-top:2px;color:${r.grade_color}80">${r.confidence}</div>` : ''}
    ${ml}
  `
}


function _nowIST() {
  return new Date().toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata'
  }) + ' IST'
}


function renderSignalQueue(queue) {
  const wrap = document.getElementById('signal-queue')
  if (!wrap) return

  if (!queue || !queue.length) {
    wrap.innerHTML = `
      <div style="text-align:center;padding:32px 0;color:#6e6e73;font-size:12px">
        No A/A+ signals in last scan.<br>
        <span style="font-size:10px">Next scan at next :00/:15/:30/:45 UTC</span>
      </div>`
    return
  }

  wrap.innerHTML = queue.map(q => `
    <div class="glass rounded-apple-sm"
         style="padding:12px;cursor:pointer;border-left:4px solid ${q.dir_color};margin-bottom:8px"
         onclick="showCoinDetail('${q.coin}')">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-weight:600;font-size:14px;color:#1d1d1f">${q.coin}USDT</span>
          <span style="font-size:12px;font-weight:600;color:${q.dir_color}">${q.dir_emoji} ${q.direction}</span>
        </div>
        <span style="font-size:12px;font-weight:700;padding:2px 8px;border-radius:100px;color:${q.grade_color};background:${q.grade_color}15">
          ${q.grade} · ${q.score}
        </span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:8px">
        <div>
          <div class="section-label" style="margin-bottom:2px">Entry</div>
          <div style="font-family:monospace;font-size:12px;font-weight:600;color:#0071e3">${q.entry}</div>
        </div>
        <div>
          <div class="section-label" style="margin-bottom:2px">Stop</div>
          <div style="font-family:monospace;font-size:12px;font-weight:600;color:#ff3b30">${q.sl}</div>
        </div>
        <div>
          <div class="section-label" style="margin-bottom:2px">TP</div>
          <div style="font-family:monospace;font-size:12px;font-weight:600;color:#34c759">${q.tp1}</div>
        </div>
      </div>
      ${q.thesis ? `<div class="thesis-block" style="margin-bottom:8px">${q.thesis}</div>` : ''}
      <div style="display:flex;align-items:center;justify-content:space-between;padding-top:8px;border-top:1px solid rgba(0,0,0,0.06)">
        <span style="font-size:10px;color:#6e6e73">${q.regime} · ${q.session}</span>
        <span style="font-size:10px;font-family:monospace;font-weight:500;color:#ff3b30">Risk: ${q.risk_amt}</span>
      </div>
    </div>
  `).join('')
}


function renderPerformance(p) {
  if (!p) return
  $set('perf-wr',       { text: p.win_rate,      color: p.win_rate_color })
  $set('perf-wr-sub',   { text: p.win_rate_sub })
  $set('perf-pnl',      { text: p.total_pnl,     color: p.pnl_color })
  $set('perf-pnl-sub',  { text: p.pnl_sub })
  $set('perf-pf',       { text: p.profit_factor })
  $set('perf-pf-sub',   { text: p.pf_sub })
  $set('perf-best',     { text: p.best_trade })
  $set('perf-best-sub', { text: p.best_sub })
  $set('perf-dd',       { text: p.max_drawdown,  color: p.dd_color })
  $set('perf-dd-sub',   { text: p.dd_sub })
  $set('aplus-wr',      { text: p.aplus_wr })
  $set('aplus-bar',     { width: p.aplus_bar, bg: C.green })
  $set('aplus-detail',  { text: p.aplus_detail })
  $set('a-wr',          { text: p.a_wr })
  $set('a-bar',         { width: p.a_bar, bg: C.blue })
  $set('a-detail',      { text: p.a_detail })
  $set('b-wr',          { text: p.b_wr || '0%' })
  $set('b-bar',         { width: p.b_bar || 0, bg: C.orange })
  $set('b-detail',      { text: p.b_detail || '0W · 0L · 0 trades · paper only' })
}


function renderHistory(history) {
  const list = document.getElementById('history-list')
  if (!list) return

  if (!history || !history.length) {
    list.innerHTML = `<div style="text-align:center;padding:32px 0;color:#6e6e73;font-size:12px">No closed signals yet</div>`
    return
  }

  list.innerHTML = history.map(h => {
    const tsIST = h.opened_at ? new Date(h.opened_at).toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata', hour12: true,
      day: '2-digit', month: 'short',
      hour: '2-digit', minute: '2-digit'
    }) + ' IST' : '--'

    return `
      <div onclick="showSignalDetail(${JSON.stringify(h).replace(/"/g, '&quot;')})"
           style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;background:rgba(0,0,0,0.03);border-left:2px solid ${h.border_color};cursor:pointer;transition:background 0.15s"
           onmouseover="this.style.background='rgba(0,0,0,0.06)'"
           onmouseout="this.style.background='rgba(0,0,0,0.03)'">
        <span style="font-weight:600;font-size:12px;color:#1d1d1f;width:48px;flex-shrink:0">${h.coin}</span>
        <span style="font-size:12px;font-weight:600;width:40px;flex-shrink:0;color:${h.dir_color}">${h.dir_emoji} ${h.direction}</span>
        <span style="flex:1;font-size:10px;color:#6e6e73;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">Grade ${h.grade} · ${tsIST}</span>
        <span style="font-family:monospace;font-size:12px;font-weight:600;flex-shrink:0;color:${h.pnl_color}">${h.pnl}</span>
        <span style="font-size:12px;flex-shrink:0">${h.outcome_emoji}</span>
      </div>`
  }).join('')
}


function renderCoinUniverse(coins) {
  const wrap  = document.getElementById('coin-universe-pills')
  const count = document.getElementById('coin-count')
  if (!wrap) return

  if (!coins || !coins.length) {
    wrap.innerHTML = `
      <div style="color:#6e6e73;font-size:12px;padding:8px 0">
        No coins yet.
        <button onclick="addCoin()" style="color:#0071e3;background:none;border:none;cursor:pointer;font-weight:600;font-size:12px">Add a coin</button>
      </div>`
    return
  }

  if (count) count.textContent = `(${coins.length} coins)`

  wrap.innerHTML = coins.map(c => {
    const enabled    = c.enabled
    const gc         = c.grade_color || '#6e6e73'
    const hasSignal  = c.has_signal
    const gradeLabel = c.grade !== '--' ? c.grade : ''
    const bg         = enabled ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.04)'
    const border     = enabled ? `1px solid ${gc}30` : '1px solid rgba(0,0,0,0.08)'
    const opacity    = enabled ? '1' : '0.5'
    const dot        = hasSignal ? `<span style="width:5px;height:5px;border-radius:50%;background:${gc};display:inline-block;margin-left:3px;vertical-align:middle"></span>` : ''

    return `
      <button
        onclick="showCoinPillDetail(${JSON.stringify(c).replace(/"/g, '&quot;')})"
        style="opacity:${opacity};display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:100px;font-size:11px;font-weight:600;background:${bg};border:${border};cursor:pointer;transition:all 0.15s;color:#1d1d1f"
        onmouseover="this.style.transform='translateY(-1px)';this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)'"
        onmouseout="this.style.transform='';this.style.boxShadow=''">
        ${c.coin}
        ${gradeLabel ? `<span style="font-size:9px;color:${gc};font-weight:700">${gradeLabel}</span>` : ''}
        ${dot}
        ${!enabled ? '<span style="font-size:9px;color:#6e6e73">⏸</span>' : ''}
      </button>`
  }).join('')
}


function showCoinPillDetail(c) {
  const title   = document.getElementById('modal-title')
  const body    = document.getElementById('modal-body')
  const overlay = document.getElementById('modal-overlay')

  const gc     = c.grade_color || '#6e6e73'
  const volStr = c.volume_24h
    ? (c.volume_24h >= 1e9
        ? '$' + (c.volume_24h / 1e9).toFixed(1) + 'B'
        : '$' + (c.volume_24h / 1e6).toFixed(0) + 'M')
    : '--'

  title.textContent = `${c.coin}USDT — Coin Info`

  body.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
      <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:14px">
        <div class="section-label" style="margin-bottom:8px">Market</div>
        <div style="font-size:20px;font-weight:700;font-family:monospace;color:#1d1d1f;margin-bottom:4px">${c.price || '--'}</div>
        <div style="font-size:12px;font-weight:600;color:${c.change_color || '#6e6e73'}">${c.change || '--'} 24h</div>
        <div style="font-size:11px;color:#6e6e73;margin-top:6px;line-height:1.8">
          <div>Volume 24h: <strong style="color:#1d1d1f">${volStr}</strong></div>
          <div>Funding: <strong style="color:${Math.abs(c.funding || 0) > 0.05 ? '#ff3b30' : '#1d1d1f'}">${c.funding !== undefined ? c.funding.toFixed(4) + '%' : '--'}</strong></div>
        </div>
      </div>
      <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:14px">
        <div class="section-label" style="margin-bottom:8px">Signal</div>
        ${c.has_signal ? `
          <div style="font-size:16px;font-weight:700;color:${gc};margin-bottom:4px">Grade ${c.grade}</div>
          <div style="font-size:12px;color:#6e6e73;margin-bottom:6px">${c.direction || '--'} · Score ${c.score}/100</div>
        ` : `
          <div style="font-size:13px;color:#6e6e73;margin-bottom:6px">No signal yet</div>
          <div style="font-size:11px;color:#6e6e73">Run /scan to get signal</div>
        `}
        <div style="font-size:11px;color:#6e6e73;line-height:1.8;margin-top:6px">
          <div>Source: <strong style="color:#1d1d1f">${c.source || 'manual'}</strong></div>
          <div>Tier: <strong style="color:#1d1d1f">${c.tier || 1}</strong></div>
        </div>
      </div>
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:rgba(0,0,0,0.04);border-radius:12px;margin-bottom:12px">
      <div>
        <div style="font-size:13px;font-weight:600;color:#1d1d1f">${c.enabled ? '✅ Enabled' : '⏸ Disabled'}</div>
        <div style="font-size:11px;color:#6e6e73;margin-top:2px">${c.enabled ? 'Coin is being scanned' : 'Coin is paused from scanning'}</div>
      </div>
      <div onclick="toggleCoin('${c.coin}', ${!c.enabled});closeModal()"
           style="width:44px;height:24px;border-radius:100px;background:${c.enabled ? '#34c759' : 'rgba(0,0,0,0.15)'};cursor:pointer;position:relative;transition:background 0.2s">
        <div style="position:absolute;top:2px;${c.enabled ? 'right:2px' : 'left:2px'};width:20px;height:20px;border-radius:50%;background:white;box-shadow:0 1px 4px rgba(0,0,0,0.2);transition:all 0.2s"></div>
      </div>
    </div>

    <div style="display:flex;gap:8px">
      ${c.has_signal ? `
        <button onclick="closeModal();showCoinDetail('${c.coin}')"
                style="flex:1;padding:10px;border-radius:10px;border:1px solid rgba(0,113,227,0.2);background:rgba(0,113,227,0.06);color:#0071e3;font-size:13px;font-weight:600;cursor:pointer">
          📊 View Full Analysis
        </button>` : ''}
      <button onclick="closeModal();deleteCoin('${c.coin}')"
              style="padding:10px 16px;border-radius:10px;border:1px solid rgba(255,59,48,0.2);background:rgba(255,59,48,0.06);color:#ff3b30;font-size:13px;font-weight:600;cursor:pointer">
        🗑️ Remove
      </button>
    </div>
  `

  overlay.classList.remove('hidden')
  overlay.classList.add('flex')
}