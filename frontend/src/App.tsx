import { Route, Routes } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Overview from './routes/Overview';
import AddressLookup from './routes/AddressLookup';
import Municipalities from './routes/Municipalities';
import SiteSuitability from './routes/SiteSuitability';
import Report from './routes/Report';
import Portfolio from './routes/Portfolio';

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg text-text flex">
      <Sidebar />
      <main className="flex-1 min-w-0">{children}</main>
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
