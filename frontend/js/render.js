'use strict'

function renderAll() {
  const d = S.data
  if (!d) return
  renderHeader(d.header)
  renderStatusBar(d)
  renderTrade(d.trade, d.state)
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
  $set('h-capital', { text: h.capital })

  $set('h-today-pnl',    { text: h.today_pnl,  color: h.today_pnl_color })
  $set('h-trades-left',  { text: h.trades_left, color: h.trades_left_color })
  $set('h-winrate',      { text: h.win_rate,    color: h.win_rate_color })

  const badge = $id('mode-badge')
  if (badge) {
    badge.textContent = h.mode
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

  if (d.state === 'idle') {
    if (dot)  dot.style.background = '#6e6e73'
    if (text) text.textContent = 'IDLE — Watching markets'
    if (sub)  sub.textContent  = 'Auto-executes A/A+ signals'
  } else {
    const t = d.trade
    if (dot)  dot.style.background = '#34c759'
    if (text) text.textContent = t ? `IN TRADE — ${t.coin} ${t.direction}` : 'IN TRADE'
    if (sub)  sub.textContent  = t ? `Entry: ${t.entry_price} · SL: ${t.sl_price} · Grade ${t.grade}` : '--'
  }

  if (d.last_scan && d.last_scan !== '--') {
    if (lst)  lst.textContent  = d.last_scan
    if (ilst) ilst.textContent = d.last_scan
  }
}

function renderTrade(t, state) {
  const idleEl   = $id('trade-idle')
  const activeEl = $id('trade-active')
  if (!idleEl || !activeEl) return

  if (state === 'idle' || !t) {
    idleEl.classList.remove('hidden')
    activeEl.classList.add('hidden')
    return
  }

  idleEl.classList.add('hidden')
  activeEl.classList.remove('hidden')

  const header = $id('trade-header')
  if (header) header.style.background = t.header_bg

  $set('trade-coin', { text: t.coin, color: t.dir_color })
  $badge('trade-dir-badge',      `${t.dir_emoji} ${t.direction}`, t.dir_color,   t.dir_border)
  $badge('trade-grade-badge',    `Grade ${t.grade}`,              t.grade_color, t.grade_color)
  $badge('trade-phase-badge',    t.phase_badge,                   t.phase_color, t.phase_color)
  $badge('trade-health-badge',   `${t.health_emoji} ${t.health_state}`, t.health_color, t.health_color)
  $set('trade-duration-badge',   { text: `${t.duration} open` })
  $set('trade-state-label',      { text: `State: ${t.state} · Opened: ${t.opened_at || '--'}` })
  $set('trade-pnl',              { text: t.pnl,     color: t.pnl_color })
  $set('trade-pnl-pct',          { text: t.pnl_pct, color: t.pnl_color })

  const prog = t.progress
  if (prog) {
    $set('prog-fill',      { width: prog.pct, bg: prog.color })
    $set('prog-sl-label',  { text: prog.left_label })
    $set('prog-mid-label', { text: prog.mid_label })
    $set('prog-tp1-label', { text: prog.right_label })
    $set('prog-status',    { text: prog.label, color: prog.color })
    $set('prog-phase',     { text: prog.phase_label })
  }

  $set('ts-current',  { text: t.current_price, color: t.current_color })
  $set('ts-move',     { text: t.move_pct,      color: t.move_color })
  $set('ts-entry',    { text: t.entry_price })
  $set('ts-sl-label', { text: `To ${t.sl_label}`, color: t.sl_color })
  $set('ts-to-sl',    { text: t.dist_to_sl,    color: t.sl_color })
  $set('ts-to-tp1',   { text: t.dist_to_tp1,   color: C.green })
  $set('ts-risk',     { text: t.risk_amt,       color: C.red })
  $set('ts-tp1-rew',  { text: t.tp1_reward,     color: C.green })
  $set('ts-pos',      { text: t.position_size })
  $set('ts-rr',       { text: t.rr_ratio })

  const thesisSection = $id('trade-thesis-section')
  if (t.thesis && thesisSection) {
    thesisSection.classList.remove('hidden')
    $set('trade-thesis-text', { text: t.thesis })
    $set('trade-risk-text',   { text: t.risk_thesis || 'No risk factors identified.' })
  }

  const healthSection = $id('trade-health-section')
  const healthDetail  = $id('trade-health-detail')
  if (healthSection && healthDetail) {
    const hasDetail = (t.health_warnings?.length || 0) > 0 || (t.health_failures?.length || 0) > 0
    if (hasDetail) {
      healthSection.classList.remove('hidden')
      const lines = []
      if (t.health_failures?.length) {
        lines.push('<span style="font-weight:600;color:#ff3b30">Invalidated:</span>')
        t.health_failures.forEach(f => lines.push(`✘ ${f}`))
      }
      if (t.health_warnings?.length) {
        lines.push('<span style="font-weight:600;color:#e8820c">Warnings:</span>')
        t.health_warnings.forEach(w => lines.push(`⚠ ${w}`))
      }
      if (t.health_checks?.length && t.health_state === 'HEALTHY') {
        t.health_checks.forEach(c => lines.push(`✔ ${c}`))
      }
      healthDetail.innerHTML = lines.join('<br>')
    } else {
      healthSection.classList.add('hidden')
    }
  }

  renderLadder(t.ladder)
}

function renderLadder(ladder) {
  const wrap = $id('ladder-rows')
  if (!wrap || !ladder) return

  wrap.innerHTML = ladder.map(row => {
    if (!row) return ''

    if (row.is_current) {
      return `
        <div class="ladder-now" style="display:flex;align-items:center;gap:12px;padding:10px 12px">
          <span style="font-size:10px;font-weight:700;width:40px;flex-shrink:0;color:#0071e3">NOW</span>
          <span style="flex:1;font-family:monospace;font-weight:700;font-size:14px;color:#0071e3">${row.price}</span>
          <span style="font-size:10px;font-weight:600;padding:2px 8px;border-radius:100px;${row.badge_style}">${row.badge}</span>
        </div>`
    }

    const opacity = row.is_hit ? 'opacity:0.4;' : ''
    const strike  = row.is_hit ? 'text-decoration:line-through;' : ''

    return `
      <div style="${opacity}display:flex;align-items:center;gap:12px;padding:8px 12px;border-radius:8px;background:${row.color}08;border:1px solid ${row.color}18">
        <span style="font-size:10px;font-weight:600;width:40px;flex-shrink:0;color:${row.color}">${row.label}</span>
        <span style="flex:1;font-family:monospace;font-weight:600;font-size:14px;${strike}color:${row.color}">${row.price}</span>
        <span style="font-family:monospace;font-size:10px;width:56px;text-align:right;font-weight:500;color:${row.color}80">${row.dist}</span>
        <span style="font-size:10px;font-weight:600;padding:2px 8px;border-radius:100px;${row.badge_style}">${row.badge}</span>
      </div>`
  }).join('')
}

function _nowIST() {
  return new Date().toLocaleTimeString('en-IN', {
    hour:     '2-digit',
    minute:   '2-digit',
    hour12:   true,
    timeZone: 'Asia/Kolkata'
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

  // Clear shimmer placeholders on first real render
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
        <div style="display:flex;align-items:center;gap:6px">
          ${q.confidence_label ? `<span style="font-size:10px;color:${q.grade_color}80">${q.confidence_label}</span>` : ''}
          <span style="font-size:12px;font-weight:700;padding:2px 8px;border-radius:100px;color:${q.grade_color};background:${q.grade_color}15">
            ${q.grade} · ${q.score}
          </span>
        </div>
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
      ${q.no_trade_reason ? `<div class="no-trade-block" style="margin-bottom:8px">${q.no_trade_reason}</div>` : ''}

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
  $set('risk-pnl-bar',    { width: r.pnl_bar_pct,    bg: r.pnl_color === C.green ? C.green : C.red })
  $set('risk-pnl-val',    { text: r.pnl_label, color: r.pnl_color })
  $set('risk-remaining-trades', { text: r.remaining_trades })
  $set('risk-remaining-loss',   { text: r.remaining_loss })

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