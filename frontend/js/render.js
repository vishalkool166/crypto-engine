'use strict'

function renderAll() {
  const d = S.data
  if (!d) return
  renderHeader(d.header)
  renderStatusBar(d)
  renderTrades(d.trades, d.state)
  renderRadar(d.radar)
  renderSignalQueue(d.queue)
  renderRisk(d.risk)
  renderPerformance(d.performance)
  renderHistory(d.history)
  renderCharts(d.history)
  syncConnectionMode(d.state)
}

function renderHeader(h) {
  if (!h) return
  $set('h-capital',    { text: h.capital })
  $set('h-tier',       { text: `T${h.tier}` })
  $set('h-leverage',   { text: h.leverage })
  $set('h-today-pnl',  { text: h.today_pnl,  color: h.today_pnl_color })
  $set('h-slots',      { text: `${h.active_trades}/${h.max_trades}` })
  $set('h-winrate',    { text: h.win_rate,    color: h.win_rate_color })

  const badge = $id('mode-badge')
  if (badge) {
    badge.textContent       = h.mode
    badge.style.background  = h.mode === 'LIVE' ? 'rgba(255,59,48,0.1)' : 'rgba(0,113,227,0.1)'
    badge.style.color       = h.mode === 'LIVE' ? '#ff3b30' : '#0071e3'
    badge.style.borderColor = h.mode === 'LIVE' ? 'rgba(255,59,48,0.2)' : 'rgba(0,113,227,0.2)'
  }
}

function renderStatusBar(d) {
  const dot  = $id('status-dot')
  const text = $id('status-text')
  const sub  = $id('status-sub')
  const lst  = $id('last-scan-time')
  const ilst = $id('idle-last-scan')

  if (S.scanning) {
    if (dot)  dot.style.background = '#0071e3'
    if (text) text.textContent = '🔍 Scanning all coins...'
    if (sub)  sub.textContent  = 'Analyzing — takes 1-2 min'
    return
  }

  if (!d) return

  const trades = d.trades || []

  if (d.state === 'idle' || !trades.length) {
    if (dot)  dot.style.background = '#6e6e73'
    if (text) text.textContent = 'IDLE — Watching markets'
    if (sub)  sub.textContent  = 'Auto-executes A/A+ signals'
  } else {
    if (dot)  dot.style.background = '#34c759'
    if (text) text.textContent = `IN TRADE — ${trades.length} active`
    if (sub)  sub.textContent  = trades.map(t => `${t.coin} ${t.direction}`).join(' · ')
  }

  if (d.last_scan && d.last_scan !== '--') {
    if (lst)  lst.textContent  = d.last_scan
    if (ilst) ilst.textContent = d.last_scan
  }
}

function renderTrades(trades, state) {
  const idleEl = $id('trade-idle')
  const grid   = $id('trades-grid')
  if (!idleEl || !grid) return

  if (!trades || !trades.length || state === 'idle') {
    idleEl.classList.remove('hidden')
    grid.classList.add('hidden')
    grid.innerHTML = ''
    return
  }

  idleEl.classList.add('hidden')
  grid.classList.remove('hidden')

  const existingIds = new Set([...grid.querySelectorAll('[data-trade-id]')].map(el => parseInt(el.dataset.tradeId)))
  const newIds      = new Set(trades.map(t => t.id))

  existingIds.forEach(id => {
    if (!newIds.has(id)) {
      const el = grid.querySelector(`[data-trade-id="${id}"]`)
      if (el) el.remove()
    }
  })

  trades.forEach(t => {
    const existing = grid.querySelector(`[data-trade-id="${t.id}"]`)
    if (existing) {
      _updateTradeCard(existing, t)
    } else {
      grid.appendChild(_createTradeCard(t))
    }
  })
}

function _createTradeCard(t) {
  const div = document.createElement('div')
  div.dataset.tradeId = t.id
  div.id              = `trade-card-${t.id}`
  div.className       = 'glass-strong rounded-apple overflow-hidden trade-card'
  _updateTradeCard(div, t)
  return div
}

