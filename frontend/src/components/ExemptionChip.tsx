import { useEffect, useState } from 'react';
import { doerApi, type ExemptionCheck, type ExemptionRequest } from '../lib/api';

/**
 * Inline exemption chip for the parcel report — modern SaaS palette.
 * Returns `is_exempt=null` is rendered neutrally so we never claim
 * "not exempt" when the user hasn't provided capacity/footprint.
 */
export default function ExemptionChip({ req }: { req: ExemptionRequest }) {
  const [result, setResult] = useState<ExemptionCheck | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    doerApi
      .checkExemption(req)
      .then((r) => {
        if (!cancelled) setResult(r);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [JSON.stringify(req)]);

  if (err) return null;
  if (!result) return null;

  let tone: { c: string; bg: string; label: string };
  let detail: string;
  if (result.is_exempt === true) {
    tone = { c: '#1f8a3d', bg: '#e4f3e7', label: 'Exempt' };
    detail = result.reason || '';
  } else if (result.is_exempt === false) {
    tone = { c: '#525252', bg: '#f1f2f4', label: 'Not exempt' };
    detail = result.regulation_reference;
  } else {
    tone = { c: '#8a8a8a', bg: '#f1f2f4', label: 'Add size to check exemption' };
    detail = (result.missing_fields || []).join(', ');
  }

  return (
    <span
      title={detail || undefined}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '5px 12px',
        background: tone.bg,
        color: tone.c,
        borderRadius: 100,
        fontSize: 12,
        fontWeight: 500,
        letterSpacing: 0.1,
      }}
    >
      <span
        aria-hidden="true"
        style={{ width: 6, height: 6, borderRadius: 100, background: tone.c }}
      />
      {tone.label}
      {detail && result.is_exempt === true && (
        <span style={{ color: '#525252', fontWeight: 400 }}>· {detail}</span>
      )}
    </span>
  );
}
