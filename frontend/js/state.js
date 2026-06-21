'use strict'

const S = {
  data:               null,
  ftData:             null,
  scanning:           false,
  nextScanEpoch:      null,
  prevGrades:         {},
  lastHistoryLen:     0,
  lastState:          null,
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

  const stateChanged = data.state !== S.lastState
  S.lastState = data.state

  ;(data.radar || []).forEach(r => {
    const prev = S.prevGrades[r.coin]
    if (prev && prev !== r.grade && r.tradeable) {
      toast(
        `🎯 Grade ${r.grade} Signal`,
        `${r.coin} ${r.direction} — Score ${r.score}`,
        r.grade === 'A+' ? 'success' : 'info'
      )
    }
    S.prevGrades[r.coin] = r.grade
  })
}