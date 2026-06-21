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
  const badge = $id('ft-status-badge')
  const btn   = $id('ft-start-btn')
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
  const btn = $id('mode-toggle-btn')
  if (!btn) return

  const isLive = mode === 'live'
  btn.dataset.mode    = mode
  btn.textContent     = isLive ? '🔴 LIVE' : '🔵 PAPER'
  btn.style.background  = isLive ? 'rgba(255,59,48,0.1)'  : 'rgba(0,113,227,0.1)'
  btn.style.color       = isLive ? '#ff3b30'               : '#0071e3'
  btn.style.borderColor = isLive ? 'rgba(255,59,48,0.2)'  : 'rgba(0,113,227,0.2)'
}

function renderFtTrades(trades) {
  const empty = $id('ft-trades-empty')
  const grid  = $id('ft-trades-grid')
  const count = $id('ft-trade-count')
  if (!grid) return

  if (!trades || !Array.isArray(trades) || trades.length === 0) {
    if (empty) empty.classList.remove('hidden')
    grid.classList.add('hidden')
    grid.innerHTML = ''
    if (count) count.textContent = 'via Freqtrade · 0 open'
    return
  }

  if (empty) empty.classList.add('hidden')
  grid.classList.remove('hidden')
  if (count) count.textContent = `via Freqtrade · ${trades.length} open`

  grid.innerHTML = trades.map(t => {
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
    const entry     = parseFloat(t.open_rate || 0)
    const current   = parseFloat(t.current_rate || 0)
    const sl        = parseFloat(t.stop_loss_abs || 0)
    const stake     = parseFloat(t.stake_amount || 0)
    const leverage  = t.leverage || 1

    const fmtP = v => v ? '$' + parseFloat(v).toFixed(4) : '--'

    const movePct    = entry > 0 ? ((current - entry) / entry * 100) : 0
    const movePctStr = (movePct >= 0 ? '+' : '') + movePct.toFixed(2) + '%'
    const moveColor  = movePct >= 0 ? '#248a3d' : '#c0392b'

    const distSl    = Math.abs(current - sl)
    const distSlPct = current > 0 ? (distSl / current * 100).toFixed(2) : '0'

    const openDate = t.open_date ? new Date(t.open_date).toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata', hour12: true,
      day: '2-digit', month: 'short',
      hour: '2-digit', minute: '2-digit'
    }) + ' IST' : '--'

    const tp = t.tp1 || null

    let progressPct   = 0
    let progressColor = '#ff3b30'
    let progressLabel = 'At entry'

    if (tp && entry) {
      const totalDist = Math.abs(tp - entry)
      const curDist   = isLong ? (current - entry) : (entry - current)
      progressPct     = totalDist > 0 ? Math.max(0, Math.min(100, curDist / totalDist * 100)) : 0
      progressColor   = progressPct > 0 ? '#34c759' : '#ff3b30'
      progressLabel   = progressPct > 0
        ? `${progressPct.toFixed(0)}% to TP`
        : `${Math.abs(progressPct).toFixed(0)}% toward SL`
    }

    const health      = t.health || null
    const healthState = health ? health.state : null

    const healthColor = {
      'HEALTHY':     '#248a3d',
      'WARNING':     '#e8820c',
      'INVALIDATED': '#ff3b30'
    }[healthState] || '#6e6e73'

    const healthEmoji = {
      'HEALTHY':     '✅',
      'WARNING':     '⚠️',
      'INVALIDATED': '🚨'
    }[healthState] || '⏳'

    const healthLabel = healthState || 'Checking...'

    const healthFailures = health ? (health.failures || []) : []
    const healthWarnings = health ? (health.warnings || []) : []

    const healthDetail = healthState === 'INVALIDATED' && healthFailures.length
      ? healthFailures[0]
      : healthState === 'WARNING' && healthWarnings.length
      ? healthWarnings[0]
      : ''

    return `
      <div class="glass-strong rounded-apple overflow-hidden trade-card" id="ft-trade-${t.trade_id}">
        <div style="padding:14px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
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
            <div style="text-align:right">
              <div data-pnl style="font-size:26px;font-weight:700;font-family:monospace;color:${pnlColor}">${pnlStr}</div>
              <div data-pnl-pct style="font-size:11px;font-family:monospace;color:${pnlColor}">${pnlPctStr}</div>
            </div>
          </div>
          ${healthDetail ? `
          <div style="margin-top:8px;padding:6px 10px;border-radius:8px;background:${healthColor}10;border:1px solid ${healthColor}25;font-size:11px;color:${healthColor}">
            ${healthState === 'INVALIDATED' ? '✘' : '⚠'} ${healthDetail}
          </div>` : ''}
        </div>

        ${tp ? `
        <div style="padding:10px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
          <div style="display:flex;justify-content:space-between;font-size:10px;color:#6e6e73;font-family:monospace;margin-bottom:6px">
            <span>${fmtP(entry)}</span>
            <span>${progressLabel}</span>
            <span>${fmtP(tp)}</span>
          </div>
          <div class="progress-track" style="height:6px">
            <div style="height:100%;border-radius:100px;width:${progressPct}%;background:${progressColor};transition:width 0.5s"></div>
          </div>
        </div>` : ''}

        <div style="display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid rgba(0,0,0,0.06)">
          <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06)">
            <div class="section-label" style="margin-bottom:4px">Current</div>
            <div data-current style="font-weight:600;font-family:monospace;font-size:13px;color:${pnlColor}">${fmtP(current)}</div>
            <div data-move style="font-size:10px;margin-top:2px;font-family:monospace;color:${moveColor}">${movePctStr}</div>
          </div>
          <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06)">
            <div class="section-label" style="margin-bottom:4px">Entry</div>
            <div style="font-weight:600;font-family:monospace;font-size:13px;color:#0071e3">${fmtP(entry)}</div>
          </div>
          <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06)">
            <div class="section-label" style="margin-bottom:4px">Stop Loss</div>
            <div style="font-weight:600;font-family:monospace;font-size:13px;color:#ff3b30">${fmtP(sl)}</div>
            <div style="font-size:10px;margin-top:2px;color:#6e6e73">${distSlPct}% away</div>
          </div>
          <div style="padding:10px 12px">
            <div class="section-label" style="margin-bottom:4px">${tp ? 'TP' : 'Stake'}</div>
            <div style="font-weight:600;font-family:monospace;font-size:13px;color:#34c759">${tp ? fmtP(tp) : '$' + stake.toFixed(2)}</div>
          </div>
        </div>

        ${health && (healthFailures.length > 1 || healthWarnings.length > 0) ? `
        <div style="padding:10px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
          <div class="section-label" style="margin-bottom:6px">Trade Health</div>
          <div style="font-size:11px;line-height:1.8">
            ${healthFailures.map(f => `<div style="color:#ff3b30">✘ ${f}</div>`).join('')}
            ${healthWarnings.slice(0,3).map(w => `<div style="color:#e8820c">⚠ ${w}</div>`).join('')}
            ${health.checks ? health.checks.slice(0,2).map(c => `<div style="color:#248a3d">✔ ${c}</div>`).join('') : ''}
          </div>
        </div>` : ''}

        <div style="padding:12px 18px;border-bottom:1px solid rgba(0,0,0,0.06)">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">
            ${['15m','1h','4h','1d'].map(t => `
              <button
                data-chart-btn="chart-${t.trade_id}"
                data-tf="${t}"
                onclick="switchChartTf('chart-${t.trade_id}','${coin}','${t}',${entry},${sl},${tp || 0})"
                style="padding:3px 10px;border-radius:100px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid rgba(0,0,0,0.1);transition:all 0.15s;background:${t === '4h' ? 'rgba(0,113,227,0.2)' : 'rgba(0,0,0,0.1)'};color:${t === '4h' ? '#0071e3' : '#6e6e73'}">
                ${t}
              </button>`).join('')}
          </div>
          <div id="chart-${t.trade_id}" style="width:100%;height:280px;border-radius:8px;overflow:hidden"></div>
        </div>

        <div style="padding:10px 18px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
          <div style="font-size:11px;color:#6e6e73">
            Opened: <strong style="color:#1d1d1f">${openDate}</strong>
            · Stake: <strong style="color:#1d1d1f">$${stake.toFixed(2)}</strong>
          </div>
          <button
            onclick="ftForceSell(${t.trade_id})"
            style="padding:6px 14px;border-radius:10px;border:1px solid rgba(255,59,48,0.2);background:rgba(255,59,48,0.06);color:#ff3b30;font-size:12px;font-weight:600;cursor:pointer">
            🔴 Force Sell
          </button>
        </div>
      </div>
    `
  }).join('')

    trades.forEach(t => {
    const coin   = (t.pair || '').replace('/USDT:USDT', '').replace('/USDT', '')
    const entry  = parseFloat(t.open_rate || 0)
    const sl     = parseFloat(t.stop_loss_abs || 0)
    const tp     = t.tp1 || 0

    setTimeout(() => {
      _createTradeChart(
        `chart-${t.trade_id}`,
        coin, '4h',
        entry, sl, tp
      )
    }, 100)
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
  const dot  = $id('status-dot')
  const text = $id('status-text')
  const sub  = $id('status-sub')
  const lst  = $id('last-scan-time')

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
  const grid = $id('radar-grid')
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

  const upd = $id('radar-updated')
  if (upd) upd.textContent = 'Updated ' + _nowIST()
}

function _createRadarCard(r) {
  const div = document.createElement('div')
  div.id        = `radar-${r.coin}`
  div.className = 'radar-card glass rounded-apple-sm'
  div.style.cssText = `padding:12px;position:relative;overflow:hidden;border-top:3px solid ${r.grade_color}`
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
  const wrap = $id('signal-queue')
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
  const list = $id('history-list')
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
  const wrap  = $id('coin-universe-pills')
  const count = $id('coin-count')
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
  const title   = $id('modal-title')
  const body    = $id('modal-body')
  const overlay = $id('modal-overlay')

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

const _tradeCharts = {}

function _createTradeChart(containerId, coin, tf, entry, sl, tp) {
  const container = document.getElementById(containerId)
  if (!container) return null

  if (_tradeCharts[containerId]) {
    try { _tradeCharts[containerId].chart.remove() } catch(e) {}
    delete _tradeCharts[containerId]
  }

  const chart = LightweightCharts.createChart(container, {
    width:  container.clientWidth || 600,
    height: 280,
    layout: {
      background: { color: '#0d1117' },
      textColor:  '#e6edf3',
    },
    grid: {
      vertLines:   { color: '#21262d' },
      horzLines:   { color: '#21262d' },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
    rightPriceScale: {
      borderColor: '#21262d',
    },
    timeScale: {
      borderColor:     '#21262d',
      timeVisible:     true,
      secondsVisible:  false,
    },
  })

  const candleSeries = chart.addCandlestickSeries({
    upColor:          '#34c759',
    downColor:        '#ff3b30',
    borderUpColor:    '#34c759',
    borderDownColor:  '#ff3b30',
    wickUpColor:      '#34c759',
    wickDownColor:    '#ff3b30',
  })

  const volumeSeries = chart.addHistogramSeries({
    color:      '#21262d',
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
    scaleMargins: { top: 0.85, bottom: 0 },
  })

  const priceLinesMap = {}

  if (entry) {
    priceLinesMap.entry = candleSeries.createPriceLine({
      price:     entry,
      color:     '#0071e3',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: true,
      title: `Entry ${entry.toFixed(4)}`,
    })
  }

  if (sl) {
    priceLinesMap.sl = candleSeries.createPriceLine({
      price:     sl,
      color:     '#ff3b30',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Solid,
      axisLabelVisible: true,
      title: `SL ${sl.toFixed(4)}`,
    })
  }

  if (tp) {
    priceLinesMap.tp = candleSeries.createPriceLine({
      price:     tp,
      color:     '#34c759',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Solid,
      axisLabelVisible: true,
      title: `TP ${tp.toFixed(4)}`,
    })
  }

  priceLinesMap.current = candleSeries.createPriceLine({
    price:     entry || 0,
    color:     '#ff9500',
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dotted,
    axisLabelVisible: true,
    title: 'Now',
  })

  _tradeCharts[containerId] = {
    chart,
    candleSeries,
    volumeSeries,
    priceLinesMap,
    coin,
    tf
  }

  _loadChartData(containerId, coin, tf)

  return _tradeCharts[containerId]
}


async function _loadChartData(containerId, coin, tf) {
  try {
    const res = await fetch(`/api/candles/${coin}/${tf}`)
    if (!res.ok) return
    const data = await res.json()
    if (!data || !data.length) return

    const chartObj = _tradeCharts[containerId]
    if (!chartObj) return

    chartObj.candleSeries.setData(data.map(c => ({
      time:  c.time,
      open:  c.open,
      high:  c.high,
      low:   c.low,
      close: c.close
    })))

    chartObj.volumeSeries.setData(data.map(c => ({
      time:  c.time,
      value: c.volume,
      color: c.close >= c.open ? 'rgba(52,199,89,0.3)' : 'rgba(255,59,48,0.3)'
    })))

    chartObj.chart.timeScale().fitContent()

  } catch(e) {
    console.error('Chart data load error:', e)
  }
}


function updateChartPrice(containerId, price) {
  const chartObj = _tradeCharts[containerId]
  if (!chartObj) return
  if (!chartObj.priceLinesMap.current) return
  try {
    chartObj.priceLinesMap.current.applyOptions({ price })
  } catch(e) {}
}


function switchChartTf(containerId, coin, tf, entry, sl, tp) {
  const chartObj = _tradeCharts[containerId]
  if (!chartObj) return

  const btns = document.querySelectorAll(`[data-chart-btn="${containerId}"]`)
  btns.forEach(b => {
    b.style.background = b.dataset.tf === tf
      ? 'rgba(0,113,227,0.2)'
      : 'rgba(0,0,0,0.1)'
    b.style.color = b.dataset.tf === tf ? '#0071e3' : '#6e6e73'
  })

  chartObj.tf   = tf
  chartObj.coin = coin
  _loadChartData(containerId, coin, tf)
}