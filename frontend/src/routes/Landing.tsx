import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';

export default function Landing() {
  const [address, setAddress] = useState('Kendall Square, Cambridge, MA 02142');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const env = await api.score(address);
      nav(`/report/${env.report_id}`);
    } catch (e: unknown) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-8 pt-rhythm-lg pb-rhythm">
      <div className="eyebrow mb-3">Score an address</div>
      <h1 className="display text-displayM mb-8">MA EEA Site Suitability</h1>
      <form
        onSubmit={submit}
        className="flex items-stretch gap-3 border hairline rounded-pill bg-surface p-2 pl-5"
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
    </div>
  );
}