function _updateTradeCard(el, t) {
  el.style.background = t.header_bg || ''

  el.innerHTML = `
    <div style="padding:16px 20px;border-bottom:1px solid rgba(0,0,0,0.06)">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap">
        <div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">
            <span style="font-size:22px;font-weight:700;color:${t.dir_color}">${t.coin}</span>
            <span style="padding:3px 10px;border-radius:100px;font-size:12px;font-weight:600;color:${t.dir_color};background:${t.dir_color}15;border:1px solid ${t.dir_border}40">${t.dir_emoji} ${t.direction}</span>
            <span style="padding:3px 10px;border-radius:100px;font-size:11px;font-weight:600;color:${t.grade_color};background:${t.grade_color}15;border:1px solid ${t.grade_color}40">Grade ${t.grade}</span>
            <span style="padding:3px 10px;border-radius:100px;font-size:11px;font-weight:600;color:${t.phase_color};background:${t.phase_color}15;border:1px solid ${t.phase_color}40">${t.phase_badge}</span>
            <span style="padding:3px 10px;border-radius:100px;font-size:11px;font-weight:600;color:${t.health_color};background:${t.health_color}15;border:1px solid ${t.health_color}40">${t.health_emoji} ${t.health_state}</span>
            <span style="padding:3px 10px;border-radius:100px;font-size:11px;font-weight:500;background:rgba(0,0,0,0.05);color:#6e6e73">${t.duration} open</span>
          </div>
          <div style="font-size:11px;color:#6e6e73">State: ${t.state} · Tier ${t.tier} · Balance ${t.balance}</div>
        </div>
        <div style="text-align:right">
          <div data-pnl style="font-size:28px;font-weight:700;font-family:monospace;color:${t.pnl_color}">${t.pnl}</div>
          <div style="font-size:11px;color:#6e6e73">unrealized PnL</div>
          <div data-pnl-pct style="font-size:11px;font-family:monospace;color:${t.pnl_color};margin-top:2px">${t.pnl_pct}</div>
        </div>
      </div>
    </div>

    <div style="padding:12px 20px;border-bottom:1px solid rgba(0,0,0,0.06)">
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#6e6e73;font-family:monospace;margin-bottom:6px">
        <span>${t.progress?.left_label || ''}</span>
        <span>${t.progress?.mid_label || ''}</span>
        <span>${t.progress?.right_label || ''}</span>
      </div>
      <div class="progress-track" style="height:8px">
        <div data-prog-fill class="bar" style="height:100%;border-radius:100px;width:${t.progress?.pct || 0}%;background:${t.progress?.color || '#0071e3'}"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:6px">
        <div style="font-size:11px;font-weight:600;font-family:monospace;color:${t.progress?.color || '#0071e3'}">${t.progress?.label || ''}</div>
        <div style="font-size:10px;color:#6e6e73">${t.progress?.phase_label || ''}</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid rgba(0,0,0,0.06)">
      <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:4px">Current</div>
        <div data-current-price style="font-weight:600;font-family:monospace;font-size:13px;color:${t.current_color}">${t.current_price}</div>
        <div data-move-pct style="font-size:10px;margin-top:2px;font-family:monospace;color:${t.move_color}">${t.move_pct}</div>
      </div>
      <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:4px">Entry</div>
        <div style="font-weight:600;font-family:monospace;font-size:13px;color:#1d1d1f">${t.entry_price}</div>
        <div style="font-size:10px;margin-top:2px;color:#6e6e73">filled at</div>
      </div>
      <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:4px;color:${t.sl_color}">To ${t.sl_label}</div>
        <div style="font-weight:600;font-family:monospace;font-size:13px;color:${t.sl_color}">${t.dist_to_sl}</div>
        <div style="font-size:10px;margin-top:2px;color:#6e6e73">distance</div>
      </div>
      <div style="padding:10px 12px">
        <div class="section-label" style="margin-bottom:4px">To TP1</div>
        <div style="font-weight:600;font-family:monospace;font-size:13px;color:#34c759">${t.dist_to_tp1}</div>
        <div style="font-size:10px;margin-top:2px;color:#6e6e73">distance</div>
      </div>
      <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06);border-top:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:4px">Risk</div>
        <div style="font-weight:600;font-family:monospace;font-size:13px;color:#ff3b30">${t.risk_amt}</div>
        <div style="font-size:10px;margin-top:2px;color:#6e6e73">max loss</div>
      </div>
      <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06);border-top:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:4px">TP1 Reward</div>
        <div style="font-weight:600;font-family:monospace;font-size:13px;color:#34c759">${t.tp1_reward}</div>
        <div style="font-size:10px;margin-top:2px;color:#6e6e73">if TP1 hit</div>
      </div>
      <div style="padding:10px 12px;border-right:1px solid rgba(0,0,0,0.06);border-top:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:4px">Position</div>
        <div style="font-weight:600;font-family:monospace;font-size:13px;color:#1d1d1f">${t.position_size}</div>
        <div style="font-size:10px;margin-top:2px;color:#6e6e73">notional</div>
      </div>
      <div style="padding:10px 12px;border-top:1px solid rgba(0,0,0,0.06)">
        <div class="section-label" style="margin-bottom:4px">R:R</div>
        <div style="font-weight:600;font-family:monospace;font-size:13px;color:#1d1d1f">${t.rr_ratio}</div>
        <div style="font-size:10px;margin-top:2px;color:#6e6e73">risk reward</div>
      </div>
    </div>

    ${t.thesis ? `
    <div style="padding:12px 20px;border-bottom:1px solid rgba(0,0,0,0.06)">
      <div class="section-label" style="margin-bottom:6px">Why This Trade</div>
      <div class="thesis-block">${t.thesis}</div>
      ${t.risk_thesis ? `<div class="section-label" style="margin-bottom:6px;margin-top:10px">Risk Factors</div><div class="risk-block">${t.risk_thesis}</div>` : ''}
    </div>` : ''}

    ${(t.health_failures?.length || t.health_warnings?.length) ? `
    <div style="padding:12px 20px;border-bottom:1px solid rgba(0,0,0,0.06)">
      <div class="section-label" style="margin-bottom:6px">Trade Health</div>
      <div style="font-size:11px;color:#6e6e73;line-height:1.8">
        ${(t.health_failures || []).map(f => `<div>✘ <span style="color:#ff3b30;font-weight:600">${f}</span></div>`).join('')}
        ${(t.health_warnings || []).map(w => `<div>⚠ <span style="color:#e8820c">${w}</span></div>`).join('')}
        ${(t.health_checks || []).map(c => `<div>✔ <span style="color:#248a3d">${c}</span></div>`).join('')}
      </div>
    </div>` : ''}

    <div style="padding:12px 20px;border-bottom:1px solid rgba(0,0,0,0.06)">
      <div class="section-label" style="margin-bottom:10px">Price Ladder</div>
      <div>${_renderLadderRows(t.ladder)}</div>
    </div>

    <div style="padding:12px 20px">
      <button
        data-close-btn="${t.id}"
        onclick="showConfirmClose(${t.id})"
        class="btn-danger">
        🔴 Close Trade at Market
      </button>
    </div>
  `
}

