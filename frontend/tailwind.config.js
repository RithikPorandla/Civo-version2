/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Earth & Paper — the primary brand system
        bg: '#ffffff',
        surface: '#fbfaf6',
        surfaceAlt: '#f3efe5',
        surfaceWarm: '#efe9dc',

        // Tinted tiles (dashboard stat cards)
        tilePaper: '#f7f3ea',
        tileStone: '#eef0ee',
        tileSage: '#e8ece2',
        tileRust: '#f3e7df',

        // Borders — warm hairline
        border: '#e6e0d2',
        borderSoft: '#ede8da',
        borderHover: '#d7cfba',

        // Text hierarchy
        text: '#1a1a1a',
        textMid: '#6b6b6b',
        textDim: '#9a9489',
        textFaint: '#c7c0af',

        // Accent — weathered linen / warm brown
        accent: '#8b7355',
        accentDeep: '#3d3126',
        accentSoft: '#f3efe5',

        // Secondary tones from the system
        rust: '#a85a4a',
        rustSoft: '#f5e8e4',
        sage: '#6b7e5a',
        sageSoft: '#eaf2e7',
        gold: '#c08a3e',
        goldSoft: '#f7efe0',

        // Status — aligned to Earth & Paper
        good: '#4a7c4f',
        goodSoft: '#eaf2e7',
        warn: '#c08a3e',
        warnSoft: '#f7efe0',
        bad: '#a85a4a',
        badSoft: '#f5e8e4',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
      },
      fontSize: {
        'num-xl': ['36px', { lineHeight: '1.0', letterSpacing: '-0.03em', fontWeight: '400' }],
        'num-lg': ['28px', { lineHeight: '1.05', letterSpacing: '-0.02em', fontWeight: '400' }],
        'display-xl': ['clamp(52px, 7.4vw, 116px)', { lineHeight: '0.96', letterSpacing: '-0.035em', fontWeight: '400' }],
        'display-lg': ['40px', { lineHeight: '1.05', letterSpacing: '-0.025em', fontWeight: '400' }],
        'display-md': ['34px', { lineHeight: '1.05', letterSpacing: '-0.018em', fontWeight: '400' }],
      },
      borderRadius: {
        card: '14px',
        pill: '999px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(26, 26, 26, 0.04)',
        lift: '0 10px 30px rgba(0, 0, 0, 0.08)',
        cta: '0 1px 0 rgba(0,0,0,0.08), 0 4px 16px rgba(26,26,26,0.18)',
      },
      letterSpacing: {
        eyebrow: '0.15em',
        display: '-0.035em',
      },
    },
  },
  plugins: [],
};
