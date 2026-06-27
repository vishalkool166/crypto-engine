const _listeners = {}

function emit(event, data) {
    const fns = _listeners[event] || []
    fns.forEach(fn => { try { fn(data) } catch(e) {} })
}

function on(event, fn) {
    if (!_listeners[event]) _listeners[event] = []
    _listeners[event].push(fn)
    return () => {
        _listeners[event] = _listeners[event].filter(f => f !== fn)
    }
}

const _store = {
    page:          'overview',
    wsState:       'connecting',
    mode:          'paper',
    nextScanEpoch: 0,
    ticker:        [],
    dashboardData: {},
    ftTrades:      [],
    ftProfit:      {},
    ftBalance:     {},
    ftBotState:    'unknown',
    theme:         localStorage.getItem('theme') || 'light',
    totp: {
        show:    false,
        title:   '',
        subtitle:'',
        resolve: null,
    },
    toast: {
        show:    false,
        message: '',
        type:    'success',
        timer:   null,
    },
}

let _ws         = null
let _wsTimer    = null
let _wsDelay    = 3000
let _countTimer = null

function _applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
    _store.theme = theme
    emit('theme', theme)
}

function toggleTheme() {
    _applyTheme(_store.theme === 'light' ? 'dark' : 'light')
}

function _applyDashboard(data) {
    if (!data) return
    const summary = data.summary || {}
    _store.dashboardData = data
    if (summary.mode)            _store.mode          = summary.mode
    if (data.ticker?.length)     _store.ticker        = data.ticker
    if (summary.next_scan_epoch) _store.nextScanEpoch = summary.next_scan_epoch
    emit('dashboard',    data)
    emit('summary',      summary)
    if (data.signals) emit('signals', data.signals)
    if (data.history) emit('history', data.history)
}

function _applyTicker(data) {
    if (!data) return
    if (data.items?.length) {
        _store.ticker = data.items
        emit('ticker', data.items)
    }
    if (data.summary) {
        if (data.summary.next_scan_epoch) _store.nextScanEpoch = data.summary.next_scan_epoch
        if (data.summary.mode)            _store.mode          = data.summary.mode
        emit('summary-lite', data.summary)
    }
}

function _applyFtUpdate(data) {
    if (!data) return
    if (Array.isArray(data.status))          _store.ftTrades   = data.status
    if (data.profit && !data.profit.detail)  _store.ftProfit   = data.profit
    if (data.balance && !data.balance.detail) {
        const currencies = data.balance.currencies || []
        const usdt       = currencies.find(c => c.currency === 'USDT') || {}
        _store.ftBalance = {
            total: data.balance.total != null ? parseFloat(data.balance.total) : null,
            free:  usdt.free           != null ? parseFloat(usdt.free)          : null,
        }
    }
    if (data.bot_state) _store.ftBotState = data.bot_state
    emit('ft_update', data)
}

function _connect() {
    if (_ws && _ws.readyState === WebSocket.OPEN) return

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url   = `${proto}://${location.host}/ws/dashboard`

    try { _ws = new WebSocket(url) } catch(e) { _scheduleReconnect(); return }

    _ws.onopen = () => {
        _store.wsState = 'connected'
        _wsDelay       = 3000
        emit('wsState', 'connected')
        if (_wsTimer) { clearTimeout(_wsTimer); _wsTimer = null }
    }

    _ws.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data)
            if      (data.type === 'dashboard') _applyDashboard(data)
            else if (data.type === 'ticker')    _applyTicker(data)
            else if (data.type === 'ft_update') _applyFtUpdate(data)
        } catch(err) {}
    }

    _ws.onclose = () => {
        _store.wsState = 'disconnected'
        emit('wsState', 'disconnected')
        _scheduleReconnect()
    }

    _ws.onerror = () => {
        _store.wsState = 'disconnected'
        emit('wsState', 'disconnected')
    }
}

function _scheduleReconnect() {
    if (_wsTimer) return
    _wsTimer = setTimeout(() => {
        _wsTimer       = null
        _store.wsState = 'connecting'
        emit('wsState', 'connecting')
        _wsDelay = Math.min(_wsDelay * 1.5, 30000)
        _connect()
    }, _wsDelay)
}

function _startCountdown() {
    if (_countTimer) clearInterval(_countTimer)
    _countTimer = setInterval(() => {
        emit('countdown', _store.nextScanEpoch)
    }, 1000)
}

async function init() {
    _applyTheme(_store.theme)

    try {
        const res = await fetch('/api/health', { credentials: 'include' })
        if (res.status === 401) { window.location.href = '/login.html'; return false }
    } catch(e) {}

    try {
        const res = await fetch('/api/dashboard', { credentials: 'include' })
        if (res.status === 401) { window.location.href = '/login.html'; return false }
        const data = await res.json()
        if (data) _applyDashboard(data)
    } catch(e) {}

    _connect()
    _startCountdown()
    return true
}

async function requireTotp(title, subtitle) {
    return new Promise((resolve) => {
        _store.totp = { show: true, title: title || 'Confirm Action', subtitle: subtitle || 'Enter your TOTP code to continue', resolve }
        emit('totp', { ..._store.totp })
    })
}

