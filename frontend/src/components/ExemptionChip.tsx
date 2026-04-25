import { useEffect, useState } from 'react';
import { doerApi, type ExemptionCheck, type ExemptionRequest } from '../lib/api';

/**
 * Inline exemption chip — warm palette, neutral when unknown so we never
 * imply "not exempt" when the user hasn't provided capacity/footprint.
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
    tone = { c: 'var(--good)', bg: 'var(--sage-soft, #eaf2e7)', label: 'Exempt' };
    detail = result.reason || '';
  } else if (result.is_exempt === false) {
    tone = { c: 'var(--text-mid)', bg: 'var(--surface-alt)', label: 'Not exempt' };
    detail = result.regulation_reference;
  } else {
    tone = {
      c: 'var(--text-dim)',
      bg: 'var(--surface-alt)',
      label: 'Add size to check exemption',
    };
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
        borderRadius: 999,
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
        <span style={{ color: 'var(--text-mid)', fontWeight: 400 }}>· {detail}</span>
      )}
    </span>
  );
}
