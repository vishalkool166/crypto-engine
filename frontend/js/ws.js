const WS = {
    _socket:      null,
    _reconnectMs: 3000,
    _maxReconnect: 30000,
    _currentDelay: 3000,
    _reconnectTimer: null,
    _listeners: {},
    _connected: false,

    connect() {
        if (this._socket && this._socket.readyState === WebSocket.OPEN) return

        const proto = location.protocol === 'https:' ? 'wss' : 'ws'
        const url   = `${proto}://${location.host}/ws/dashboard`

        this._socket = new WebSocket(url)

        this._socket.onopen = () => {
            this._connected   = true
            this._currentDelay = this._reconnectMs
            this._emit('connected', {})
            if (this._reconnectTimer) {
                clearTimeout(this._reconnectTimer)
                this._reconnectTimer = null
            }
        }

        this._socket.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data)
                this._emit('message', data)
                if (data.type) {
                    this._emit(data.type, data)
                }
            } catch (err) {}
        }

        this._socket.onclose = () => {
            this._connected = false
            this._emit('disconnected', {})
            this._scheduleReconnect()
        }

        this._socket.onerror = () => {
            this._connected = false
            this._emit('error', {})
        }
    },

    disconnect() {
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer)
            this._reconnectTimer = null
        }
        if (this._socket) {
            this._socket.onclose = null
            this._socket.close()
            this._socket = null
        }
        this._connected = false
    },

    _scheduleReconnect() {
        if (this._reconnectTimer) return
        this._reconnectTimer = setTimeout(() => {
            this._reconnectTimer = null
            this._currentDelay   = Math.min(this._currentDelay * 1.5, this._maxReconnect)
            this.connect()
        }, this._currentDelay)
    },

    on(event, cb) {
        if (!this._listeners[event]) this._listeners[event] = []
        this._listeners[event].push(cb)
        return () => this.off(event, cb)
    },

    off(event, cb) {
        if (!this._listeners[event]) return
        this._listeners[event] = this._listeners[event].filter(fn => fn !== cb)
    },

    _emit(event, data) {
        const fns = this._listeners[event] || []
        fns.forEach(fn => {
            try { fn(data) } catch (e) {}
        })
    },

    isConnected() {
        return this._connected
    },
}

window.WS = WS