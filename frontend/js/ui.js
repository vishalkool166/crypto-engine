'use strict'

const C = {
  green:      '#34c759',
  green_dark: '#248a3d',
  green_bg:   'rgba(52,199,89,0.10)',
  red:        '#ff3b30',
  red_dark:   '#c0392b',
  red_bg:     'rgba(255,59,48,0.10)',
  blue:       '#0071e3',
  blue_dark:  '#0051a8',
  blue_bg:    'rgba(0,113,227,0.10)',
  orange:     '#e8820c',
  orange_bg:  'rgba(255,149,0,0.10)',
  purple:     '#7d3dbd',
  muted:      '#6e6e73',
  text:       '#1d1d1f',
  text2:      '#3a3a3c',
}

function $id(id) {
  return document.getElementById(id)
}

function $set(id, opts = {}) {
  const el = $id(id)
  if (!el) return
  if (opts.text  !== undefined && opts.text !== null) el.textContent    = opts.text
  if (opts.color !== undefined)                       el.style.color    = opts.color
  if (opts.bg    !== undefined)                       el.style.background = opts.bg
  if (opts.width !== undefined)                       el.style.width    = Math.min(100, opts.width || 0) + '%'
  if (opts.html  !== undefined)                       el.innerHTML      = opts.html
}

function $badge(id, text, color, borderColor) {
  const el = $id(id)
  if (!el) return
  el.textContent       = text
  el.style.color       = color
  el.style.borderColor = (borderColor || color) + '40'
  el.style.background  = color + '12'
}

function toast(title, body = '', type = 'info', dur = 5000) {
  const accent = { info: C.blue, success: C.green, warning: C.orange, error: C.red }
  const icons  = { info: '💬', success: '✅', warning: '⚠️', error: '❌' }

  const el = document.createElement('div')
  el.className = 'animate-slide-in glass-strong rounded-apple-sm shadow-apple-md'
  el.style.cssText = `
    pointer-events:auto;
    border-left: 4px solid ${accent[type] || accent.info};
    padding: 14px;
    max-width: 320px;
  `
  el.innerHTML = `
    <div style="display:flex;align-items:flex-start;gap:10px">
      <span style="font-size:16px;margin-top:1px;flex-shrink:0">${icons[type]}</span>
      <div>
        <div style="font-weight:600;font-size:12px;color:#1d1d1f;line-height:1.3">${title}</div>
        ${body ? `<div style="font-size:11px;margin-top:3px;color:#6e6e73;line-height:1.4">${body}</div>` : ''}
      </div>
    </div>`

  $id('toasts').appendChild(el)
  setTimeout(() => {
    el.classList.remove('animate-slide-in')
    el.classList.add('animate-fade-out')
    setTimeout(() => el.remove(), 300)
  }, dur)
}

function gradeColor(grade) {
  return { 'A+': C.green, 'A': C.blue, 'B': C.orange, 'C': '#7d5a00', 'F': C.muted }[grade] || C.muted
}

function pnlColor(n) {
  try { return parseFloat(n) >= 0 ? C.green_dark : C.red_dark }
  catch { return C.muted }
}

function progressColor(pct) {
  if (pct >= 75) return C.green
  if (pct >= 50) return C.blue
  if (pct >= 25) return C.orange
  return C.red
}

function healthColor(state) {
  return { HEALTHY: C.green_dark, WARNING: C.orange, INVALIDATED: C.red_dark }[state] || C.muted
}

function healthEmoji(state) {
  return { HEALTHY: '✅', WARNING: '⚠️', INVALIDATED: '🚨' }[state] || '—'
}

function fmtPrice(n) {
  if (n === null || n === undefined || n === 0) return '--'
  try {
    n = parseFloat(n)
    if (n >= 1000)  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    if (n >= 100)   return '$' + n.toFixed(2)
    if (n >= 1)     return '$' + n.toFixed(4)
    if (n >= 0.01)  return '$' + n.toFixed(6)
    return '$' + n.toFixed(8)
  } catch { return '--' }
}

function fmtPnl(n) {
  if (n === null || n === undefined) return '--'
  try {
    n = parseFloat(n)
    return (n >= 0 ? '+$' : '-$') + Math.abs(n).toFixed(4)
  } catch { return '--' }
}

function fmtPct(n) {
  if (n === null || n === undefined) return '--'
  try {
    n = parseFloat(n)
    return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
  } catch { return '--' }
}

function setWsStatus(connected) {
  const dot  = document.querySelector('.ws-dot')
  const text = $id('ws-status-text')
  if (dot)  dot.style.background = connected ? C.green : C.muted
  if (text) text.textContent     = connected ? 'live' : 'connecting'
}

function showSpinner(id) {
  const el = $id(id)
  if (el) el.innerHTML = '<div class="spinner"></div>'
}

function showTotpModal(title, onConfirm) {
  const existing = $id('totp-modal-el')
  if (existing) existing.remove()

  const overlay = document.createElement('div')
  overlay.id        = 'totp-modal-el'
  overlay.className = 'totp-modal-overlay'
  overlay.innerHTML = `
    <div class="totp-modal">
      <div style="font-size:24px;text-align:center;margin-bottom:12px">🔐</div>
      <div style="font-weight:700;font-size:16px;text-align:center;margin-bottom:8px">${title}</div>
      <div style="font-size:13px;color:#6e6e73;text-align:center;margin-bottom:20px">Enter your 6-digit authenticator code</div>
      <input
        id="totp-input"
        type="number"
        placeholder="000000"
        maxlength="6"
        style="width:100%;padding:14px;border:1.5px solid rgba(0,0,0,0.1);border-radius:12px;font-size:24px;font-family:monospace;text-align:center;letter-spacing:0.2em;outline:none;margin-bottom:16px"
      >
      <div style="display:flex;gap:12px">
        <button onclick="closeTotpModal()"
                style="flex:1;padding:12px;border-radius:12px;border:1px solid rgba(0,0,0,0.1);background:rgba(0,0,0,0.04);font-weight:600;font-size:13px;cursor:pointer">
          Cancel
        </button>
        <button id="totp-confirm-btn"
                style="flex:1;padding:12px;border-radius:12px;border:none;background:#0071e3;color:white;font-weight:600;font-size:13px;cursor:pointer"
                onclick="confirmTotp()">
          Confirm
        </button>
      </div>
      <div id="totp-error" style="margin-top:12px;font-size:12px;color:#ff3b30;text-align:center;display:none"></div>
    </div>`

  document.body.appendChild(overlay)

  window._totpCallback = onConfirm

  setTimeout(() => {
    const inp = $id('totp-input')
    if (inp) {
      inp.focus()
      inp.addEventListener('input', () => {
        if (inp.value.length > 6) inp.value = inp.value.slice(0, 6)
      })
      inp.addEventListener('keydown', e => {
        if (e.key === 'Enter') confirmTotp()
      })
    }
  }, 100)
}

function closeTotpModal() {
  const el = $id('totp-modal-el')
  if (el) el.remove()
  window._totpCallback = null
}

function confirmTotp() {
  const inp  = $id('totp-input')
  const err  = $id('totp-error')
  const code = inp ? inp.value.trim() : ''

  if (code.length !== 6) {
    if (err) { err.textContent = 'Enter your 6-digit code'; err.style.display = 'block' }
    return
  }

  if (window._totpCallback) {
    window._totpCallback(code)
  }
  closeTotpModal()
}