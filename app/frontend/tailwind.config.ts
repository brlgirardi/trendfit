import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Design system dark theme (Glassnode-like)
        'bg-primary': '#0D0D0D',
        'bg-panel': '#1A1A1A',
        'border-line': '#2A2A2A',
        bull: '#00FF88',
        bear: '#FF3B3B',
        neutral: '#FFB800',
        'very-bad': '#FF0000',
        'text-primary': '#E8E8E8',
        'text-secondary': '#888888',
        // Postura -> cor
        'posture-acumular': '#16a34a',
        'posture-neutro': '#3b82f6',
        'posture-cauteloso': '#f59e0b',
        'posture-defensivo': '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}

export default config
