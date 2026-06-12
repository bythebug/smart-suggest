import { useEffect, useState } from 'react';
import { CheckCircle, Loader2, RefreshCw, ShoppingCart, Tag } from 'lucide-react';
import { api } from '../api.js';

const CATEGORY_COLORS = {
  electronics:      'bg-blue-100 text-blue-700',
  books:            'bg-yellow-100 text-yellow-700',
  clothing:         'bg-pink-100 text-pink-700',
  sports:           'bg-green-100 text-green-700',
  home_appliances:  'bg-orange-100 text-orange-700',
  health:           'bg-teal-100 text-teal-700',
  beauty:           'bg-rose-100 text-rose-700',
  food_and_grocery: 'bg-lime-100 text-lime-700',
  automotive:       'bg-slate-100 text-slate-700',
  toys:             'bg-purple-100 text-purple-700',
};

const STRATEGIES = [
  {
    key: 'v1',
    label: 'Strategy A — Collaborative Filtering',
    tagline: 'Users who agreed in the past will agree in the future.',
    detail: 'Builds a weighted user-item interaction matrix (view=1, click=3, purchase=5), finds top-K cosine-similar neighbours, and scores unseen items by neighbour agreement.',
    headerClass: 'bg-indigo-600',
    badgeClass: 'bg-indigo-100 text-indigo-700',
    scoreBg: 'bg-indigo-50',
    scoreText: 'text-indigo-600',
  },
  {
    key: 'v2',
    label: 'Strategy B — Content-Based Filtering',
    tagline: 'Recommend items similar to what this user already liked.',
    detail: 'Builds TF-IDF item feature vectors from descriptions + category, computes item-item cosine similarity (cached), and scores candidates by similarity × interaction weight.',
    headerClass: 'bg-violet-600',
    badgeClass: 'bg-violet-100 text-violet-700',
    scoreBg: 'bg-violet-50',
    scoreText: 'text-violet-600',
  },
];

function ItemCard({ item, strategyKey, badgeClass, scoreBg, scoreText, userId, onLogged }) {
  const [status, setStatus] = useState(null); // null | 'loading' | 'done'

  async function log(action) {
    setStatus('loading');
    try {
      await api.logInteraction(userId, item.item_id, action);
      setStatus('done');
      onLogged?.();
      setTimeout(() => setStatus(null), 2000);
    } catch {
      setStatus(null);
    }
  }

  const catColor = CATEGORY_COLORS[item.category] ?? 'bg-slate-100 text-slate-600';

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col gap-2 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-slate-800 leading-snug">{item.name}</span>
        <span className={`${scoreBg} ${scoreText} text-xs font-mono font-semibold px-2 py-0.5 rounded shrink-0`}>
          {item.score.toFixed(2)}
        </span>
      </div>
      <span className={`${catColor} text-xs font-medium px-2 py-0.5 rounded-full w-fit`}>
        {item.category.replace(/_/g, ' ')}
      </span>
      <div className="flex gap-1.5 mt-1">
        {['view', 'click', 'purchase'].map((action) => (
          <button
            key={action}
            onClick={() => log(action)}
            disabled={status !== null}
            className="text-xs px-2 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50 capitalize transition-colors"
          >
            {action === 'purchase' ? <ShoppingCart size={11} className="inline mr-0.5" /> : null}
            {action}
          </button>
        ))}
        {status === 'loading' && <Loader2 size={14} className="text-slate-400 animate-spin self-center ml-1" />}
        {status === 'done' && <CheckCircle size={14} className="text-emerald-500 self-center ml-1" />}
      </div>
    </div>
  );
}

