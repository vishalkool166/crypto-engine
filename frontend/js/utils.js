const Utils = {

    fmtPrice(n) {
        if (n == null || n === 0) return '--'
        n = parseFloat(n)
        if (isNaN(n)) return '--'
        if (n >= 10000)  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        if (n >= 1000)   return '$' + n.toFixed(2)
        if (n >= 100)    return '$' + n.toFixed(3)
        if (n >= 1)      return '$' + n.toFixed(4)
        if (n >= 0.1)    return '$' + n.toFixed(5)
        if (n >= 0.01)   return '$' + n.toFixed(6)
        if (n >= 0.001)  return '$' + n.toFixed(7)
        return '$' + n.toFixed(8)
    },

    fmtPnl(n) {
        if (n == null) return '--'
        n = parseFloat(n)
        if (isNaN(n)) return '--'
        const sign = n >= 0 ? '+' : '-'
        return sign + '$' + Math.abs(n).toFixed(4)
    },

    fmtPct(n) {
        if (n == null) return '--'
        n = parseFloat(n)
        if (isNaN(n)) return '--'
        const sign = n >= 0 ? '+' : ''
        return sign + n.toFixed(2) + '%'
    },

    fmtScore(n) {
        if (n == null) return '--'
        return Math.round(parseFloat(n)) + '/100'
    },

    fmtDuration(openedAt) {
        if (!openedAt) return '--'
        try {
            const opened = new Date(openedAt)
            const diff   = Date.now() - opened.getTime()
            const mins   = Math.floor(diff / 60000)
            const hrs    = Math.floor(mins / 60)
            const days   = Math.floor(hrs / 24)
            if (days > 0)  return `${days}d ${hrs % 24}h`
            if (hrs > 0)   return `${hrs}h ${mins % 60}m`
            return `${mins}m`
        } catch (e) {
            return '--'
        }
    },

    fmtTime(ts) {
        if (!ts) return '--'
        try {
            const d = new Date(ts)
            return d.toLocaleString('en-IN', {
                timeZone:    'Asia/Kolkata',
                day:         '2-digit',
                month:       'short',
                hour:        '2-digit',
                minute:      '2-digit',
                hour12:      true
            }) + ' IST'
        } catch (e) {
            return '--'
        }
    },

    fmtTimeAgo(ts) {
        if (!ts) return '--'
        try {
            const diff = Date.now() - new Date(ts).getTime()
            const mins = Math.floor(diff / 60000)
            const hrs  = Math.floor(mins / 60)
            const days = Math.floor(hrs / 24)
            if (days > 0)  return `${days}d ago`
            if (hrs > 0)   return `${hrs}h ago`
            if (mins > 0)  return `${mins}m ago`
            return 'Just now'
        } catch (e) {
            return '--'
        }
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

    pnlColor(n) {
        if (n == null) return 'var(--text-muted)'
        return parseFloat(n) >= 0 ? 'var(--green)' : 'var(--red)'
    },

    changeColor(n) {
        if (n == null) return 'var(--text-muted)'
        const v = typeof n === 'string' ? parseFloat(n) : n
        return v >= 0 ? 'var(--green)' : 'var(--red)'
    },

    gradeColor(grade) {
        const map = {
            'A+': 'var(--purple)',
            'A':  'var(--blue)',
            'B':  'var(--orange)',
            'C':  'var(--yellow)',
            'F':  'var(--text-muted)',
        }
        return map[grade] || 'var(--text-muted)'
    },

    gradeBadgeClass(grade) {
        const map = {
            'A+': 'badge-aplus',
            'A':  'badge-a',
            'B':  'badge-b',
            'C':  'badge-c',
            'F':  'badge-f',
        }
        return 'badge ' + (map[grade] || 'badge-f')
    },

    dirBadgeClass(dir) {
        const map = {
            'LONG':     'badge-long',
            'SHORT':    'badge-short',
            'WATCH':    'badge-watch',
            'NO TRADE': 'badge-f',
        }
        return 'badge ' + (map[dir] || 'badge-f')
    },

    outcomeBadgeClass(outcome) {
        const map = {
            'win':     'badge-win',
            'loss':    'badge-loss',
            'pending': 'badge-pending',
            'timeout': 'badge-f',
        }
        return 'badge ' + (map[outcome] || 'badge-f')
    },

    healthBadgeClass(state) {
        const map = {
            'HEALTHY':     'badge-healthy',
            'WARNING':     'badge-warning',
            'INVALIDATED': 'badge-invalidated',
        }
        return 'badge ' + (map[state] || 'badge-f')
    },

    healthBarClass(state) {
        const map = {
            'HEALTHY':     'healthy',
            'WARNING':     'warning',
            'INVALIDATED': 'invalidated',
        }
        return 'health-bar ' + (map[state] || '')
    },

    healthEmoji(state) {
        const map = {
            'HEALTHY':     '✅',
            'WARNING':     '⚠️',
            'INVALIDATED': '🚨',
        }
        return map[state] || '⏳'
    },

    scoreBarColor(score) {
        score = parseFloat(score) || 0
        if (score >= 85) return 'var(--purple)'
        if (score >= 68) return 'var(--blue)'
        if (score >= 52) return 'var(--orange)'
        if (score >= 38) return 'var(--yellow)'
        return 'var(--text-muted)'
    },

    ramColor(pct) {
        pct = parseFloat(pct) || 0
        if (pct >= 85) return 'var(--red)'
        if (pct >= 70) return 'var(--orange)'
        return 'var(--green)'
    },

    cpuColor(pct) {
        pct = parseFloat(pct) || 0
        if (pct >= 80) return 'var(--red)'
        if (pct >= 60) return 'var(--orange)'
        return 'var(--green)'
    },

    diskColor(pct) {
        pct = parseFloat(pct) || 0
        if (pct >= 90) return 'var(--red)'
        if (pct >= 75) return 'var(--orange)'
        return 'var(--blue)'
    },

    winRateColor(wr) {
        wr = parseFloat(wr) || 0
        if (wr >= 55) return 'var(--green)'
        if (wr >= 45) return 'var(--orange)'
        return 'var(--red)'
    },

    edgeColor(edge) {
        if (edge == null) return 'var(--text-muted)'
        edge = parseFloat(edge)
        if (edge > 10)  return 'var(--green)'
        if (edge > 0)   return 'var(--blue)'
        if (edge > -10) return 'var(--orange)'
        return 'var(--red)'
    },

    dirEmoji(dir) {
        const map = {
            'LONG':  '📈',
            'SHORT': '📉',
            'WATCH': '👁',
        }
        return map[dir] || '—'
    },

    gradeEmoji(grade) {
        const map = {
            'A+': '🏆',
            'A':  '✅',
            'B':  '👀',
            'C':  '⏳',
            'F':  '🚫',
        }
        return map[grade] || '—'
    },

    truncate(str, len = 40) {
        if (!str) return '--'
        return str.length > len ? str.slice(0, len) + '...' : str
    },

    isEmpty(val) {
        if (val == null) return true
        if (Array.isArray(val)) return val.length === 0
        if (typeof val === 'object') return Object.keys(val).length === 0
        return false
    },

    progressBar(pct, color) {
        pct   = Math.min(100, Math.max(0, parseFloat(pct) || 0))
        color = color || 'var(--blue)'
        return `
            <div class="progress-bar">
                <div class="progress-fill" style="width:${pct}%;background:${color};"></div>
            </div>
        `
    },

    scoreBar(score) {
        score = parseFloat(score) || 0
        const color = Utils.scoreBarColor(score)
        return `
            <div class="score-bar">
                <span class="mono" style="font-size:12px;font-weight:600;color:${color};min-width:32px;">${Math.round(score)}</span>
                <div class="score-bar-track">
                    <div class="score-bar-fill" style="width:${score}%;background:${color};"></div>
                </div>
            </div>
        `
    },

    emptyState(message = 'No data available') {
        return `
            <div class="empty-state">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span class="empty-state-text">${message}</span>
            </div>
        `
    },

    loadingState() {
        return `
            <div class="empty-state">
                <div class="spinner"></div>
                <span class="empty-state-text">Loading...</span>
            </div>
        `
    },
}

window.Utils = Utils