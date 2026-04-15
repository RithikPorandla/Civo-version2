import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { MapView } from '../components/MapView';
const C = {
    bg: '#fafaf7',
    surface: '#ffffff',
    surfaceAlt: '#f5f2ea',
    border: '#ececec',
    borderHover: '#d4d1c7',
    text: '#1a1a1a',
    textMid: '#6b6b6b',
    textDim: '#9b9b9b',
    textFaint: '#b8b8b8',
    accent: '#8b7355',
    accentSoft: '#f0ede5',
    good: '#4a7c4f',
    goodSoft: '#eaf2e7',
    warn: '#c08a3e',
    warnSoft: '#f7efe0',
    bad: '#a85a4a',
    badSoft: '#f5e8e4',
};
const DISPLAY = "'Fraunces', Georgia, serif";
const SANS = "'Inter', -apple-system, system-ui, sans-serif";
const bucketTone = (b) => b === 'SUITABLE'
    ? { c: C.good, bg: C.goodSoft, label: 'Suitable' }
    : b === 'CONDITIONALLY SUITABLE'
        ? { c: C.warn, bg: C.warnSoft, label: 'Conditionally Suitable' }
        : { c: C.bad, bg: C.badSoft, label: 'Constrained' };
const statusTone = (s) => {
    if (s === 'ok')
        return { c: C.good, bg: C.goodSoft, label: 'OK' };
    if (s === 'flagged')
        return { c: C.warn, bg: C.warnSoft, label: 'Caution' };
    if (s === 'ineligible')
        return { c: C.bad, bg: C.badSoft, label: 'Risk' };
    return { c: C.textMid, bg: C.accentSoft, label: 'Pending' };
};
// Maps a flagged/ineligible primary constraint to a short mitigation hierarchy.
const mitigationFor = (primary, address) => {
    const common = [
        {
            tier: 'Avoid',
            text: 'Relocate or reduce the project footprint to eliminate overlap with the limiting constraint area.',
        },
        {
            tier: 'Minimize',
            text: 'Maintain buffers from sensitive resource areas. Keep disturbance under 50% of the parcel. Preserve existing vegetated corridors.',
        },
        {
            tier: 'Mitigate',
            text: 'Offsite restoration or in-lieu fee per 310 CMR 10.55 and applicable town wetland bylaws; SMART 3.0 benchmarks for solar apply.',
        },
    ];
    if (primary === 'biodiversity')
        return [
            {
                tier: 'Avoid',
                text: `Shift the project footprint away from the BioMap Core / NHESP Priority overlap near ${address}.`,
            },
            {
                tier: 'Minimize',
                text: 'Reduce footprint below 5 acres; retain 100-foot buffer from wetland resource edge and any documented vernal pool.',
            },
            common[2],
        ];
    if (primary === 'climate_resilience')
        return [
            {
                tier: 'Avoid',
                text: 'Site equipment outside the Special Flood Hazard Area (FEMA A/AE/VE). No habitable basements in SFHA.',
            },
            {
                tier: 'Minimize',
                text: 'Elevate critical equipment ≥2 ft above BFE per ResilientMass standards. Flood-proof enclosures.',
            },
            {
                tier: 'Mitigate',
                text: 'Design storm water management to the 100-year + 20% climate adder; coordinate with MassDEP 401.',
            },
        ];
    if (primary === 'agriculture')
        return [
            { tier: 'Avoid', text: 'Relocate from Prime Farmland soils and Chapter 61A parcels where feasible.' },
            {
                tier: 'Minimize',
                text: 'Dual-use (agrivoltaic) configuration per SMART 3.0 ADU incentives; preserve top 18" topsoil.',
            },
            common[2],
        ];
    return common;
};
function Eyebrow({ children }) {
    return (_jsx("div", { style: {
            fontFamily: DISPLAY,
            fontStyle: 'italic',
            fontSize: 13,
            color: C.accent,
            marginBottom: 6,
        }, children: children }));
}
function MetaItem({ label, value }) {
    return (_jsxs("div", { children: [_jsx("div", { style: {
                    fontSize: 11,
                    color: C.textDim,
                    marginBottom: 4,
                    letterSpacing: 0.3,
                    textTransform: 'uppercase',
                    fontWeight: 500,
                }, children: label }), _jsx("div", { style: { fontSize: 14, color: C.text }, children: value })] }));
}
function btnGhost() {
    return {
        background: 'transparent',
        color: C.textMid,
        border: `1px solid ${C.border}`,
        borderRadius: 100,
        padding: '10px 18px',
        fontSize: 13,
        cursor: 'pointer',
        fontFamily: SANS,
    };
}
function btnPrimary() {
    return {
        background: C.text,
        color: C.bg,
        border: 'none',
        borderRadius: 100,
        padding: '10px 20px',
        fontSize: 13,
        fontWeight: 500,
        cursor: 'pointer',
        fontFamily: SANS,
    };
}
export default function Report() {
    const { reportId } = useParams();
    const { data: report, isLoading, error } = useQuery({
        queryKey: ['report', reportId],
        queryFn: () => api.report(reportId),
        enabled: !!reportId,
    });
    const { data: precedents } = useQuery({
        queryKey: ['precedents', report?.parcel_id],
        queryFn: () => api.parcelPrecedents(report.parcel_id, 5),
        enabled: !!report?.parcel_id,
    });
    const [expanded, setExpanded] = useState(null);
    if (isLoading)
        return _jsx(Loading, {});
    if (error || !report)
        return _jsx(ErrorState, { err: String(error) });
    return _jsx(ReportView, { report: report, precedents: precedents || [], expanded: expanded, setExpanded: setExpanded });
}
function Loading() {
    return (_jsx("div", { style: { padding: '80px 40px', fontFamily: SANS, color: C.textDim, textAlign: 'center' }, children: _jsx("div", { style: { fontFamily: DISPLAY, fontStyle: 'italic' }, children: "Loading report\u2026" }) }));
}
function ErrorState({ err }) {
    return (_jsxs("div", { style: { padding: '80px 40px', fontFamily: SANS, color: C.bad, maxWidth: 720, margin: '0 auto' }, children: [_jsx(Eyebrow, { children: "Something went wrong" }), _jsx("p", { children: err }), _jsx(Link, { to: "/", style: { color: C.accent }, children: "\u2190 Back to search" })] }));
}
function ReportView({ report, precedents, expanded, setExpanded, }) {
    const tone = bucketTone(report.bucket);
    const address = report.address || report.parcel_id;
    const mitigation = useMemo(() => mitigationFor(report.primary_constraint, address), [report.primary_constraint, address]);
    return (_jsxs("div", { style: { fontFamily: SANS, background: C.bg, color: C.text, minHeight: '100vh' }, children: [_jsxs("div", { style: {
                    padding: '22px 40px',
                    borderBottom: `1px solid ${C.border}`,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: C.bg,
                    position: 'sticky',
                    top: 0,
                    zIndex: 10,
                }, children: [_jsxs("div", { style: { display: 'flex', alignItems: 'center', gap: 40 }, children: [_jsx(Link, { to: "/", style: { fontFamily: DISPLAY, fontSize: 22, fontWeight: 500, letterSpacing: -0.5, color: C.text, textDecoration: 'none' }, children: "Civo" }), _jsx("div", { style: { display: 'flex', gap: 28, fontSize: 13, color: C.textMid }, children: ['Dashboard', 'Portfolio', 'Towns', 'Methodology'].map((l, i) => (_jsx("span", { style: { cursor: 'pointer' }, children: l }, i))) })] }), _jsxs("div", { style: { display: 'flex', gap: 10 }, children: [_jsx("button", { style: btnGhost(), children: "Export PDF" }), _jsx("button", { style: btnGhost(), children: "Save to portfolio" }), _jsx(Link, { to: "/", style: { textDecoration: 'none' }, children: _jsx("button", { style: btnPrimary(), children: "New analysis" }) })] })] }), _jsxs("div", { style: { maxWidth: 1180, margin: '0 auto', padding: '40px 40px 80px' }, children: [_jsxs("div", { style: {
                            fontSize: 13,
                            color: C.textDim,
                            marginBottom: 20,
                            display: 'flex',
                            gap: 10,
                            alignItems: 'center',
                        }, children: [_jsx(Link, { to: "/", style: { color: C.textDim, textDecoration: 'none' }, children: "Portfolio" }), _jsx("span", { children: "\u203A" }), _jsx("span", { children: "candidate-sites" }), _jsx("span", { children: "\u203A" }), _jsx("span", { style: { color: C.text }, children: address })] }), _jsxs("div", { style: {
                            display: 'grid',
                            gridTemplateColumns: '1fr 360px',
                            gap: 48,
                            alignItems: 'flex-start',
                            marginBottom: 56,
                        }, children: [_jsxs("div", { children: [_jsx(Eyebrow, { children: "Suitability Report" }), _jsx("h1", { style: {
                                            fontFamily: DISPLAY,
                                            fontSize: 54,
                                            fontWeight: 400,
                                            lineHeight: 1.05,
                                            letterSpacing: -1.5,
                                            margin: '0 0 12px',
                                        }, children: address }), _jsx("div", { style: { fontSize: 17, color: C.textMid, marginBottom: 28 }, children: report.parcel_id }), _jsxs("div", { style: {
                                            display: 'grid',
                                            gridTemplateColumns: 'repeat(4, auto)',
                                            gap: 40,
                                            paddingTop: 20,
                                            borderTop: `1px solid ${C.border}`,
                                        }, children: [_jsx(MetaItem, { label: "Parcel ID", value: report.parcel_id }), _jsx(MetaItem, { label: "Project type", value: report.project_type }), _jsx(MetaItem, { label: "Methodology", value: report.config_version }), _jsx(MetaItem, { label: "Primary constraint", value: report.primary_constraint || '—' })] })] }), _jsxs("div", { style: {
                                    background: C.surface,
                                    borderRadius: 20,
                                    padding: '36px 32px',
                                    border: `1px solid ${C.border}`,
                                }, children: [_jsx(Eyebrow, { children: "Total score" }), _jsxs("div", { style: { display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 16 }, children: [_jsx("div", { style: {
                                                    fontFamily: DISPLAY,
                                                    fontSize: 96,
                                                    fontWeight: 400,
                                                    lineHeight: 0.9,
                                                    letterSpacing: -4,
                                                }, children: Math.round(report.total_score) }), _jsx("div", { style: { fontSize: 20, color: C.textDim, fontWeight: 300 }, children: "/ 100" })] }), _jsx("div", { style: {
                                            display: 'inline-block',
                                            padding: '8px 16px',
                                            background: tone.bg,
                                            borderRadius: 100,
                                            fontSize: 13,
                                            color: tone.c,
                                            fontWeight: 500,
                                            marginBottom: 20,
                                        }, children: tone.label }), _jsx("p", { style: {
                                            fontSize: 14,
                                            color: C.textMid,
                                            lineHeight: 1.6,
                                            margin: 0,
                                            paddingTop: 20,
                                            borderTop: `1px solid ${C.border}`,
                                        }, children: interpretationText(report) })] })] }), _jsxs("section", { style: { marginBottom: 80 }, children: [_jsxs("div", { style: {
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'flex-end',
                                    marginBottom: 20,
                                }, children: [_jsxs("div", { children: [_jsx(Eyebrow, { children: "Site context" }), _jsx("h2", { style: {
                                                    fontFamily: DISPLAY,
                                                    fontSize: 32,
                                                    fontWeight: 400,
                                                    letterSpacing: -0.8,
                                                    margin: 0,
                                                }, children: "The parcel and its surroundings" })] }), _jsx("div", { style: { display: 'flex', gap: 8 }, children: ['Parcel', 'Habitat', 'Wetlands', 'ESMP'].map((l, i) => (_jsx("span", { style: {
                                                fontSize: 12,
                                                color: C.textMid,
                                                padding: '6px 12px',
                                                background: C.surface,
                                                border: `1px solid ${C.border}`,
                                                borderRadius: 100,
                                                cursor: 'default',
                                            }, children: l }, i))) })] }), _jsx(MapView, { parcelId: report.parcel_id })] }), _jsxs("section", { style: { marginBottom: 80 }, children: [_jsxs("div", { style: { marginBottom: 32 }, children: [_jsx(Eyebrow, { children: "How the score breaks down" }), _jsx("h2", { style: {
                                            fontFamily: DISPLAY,
                                            fontSize: 32,
                                            fontWeight: 400,
                                            letterSpacing: -0.8,
                                            margin: '0 0 12px',
                                        }, children: "Seven criteria, weighted." }), _jsx("p", { style: {
                                            fontSize: 15,
                                            color: C.textMid,
                                            lineHeight: 1.6,
                                            margin: 0,
                                            maxWidth: 680,
                                        }, children: "Each criterion is evaluated against the 2024 Climate Act methodology codified in 225 CMR 29.00. Click any row to see the full finding and cited sources." })] }), _jsx("div", { style: {
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 1,
                                    background: C.border,
                                    borderRadius: 16,
                                    overflow: 'hidden',
                                    border: `1px solid ${C.border}`,
                                }, children: report.criteria.map((c, i) => (_jsx(CriterionRow, { idx: i + 1, c: c, expanded: expanded === c.key, onToggle: () => setExpanded(expanded === c.key ? null : c.key) }, c.key))) })] }), _jsxs("section", { style: {
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr',
                            gap: 40,
                            marginBottom: 80,
                        }, children: [_jsxs("div", { children: [_jsxs("div", { style: { marginBottom: 24 }, children: [_jsx(Eyebrow, { children: "What you can do about it" }), _jsx("h2", { style: {
                                                    fontFamily: DISPLAY,
                                                    fontSize: 28,
                                                    fontWeight: 400,
                                                    letterSpacing: -0.6,
                                                    margin: 0,
                                                }, children: "Mitigation hierarchy" })] }), _jsx("div", { style: { display: 'flex', flexDirection: 'column', gap: 16 }, children: mitigation.map((m, i) => (_jsxs("div", { style: {
                                                background: C.surface,
                                                border: `1px solid ${C.border}`,
                                                borderRadius: 14,
                                                padding: '20px 24px',
                                            }, children: [_jsxs("div", { style: {
                                                        fontSize: 12,
                                                        color: C.accent,
                                                        fontFamily: DISPLAY,
                                                        fontStyle: 'italic',
                                                        marginBottom: 8,
                                                    }, children: [String(i + 1).padStart(2, '0'), " \u00B7 ", m.tier] }), _jsx("p", { style: { fontSize: 14, color: C.textMid, lineHeight: 1.6, margin: 0 }, children: m.text })] }, i))) })] }), _jsxs("div", { children: [_jsxs("div", { style: { marginBottom: 24 }, children: [_jsx(Eyebrow, { children: "What this town has decided before" }), _jsx("h2", { style: {
                                                    fontFamily: DISPLAY,
                                                    fontSize: 28,
                                                    fontWeight: 400,
                                                    letterSpacing: -0.6,
                                                    margin: 0,
                                                }, children: "Relevant precedents" })] }), _jsx("div", { style: { display: 'flex', flexDirection: 'column', gap: 16 }, children: precedents.length === 0 ? (_jsx("div", { style: {
                                                background: C.surface,
                                                border: `1px solid ${C.border}`,
                                                borderRadius: 14,
                                                padding: '20px 24px',
                                                color: C.textDim,
                                                fontSize: 14,
                                                lineHeight: 1.6,
                                            }, children: "No precedents loaded for this town yet. The research agent has only populated Acton in this build. Other towns will populate in the next run." })) : (precedents.map((p) => (_jsxs("a", { href: p.source_url, target: "_blank", rel: "noreferrer", style: {
                                                textDecoration: 'none',
                                                background: C.surface,
                                                border: `1px solid ${C.border}`,
                                                borderRadius: 14,
                                                padding: '20px 24px',
                                                display: 'block',
                                                color: 'inherit',
                                            }, children: [_jsxs("div", { style: {
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'flex-start',
                                                        marginBottom: 8,
                                                        gap: 12,
                                                    }, children: [_jsxs("div", { children: [_jsx("div", { style: {
                                                                        fontSize: 15,
                                                                        color: C.text,
                                                                        fontWeight: 500,
                                                                        fontFamily: DISPLAY,
                                                                    }, children: p.applicant || p.project_address || p.docket || 'Unnamed project' }), _jsxs("div", { style: { fontSize: 12, color: C.textDim, marginTop: 3 }, children: [(p.decision_date || p.filing_date || p.created_at).slice(0, 10), " \u00B7", ' ', p.project_type, " ", p.meeting_body ? `· ${p.meeting_body}` : ''] })] }), p.decision && _jsx(PrecedentDecisionPill, { decision: p.decision })] }), p.project_address && (_jsxs("p", { style: {
                                                        fontSize: 13,
                                                        color: C.textMid,
                                                        lineHeight: 1.55,
                                                        margin: 0,
                                                    }, children: [p.project_address, p.docket ? ` · ${p.docket}` : ''] }))] }, p.id)))) })] })] }), _jsxs("div", { style: {
                            paddingTop: 32,
                            borderTop: `1px solid ${C.border}`,
                            display: 'flex',
                            justifyContent: 'space-between',
                            fontSize: 12,
                            color: C.textDim,
                            flexWrap: 'wrap',
                            gap: 16,
                        }, children: [_jsxs("div", { children: ["Scored on ", new Date(report.computed_at).toLocaleDateString(), " \u00B7 Configuration", ' ', report.config_version] }), _jsx("div", { children: "Data sources: MassGIS \u00B7 NHESP \u00B7 FEMA NFHL \u00B7 Eversource ESMP DPU 24-10" }), _jsxs("div", { children: ["All scoring traceable to ", report.methodology] })] })] })] }));
}
function interpretationText(report) {
    const pc = report.primary_constraint;
    const niceName = {
        biodiversity: 'Biodiversity',
        climate_resilience: 'Climate resilience',
        carbon_storage: 'Carbon storage',
        grid_alignment: 'Grid alignment',
        burdens: 'Environmental burdens',
        benefits: 'Environmental benefits',
        agriculture: 'Agricultural production',
    };
    if (report.bucket === 'SUITABLE')
        return `Site meets the MA EEA site-suitability threshold. ${pc ? niceName[pc] ?? pc : 'No individual'} is the lowest-scoring criterion; review the row below for detail.`;
    if (report.bucket === 'CONDITIONALLY SUITABLE')
        return `${niceName[pc || ''] || 'A scoring criterion'} is the limiting factor. Site is developable with mitigation. See precedents for how similar outcomes have been conditioned.`;
    return `${niceName[pc || ''] || 'Multiple criteria'} are driving a constrained rating. Consider an alternate site or a significantly reduced footprint.`;
}
function PrecedentDecisionPill({ decision }) {
    const denied = decision === 'denied';
    const withdrawn = decision === 'withdrawn';
    const pending = decision === 'pending' || decision === 'continued';
    const tone = denied || withdrawn
        ? { c: C.bad, bg: C.badSoft }
        : pending
            ? { c: C.warn, bg: C.warnSoft }
            : { c: C.good, bg: C.goodSoft };
    const label = decision.replace(/_/g, ' ');
    return (_jsx("div", { style: {
            fontSize: 11,
            color: tone.c,
            background: tone.bg,
            padding: '4px 12px',
            borderRadius: 100,
            fontWeight: 500,
            whiteSpace: 'nowrap',
            textTransform: 'capitalize',
        }, children: label }));
}
function CriterionRow({ idx, c, expanded, onToggle, }) {
    const tone = statusTone(c.status);
    return (_jsxs("div", { onClick: onToggle, style: { background: C.surface, padding: '24px 32px', cursor: 'pointer' }, children: [_jsxs("div", { style: {
                    display: 'grid',
                    gridTemplateColumns: '40px 1fr 200px 80px 40px',
                    gap: 24,
                    alignItems: 'center',
                }, children: [_jsx("div", { style: {
                            fontSize: 13,
                            color: C.textDim,
                            fontFamily: DISPLAY,
                            fontStyle: 'italic',
                        }, children: String(idx).padStart(2, '0') }), _jsxs("div", { children: [_jsx("div", { style: { fontSize: 17, color: C.text, fontWeight: 500, fontFamily: DISPLAY }, children: c.name }), _jsxs("div", { style: { fontSize: 12, color: C.textDim, marginTop: 4 }, children: ["Weight ", Math.round(c.weight * 100), "%"] })] }), _jsxs("div", { style: { display: 'flex', alignItems: 'center', gap: 12 }, children: [_jsx("div", { style: {
                                    flex: 1,
                                    height: 4,
                                    background: C.border,
                                    borderRadius: 2,
                                    overflow: 'hidden',
                                }, children: _jsx("div", { style: {
                                        width: `${c.raw_score * 10}%`,
                                        height: '100%',
                                        background: tone.c,
                                        borderRadius: 2,
                                        transition: 'width 240ms ease',
                                    } }) }), _jsxs("div", { style: { fontSize: 13, color: C.textMid, minWidth: 36, textAlign: 'right' }, children: [c.raw_score.toFixed(1), "/10"] })] }), _jsx("div", { style: {
                            fontSize: 11,
                            color: tone.c,
                            fontWeight: 500,
                            padding: '4px 10px',
                            background: tone.bg,
                            borderRadius: 100,
                            textAlign: 'center',
                        }, children: tone.label }), _jsx("div", { style: {
                            fontSize: 14,
                            color: C.textDim,
                            textAlign: 'right',
                            transform: expanded ? 'rotate(180deg)' : 'none',
                            transition: 'transform 0.2s',
                        }, children: "\u2304" })] }), expanded && (_jsxs("div", { style: {
                    marginTop: 20,
                    paddingTop: 20,
                    borderTop: `1px solid ${C.border}`,
                    display: 'grid',
                    gridTemplateColumns: '40px 1fr',
                    gap: 24,
                }, children: [_jsx("div", {}), _jsxs("div", { children: [_jsx("div", { style: {
                                    fontSize: 11,
                                    color: C.textDim,
                                    textTransform: 'uppercase',
                                    letterSpacing: 0.5,
                                    marginBottom: 10,
                                    fontWeight: 500,
                                }, children: "Finding" }), _jsx("p", { style: {
                                    fontSize: 15,
                                    color: C.text,
                                    lineHeight: 1.65,
                                    margin: '0 0 20px',
                                }, children: c.finding }), c.citations.length > 0 && (_jsxs(_Fragment, { children: [_jsx("div", { style: {
                                            fontSize: 11,
                                            color: C.textDim,
                                            textTransform: 'uppercase',
                                            letterSpacing: 0.5,
                                            marginBottom: 10,
                                            fontWeight: 500,
                                        }, children: "Sources" }), _jsx("div", { style: { display: 'flex', flexWrap: 'wrap', gap: 8 }, children: c.citations.map((s, i) => s.url ? (_jsxs("a", { href: s.url, target: "_blank", rel: "noreferrer", style: {
                                                fontSize: 12,
                                                color: C.accent,
                                                padding: '4px 12px',
                                                background: C.accentSoft,
                                                borderRadius: 100,
                                                textDecoration: 'none',
                                            }, children: [s.dataset, s.detail ? ` · ${s.detail}` : '', " \u2197"] }, i)) : (_jsxs("span", { style: {
                                                fontSize: 12,
                                                color: C.textMid,
                                                padding: '4px 12px',
                                                background: C.accentSoft,
                                                borderRadius: 100,
                                            }, children: [s.dataset, s.detail ? ` · ${s.detail}` : ''] }, i))) })] }))] })] }))] }));
}
