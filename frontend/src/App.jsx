import { useState } from 'react';
import { Cpu, FlaskConical, LayoutDashboard } from 'lucide-react';
import OverviewPage from './pages/OverviewPage.jsx';
import RecommendationsPage from './pages/RecommendationsPage.jsx';
import ABTestsPage from './pages/ABTestsPage.jsx';

const TABS = [
  { id: 'overview',        label: 'Overview',        Icon: LayoutDashboard },
  { id: 'recommendations', label: 'Recommendations',  Icon: Cpu },
  { id: 'abtests',         label: 'A/B Tests',        Icon: FlaskConical },
];

export default function App() {
  const [tab, setTab] = useState('overview');

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Nav */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 flex items-center gap-8 h-14">
          <span className="font-bold text-lg text-indigo-600 tracking-tight select-none">
            SmartSuggest
          </span>
          <div className="flex gap-1">
            {TABS.map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  tab === id
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {tab === 'overview'        && <OverviewPage />}
        {tab === 'recommendations' && <RecommendationsPage />}
        {tab === 'abtests'         && <ABTestsPage />}
      </main>
    </div>
  );
}
