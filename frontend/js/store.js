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
    page:             'now',
    wsState:          'connecting',
    mode:             'paper',
    tier:             'pro',
    regime:           '',
    confidence:       0,
    nextScanEpoch:    0,
    dashboardData:    {},
    ftTrades:         [],
    ftProfit:         {},
    ftBalance:        {},
    ftBotState:       'unknown',
    theme:            localStorage.getItem('se_theme') || 'dark',
    notifications:    [],
    totp: {
        show:     false,
        title:    '',
        subtitle: '',
        resolve:  null,
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
    localStorage.setItem('se_theme', theme)
    _store.theme = theme
    emit('theme', theme)
}

function toggleTheme() {
    _applyTheme(_store.theme === 'dark' ? 'light' : 'dark')
}

function _extractRegime(data) {
    if (!data) return ''
    const results = data.signals?.radar || []
    if (!results.length) return ''
    const regimes = results.map(r => r.regime).filter(Boolean)
    if (!regimes.length) return ''
    const counts = {}
    regimes.forEach(r => { counts[r] = (counts[r] || 0) + 1 })
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
}

function _extractConfidence(data) {
    if (!data) return 0
    const summary = data.summary || {}
    return Utils.confidenceScore(summary)
}

function _applyDashboard(data) {
    if (!data) return
    const summary = data.summary || {}

    _store.dashboardData = {
        ..._store.dashboardData,
        ...data,
        performance: 'performance' in data ? data.performance : (_store.dashboardData.performance || {}),
        signals:     'signals'     in data ? data.signals     : (_store.dashboardData.signals     || {}),
        history:     'history'     in data ? data.history     : (_store.dashboardData.history     || []),
        universe:    'universe'    in data ? data.universe    : (_store.dashboardData.universe    || []),
        ticker:      'ticker'      in data ? data.ticker      : (_store.dashboardData.ticker      || []),
    }

    if (summary.mode)            _store.mode          = summary.mode
    if (summary.next_scan_epoch) _store.nextScanEpoch = summary.next_scan_epoch
    _store.regime     = _extractRegime(_store.dashboardData)
    _store.confidence = _extractConfidence(_store.dashboardData)

    emit('dashboard',  _store.dashboardData)
    emit('summary',    summary)
    emit('regime',     _store.regime)
    emit('confidence', _store.confidence)
    if (data.signals) emit('signals', _store.dashboardData.signals)
    if (data.history) emit('history', _store.dashboardData.history)
    _checkForNewSignals(_store.dashboardData)
    _emitTopbarState()
}

function _applyFtUpdate(data) {
    if (!data) return
    if (Array.isArray(data.status))           _store.ftTrades  = data.status
    if (data.profit  && !data.profit.detail)  _store.ftProfit  = data.profit
    if (data.balance && !data.balance.detail) {
        const currencies = data.balance.currencies || []
        const usdt       = currencies.find(c => c.currency === 'USDT') || {}
        _store.ftBalance = {
            total: data.balance.total != null ? parseFloat(data.balance.total) : null,
            free:  usdt.free           != null ? parseFloat(usdt.free)          : null,
        }
    }
    if (data.bot_state) _store.ftBotState = data.bot_state
    emit('ft_update', {
        trades:   _store.ftTrades,
        profit:   _store.ftProfit,
        balance:  _store.ftBalance,
        botState: _store.ftBotState,
    })
    _emitTopbarState()
}

