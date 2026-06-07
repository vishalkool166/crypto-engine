'use strict'

const API = window.location.origin + '/api'

async function fetchDashboard() {
  try {
    const res = await fetch(`${API}/dashboard`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const data = await res.json()
    const { stateChanged, tradeChanged, healthChanged } = applyDashboard(data)

    renderHeader(data.header)
    renderStatusBar(data)
    renderRisk(data.risk)

    if (stateChanged || tradeChanged || healthChanged) {
      renderTrade(data.trade, data.state)
      syncConnectionMode(data.state)
    }

    renderRadar(data.radar)
    renderSignalQueue(data.queue)
    renderPerformance(data.performance)

    if ((data.history?.length || 0) !== S.lastHistoryLen) {
      S.lastHistoryLen = data.history?.length || 0
      renderHistory(data.history)
      renderCharts(data.history)
    }

    setApiStatus(true)

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
    const res  = await fetch(`${API}/scan`)
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

async function closeTrade() {
  const btn = $id('close-trade-btn')
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Closing...' }

  try {
    const res    = await fetch(`${API}/trade/close`, { method: 'POST' })
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
  const res  = await fetch(`${API}/analyze/${coin}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return await res.json()
}