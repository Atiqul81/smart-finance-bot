// webapp/src/BudgetApp.jsx
import React, { useEffect, useMemo, useState } from 'react'

const tg = window?.Telegram?.WebApp

export default function BudgetApp() {
  const [rows, setRows] = useState([]) // [{id, name, setBudget, used, inHand}]
  const [dirty, setDirty] = useState(false)
  const [loading, setLoading] = useState(true)

 useEffect(() => {
  tg?.ready?.();

  function b64urlDecode(s) {
    // base64url -> base64
    s = s.replace(/-/g, '+').replace(/_/g, '/');
    const pad = s.length % 4;
    if (pad) s += '='.repeat(4 - pad);
    return atob(s);
  }

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams(window.location.search);
      const p = params.get('payload');

      if (p) {
        const decoded = JSON.parse(b64urlDecode(p));
        if (decoded?.type === 'budget.init' && Array.isArray(decoded.items)) {
          const mapped = decoded.items.map(r => ({
            id: r.id ?? Date.now() + Math.random(),
            name: r.name,
            setBudget: Number(r.setBudget || 0),
            used: Number(r.used || 0),
          }));
          setRows(mapped.map(r => ({ ...r, inHand: Number(r.setBudget) - Number(r.used) })));
          setLoading(false);
          return;
        }
      }

      // Fallback: mock data (if no payload found)
      const mock = [
        { id: 1, name: 'Food', setBudget: 150, used: 42.5 },
        { id: 2, name: 'Transport', setBudget: 80, used: 20 },
        { id: 3, name: 'Entertainment', setBudget: 50, used: 35 },
      ];
      setRows(mock.map(r => ({ ...r, inHand: Number(r.setBudget) - Number(r.used) })));
    } catch (e) {
      // in case of bad payload, still fallback
      const mock = [
        { id: 1, name: 'Food', setBudget: 150, used: 42.5 },
        { id: 2, name: 'Transport', setBudget: 80, used: 20 },
        { id: 3, name: 'Entertainment', setBudget: 50, used: 35 },
      ];
      setRows(mock.map(r => ({ ...r, inHand: Number(r.setBudget) - Number(r.used) })));
    } finally {
      setLoading(false);
    }
  }

  load();
}, []);


useEffect(() => {
  console.log('initDataUnsafe', tg?.initDataUnsafe);
  if (tg?.ready) tg.ready();
}, []);


  const totals = useMemo(() => {
    const setSum = rows.reduce((a, r) => a + Number(r.setBudget || 0), 0)
    const usedSum = rows.reduce((a, r) => a + Number(r.used || 0), 0)
    return { setSum, usedSum, inHand: setSum - usedSum }
  }, [rows])

  const onSetBudgetChange = (i, val) => {
    const v = val === '' ? '' : Math.max(0, Number(val))
    setRows(prev => prev.map((r, idx) => idx === i ? { ...r, setBudget: v, inHand: (v || 0) - Number(r.used || 0) } : r))
    setDirty(true)
  }

  const addCategory = () => {
    const name = prompt('New category name')
    if (!name) return
    setRows(prev => [...prev, { id: Date.now(), name, setBudget: 0, used: 0, inHand: 0 }])
    setDirty(true)
  }

const onSave = () => {
  try {
    const payload = {
      type: 'budget.save',
      items: rows.map(({ id, name, setBudget }) => ({
        id,
        name,
        amount: Number(setBudget || 0),
      })),
    };

    if (tg && typeof tg.sendData === 'function') {
      // optional user hint
      tg.showAlert && tg.showAlert('Sending your budget to the bot…');

      tg.sendData(JSON.stringify(payload));

      // ensure Telegram delivers the service message
      tg.close && tg.close();
    } else {
      alert('Open this page via Telegram bot button to save.');
    }
  } catch (e) {
    alert('Save error: ' + (e?.message || e));
  }
};


  return (
    <div className="p-4 text-sm" style={{ fontFamily: 'system-ui, Arial' }}>
      <h2 className="text-xl mb-3">Monthly Budget</h2>
      {loading ? <div>Loading…</div> : (
        <div className="space-y-3">
          <div className="border rounded">
            <div className="grid grid-cols-4 font-semibold p-2 bg-gray-100">
              <div>Category</div>
              <div>Set Budget</div>
              <div>Used</div>
              <div>In Hand</div>
            </div>
            {rows.map((r, i) => (
              <div key={r.id} className="grid grid-cols-4 p-2 border-t items-center">
                <div>{r.name}</div>
                <div>
                  <input type="number" min={0} value={r.setBudget} onChange={e => onSetBudgetChange(i, e.target.value)} className="w-full border rounded p-1" />
                </div>
                <div>{Number(r.used).toFixed(2)}</div>
                <div>{Number(r.inHand).toFixed(2)}</div>
              </div>
            ))}
            <div className="grid grid-cols-4 p-2 border-t font-semibold">
              <div>Total</div>
              <div>{totals.setSum.toFixed(2)}</div>
              <div>{totals.usedSum.toFixed(2)}</div>
              <div>{totals.inHand.toFixed(2)}</div>
            </div>
          </div>

          <div className="flex gap-2">
            <button onClick={addCategory} className="border rounded px-3 py-2">Add New Category</button>
            <button disabled className="border rounded px-3 py-2">Edit Budget</button>
            <button disabled={!dirty} onClick={onSave} className="border rounded px-3 py-2 {dirty ? '' : 'opacity-50'}">Save</button>
          </div>
        </div>
      )}
    </div>
  )
}