function _deriveTopbarState() {
    const trades  = _store.ftTrades || []
    const signals = _store.dashboardData?.signals?.queue || []
    const mode    = _store.mode || 'paper'

    if (trades.length > 0) {
        const invalidated = trades.find(t => t.health?.state === 'INVALIDATED')
        if (invalidated) {
            const pair  = (invalidated.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
            const pnl   = parseFloat(invalidated.profit_abs || 0)
            const pnlPos = pnl >= 0
            return {
                type:      'invalidated',
                primary:   '⚠ ' + pair + ' · ' + Utils.fmtPnl(pnl, pnlPos),
                secondary: 'Thesis invalidated — review position',
                color:     'state-invalidated',
                trade:     invalidated,
            }
        }

        const warning = trades.find(t => t.health?.state === 'WARNING')
        if (warning) {
            const pair  = (warning.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
            const pnl   = parseFloat(warning.profit_abs || 0)
            const pnlPos = pnl >= 0
            return {
                type:      'warning',
                primary:   '◉ ' + pair + ' · ' + Utils.fmtPnl(pnl, pnlPos),
                secondary: 'Thesis weakening — monitor closely',
                color:     'state-warning',
                trade:     warning,
            }
        }

        const best    = trades.reduce((a, b) =>
            Math.abs(parseFloat(b.profit_abs || 0)) > Math.abs(parseFloat(a.profit_abs || 0)) ? b : a
        )
        const pair    = (best.pair || '').replace('/USDT:USDT', 'USDT').replace('/USDT', 'USDT')
        const pnl     = parseFloat(best.profit_abs || 0)
        const pnlPos  = pnl >= 0
        const dir     = best.is_short ? 'SHORT' : 'LONG'
        const dur     = Utils.fmtDuration(best.open_date)
        const lev     = best.leverage ? best.leverage + 'x' : ''
        return {
            type:      pnlPos ? 'trade' : 'trade-loss',
            primary:   pair + ' ' + dir + ' · ' + Utils.fmtPnl(pnl, pnlPos),
            secondary: dur + ' open' + (lev ? ' · ' + lev : '') + (trades.length > 1 ? ' · ' + trades.length + ' positions' : ''),
            color:     pnlPos ? 'state-trade' : 'state-trade-loss',
            trade:     best,
        }
    }

    if (signals.length > 0) {
        const top   = signals[0]
        const grade = top.grade || 'F'
        const coin  = (top.coin || '--') + 'USDT'
        const dir   = top.direction || '--'
        const score = top.score || 0

        if (grade === 'A+') {
            return {
                type:      'signal-aplus',
                primary:   coin + ' A+ ' + dir,
                secondary: 'Score ' + score + '/100 · tap to view',
                color:     'state-signal-aplus',
                signal:    top,
            }
        }

        if (grade === 'A') {
            return {
                type:      'signal-a',
                primary:   coin + ' A ' + dir,
                secondary: 'Score ' + score + '/100 · tap to view',
                color:     'state-signal-a',
                signal:    top,
            }
        }
    }

    const arc     = Utils.fmtCountdownArc(_store.nextScanEpoch)
    const session = Utils.currentSession()
    return {
        type:      'watching',
        primary:   'Watching ' + (_store.dashboardData?.summary?.coins_count || '--') + ' coins',
        secondary: session.label + ' · Next scan ' + arc.mins + ':' + arc.secs,
        color:     'state-watching',
        signal:    null,
        trade:     null,
    }
}

function _emitTopbarState() {
    emit('topbar-state', _deriveTopbarState())
}

let _lastSignalIds = new Set()

function _checkForNewSignals(data) {
    const queue = data.signals?.queue || []
    if (!queue.length) return
    const currentIds = new Set(queue.map(s => s.coin + '_' + s.direction))
    if (_lastSignalIds.size === 0) {
        _lastSignalIds = currentIds
        return
    }
    for (const id of currentIds) {
        if (!_lastSignalIds.has(id)) {
            const sig = queue.find(s => s.coin + '_' + s.direction === id)
            if (sig) {
                _addNotification({
                    type:      'signal',
                    title:     `${sig.coin}USDT ${sig.direction}`,
                    message:   `Grade ${sig.grade} · Score ${sig.score}/100`,
                    coin:      sig.coin,
                    grade:     sig.grade,
                    timestamp: Date.now(),
                })
                showToast(
                    `${sig.coin}USDT ${sig.direction} — Grade ${sig.grade}`,
                    'signal',
                    6000
                )
                if (navigator.vibrate && sig.grade === 'A+') {
                    navigator.vibrate([10, 50, 10])
                }
            }
        }
    }
    _lastSignalIds = currentIds
}

function _addNotification(notif) {
    _store.notifications.unshift({ ...notif, id: Date.now() + Math.random() })
    if (_store.notifications.length > 50) {
        _store.notifications = _store.notifications.slice(0, 50)
    }
    emit('notifications', _store.notifications)
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

function _applyTicker(data) {
    if (!data) return
    if (data.status && Array.isArray(data.status)) {
        _store.ftTrades = data.status
        emit('ft_update', {
            trades:   _store.ftTrades,
            profit:   _store.ftProfit,
            balance:  _store.ftBalance,
            botState: _store.ftBotState,
        })
        _emitTopbarState()
    }
    if (data.summary) {
        if (data.summary.next_scan_epoch) _store.nextScanEpoch = data.summary.next_scan_epoch
        if (data.summary.mode)            _store.mode          = data.summary.mode
        emit('summary-lite', data.summary)
        _emitTopbarState()
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
        _emitTopbarState()
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
        _store.totp = {
            show:     true,
            title:    title    || 'Confirm Action',
            subtitle: subtitle || 'Enter your 6-digit authenticator code to continue.',
            resolve
        }
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

function hideToast() {
    if (_store.toast.timer) clearTimeout(_store.toast.timer)
    _store.toast.show = false
    emit('toast', { ..._store.toast })
}

function logout() {
    fetch('/auth/logout').finally(() => { window.location.href = '/login.html' })
}

function navigate(page) {
    _store.page = page
    emit('navigate', page)
    window.scrollTo({ top: 0, behavior: 'smooth' })
}

function getState() { return _store }

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
    const [arc, setArc] = useState({ mins: '--', secs: '--', pct: 0 })
    useEffect(() => on('countdown', epoch => {
        setArc(Utils.fmtCountdownArc(epoch))
    }), [])
    return arc
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
        if (_store.mode) setMode(_store.mode)
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

function useRegime() {
    const { useState, useEffect } = preactHooks
    const [regime, setRegime] = useState(_store.regime)
    useEffect(() => {
        if (_store.regime) setRegime(_store.regime)
        return on('regime', r => setRegime(r))
    }, [])
    return regime
}

function useConfidence() {
    const { useState, useEffect } = preactHooks
    const [conf, setConf] = useState(_store.confidence)
    useEffect(() => {
        if (_store.confidence) setConf(_store.confidence)
        return on('confidence', c => setConf(c))
    }, [])
    return conf
}

function useNotifications() {
    const { useState, useEffect } = preactHooks
    const [notifs, setNotifs] = useState([..._store.notifications])
    useEffect(() => on('notifications', n => setNotifs([...n])), [])
    return notifs
}

function useFtTrades() {
    const { useState, useEffect } = preactHooks
    const [trades, setTrades] = useState([..._store.ftTrades])
    useEffect(() => on('ft_update', d => setTrades([...(d.trades || [])])), [])
    return trades
}

function useTopbarState() {
    const { useState, useEffect } = preactHooks
    const [state, setState] = useState(() => _deriveTopbarState())
    useEffect(() => {
        return on('topbar-state', s => setState({ ...s }))
    }, [])
    return state
}

window.Store = {
    init, navigate, getState, logout, toggleTheme,
    requireTotp, confirmTotp, closeTotp,
    showToast, hideToast,
    on, emit,
    usePage, useWsState, useFtUpdate,
    useDashboard, useNextScan, useTotp, useToast,
    useMode, useTheme, useRegime, useConfidence,
    useNotifications, useFtTrades, useTopbarState,
}