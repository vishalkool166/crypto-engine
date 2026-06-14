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
  renderRisk(data.risk)
  renderTrades(data.trades, data.state)
  syncConnectionMode(data.state)
  renderRadar(data.radar)
  renderSignalQueue(data.queue)
  renderPerformance(data.performance)
  renderCoinUniverse(data.coin_universe)

  if ((data.history?.length || 0) !== S.lastHistoryLen) {
    S.lastHistoryLen = data.history?.length || 0
    renderHistory(data.history)
    renderCharts(data.history)
  }

  setApiStatus(true)
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


async function closeTrade(tradeId = null) {
  const btn = tradeId
    ? document.querySelector(`[data-close-btn="${tradeId}"]`)
    : $id('close-trade-btn')

  if (btn) { btn.disabled = true; btn.textContent = '⏳ Closing...' }

  try {
    const body = tradeId ? JSON.stringify({ trade_id: tradeId }) : '{}'
    const res  = await fetch(`${API}/trade/close`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body
    })
    const result = await res.json()

    if (result.success) {
      toast('✅ Trade Closed', 'Position closed at market', 'success')
      await fetchDashboard()
    } else {
      toast('❌ Close Failed', result.reason || 'Unknown error', 'error')
      if (btn) { btn.disabled = false; btn.textContent = '🔴 Close Trade at Market' }
    }
  } catch(e) {
    toast('❌ Error', e.message, 'error')
    if (btn) { btn.disabled = false; btn.textContent = '🔴 Close Trade at Market' }
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