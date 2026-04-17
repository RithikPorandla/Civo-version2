/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Page + surfaces
        bg: '#f7f8fa',              // near-white page background
        surface: '#ffffff',          // cards / panels
        surfaceAlt: '#f1f2f4',       // hover / very subtle fills
        hover: '#f4f5f7',            // row hover

        // Borders — hairline
        border: '#e8eaed',
        borderHover: '#d7dae0',

        // Text hierarchy
        text: '#1a1a1a',
        textMid: '#525252',
        textDim: '#8a8a8a',
        textFaint: '#b8b8b8',

        // Accent — quiet indigo/slate for links and focus
        accent: '#2563eb',
        accentSoft: '#e8efff',

        // Pastel stat card fills (match the screenshot)
        pastelBlue: '#e3ebf5',
        pastelLavender: '#eeedf2',
        pastelMint: '#dbe8cc',
        pastelPeach: '#f8e8d6',

        // Status — kept muted
        good: '#1f8a3d',
        goodSoft: '#e4f3e7',
        warn: '#b6781c',
        warnSoft: '#fbecd6',
        bad: '#c0392b',
        badSoft: '#f9e3df',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'num-xl': ['36px', { lineHeight: '1.05', letterSpacing: '-0.02em', fontWeight: '600' }],
        'num-lg': ['28px', { lineHeight: '1.1', letterSpacing: '-0.01em', fontWeight: '600' }],
      },
      borderRadius: {
        card: '16px',
        pill: '100px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 15, 15, 0.04)',
      },
    },
  },
  plugins: [],
};
