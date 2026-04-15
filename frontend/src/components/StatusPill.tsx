import type { Bucket, CriterionStatus } from '../lib/api';

const bucketStyles: Record<Bucket, string> = {
  SUITABLE: 'bg-goodSoft text-good border-good/20',
  'CONDITIONALLY SUITABLE': 'bg-warnSoft text-warn border-warn/20',
  CONSTRAINED: 'bg-badSoft text-bad border-bad/20',
};

const criterionStyles: Record<CriterionStatus, string> = {
  ok: 'bg-goodSoft text-good border-good/20',
  flagged: 'bg-warnSoft text-warn border-warn/20',
  ineligible: 'bg-badSoft text-bad border-bad/20',
  data_unavailable: 'bg-accentSoft text-textMid border-border',
};

const criterionLabels: Record<CriterionStatus, string> = {
  ok: 'Clear',
  flagged: 'Flagged',
  ineligible: 'Ineligible',
  data_unavailable: 'Data pending',
};

export function BucketPill({ bucket }: { bucket: Bucket }) {
  return (
    <span
      className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-pill border text-[13px] tracking-wide ${bucketStyles[bucket]}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {bucket}
    </span>
  );
}

export function CriterionPill({ status }: { status: CriterionStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-pill border text-[11px] ${criterionStyles[status]}`}
    >
      {criterionLabels[status]}
    </span>
  );
}
