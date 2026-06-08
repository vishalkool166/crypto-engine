'use strict'

const WS_PRICE_URL     = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/price`
const WS_DASHBOARD_URL = `${window.location.origin.replace('https','wss').replace('http','ws')}/ws/dashboard`

let _priceSocket     = null
let _dashSocket      = null
let _pingTimer       = null
let _priceReconnect  = null
let _dashReconnect   = null


function startPriceSocket() {
    if (_priceSocket?.readyState === WebSocket.OPEN) return

    _priceSocket = new WebSocket(WS_PRICE_URL)

    _priceSocket.onopen = () => {
        setWsStatus(true)
        log.debug('Price WS connected')
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

    _priceSocket.onclose = (e) => {
        _cleanupPrice()
        setWsStatus(false)
        if (S.data === null || S.data?.state !== 'idle') {
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
    if (_dashSocket?.readyState === WebSocket.OPEN) return

    _dashSocket = new WebSocket(WS_DASHBOARD_URL)

    _dashSocket.onopen = () => {
        console.log('Dashboard WS connected')
    }

    _dashSocket.onmessage = (event) => {
        try {
            const d = JSON.parse(event.data)
            if (d.type === 'dashboard') {
                _applyDashboardPush(d)
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


function _applyDashboardPush(data) {
    const { stateChanged, tradeChanged, healthChanged } = applyDashboard(data)

    renderHeader(data.header)
    renderStatusBar(data)
    renderRisk(data.risk)
    renderTrade(data.trade, data.state)
    syncConnectionMode(data.state)
    renderRadar(data.radar)
    renderSignalQueue(data.queue)
    renderPerformance(data.performance)

    if ((data.history?.length || 0) !== S.lastHistoryLen) {
        S.lastHistoryLen = data.history?.length || 0
        renderHistory(data.history)
        renderCharts(data.history)
    }

    setApiStatus(true)
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
    $set('h-today-pnl',   { text: d.pnl,      color: d.pnl_color })

    if (d.price_raw) {
        const pct = _calcProgressPct(d.price_raw, trade)
        $set('prog-fill',   { width: pct, bg: trade.progress?.color })
        $set('prog-status', { text: `${pct}% to TP1` })
    }

    const ladderNow = document.querySelector('.ladder-now span:nth-child(2)')
    if (ladderNow) ladderNow.textContent = d.price
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