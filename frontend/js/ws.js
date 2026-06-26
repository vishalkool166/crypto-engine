const WS = {
    _socket:        null,
    _reconnectMs:   3000,
    _maxReconnect:  30000,
    _currentDelay:  3000,
    _reconnectTimer: null,
    _listeners:     {},
    _connected:     false,
    _pingTimer:     null,

    connect() {
        if (this._socket && this._socket.readyState === WebSocket.OPEN) return

        const proto = location.protocol === 'https:' ? 'wss' : 'ws'
        const url   = `${proto}://${location.host}/ws/dashboard`

        try {
            this._socket = new WebSocket(url)
        } catch (e) {
            this._scheduleReconnect()
            return
        }

        this._socket.onopen = () => {
            this._connected    = true
            this._currentDelay = this._reconnectMs
            this._emit('connected', {})
            this._startPing()
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
            this._stopPing()
            this._emit('disconnected', {})
            this._scheduleReconnect()
        }

        this._socket.onerror = () => {
            this._connected = false
            this._stopPing()
            this._emit('error', {})
        }
    },

    disconnect() {
        this._stopPing()
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

    _startPing() {
        this._stopPing()
        this._pingTimer = setInterval(() => {
            if (this._socket && this._socket.readyState === WebSocket.OPEN) {
                try {
                    this._socket.send(JSON.stringify({ type: 'ping' }))
                } catch (e) {}
            }
        }, 30000)
    },

    _stopPing() {
        if (this._pingTimer) {
            clearInterval(this._pingTimer)
            this._pingTimer = null
        }
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

    offAll(event) {
        if (event) {
            delete this._listeners[event]
        } else {
            this._listeners = {}
        }
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