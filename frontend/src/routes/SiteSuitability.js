import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from 'react-router-dom';
const DISPLAY = "'Fraunces', Georgia, serif";
const EXAMPLES = [
    { id: 1, address: 'Kendall Square, Cambridge, MA', score: 92.5, bucket: 'SUITABLE' },
    { id: 2, address: '50 Nagog Park, Acton, MA', score: 64.1, bucket: 'CONDITIONALLY SUITABLE' },
    { id: 3, address: 'East Freetown, MA', score: 35.4, bucket: 'CONSTRAINED' },
];
export default function SiteSuitability() {
    return (_jsxs("div", { className: "px-12 py-12 max-w-6xl", children: [_jsx("div", { className: "eyebrow mb-3", children: "Site Suitability" }), _jsx("h1", { style: {
                    fontFamily: DISPLAY,
                    fontSize: 54,
                    letterSpacing: -1.5,
                    lineHeight: 1.05,
                    fontWeight: 400,
                }, children: "Your scored reports." }), _jsx("p", { className: "text-textMid mt-6 max-w-2xl mb-12", children: "Civo scores every MassGIS parcel against 225 CMR 29.00 \u2014 seven weighted criteria, every finding cited. Open an existing report or run a new one from Address Lookup." }), _jsx(Link, { to: "/lookup", className: "btn-pill btn-pill-primary inline-flex mb-10", children: "Run a new report \u2192" }), _jsx("div", { className: "eyebrow mb-4", children: "Reference parcels" }), _jsxs("div", { className: "border hairline rounded-md overflow-hidden bg-surface", children: [_jsxs("div", { className: "grid text-[12px] uppercase tracking-wider text-textDim px-6 py-3 border-b hairline", style: { gridTemplateColumns: '1fr 140px 200px 80px' }, children: [_jsx("div", { children: "Address" }), _jsx("div", { children: "Score" }), _jsx("div", { children: "Bucket" }), _jsx("div", {})] }), EXAMPLES.map((e) => (_jsxs("div", { className: "grid items-center px-6 py-4 border-b hairline last:border-b-0", style: { gridTemplateColumns: '1fr 140px 200px 80px' }, children: [_jsx("div", { style: { fontFamily: DISPLAY, fontSize: 17 }, children: e.address }), _jsx("div", { style: { fontFamily: DISPLAY, fontSize: 22 }, children: e.score }), _jsx("div", { className: "text-[12px] text-textMid", children: e.bucket }), _jsx("div", { className: "text-right", children: _jsx(Link, { to: `/report/${e.id}`, style: { color: '#8b7355', fontSize: 13 }, children: "Open \u2192" }) })] }, e.id)))] }), _jsx("div", { className: "text-[11px] text-textDim mt-3", children: "The reference rows assume report IDs 1-3 exist in your local database. Run a fresh score from Address Lookup to populate new ones." })] }));
}
