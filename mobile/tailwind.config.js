/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          dark: '#08090D',
          sidebar: '#0C0E14',
          surface: '#12151E',
          card: '#161A26',
        },
        border: {
          subtle: 'rgba(255, 255, 255, 0.08)',
          glow: 'rgba(124, 58, 237, 0.3)',
        },
        accent: {
          violet: '#7C3AED',
          turquoise: '#06B6D4',
          gold: '#F59E0B',
          green: '#10B981',
          red: '#EF4444',
        }
      }
    },
  },
  plugins: [],
}
