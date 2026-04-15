import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink } from 'react-router-dom';
const items = [
    { to: '/', label: 'Overview', eyebrow: '01' },
    { to: '/lookup', label: 'Address Lookup', eyebrow: '02' },
    { to: '/municipalities', label: 'Municipalities', eyebrow: '03' },
    { to: '/suitability', label: 'Site Suitability', eyebrow: '04' },
];
export default function Sidebar() {
    return (_jsxs("aside", { className: "border-r hairline bg-surface", style: { width: 260, minHeight: '100vh', position: 'sticky', top: 0 }, children: [_jsxs("div", { className: "px-6 pt-8 pb-10", children: [_jsxs("div", { className: "display text-[24px] tracking-tight", children: ["Civo", _jsx("span", { className: "text-accent italic", children: "." })] }), _jsx("div", { className: "eyebrow mt-2", style: { fontSize: 11 }, children: "MA Permitting Intelligence" })] }), _jsx("nav", { className: "px-3 flex flex-col gap-1", children: items.map((i) => (_jsx(NavLink, { to: i.to, end: i.to === '/', className: ({ isActive }) => [
                        'block px-3 py-3 rounded-sm transition-colors',
                        isActive
                            ? 'bg-accentSoft text-text'
                            : 'text-textMid hover:text-text hover:bg-accentSoft/60',
                    ].join(' '), children: _jsxs("div", { className: "flex items-baseline gap-3", children: [_jsx("span", { className: "display italic text-textDim", style: { fontSize: 13, width: 22 }, children: i.eyebrow }), _jsx("span", { className: "display", style: { fontSize: 17, letterSpacing: '-0.01em' }, children: i.label })] }) }, i.to))) }), _jsxs("div", { className: "px-6 absolute bottom-6 text-[11px] text-textDim", style: { width: 260 }, children: [_jsx("div", { className: "eyebrow mb-2", style: { fontSize: 10 }, children: "Methodology" }), _jsx("div", { children: "225 CMR 29.00 \u00B7 v1" }), _jsx("div", { children: "MassGIS \u00B7 Eversource ESMP" })] })] }));
}
