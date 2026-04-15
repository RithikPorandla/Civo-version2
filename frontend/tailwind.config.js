/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#fafaf7',
        surface: '#ffffff',
        surfaceAlt: '#f5f2ea',
        accentSoft: '#f0ede5',
        border: '#ececec',
        borderHover: '#d4d1c7',
        text: '#1a1a1a',
        textMid: '#6b6b6b',
        textDim: '#9b9b9b',
        textFaint: '#b8b8b8',
        accent: '#8b7355',
        good: '#4a7c4f',
        goodSoft: '#eaf2e7',
        warn: '#c08a3e',
        warnSoft: '#f7efe0',
        bad: '#a85a4a',
        badSoft: '#f5e8e4',
      },
      fontFamily: {
        display: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        displayXL: ['68px', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
        displayL: ['54px', { lineHeight: '1.05', letterSpacing: '-0.015em' }],
        displayM: ['40px', { lineHeight: '1.15', letterSpacing: '-0.01em' }],
        displayS: ['32px', { lineHeight: '1.2', letterSpacing: '-0.008em' }],
        displayXS: ['26px', { lineHeight: '1.2', letterSpacing: '-0.005em' }],
        hero: ['96px', { lineHeight: '0.9', letterSpacing: '-0.04em' }],
      },
      borderRadius: {
        sm: '8px',
        md: '14px',
        lg: '20px',
        pill: '100px',
      },
      spacing: {
        'rhythm-sm': '40px',
        'rhythm': '56px',
        'rhythm-lg': '80px',
      },
    },
  },
  plugins: [],
};
