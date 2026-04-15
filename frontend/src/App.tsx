import { Link, Route, Routes } from 'react-router-dom';
import Landing from './routes/Landing';
import Report from './routes/Report';
import Portfolio from './routes/Portfolio';

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b hairline">
        <div className="max-w-6xl mx-auto px-8 py-6 flex items-center justify-between">
          <Link to="/" className="display text-[22px] tracking-tight">
            Civo<span className="text-accent italic">.</span>
          </Link>
          <div className="flex items-center gap-6 text-sm text-textMid">
            <span className="eyebrow">Massachusetts Permitting Intelligence</span>
          </div>
        </div>
      </header>
      <main>{children}</main>
      <footer className="border-t hairline mt-rhythm-lg">
        <div className="max-w-6xl mx-auto px-8 py-6 flex items-center justify-between text-xs text-textDim">
          <span>Civo · v0.1 · MA EEA 225 CMR 29.00</span>
          <span>Sources: MassGIS · MassDEP · Eversource ESMP · OEJE · USDA NRCS</span>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/report/:reportId" element={<Report />} />
        <Route path="/portfolio/:portfolioId" element={<Portfolio />} />
      </Routes>
    </Shell>
  );
}
