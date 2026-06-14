'use strict'

const S = {
  data:               null,
  scanning:           false,
  nextScanEpoch:      null,
  prevGrades:         {},
  lastHistoryLen:     0,
  lastTradeIds:       new Set(),
  lastState:          null,
  lastHealthStates:   {},
  _clockInterval:     null,
  _countdownInterval: null,
}


function startClock() {
  const tick = () => {
    const el = $id('live-clock')
    if (el) el.textContent = new Date().toLocaleTimeString('en-IN', {
      hour:     '2-digit',
      minute:   '2-digit',
      second:   '2-digit',
      hour12:   false,
      timeZone: 'Asia/Kolkata'
    }) + ' IST'
  }
  tick()
  S._clockInterval = setInterval(tick, 1000)
}


function startCountdown() {
  const tick = () => {
    const el = $id('countdown-val')
    if (!el) return
    if (!S.nextScanEpoch) { el.textContent = '--:--'; return }
    const rem = S.nextScanEpoch - Date.now()
    if (rem <= 0) { el.textContent = '00:00'; return }
    const m = Math.floor(rem / 60000)
    const s = Math.floor((rem % 60000) / 1000)
    el.textContent = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0')
  }
  tick()
  S._countdownInterval = setInterval(tick, 1000)
}


function applyDashboard(data) {
  S.data = data
  if (data.next_scan_epoch) S.nextScanEpoch = data.next_scan_epoch

  const prevIds       = new Set(S.lastTradeIds)
  const newIds        = new Set((data.trades || []).map(t => t.id))
  const stateChanged  = data.state !== S.lastState
  const tradesChanged = (
    newIds.size !== prevIds.size ||
    [...newIds].some(id => !prevIds.has(id))
  )

  const healthChanged = (data.trades || []).some(t => {
    return t.health_state !== S.lastHealthStates[t.id]
  })

  S.lastState = data.state
  S.lastTradeIds = newIds;
  (data.trades || []).forEach(t => {
    S.lastHealthStates[t.id] = t.health_state
  })

  if (stateChanged && data.state !== 'idle') {
    toast('⚡ Trade Active', `${data.trade?.coin || ''} ${data.trade?.direction || ''}`, 'success')
  }

  if (healthChanged) {
    (data.trades || []).forEach(t => {
      if (t.health_state === 'INVALIDATED') {
        toast(`🚨 ${t.coin} Invalidated`, 'Thesis failed — consider closing', 'error', 8000)
      } else if (t.health_state === 'WARNING') {
        toast(`⚠️ ${t.coin} Warning`, 'Thesis weakening', 'warning', 6000)
      }
    })
  }

  return { stateChanged, tradesChanged, healthChanged }
}