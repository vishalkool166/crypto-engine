'use strict'

const WS_URL = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/price`

let _socket   = null
let _pingTimer = null
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
  _pingTimer      = null
  _reconnectTimer = null
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

  $set('ts-current',    { text: d.price,    color: d.current_color })
  $set('ts-move',       { text: d.move_pct, color: d.move_color })
  $set('trade-pnl',     { text: d.pnl,      color: d.pnl_color })
  $set('trade-pnl-pct', { text: d.pnl_pct,  color: d.pnl_color })

  const hpnl = $id('h-today-pnl')
  if (hpnl) { hpnl.textContent = d.pnl; hpnl.style.color = d.pnl_color }
}