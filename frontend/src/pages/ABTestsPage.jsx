import { useEffect, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  AlertCircle, CheckCircle2, FlaskConical, Loader2,
  Plus, TrendingUp, XCircle,
} from 'lucide-react';
import { api } from '../api.js';

function pct(n) { return n != null ? `${(n * 100).toFixed(1)}%` : '—'; }
function fmt(n, digits = 4) { return n != null ? n.toFixed(digits) : '—'; }

function MetricCard({ label, variantA, variantB, liftAbs, liftPct, format = pct }) {
  const better = liftAbs > 0 ? 'B' : liftAbs < 0 ? 'A' : null;
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">{label}</div>
      <div className="flex gap-4 mb-3">
        <div className="flex-1">
          <div className={`text-2xl font-bold ${better === 'A' ? 'text-indigo-700' : 'text-slate-800'}`}>
            {format(variantA)}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Variant A (CF)</div>
        </div>
        <div className="flex-1">
          <div className={`text-2xl font-bold ${better === 'B' ? 'text-violet-700' : 'text-slate-800'}`}>
            {format(variantB)}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Variant B (Content)</div>
        </div>
      </div>
      {liftAbs != null && (
        <div className={`text-xs font-medium ${liftAbs > 0 ? 'text-emerald-600' : liftAbs < 0 ? 'text-red-500' : 'text-slate-400'}`}>
          {liftAbs > 0 ? '↑' : liftAbs < 0 ? '↓' : ''} {Math.abs(liftPct).toFixed(1)}% relative lift
        </div>
      )}
    </div>
  );
}

