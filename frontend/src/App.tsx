import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Overview from './routes/Overview';
import AddressLookup from './routes/AddressLookup';
import Municipalities from './routes/Municipalities';
import SiteSuitability from './routes/SiteSuitability';
import Discover from './routes/Discover';
import Report from './routes/Report';
import Portfolio from './routes/Portfolio';
import DataSources from './routes/DataSources';

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
    <Routes>
      <Route path="/" element={<Navigate to="/app/" replace />} />
      <Route
        path="/app/*"
        element={
          <Shell>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/lookup" element={<AddressLookup />} />
              <Route path="/suitability" element={<SiteSuitability />} />
              <Route path="/discover" element={<Discover />} />
              <Route path="/data-sources" element={<DataSources />} />
              <Route path="/portfolio" element={<Portfolio />} />
            </Routes>
          </Shell>
        }
      />
      <Route
        path="/municipalities/*"
        element={
          <Shell>
            <Routes>
              <Route path="/" element={<Municipalities />} />
              <Route path=":townId" element={<Municipalities />} />
            </Routes>
          </Shell>
        }
      />
      <Route
        path="/report/:reportId"
        element={
          <Shell>
            <Report />
          </Shell>
        }
      />
      <Route path="/portfolio/:portfolioId" element={<Navigate to="/app/portfolio" replace />} />
    </Routes>
  );
}
