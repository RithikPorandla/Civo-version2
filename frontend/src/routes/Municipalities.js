import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../lib/api';
const DISPLAY = "'Fraunces', Georgia, serif";
const PROJECT_TYPES = [
    { code: 'solar_ground_mount', label: 'Solar PV (Ground)' },
    { code: 'bess', label: 'Battery Storage' },
    { code: 'substation', label: 'Substation' },
    { code: 'wind', label: 'Wind' },
    { code: 'transmission', label: 'Transmission' },
];
export default function MunicipalitiesRoute() {
    const { townId } = useParams();
    if (townId)
        return _jsx(MunicipalityDetail, { townId: Number(townId) });
    return _jsx(MunicipalityIndex, {});
}
function MunicipalityIndex() {
    const { data, isLoading } = useQuery({
        queryKey: ['municipalities'],
        queryFn: () => api.listMunicipalities(),
    });
    if (isLoading)
        return _jsx("div", { className: "px-12 py-12 text-textDim", children: "Loading\u2026" });
    return (_jsxs("div", { className: "px-12 py-12 max-w-6xl", children: [_jsx("div", { className: "eyebrow mb-3", children: "Municipalities" }), _jsx("h1", { style: {
                    fontFamily: DISPLAY,
                    fontSize: 54,
                    letterSpacing: -1.5,
                    lineHeight: 1.05,
                    fontWeight: 400,
                }, children: "Permitting by town." }), _jsx("p", { className: "text-textMid mt-6 max-w-2xl mb-12", children: "Zoning, wetlands, and conservation bylaws for every town where Eversource has a planned ESMP project. Each entry cites back to the town's own bylaw document." }), _jsx("div", { className: "grid grid-cols-2 gap-4", children: (data || []).map((m) => (_jsxs(Link, { to: `/municipalities/${m.town_id}`, className: "border hairline rounded-md bg-surface px-6 py-6 hover:border-borderHover transition", children: [_jsx("div", { style: { fontFamily: DISPLAY, fontSize: 26 }, className: "mb-2", children: m.town_name }), _jsx("div", { className: "flex gap-2 flex-wrap", children: m.project_types.map((pt) => (_jsx("span", { className: "chip", style: { fontSize: 11, padding: '2px 10px' }, children: pt.replace(/_/g, ' ') }, pt))) })] }, m.town_id))) })] }));
}
function MunicipalityDetail({ townId }) {
    const { data, isLoading } = useQuery({
        queryKey: ['municipality', townId],
        queryFn: () => api.getMunicipality(townId),
    });
    const [active, setActive] = useState('solar_ground_mount');
    if (isLoading || !data)
        return _jsx("div", { className: "px-12 py-12 text-textDim", children: "Loading\u2026" });
    const bylaws = data.project_type_bylaws[active] || null;
    return (_jsxs("div", { className: "px-12 py-12 max-w-6xl", children: [_jsx("div", { className: "eyebrow mb-3", children: _jsx(Link, { to: "/municipalities", className: "hover:text-text", children: "\u2190 Municipalities" }) }), _jsx("h1", { style: {
                    fontFamily: DISPLAY,
                    fontSize: 54,
                    letterSpacing: -1.5,
                    lineHeight: 1.05,
                    fontWeight: 400,
                }, children: data.town_name }), _jsxs("div", { className: "text-sm text-textDim mt-2 mb-10", children: ["town_id ", data.town_id, " \u00B7 refreshed", ' ', data.last_refreshed_at
                        ? new Date(data.last_refreshed_at).toLocaleDateString()
                        : '—'] }), _jsx("div", { className: "flex gap-1 mb-8 border-b hairline", children: PROJECT_TYPES.map((pt) => (_jsx("button", { onClick: () => setActive(pt.code), className: "px-4 py-3 text-sm transition-colors", style: {
                        color: active === pt.code ? '#1a1a1a' : '#9b9b9b',
                        borderBottom: active === pt.code ? '2px solid #8b7355' : '2px solid transparent',
                        marginBottom: -1,
                    }, children: pt.label }, pt.code))) }), bylaws ? _jsx(BylawPanel, { bylaws: bylaws }) : (_jsx("div", { className: "text-textDim", children: "No data for this project type." }))] }));
}
function BylawPanel({ bylaws }) {
    const range = bylaws.estimated_timeline_months;
    return (_jsxs("div", { className: "grid grid-cols-3 gap-8", children: [_jsxs("div", { className: "col-span-2 space-y-6", children: [_jsx(Block, { label: "Approval authority", value: bylaws.approval_authority }), _jsx(Block, { label: "Process", value: String(bylaws.process || '—').replace(/_/g, ' ') }), _jsx(Block, { label: "Estimated timeline", value: range ? `${range[0]}–${range[1]} months` : '—' }), bylaws.notes && _jsx(Block, { label: "Notes", value: bylaws.notes }), bylaws.key_triggers?.length > 0 && (_jsxs("div", { children: [_jsx("div", { className: "eyebrow mb-3", children: "Key triggers" }), _jsx("ul", { className: "space-y-3", children: bylaws.key_triggers.map((t, i) => (_jsxs("li", { className: "border-l-2 pl-4", style: { borderColor: '#ececec' }, children: [_jsx("div", { className: "text-[14px]", children: t.description }), t.bylaw_ref && (_jsx("div", { className: "text-[11px] text-textDim mt-1 eyebrow", style: { fontSize: 11 }, children: t.bylaw_ref })), t.source_url && (_jsx("a", { href: t.source_url, target: "_blank", rel: "noreferrer", className: "text-[11px] text-accent hover:underline mt-1 inline-block", children: "Source \u2197" }))] }, i))) })] }))] }), _jsxs("div", { className: "space-y-4", children: [bylaws.setbacks_ft && (_jsxs("div", { className: "border hairline rounded-md bg-surface p-5", children: [_jsx("div", { className: "eyebrow mb-3", style: { fontSize: 11 }, children: "Setbacks (ft)" }), _jsxs("div", { className: "text-[13px] space-y-1", children: [_jsxs("div", { children: ["Front: ", bylaws.setbacks_ft.front ?? '—'] }), _jsxs("div", { children: ["Side: ", bylaws.setbacks_ft.side ?? '—'] }), _jsxs("div", { children: ["Rear: ", bylaws.setbacks_ft.rear ?? '—'] })] }), bylaws.setbacks_ft.note && (_jsx("div", { className: "text-[11px] text-textDim mt-3", children: bylaws.setbacks_ft.note }))] })), bylaws.citations?.length > 0 && (_jsxs("div", { className: "border hairline rounded-md bg-surface p-5", children: [_jsx("div", { className: "eyebrow mb-3", style: { fontSize: 11 }, children: "Citations" }), _jsx("ul", { className: "space-y-3", children: bylaws.citations.map((c, i) => (_jsx("li", { className: "text-[12px]", children: _jsx("a", { href: c.source_url, target: "_blank", rel: "noreferrer", className: "text-accent hover:underline", children: c.document_title }) }, i))) })] })), bylaws.verification_note && (_jsx("div", { className: "text-[11px] text-textDim italic", children: bylaws.verification_note }))] })] }));
}
function Block({ label, value }) {
    return (_jsxs("div", { children: [_jsx("div", { className: "eyebrow mb-2", style: { fontSize: 11 }, children: label }), _jsx("div", { style: { fontFamily: DISPLAY, fontSize: 20, lineHeight: 1.35 }, children: value })] }));
}