function _renderLadderRows(ladder) {
  if (!ladder) return ''
  return ladder.map(row => {
    if (!row) return ''
    if (row.is_current) {
      return `
        <div class="ladder-now" style="display:flex;align-items:center;gap:12px;padding:10px 12px;margin-bottom:6px">
          <span style="font-size:10px;font-weight:700;width:40px;flex-shrink:0;color:#0071e3">NOW</span>
          <span style="flex:1;font-family:monospace;font-weight:700;font-size:14px;color:#0071e3">${row.price}</span>
          <span style="font-size:10px;font-weight:600;padding:2px 8px;border-radius:100px;${row.badge_style}">${row.badge}</span>
        </div>`
    }
    const opacity = row.is_hit ? 'opacity:0.4;' : ''
    const strike  = row.is_hit ? 'text-decoration:line-through;' : ''
    return `
      <div style="${opacity}display:flex;align-items:center;gap:12px;padding:8px 12px;border-radius:8px;background:${row.color}08;border:1px solid ${row.color}18;margin-bottom:4px">
        <span style="font-size:10px;font-weight:600;width:40px;flex-shrink:0;color:${row.color}">${row.label}</span>
        <span style="flex:1;font-family:monospace;font-weight:600;font-size:14px;${strike}color:${row.color}">${row.price}</span>
        <span style="font-family:monospace;font-size:10px;width:56px;text-align:right;font-weight:500;color:${row.color}80">${row.dist}</span>
        <span style="font-size:10px;font-weight:600;padding:2px 8px;border-radius:100px;${row.badge_style}">${row.badge}</span>
      </div>`
  }).join('')
}

