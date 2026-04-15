import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
const C = {
    border: '#ececec',
    accent: '#8b7355',
    textMid: '#6b6b6b',
    textDim: '#9b9b9b',
};
const DISPLAY = "'Fraunces', Georgia, serif";
export default function Overview() {
    const { data: munis } = useQuery({
        queryKey: ['municipalities'],
        queryFn: () => api.listMunicipalities(),
    });
    const { data: health } = useQuery({
        queryKey: ['health'],
        queryFn: () => api.health(),
    });
    const projectTypes = [
        { code: 'solar_ground_mount', label: 'Solar PV (Ground-Mount)' },
        { code: 'bess', label: 'Battery Energy Storage' },
        { code: 'substation', label: 'Substation' },
        { code: 'wind', label: 'Wind Turbine' },
        { code: 'transmission', label: 'Transmission' },
    ];
    return (_jsxs("div", { className: "px-12 py-12 max-w-6xl", children: [_jsx("div", { className: "eyebrow mb-3", children: "Overview" }), _jsxs("h1", { style: {
                    fontFamily: DISPLAY,
                    fontSize: 54,
                    letterSpacing: -1.5,
                    lineHeight: 1.05,
                    fontWeight: 400,
                }, children: ["Massachusetts permitting,", _jsx("br", {}), "triaged in seconds."] }), _jsx("p", { className: "text-textMid mt-6 max-w-2xl", children: "Civo scores energy-infrastructure sites against 225 CMR 29.00 and cross-references every Massachusetts municipality's zoning, wetland, and conservation bylaws. Every number traces back to a cited source row." }), _jsxs("div", { className: "mt-12 grid grid-cols-4 gap-6", children: [_jsx(Stat, { label: "Parcels indexed", value: health?.parcels_loaded?.toLocaleString() || '—' }), _jsx(Stat, { label: "ESMP projects", value: String(health?.esmp_projects_loaded || '—') }), _jsx(Stat, { label: "Towns covered", value: String(munis?.length || '—') }), _jsx(Stat, { label: "Project types", value: "5" })] }), _jsxs("section", { className: "mt-16", children: [_jsx("div", { className: "eyebrow mb-4", children: "Covered municipalities" }), _jsx("div", { className: "grid grid-cols-2 gap-4", children: (munis || []).map((m) => (_jsxs(Link, { to: `/municipalities/${m.town_id}`, className: "border hairline rounded-md bg-surface px-6 py-5 hover:border-borderHover transition", children: [_jsx("div", { style: { fontFamily: DISPLAY, fontSize: 22 }, className: "mb-1", children: m.town_name }), _jsxs("div", { className: "text-[12px] text-textDim", children: [m.project_types.length, " project types \u00B7 refreshed", ' ', m.last_refreshed_at ? new Date(m.last_refreshed_at).toLocaleDateString() : '—'] })] }, m.town_id))) })] }), _jsxs("section", { className: "mt-16", children: [_jsx("div", { className: "eyebrow mb-4", children: "Supported project types" }), _jsx("div", { className: "grid grid-cols-5 gap-3", children: projectTypes.map((p) => (_jsx("div", { className: "border hairline rounded-md bg-surface px-4 py-4 text-[13px]", style: { color: C.textMid }, children: p.label }, p.code))) })] }), _jsxs("section", { className: "mt-16 pb-16", children: [_jsx("div", { className: "eyebrow mb-4", children: "Start here" }), _jsx(Link, { to: "/lookup", className: "btn-pill btn-pill-primary inline-flex", children: "Score an address \u2192" })] })] }));
}
function Stat({ label, value }) {
    return (_jsxs("div", { className: "border hairline rounded-md bg-surface px-6 py-6", children: [_jsx("div", { className: "eyebrow mb-2", style: { fontSize: 11 }, children: label }), _jsx("div", { style: { fontFamily: DISPLAY, fontSize: 34, letterSpacing: '-0.02em' }, children: value })] }));
}
