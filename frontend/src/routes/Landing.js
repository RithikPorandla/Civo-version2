import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
export default function Landing() {
    const [address, setAddress] = useState('Kendall Square, Cambridge, MA 02142');
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);
    const nav = useNavigate();
    async function submit(e) {
        e.preventDefault();
        setErr(null);
        setBusy(true);
        try {
            const env = await api.score(address);
            nav(`/report/${env.report_id}`);
        }
        catch (e) {
            setErr(String(e));
        }
        finally {
            setBusy(false);
        }
    }
    return (_jsxs("div", { className: "max-w-3xl mx-auto px-8 pt-rhythm-lg pb-rhythm", children: [_jsx("div", { className: "eyebrow mb-3", children: "Score an address" }), _jsx("h1", { className: "display text-displayM mb-8", children: "MA EEA Site Suitability" }), _jsxs("form", { onSubmit: submit, className: "flex items-stretch gap-3 border hairline rounded-pill bg-surface p-2 pl-5", children: [_jsx("input", { className: "flex-1 bg-transparent outline-none text-[15px] py-3", value: address, onChange: (e) => setAddress(e.target.value), placeholder: "Paste a Massachusetts address" }), _jsx("button", { className: "btn-pill btn-pill-primary", disabled: busy, children: busy ? 'Scoring…' : 'Score →' })] }), err && _jsx("div", { className: "text-bad text-sm mt-4", children: err })] }));
}