function StrategyColumn({ strategy, recs, loading, error, userId, itemMap, onLogged }) {
  const items = (recs || []).map((r) => ({ ...r, ...(itemMap[r.item_id] || {}) }));

  return (
    <div className="flex flex-col gap-0 flex-1 min-w-0">
      {/* Header */}
      <div className={`${strategy.headerClass} rounded-t-xl px-5 py-4 text-white`}>
        <div className="text-sm font-bold mb-1">{strategy.label}</div>
        <div className="text-xs text-white/80 italic">{strategy.tagline}</div>
      </div>

      {/* Strategy info */}
      <div className="bg-slate-50 border-x border-slate-200 px-5 py-3">
        <p className="text-xs text-slate-600 leading-relaxed">{strategy.detail}</p>
      </div>

      {/* Results */}
      <div className="border border-t-0 border-slate-200 rounded-b-xl bg-slate-50 px-4 py-4 flex flex-col gap-2 min-h-[200px]">
        {loading && (
          <div className="flex items-center justify-center h-32 text-slate-400">
            <Loader2 size={20} className="animate-spin mr-2" /> Loading…
          </div>
        )}
        {error && (
          <div className="text-sm text-red-500 px-2">{error}</div>
        )}
        {!loading && !error && items.length === 0 && recs !== null && (
          <div className="text-sm text-slate-400 text-center pt-8">
            No recommendations — try a user with more interaction history (users 1-10).
          </div>
        )}
        {!loading && items.map((item) => (
          <ItemCard
            key={item.item_id}
            item={item}
            strategyKey={strategy.key}
            badgeClass={strategy.badgeClass}
            scoreBg={strategy.scoreBg}
            scoreText={strategy.scoreText}
            userId={userId}
            onLogged={onLogged}
          />
        ))}
      </div>
    </div>
  );
}

export default function RecommendationsPage() {
  const [users, setUsers] = useState([]);
  const [items, setItems] = useState([]);
  const [selectedUser, setSelectedUser] = useState('');
  const [recsV1, setRecsV1] = useState(null);
  const [recsV2, setRecsV2] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [backendError, setBackendError] = useState(false);

  useEffect(() => {
    Promise.all([api.getUsers(), api.getItems()])
      .then(([u, i]) => {
        setUsers(u);
        setItems(i);
        if (u.length > 0) setSelectedUser(u[0].id);
      })
      .catch(() => setBackendError(true));
  }, []);

  const itemMap = Object.fromEntries(items.map((i) => [i.id, i]));

  async function getRecs() {
    if (!selectedUser) return;
    setLoading(true);
    setError(null);
    setRecsV1(null);
    setRecsV2(null);
    try {
      const [r1, r2] = await Promise.all([
        api.getRecsV1(selectedUser),
        api.getRecsV2(selectedUser),
      ]);
      setRecsV1(r1.recommendations);
      setRecsV2(r2.recommendations);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (backendError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
        <div className="text-red-600 font-semibold mb-2">Backend not reachable</div>
        <div className="text-sm text-red-500">Start the API with <code className="bg-red-100 px-1 rounded">uvicorn app:app --reload</code></div>
      </div>
    );
  }

  const displayUsers = users.slice(0, 10);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Recommendations</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Compare Collaborative Filtering and Content-Based recommendations side by side.
          Log interactions to influence future recommendations.
        </p>
      </div>

      {/* User selector */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 flex items-end gap-4 flex-wrap">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">User</label>
          <select
            value={selectedUser}
            onChange={(e) => setSelectedUser(Number(e.target.value))}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {displayUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username} (id: {u.id})
              </option>
            ))}
          </select>
          <span className="text-xs text-slate-400">Users 1-10 have rich interaction history</span>
        </div>
        <button
          onClick={getRecs}
          disabled={loading || !selectedUser}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          Get Recommendations
        </button>
      </div>

      {/* Columns */}
      <div className="flex gap-4 items-start">
        {STRATEGIES.map((strategy) => (
          <StrategyColumn
            key={strategy.key}
            strategy={strategy}
            recs={strategy.key === 'v1' ? recsV1 : recsV2}
            loading={loading}
            error={error}
            userId={selectedUser}
            itemMap={itemMap}
            onLogged={() => {}}
          />
        ))}
      </div>

      {/* Hint */}
      {(recsV1 || recsV2) && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-5 py-3 text-sm text-amber-700">
          <Tag size={14} className="inline mr-1.5 align-middle" />
          Log interactions (view / click / purchase) to update the user's preference profile and change future recommendations.
        </div>
      )}
    </div>
  );
}
