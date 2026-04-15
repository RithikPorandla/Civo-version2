import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
const bucketStyles = {
    SUITABLE: 'bg-goodSoft text-good border-good/20',
    'CONDITIONALLY SUITABLE': 'bg-warnSoft text-warn border-warn/20',
    CONSTRAINED: 'bg-badSoft text-bad border-bad/20',
};
const criterionStyles = {
    ok: 'bg-goodSoft text-good border-good/20',
    flagged: 'bg-warnSoft text-warn border-warn/20',
    ineligible: 'bg-badSoft text-bad border-bad/20',
    data_unavailable: 'bg-accentSoft text-textMid border-border',
};
const criterionLabels = {
    ok: 'Clear',
    flagged: 'Flagged',
    ineligible: 'Ineligible',
    data_unavailable: 'Data pending',
};
export function BucketPill({ bucket }) {
    return (_jsxs("span", { className: `inline-flex items-center gap-2 px-4 py-1.5 rounded-pill border text-[13px] tracking-wide ${bucketStyles[bucket]}`, children: [_jsx("span", { className: "w-1.5 h-1.5 rounded-full bg-current" }), bucket] }));
}
export function CriterionPill({ status }) {
    return (_jsx("span", { className: `inline-flex items-center px-2.5 py-0.5 rounded-pill border text-[11px] ${criterionStyles[status]}`, children: criterionLabels[status] }));
}
