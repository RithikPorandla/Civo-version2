import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { CriterionPill } from './StatusPill';
const fillColor = (status) => {
    switch (status) {
        case 'ok':
            return '#4a7c4f';
        case 'flagged':
            return '#c08a3e';
        case 'ineligible':
            return '#a85a4a';
        default:
            return '#9b9b9b';
    }
};
export function CriterionRow({ idx, criterion }) {
    const [open, setOpen] = useState(false);
    const pct = (criterion.raw_score / 10) * 100;
    return (_jsx("div", { className: "border-b hairline py-7", children: _jsxs("button", { className: "w-full flex items-start gap-6 text-left", onClick: () => setOpen((o) => !o), children: [_jsx("div", { className: "w-10 pt-1 shrink-0", children: _jsx("span", { className: "display italic text-textDim text-[20px]", children: idx.toString().padStart(2, '0') }) }), _jsxs("div", { className: "flex-1", children: [_jsxs("div", { className: "flex items-start justify-between gap-6 mb-4", children: [_jsxs("div", { children: [_jsx("div", { className: "display text-displayXS text-text", children: criterion.name }), _jsxs("div", { className: "eyebrow mt-1", children: ["Weight ", Math.round(criterion.weight * 100), "%"] })] }), _jsxs("div", { className: "flex items-center gap-4 shrink-0", children: [_jsx(CriterionPill, { status: criterion.status }), _jsxs("div", { className: "text-right", children: [_jsx("div", { className: "display text-displayS", children: criterion.raw_score.toFixed(1) }), _jsx("div", { className: "eyebrow", children: "of 10" })] })] })] }), _jsx("div", { className: "bar-track", children: _jsx("div", { className: "bar-fill", style: { width: `${pct}%`, background: fillColor(criterion.status) } }) }), open && (_jsxs("div", { className: "mt-6 space-y-4", children: [_jsx("p", { className: "text-[15px] leading-[1.7] text-textMid max-w-3xl", children: criterion.finding }), _jsx("div", { className: "flex flex-wrap gap-2", children: criterion.citations.map((c, i) => (_jsxs("a", { href: c.url || '#', target: "_blank", rel: "noreferrer", className: "chip hover:border-borderHover", children: [_jsx("span", { className: "text-text", children: c.dataset }), c.detail && _jsxs("span", { children: ["\u00B7 ", c.detail] })] }, i))) })] }))] })] }) }));
}
