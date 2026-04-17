import { useState } from 'react';
import type {
  DoerAdoptionDetail,
  DoerAdoptionStatus,
  DoerProjectType,
  DoerSafeHarbor,
  DoerSeverity,
  DoerStatusResponse,
} from '../lib/api';
import { IconArrowUpRight } from './Icon';

interface Props {
  status: DoerStatusResponse;
}

const STATUS_TONE: Record<
  DoerAdoptionStatus,
  { c: string; bg: string; label: string }
> = {
  adopted: { c: '#1f8a3d', bg: '#e4f3e7', label: 'Adopted' },
  in_progress: { c: '#b6781c', bg: '#fbecd6', label: 'In progress' },
  not_started: { c: '#c0392b', bg: '#f9e3df', label: 'Not started' },
  unknown: { c: '#8a8a8a', bg: '#f1f2f4', label: 'Unknown' },
};

const SAFE_HARBOR_TONE: Record<DoerSafeHarbor, { c: string; label: string }> = {
  safe: { c: '#1f8a3d', label: 'Safe harbor' },
  at_risk: { c: '#c0392b', label: 'At risk · Dover' },
  unknown: { c: '#8a8a8a', label: 'Unassessed' },
};

export default function DoerAlignmentStrip({ status }: Props) {
  const [openPt, setOpenPt] = useState<DoerProjectType | null>(null);

  return (
    <>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 12,
          marginBottom: 10,
        }}
      >
        <DoerCard
          label="Solar"
          detail={status.solar}
          deadline={status.deadline}
          daysRemaining={status.days_remaining}
          onOpen={() => setOpenPt('solar')}
        />
        <DoerCard
          label="BESS"
          detail={status.bess}
          deadline={status.deadline}
          daysRemaining={status.days_remaining}
          onOpen={() => setOpenPt('bess')}
        />
      </div>
      <div className="text-textDim" style={{ fontSize: 12, maxWidth: 620 }}>
        {status.other_project_types_note}
      </div>

      {openPt && (
        <DoerDrawer
          detail={openPt === 'solar' ? status.solar : status.bess}
          label={openPt === 'solar' ? 'Solar' : 'BESS'}
          onClose={() => setOpenPt(null)}
        />
      )}
    </>
  );
}

function DoerCard({
  label,
  detail,
  deadline,
  daysRemaining,
  onOpen,
}: {
  label: string;
  detail: DoerAdoptionDetail | null;
  deadline: string;
  daysRemaining: number;
  onOpen: () => void;
}) {
  if (!detail) {
    return (
      <div className="card" style={{ padding: '16px 18px' }}>
        <div className="label" style={{ marginBottom: 8 }}>
          {label} · DOER
        </div>
        <div className="text-textDim" style={{ fontSize: 13 }}>
          No DOER model loaded.
        </div>
      </div>
    );
  }

  const tone = STATUS_TONE[detail.adoption_status];
  const harbor = SAFE_HARBOR_TONE[detail.safe_harbor_status];
  const counts = detail.comparison?.deviation_counts;

  return (
    <button
      onClick={onOpen}
      className="card"
      style={{
        padding: '16px 18px',
        textAlign: 'left',
        cursor: 'pointer',
        transition: 'border-color 120ms ease',
        fontFamily: 'inherit',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
        }}
      >
        <div className="label">{label} · DOER model bylaw</div>
        <span
          style={{
            fontSize: 11,
            color: tone.c,
            background: tone.bg,
            padding: '3px 10px',
            borderRadius: 100,
            fontWeight: 500,
          }}
        >
          {tone.label}
        </span>
      </div>

      <div
        style={{
          fontSize: 20,
          fontWeight: 600,
          letterSpacing: -0.3,
          marginBottom: 6,
        }}
      >
        {detail.adopted_date
          ? `Adopted ${new Date(detail.adopted_date).toLocaleDateString()}`
          : `${daysRemaining} days to deadline`}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 12,
          color: '#525252',
        }}
      >
        {counts ? (
          <>
            <DeviationPill severity="major" count={counts.major} />
            <DeviationPill severity="moderate" count={counts.moderate} />
            <DeviationPill severity="minor" count={counts.minor} />
          </>
        ) : (
          <span className="text-textDim">Comparison deferred</span>
        )}
        <span
          style={{
            marginLeft: 'auto',
            color: harbor.c,
            fontSize: 11,
            fontWeight: 500,
          }}
        >
          {harbor.label}
        </span>
      </div>

      {!detail.adopted_date && (
        <div className="text-textDim" style={{ fontSize: 11, marginTop: 6 }}>
          Deadline {new Date(deadline).toLocaleDateString()}
        </div>
      )}
    </button>
  );
}

