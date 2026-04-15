import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
const C = {
    border: '#ececec',
    text: '#1a1a1a',
    textMid: '#6b6b6b',
    textDim: '#9b9b9b',
    accent: '#8b7355',
    surface: '#ffffff',
    good: '#4a7c4f',
    goodSoft: '#eaf2e7',
    warn: '#c08a3e',
    warnSoft: '#f7efe0',
    bad: '#a85a4a',
    badSoft: '#f5e8e4',
};
const DISPLAY = "'Fraunces', Georgia, serif";
export default function Portfolio() {
    const { portfolioId } = useParams();
    const { data, isLoading, error } = useQuery({
        queryKey: ['portfolio', portfolioId],
        queryFn: () => api.portfolio(portfolioId),
        enabled: !!portfolioId,
    });
    if (isLoading)
        return (_jsx("div", { className: "max-w-5xl mx-auto px-8 pt-rhythm", style: { color: C.textDim }, children: "Loading portfolio\u2026" }));
    if (error || !data)
        return (_jsxs("div", { className: "max-w-5xl mx-auto px-8 pt-rhythm text-bad", children: ["Error: ", String(error)] }));
    return (_jsxs("div", { className: "max-w-5xl mx-auto px-8 pt-rhythm pb-rhythm-lg", children: [_jsx("div", { className: "eyebrow mb-3", children: "Portfolio" }), _jsx("h1", { style: { fontFamily: DISPLAY, fontSize: 54, letterSpacing: -1.5, lineHeight: 1.05, fontWeight: 400 }, children: data.name || 'Untitled' }), _jsxs("div", { className: "text-sm text-textMid mt-2 mb-10", children: [data.id, " \u00B7 ", data.items.length, " parcels \u00B7 ", data.project_type || 'generic', " \u00B7 scored", ' ', new Date(data.scored_at).toLocaleDateString()] }), _jsxs("div", { className: "border hairline rounded-md overflow-hidden bg-surface", children: [_jsxs("div", { className: "grid text-[12px] uppercase tracking-wider text-textDim px-6 py-3 border-b hairline", style: { gridTemplateColumns: '40px 1fr 100px 220px 60px' }, children: [_jsx("div", { children: "#" }), _jsx("div", { children: "Address" }), _jsx("div", { children: "Score" }), _jsx("div", { children: "Bucket" }), _jsx("div", {})] }), data.items.map((it) => {
                        const tone = it.bucket === 'SUITABLE'
                            ? { c: C.good, bg: C.goodSoft }
                            : it.bucket === 'CONDITIONALLY SUITABLE'
                                ? { c: C.warn, bg: C.warnSoft }
                                : { c: C.bad, bg: C.badSoft };
                        return (_jsxs("div", { className: "grid items-center px-6 py-4 border-b hairline", style: { gridTemplateColumns: '40px 1fr 100px 220px 60px' }, children: [_jsx("div", { style: { fontFamily: DISPLAY, fontStyle: 'italic', color: C.textDim }, children: String(it.rank).padStart(2, '0') }), _jsxs("div", { children: [_jsx("div", { className: "text-[15px]", style: { fontFamily: DISPLAY }, children: it.address }), it.parcel_id && (_jsx("div", { className: "text-[12px] text-textDim", children: it.parcel_id }))] }), _jsx("div", { style: { fontFamily: DISPLAY, fontSize: 22 }, children: it.ok && it.total_score !== null ? Math.round(it.total_score) : '—' }), _jsx("div", { children: it.bucket ? (_jsx("span", { style: {
                                            display: 'inline-block',
                                            padding: '4px 12px',
                                            background: tone.bg,
                                            color: tone.c,
                                            borderRadius: 100,
                                            fontSize: 12,
                                            fontWeight: 500,
                                        }, children: it.bucket })) : (_jsx("span", { className: "text-textDim text-sm", children: it.error || '—' })) }), _jsx("div", { className: "text-right", children: it.score_report_id && (_jsx(Link, { to: `/report/${it.score_report_id}`, style: { color: C.accent, fontSize: 13 }, children: "View \u2192" })) })] }, it.rank));
                    })] })] }));
}
