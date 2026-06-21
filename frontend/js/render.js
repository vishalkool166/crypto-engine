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
  $set('h-today-pnl',    { text: h.today_pnl,    color: h.today_pnl_color })
  $set('h-winrate',      { text: h.win_rate,      color: h.win_rate_color })
  $set('h-coins-count',  { text: h.coins_count })
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

  const cached_count  = (d.radar || []).length
  const tradeable     = (d.queue || []).length

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
    list.innerHTML = `<div style="text-align:center;padding:32px 0;color:#6e6e73;font-size:12px">No closed signals yet</div>`
    return
  }

  list.innerHTML = history.map(h => `
    <div onclick="showSignalDetail(${JSON.stringify(h).replace(/"/g, '&quot;')})"
         style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;background:rgba(0,0,0,0.03);border-left:2px solid ${h.border_color};cursor:pointer;transition:background 0.15s"
         onmouseover="this.style.background='rgba(0,0,0,0.06)'"
         onmouseout="this.style.background='rgba(0,0,0,0.03)'">
      <span style="font-weight:600;font-size:12px;color:#1d1d1f;width:48px;flex-shrink:0">${h.coin}</span>
      <span style="font-size:12px;font-weight:600;width:40px;flex-shrink:0;color:${h.dir_color}">${h.dir_emoji} ${h.direction}</span>
      <span style="flex:1;font-size:10px;color:#6e6e73;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">Grade ${h.grade} · Score ${h.score_at_entry || '--'}</span>
      <span style="font-family:monospace;font-size:12px;font-weight:600;flex-shrink:0;color:${h.pnl_color}">${h.pnl}</span>
      <span style="font-size:12px;flex-shrink:0">${h.outcome_emoji}</span>
    </div>
  `).join('')
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