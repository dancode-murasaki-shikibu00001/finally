/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0d1117',
        surface: '#161b22',
        'surface-2': '#1c2128',
        border: '#21262d',
        accent: '#ecad0a',
        blue: '#209dd7',
        purple: '#753991',
        green: '#3fb950',
        red: '#f85149',
        'text-primary': '#e6edf3',
        'text-muted': '#8b949e',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      },
      animation: {
        'flash-green': 'flashGreen 0.5s ease-out',
        'flash-red': 'flashRed 0.5s ease-out',
        'pulse-dot': 'pulseDot 2s ease-in-out infinite',
        'dots': 'dots 1.5s steps(3, end) infinite',
      },
    },
  },
  plugins: [],
}
