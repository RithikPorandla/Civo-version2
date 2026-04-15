import { useState } from 'react';
import type { CriterionScore } from '../lib/api';
import { CriterionPill } from './StatusPill';

const fillColor = (status: CriterionScore['status']) => {
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

export function CriterionRow({ idx, criterion }: { idx: number; criterion: CriterionScore }) {
  const [open, setOpen] = useState(false);
  const pct = (criterion.raw_score / 10) * 100;
  return (
    <div className="border-b hairline py-7">
      <button
        className="w-full flex items-start gap-6 text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="w-10 pt-1 shrink-0">
          <span className="display italic text-textDim text-[20px]">
            {idx.toString().padStart(2, '0')}
          </span>
        </div>
        <div className="flex-1">
          <div className="flex items-start justify-between gap-6 mb-4">
            <div>
              <div className="display text-displayXS text-text">{criterion.name}</div>
              <div className="eyebrow mt-1">Weight {Math.round(criterion.weight * 100)}%</div>
            </div>
            <div className="flex items-center gap-4 shrink-0">
              <CriterionPill status={criterion.status} />
              <div className="text-right">
                <div className="display text-displayS">{criterion.raw_score.toFixed(1)}</div>
                <div className="eyebrow">of 10</div>
              </div>
            </div>
          </div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${pct}%`, background: fillColor(criterion.status) }} />
          </div>
          {open && (
            <div className="mt-6 space-y-4">
              <p className="text-[15px] leading-[1.7] text-textMid max-w-3xl">{criterion.finding}</p>
              <div className="flex flex-wrap gap-2">
                {criterion.citations.map((c, i) => (
                  <a
                    key={i}
                    href={c.url || '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="chip hover:border-borderHover"
                  >
                    <span className="text-text">{c.dataset}</span>
                    {c.detail && <span>· {c.detail}</span>}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </button>
    </div>
  );
}
