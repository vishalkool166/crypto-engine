'use strict'

const WS_PRICE_URL     = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/price`
const WS_DASHBOARD_URL = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/dashboard`

let _priceSocket     = null
let _dashSocket      = null
let _pingTimer       = null
let _priceReconnect  = null
let _dashReconnect   = null


function startPriceSocket() {
  if (_priceSocket && (_priceSocket.readyState === WebSocket.CONNECTING || _priceSocket.readyState === WebSocket.OPEN)) return
  _cleanupPrice()

  _priceSocket = new WebSocket(WS_PRICE_URL)

  _priceSocket.onopen = () => {
    setWsStatus(true)
    _pingTimer = setInterval(() => {
      if (_priceSocket?.readyState === WebSocket.OPEN) {
        _priceSocket.send('ping')
      }
    }, 30000)
  }

  _priceSocket.onmessage = (event) => {
    try {
      const d = JSON.parse(event.data)
      if (d.type === 'price') applyPriceUpdate(d)
    } catch(e) {
      console.error('Price WS parse error:', e)
    }
  }

  _priceSocket.onclose = () => {
    _cleanupPrice()
    setWsStatus(false)
    if (S.data?.state !== 'idle') {
      _priceReconnect = setTimeout(startPriceSocket, 3000)
    }
  }

  _priceSocket.onerror = () => {
    _priceSocket?.close()
  }
}


function stopPriceSocket() {
  _cleanupPrice()
  setWsStatus(false)
}


function _cleanupPrice() {
  clearInterval(_pingTimer)
  clearTimeout(_priceReconnect)
  _pingTimer      = null
  _priceReconnect = null
  if (_priceSocket) {
    _priceSocket.onclose = null
    _priceSocket.close()
    _priceSocket = null
  }
}


function startDashboardSocket() {
  if (_dashSocket && (_dashSocket.readyState === WebSocket.CONNECTING || _dashSocket.readyState === WebSocket.OPEN)) return

  _dashSocket = new WebSocket(WS_DASHBOARD_URL)

  _dashSocket.onopen = () => {
    console.log('Dashboard WS connected')
  }

  _dashSocket.onmessage = (event) => {
    try {
      const d = JSON.parse(event.data)

      if (d.type === 'dashboard') {
        applyAndRender(d)
        return
      }

      if (d.type === 'ping') {
        return
      }

      if (
        d.type === 'trade_opened' ||
        d.type === 'trade_closed' ||
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


function syncConnectionMode(state) {
  if (state !== 'idle') {
    startPriceSocket()
  } else {
    stopPriceSocket()
  }
}


function applyPriceUpdate(d) {
  const trades = S.data?.trades || []
  const trade  = trades.find(t => t.id === d.trade_id) || trades[0]
  if (!trade) return

  const cardId = `trade-card-${d.trade_id || (trade ? trade.id : '')}`
  const card   = $id(cardId)

  if (card) {
    const curEl    = card.querySelector('[data-current-price]')
    const moveEl   = card.querySelector('[data-move-pct]')
    const pnlEl    = card.querySelector('[data-pnl]')
    const pnlPctEl = card.querySelector('[data-pnl-pct]')

    if (curEl)    { curEl.textContent    = d.price;    curEl.style.color    = d.current_color }
    if (moveEl)   { moveEl.textContent   = d.move_pct; moveEl.style.color   = d.move_color }
    if (pnlEl)    { pnlEl.textContent    = d.pnl;      pnlEl.style.color    = d.pnl_color }
    if (pnlPctEl) { pnlPctEl.textContent = d.pnl_pct;  pnlPctEl.style.color = d.pnl_color }
  }

  $set('h-today-pnl', { text: d.pnl, color: d.pnl_color })

  if (d.price_raw && trade) {
    const entry  = trade.entry_price_raw  || 0
    const sl     = trade.sl_price_raw     || 0
    const isLong = trade.direction === 'LONG'

    const total = Math.abs(entry - sl)
    let pct     = 0
    let inProfit = false

    if (total > 0) {
      pct      = isLong
        ? (d.price_raw - entry) / total * 100
        : (entry - d.price_raw) / total * 100
      inProfit = pct > 0
      pct      = Math.max(-100, Math.min(100, Math.round(pct)))
    }

    const fillEl = card ? card.querySelector('[data-prog-fill]') : null
    if (fillEl) {
      fillEl.style.width      = Math.abs(pct) / 2 + '%'
      fillEl.style.left       = inProfit ? '50%' : 'auto'
      fillEl.style.right      = inProfit ? 'auto' : '50%'
      fillEl.style.background = inProfit ? '#34c759' : '#ff3b30'
    }

    const ladderNow = card ? card.querySelector('.ladder-now span:nth-child(2)') : null
    if (ladderNow) ladderNow.textContent = d.price
  }
}