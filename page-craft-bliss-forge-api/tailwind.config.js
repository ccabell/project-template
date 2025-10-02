/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/frontend/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'allergan': '#0066CC',
        'galderma': '#E31E24',
        'revance': '#00A651',
        'merz': '#8B1538',
        'prollenium': '#FF6B35'
      }
    },
  },
  plugins: [],
}