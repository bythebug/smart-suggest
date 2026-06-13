import { useEffect, useState } from 'react';
import { CheckCircle, Loader2, Plus, RefreshCw, X } from 'lucide-react';
import { api } from '../api.js';

const CATEGORIES = [
  'electronics', 'books', 'clothing', 'sports',
  'home_appliances', 'health', 'beauty', 'food_and_grocery', 'toys', 'automotive',
];

const CATEGORY_COLORS = {
  electronics:      'bg-blue-50 text-blue-700 border-blue-200',
  books:            'bg-amber-50 text-amber-700 border-amber-200',
  clothing:         'bg-pink-50 text-pink-700 border-pink-200',
  sports:           'bg-green-50 text-green-700 border-green-200',
  home_appliances:  'bg-orange-50 text-orange-700 border-orange-200',
  health:           'bg-teal-50 text-teal-700 border-teal-200',
  beauty:           'bg-rose-50 text-rose-700 border-rose-200',
};

// maps recommendation interaction → A/B test event type
const EVENT_MAP = { view: 'impression', click: 'click', purchase: 'purchase' };

const STRATEGIES = [
  {
    key: 'v1', variantKey: 'A',
    label: 'Strategy A', sublabel: 'Collaborative Filtering',
    tagline: 'Users who agreed in the past will agree in the future.',
    detail: 'Builds a weighted user-item interaction matrix (view=1, click=3, purchase=5), computes cosine similarity between users, and scores unseen items by neighbour agreement.',
    accent: 'border-t-blue-600',
    scoreClass: 'text-blue-600 bg-blue-50',
    pillClass: 'bg-blue-600',
  },
  {
    key: 'v2', variantKey: 'B',
    label: 'Strategy B', sublabel: 'Content-Based Filtering',
    tagline: 'Recommend items similar to what this user already liked.',
    detail: 'Runs TF-IDF on item descriptions + category indicators, pre-computes item-item cosine similarity (cached 1 hr), and scores candidates by similarity × interaction weight.',
    accent: 'border-t-violet-600',
    scoreClass: 'text-violet-600 bg-violet-50',
    pillClass: 'bg-violet-600',
  },
];

