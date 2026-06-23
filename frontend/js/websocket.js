'use strict'

const WS_DASHBOARD_URL = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/dashboard`

let _dashSocket    = null
let _dashReconnect = null

const _binanceWsSockets = {}
const _priceHistory     = {}
const MAX_PRICE_POINTS  = 60


function startDashboardSocket() {
  if (_dashSocket && (_dashSocket.readyState === WebSocket.CONNECTING || _dashSocket.readyState === WebSocket.OPEN)) return

  _dashSocket = new WebSocket(WS_DASHBOARD_URL)

  _dashSocket.onopen = () => {
    setWsStatus(true)
    console.log('Dashboard WS connected')
  }

  _dashSocket.onmessage = (event) => {
    try {
      const d = JSON.parse(event.data)

      if (d.type === 'ft_update') {
        applyFtUpdate(d)
        return
      }

      if (d.type === 'dashboard') {
        applyAndRender(d)
        return
      }

      if (d.header !== undefined || d.radar !== undefined) {
        applyAndRender(d)
        return
      }

      if (
        d.type === 'trade_opened'   ||
        d.type === 'trade_closed'   ||
        d.type === 'health_changed' ||
        d.type === 'scan_complete'
      ) {
        fetchDashboard()
        return
      }

    } catch(e) {
      console.error('Dashboard WS parse error:', e)
    }
  }

  _dashSocket.onclose = () => {
    _cleanupDash()
    setWsStatus(false)
    _dashReconnect = setTimeout(startDashboardSocket, 3000)
  }

  _dashSocket.onerror = () => {
    _dashSocket?.close()
  }
}


function stopDashboardSocket() {
  _cleanupDash()
}


function _cleanupDash() {
  clearTimeout(_dashReconnect)
  _dashReconnect = null
  if (_dashSocket) {
    _dashSocket.onclose = null
    _dashSocket.close()
    _dashSocket = null
  }
}


async function _backfillPriceHistory(symbol) {
  try {
    const key = symbol.toLowerCase()
    if (_priceHistory[key] && _priceHistory[key].length >= 10) return

    const url = `/api/proxy/binance/aggTrades?symbol=${symbol}&limit=100`
    const res = await fetch(url)
    if (!res.ok) return

    const trades = await res.json()
    if (!Array.isArray(trades) || !trades.length) return

    if (!_priceHistory[key]) _priceHistory[key] = []

    const existing = new Set(_priceHistory[key].map(h => h.time))

    trades.forEach(t => {
      const price = parseFloat(t.p)
      const time  = t.T
      if (price && time && !existing.has(time)) {
        _priceHistory[key].push({ time, price })
      }
    })

    _priceHistory[key].sort((a, b) => a.time - b.time)

    if (_priceHistory[key].length > MAX_PRICE_POINTS) {
      _priceHistory[key] = _priceHistory[key].slice(-MAX_PRICE_POINTS)
    }

    const cards = document.querySelectorAll(`[data-symbol="${symbol}"]`)
    cards.forEach(card => {
      const tradeId = card.id.replace('ft-trade-', '')
      const sparkEl = document.getElementById(`sparkline-${tradeId}`)
      if (sparkEl) {
        const html = _buildSparkline(symbol)
        sparkEl.innerHTML = html
      }
    })

  } catch(e) {
    console.warn(`Backfill failed for ${symbol}:`, e)
  }
}


function startBinanceTickerWs(symbol) {
  const key = symbol.toLowerCase()
  if (_binanceWsSockets[key]) return

  _backfillPriceHistory(symbol)

  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/proxy/binance/price?symbol=${symbol}`)
      if (!res.ok) return
      const data = await res.json()
      if (!data.price) return

      const price = parseFloat(data.price)
      const time  = Date.now()

      if (!_priceHistory[key]) _priceHistory[key] = []
      _priceHistory[key].push({ time, price })
      if (_priceHistory[key].length > MAX_PRICE_POINTS) {
        _priceHistory[key].shift()
      }

      updateTradeCardPrice(symbol, price)

    } catch(e) {}
  }, 1000)

  _binanceWsSockets[key] = {
    readyState: 1,
    close:      () => clearInterval(interval),
    onclose:    null
  }
}


function stopBinanceTickerWs(symbol) {
  const key = symbol.toLowerCase()
  if (_binanceWsSockets[key]) {
    _binanceWsSockets[key].close()
    delete _binanceWsSockets[key]
  }
  delete _priceHistory[key]
}


function stopAllBinanceWs() {
  Object.keys(_binanceWsSockets).forEach(key => {
    try {
      _binanceWsSockets[key].close()
    } catch(e) {}
  })
  Object.keys(_binanceWsSockets).forEach(k => delete _binanceWsSockets[k])
  Object.keys(_priceHistory).forEach(k => delete _priceHistory[k])
}


function getPriceHistory(symbol) {
  return _priceHistory[symbol.toLowerCase()] || []
}