function _nowIST() {
  return new Date().toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata'
  }) + ' IST'
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

  if (!grid.querySelector('[id^="radar-"]')) grid.innerHTML = ''

  radar.forEach(r => {
    const prev = S.prevGrades[r.coin]
    if (prev && prev !== r.grade && r.tradeable) {
      toast(`🎯 Grade ${r.grade} Signal`, `${r.coin} ${r.direction} — Score ${r.score}`, r.grade === 'A+' ? 'success' : 'info')
    }
    S.prevGrades[r.coin] = r.grade

    const existing = $id(`radar-${r.coin}`)
    if (existing) {
      _updateRadarCard(existing, r)
    } else {
      grid.appendChild(_createRadarCard(r))
    }
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
    ${r.confidence ? `<div style="font-size:10px;margin-top:4px;color:${r.grade_color}80">${r.confidence}</div>` : ''}
  `
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
          <div class="section-label" style="margin-bottom:2px">TP1</div>
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

function renderRisk(r) {
  if (!r) return
  $set('risk-trades-bar', { width: r.trades_bar_pct, bg: r.trades_bar_color })
  $set('risk-trades-val', { text: r.trades_label })
  $set('risk-loss-bar',   { width: r.loss_bar_pct,   bg: r.loss_bar_color })
  $set('risk-loss-val',   { text: r.loss_label })
  $set('risk-pnl-bar',    { width: r.pnl_bar_pct,    bg: r.pnl_color === C.green_dark ? C.green : C.red })
  $set('risk-pnl-val',    { text: r.pnl_label, color: r.pnl_color })
  $set('risk-remaining-trades', { text: r.remaining_trades })
  $set('risk-remaining-loss',   { text: r.remaining_loss })
  $set('risk-tier',    { text: r.tier })
  $set('risk-balance', { text: r.balance })

  const capEl = $id('risk-cap-status')
  if (capEl) { capEl.textContent = r.cap_status; capEl.style.color = r.cap_color }
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
}

function renderHistory(history) {
  const list = $id('history-list')
  if (!list) return

  if (!history || !history.length) {
    list.innerHTML = `<div style="text-align:center;padding:32px 0;color:#6e6e73;font-size:12px">No closed trades yet</div>`
    return
  }

  list.innerHTML = history.map(h => `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;background:rgba(0,0,0,0.03);border-left:2px solid ${h.border_color}">
      <span style="font-weight:600;font-size:12px;color:#1d1d1f;width:48px;flex-shrink:0">${h.coin}</span>
      <span style="font-size:12px;font-weight:600;width:40px;flex-shrink:0;color:${h.dir_color}">${h.dir_emoji} ${h.direction}</span>
      <span style="flex:1;font-size:10px;color:#6e6e73;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${h.close_reason || '--'} · Grade ${h.grade}</span>
      <span style="font-family:monospace;font-size:12px;font-weight:600;flex-shrink:0;color:${h.pnl_color}">${h.pnl}</span>
      <span style="font-size:12px;flex-shrink:0">${h.outcome_emoji}</span>
    </div>
  `).join('')
}