'use strict'

const WS_DASHBOARD_URL = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/dashboard`

let _dashSocket    = null
let _dashReconnect = null


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

      if (d.type === 'dashboard') {
        applyAndRender(d)
        return
      }

      if (d.header !== undefined || d.radar !== undefined) {
        applyAndRender(d)
        return
      }

      if (
        d.type === 'trade_opened'  ||
        d.type === 'trade_closed'  ||
        d.type === 'health_changed'||
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