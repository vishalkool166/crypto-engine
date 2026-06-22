'use strict'

const API = window.location.origin + '/api'

function _authHeaders() {
  const apiKey = window._apiKey || ''
  return apiKey ? { 'X-API-Key': apiKey } : {}
}


function applyAndRender(data) {
  applyDashboard(data)
  renderHeader(data.header)
  renderStatusBar(data)
  renderRadar(data.radar)
  renderSignalQueue(data.queue)
  renderPerformance(data.performance)
  renderCoinUniverse(data.coin_universe)
  renderModeToggle(data.header?.mode?.toLowerCase() || 'paper')

  if ((data.history?.length || 0) !== S.lastHistoryLen) {
    S.lastHistoryLen = data.history?.length || 0
    renderHistory(data.history)
    renderCharts(data.history)
  }

  setApiStatus(true)
}


function applyFtUpdate(data) {
  if (data.status !== undefined) {
    renderFtTrades(data.status)
    renderFtBotStatus(data.status, data.bot_state)

    if (Array.isArray(data.status)) {
      data.status.forEach(t => {
        const current  = parseFloat(t.current_rate || 0)
        const entry    = parseFloat(t.open_rate || 0)
        const pnl      = parseFloat(t.profit_abs || 0)
        const pnlPct   = parseFloat(t.profit_ratio || 0) * 100
        const pnlColor = pnl >= 0 ? '#248a3d' : '#c0392b'
        const pnlStr   = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(4)
        const pnlPctStr = (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%'
        const movePct  = entry > 0 ? ((current - entry) / entry * 100) : 0
        const moveStr  = (movePct >= 0 ? '+' : '') + movePct.toFixed(2) + '%'
        const moveColor = movePct >= 0 ? '#248a3d' : '#c0392b'

        const card = $id(`ft-trade-${t.trade_id}`)
        if (card) {
          const pnlEl     = card.querySelector('[data-pnl]')
          const pnlPctEl  = card.querySelector('[data-pnl-pct]')
          const curEl     = card.querySelector('[data-current]')
          const moveEl    = card.querySelector('[data-move]')

          if (pnlEl)    { pnlEl.textContent    = pnlStr;                        pnlEl.style.color    = pnlColor }
          if (pnlPctEl) { pnlPctEl.textContent = pnlPctStr;                     pnlPctEl.style.color = pnlColor }
          if (curEl)    { curEl.textContent     = '$' + current.toFixed(4);      curEl.style.color    = pnlColor }
          if (moveEl)   { moveEl.textContent    = moveStr;                       moveEl.style.color   = moveColor }
        }

        updateChartPrice(`chart-${t.trade_id}`, current)
      })
    }
  }

  if (data.profit && Object.keys(data.profit).length) {
    renderFtProfit(data.profit)
  }

  if (data.balance && Object.keys(data.balance).length) {
    renderFtHeader(data.balance, data.profit)
  }
}


async function fetchDashboard() {
  try {
    const res = await fetch(`${API}/dashboard`, { headers: _authHeaders() })
    if (res.status === 401) {
      window.location.href = '/login.html'
      return
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    applyAndRender(data)
  } catch(e) {
    console.error('Dashboard fetch error:', e)
    setApiStatus(false)
  }
}


function setApiStatus(ok) {
  const dot  = $id('status-dot')
  const text = $id('api-error-banner')
  if (dot)  dot.style.background = ok ? null : '#ff3b30'
  if (text) text.style.display   = ok ? 'none' : 'flex'
}


async function triggerScan() {
  if (S.scanning) return

  S.scanning = true
  const btn  = $id('scan-btn')
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Scanning...' }

  renderStatusBar(S.data)
  toast('🔍 Scan Started', 'Analyzing all coins — 1-2 min', 'info', 3000)

  try {
    const res  = await fetch(`${API}/scan`, { headers: _authHeaders() })
    if (res.status === 401) { window.location.href = '/login.html'; return }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()

    const results   = data.results || []
    const tradeable = results.filter(r =>
      (r.grade === 'A+' || r.grade === 'A') &&
      (r.direction === 'LONG' || r.direction === 'SHORT')
    )
    const aplus = tradeable.filter(r => r.grade === 'A+')
    const a     = tradeable.filter(r => r.grade === 'A')

    if (aplus.length) {
      toast(
        `🏆 ${aplus.length} A+ Signal${aplus.length > 1 ? 's' : ''}!`,
        aplus.map(r => `${r.coin} ${r.direction}`).join(', '),
        'success', 8000
      )
    } else if (a.length) {
      toast(
        `✅ ${a.length} Grade A Signal${a.length > 1 ? 's' : ''}`,
        a.map(r => `${r.coin} ${r.direction}`).join(', '),
        'info', 6000
      )
    } else {
      toast('😴 No Tradeable Signals', 'No A/A+ setups this scan', 'warning', 4000)
    }

    await fetchDashboard()

  } catch(e) {
    console.error('Scan error:', e)
    toast('❌ Scan Failed', e.message, 'error', 5000)
  } finally {
    S.scanning = false
    if (btn) { btn.disabled = false; btn.textContent = '🔍 Scan Now' }
    renderStatusBar(S.data)
  }
}


async function fetchCoinDetail(coin) {
  const res = await fetch(`${API}/analyze/${coin}`, { headers: _authHeaders() })
  if (res.status === 401) { window.location.href = '/login.html'; return null }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json()
}


async function addCoin(coinOverride = null) {
  const inp  = $id('coin-add-input')
  const coin = (coinOverride || (inp ? inp.value : '')).trim().toUpperCase().replace('USDT', '').replace('/', '')
  if (!coin) return

  try {
    const res  = await fetch(`${API}/coins/add`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body:    JSON.stringify({ coin })
    })
    const data = await res.json()
    if (data.success) {
      toast(`✅ ${coin} added`, data.message || 'Coin added to universe', 'success')
      if (inp) inp.value = ''
      await fetchDashboard()
    } else {
      toast(`❌ ${coin} rejected`, data.reason || 'Error', 'error', 6000)
    }
  } catch(e) {
    toast('❌ Error', e.message, 'error')
  }
}


async function toggleCoin(coin, enabled) {
  try {
    const res  = await fetch(`${API}/coins/toggle`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body:    JSON.stringify({ coin, enabled })
    })
    const data = await res.json()
    if (data.success) {
      toast(`${enabled ? '✅' : '⏸'} ${coin}`, enabled ? 'Enabled' : 'Disabled', 'info')
      await fetchDashboard()
    } else {
      toast('❌ Failed', data.reason || 'Error', 'error')
    }
  } catch(e) {
    toast('❌ Error', e.message, 'error')
  }
}


