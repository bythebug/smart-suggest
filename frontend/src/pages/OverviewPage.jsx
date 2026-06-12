import { ArrowRight, BarChart2, Brain, FlaskConical, Layers, Zap } from 'lucide-react';

const TECH = [
  { label: 'FastAPI',      color: 'bg-teal-100 text-teal-800' },
  { label: 'SQLAlchemy',   color: 'bg-blue-100 text-blue-800' },
  { label: 'SQLite / PostgreSQL', color: 'bg-sky-100 text-sky-800' },
  { label: 'Redis',        color: 'bg-red-100 text-red-800' },
  { label: 'scikit-learn', color: 'bg-orange-100 text-orange-800' },
  { label: 'Docker',       color: 'bg-slate-100 text-slate-700' },
  { label: 'Python 3.12',  color: 'bg-yellow-100 text-yellow-800' },
];

const FEATURES = [
  {
    Icon: Brain,
    title: 'Two Recommendation Strategies',
    body: 'User-based Collaborative Filtering (v1) discovers items through shared taste, while Content-Based Filtering (v2) leverages TF-IDF item similarity. Both exposed through the same API so they\'re A/B-testable out of the box.',
    color: 'text-indigo-600',
    bg: 'bg-indigo-50',
  },
  {
    Icon: FlaskConical,
    title: 'Statistical A/B Testing',
    body: 'Deterministic MD5-hashed variant assignment keeps users in the same bucket across restarts. Impressions, clicks, and purchases feed into chi-square / z-tests with confidence intervals and Cohen\'s h effect sizes.',
    color: 'text-violet-600',
    bg: 'bg-violet-50',
  },
  {
    Icon: BarChart2,
    title: 'Real-Time KPI Tracking',
    body: 'CTR, conversion rate, and avg. engagement time computed per variant with absolute and relative lift. Time-series aggregation buckets events by day or hour for trend charts.',
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
  },
  {
    Icon: Zap,
    title: 'Caching Layer',
    body: 'Item-item similarity matrices are cached with a TTL (in-memory with a Redis-ready interface). User recommendation results invalidate on new interactions, keeping latency low without stale results.',
    color: 'text-amber-600',
    bg: 'bg-amber-50',
  },
];

const ARCH_NODES = [
  { label: 'FastAPI', sub: 'REST + OpenAPI', col: 'col-start-3', row: 'row-start-1' },
  { label: 'Recommenders', sub: 'CF · Content-Based', col: 'col-start-1', row: 'row-start-3' },
  { label: 'A/B Testing', sub: 'Assignment · Events', col: 'col-start-3', row: 'row-start-3' },
  { label: 'Tracking', sub: 'Interactions · Profiles', col: 'col-start-5', row: 'row-start-3' },
  { label: 'SQLite / Redis', sub: 'Storage · Cache', col: 'col-start-3', row: 'row-start-5' },
];

