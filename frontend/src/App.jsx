import { useState } from 'react';
import OverviewPage from './pages/OverviewPage.jsx';
import RecommendationsPage from './pages/RecommendationsPage.jsx';
import ABTestsPage from './pages/ABTestsPage.jsx';

const TABS = [
  { id: 'recommendations', label: 'Recommendations' },
  { id: 'abtests',         label: 'A/B Tests' },
  { id: 'overview',        label: 'Overview' },
];

export default function App() {
  const [tab, setTab] = useState('recommendations');

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <nav className="bg-zinc-950 border-b border-zinc-800 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 flex items-center gap-8 h-12">
          <span className="text-white font-semibold text-sm tracking-tight select-none">
            SmartSuggest
          </span>
          <div className="flex items-center gap-0.5">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`px-3 py-1.5 rounded text-sm transition-colors font-medium ${
                  tab === id
                    ? 'bg-zinc-800 text-white'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-10">
        {tab === 'overview'        && <OverviewPage />}
        {tab === 'recommendations' && <RecommendationsPage />}
        {tab === 'abtests'         && <ABTestsPage />}
      </main>
    </div>
  );
}
