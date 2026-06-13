import { useState } from 'react';
import { api } from '../api';

const TECH = ['FastAPI', 'SQLAlchemy', 'SQLite → PostgreSQL', 'Redis', 'scikit-learn', 'Docker', 'Python 3.12'];

const FEATURES = [
  {
    title: 'Two Recommendation Strategies',
    body: 'Collaborative Filtering (v1) builds a weighted user-item matrix and finds top-K cosine-similar neighbours. Content-Based (v2) runs TF-IDF on item descriptions and scores by item-item cosine similarity, cached with a 1-hour TTL.',
  },
  {
    title: 'Deterministic A/B Assignment',
    body: 'MD5-hash of (test_id, user_id) gives stable variant assignment across restarts and servers. Impressions, clicks, and purchases feed into z-tests with Wilson score confidence intervals.',
  },
  {
    title: 'Statistical Significance Testing',
    body: "Chi-square and two-proportion z-tests for CTR and conversion rate. Welch's t-test for engagement time. Cohen's h effect sizes classify results as negligible, small, medium, or large.",
  },
  {
    title: 'Redis-Ready Caching',
    body: 'Item-item similarity matrices are cached with a TTL interface that swaps between in-memory (dev) and Redis (prod) with zero code changes. User recommendation caches invalidate on new interactions.',
  },
];

const WORKFLOW = [
  { n: '1', title: 'Create test',     sub: 'POST /ab_tests' },
  { n: '2', title: 'Assign variant',  sub: 'MD5 hash' },
  { n: '3', title: 'Serve recs',      sub: '/v1 or /v2' },
  { n: '4', title: 'Log events',      sub: 'POST /interactions' },
  { n: '5', title: 'Measure',         sub: '/results' },
  { n: '6', title: 'Analyse',         sub: '/analysis' },
];


