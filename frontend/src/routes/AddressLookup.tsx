import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ProjectTypeCode } from '../lib/api';
import ThreeDMap from '../components/ThreeDMap';

const DISPLAY = "'Fraunces', Georgia, serif";

const PROJECT_TYPES: Array<{ code: ProjectTypeCode; label: string; hint: string }> = [
  { code: 'solar_ground_mount', label: 'Solar PV (Ground-Mount)', hint: '225 CMR 29 + town bylaw' },
  { code: 'bess', label: 'Battery Energy Storage', hint: '527 CMR 1 + NFPA 855' },
  { code: 'substation', label: 'Substation', hint: 'G.L. c.40A §3 + EFSB' },
  { code: 'wind', label: 'Wind Turbine', hint: 'Town height bylaw + EFSB ≥100 MW' },
  { code: 'transmission', label: 'Transmission Line', hint: 'G.L. c.164 §69J (≥69 kV)' },
];

export default function AddressLookup() {
  const [address, setAddress] = useState('Kendall Square, Cambridge, MA 02142');
  const [projectType, setProjectType] = useState<ProjectTypeCode>('substation');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const env = await api.score(address, projectType);
      nav(`/report/${env.report_id}?pt=${projectType}`);
    } catch (e: unknown) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="px-12 py-12 max-w-6xl">
      <div className="eyebrow mb-3">Address Lookup</div>
      <h1
        style={{
          fontFamily: DISPLAY,
          fontSize: 54,
          letterSpacing: -1.5,
          lineHeight: 1.05,
          fontWeight: 400,
        }}
      >
        Score a Massachusetts site.
      </h1>
      <p className="text-textMid mt-6 max-w-2xl mb-10">
        Paste any MA address and pick the project type. Civo resolves it to the
        MassGIS parcel, surfaces the overhead view, and produces a scored report
        with every constraint cited.
      </p>

      <form
        onSubmit={submit}
        className="flex items-stretch gap-3 border hairline rounded-pill bg-surface p-2 pl-5 max-w-3xl"
      >
        <input
          className="flex-1 bg-transparent outline-none text-[15px] py-3"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="Paste a Massachusetts address"
        />
        <button className="btn-pill btn-pill-primary" disabled={busy}>
          {busy ? 'Scoring…' : 'Score →'}
        </button>
      </form>
      {err && <div className="text-bad text-sm mt-4">{err}</div>}

      <section className="mt-10">
        <div className="eyebrow mb-3">Project type</div>
        <div className="grid grid-cols-5 gap-3 max-w-4xl">
          {PROJECT_TYPES.map((pt) => {
            const active = projectType === pt.code;
            return (
              <button
                key={pt.code}
                type="button"
                onClick={() => setProjectType(pt.code)}
                className="border hairline rounded-md bg-surface px-4 py-4 text-left transition"
                style={{
                  borderColor: active ? '#8b7355' : '#ececec',
                  background: active ? '#f5f2ea' : '#ffffff',
                }}
              >
                <div style={{ fontFamily: DISPLAY, fontSize: 15 }} className="mb-1">
                  {pt.label}
                </div>
                <div className="text-[11px] text-textDim">{pt.hint}</div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="mt-12">
        <div className="eyebrow mb-3">Site preview (3D)</div>
        <div
          className="border hairline rounded-md overflow-hidden bg-surface"
          style={{ height: 440 }}
        >
          <ThreeDMap address={address} />
        </div>
        <div className="text-[11px] text-textDim mt-2">
          Imagery: Google Photorealistic 3D Tiles. Click-and-drag to orbit, scroll to zoom.
        </div>
      </section>
    </div>
  );
}
