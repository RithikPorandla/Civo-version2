import { useEffect, useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Overview from './routes/Overview';
import AddressLookup from './routes/AddressLookup';
import Municipalities from './routes/Municipalities';
import SiteSuitability from './routes/SiteSuitability';
import Report from './routes/Report';
import Portfolio from './routes/Portfolio';

const STORAGE_KEY = 'civo.sidebar.collapsed';

function Shell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  return (
    <div className="min-h-screen bg-bg text-text flex">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <TopBar />
        <main style={{ flex: 1 }}>{children}</main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/lookup" element={<AddressLookup />} />
        <Route path="/municipalities" element={<Municipalities />} />
        <Route path="/municipalities/:townId" element={<Municipalities />} />
        <Route path="/suitability" element={<SiteSuitability />} />
        <Route path="/report/:reportId" element={<Report />} />
        <Route path="/portfolio/:portfolioId" element={<Portfolio />} />
      </Routes>
    </Shell>
  );
}