function DeviationPill({
  severity,
  count,
}: {
  severity: DoerSeverity;
  count: number;
}) {
  const tone =
    severity === 'major'
      ? { c: '#c0392b', bg: '#f9e3df' }
      : severity === 'moderate'
      ? { c: '#b6781c', bg: '#fbecd6' }
      : { c: '#525252', bg: '#f1f2f4' };
  if (count === 0) {
    return (
      <span className="text-textDim" style={{ fontSize: 11 }}>
        0 {severity}
      </span>
    );
  }
  return (
    <span
      style={{
        fontSize: 11,
        color: tone.c,
        background: tone.bg,
        padding: '3px 9px',
        borderRadius: 100,
        fontWeight: 500,
      }}
    >
      {count} {severity}
    </span>
  );
}

function DoerDrawer({
  detail,
  label,
  onClose,
}: {
  detail: DoerAdoptionDetail | null;
  label: string;
  onClose: () => void;
}) {
  if (!detail) return null;
  const c = detail.comparison;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15,15,15,0.32)',
        display: 'flex',
        justifyContent: 'flex-end',
        zIndex: 50,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(560px, 100%)',
          height: '100%',
          background: '#ffffff',
          borderLeft: '1px solid #e8eaed',
          padding: '28px 26px',
          overflowY: 'auto',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: 20,
          }}
        >
          <div>
            <div className="label" style={{ marginBottom: 4 }}>
              {label} · DOER model
            </div>
            <h2
              style={{
                fontSize: 20,
                fontWeight: 600,
                letterSpacing: -0.3,
                margin: 0,
              }}
            >
              {c?.comparison_available
                ? `${c.deviations.length} deviation${c.deviations.length === 1 ? '' : 's'} from DOER model`
                : 'Comparison not available'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-textDim"
            style={{
              background: 'none',
              border: 'none',
              fontSize: 22,
              lineHeight: 1,
              cursor: 'pointer',
            }}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <Meta label="Adoption status" value={STATUS_TONE[detail.adoption_status].label} />
        {detail.adopted_date && (
          <Meta label="Adopted" value={new Date(detail.adopted_date).toLocaleDateString()} />
        )}
        {detail.town_meeting_article && (
          <Meta label="Town meeting article" value={detail.town_meeting_article} />
        )}
        <Meta label="DOER version compared" value={detail.doer_version_ref || '—'} />
        <Meta label="Safe harbor" value={SAFE_HARBOR_TONE[detail.safe_harbor_status].label} />
        <Meta
          label="Source"
          value={
            <a
              href={detail.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-accent"
              style={{
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              {detail.source_type.replace(/_/g, ' ')}
              <IconArrowUpRight size={11} />
            </a>
          }
        />

        {c?.reason_unavailable && (
          <div
            className="card"
            style={{ padding: '12px 14px', fontSize: 13, color: '#525252', marginTop: 16 }}
          >
            {c.reason_unavailable}
          </div>
        )}

        {c?.comparison_available && c.deviations.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 20 }}>
            {c.deviations.map((d, i) => (
              <DeviationRow key={i} d={d} />
            ))}
          </div>
        )}

        {c?.comparison_available && c.deviations.length === 0 && (
          <div
            className="card"
            style={{ padding: '12px 14px', fontSize: 13, color: '#525252', marginTop: 16 }}
          >
            No deviations — town bylaw aligns with the DOER model.
          </div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div className="label" style={{ marginBottom: 3 }}>
        {label}
      </div>
      <div style={{ fontSize: 13 }}>{value}</div>
    </div>
  );
}

function DeviationRow({ d }: { d: import('../lib/api').DoerDeviation }) {
  const tone =
    d.severity === 'major'
      ? { c: '#c0392b', bg: '#f9e3df' }
      : d.severity === 'moderate'
      ? { c: '#b6781c', bg: '#fbecd6' }
      : { c: '#525252', bg: '#f1f2f4' };
  return (
    <div className="card" style={{ padding: '12px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span
          style={{
            fontSize: 10,
            color: tone.c,
            background: tone.bg,
            padding: '2px 8px',
            borderRadius: 100,
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: 0.3,
          }}
        >
          {d.severity}
        </span>
        <span className="text-textDim" style={{ fontSize: 11 }}>
          {d.category.replace(/_/g, ' ')}
        </span>
        {d.dover_risk && (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: 10,
              color: '#c0392b',
              textTransform: 'uppercase',
              letterSpacing: 0.3,
              fontWeight: 500,
            }}
          >
            Dover risk
          </span>
        )}
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.55, marginBottom: 8 }}>{d.summary}</div>
      <div
        className="text-textDim"
        style={{
          fontSize: 11,
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          gap: '3px 12px',
        }}
      >
        <span>Tier</span>
        <span>{d.tier_context}</span>
        {d.town_value && (
          <>
            <span>Town</span>
            <span>{d.town_value}</span>
          </>
        )}
        {d.doer_value && (
          <>
            <span>DOER model</span>
            <span>{d.doer_value}</span>
          </>
        )}
      </div>
    </div>
  );
}
