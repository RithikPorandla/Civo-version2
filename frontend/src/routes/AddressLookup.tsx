import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ProjectTypeCode } from '../lib/api';

const PROJECT_TYPES: Array<{ code: ProjectTypeCode; label: string; hint: string }> = [
  { code: 'solar_rooftop', label: 'Solar Rooftop', hint: 'Building permit · by-right accessory' },
  { code: 'solar_ground_mount', label: 'Solar Ground-Mount', hint: '225 CMR 29 + town bylaw' },
  { code: 'solar_canopy', label: 'Solar Canopy', hint: 'Parking-lot · SMART canopy adder' },
  { code: 'bess_standalone', label: 'BESS Standalone', hint: 'NFPA 855 · 50 ft setback' },
  { code: 'bess_colocated', label: 'BESS Co-located', hint: 'Rider on solar permit' },
  { code: 'substation', label: 'Substation', hint: 'G.L. c.40A §3 + EFSB' },
  { code: 'transmission', label: 'Transmission', hint: 'G.L. c.164 §69J (≥69 kV)' },
  { code: 'ev_charging', label: 'EV Charging', hint: 'By-right statewide (2022)' },
];

export default function AddressLookup() {
  const [address, setAddress] = useState('Kendall Square, Cambridge, MA 02142');
  const [projectType, setProjectType] = useState<ProjectTypeCode>('solar_ground_mount');
  const [nameplateKw, setNameplateKw] = useState('');
  const [footprintAcres, setFootprintAcres] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();

  const current = PROJECT_TYPES.find((p) => p.code === projectType)!;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const env = await api.score(address, projectType);
      const qs = new URLSearchParams({ pt: projectType });
      if (nameplateKw) qs.set('kw', nameplateKw);
      if (footprintAcres) qs.set('acres', footprintAcres);
      nav(`/report/${env.report_id}?${qs.toString()}`);
    } catch (e: unknown) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ padding: '36px 40px 80px', maxWidth: 840 }}>
      <div className="eyebrow" style={{ marginBottom: 10 }}>
        Score a site
      </div>
      <h1
        className="display"
        style={{ fontSize: 34, margin: 0, letterSpacing: '-0.018em', lineHeight: 1.05 }}
      >
        Score a Massachusetts site
      </h1>
      <p
        style={{
          fontSize: 15,
          lineHeight: 1.6,
          color: 'var(--text-mid)',
          maxWidth: 560,
          margin: '14px 0 0',
        }}
      >
        Paste any MA address and pick the project type. Civo resolves to the MassGIS parcel and
        produces a scored report with every constraint cited.
      </p>
      <hr className="rule" style={{ margin: '28px 0' }} />

      <form
        onSubmit={submit}
        className="card"
        style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 20 }}
      >
        <Field label="Address">
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="e.g. 50 Nagog Park, Acton, MA"
            style={inputStyle}
          />
        </Field>

        <Field label="Project type" hint={current.hint}>
          <div style={{ position: 'relative' }}>
            <select
              value={projectType}
              onChange={(e) => setProjectType(e.target.value as ProjectTypeCode)}
              style={{ ...inputStyle, appearance: 'none', paddingRight: 38, cursor: 'pointer' }}
            >
              {PROJECT_TYPES.map((pt) => (
                <option key={pt.code} value={pt.code}>
                  {pt.label}
                </option>
              ))}
            </select>
            <span
              aria-hidden="true"
              style={{
                position: 'absolute',
                right: 14,
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-dim)',
                fontSize: 12,
                pointerEvents: 'none',
              }}
            >
              ▾
            </span>
          </div>
        </Field>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Field label="Nameplate kW (optional)">
            <input
              type="number"
              step="any"
              min="0"
              value={nameplateKw}
              onChange={(e) => setNameplateKw(e.target.value)}
              placeholder="10"
              style={inputStyle}
            />
          </Field>
          <Field label="Footprint acres (optional)">
            <input
              type="number"
              step="any"
              min="0"
              value={footprintAcres}
              onChange={(e) => setFootprintAcres(e.target.value)}
              placeholder="0.5"
              style={inputStyle}
            />
          </Field>
        </div>
        <p
          style={{
            fontSize: 12,
            color: 'var(--text-dim)',
            fontFamily: "'Fraunces', Georgia, serif",
            fontStyle: 'italic',
            margin: '-4px 0 0',
          }}
        >
          Both values together trigger the 225 CMR 29.07(1) exemption check.
        </p>

        <div>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Scoring…' : 'Score site'}
            <span className="arr">→</span>
          </button>
        </div>
      </form>

      {err && (
        <div style={{ color: 'var(--bad)', fontSize: 13, lineHeight: 1.55, marginTop: 14 }}>
          {err}
        </div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '11px 14px',
  fontSize: 14,
  fontFamily: 'inherit',
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  outline: 'none',
  color: 'var(--text)',
  transition: 'border-color 150ms ease, box-shadow 150ms ease',
};

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span className="label">{label}</span>
      {children}
      {hint && (
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
          {hint}
        </span>
      )}
    </label>
  );
}
