const API = {

    async _request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
        }
        if (body) opts.body = JSON.stringify(body)

        const res = await fetch('/api' + path, opts)

        if (res.status === 401) {
            window.location.href = '/login.html'
            return null
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }))
            throw new Error(err.detail || err.reason || 'Request failed')
        }

        return res.json()
    },

    get(path)         { return this._request('GET',    path)       },
    post(path, body)  { return this._request('POST',   path, body) },
    del(path)         { return this._request('DELETE', path)       },

    dashboard()       { return this.get('/dashboard')              },
    stats()           { return this.get('/stats')                  },
    health()          { return this.get('/health')                 },

    signals(params = {}) {
        const q = new URLSearchParams()
        if (params.limit)   q.set('limit',   params.limit)
        if (params.grade)   q.set('grade',   params.grade)
        if (params.coin)    q.set('coin',    params.coin)
        if (params.outcome) q.set('outcome', params.outcome)
        return this.get('/signals?' + q.toString())
    },

    scan()            { return this.get('/scan')                   },

    ftSummary()       { return this.get('/ft/summary')             },
    ftStatus()        { return this.get('/ft/status')              },
    ftProfit()        { return this.get('/ft/profit')              },
    ftBalance()       { return this.get('/ft/balance')             },
    ftStart()         { return this.post('/ft/start')              },
    ftStop()          { return this.post('/ft/stop')               },

    ftForceSell(tradeid, totpCode) {
        return this.post('/ft/forcesell', { tradeid, totp_code: totpCode })
    },

    coins()           { return this.get('/coins')                  },

    addCoin(coin) {
        return this.post('/coins/add', { coin })
    },

    toggleCoin(coin, enabled) {
        return this.post('/coins/toggle', { coin, enabled })
    },

    deleteCoin(coin)  { return this.del(`/coins/${coin}`)          },

    validateCoin(coin){ return this.get(`/coins/validate/${coin}`) },

    backtest(coin)    { return this.get(`/backtest/${coin}`)        },

    backtestHistory() { return this.get('/backtest/history/all')   },

    factorAnalysis()  { return this.get('/analysis/factors')       },

    auditLog(limit = 100) {
        return this.get(`/audit/log?limit=${limit}`)
    },

    modeStatus()      { return this.get('/mode/status')            },

    modeToggle(mode, totpCode) {
        return this.post('/mode/toggle', { mode, totp_code: totpCode })
    },

    syncOutcomes()    { return this.post('/sync/outcomes')         },

    fearGreed()       { return this.get('/fear-greed')             },

    macroEvents()     { return this.get('/macro-events')           },

    candles(coin, tf) { return this.get(`/candles/${coin}/${tf}`)  },
}

window.API = API