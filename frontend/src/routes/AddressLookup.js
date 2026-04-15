import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import ThreeDMap from '../components/ThreeDMap';
const DISPLAY = "'Fraunces', Georgia, serif";
const PROJECT_TYPES = [
    { code: 'solar_ground_mount', label: 'Solar PV (Ground-Mount)', hint: '225 CMR 29 + town bylaw' },
    { code: 'bess', label: 'Battery Energy Storage', hint: '527 CMR 1 + NFPA 855' },
    { code: 'substation', label: 'Substation', hint: 'G.L. c.40A §3 + EFSB' },
    { code: 'wind', label: 'Wind Turbine', hint: 'Town height bylaw + EFSB ≥100 MW' },
    { code: 'transmission', label: 'Transmission Line', hint: 'G.L. c.164 §69J (≥69 kV)' },
];
export default function AddressLookup() {
    const [address, setAddress] = useState('Kendall Square, Cambridge, MA 02142');
    const [projectType, setProjectType] = useState('substation');
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);
    const nav = useNavigate();
    async function submit(e) {
        e.preventDefault();
        setErr(null);
        setBusy(true);
        try {
            const env = await api.score(address, projectType);
            nav(`/report/${env.report_id}?pt=${projectType}`);
        }
        catch (e) {
            setErr(String(e));
        }
        finally {
            setBusy(false);
        }
    }
    return (_jsxs("div", { className: "px-12 py-12 max-w-6xl", children: [_jsx("div", { className: "eyebrow mb-3", children: "Address Lookup" }), _jsx("h1", { style: {
                    fontFamily: DISPLAY,
                    fontSize: 54,
                    letterSpacing: -1.5,
                    lineHeight: 1.05,
                    fontWeight: 400,
                }, children: "Score a Massachusetts site." }), _jsx("p", { className: "text-textMid mt-6 max-w-2xl mb-10", children: "Paste any MA address and pick the project type. Civo resolves it to the MassGIS parcel, surfaces the overhead view, and produces a scored report with every constraint cited." }), _jsxs("form", { onSubmit: submit, className: "flex items-stretch gap-3 border hairline rounded-pill bg-surface p-2 pl-5 max-w-3xl", children: [_jsx("input", { className: "flex-1 bg-transparent outline-none text-[15px] py-3", value: address, onChange: (e) => setAddress(e.target.value), placeholder: "Paste a Massachusetts address" }), _jsx("button", { className: "btn-pill btn-pill-primary", disabled: busy, children: busy ? 'Scoring…' : 'Score →' })] }), err && _jsx("div", { className: "text-bad text-sm mt-4", children: err }), _jsxs("section", { className: "mt-10", children: [_jsx("div", { className: "eyebrow mb-3", children: "Project type" }), _jsx("div", { className: "grid grid-cols-5 gap-3 max-w-4xl", children: PROJECT_TYPES.map((pt) => {
                            const active = projectType === pt.code;
                            return (_jsxs("button", { type: "button", onClick: () => setProjectType(pt.code), className: "border hairline rounded-md bg-surface px-4 py-4 text-left transition", style: {
                                    borderColor: active ? '#8b7355' : '#ececec',
                                    background: active ? '#f5f2ea' : '#ffffff',
                                }, children: [_jsx("div", { style: { fontFamily: DISPLAY, fontSize: 15 }, className: "mb-1", children: pt.label }), _jsx("div", { className: "text-[11px] text-textDim", children: pt.hint })] }, pt.code));
                        }) })] }), _jsxs("section", { className: "mt-12", children: [_jsx("div", { className: "eyebrow mb-3", children: "Site preview (3D)" }), _jsx("div", { className: "border hairline rounded-md overflow-hidden bg-surface", style: { height: 440 }, children: _jsx(ThreeDMap, { address: address }) }), _jsx("div", { className: "text-[11px] text-textDim mt-2", children: "Imagery: Google Photorealistic 3D Tiles. Click-and-drag to orbit, scroll to zoom." })] })] }));
}
