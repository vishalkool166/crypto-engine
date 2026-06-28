const Utils = {

    fmtPrice(n) {
        if (n == null || n === '' || n === false) return '--'
        n = parseFloat(n)
        if (isNaN(n) || !isFinite(n)) return '--'
        if (n === 0) return '$0.00'
        const abs = Math.abs(n)
        if (abs >= 100000) return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        if (abs >= 10000)  return '$' + n.toFixed(2)
        if (abs >= 1000)   return '$' + n.toFixed(2)
        if (abs >= 100)    return '$' + n.toFixed(3)
        if (abs >= 10)     return '$' + n.toFixed(4)
        if (abs >= 1)      return '$' + n.toFixed(4)
        if (abs >= 0.1)    return '$' + n.toFixed(5)
        if (abs >= 0.01)   return '$' + n.toFixed(6)
        if (abs >= 0.001)  return '$' + n.toFixed(7)
        return '$' + n.toFixed(8)
    },

    fmtPnl(n, pos) {
        if (n == null) return '--'
        n = parseFloat(n)
        if (isNaN(n)) return '--'
        const positive = pos != null ? pos : n >= 0
        const sign     = positive ? '+' : '-'
        const abs      = Math.abs(n)
        if (abs >= 1000) return sign + '$' + abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        if (abs >= 1)    return sign + '$' + abs.toFixed(2)
        return sign + '$' + abs.toFixed(4)
    },

    fmtPct(n, showSign = true) {
        if (n == null) return '--'
        n = parseFloat(n)
        if (isNaN(n)) return '--'
        const sign = showSign ? (n >= 0 ? '+' : '') : ''
        return sign + n.toFixed(2) + '%'
    },

    fmtNumber(n, decimals = 0) {
        if (n == null) return '--'
        n = parseFloat(n)
        if (isNaN(n)) return '--'
        return n.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        })
    },

    fmtDuration(openedAt) {
        if (!openedAt) return '--'
        try {
            const diff = Date.now() - new Date(openedAt).getTime()
            if (diff < 0) return '--'
            const mins = Math.floor(diff / 60000)
            const hrs  = Math.floor(mins / 60)
            const days = Math.floor(hrs / 24)
            if (days > 0) return `${days}d ${hrs % 24}h`
            if (hrs > 0)  return `${hrs}h ${mins % 60}m`
            if (mins > 0) return `${mins}m`
            return 'Just now'
        } catch(e) { return '--' }
    },

    fmtTime(ts) {
        if (!ts) return '--'
        try {
            return new Date(ts).toLocaleString('en-IN', {
                timeZone: 'Asia/Kolkata',
                day:      '2-digit',
                month:    'short',
                hour:     '2-digit',
                minute:   '2-digit',
                hour12:   true
            }) + ' IST'
        } catch(e) { return '--' }
    },

    fmtTimeShort(ts) {
        if (!ts) return '--'
        try {
            return new Date(ts).toLocaleString('en-IN', {
                timeZone: 'Asia/Kolkata',
                hour:     '2-digit',
                minute:   '2-digit',
                hour12:   true
            })
        } catch(e) { return '--' }
    },

    fmtDate(ts) {
        if (!ts) return '--'
        try {
            return new Date(ts).toLocaleString('en-IN', {
                timeZone: 'Asia/Kolkata',
                day:      '2-digit',
                month:    'short',
                year:     'numeric'
            })
        } catch(e) { return '--' }
    },

    fmtTimeAgo(ts) {
        if (!ts) return '--'
        try {
            const diff = Date.now() - new Date(ts).getTime()
            if (diff < 0) return '--'
            const mins = Math.floor(diff / 60000)
            const hrs  = Math.floor(mins / 60)
            const days = Math.floor(hrs / 24)
            if (days > 0) return `${days}d ago`
            if (hrs > 0)  return `${hrs}h ago`
            if (mins > 0) return `${mins}m ago`
            return 'Just now'
        } catch(e) { return '--' }
    },

    fmtUptime(secs) {
        if (!secs) return '--'
        const d = Math.floor(secs / 86400)
        const h = Math.floor((secs % 86400) / 3600)
        const m = Math.floor((secs % 3600) / 60)
        if (d > 0) return `${d}d ${h}h ${m}m`
        if (h > 0) return `${h}h ${m}m`
        return `${m}m`
    },

    fmtCountdown(epochMs) {
        if (!epochMs) return '--'
        const diff = Math.max(0, epochMs - Date.now())
        const mins = Math.floor(diff / 60000)
        const secs = Math.floor((diff % 60000) / 1000)
        return `${mins}m ${secs.toString().padStart(2, '0')}s`
    },

    fmtCountdownArc(epochMs) {
        if (!epochMs) return { mins: '--', secs: '--', pct: 0 }
        const total = 15 * 60 * 1000
        const diff  = Math.max(0, epochMs - Date.now())
        const mins  = Math.floor(diff / 60000)
        const secs  = Math.floor((diff % 60000) / 1000)
        const pct   = Math.min(1, diff / total)
        return {
            mins: mins.toString(),
            secs: secs.toString().padStart(2, '0'),
            pct
        }
    },

    pnlColor(pos) {
        if (pos == null) return 'var(--label-3)'
        const positive = typeof pos === 'boolean' ? pos : parseFloat(pos) >= 0
        return positive ? 'var(--profit)' : 'var(--loss)'
    },

    pnlClass(pos) {
        if (pos == null) return 'neutral'
        const positive = typeof pos === 'boolean' ? pos : parseFloat(pos) >= 0
        return positive ? 'positive' : 'negative'
    },

    changeColor(n) {
        if (n == null) return 'var(--label-3)'
        try {
            const v = parseFloat(String(n).replace('%', '').replace('+', ''))
            if (isNaN(v)) return 'var(--label-3)'
            return v >= 0 ? 'var(--profit)' : 'var(--loss)'
        } catch(e) { return 'var(--label-3)' }
    },

    changeClass(n) {
        if (n == null) return 'neutral'
        try {
            const v = parseFloat(String(n).replace('%', '').replace('+', ''))
            if (isNaN(v)) return 'neutral'
            return v >= 0 ? 'positive' : 'negative'
        } catch(e) { return 'neutral' }
    },

    gradeColor(grade) {
        const map = {
            'A+': 'var(--grade-aplus)',
            'A':  'var(--grade-a)',
            'B':  'var(--grade-b)',
            'C':  'var(--label-3)',
            'F':  'var(--label-4)',
        }
        return map[grade] || 'var(--label-4)'
    },

    gradeBadgeClass(grade) {
        const map = {
            'A+': 'badge badge-aplus',
            'A':  'badge badge-a',
            'B':  'badge badge-b',
            'C':  'badge badge-c',
            'F':  'badge badge-f',
        }
        return map[grade] || 'badge badge-f'
    },

    gradeCardClass(grade) {
        const map = {
            'A+': 'signal-card signal-card-aplus',
            'A':  'signal-card signal-card-a',
            'B':  'signal-card signal-card-b',
            'C':  'signal-card signal-card-c',
            'F':  'signal-card',
        }
        return map[grade] || 'signal-card'
    },

    gradeHeroClass(grade) {
        const map = {
            'A+': 'signal-hero-card signal-hero-card-aplus',
            'A':  'signal-hero-card signal-hero-card-a',
            'B':  'signal-hero-card signal-hero-card-b',
        }
        return map[grade] || 'signal-hero-card signal-hero-card-watching'
    },

    gradeTileClass(grade) {
        const map = {
            'A+': 'coin-tile coin-tile-aplus',
            'A':  'coin-tile coin-tile-a',
            'B':  'coin-tile coin-tile-b',
        }
        return map[grade] || 'coin-tile'
    },

    gradeScoreRingClass(grade) {
        const map = {
            'A+': 'score-ring-fill score-ring-fill-aplus',
            'A':  'score-ring-fill score-ring-fill-a',
            'B':  'score-ring-fill score-ring-fill-b',
            'C':  'score-ring-fill score-ring-fill-c',
            'F':  'score-ring-fill score-ring-fill-f',
        }
        return map[grade] || 'score-ring-fill score-ring-fill-f'
    },

    dirBadgeClass(dir) {
        const map = {
            'LONG':     'badge badge-long',
            'SHORT':    'badge badge-short',
            'WATCH':    'badge badge-watch',
            'NO TRADE': 'badge badge-notrade',
        }
        return map[dir] || 'badge badge-notrade'
    },

    outcomeBadgeClass(outcome) {
        const map = {
            'win':     'badge badge-win',
            'loss':    'badge badge-loss',
            'pending': 'badge badge-pending',
            'timeout': 'badge badge-timeout',
        }
        return map[outcome] || 'badge badge-timeout'
    },

    healthClass(state) {
        const map = {
            'HEALTHY':     'healthy',
            'WARNING':     'warning',
            'INVALIDATED': 'invalidated',
        }
        return map[state] || 'unknown'
    },

    healthDotClass(state) {
        const map = {
            'HEALTHY':     'status-dot status-dot-md status-dot-healthy',
            'WARNING':     'status-dot status-dot-md status-dot-warning',
            'INVALIDATED': 'status-dot status-dot-md status-dot-invalidated',
        }
        return map[state] || 'status-dot status-dot-md status-dot-unknown'
    },

    healthRowClass(state) {
        const map = {
            'HEALTHY':     'health-row health-row-healthy',
            'WARNING':     'health-row health-row-warning',
            'INVALIDATED': 'health-row health-row-invalidated',
        }
        return map[state] || 'health-row health-row-unknown'
    },

    scoreColor(score) {
        score = parseFloat(score) || 0
        if (score >= 85) return 'var(--grade-aplus)'
        if (score >= 68) return 'var(--grade-a)'
        if (score >= 52) return 'var(--grade-b)'
        if (score >= 38) return 'var(--label-3)'
        return 'var(--label-4)'
    },

    scoreGrade(score) {
        score = parseFloat(score) || 0
        if (score >= 85) return 'aplus'
        if (score >= 68) return 'a'
        if (score >= 52) return 'b'
        if (score >= 38) return 'c'
        return 'f'
    },

    winRateColor(wr) {
        wr = parseFloat(wr) || 0
        if (wr >= 60) return 'var(--profit)'
        if (wr >= 45) return 'var(--warning)'
        return 'var(--loss)'
    },

    ramColor(pct) {
        pct = parseFloat(pct) || 0
        if (pct >= 85) return 'danger'
        if (pct >= 70) return 'warn'
        return 'ok'
    },

    cpuColor(pct) {
        pct = parseFloat(pct) || 0
        if (pct >= 80) return 'danger'
        if (pct >= 60) return 'warn'
        return 'ok'
    },

    diskColor(pct) {
        pct = parseFloat(pct) || 0
        if (pct >= 90) return 'danger'
        if (pct >= 75) return 'warn'
        return 'ok'
    },

    drawdownClass(pct) {
        pct = parseFloat(pct) || 0
        if (pct >= 15) return 'danger'
        if (pct >= 8)  return 'caution'
        return 'safe'
    },

    edgeColor(edge) {
        if (edge == null) return 'var(--label-4)'
        edge = parseFloat(edge)
        if (edge > 10)  return 'var(--profit)'
        if (edge > 0)   return 'var(--brand)'
        if (edge > -10) return 'var(--warning)'
        return 'var(--loss)'
    },

    regimeBadgeClass(regime) {
        if (!regime) return 'regime-badge regime-unknown'
        const r = regime.toLowerCase()
        if (r.includes('trending') && r.includes('bull')) return 'regime-badge regime-trending-bull'
        if (r.includes('trending') && r.includes('bear')) return 'regime-badge regime-trending-bear'
        if (r.includes('ranging'))   return 'regime-badge regime-ranging'
        if (r.includes('expansion')) return 'regime-badge regime-expansion'
        if (r.includes('weak'))      return 'regime-badge regime-weak-trend'
        if (r.includes('chop'))      return 'regime-badge regime-chop'
        return 'regime-badge regime-unknown'
    },

    regimeTopbarClass(regime) {
        if (!regime) return 'topbar-regime'
        const r = regime.toLowerCase()
        if (r.includes('trending') && r.includes('bull')) return 'topbar-regime trending-bull'
        if (r.includes('trending') && r.includes('bear')) return 'topbar-regime trending-bear'
        if (r.includes('ranging'))   return 'topbar-regime ranging'
        if (r.includes('chop'))      return 'topbar-regime chop'
        return 'topbar-regime'
    },

    sessionBadgeClass(session) {
        if (!session) return 'session-badge session-off'
        const s = session.toLowerCase()
        if (s.includes('london') && (s.includes('ny') || s.includes('new york') || s.includes('overlap'))) {
            return 'session-badge session-london-ny'
        }
        if (s.includes('new york') || s.includes('ny')) return 'session-badge session-ny'
        if (s.includes('london'))  return 'session-badge session-london'
        if (s.includes('asian'))   return 'session-badge session-asian'
        if (s.includes('off'))     return 'session-badge session-off'
        return 'session-badge session-off'
    },

    sessionLabel(session) {
        if (!session) return 'Off Hours'
        const s = session.toLowerCase()
        if (s.includes('london') && (s.includes('ny') || s.includes('new york') || s.includes('overlap'))) {
            return 'London/NY'
        }
        if (s.includes('new york') || s.includes('ny')) return 'New York'
        if (s.includes('london'))  return 'London'
        if (s.includes('asian'))   return 'Asian'
        if (s.includes('off'))     return 'Off Hours'
        return session
    },

    sessionQuality(session) {
        if (!session) return 'off'
        const s = session.toLowerCase()
        if (s.includes('overlap') || (s.includes('london') && s.includes('ny'))) return 'best'
        if (s.includes('london') || s.includes('new york') || s.includes('ny'))  return 'good'
        if (s.includes('asian')) return 'caution'
        return 'off'
    },

    mlBadgeClass(prob) {
        if (prob == null) return ''
        prob = parseFloat(prob)
        if (prob >= 0.70) return 'ml-badge ml-badge-high'
        if (prob >= 0.55) return 'ml-badge ml-badge-medium'
        return 'ml-badge ml-badge-low'
    },

    confidenceClass(label) {
        if (!label) return 'confidence-pill'
        const l = label.toLowerCase()
        if (l.includes('very high')) return 'confidence-pill confidence-very-high'
        if (l.includes('high'))      return 'confidence-pill confidence-high'
        if (l.includes('moderate'))  return 'confidence-pill confidence-moderate'
        return 'confidence-pill confidence-low'
    },

    scoreRingDasharray(score, radius) {
        const circumference = 2 * Math.PI * radius
        const pct           = Math.min(100, Math.max(0, parseFloat(score) || 0)) / 100
        const filled        = circumference * pct
        const empty         = circumference - filled
        return `${filled} ${empty}`
    },

    confidenceScore(summary) {
        if (!summary) return 0
        let score = 50
        const regime = (summary.regime || '').toLowerCase()
        if (regime.includes('trending'))    score += 20
        else if (regime.includes('ranging')) score -= 10
        else if (regime.includes('chop'))    score -= 30
        const wr = parseFloat(summary.win_rate) || 0
        if (wr >= 60)      score += 15
        else if (wr >= 50) score += 5
        else if (wr < 40)  score -= 10
        const tradeable = parseInt(summary.tradeable_count) || 0
        if (tradeable >= 2)     score += 10
        else if (tradeable === 0) score -= 10
        return Math.min(100, Math.max(0, Math.round(score)))
    },

    truncate(str, len = 40) {
        if (!str) return '--'
        str = String(str)
        return str.length > len ? str.slice(0, len) + '…' : str
    },

    isEmpty(val) {
        if (val == null) return true
        if (Array.isArray(val)) return val.length === 0
        if (typeof val === 'object') return Object.keys(val).length === 0
        return false
    },

    clamp(val, min, max) {
        return Math.min(max, Math.max(min, val))
    },

    lerp(a, b, t) {
        return a + (b - a) * t
    },

    pct(value, total) {
        if (!total || total === 0) return 0
        return Math.min(100, Math.max(0, (value / total) * 100))
    },

    tradeProgressPct(trade) {
        const entry   = parseFloat(trade.open_rate    || 0)
        const current = parseFloat(trade.current_rate || 0)
        const sl      = parseFloat(trade.sl_signal    || trade.stop_loss_abs || 0)
        const tp      = parseFloat(trade.tp1          || 0)
        const isShort = trade.is_short

        if (!entry || !current || !sl || !tp) return { pct: 50, toward: 'neutral' }

        const totalRange = Math.abs(tp - sl)
        if (totalRange <= 0) return { pct: 50, toward: 'neutral' }

        const entryPct = (Math.abs(entry - sl) / totalRange) * 100
        const currPct  = (Math.abs(current - sl) / totalRange) * 100
        const movingTowardTp = isShort ? current < entry : current > entry

        return {
            pct:      this.clamp(currPct, 0, 100),
            entryPct: this.clamp(entryPct, 0, 100),
            toward:   movingTowardTp ? 'profit' : 'loss'
        }
    },

    segmentColors(index) {
        const colors = [
            '#007AFF', '#34C759', '#FFCC00', '#FF9500',
            '#AF52DE', '#FF3B30', '#5AC8FA', '#FF6B6B',
            '#30D158', '#32ADE6', '#FF9F0A', '#BF5AF2',
        ]
        return colors[index % colors.length]
    },

    debounce(fn, delay) {
        let timer
        return (...args) => {
            clearTimeout(timer)
            timer = setTimeout(() => fn(...args), delay)
        }
    },

    throttle(fn, limit) {
        let last = 0
        return (...args) => {
            const now = Date.now()
            if (now - last >= limit) {
                last = now
                fn(...args)
            }
        }
    },

    deepEqual(a, b) {
        return JSON.stringify(a) === JSON.stringify(b)
    },

    groupBy(arr, key) {
        return arr.reduce((acc, item) => {
            const k = typeof key === 'function' ? key(item) : item[key]
            if (!acc[k]) acc[k] = []
            acc[k].push(item)
            return acc
        }, {})
    },

    sortBy(arr, key, dir = 'asc') {
        return [...arr].sort((a, b) => {
            const av = typeof key === 'function' ? key(a) : a[key]
            const bv = typeof key === 'function' ? key(b) : b[key]
            if (av < bv) return dir === 'asc' ? -1 : 1
            if (av > bv) return dir === 'asc' ? 1  : -1
            return 0
        })
    },

    copyToClipboard(text) {
        if (navigator.clipboard) {
            return navigator.clipboard.writeText(text)
        }
        const el = document.createElement('textarea')
        el.value = text
        el.style.position = 'fixed'
        el.style.opacity  = '0'
        document.body.appendChild(el)
        el.select()
        document.execCommand('copy')
        document.body.removeChild(el)
        return Promise.resolve()
    },

    isMobile()  { return window.innerWidth <= 768;  },
    isTablet()  { return window.innerWidth > 768 && window.innerWidth <= 1024; },
}

window.Utils = Utils