export default function OverviewPage({ onDataChange }) {
  const [seedStatus, setSeedStatus] = useState('idle');   // idle | loading | success | error
  const [clearStatus, setClearStatus] = useState('idle'); // idle | loading | success | error
  const [actionError, setActionError] = useState('');

  async function handleSeed() {
    setSeedStatus('loading');
    setClearStatus('idle');
    setActionError('');
    try {
      await api.seedData();
      setSeedStatus('success');
      onDataChange();
    } catch (e) {
      setSeedStatus('error');
      setActionError(e.message);
    }
  }

  async function handleClear() {
    setClearStatus('loading');
    setSeedStatus('idle');
    setActionError('');
    try {
      await api.clearData();
      setClearStatus('success');
      onDataChange();
    } catch (e) {
      setClearStatus('error');
      setActionError(e.message);
    }
  }

  return (
    <div className="space-y-10">

      {/* Hero */}
      <div className="rounded-xl bg-zinc-950 px-10 py-12">
        <div className="inline-flex items-center gap-2 text-xs text-zinc-400 border border-zinc-700 rounded-full px-3 py-1 mb-6">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
          v0.1.0 · open source · MIT
        </div>
        <h1 className="text-5xl font-bold text-white tracking-tight mb-4">
          SmartSuggest
        </h1>
        <p className="text-zinc-400 text-lg leading-relaxed max-w-2xl mb-8">
          Recommendation engine with built-in A/B testing, statistical significance
          testing, and KPI tracking. Written from scratch in Python.
        </p>
        <div className="flex flex-wrap gap-2">
          {TECH.map((t) => (
            <span key={t} className="text-xs font-medium text-zinc-300 bg-zinc-900 border border-zinc-700 px-3 py-1 rounded">
              {t}
            </span>
          ))}
        </div>

        <div className="mt-8 flex items-center gap-3">
          <button
            onClick={handleSeed}
            disabled={seedStatus === 'loading' || clearStatus === 'loading'}
            className="inline-flex items-center gap-2 text-sm font-medium bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed text-zinc-200 border border-zinc-600 px-4 py-2 rounded-lg transition-colors"
          >
            {seedStatus === 'loading' ? (
              <>
                <span className="w-3.5 h-3.5 rounded-full border-2 border-zinc-400 border-t-transparent animate-spin" />
                Loading…
              </>
            ) : (
              <>
                <span className="text-base">⚗</span>
                Load sample data
              </>
            )}
          </button>
          <button
            onClick={handleClear}
            disabled={seedStatus === 'loading' || clearStatus === 'loading'}
            className="inline-flex items-center gap-2 text-sm font-medium bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed text-zinc-400 border border-zinc-700 px-4 py-2 rounded-lg transition-colors"
          >
            {clearStatus === 'loading' ? (
              <>
                <span className="w-3.5 h-3.5 rounded-full border-2 border-zinc-600 border-t-transparent animate-spin" />
                Clearing…
              </>
            ) : (
              <>
                <span className="text-base">✕</span>
                Clear data
              </>
            )}
          </button>
          {seedStatus === 'success' && (
            <span className="text-sm text-emerald-400">
              Sample data loaded — 50 users, 20 items, 1 A/B test.
            </span>
          )}
          {clearStatus === 'success' && (
            <span className="text-sm text-zinc-400">All data cleared.</span>
          )}
          {(seedStatus === 'error' || clearStatus === 'error') && (
            <span className="text-sm text-red-400">{actionError}</span>
          )}
        </div>
      </div>

      {/* Architecture */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">
          System Architecture
        </h2>
        <div className="bg-white border border-gray-200 rounded-xl p-10">
          <div className="flex flex-col items-center gap-0">

            {/* Client */}
            <div className="border border-gray-300 rounded-lg px-6 py-2.5 text-center bg-gray-50">
              <div className="text-sm font-medium text-gray-700">Client</div>
              <div className="text-xs text-gray-400 font-mono">Browser / curl</div>
            </div>

            <div className="w-px h-6 bg-gray-200" />

            {/* FastAPI */}
            <div className="border-2 border-blue-600 rounded-lg px-12 py-3 text-center">
              <div className="text-sm font-semibold text-blue-700">FastAPI + Uvicorn</div>
              <div className="text-xs text-blue-500 font-mono mt-0.5">REST API · Pydantic validation · OpenAPI docs</div>
            </div>

            <div className="w-px h-6 bg-gray-200" />

            {/* Three modules */}
            <div className="flex gap-3">
              {[
                { name: 'Recommenders', sub: 'CF · Content-Based\nCosine similarity' },
                { name: 'A/B Testing',  sub: 'MD5 assignment\nEvent logging' },
                { name: 'Tracking',     sub: 'Interactions\nUser profiles' },
                { name: 'Analytics',    sub: 'CTR · Conversion\np-values · CIs' },
              ].map(({ name, sub }) => (
                <div key={name} className="border border-gray-200 rounded-lg px-5 py-3 text-center bg-gray-50 min-w-[130px]">
                  <div className="text-sm font-semibold text-gray-800">{name}</div>
                  <div className="text-xs text-gray-400 font-mono mt-1 whitespace-pre-line leading-4">{sub}</div>
                </div>
              ))}
            </div>

            <div className="w-px h-6 bg-gray-200" />

            {/* Storage */}
            <div className="flex gap-3">
              <div className="border border-gray-200 rounded-lg px-8 py-3 text-center bg-gray-50">
                <div className="text-sm font-semibold text-gray-800">SQLite / PostgreSQL</div>
                <div className="text-xs text-gray-400 font-mono mt-0.5">SQLAlchemy ORM</div>
              </div>
              <div className="border border-gray-200 rounded-lg px-8 py-3 text-center bg-gray-50">
                <div className="text-sm font-semibold text-gray-800">Redis</div>
                <div className="text-xs text-gray-400 font-mono mt-0.5">TTL cache</div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* A/B workflow */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">
          A/B Testing Workflow
        </h2>
        <div className="bg-white border border-gray-200 rounded-xl px-10 py-8">
          <div className="flex items-center">
            {WORKFLOW.map(({ n, title, sub }, i) => (
              <div key={n} className="flex items-center flex-1">
                <div className="flex flex-col items-center">
                  <div className="w-7 h-7 rounded-full border-2 border-blue-600 text-blue-600 text-xs font-bold flex items-center justify-center shrink-0">
                    {n}
                  </div>
                  <div className="text-xs font-semibold text-gray-800 mt-2 text-center">{title}</div>
                  <div className="text-xs text-gray-400 font-mono mt-0.5 text-center">{sub}</div>
                </div>
                {i < WORKFLOW.length - 1 && (
                  <div className="flex-1 h-px bg-gray-200 mx-2 mb-8" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <section>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">
          Key Features
        </h2>
        <div className="grid grid-cols-2 gap-4">
          {FEATURES.map(({ title, body }) => (
            <div key={title} className="bg-white border border-gray-200 rounded-xl p-6">
              <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>


    </div>
  );
}
