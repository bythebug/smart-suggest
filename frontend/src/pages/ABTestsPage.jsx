import { useEffect, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { CheckCircle2, AlertTriangle, CheckCircle, FlaskConical, Loader2, Plus, Shuffle, X } from 'lucide-react';
import { api } from '../api.js';

function pct(n)  { return n != null ? `${(n * 100).toFixed(1)}%` : 'N/A'; }

function StatCard({ label, valueA, valueB, liftPct, format = pct }) {
  const positive = liftPct > 0;
  const winner = liftPct >= 0 ? 'B' : 'A';
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6">
      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">{label}</div>
      <div className="flex gap-6 mb-3">
        <div>
          <div className="text-3xl font-bold text-gray-900 font-mono">{format(valueA)}</div>
          <div className="text-xs text-gray-400 mt-1 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-600 inline-block" /> Variant A
          </div>
        </div>
        <div className="w-px bg-gray-100" />
        <div>
          <div className={`text-3xl font-bold font-mono ${winner === 'B' ? 'text-violet-600' : 'text-gray-900'}`}>
            {format(valueB)}
          </div>
          <div className="text-xs text-gray-400 mt-1 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-violet-600 inline-block" /> Variant B
          </div>
        </div>
      </div>
      {liftPct != null && (
        <div className={`text-xs font-semibold font-mono ${positive ? 'text-emerald-600' : 'text-red-500'}`}>
          {positive ? '↑' : '↓'} {Math.abs(liftPct).toFixed(1)}% relative lift
        </div>
      )}
    </div>
  );
}

function Verdict({ result }) {
  if (!result?.statistical_tests) return null;
  const t = result.statistical_tests.ctr;
  const pVal = t?.p_value ?? t?.pvalue;
  if (pVal == null) return null;
  const sig = pVal < 0.05;
  const liftPct = result.lift?.ctr_relative_pct;
  const winner = (result.lift?.ctr_absolute ?? 0) >= 0 ? 'Variant B' : 'Variant A';

  if (sig) return (
    <div className="flex items-start gap-3 bg-emerald-50 border border-emerald-200 rounded-xl p-4">
      <CheckCircle2 size={18} className="text-emerald-600 shrink-0 mt-0.5" />
      <div>
        <div className="font-semibold text-emerald-900 text-sm">{winner} wins, statistically significant</div>
        <div className="text-xs text-emerald-700 mt-0.5 font-mono">
          p = {pVal.toFixed(4)} · α = 0.05
          {liftPct != null && ` · ${Math.abs(liftPct).toFixed(1)}% CTR lift`}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
      <AlertTriangle size={18} className="text-amber-600 shrink-0 mt-0.5" />
      <div>
        <div className="font-semibold text-amber-900 text-sm">Not yet significant</div>
        <div className="text-xs text-amber-700 mt-0.5 font-mono">p = {pVal.toFixed(4)}, collect more data before drawing conclusions</div>
      </div>
    </div>
  );
}