async function deleteCoin(coin) {
  if (!confirm(`Remove ${coin} from coin universe?\n\nThis permanently deletes it. You can re-add it later.`)) return

  try {
    const res  = await fetch(`${API}/coins/${coin}`, {
      method:  'DELETE',
      headers: _authHeaders()
    })
    const data = await res.json()
    if (data.success) {
      toast(`🗑️ ${coin} removed`, 'Coin removed from universe', 'info')
      await fetchDashboard()
    } else {
      toast('❌ Failed', data.reason || 'Error', 'error')
    }
  } catch(e) {
    toast('❌ Error', e.message, 'error')
  }
}


let _ftPollTimer = null


async function fetchFtSummary() {
  try {
    const res = await fetch(`${API}/ft/summary`, { headers: _authHeaders() })
    if (!res.ok) return
    const data = await res.json()
    S.ftData = data
    applyFtUpdate(data)
  } catch(e) {
    console.error('FT summary error:', e)
  }
}


function startFtPolling() {
  if (_ftPollTimer) clearInterval(_ftPollTimer)
  _ftPollTimer = setInterval(fetchFtSummary, 30000)
}


function stopFtPolling() {
  if (_ftPollTimer) clearInterval(_ftPollTimer)
  _ftPollTimer = null
}


async function ftStartStop() {
  const btn       = $id('ft-start-btn')
  const badge     = $id('ft-status-badge')
  const isRunning = badge && badge.dataset.running === 'true'

  if (btn) { btn.disabled = true; btn.textContent = '⏳...' }

  try {
    const endpoint = isRunning ? '/ft/stop' : '/ft/start'
    const res = await fetch(`${API}${endpoint}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() }
    })
    const data = await res.json()
    toast(
      isRunning ? '⏹ Bot Stopped' : '▶ Bot Started',
      data.status || '',
      isRunning ? 'warning' : 'success'
    )
    await fetchFtSummary()
  } catch(e) {
    toast('❌ Error', e.message, 'error')
  } finally {
    if (btn) { btn.disabled = false }
  }
}


async function ftForceSell(tradeid) {
  if (!confirm(`Force sell trade #${tradeid}?`)) return
  try {
    const res = await fetch(`${API}/ft/forcesell`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body:    JSON.stringify({ tradeid })
    })
    const data = await res.json()
    toast('✅ Force Sell', `Trade #${tradeid} closed`, 'success')
    await fetchFtSummary()
  } catch(e) {
    toast('❌ Error', e.message, 'error')
  }
}


async function syncOutcomes() {
  toast('🔄 Syncing outcomes...', '', 'info', 3000)
  try {
    const res  = await fetch(`${API}/sync/outcomes`, {
      method:  'POST',
      headers: _authHeaders()
    })
    const data = await res.json()
    toast(
      `✅ Sync Complete`,
      `${data.synced || 0} synced · ${data.unmatched || 0} unmatched`,
      'success'
    )
    await fetchDashboard()
  } catch(e) {
    toast('❌ Sync Failed', e.message, 'error')
  }
}