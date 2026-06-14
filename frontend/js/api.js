'use strict'

const API = window.location.origin + '/api'

let _binanceCoins    = []
let _binanceLoaded   = false
let _binanceLoading  = false

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


async function loadBinanceCoins() {
  if (_binanceLoaded || _binanceLoading) return
  _binanceLoading = true

  try {
    const res  = await fetch(`${API}/coins/all-binance`, { headers: _authHeaders() })
    const data = await res.json()
    _binanceCoins  = data.coins || []
    _binanceLoaded = true
  } catch(e) {
    console.error('Failed to load Binance coins:', e)
  } finally {
    _binanceLoading = false
  }
}


function onCoinSearch(val) {
  const q    = val.trim().toUpperCase()
  const wrap = $id('coin-suggestions')
  if (!wrap) return

  if (!q || q.length < 1) {
    wrap.style.display = 'none'
    return
  }

  const existing = new Set((S.data?.coin_universe || []).map(c => c.coin))

  const matches = _binanceCoins
    .filter(c => c.coin.startsWith(q) || c.coin.includes(q))
    .slice(0, 12)

  if (!matches.length) {
    wrap.style.display = 'none'
    return
  }

  wrap.style.display = 'block'
  wrap.innerHTML = matches.map((c, i) => {
    const inUniverse = existing.has(c.coin)
    const volStr     = c.volume >= 1e9
      ? '$' + (c.volume / 1e9).toFixed(1) + 'B'
      : c.volume >= 1e6
        ? '$' + (c.volume / 1e6).toFixed(0) + 'M'
        : '--'

    return `
      <div
        id="suggestion-${i}"
        onclick="selectCoinSuggestion('${c.coin}')"
        style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;cursor:pointer;transition:background 0.1s;border-bottom:1px solid rgba(0,0,0,0.04)"
        onmouseover="this.style.background='rgba(0,113,227,0.06)'"
        onmouseout="this.style.background=''">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-weight:600;font-size:13px;color:#1d1d1f">${c.coin}</span>
          <span style="font-size:10px;color:#6e6e73">USDT</span>
          ${inUniverse ? '<span style="font-size:10px;color:#34c759;font-weight:600">✓ added</span>' : ''}
        </div>
        <span style="font-size:10px;font-family:monospace;color:#6e6e73">${volStr}</span>
      </div>`
  }).join('')
}


function onCoinInputKey(e) {
  if (e.key === 'Enter') {
    const val = e.target.value.trim()
    if (val) selectCoinSuggestion(val.toUpperCase().replace('USDT', ''))
  }
  if (e.key === 'Escape') {
    closeCoinSuggestions()
  }
}


async function selectCoinSuggestion(coin) {
  const inp = $id('coin-add-input')
  if (inp) inp.value = coin
  closeCoinSuggestions()
  await addCoin(coin)
}


function closeCoinSuggestions() {
  const wrap = $id('coin-suggestions')
  if (wrap) wrap.style.display = 'none'
}


async function addCoin(coinOverride = null) {
  const inp  = $id('coin-add-input')
  const coin = (coinOverride || (inp ? inp.value : '')).trim().toUpperCase().replace('USDT', '').replace('/', '')
  if (!coin) return

  const btn = document.querySelector('button[onclick="addCoin()"]')
  if (btn) { btn.disabled = true; btn.textContent = '⏳...' }

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
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '+ Add' }
  }
}


async function showSyncModal() {
  const title   = $id('modal-title')
  const body    = $id('modal-body')
  const overlay = $id('modal-overlay')

  title.textContent = '🔄 Sync Coins from Binance'
  body.innerHTML = `
    <div style="text-align:center;padding:32px 0;color:#6e6e73;font-size:12px">
      <div class="spinner" style="margin:0 auto 12px"></div>
      Fetching top volume coins...
    </div>`

  overlay.classList.remove('hidden')
  overlay.classList.add('flex')

  try {
    const res  = await fetch(`${API}/coins/suggest-sync`, { headers: _authHeaders() })
    const data = await res.json()
    const suggested = data.suggested || []
    const isEmpty   = data.is_empty  || false

    if (!suggested.length) {
      body.innerHTML = `
        <div style="text-align:center;padding:32px 0;color:#6e6e73;font-size:13px">
          ✅ Your coin universe is already up to date!<br>
          <span style="font-size:11px">No new top-volume coins to add.</span>
        </div>`
      return
    }

    const checkboxes = suggested.map((c, i) => `
      <label style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-radius:8px;background:rgba(0,0,0,0.03);cursor:pointer;margin-bottom:4px">
        <div style="display:flex;align-items:center;gap:10px">
          <input type="checkbox" id="sync-coin-${i}" value="${c.coin}" checked
                 style="width:15px;height:15px;accent-color:#0071e3;cursor:pointer">
          <span style="font-weight:600;font-size:13px;color:#1d1d1f">${c.coin}</span>
          <span style="font-size:10px;color:#6e6e73">USDT Perpetual</span>
        </div>
        <span style="font-size:11px;font-family:monospace;color:#6e6e73">${c.vol_str}</span>
      </label>`
    ).join('')

    const headerText = isEmpty
      ? 'Your coin universe is empty. Select coins to add from top Binance volume:'
      : 'These are the top volume coins not yet in your universe. Select which ones to add:'

    body.innerHTML = `
      <p style="font-size:13px;color:#6e6e73;margin-bottom:16px;line-height:1.6">${headerText}</p>
      <div style="margin-bottom:16px;max-height:300px;overflow-y:auto">
        ${checkboxes}
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <button onclick="document.querySelectorAll('[id^=sync-coin-]').forEach(c=>c.checked=true)"
                style="font-size:12px;color:#0071e3;background:none;border:none;cursor:pointer;font-weight:600">
          Select All
        </button>
        <button onclick="document.querySelectorAll('[id^=sync-coin-]').forEach(c=>c.checked=false)"
                style="font-size:12px;color:#6e6e73;background:none;border:none;cursor:pointer">
          Deselect All
        </button>
      </div>
      <div style="display:flex;gap:8px">
        <button onclick="closeModal()"
                style="flex:1;padding:12px;border-radius:10px;border:1px solid rgba(0,0,0,0.1);background:rgba(0,0,0,0.04);font-weight:600;font-size:13px;cursor:pointer">
          Cancel
        </button>
        <button onclick="confirmSyncCoins()"
                style="flex:1;padding:12px;border-radius:10px;border:none;background:#0071e3;color:white;font-weight:600;font-size:13px;cursor:pointer">
          Add Selected Coins
        </button>
      </div>`

  } catch(e) {
    body.innerHTML = `
      <div style="text-align:center;padding:32px 0;color:#ff3b30;font-size:13px">
        ❌ Failed to fetch suggestions: ${e.message}
      </div>`
  }
}


async function confirmSyncCoins() {
  const checkboxes = document.querySelectorAll('[id^=sync-coin-]:checked')
  const coins      = [...checkboxes].map(c => c.value)

  if (!coins.length) {
    toast('⚠️ No coins selected', '', 'warning')
    return
  }

  closeModal()

  try {
    const res  = await fetch(`${API}/coins/add-bulk`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body:    JSON.stringify({ coins })
    })
    const data = await res.json()
    if (data.success) {
      toast(`✅ ${data.added?.length || 0} coins added`, data.added?.join(', ') || '', 'success', 6000)
      await fetchDashboard()
    } else {
      toast('❌ Sync failed', '', 'error')
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