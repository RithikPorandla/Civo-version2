/**
 * Minimal line-icon set, 18px default, 1.5 stroke.
 * Only the icons we actually use on the dashboard.
 */

type IconProps = {
  size?: number;
  className?: string;
};

const base = (size = 18) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
});

export const IconSidebar = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M9 4v16" />
  </svg>
);

export const IconStar = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <polygon points="12 2 15 9 22 9.5 17 14.5 18.5 21 12 17.5 5.5 21 7 14.5 2 9.5 9 9" />
  </svg>
);

export const IconSearch = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-3-3" />
  </svg>
);

export const IconBell = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M6 8a6 6 0 0 1 12 0v5l1.5 3h-15L6 13V8z" />
    <path d="M10 19a2 2 0 0 0 4 0" />
  </svg>
);

export const IconClock = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const IconSun = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.5 1.5M17.6 17.6l1.5 1.5M4.9 19.1l1.5-1.5M17.6 6.4l1.5-1.5" />
  </svg>
);

export const IconHome = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M4 11l8-7 8 7" />
    <path d="M6 10v10h12V10" />
  </svg>
);

export const IconMap = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <polygon points="3 6 9 4 15 6 21 4 21 18 15 20 9 18 3 20" />
    <path d="M9 4v14M15 6v14" />
  </svg>
);

export const IconBuilding = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <rect x="5" y="3" width="14" height="18" rx="1" />
    <path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2" />
  </svg>
);

export const IconChart = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </svg>
);

export const IconFolder = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
  </svg>
);

export const IconUser = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 20c1-4 5-6 8-6s7 2 8 6" />
  </svg>
);

export const IconBook = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M4 4h10a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4V4z" />
    <path d="M4 4v12a4 4 0 0 0 4 4" />
  </svg>
);

export const IconChevronDown = ({ size = 14, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

export const IconChevronRight = ({ size = 14, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <polyline points="9 6 15 12 9 18" />
  </svg>
);

export const IconArrowUpRight = ({ size = 12, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M7 17L17 7" />
    <path d="M8 7h9v9" />
  </svg>
);

export const IconArrowDownRight = ({ size = 12, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <path d="M7 7l10 10" />
    <path d="M17 8v9H8" />
  </svg>
);

export const IconLayers = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </svg>
);

export const IconPlus = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

export const IconFilter = ({ size, className }: IconProps) => (
  <svg {...base(size)} className={className}>
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
  </svg>
);
