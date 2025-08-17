// src/ExpenseApp.jsx
import React, { useMemo, useState, useEffect } from 'react';

const tg = window.Telegram?.WebApp;

function b64urlDecode(s) {
  if (!s) return '';
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  const pad = s.length % 4;
  if (pad) s += '='.repeat(4 - pad);
  return atob(s);
}

export default function ExpenseApp() {
  const [amount, setAmount] = useState('');
  const [desc, setDesc] = useState('');
  const [category, setCategory] = useState('');
  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    tg?.ready?.();
    // Load categories from payload (only those with a budget set)
    try {
      const params = new URLSearchParams(window.location.search);
      const p = params.get('payload');
      if (p) {
        const decoded = JSON.parse(b64urlDecode(p));
        if (decoded?.items?.length) {
          const names = decoded.items.map(it => it.name).filter(Boolean);
          setCats(names);
        }
      }
    } catch (e) { /* fallback: empty cats */ }
    setLoading(false);

    // Nice UX
    tg?.MainButton?.setText?.('Save Expense');
    tg?.MainButton?.hide?.();
  }, []);

  useEffect(() => {
    const valid = Number(amount) > 0 && category;
    if (valid) tg?.MainButton?.show?.(); else tg?.MainButton?.hide?.();
  }, [amount, category]);

  useEffect(() => {
    if (!tg) return;
    const onMainButton = () => onSave();
    tg.onEvent?.('mainButtonClicked', onMainButton);
    return () => tg.offEvent?.('mainButtonClicked', onMainButton);
  }, [amount, desc, category]);

 const onSave = () => {
  try {
    const payload = {
      type: 'expense.add',            // 👈👈 এটা ঠিক এইটাই হবে
      amount: Number(amount),
      description: desc || '',
      category,
    };
    tg?.showAlert?.('Saving your expense…');
    tg?.sendData?.(JSON.stringify(payload));
    tg?.close?.();
  } catch (e) {
    alert('Error: ' + (e?.message || e));
  }
};


  const onViewLast10 = () => {
    tg?.sendData?.(JSON.stringify({ type: 'expense.view' }));
    tg?.close?.();
  };

  const onAddNewCategory = () => {
    tg?.showAlert?.('To add a new category, please open Budget and set it first.');
    tg?.close?.();
  };

  if (loading) return <div style={{ padding: 16 }}>Loading…</div>;

  return (
    <div style={{ padding: 16, fontFamily: 'system-ui, Arial' }}>
      <h2>Quick Expense</h2>

      <div style={{ marginTop: 12 }}>
        <label style={{ width: 120, display: 'inline-block' }}>Amount</label>
        <input
          type="number"
          step="0.01"
          placeholder="0.00"
          value={amount}
          onChange={e => setAmount(e.target.value)}
          style={{ padding: 8, width: 180 }}
        />
      </div>

      <div style={{ marginTop: 12 }}>
        <label style={{ width: 120, display: 'inline-block' }}>Description</label>
        <input
          type="text"
          placeholder="optional note"
          value={desc}
          onChange={e => setDesc(e.target.value)}
          style={{ padding: 8, width: 240 }}
        />
      </div>

      <div style={{ marginTop: 12 }}>
        <label style={{ width: 120, display: 'inline-block' }}>Category</label>
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          style={{ padding: 8, width: 200 }}
        >
          <option value="">-- select --</option>
          {cats.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
          <option value="__ADD_NEW__">➕ Add New Category</option>
        </select>
        {category === '__ADD_NEW__' && (
          <div style={{ marginTop: 8 }}>
            <button onClick={onAddNewCategory}>Open Budget</button>
          </div>
        )}
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button onClick={onSave}>Save</button>
        <button onClick={onViewLast10}>View last 10</button>
      </div>

      <p style={{ marginTop: 12, opacity: 0.7 }}>
        Only categories that have a monthly budget appear here.
      </p>
    </div>
  );
}