function ItemCard({ item, scoreClass, userId, linkedTest, userVariant, strategyVariantKey }) {
  const [logged, setLogged] = useState(null);
  const catClass = CATEGORY_COLORS[item.category] ?? 'bg-gray-50 text-gray-600 border-gray-200';

  async function log(action) {
    try {
      // always log user interaction (for rec engine)
      await api.logInteraction(userId, item.item_id, action);
      // if a test is linked, also fire the A/B event
      if (linkedTest && userVariant) {
        await api.logTestEvent(linkedTest.id, userId, item.item_id, EVENT_MAP[action]);
      }
      setLogged(action);
      setTimeout(() => setLogged(null), 2000);
    } catch {}
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors group">
      <div className="flex items-start justify-between gap-3 mb-2">
        <span className="text-sm font-medium text-gray-900 leading-snug">{item.name}</span>
        <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded shrink-0 ${scoreClass}`}>
          {item.score.toFixed(2)}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-xs font-medium px-2 py-0.5 rounded border ${catClass}`}>
          {item.category.replace(/_/g, ' ')}
        </span>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {logged ? (
            <span className="flex items-center gap-1 text-xs text-emerald-600">
              <CheckCircle size={12} /> {logged}
            </span>
          ) : (
            ['view', 'click', 'purchase'].map((a) => (
              <button key={a} onClick={() => log(a)}
                className="text-xs px-2 py-0.5 rounded border border-gray-200 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors capitalize">
                {a}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function Column({ strategy, recs, loading, itemMap, userId, linkedTest, userVariant, isAssigned }) {
  const items = (recs || []).map((r) => ({ ...r, ...(itemMap[r.item_id] || {}) }));

  return (
    <div className="flex-1 min-w-0">
      <div className={`bg-white border border-gray-200 rounded-xl overflow-hidden ${isAssigned ? 'ring-2 ring-offset-2 ring-blue-400' : ''}`}>
        <div className="px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold text-white px-2 py-0.5 rounded ${strategy.pillClass}`}>
              {strategy.label}
            </span>
            <span className="text-sm font-semibold text-gray-800">{strategy.sublabel}</span>
            {isAssigned && (
              <span className="ml-auto text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
                user's variant
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 italic">{strategy.tagline}</p>
        </div>
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100">
          <p className="text-xs text-gray-500 leading-relaxed">{strategy.detail}</p>
        </div>
        <div className="p-4 space-y-2 min-h-[180px]">
          {loading && (
            <div className="flex items-center justify-center h-32 text-gray-400">
              <Loader2 size={18} className="animate-spin mr-2" />
              <span className="text-sm">Loading…</span>
            </div>
          )}
          {!loading && items.length === 0 && recs !== null && (
            <div className="text-center pt-8 text-sm text-gray-400">
              No recommendations. Try a user with more interaction history (1-10).
            </div>
          )}
          {!loading && items.map((item) => (
            <ItemCard key={item.item_id} item={item}
              scoreClass={strategy.scoreClass} userId={userId}
              linkedTest={linkedTest} userVariant={userVariant}
              strategyVariantKey={strategy.variantKey} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function RecommendationsPage() {
  const [users, setUsers]       = useState([]);
  const [items, setItems]       = useState([]);
  const [tests, setTests]       = useState([]);
  const [selected, setSelected] = useState(() => Number(localStorage.getItem('ss_user')) || '');
  const [linkedTestId, setLinkedTestId] = useState(() => localStorage.getItem('ss_test') || 'none');
  const [userVariant, setUserVariant]   = useState(null); // 'A' | 'B' | null
  const [recsV1, setRecsV1]     = useState(null);
  const [recsV2, setRecsV2]     = useState(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);
  const [offline, setOffline]       = useState(false);
  const [impressionsLogged, setImpressionsLogged] = useState(null); // count
  const [manualItem, setManualItem]   = useState('');
  const [manualLogging, setManualLogging] = useState(null);
  const [manualLog, setManualLog]     = useState(null);
  const [showAddItem, setShowAddItem] = useState(false);
  const [newItem, setNewItem]   = useState({ name: '', category: CATEGORIES[0], description: '' });
  const [adding, setAdding]     = useState(false);

  const linkedTest = tests.find(t => String(t.id) === linkedTestId) ?? null;

  async function loadData() {
    const [u, i, t] = await Promise.all([api.getUsers(), api.getItems(), api.listABTests()]);
    setUsers(u); setItems(i); setTests(t);
    if (u.length && !selected) { setSelected(u[0].id); localStorage.setItem('ss_user', u[0].id); }
    if (i.length) setManualItem(i[0].id);
  }

  useEffect(() => { loadData().catch(() => setOffline(true)); }, []);

  // resolve user's variant whenever user or linked test changes
  useEffect(() => {
    if (!selected || !linkedTest) { setUserVariant(null); return; }
    api.getTestAssignment(linkedTest.id, selected)
      .then(a => setUserVariant(a.variant))
      .catch(() => setUserVariant(null));
  }, [selected, linkedTestId]);

  const itemMap = Object.fromEntries(items.map((i) => [i.id, i]));

  async function getRecs() {
    if (!selected) return;
    setLoading(true); setError(null); setRecsV1(null); setRecsV2(null); setImpressionsLogged(null);
    try {
      const [r1, r2] = await Promise.all([api.getRecsV1(selected), api.getRecsV2(selected)]);
      setRecsV1(r1.recommendations);
      setRecsV2(r2.recommendations);

      // If a test is linked, auto-log impressions for the user's assigned variant
      if (linkedTest && userVariant) {
        const assignedRecs = userVariant === 'A' ? r1.recommendations : r2.recommendations;
        await Promise.allSettled(
          assignedRecs.map(r => api.logTestEvent(linkedTest.id, selected, r.item_id, 'impression'))
        );
        setImpressionsLogged(assignedRecs.length);
      }
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function logManualEvent(eventType) {
    if (!linkedTest || !selected || !manualItem) return;
    setManualLogging(eventType);
    try {
      await api.logTestEvent(linkedTest.id, selected, manualItem, eventType);
      const itemName = items.find(i => i.id === Number(manualItem))?.name ?? 'item';
      setManualLog({ event: eventType, item: itemName });
      setTimeout(() => setManualLog(null), 3000);
    } catch (e) { alert(e.message); }
    finally { setManualLogging(null); }
  }

  async function submitItem(e) {
    e.preventDefault();
    if (!newItem.name.trim()) return;
    setAdding(true);
    try {
      await api.createItem(newItem.name, newItem.category, newItem.description);
      setNewItem({ name: '', category: CATEGORIES[0], description: '' });
      setShowAddItem(false);
      await loadData();
    } catch (err) { alert(err.message); }
    finally { setAdding(false); }
  }

  if (offline) return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
      <div className="font-semibold text-red-700 mb-1">Backend not reachable</div>
      <div className="text-sm text-red-500 font-mono">uvicorn app:app --reload</div>
    </div>
  );

  const variantStrategy = STRATEGIES.find(s => s.variantKey === userVariant);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Recommendations</h1>
          <p className="text-gray-500 text-sm mt-1">
            Compare Collaborative Filtering and Content-Based strategies side by side.
            Link to an A/B test to record real impressions, clicks, and purchases as test events.
          </p>
        </div>
        <button onClick={() => setShowAddItem(v => !v)}
          className="flex items-center gap-2 border border-gray-300 hover:border-gray-400 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors shrink-0">
          <Plus size={14} /> Add Item
          {items.length > 0 && <span className="text-gray-400 font-normal">({items.length})</span>}
        </button>
      </div>

      {/* Add item form */}
      {showAddItem && (
        <form onSubmit={submitItem} className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold text-gray-800">New Item</span>
            <button type="button" onClick={() => setShowAddItem(false)} className="text-gray-400 hover:text-gray-600">
              <X size={16} />
            </button>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Name</label>
              <input required value={newItem.name}
                onChange={e => setNewItem(v => ({ ...v, name: e.target.value }))}
                placeholder="e.g. Wireless Earbuds"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Category</label>
              <select value={newItem.category}
                onChange={e => setNewItem(v => ({ ...v, category: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">
                Description <span className="text-gray-400 font-normal">(powers content-based recs)</span>
              </label>
              <input value={newItem.description}
                onChange={e => setNewItem(v => ({ ...v, description: e.target.value }))}
                placeholder="keywords that describe this item"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
          <button type="submit" disabled={adding}
            className="flex items-center gap-2 bg-gray-900 hover:bg-gray-700 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium">
            {adding ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            {adding ? 'Adding…' : 'Add Item'}
          </button>
        </form>
      )}

      {/* Controls */}
      <div className="bg-white border border-gray-200 rounded-xl px-6 py-5 space-y-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">User</label>
            <select value={selected} onChange={(e) => { const v = Number(e.target.value); setSelected(v); localStorage.setItem('ss_user', v); }}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              {users.slice(0, 10).map((u) => (
                <option key={u.id} value={u.id}>{u.username}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Link to A/B Test
              <span className="text-gray-400 font-normal normal-case tracking-normal ml-1">(optional)</span>
            </label>
            <select value={linkedTestId} onChange={e => { setLinkedTestId(e.target.value); localStorage.setItem('ss_test', e.target.value); }}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="none">None</option>
              {tests.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>

          <button onClick={getRecs} disabled={loading || !selected}
            className="flex items-center gap-2 bg-gray-900 hover:bg-gray-700 disabled:opacity-40 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors mt-5">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Get Recommendations
          </button>
          {error && <span className="text-sm text-red-500 mt-5">{error}</span>}
        </div>
        <p className="text-xs text-gray-400">Users 1–10 have seeded history. When a test is linked, interactions also count as test events.</p>

        {/* Variant assignment banner */}
        {linkedTest && userVariant && (
          <div className={`rounded-lg px-4 py-3 text-sm border ${
            userVariant === 'A'
              ? 'bg-blue-50 border-blue-200 text-blue-800'
              : 'bg-violet-50 border-violet-200 text-violet-800'
          }`}>
            <div className="flex items-center gap-3">
              <span className={`text-xs font-bold text-white px-2 py-0.5 rounded shrink-0 ${userVariant === 'A' ? 'bg-blue-600' : 'bg-violet-600'}`}>
                Variant {userVariant}
              </span>
              <span>
                <span className="font-semibold">{users.find(u => u.id === selected)?.username}</span>
                {' '}is in{' '}
                <span className="font-semibold">{variantStrategy?.sublabel}</span>
                {' '}for <span className="font-semibold">{linkedTest.name}</span>.
              </span>
            </div>
            <div className="mt-2 text-xs opacity-80 space-y-0.5 pl-1">
              {impressionsLogged !== null
                ? <p><span className="font-semibold">{impressionsLogged} impressions</span> logged to the test. Now hover items and click <span className="font-semibold">click</span> or <span className="font-semibold">purchase</span> to record real engagement data.</p>
                : <p>Click <span className="font-semibold">Get Recommendations</span> to load items and auto-log impressions to the test.</p>
              }
            </div>
          </div>
        )}
      </div>

      {/* Columns */}
      <div className="flex gap-5">
        {STRATEGIES.map((s) => (
          <Column key={s.key} strategy={s}
            recs={s.key === 'v1' ? recsV1 : recsV2}
            loading={loading} itemMap={itemMap} userId={selected}
            linkedTest={linkedTest} userVariant={userVariant}
            isAssigned={!!linkedTest && userVariant === s.variantKey}
          />
        ))}
      </div>

      {/* Test specific items directly */}
      {linkedTest && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="mb-1">
            <span className="text-sm font-semibold text-gray-800">Test a specific item</span>
            <span className="text-xs text-gray-400 ml-2">
              Directly log events for any item in your catalog, including ones you just added.
            </span>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            Newly added items won't appear in recommendations until they have interaction history.
            Use this to test them right away.
          </p>
          <div className="flex items-end gap-3 flex-wrap">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">Item</label>
              <select
                value={manualItem}
                onChange={e => setManualItem(Number(e.target.value))}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {items.map(i => (
                  <option key={i.id} value={i.id}>{i.name}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              {['impression', 'click', 'purchase'].map(ev => (
                <button
                  key={ev}
                  onClick={() => logManualEvent(ev)}
                  disabled={!!manualLogging}
                  className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40 transition-colors capitalize"
                >
                  {manualLogging === ev ? <Loader2 size={13} className="inline animate-spin mr-1" /> : null}
                  {ev}
                </button>
              ))}
            </div>
            {manualLog && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-700">
                <CheckCircle size={13} />
                {manualLog.event} logged for <span className="font-semibold">{manualLog.item}</span>
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-3">
            Logged to <span className="font-semibold text-gray-600">{linkedTest.name}</span> as{' '}
            {users.find(u => u.id === selected)?.username ?? 'the selected user'}
            {userVariant ? ` (Variant ${userVariant})` : ''}.
          </p>
        </div>
      )}
    </div>
  );
}
