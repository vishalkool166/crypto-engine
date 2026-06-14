'use strict'

const _modalCache = {}

function showCoinDetail(coin) {
  const overlay = $id('modal-overlay')
  const title   = $id('modal-title')
  const body    = $id('modal-body')

  title.textContent = `${coin}USDT — Loading...`
  body.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:center;gap:12px;padding:64px 0;color:#6e6e73;font-size:12px">
      <div class="spinner"></div>
      Fetching analysis...
    </div>`

  overlay.classList.remove('hidden')
  overlay.classList.add('flex')

  const cached = _modalCache[coin]
  if (cached && Date.now() - cached.ts < 300000) {
    _renderModalData(coin, cached.data, title, body)
    return
  }

  fetchCoinDetail(coin)
    .then(data => {
      if (!data) return
      _modalCache[coin] = { data, ts: Date.now() }
      _renderModalData(coin, data, title, body)
    })
    .catch(e => {
      body.innerHTML = `
        <div style="text-align:center;padding:40px 0;color:#ff3b30;font-size:12px">
          Failed to load: ${e.message}
        </div>`
    })
}

function closeModal() {
  const overlay = $id('modal-overlay')
  overlay.classList.add('hidden')
  overlay.classList.remove('flex')
}

function showConfirmClose(tradeId = null) {
  const d = S.data
  if (!d || d.state === 'idle') {
    toast('⚠️ No active trade', '', 'warning')
    return
  }

  const trades = d.trades || []
  const t      = tradeId
    ? trades.find(tr => tr.id === tradeId)
    : trades[0]

  if (!t) {
    toast('⚠️ Trade not found', '', 'warning')
    return
  }

  const title   = $id('modal-title')
  const body    = $id('modal-body')
  const overlay = $id('modal-overlay')

  title.textContent = `Close ${t.coin} ${t.direction}?`

  body.innerHTML = `
    <div style="margin-bottom:16px">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
        <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:12px">
          <div class="section-label" style="margin-bottom:4px">Entry</div>
          <div style="font-family:monospace;font-weight:600;font-size:14px">${t.entry_price}</div>
        </div>
        <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:12px">
          <div class="section-label" style="margin-bottom:4px">Current</div>
          <div style="font-family:monospace;font-weight:600;font-size:14px;color:${t.current_color}">${t.current_price}</div>
        </div>
        <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:12px">
          <div class="section-label" style="margin-bottom:4px">uPnL</div>
          <div style="font-family:monospace;font-weight:600;font-size:14px;color:${t.pnl_color}">${t.pnl}</div>
        </div>
        <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:12px">
          <div class="section-label" style="margin-bottom:4px">Health</div>
          <div style="font-weight:600;font-size:14px;color:${t.health_color}">${t.health_emoji} ${t.health_state}</div>
        </div>
      </div>
      <p style="font-size:12px;color:#6e6e73;margin-bottom:16px;text-align:center">
        This cancels all SL/TP orders and closes at market price.
      </p>
      <div style="display:flex;gap:12px">
        <button onclick="closeModal()"
                style="flex:1;padding:12px;border-radius:12px;border:1px solid rgba(0,0,0,0.1);background:rgba(0,0,0,0.04);font-weight:600;font-size:13px;cursor:pointer">
          Cancel
        </button>
        <button onclick="closeModal();closeTrade(${tradeId || ''})"
                class="btn-danger"
                style="flex:1">
          ✅ Yes, Close
        </button>
      </div>
    </div>`

  overlay.classList.remove('hidden')
  overlay.classList.add('flex')
}

function _renderModalData(coin, data, title, body) {
  const grade   = data.grade  || 'F'
  const dir     = data.direction || '--'
  const score   = data.score  || 0
  const sig     = data.signal || {}
  const wconf   = data.wconf  || {}
  const factors = wconf.factors || []
  const noTrade = data.no_trade || {}
  const hards   = noTrade.hard_blocks || []
  const softs   = noTrade.soft_blocks || []
  const sweep   = data.sweep  || {}
  const disp    = data.displacement || {}
  const retest  = data.retest || {}
  const market  = data.market || {}
  const expl    = data.explanation || {}
  const ob      = data.d4h?.order_blocks || {}

  const gc = gradeColor(grade)

  title.textContent = `${coin}USDT — Grade ${grade} ${dir} — Score ${score}/100`

  body.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
      <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:12px">
        <div class="section-label" style="margin-bottom:8px">Market</div>
        <div style="font-family:monospace;font-weight:700;font-size:14px;color:#1d1d1f">
          ${market.price ? '$' + Number(market.price).toLocaleString() : '--'}
          <span style="font-size:12px;font-weight:600;margin-left:4px;color:${(market.change24||0)>=0?'#34c759':'#ff3b30'}">
            ${(market.change24||0)>=0?'+':''}${Number(market.change24||0).toFixed(2)}%
          </span>
        </div>
        <div style="font-size:10px;color:#6e6e73;margin-top:4px">${data.regime||'--'} · ${data.session||'--'}</div>
        <div style="font-size:10px;color:#6e6e73;margin-top:2px">
          Funding: ${(Number(market.funding||0)*100).toFixed(4)}%
        </div>
        ${expl.confidence_label ? `<div style="font-size:10px;margin-top:4px;font-weight:600;color:${gc}">Confidence: ${expl.confidence_label} (${score}/100)</div>` : ''}
      </div>

      <div style="background:rgba(0,0,0,0.04);border-radius:12px;padding:12px">
        <div class="section-label" style="margin-bottom:8px">Engines</div>
        ${_engineRow('Sweep',  sweep.confirmed,  sweep.score  || 0, 12)}
        ${_engineRow('Disp',   disp.confirmed,   disp.score   || 0, 11)}
        ${_engineRow('Retest', retest.confirmed, retest.score || 0, 12, retest.failed)}
        ${ob.label ? _engineRow('OB', ob.score >= 3, ob.score || 0, 10) : ''}
      </div>
    </div>

    ${expl.thesis ? `
      <div style="margin-bottom:12px">
        <div class="section-label" style="margin-bottom:6px">Why This Trade</div>
        <div class="thesis-block">${expl.thesis}</div>
      </div>` : ''}

    ${expl.risk_thesis ? `
      <div style="margin-bottom:12px">
        <div class="section-label" style="margin-bottom:6px">Risk Factors</div>
        <div class="risk-block">${expl.risk_thesis}</div>
      </div>` : ''}

    ${expl.no_trade_reason ? `
      <div style="margin-bottom:12px">
        <div class="section-label" style="margin-bottom:6px">Why No Trade</div>
        <div class="no-trade-block">${expl.no_trade_reason}</div>
      </div>` : ''}

    ${(grade === 'A+' || grade === 'A') ? `
      <div style="border-radius:12px;padding:12px;margin-bottom:12px;background:${gc}10;border:1px solid ${gc}25">
        <div class="section-label" style="margin-bottom:8px">Signal Levels</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
          ${_levelCell('Entry', sig.entry, '#0071e3')}
          ${_levelCell('Stop',  sig.sl,    '#ff3b30')}
          ${_levelCell('TP1',   sig.tp1,   '#34c759')}
          ${_levelCell('TP2',   sig.tp2,   '#34c759')}
        </div>
        <div style="display:flex;gap:16px;margin-top:8px;padding-top:8px;border-top:1px solid rgba(0,0,0,0.06);font-size:10px;color:#6e6e73">
          <span>SL: ${sig.sl_pct ? Number(sig.sl_pct).toFixed(2)+'%' : '--'}</span>
          <span>Risk: $${sig.risk_amt ? Number(sig.risk_amt).toFixed(2) : '--'}</span>
          <span>Size: $${sig.pos_size ? Number(sig.pos_size).toFixed(2) : '--'}</span>
          <span>Lev: ${sig.eff_lev||'--'}x</span>
        </div>
      </div>` : ''}

    ${hards.length ? `
      <div style="border-radius:12px;padding:12px;margin-bottom:12px;background:rgba(255,59,48,0.06);border:1px solid rgba(255,59,48,0.2)">
        ${hards.map(b => `
          <div style="display:flex;align-items:flex-start;gap:8px;font-size:12px;margin-bottom:4px">
            <span style="flex-shrink:0">🚫</span>
            <div>
              <span style="font-weight:600;color:#ff3b30">${b.reason}</span>
              <span style="color:#6e6e73;margin-left:4px">— ${b.detail}</span>
            </div>
          </div>`).join('')}
      </div>` : ''}

    ${softs.length ? `
      <div style="border-radius:12px;padding:12px;margin-bottom:12px;background:rgba(255,149,0,0.06);border:1px solid rgba(255,149,0,0.2)">
        ${softs.map(s => `
          <div style="display:flex;align-items:flex-start;gap:8px;font-size:12px;margin-bottom:4px">
            <span style="flex-shrink:0">⚠️</span>
            <div>
              <span style="color:#1d1d1f">${s.reason}</span>
              <span style="font-family:monospace;color:#ff3b30;margin-left:4px">(-${s.penalty}pts)</span>
            </div>
          </div>`).join('')}
      </div>` : ''}

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <div class="section-label">Confluence Factors</div>
      <div style="font-size:10px;color:#6e6e73;font-family:monospace">
        ${wconf.total_earned||0} / ${wconf.max_possible||0} pts → ${score}/100
      </div>
    </div>

    <div style="display:flex;flex-direction:column;gap:8px">
      ${factors.map(f => {
        const pct   = Math.round(f.earned / f.max * 100)
        const color = f.pass ? '#34c759' : pct >= 50 ? '#ff9500' : '#ff3b30'
        return `
          <div style="display:flex;align-items:center;gap:12px" title="${f.detail||''}">
            <span style="font-size:10px;color:#6e6e73;width:140px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${f.label}</span>
            <div class="progress-track" style="flex:1;height:6px">
              <div class="bar" style="height:100%;border-radius:100px;width:${pct}%;background:${color}"></div>
            </div>
            <span style="font-family:monospace;font-size:10px;width:32px;text-align:right;flex-shrink:0;font-weight:600;color:${color}">${f.earned}/${f.max}</span>
            <span style="font-size:10px;width:16px;text-align:center;flex-shrink:0">${f.pass?'✅':'❌'}</span>
          </div>`
      }).join('')}
    </div>
  `
}

function _engineRow(label, confirmed, score, max, failed = false) {
  const color = confirmed ? '#34c759' : failed ? '#ff3b30' : '#6e6e73'
  const icon  = confirmed ? '✅' : failed ? '❌' : '⏳'
  return `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
      <span style="font-size:12px;color:#6e6e73">${label}</span>
      <span style="font-family:monospace;font-size:12px;font-weight:600;color:${color}">
        ${icon} ${score}/${max}
      </span>
    </div>`
}

function _levelCell(label, val, color) {
  return `
    <div>
      <div class="section-label" style="margin-bottom:4px">${label}</div>
      <div style="font-family:monospace;font-weight:600;font-size:12px;color:${color}">
        ${val ? '$'+Number(val).toFixed(4) : '--'}
      </div>
    </div>`
}