import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0d1117',
          secondary: '#161b22',
          tertiary: '#21262d',
        },
        border: {
          DEFAULT: '#30363d',
          subtle: '#21262d',
        },
        text: {
          primary: '#e6edf3',
          secondary: '#7d8590',
          muted: '#484f58',
        },
        accent: {
          yellow: '#ecad0a',
          blue: '#209dd7',
          purple: '#753991',
        },
        price: {
          up: '#3fb950',
          down: '#f85149',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
