import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Route, Routes } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Overview from './routes/Overview';
import AddressLookup from './routes/AddressLookup';
import Municipalities from './routes/Municipalities';
import SiteSuitability from './routes/SiteSuitability';
import Report from './routes/Report';
import Portfolio from './routes/Portfolio';
function Shell({ children }) {
    return (_jsxs("div", { className: "min-h-screen bg-bg text-text flex", children: [_jsx(Sidebar, {}), _jsx("main", { className: "flex-1 min-w-0", children: children })] }));
}
export default function App() {
    return (_jsx(Shell, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(Overview, {}) }), _jsx(Route, { path: "/lookup", element: _jsx(AddressLookup, {}) }), _jsx(Route, { path: "/municipalities", element: _jsx(Municipalities, {}) }), _jsx(Route, { path: "/municipalities/:townId", element: _jsx(Municipalities, {}) }), _jsx(Route, { path: "/suitability", element: _jsx(SiteSuitability, {}) }), _jsx(Route, { path: "/report/:reportId", element: _jsx(Report, {}) }), _jsx(Route, { path: "/portfolio/:portfolioId", element: _jsx(Portfolio, {}) })] }) }));
}