function SignificanceBanner({ testResult }) {
  if (!testResult?.statistical_tests) return null;
  const ctrTest = testResult.statistical_tests.ctr;
  const pVal = ctrTest?.p_value ?? ctrTest?.pvalue;
  if (pVal == null) return null;

  const sig = pVal < 0.05;
  const liftPct = testResult.lift?.ctr_relative_pct;
  const winner = (testResult.lift?.ctr_absolute ?? 0) >= 0 ? 'Variant B' : 'Variant A';

  if (sig) {
    return (
      <div className="flex items-start gap-3 bg-emerald-50 border border-emerald-200 rounded-xl p-4">
        <CheckCircle2 size={20} className="text-emerald-600 shrink-0 mt-0.5" />
        <div>
          <div className="font-semibold text-emerald-800">Statistically significant result</div>
          <div className="text-sm text-emerald-700 mt-0.5">
            {winner} wins with p = {pVal.toFixed(4)} (α = 0.05).{' '}
            {liftPct != null && `${Math.abs(liftPct).toFixed(1)}% relative CTR lift.`}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
      <AlertCircle size={20} className="text-amber-600 shrink-0 mt-0.5" />
      <div>
        <div className="font-semibold text-amber-800">Not yet significant</div>
        <div className="text-sm text-amber-700 mt-0.5">
          p = {pVal.toFixed(4)} — collect more data before drawing conclusions.
        </div>
      </div>
    </div>
  );
}

function TestDetail({ test }) {
  const [results, setResults] = useState(null);
  const [overtime, setOvertime] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.getTestAnalysis(test.id), api.getMetricsOverTime(test.id)])
      .then(([r, ot]) => { setResults(r); setOvertime(ot); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [test.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-slate-400">
        <Loader2 size={20} className="animate-spin mr-2" /> Loading test data…
      </div>
    );
  }

  if (error) {
    return <div className="text-sm text-red-500 p-4">{error}</div>;
  }

  const vA = results?.variants?.A;
  const vB = results?.variants?.B;
  const lift = results?.lift;

  // Bar chart data
  const barData = [
    { name: 'CTR', A: vA ? +(vA.ctr * 100).toFixed(2) : 0, B: vB ? +(vB.ctr * 100).toFixed(2) : 0 },
    { name: 'Conversion', A: vA ? +(vA.conversion_rate * 100).toFixed(2) : 0, B: vB ? +(vB.conversion_rate * 100).toFixed(2) : 0 },
  ];

  // Line chart data
  const lineData = (overtime || []).map((d) => ({
    period: d.period,
    'Variant A': +(d.A.ctr * 100).toFixed(1),
    'Variant B': +(d.B.ctr * 100).toFixed(1),
  }));

  return (
    <div className="space-y-5">
      {/* Significance banner */}
      <SignificanceBanner testResult={results} />

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          label="Click-Through Rate"
          variantA={vA?.ctr}
          variantB={vB?.ctr}
          liftAbs={lift?.ctr_absolute}
          liftPct={lift?.ctr_relative_pct}
        />
        <MetricCard
          label="Conversion Rate"
          variantA={vA?.conversion_rate}
          variantB={vB?.conversion_rate}
          liftAbs={lift?.conversion_rate_absolute}
          liftPct={lift?.conversion_rate_relative_pct}
        />
      </div>

      {/* Event counts */}
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <div className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">Event Counts</div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          {['Impressions', 'Clicks', 'Purchases'].map((label, i) => {
            const keys = ['impressions', 'clicks', 'users_converted'];
            const k = keys[i];
            return (
              <div key={label}>
                <div className="text-slate-500 text-xs mb-1">{label}</div>
                <div className="flex gap-3">
                  <span className="font-mono text-indigo-700 font-semibold">{vA?.[k] ?? '—'}</span>
                  <span className="text-slate-400">vs</span>
                  <span className="font-mono text-violet-700 font-semibold">{vB?.[k] ?? '—'}</span>
                </div>
              </div>
            );
          })}
          <div>
            <div className="text-slate-500 text-xs mb-1">Avg. Engagement</div>
            <div className="flex gap-3">
              <span className="font-mono text-indigo-700 font-semibold">{vA?.avg_engagement_time_s ?? '—'}s</span>
              <span className="text-slate-400">vs</span>
              <span className="font-mono text-violet-700 font-semibold">{vB?.avg_engagement_time_s ?? '—'}s</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bar chart */}
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <div className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-4">
          Metric Comparison (%)
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={barData} barCategoryGap="30%" barGap={4}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
            <Tooltip formatter={(v) => `${v}%`} />
            <Legend />
            <Bar dataKey="A" name="Variant A (CF)" fill="#6366f1" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="B" name="Variant B (Content)" fill="#8b5cf6" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Line chart */}
      {lineData.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={15} className="text-slate-500" />
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">CTR Over Time (%)</div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={lineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="period" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <Legend />
              <Line type="monotone" dataKey="Variant A" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              <Line type="monotone" dataKey="Variant B" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* p-value detail */}
      {results?.statistical_tests && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">Statistical Tests</div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {Object.entries(results.statistical_tests).map(([metric, t]) => (
              <div key={metric} className="space-y-1">
                <div className="font-medium text-slate-700 capitalize">{metric.replace(/_/g, ' ')}</div>
                {Object.entries(t || {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs text-slate-500">
                    <span className="font-mono text-slate-400">{k}</span>
                    <span className="font-mono text-slate-700">{typeof v === 'number' ? v.toFixed(4) : String(v)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ABTestsPage() {
  const [tests, setTests] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [backendError, setBackendError] = useState(false);

  async function loadTests() {
    try {
      const data = await api.listABTests();
      setTests(data);
      if (data.length > 0 && !selected) setSelected(data[0]);
    } catch {
      setBackendError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTests(); }, []);

  async function createTest(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const test = await api.createABTest(newName.trim());
      setNewName('');
      setShowForm(false);
      await loadTests();
      setSelected(test);
    } catch (err) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  }

  if (backendError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
        <div className="text-red-600 font-semibold mb-2">Backend not reachable</div>
        <div className="text-sm text-red-500">
          Start the API: <code className="bg-red-100 px-1 rounded">uvicorn app:app --reload</code>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">A/B Tests</h1>
          <p className="text-slate-500 mt-1 text-sm">
            Compare recommendation strategies with statistical significance testing.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={15} /> New Test
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={createTest} className="bg-white border border-slate-200 rounded-xl p-5 flex gap-3 items-end">
          <div className="flex-1">
            <label className="text-xs font-medium text-slate-600 uppercase tracking-wide block mb-1.5">
              Test Name
            </label>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. homepage-recs-v3"
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
            <div className="text-xs text-slate-400 mt-1">control=v1 (CF), treatment=v2 (Content-Based)</div>
          </div>
          <button
            type="submit"
            disabled={creating}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {creating ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
            Create
          </button>
          <button
            type="button"
            onClick={() => setShowForm(false)}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-600"
          >
            <XCircle size={18} />
          </button>
        </form>
      )}

      {/* Main layout */}
      <div className="flex gap-5 items-start">
        {/* Test list */}
        <div className="w-64 shrink-0">
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 text-xs font-medium text-slate-500 uppercase tracking-wide">
              Active Tests ({tests.length})
            </div>
            {loading ? (
              <div className="p-4 text-slate-400 text-sm flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" /> Loading…
              </div>
            ) : tests.length === 0 ? (
              <div className="p-4 text-sm text-slate-400">
                No active tests. Create one to get started.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {tests.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setSelected(t)}
                    className={`w-full text-left px-4 py-3 transition-colors ${
                      selected?.id === t.id
                        ? 'bg-indigo-50 border-r-2 border-indigo-500'
                        : 'hover:bg-slate-50'
                    }`}
                  >
                    <div className="text-sm font-medium text-slate-800 truncate">{t.name}</div>
                    <div className="text-xs text-slate-400 mt-0.5 font-mono">
                      {t.control} vs {t.treatment}
                    </div>
                    <div className="text-xs text-slate-400">
                      {new Date(t.created_at).toLocaleDateString()}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1 min-w-0">
          {selected ? (
            <div>
              <div className="flex items-center gap-3 mb-5">
                <FlaskConical size={18} className="text-indigo-500" />
                <h2 className="text-lg font-bold text-slate-900">{selected.name}</h2>
                <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold px-2 py-0.5 rounded-full">
                  active
                </span>
              </div>
              <TestDetail key={selected.id} test={selected} />
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-400">
              Select a test from the left to view results.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
