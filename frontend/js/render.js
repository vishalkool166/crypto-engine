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
  renderCoinUniverse(d.coin_universe)
  renderCharts(d.history)
  syncConnectionMode(d.state)
}

function renderHeader(h) {
  if (!h) return
  $set('h-capital',   { text: h.capital })
  $set('h-tier',      { text: `T${h.tier}` })
  $set('h-leverage',  { text: h.leverage })
  $set('h-today-pnl', { text: h.today_pnl,  color: h.today_pnl_color })
  $set('h-slots',     { text: `${h.active_trades}/${h.max_trades}` })
  $set('h-winrate',   { text: h.win_rate,    color: h.win_rate_color })

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
  const imt  = $id('idle-mode-text')

  if (S.scanning) {
    if (dot)  dot.style.background = '#0071e3'
    if (text) text.textContent = '🔍 Scanning all coins...'
    if (sub)  sub.textContent  = 'Analyzing — takes 1-2 min'
    return
  }

  if (!d) return

  const trades = d.trades || []
  const mode   = d.header?.mode || 'PAPER'
  const paused = d.header?.paused || false
  const isLive = mode === 'LIVE'

  if (d.state === 'idle' || !trades.length) {
    if (dot)  dot.style.background = '#6e6e73'
    if (text) text.textContent = 'IDLE — Watching markets'
    if (sub)  sub.textContent  = isLive ? '🔴 Live mode' : '🔵 Paper mode'

    if (imt) {
      if (paused) {
        imt.textContent = '⏸ Auto-execution paused'
      } else if (isLive) {
        imt.textContent = '🔴 Live — auto-executes A/A+ signals'
      } else {
        imt.textContent = '🔵 Paper — auto-executes A/A+ signals'
      }
    }
  } else {
    if (dot)  dot.style.background = '#34c759'
    if (text) text.textContent = `IN TRADE — ${trades.length} active`
    if (sub)  sub.textContent  = trades.map(t => `${t.coin} ${t.direction}`).join(' · ')
    if (imt)  imt.textContent  = ''
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
      <div class="progress-track" style="height:8px;position:relative;overflow:visible">
        <div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(0,0,0,0.2)"></div>
        <div data-prog-fill style="position:absolute;height:100%;border-radius:100px;
          ${t.progress?.pct > 0
            ? `left:50%;right:auto;width:${Math.abs(t.progress?.pct || 0) / 2}%;background:${t.progress?.color}`
            : `right:50%;left:auto;width:${Math.abs(t.progress?.pct || 0) / 2}%;background:${t.progress?.color}`
          }">
        </div>
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
        ${(t.health_checks   || []).map(c => `<div>✔ <span style="color:#248a3d">${c}</span></div>`).join('')}
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
    <div onclick="showTradeDetail(${JSON.stringify(h).replace(/"/g, '&quot;')})"
         style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;background:rgba(0,0,0,0.03);border-left:2px solid ${h.border_color};cursor:pointer;transition:background 0.15s"
         onmouseover="this.style.background='rgba(0,0,0,0.06)'"
         onmouseout="this.style.background='rgba(0,0,0,0.03)'">
      <span style="font-weight:600;font-size:12px;color:#1d1d1f;width:48px;flex-shrink:0">${h.coin}</span>
      <span style="font-size:12px;font-weight:600;width:40px;flex-shrink:0;color:${h.dir_color}">${h.dir_emoji} ${h.direction}</span>
      <span style="flex:1;font-size:10px;color:#6e6e73;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${h.close_reason || '--'} · Grade ${h.grade}</span>
      <span style="font-family:monospace;font-size:12px;font-weight:600;flex-shrink:0;color:${h.pnl_color}">${h.pnl}</span>
      <span style="font-size:12px;flex-shrink:0">${h.outcome_emoji}</span>
    </div>
  `).join('')
}

function showTradeDetail(h) {
  const title   = $id('modal-title')
  const body    = $id('modal-body')
  const overlay = $id('modal-overlay')

  const isLong       = h.direction === 'LONG'
  const dirColor     = isLong ? '#248a3d' : '#c0392b'
  const outcomeColor = h.outcome === 'win' ? '#248a3d' : h.outcome === 'loss' ? '#c0392b' : '#6e6e73'

  title.textContent = `${h.coin}USDT ${h.direction} — ${(h.outcome || '--').toUpperCase()}`

  const fmt = v => v ? '$' + parseFloat(v).toFixed(4) : '--'

  const fmtDate = s => {
    if (!s) return '--'
    try {
      return new Date(s).toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata', hour12: true,
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      }) + ' IST'
    } catch { return s }
  }

  const duration = () => {
    if (!h.opened_at || !h.closed_at) return '--'
    try {
      const ms   = new Date(h.closed_at) - new Date(h.opened_at)
      const mins = Math.floor(ms / 60000)
      const hrs  = Math.floor(mins / 60)
      const days = Math.floor(hrs / 24)
      if (days > 0) return `${days}d ${hrs % 24}h`
      if (hrs > 0)  return `${hrs}h ${mins % 60}m`
      return `${mins}m`
    } catch { return '--' }
  }

  body.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
      <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:14px">
        <div class="section-label" style="margin-bottom:8px">Trade Info</div>
        <div style="font-size:13px;font-weight:700;color:${dirColor};margin-bottom:6px">
          ${h.dir_emoji || ''} ${h.coin}USDT ${h.direction}
        </div>
        <div style="font-size:11px;color:#6e6e73;line-height:2">
          <div>Grade: <strong style="color:#1d1d1f">${h.grade || '--'}</strong></div>
          <div>Score: <strong style="color:#1d1d1f">${h.score_at_entry || '--'}/100</strong></div>
          <div>Regime: <strong style="color:#1d1d1f">${h.regime_at_entry || '--'}</strong></div>
          <div>Session: <strong style="color:#1d1d1f">${h.session_at_entry || '--'}</strong></div>
          <div>Duration: <strong style="color:#1d1d1f">${duration()}</strong></div>
        </div>
      </div>
      <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:14px">
        <div class="section-label" style="margin-bottom:8px">Outcome</div>
        <div style="font-size:22px;font-weight:700;font-family:monospace;color:${h.pnl_color || outcomeColor};margin-bottom:6px">
          ${h.pnl || '--'}
        </div>
        <div style="font-size:11px;color:#6e6e73;line-height:2">
          <div>Result: <strong style="color:${outcomeColor}">${(h.outcome || '--').toUpperCase()}</strong></div>
          <div>Reason: <strong style="color:#1d1d1f">${h.close_reason || '--'}</strong></div>
          <div>TP1 Hit: <strong style="color:#1d1d1f">${h.tp1_hit ? '✅ Yes' : '❌ No'}</strong></div>
          ${h.partial_pnl ? `<div>Partial PnL: <strong style="color:#248a3d">+$${parseFloat(h.partial_pnl).toFixed(4)}</strong></div>` : ''}
          <div>Health at close: <strong style="color:#1d1d1f">${h.health_at_close || '--'}</strong></div>
        </div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">
      ${_detailCell('Entry',    fmt(h.entry_price),   '#0071e3')}
      ${_detailCell('Exit',     fmt(h.exit_price),    h.pnl_color || outcomeColor)}
      ${_detailCell('Stop',     fmt(h.sl_price),      '#ff3b30')}
      ${_detailCell('TP1',      fmt(h.tp1_price),     '#34c759')}
      ${_detailCell('TP2',      fmt(h.tp2_price),     '#34c759')}
      ${_detailCell('Risk',     fmt(h.risk_amt),      '#ff3b30')}
      ${_detailCell('Size',     fmt(h.position_size), '#1d1d1f')}
      ${_detailCell('Leverage', (h.leverage || '--') + 'x', '#1d1d1f')}
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
      <div style="background:rgba(0,0,0,0.04);border-radius:10px;padding:12px">
        <div class="section-label" style="margin-bottom:4px">Opened</div>
        <div style="font-size:12px;color:#1d1d1f;font-weight:500">${fmtDate(h.opened_at)}</div>
      </div>
      <div style="background:rgba(0,0,0,0.04);border-radius:10px;padding:12px">
        <div class="section-label" style="margin-bottom:4px">Closed</div>
        <div style="font-size:12px;color:#1d1d1f;font-weight:500">${fmtDate(h.closed_at)}</div>
      </div>
    </div>

    ${(h.balance_at_open || h.tier_at_open) ? `
    <div style="background:rgba(0,113,227,0.04);border:1px solid rgba(0,113,227,0.12);border-radius:10px;padding:12px">
      <div class="section-label" style="margin-bottom:6px">Account at Open</div>
          <div style="font-size:11px;color:#6e6e73;line-height:2">
            ${h.balance_at_open ? `<div>Balance: <strong style="color:#1d1d1f">$${parseFloat(h.balance_at_open).toFixed(2)}</strong></div>` : ''}
            ${h.tier_at_open    ? `<div>Tier: <strong style="color:#1d1d1f">${h.tier_at_open}</strong></div>` : ''}
          </div>
        </div>` : ''}
  `

  overlay.classList.remove('hidden')
  overlay.classList.add('flex')
}

function _detailCell(label, value, color) {
  return `
    <div style="background:rgba(0,0,0,0.04);border-radius:10px;padding:10px 12px">
      <div class="section-label" style="margin-bottom:4px">${label}</div>
      <div style="font-family:monospace;font-weight:600;font-size:13px;color:${color}">${value}</div>
    </div>`
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

    const bg      = enabled ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.04)'
    const border  = enabled ? `1px solid ${gc}30` : '1px solid rgba(0,0,0,0.08)'
    const opacity = enabled ? '1' : '0.5'
    const dot     = hasSignal ? `<span style="width:5px;height:5px;border-radius:50%;background:${gc};display:inline-block;margin-left:3px;vertical-align:middle"></span>` : ''

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

  const gc      = c.grade_color || '#6e6e73'
  const volStr  = c.volume_24h
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