export default function OverviewPage() {
  return (
    <div className="space-y-12">
      {/* Hero */}
      <div className="rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-700 px-10 py-12 text-white">
        <h1 className="text-4xl font-bold mb-3">SmartSuggest</h1>
        <p className="text-indigo-100 text-lg max-w-2xl mb-6">
          A production-grade recommendation engine with built-in A/B testing infrastructure,
          statistical significance testing, and KPI tracking — built from scratch in Python.
        </p>
        <div className="flex flex-wrap gap-2">
          {TECH.map(({ label, color }) => (
            <span key={label} className={`${color} px-3 py-1 rounded-full text-xs font-semibold`}>
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Architecture */}
      <section>
        <h2 className="text-xl font-bold text-slate-900 mb-6">System Architecture</h2>
        <div className="bg-white border border-slate-200 rounded-xl p-8">
          {/* Flow diagram */}
          <div className="flex flex-col items-center gap-0">
            {/* Row 1: Client */}
            <div className="flex items-center gap-4">
              <div className="bg-slate-100 border border-slate-300 rounded-lg px-5 py-3 text-center">
                <div className="text-sm font-semibold text-slate-700">Client</div>
                <div className="text-xs text-slate-500">Browser / CLI</div>
              </div>
            </div>
            <div className="flex flex-col items-center text-slate-400 my-1">
              <div className="w-px h-4 bg-slate-300" />
              <ArrowRight size={14} className="rotate-90" />
            </div>

            {/* Row 2: FastAPI */}
            <div className="bg-indigo-50 border-2 border-indigo-300 rounded-lg px-8 py-3 text-center">
              <div className="text-sm font-bold text-indigo-700">FastAPI</div>
              <div className="text-xs text-indigo-500">REST API · Pydantic · Uvicorn</div>
            </div>
            <div className="flex flex-col items-center text-slate-400 my-1">
              <div className="w-px h-4 bg-slate-300" />
              <ArrowRight size={14} className="rotate-90" />
            </div>

            {/* Row 3: three modules side by side */}
            <div className="flex gap-4 items-stretch">
              <div className="bg-violet-50 border border-violet-200 rounded-lg px-5 py-3 text-center">
                <div className="text-sm font-semibold text-violet-700">Recommenders</div>
                <div className="text-xs text-violet-500 mt-0.5">CF · Content-Based</div>
                <div className="text-xs text-violet-500">Cosine Similarity</div>
              </div>
              <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg px-5 py-3 text-center">
                <div className="text-sm font-semibold text-fuchsia-700">A/B Testing</div>
                <div className="text-xs text-fuchsia-500 mt-0.5">MD5 Assignment</div>
                <div className="text-xs text-fuchsia-500">Event Logger</div>
              </div>
              <div className="bg-teal-50 border border-teal-200 rounded-lg px-5 py-3 text-center">
                <div className="text-sm font-semibold text-teal-700">Tracking</div>
                <div className="text-xs text-teal-500 mt-0.5">Interactions</div>
                <div className="text-xs text-teal-500">User Profiles</div>
              </div>
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-5 py-3 text-center">
                <div className="text-sm font-semibold text-emerald-700">Analytics</div>
                <div className="text-xs text-emerald-500 mt-0.5">CTR · Conversion</div>
                <div className="text-xs text-emerald-500">p-values · CIs</div>
              </div>
            </div>
            <div className="flex flex-col items-center text-slate-400 my-1">
              <div className="w-px h-4 bg-slate-300" />
              <ArrowRight size={14} className="rotate-90" />
            </div>

            {/* Row 4: Storage */}
            <div className="flex gap-4">
              <div className="bg-slate-100 border border-slate-300 rounded-lg px-6 py-3 text-center">
                <div className="text-sm font-semibold text-slate-700">SQLite / PostgreSQL</div>
                <div className="text-xs text-slate-500">SQLAlchemy ORM</div>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-lg px-6 py-3 text-center">
                <div className="text-sm font-semibold text-red-600">Redis</div>
                <div className="text-xs text-red-400">TTL Cache</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* A/B workflow */}
      <section>
        <h2 className="text-xl font-bold text-slate-900 mb-6">A/B Testing Workflow</h2>
        <div className="bg-white border border-slate-200 rounded-xl p-8">
          <div className="flex items-start gap-0 overflow-x-auto">
            {[
              { step: '1', title: 'Create Test', desc: 'POST /ab_tests\ncontrol=v1, treatment=v2' },
              { step: '2', title: 'Assign Variant', desc: 'MD5 hash of user_id + test_id → deterministic A/B split' },
              { step: '3', title: 'Serve Recs', desc: 'Call /recommendations/v1 or /v2 based on variant' },
              { step: '4', title: 'Log Events', desc: 'POST /interactions → impression, click, purchase' },
              { step: '5', title: 'Measure', desc: 'GET /results → CTR, conversion rate, avg. engagement' },
              { step: '6', title: 'Analyse', desc: 'GET /analysis → p-value, CI, Cohen\'s h, verdict' },
            ].map(({ step, title, desc }, i, arr) => (
              <div key={step} className="flex items-center">
                <div className="flex flex-col items-center min-w-[130px]">
                  <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-bold mb-2">
                    {step}
                  </div>
                  <div className="text-sm font-semibold text-slate-800 mb-1 text-center">{title}</div>
                  <div className="text-xs text-slate-500 text-center whitespace-pre-line">{desc}</div>
                </div>
                {i < arr.length - 1 && (
                  <ArrowRight size={18} className="text-slate-300 mx-2 flex-shrink-0 mt-[-24px]" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <section>
        <h2 className="text-xl font-bold text-slate-900 mb-6">Key Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FEATURES.map(({ Icon, title, body, color, bg }) => (
            <div key={title} className="bg-white border border-slate-200 rounded-xl p-6">
              <div className={`${bg} w-10 h-10 rounded-lg flex items-center justify-center mb-4`}>
                <Icon size={20} className={color} />
              </div>
              <h3 className="font-semibold text-slate-900 mb-2">{title}</h3>
              <p className="text-sm text-slate-600 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Layers card */}
      <section>
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Layers size={18} className="text-slate-500" />
            <h2 className="font-semibold text-slate-900">Tech Stack</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {[
              ['API', 'FastAPI + Uvicorn'],
              ['ORM', 'SQLAlchemy 2.0'],
              ['Database', 'SQLite → PostgreSQL'],
              ['Cache', 'In-memory TTL (Redis-ready)'],
              ['Stats', 'Pure Python — no scipy required'],
              ['ML', 'TF-IDF, cosine similarity'],
              ['Testing', 'pytest + httpx'],
              ['Deploy', 'Docker + AWS ECS Fargate'],
            ].map(([label, value]) => (
              <div key={label}>
                <div className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</div>
                <div className="text-slate-700 font-medium">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