function TestDetail({ test }) {
  const [result, setResult]         = useState(null);
  const [overtime, setOT]           = useState(null);
  const [loading, setLoading]       = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [error, setError]           = useState(null);

  // custom event logger state
  const [users, setUsers]           = useState([]);
  const [items, setItems]           = useState([]);
  const [selUser, setSelUser]       = useState('');
  const [selItem, setSelItem]       = useState('');
  const [lastLog, setLastLog]       = useState(null); // { variant, event }
  const [logging, setLogging]       = useState(null); // event type being logged

  async function load() {
    setLoading(true); setError(null);
    try {
      const [r, ot] = await Promise.all([api.getTestAnalysis(test.id), api.getMetricsOverTime(test.id)]);
      setResult(r); setOT(ot);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    load();
    Promise.all([api.getUsers(), api.getItems()]).then(([u, i]) => {
      setUsers(u.slice(0, 10));
      setItems(i);
      if (u.length) setSelUser(u[0].id);
      if (i.length) setSelItem(i[0].id);
    });
  }, [test.id]);

  async function logEvent(eventType) {
    if (!selUser || !selItem) return;
    setLogging(eventType);
    try {
      const res = await api.logTestEvent(test.id, selUser, selItem, eventType);
      setLastLog({ variant: res.variant, event: eventType, user: users.find(u => u.id === selUser)?.username });
      await load();
    } catch (e) { alert(e.message); }
    finally { setLogging(null); }
  }

  async function simulate() {
    setSimulating(true);
    try {
      await api.simulateTestData(test.id);
      await load();
    } catch (e) { alert(e.message); }
    finally { setSimulating(false); }
  }

  if (loading) return (
    <div className="flex items-center gap-2 text-gray-400 py-16 justify-center">
      <Loader2 size={18} className="animate-spin" /> Loading…
    </div>
  );
  if (error) return <div className="text-sm text-red-500 py-8">{error}</div>;

  const vA = result?.variants?.A;
  const vB = result?.variants?.B;
  const lift = result?.lift;
  const hasData = (vA?.impressions ?? 0) > 0;

  const barData = [
    { name: 'CTR',        A: vA ? +(vA.ctr * 100).toFixed(1) : 0, B: vB ? +(vB.ctr * 100).toFixed(1) : 0 },
    { name: 'Conversion', A: vA ? +(vA.conversion_rate * 100).toFixed(1) : 0, B: vB ? +(vB.conversion_rate * 100).toFixed(1) : 0 },
  ];

  const lineData = (overtime || []).map((d) => ({
    period: d.period.slice(5),
    A: +(d.A.ctr * 100).toFixed(1),
    B: +(d.B.ctr * 100).toFixed(1),
  }));

  return (
    <div className="space-y-4">
      {!hasData && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
          <p className="text-sm font-semibold text-gray-700 mb-1">No event data yet</p>
          <p className="text-sm text-gray-400 mb-5">
            This test has no impressions logged. Simulate a realistic dataset to see metrics, charts, and significance results.
          </p>
          <button
            onClick={simulate}
            disabled={simulating}
            className="inline-flex items-center gap-2 bg-gray-900 hover:bg-gray-700 disabled:opacity-40 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {simulating ? <Loader2 size={14} className="animate-spin" /> : <Shuffle size={14} />}
            {simulating ? 'Simulating…' : 'Simulate data'}
          </button>
          <p className="text-xs text-gray-400 mt-3">
            Assigns 50 users to variants and logs impressions, clicks, and purchases with realistic CTR differences.
          </p>
        </div>
      )}
      <Verdict result={result} />

      <div className="grid grid-cols-2 gap-4">
        <StatCard
          label="Click-Through Rate"
          valueA={vA?.ctr}
          valueB={vB?.ctr}
          liftPct={lift?.ctr_relative_pct}
        />
        <StatCard
          label="Conversion Rate"
          valueA={vA?.conversion_rate}
          valueB={vB?.conversion_rate}
          liftPct={lift?.conversion_rate_relative_pct}
        />
      </div>

      {/* Event counts */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Event Counts</div>
        <div className="grid grid-cols-4 gap-6">
          {[
            ['Impressions', vA?.impressions,           vB?.impressions],
            ['Clicks',      vA?.clicks,                vB?.clicks],
            ['Purchases',   vA?.users_converted,       vB?.users_converted],
            ['Avg. Engage', `${vA?.avg_engagement_time_s ?? 'N/A'}s`, `${vB?.avg_engagement_time_s ?? 'N/A'}s`],
          ].map(([label, a, b]) => (
            <div key={label}>
              <div className="text-xs text-gray-400 mb-2">{label}</div>
              <div className="flex items-baseline gap-2">
                <span className="font-mono font-semibold text-blue-600">{a ?? 'N/A'}</span>
                <span className="text-xs text-gray-300">vs</span>
                <span className="font-mono font-semibold text-violet-600">{b ?? 'N/A'}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bar chart */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Metric Comparison
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={barData} barGap={4} barCategoryGap="30%">
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} unit="%" domain={[0, 100]} axisLine={false} tickLine={false} />
            <Tooltip formatter={(v) => `${v}%`} contentStyle={{ border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="A" name="Variant A" fill="#2563eb" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="B" name="Variant B" fill="#7c3aed" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Line chart */}
      {lineData.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
            CTR Over Time
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={lineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="period" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} unit="%" axisLine={false} tickLine={false} />
              <Tooltip formatter={(v) => `${v}%`} contentStyle={{ border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
              <Line dataKey="A" name="Variant A" stroke="#2563eb" strokeWidth={2} dot={{ r: 3, fill: '#2563eb' }} isAnimationActive={false} />
              <Line dataKey="B" name="Variant B" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3, fill: '#7c3aed' }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Custom event logger */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Log Custom Event</div>
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">User</label>
            <select
              value={selUser}
              onChange={e => setSelUser(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {users.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Item</label>
            <select
              value={selItem}
              onChange={e => setSelItem(Number(e.target.value))}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {items.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
            </select>
          </div>
          <div className="flex gap-2">
            {['impression', 'click', 'purchase'].map(ev => (
              <button
                key={ev}
                onClick={() => logEvent(ev)}
                disabled={!!logging}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40 transition-colors capitalize"
              >
                {logging === ev ? <Loader2 size={13} className="animate-spin" /> : null}
                {ev}
              </button>
            ))}
          </div>
        </div>
        {lastLog && (
          <div className="mt-3 flex items-center gap-2 text-xs text-emerald-700">
            <CheckCircle size={13} />
            <span>
              <span className="font-semibold">{lastLog.user}</span> logged as{' '}
              <span className={`font-semibold ${lastLog.variant === 'A' ? 'text-blue-600' : 'text-violet-600'}`}>
                Variant {lastLog.variant}
              </span>
              {' '}· {lastLog.event} recorded · metrics refreshed
            </span>
          </div>
        )}
        <p className="text-xs text-gray-400 mt-3">
          The variant is assigned deterministically by user ID — the same user always lands in the same bucket.
        </p>
      </div>

      {/* Statistical tests */}
      {result?.statistical_tests && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Statistical Tests</div>
          <div className="grid grid-cols-2 gap-8">
            {Object.entries(result.statistical_tests).map(([metric, t]) => (
              <div key={metric}>
                <div className="text-sm font-semibold text-gray-700 mb-3 capitalize">{metric.replace(/_/g, ' ')}</div>
                <div className="space-y-1.5">
                  {Object.entries(t || {}).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-xs text-gray-400 font-mono">{k}</span>
                      <span className="text-xs text-gray-700 font-mono font-medium">
                        {typeof v === 'number' ? v.toFixed(4) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ABTestsPage({ dataVersion }) {
  const [tests, setTests]     = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [offline, setOffline] = useState(false);

  async function loadTests() {
    try {
      const data = await api.listABTests();
      setTests(data);
      if (data.length > 0 && !selected) setSelected(data[0]);
    } catch { setOffline(true); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadTests(); }, [dataVersion]);

  async function createTest(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const test = await api.createABTest(newName.trim());
      setNewName(''); setShowForm(false);
      await loadTests();
      setSelected(test);
    } catch (err) { alert(err.message); }
    finally { setCreating(false); }
  }

  if (offline) return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
      <div className="font-semibold text-red-700 mb-1">Backend not reachable</div>
      <div className="text-sm text-red-500 font-mono">uvicorn app:app --reload</div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">A/B Tests</h1>
          <p className="text-gray-500 text-sm mt-1">Compare recommendation strategies with statistical significance testing.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-gray-900 hover:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={14} /> New Test
        </button>
      </div>

      {showForm && (
        <form onSubmit={createTest} className="bg-white border border-gray-200 rounded-xl px-6 py-5 flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Test Name</label>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. homepage-v3"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-400 mt-1.5 font-mono">control=v1 (CF) · treatment=v2 (content-based)</p>
          </div>
          <button type="submit" disabled={creating}
            className="flex items-center gap-2 bg-gray-900 hover:bg-gray-700 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium">
            {creating ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />} Create
          </button>
          <button type="button" onClick={() => setShowForm(false)} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
            <X size={16} />
          </button>
        </form>
      )}

      <div className="flex gap-5 items-start">
        {/* Sidebar */}
        <div className="w-60 shrink-0">
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Active Tests {tests.length > 0 && `(${tests.length})`}
              </span>
            </div>
            {loading ? (
              <div className="flex items-center gap-2 text-gray-400 text-sm px-4 py-4">
                <Loader2 size={14} className="animate-spin" /> Loading…
              </div>
            ) : tests.length === 0 ? (
              <div className="px-4 py-4 text-sm text-gray-400">No active tests yet.</div>
            ) : (
              <div className="divide-y divide-gray-100">
                {tests.map((t) => (
                  <button key={t.id} onClick={() => setSelected(t)}
                    className={`w-full text-left px-4 py-3 transition-colors ${
                      selected?.id === t.id
                        ? 'bg-blue-50 border-r-2 border-r-blue-600'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 truncate">{t.name}</span>
                      {t.id === 1 && (
                        <span className="text-xs text-gray-400 bg-gray-100 border border-gray-200 px-1.5 py-0.5 rounded shrink-0">
                          sample
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 font-mono mt-0.5">{t.control} vs {t.treatment}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Detail */}
        <div className="flex-1 min-w-0">
          {selected ? (
            <>
              <div className="flex items-center gap-3 mb-5">
                <FlaskConical size={16} className="text-gray-400" />
                <h2 className="text-base font-semibold text-gray-900">{selected.name}</h2>
                <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                  active
                </span>
              </div>
              {selected.id === 1 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2.5 text-xs text-amber-700 mb-5">
                  This test is pre-loaded with simulated data so you can explore the dashboard. Create a new test and use <span className="font-semibold">Simulate data</span> or <span className="font-semibold">Log Custom Event</span> to add your own.
                </div>
              )}
              <TestDetail key={selected.id} test={selected} />
            </>
          ) : (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400 text-sm">
              Select a test to view results.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
