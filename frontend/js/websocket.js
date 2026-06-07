'use strict'

const WS_URL = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/price`

let _socket        = null
let _pingTimer     = null
let _reconnectTimer = null

function startPriceSocket() {
  if (_socket?.readyState === WebSocket.OPEN) return

  _socket = new WebSocket(WS_URL)

  _socket.onopen = () => {
    setWsStatus(true)
    _pingTimer = setInterval(() => {
      if (_socket?.readyState === WebSocket.OPEN) _socket.send('ping')
    }, 30000)
  }

  _socket.onmessage = (event) => {
    try {
      const d = JSON.parse(event.data)
      if (d.type === 'price') applyPriceUpdate(d)
    } catch(e) {}
  }

  _socket.onclose = () => {
    _cleanup()
    setWsStatus(false)
    if (S.data?.state !== 'idle') {
      _reconnectTimer = setTimeout(startPriceSocket, 3000)
    }
  }

  _socket.onerror = () => _socket?.close()
}

function stopPriceSocket() {
  _cleanup()
  setWsStatus(false)
}

function _cleanup() {
  clearInterval(_pingTimer)
  clearTimeout(_reconnectTimer)
  _pingTimer       = null
  _reconnectTimer  = null
  if (_socket) {
    _socket.onclose = null
    _socket.close()
    _socket = null
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
  const trade = S.data?.trade
  if (!trade) return

  // Price ticker
  $set('ts-current',    { text: d.price,    color: d.current_color })
  $set('ts-move',       { text: d.move_pct, color: d.move_color })

  // PnL
  $set('trade-pnl',     { text: d.pnl,      color: d.pnl_color })
  $set('trade-pnl-pct', { text: d.pnl_pct,  color: d.pnl_color })

  // Header
  $set('h-today-pnl',   { text: d.pnl,      color: d.pnl_color })

  // Progress bar
  if (d.price_raw) {
    const pct = _calcProgressPct(d.price_raw, trade)
    $set('prog-fill',   { width: pct, bg: trade.progress?.color })
    $set('prog-status', { text: `${pct}% to TP1` })
  }
}

function _calcProgressPct(price, trade) {
  const clean  = s => parseFloat((s || '0').toString().replace(/[$,]/g, '')) || 0
  const entry  = clean(trade.entry_price)
  const sl     = clean(trade.sl_price)
  const tp1    = clean(trade.tp1_price)
  const isLong = trade.direction === 'LONG'
  const total  = Math.abs(tp1 - sl)
  if (total === 0) return 0
  const pct = isLong
    ? (price - sl) / total * 100
    : (sl - price) / total * 100
  return Math.max(0, Math.min(100, Math.round(pct)))
}