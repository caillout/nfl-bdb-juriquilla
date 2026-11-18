/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Paleta de día de partido (sin logos ni marcas)
        nfl: {
          navy: '#013369',
          red: '#D50A0A',
          night: '#061325',
          field: '#1d5e34',
          gold: '#FFB612',
        },
      },
      fontFamily: {
        // Fuentes del sistema, sin descargas externas
        titular: ['"Arial Narrow"', '"Roboto Condensed"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
