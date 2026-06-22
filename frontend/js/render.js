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
    $set('h-open-trades', { text: profit.trade_count || 0 })
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
  } catch(e) { return null }
}

function _formatIST(dt) {
  if (!dt) return '--'
  try {
    return dt.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata', hour12: true,
      day: '2-digit', month: 'short',
      hour: '2-digit', minute: '2-digit'
    }) + ' IST'
  } catch(e) { return '--' }
}

function _formatDuration(dt) {
  if (!dt) return '--'
  try {
    const diffMs   = Date.now() - dt.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1)  return 'Just opened'
    if (diffMins < 60) return `${diffMins}m`
    const hrs  = Math.floor(diffMins / 60)
    const mins = diffMins % 60
    if (hrs < 24) return `${hrs}h ${mins}m`
    const days = Math.floor(hrs / 24)
    return `${days}d ${hrs % 24}h`
  } catch(e) { return '--' }
}

function _fmtP(v) {
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
  } catch(e) { return '--' }
}

function _buildTradeCardHTML(t) {
  const isLong   = !t.is_short
  const dirColor = isLong ? '#248a3d' : '#c0392b'
  const dirEmoji = isLong ? '📈' : '📉'
  const dirLabel = isLong ? 'LONG' : 'SHORT'
  const pnl      = parseFloat(t.profit_abs || 0)
  const pnlPct   = parseFloat(t.profit_ratio || 0) * 100
  const pnlColor = pnl >= 0 ? '#248a3d' : '#c0392b'
  const pnlStr   = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(4)
  const pnlPctStr = (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%'
  const pair     = t.pair || '--'
  const coin     = pair.replace('/USDT:USDT', '').replace('/USDT', '')
  const symbol   = coin + 'USDT'
  const entry    = parseFloat(t.open_rate || 0)
  const current  = parseFloat(t.current_rate || entry)
  const sl       = t.sl_signal ? parseFloat(t.sl_signal) : parseFloat(t.stop_loss_abs || 0)
  const stake    = parseFloat(t.stake_amount || 0)
  const leverage = t.leverage || 1
  const tp       = (t.tp1 !== undefined && t.tp1 !== null && t.tp1 !== 0) ? parseFloat(t.tp1) : null

  const openDt   = _parseOpenDate(t.open_date)
  const openIST  = _formatIST(openDt)
  const duration = _formatDuration(openDt)

  const health      = t.health || null
  const healthState = health ? health.state : null
  const hColor      = { 'HEALTHY': '#248a3d', 'WARNING': '#e8820c', 'INVALIDATED': '#ff3b30' }[healthState] || '#6e6e73'
  const hEmoji      = { 'HEALTHY': '✅', 'WARNING': '⚠️', 'INVALIDATED': '🚨' }[healthState] || '⏳'
  const hLabel      = healthState || 'Checking...'
  const hFailures   = health ? (health.failures || []) : []
  const hWarnings   = health ? (health.warnings || []) : []
  const hDetail     = healthState === 'INVALIDATED' && hFailures.length ? hFailures[0]
                    : healthState === 'WARNING'     && hWarnings.length ? hWarnings[0]
                    : ''

  const inProfit    = isLong ? current > entry : current < entry
  const profitColor = inProfit ? '#248a3d' : '#c0392b'
  const movePct     = entry > 0 ? ((isLong ? current - entry : entry - current) / entry * 100) : 0
  const movePctStr  = (movePct >= 0 ? '+' : '') + movePct.toFixed(3) + '%'
  const moveColor   = movePct >= 0 ? '#248a3d' : '#c0392b'

  const slDist    = Math.abs(current - sl)
  const slDistPct = current > 0 ? (slDist / current * 100).toFixed(2) : '0'
  const tpDist    = tp ? Math.abs(tp - current) : 0
  const tpDistPct = tp && current > 0 ? (tpDist / current * 100).toFixed(2) : '0'

  const totalRange   = tp ? Math.abs(tp - entry) : 0
  const slRange      = Math.abs(sl - entry)
  const currentMove  = Math.abs(current - entry)
  const progressToTp = totalRange > 0 ? Math.min(100, (currentMove / totalRange * 100)) : 0
  const progressToSl = slRange   > 0 ? Math.min(100, (currentMove / slRange   * 100)) : 0

  const barLeftWidth  = (!inProfit && tp) ? progressToSl.toFixed(1) : '0'
  const barRightWidth = (inProfit  && tp) ? progressToTp.toFixed(1) : '0'
  const barPctText    = tp
    ? (inProfit ? progressToTp.toFixed(1) + '% to TP' : progressToSl.toFixed(1) + '% to SL')
    : '--'

  return `
    <div class="trade-card glass-strong rounded-apple overflow-hidden"
         id="ft-trade-${t.trade_id}"
         data-symbol="${symbol}"
         data-entry="${entry}"
         data-sl="${sl}"
         data-tp="${tp || 0}"
         data-islong="${isLong}">

      <div class="px-5 py-4 border-b divider">
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap mb-2">
              <span class="font-bold text-lg" style="color:${dirColor}">${coin}</span>
              <span class="text-xs font-semibold px-2 py-0.5 rounded-full"
                    style="color:${dirColor};background:${dirColor}18;border:1px solid ${dirColor}35">
                ${dirEmoji} ${dirLabel}
              </span>
              <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-black/5 text-apple-secondary">
                #${t.trade_id} · ${leverage}x
              </span>
              <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style="color:${hColor};background:${hColor}15;border:1px solid ${hColor}30">
                ${hEmoji} ${hLabel}
              </span>
            </div>
            <div class="flex items-baseline gap-3">
              <span data-pnl class="num font-bold text-2xl" style="color:${pnlColor}">${pnlStr}</span>
              <span data-pnl-pct class="num text-xs font-semibold" style="color:${pnlColor}">${pnlPctStr}</span>
            </div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="text-xs font-semibold text-apple-text">Open ${duration}</div>
            <div class="text-[10px] text-apple-secondary mt-0.5">${openIST}</div>
          </div>
        </div>

        ${hDetail ? `
        <div class="mt-3 px-3 py-2 rounded-apple-xs text-[11px] font-medium"
             style="background:${hColor}10;border:1px solid ${hColor}25;color:${hColor}">
          ${healthState === 'INVALIDATED' ? '✘' : '⚠'} ${hDetail}
        </div>` : ''}
      </div>

      <div class="grid grid-cols-4 divide-x divide-black/[0.06] border-b divider">

        <div class="px-4 py-3">
          <div class="section-label mb-1.5">ENTRY</div>
          <div class="num font-semibold text-sm text-apple-blue">${_fmtP(entry)}</div>
          <div class="num text-[10px] text-apple-secondary mt-0.5">reference</div>
        </div>

        <div class="px-4 py-3">
          <div class="section-label mb-1.5">NOW</div>
          <div class="num font-semibold text-sm flex items-center gap-1"
               id="now-price-${t.trade_id}"
               style="color:${profitColor}">
            ${_fmtP(current)}
            <span class="live-dot" style="background:${profitColor}"></span>
          </div>
          <div class="num text-[10px] mt-0.5"
               id="now-move-${t.trade_id}"
               style="color:${moveColor}">
            ${movePctStr}
          </div>
        </div>

        <div class="px-4 py-3">
          <div class="section-label mb-1.5">STOP</div>
          <div class="num font-semibold text-sm text-apple-red">${_fmtP(sl)}</div>
          <div class="num text-[10px] text-apple-secondary mt-0.5">${slDistPct}% away</div>
        </div>

        <div class="px-4 py-3">
          <div class="section-label mb-1.5">TARGET</div>
          <div class="num font-semibold text-sm text-apple-green">${tp ? _fmtP(tp) : '--'}</div>
          <div class="num text-[10px] text-apple-secondary mt-0.5">${tp ? tpDistPct + '% away' : 'no target'}</div>
        </div>

      </div>

      ${tp ? `
      <div class="px-5 py-3 border-b divider">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-semibold text-apple-red">SL ◄</span>
            <span class="text-[9px] text-apple-secondary uppercase tracking-wider">progress</span>
            <span class="text-[10px] font-semibold text-apple-green">► TP</span>
          </div>
          <span id="bar-pct-${t.trade_id}"
                class="num text-[10px] font-bold"
                style="color:${profitColor}">
            ${barPctText}
          </span>
        </div>
        <div class="relative h-2 bg-black/[0.06] rounded-full overflow-hidden flex">
          <div id="bar-sl-${t.trade_id}"
               class="tc-bar-left"
               style="width:${barLeftWidth}%;background:#ff3b30;${!inProfit ? 'box-shadow:0 0 6px rgba(255,59,48,0.4)' : ''}">
          </div>
          <div class="flex-1"></div>
          <div id="bar-tp-${t.trade_id}"
               class="tc-bar-right"
               style="width:${barRightWidth}%;background:#34c759;${inProfit ? 'box-shadow:0 0 6px rgba(52,199,89,0.4)' : ''}">
          </div>
          <div class="absolute left-1/2 top-0 bottom-0 w-px bg-black/20 -translate-x-1/2"></div>
        </div>
      </div>` : ''}

      ${health && (hFailures.length > 1 || hWarnings.length > 0) ? `
      <div class="px-5 py-3 border-b divider">
        <div class="section-label mb-2">Health Detail</div>
        <div class="space-y-1 text-[11px]">
          ${hFailures.map(f => `<div style="color:#ff3b30">✘ ${f}</div>`).join('')}
          ${hWarnings.slice(0,3).map(w => `<div style="color:#e8820c">⚠ ${w}</div>`).join('')}
          ${health.checks ? health.checks.slice(0,2).map(c => `<div style="color:#248a3d">✔ ${c}</div>`).join('') : ''}
        </div>
      </div>` : ''}

      <div class="px-5 py-3 flex items-center justify-between gap-3 flex-wrap">
        <div class="text-[11px] text-apple-secondary">
          Stake <strong class="text-apple-text">$${stake.toFixed(2)}</strong>
          · <strong class="text-apple-text">${leverage}x</strong>
          · <strong class="text-apple-text">${symbol}</strong>
        </div>
        <button onclick="ftForceSell(${t.trade_id})"
                class="text-[11px] font-semibold px-3 py-1.5 rounded-apple-xs transition-colors"
                style="border:1px solid rgba(255,59,48,0.2);background:rgba(255,59,48,0.06);color:#ff3b30">
          🔴 Force Sell
        </button>
      </div>

    </div>
  `
}


function updateTradeCardPrice(symbol, price) {
  const cards = document.querySelectorAll(`[data-symbol="${symbol}"]`)
  cards.forEach(card => {
    const entry   = parseFloat(card.dataset.entry || 0)
    const sl      = parseFloat(card.dataset.sl || 0)
    const tp      = parseFloat(card.dataset.tp || 0)
    const isLong  = card.dataset.islong === 'true'
    const tradeId = card.id.replace('ft-trade-', '')

    const inProfit    = isLong ? price > entry : price < entry
    const profitColor = inProfit ? '#248a3d' : '#c0392b'
    const movePct     = entry > 0 ? ((isLong ? price - entry : entry - price) / entry * 100) : 0
    const movePctStr  = (movePct >= 0 ? '+' : '') + movePct.toFixed(3) + '%'
    const moveColor   = movePct >= 0 ? '#248a3d' : '#c0392b'

    const nowPriceEl = document.getElementById(`now-price-${tradeId}`)
    const nowMoveEl  = document.getElementById(`now-move-${tradeId}`)
    const barTpEl    = document.getElementById(`bar-tp-${tradeId}`)
    const barSlEl    = document.getElementById(`bar-sl-${tradeId}`)
    const barPctEl   = document.getElementById(`bar-pct-${tradeId}`)

    if (nowPriceEl) {
      const dot = nowPriceEl.querySelector('.live-dot')
      nowPriceEl.childNodes[0].textContent = _fmtP(price) + ' '
      nowPriceEl.style.color = profitColor
      if (dot) dot.style.background = profitColor
    }

    if (nowMoveEl) {
      nowMoveEl.textContent = movePctStr
      nowMoveEl.style.color = moveColor
    }

    if (tp && entry) {
      const totalRange   = Math.abs(tp - entry)
      const slRange      = Math.abs(sl - entry)
      const currentMove  = Math.abs(price - entry)
      const progressToTp = totalRange > 0 ? Math.min(100, (currentMove / totalRange * 100)) : 0
      const progressToSl = slRange   > 0 ? Math.min(100, (currentMove / slRange   * 100)) : 0

      if (barTpEl) {
        barTpEl.style.width      = inProfit ? progressToTp.toFixed(1) + '%' : '0%'
        barTpEl.style.boxShadow  = inProfit ? '0 0 6px rgba(52,199,89,0.4)' : 'none'
      }
      if (barSlEl) {
        barSlEl.style.width      = !inProfit ? progressToSl.toFixed(1) + '%' : '0%'
        barSlEl.style.boxShadow  = !inProfit ? '0 0 6px rgba(255,59,48,0.4)' : 'none'
      }
      if (barPctEl) {
        barPctEl.textContent = inProfit
          ? progressToTp.toFixed(1) + '% to TP'
          : progressToSl.toFixed(1) + '% to SL'
        barPctEl.style.color = profitColor
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
    const sym = key.toUpperCase().replace('USDT', '') + 'USDT'
    if (!activeSymbols.includes(sym)) stopBinanceTickerWs(sym)
  })

  if (newIds !== existingIds) {
    grid.innerHTML = trades.map(t => _buildTradeCardHTML(t)).join('')
  }

  trades.forEach(t => {
    const coin   = (t.pair || '').replace('/USDT:USDT', '').replace('/USDT', '')
    startBinanceTickerWs(coin + 'USDT')
  })
}


function renderFtProfit(profit) {
  if (!profit) return
  const total    = parseFloat(profit.profit_all_coin || 0)
  const totalStr = (total >= 0 ? '+$' : '-$') + Math.abs(total).toFixed(4)
  $set('ft-total-profit', { text: totalStr, color: total >= 0 ? '#248a3d' : '#c0392b' })
  $set('ft-win-rate',     { text: (parseFloat(profit.winrate || 0) * 100).toFixed(1) + '%' })
  $set('ft-total-trades', { text: profit.trade_count || 0 })
  $set('ft-avg-duration', { text: profit.profit_factor ? profit.profit_factor.toFixed(2) + 'x' : '--' })
  $set('ft-best-trade',   { text: '+' + (parseFloat(profit.best_pair_profit_ratio  || 0) * 100).toFixed(2) + '%', color: '#248a3d' })
  $set('ft-worst-trade',  { text:       (parseFloat(profit.worst_pair_profit_ratio || 0) * 100).toFixed(2) + '%', color: '#c0392b' })
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
      <div class="col-span-full text-center py-10 text-apple-secondary text-xs">
        No scan data yet.<br>
        <button onclick="triggerScan()" class="mt-2 text-apple-blue font-semibold bg-transparent border-none cursor-pointer">
          Click Scan Now
        </button>
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
  div.className = 'radar-card glass rounded-apple-sm p-3 relative overflow-hidden cursor-pointer'
  div.style.borderTop = `3px solid ${r.grade_color}`
  div.onclick   = () => showCoinDetail(r.coin)
  _updateRadarCard(div, r)
  return div
}


function _updateRadarCard(el, r) {
  el.style.borderTopColor = r.grade_color
  const ml = r.ml_probability !== null && r.ml_probability !== undefined
    ? `<div class="text-[9px] mt-1 font-semibold" style="color:${r.ml_probability >= 0.65 ? '#248a3d' : '#ff3b30'}">ML ${(r.ml_probability*100).toFixed(0)}%</div>`
    : ''

  el.innerHTML = `
    <div class="font-semibold text-xs text-apple-text mb-1">${r.coin}</div>
    <div class="text-[11px] font-semibold mb-2" style="color:${r.dir_color}">${r.dir_emoji} ${r.direction}</div>
    <div class="progress-track h-1 mb-2">
      <div class="bar h-full rounded-full" style="width:${r.score_pct}%;background:${r.grade_color}"></div>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-[10px] font-bold" style="color:${r.grade_color}">${r.grade} · ${r.score}</span>
      <span class="num text-[10px]" style="color:${r.change_color}">${r.change}</span>
    </div>
    <div class="num text-[10px] text-apple-secondary mt-0.5">${r.price}</div>
    ${r.confidence ? `<div class="text-[10px] mt-0.5" style="color:${r.grade_color}80">${r.confidence}</div>` : ''}
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
      <div class="text-center py-8 text-apple-secondary text-xs">
        No A/A+ signals in last scan.<br>
        <span class="text-[10px]">Next scan at next :00/:15/:30/:45 UTC</span>
      </div>`
    return
  }

  wrap.innerHTML = queue.map(q => `
    <div class="glass rounded-apple-sm p-3 cursor-pointer mb-2 transition-shadow hover:shadow-apple-md"
         style="border-left:4px solid ${q.dir_color}"
         onclick="showCoinDetail('${q.coin}')">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <span class="font-semibold text-sm text-apple-text">${q.coin}USDT</span>
          <span class="text-xs font-semibold" style="color:${q.dir_color}">${q.dir_emoji} ${q.direction}</span>
        </div>
        <span class="text-xs font-bold px-2 py-0.5 rounded-full"
              style="color:${q.grade_color};background:${q.grade_color}15">
          ${q.grade} · ${q.score}
        </span>
      </div>
      <div class="grid grid-cols-3 gap-2 mb-2">
        <div>
          <div class="section-label mb-1">Entry</div>
          <div class="num text-xs font-semibold text-apple-blue">${q.entry}</div>
        </div>
        <div>
          <div class="section-label mb-1">Stop</div>
          <div class="num text-xs font-semibold text-apple-red">${q.sl}</div>
        </div>
        <div>
          <div class="section-label mb-1">Target</div>
          <div class="num text-xs font-semibold text-apple-green">${q.tp1}</div>
        </div>
      </div>
      ${q.thesis ? `<div class="thesis-block mb-2">${q.thesis}</div>` : ''}
      <div class="flex items-center justify-between pt-2 border-t divider">
        <span class="text-[10px] text-apple-secondary">${q.regime} · ${q.session}</span>
        <span class="num text-[10px] font-medium text-apple-red">Risk: ${q.risk_amt}</span>
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
    list.innerHTML = `<div class="text-center py-8 text-apple-secondary text-xs">No closed signals yet</div>`
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
           class="flex items-center gap-2 px-3 py-2 rounded-apple-xs cursor-pointer transition-colors hover:bg-black/[0.06]"
           style="border-left:2px solid ${h.border_color}">
        <span class="font-semibold text-xs text-apple-text w-12 flex-shrink-0">${h.coin}</span>
        <span class="text-xs font-semibold w-10 flex-shrink-0" style="color:${h.dir_color}">${h.dir_emoji} ${h.direction}</span>
        <span class="flex-1 text-[10px] text-apple-secondary truncate">Grade ${h.grade} · ${tsIST}</span>
        <span class="num text-xs font-semibold flex-shrink-0" style="color:${h.pnl_color}">${h.pnl}</span>
        <span class="text-xs flex-shrink-0">${h.outcome_emoji}</span>
      </div>`
  }).join('')
}


function renderCoinUniverse(coins) {
  const wrap  = document.getElementById('coin-universe-pills')
  const count = document.getElementById('coin-count')
  if (!wrap) return

  if (!coins || !coins.length) {
    wrap.innerHTML = `
      <div class="text-apple-secondary text-xs py-2">
        No coins yet.
        <button onclick="addCoin()" class="text-apple-blue font-semibold bg-transparent border-none cursor-pointer text-xs">Add a coin</button>
      </div>`
    return
  }

  if (count) count.textContent = `(${coins.length} coins)`

  wrap.innerHTML = coins.map(c => {
    const gc         = c.grade_color || '#6e6e73'
    const gradeLabel = c.grade !== '--' ? c.grade : ''
    const dot        = c.has_signal
      ? `<span class="inline-block w-1.5 h-1.5 rounded-full ml-1 align-middle" style="background:${gc}"></span>`
      : ''

    return `
      <button
        onclick="showCoinPillDetail(${JSON.stringify(c).replace(/"/g, '&quot;')})"
        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold transition-all hover:-translate-y-px hover:shadow-apple text-apple-text"
        style="opacity:${c.enabled ? '1' : '0.5'};
               background:${c.enabled ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.04)'};
               border:${c.enabled ? `1px solid ${gc}30` : '1px solid rgba(0,0,0,0.08)'}">
        ${c.coin}
        ${gradeLabel ? `<span class="text-[9px] font-bold" style="color:${gc}">${gradeLabel}</span>` : ''}
        ${dot}
        ${!c.enabled ? '<span class="text-[9px] text-apple-secondary">⏸</span>' : ''}
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
    <div class="grid grid-cols-2 gap-3 mb-4">
      <div class="bg-black/[0.04] rounded-apple-sm p-3">
        <div class="section-label mb-2">Market</div>
        <div class="num font-bold text-xl text-apple-text mb-1">${c.price || '--'}</div>
        <div class="num text-xs font-semibold mb-2" style="color:${c.change_color || '#6e6e73'}">${c.change || '--'} 24h</div>
        <div class="text-[11px] text-apple-secondary space-y-1">
          <div>Volume: <strong class="text-apple-text">${volStr}</strong></div>
          <div>Funding: <strong style="color:${Math.abs(c.funding || 0) > 0.05 ? '#ff3b30' : '#1d1d1f'}">${c.funding !== undefined ? c.funding.toFixed(4) + '%' : '--'}</strong></div>
        </div>
      </div>
      <div class="bg-black/[0.04] rounded-apple-sm p-3">
        <div class="section-label mb-2">Signal</div>
        ${c.has_signal ? `
          <div class="text-base font-bold mb-1" style="color:${gc}">Grade ${c.grade}</div>
          <div class="text-xs text-apple-secondary mb-2">${c.direction || '--'} · Score ${c.score}/100</div>
        ` : `
          <div class="text-sm text-apple-secondary mb-1">No signal yet</div>
          <div class="text-[11px] text-apple-secondary">Run /scan to get signal</div>
        `}
        <div class="text-[11px] text-apple-secondary space-y-1 mt-2">
          <div>Source: <strong class="text-apple-text">${c.source || 'manual'}</strong></div>
          <div>Tier: <strong class="text-apple-text">${c.tier || 1}</strong></div>
        </div>
      </div>
    </div>

    <div class="flex items-center justify-between p-3 bg-black/[0.04] rounded-apple-sm mb-3">
      <div>
        <div class="text-sm font-semibold text-apple-text">${c.enabled ? '✅ Enabled' : '⏸ Disabled'}</div>
        <div class="text-[11px] text-apple-secondary mt-0.5">${c.enabled ? 'Coin is being scanned' : 'Coin is paused'}</div>
      </div>
      <div onclick="toggleCoin('${c.coin}', ${!c.enabled});closeModal()"
           class="w-11 h-6 rounded-full cursor-pointer relative transition-colors"
           style="background:${c.enabled ? '#34c759' : 'rgba(0,0,0,0.15)'}">
        <div class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all"
             style="${c.enabled ? 'right:2px' : 'left:2px'}"></div>
      </div>
    </div>

    <div class="flex gap-2">
      ${c.has_signal ? `
        <button onclick="closeModal();showCoinDetail('${c.coin}')"
                class="flex-1 py-2.5 rounded-apple-xs text-sm font-semibold cursor-pointer transition-colors"
                style="border:1px solid rgba(0,113,227,0.2);background:rgba(0,113,227,0.06);color:#0071e3">
          📊 View Full Analysis
        </button>` : ''}
      <button onclick="closeModal();deleteCoin('${c.coin}')"
              class="px-4 py-2.5 rounded-apple-xs text-sm font-semibold cursor-pointer transition-colors"
              style="border:1px solid rgba(255,59,48,0.2);background:rgba(255,59,48,0.06);color:#ff3b30">
        🗑️ Remove
      </button>
    </div>
  `

  overlay.classList.remove('hidden')
  overlay.classList.add('flex')
}