// Spec: FRONTEND_DESIGN.md — Design Tokens
import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0b1326',
          'container-lowest': '#060e20',
          'container-low': '#131b2e',
          container: '#171f33',
          'container-high': '#222a3d',
          'container-highest': '#2d3449',
          variant: '#2d3449',
          bright: '#31394d',
        },
        primary: {
          DEFAULT: '#89ceff',
          container: '#0ea5e9',
        },
        secondary: {
          DEFAULT: '#d0bcff',
          container: '#571bc1',
        },
        tertiary: {
          DEFAULT: '#4edea3',
          container: '#00b17b',
        },
        error: {
          DEFAULT: '#ffb4ab',
          container: '#93000a',
        },
        warning: '#f59e0b',
        'on-surface': '#dae2fd',
        'on-surface-variant': '#bec8d2',
        'on-background': '#dae2fd',
        'on-primary': '#00344d',
        'on-secondary': '#3c0091',
        'on-error': '#690005',
        outline: '#88929b',
        'outline-variant': '#3e4850',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        xs: '2px',
        sm: '4px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      spacing: {
        'module-gap': '3.5rem',
      },
      boxShadow: {
        'neural-glow': '0 0 40px rgba(14, 165, 233, 0.08)',
        'ai-glow': '0 0 20px rgba(87, 27, 193, 0.3)',
      },
    },
  },
  plugins: [],
} satisfies Config;
