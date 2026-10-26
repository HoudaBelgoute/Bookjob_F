/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: 'var(--navy-900)',
          800: 'var(--navy-800)',
          700: 'var(--navy-700)',
          600: 'var(--navy-600)',
        },
        primary: {
          DEFAULT: 'var(--primary)',
          hover: 'var(--primary-hover)',
          soft: 'var(--primary-soft)',
        },
        gold: { DEFAULT: 'var(--gold)', soft: 'var(--gold-soft)', ink: 'var(--gold-ink)' },
        success: { DEFAULT: 'var(--success)', soft: 'var(--success-soft)' },
        violet: { soft: 'var(--violet-soft)', ink: 'var(--violet-ink)' },
        ink: 'var(--ink)',
        muted: 'var(--muted)',
        faint: 'var(--faint)',
        line: 'var(--line)',
        surface: 'var(--surface)',
        chip: 'var(--chip)',
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      boxShadow: {
        card: '0 1px 2px rgba(15,36,68,.04), 0 1px 1px rgba(15,36,68,.03)',
        pop: '0 12px 32px rgba(15,36,68,.16)',
        fab: '0 10px 24px rgba(15,36,68,.35)',
      },
    },
  },
  plugins: [],
}
