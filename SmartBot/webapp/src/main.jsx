import React from 'react'
import ReactDOM from 'react-dom/client'
import BudgetApp from './BudgetApp.jsx'
import ExpenseApp from './ExpenseApp.jsx'

// ----- UTF-8 safe Base64URL decode -----
function b64urlToUtf8(jsonB64url) {
  if (!jsonB64url) return ''
  let s = jsonB64url.replace(/-/g, '+').replace(/_/g, '/')
  const pad = s.length % 4
  if (pad) s += '='.repeat(4 - pad)
  const bin = atob(s)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new TextDecoder('utf-8').decode(bytes)
}

function AppChooser() {
  const params = new URLSearchParams(window.location.search)
  const hash = (window.location.hash || '').replace(/^#\/?/, '').trim()
  const path = (window.location.pathname || '/').replace(/\/+$/, '')

  // 1) payload.ui (highest priority)
  let ui = ''
  const p = params.get('payload')
  if (p) {
    try {
      const txt = b64urlToUtf8(p)
      const decoded = JSON.parse(txt)
      ui = (decoded && decoded.ui) || ''
    } catch (_) {}
  }

  // 2) fallbacks: query / path / hash
  const viewQ = params.get('view') || ''
  const viewP = path.endsWith('/expense') ? 'expense' : (path.endsWith('/budget') ? 'budget' : '')
  const viewH = hash === 'expense' ? 'expense' : (hash === 'budget' ? 'budget' : '')

  // decision order: payload.ui > query > path > hash (first non-empty wins)
  const choice = ui || viewQ || viewP || viewH || 'budget'

  // Optional: inline debug banner (enable via ?debug=1)
  const debug = params.get('debug') === '1'
  const Banner = debug ? (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, padding: 8,
      background: '#222', color: '#fff', fontSize: 12, zIndex: 9999
    }}>
      <div><b>DEBUG</b> choice={choice} ui={ui} q={viewQ} p={viewP} h={viewH}</div>
      <div>href={window.location.href}</div>
    </div>
  ) : null

  if (choice === 'expense') return (<><ExpenseApp />{Banner}</>)
  return (<><BudgetApp />{Banner}</>)
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AppChooser />
  </React.StrictMode>
)