function confirmTotp(code) {
    if (_store.totp.resolve) {
        _store.totp.resolve(code)
        _store.totp = { show: false, title: '', subtitle: '', resolve: null }
        emit('totp', { ..._store.totp })
    }
}

function closeTotp() {
    if (_store.totp.resolve) _store.totp.resolve(null)
    _store.totp = { show: false, title: '', subtitle: '', resolve: null }
    emit('totp', { ..._store.totp })
}

function showToast(message, type = 'success', duration = 3500) {
    if (_store.toast.timer) clearTimeout(_store.toast.timer)
    _store.toast = {
        show:    true,
        message,
        type,
        timer: setTimeout(() => {
            _store.toast.show = false
            emit('toast', { ..._store.toast })
        }, duration)
    }
    emit('toast', { ..._store.toast })
}

function logout() {
    fetch('/auth/logout').finally(() => { window.location.href = '/login.html' })
}

function navigate(page) {
    _store.page = page
    emit('navigate', page)
}

function getState() { return _store }

function useStore(selector) {
    const { useState, useEffect } = preactHooks
    const [val, setVal] = useState(() => selector(_store))
    useEffect(() => {
        const events  = ['dashboard','ticker','ft_update','wsState','navigate','totp','toast','summary','summary-lite','countdown','theme']
        const unsubs  = events.map(e => on(e, () => {
            const next = selector(_store)
            setVal(prev => JSON.stringify(prev) !== JSON.stringify(next) ? next : prev)
        }))
        return () => unsubs.forEach(fn => fn())
    }, [])
    return val
}

function usePage() {
    const { useState, useEffect } = preactHooks
    const [page, setPage] = useState(_store.page)
    useEffect(() => on('navigate', p => setPage(p)), [])
    return page
}

function useWsState() {
    const { useState, useEffect } = preactHooks
    const [state, setState] = useState(_store.wsState)
    useEffect(() => on('wsState', s => setState(s)), [])
    return state
}

function useTicker() {
    const { useState, useEffect } = preactHooks
    const [ticker, setTicker] = useState(() => [..._store.ticker])
    useEffect(() => {
        if (_store.ticker.length) setTicker([..._store.ticker])
        return on('ticker', t => setTicker([...t]))
    }, [])
    return ticker
}

function useFtUpdate() {
    const { useState, useEffect } = preactHooks
    const [data, setData] = useState({
        trades:   _store.ftTrades,
        profit:   _store.ftProfit,
        balance:  _store.ftBalance,
        botState: _store.ftBotState,
    })
    useEffect(() => on('ft_update', () => setData({
        trades:   _store.ftTrades,
        profit:   _store.ftProfit,
        balance:  _store.ftBalance,
        botState: _store.ftBotState,
    })), [])
    return data
}

function useDashboard() {
    const { useState, useEffect } = preactHooks
    const [data, setData] = useState(() => ({ ..._store.dashboardData }))
    useEffect(() => {
        if (Object.keys(_store.dashboardData).length) setData({ ..._store.dashboardData })
        return on('dashboard', d => setData({ ...d }))
    }, [])
    return data
}

function useNextScan() {
    const { useState, useEffect } = preactHooks
    const [label, setLabel] = useState('--')
    useEffect(() => on('countdown', epoch => {
        if (!epoch) { setLabel('--'); return }
        const diff = Math.max(0, epoch - Date.now())
        const mins = Math.floor(diff / 60000)
        const secs = Math.floor((diff % 60000) / 1000)
        setLabel(`${mins}m ${secs}s`)
    }), [])
    return label
}

function useTotp() {
    const { useState, useEffect } = preactHooks
    const [state, setState] = useState({ ..._store.totp })
    useEffect(() => on('totp', s => setState({ ...s })), [])
    return state
}

function useToast() {
    const { useState, useEffect } = preactHooks
    const [state, setState] = useState({ ..._store.toast })
    useEffect(() => on('toast', s => setState({ ...s })), [])
    return state
}

function useMode() {
    const { useState, useEffect } = preactHooks
    const [mode, setMode] = useState(_store.mode)
    useEffect(() => {
        if (_store.mode && _store.mode !== 'paper') setMode(_store.mode)
        const u1 = on('summary',      d => { if (d?.mode) setMode(d.mode) })
        const u2 = on('summary-lite', d => { if (d?.mode) setMode(d.mode) })
        return () => { u1(); u2() }
    }, [])
    return mode
}

function useTheme() {
    const { useState, useEffect } = preactHooks
    const [theme, setTheme] = useState(_store.theme)
    useEffect(() => on('theme', t => setTheme(t)), [])
    return theme
}

window.Store = {
    init, navigate, getState, requireTotp, confirmTotp,
    closeTotp, showToast, logout, toggleTheme,
    on, emit,
    useStore, usePage, useWsState, useTicker, useFtUpdate,
    useDashboard, useNextScan, useTotp, useToast, useMode, useTheme,
}