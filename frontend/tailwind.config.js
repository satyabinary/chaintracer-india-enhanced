/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#070A10",
          900: "#0D1219",
          850: "#10151F",
          800: "#161D2B",
          700: "#1E2635",
          600: "#2A3344",
        },
        line: {
          700: "#232B3A",
          600: "#3A465C",
        },
        parchment: {
          100: "#E6E9EF",
          400: "#8792A6",
          500: "#6B7690",
        },
        brass: {
          400: "#D9A15E",
          500: "#C98A3E",
          600: "#A96F2C",
        },
        steel: {
          500: "#5B8DEF",
        },
        risk: {
          high: "#E5484D",
          "high-bg": "rgba(229,72,77,0.14)",
          med: "#F2A93B",
          "med-bg": "rgba(242,169,59,0.14)",
          low: "#4C9F70",
          "low-bg": "rgba(76,159,112,0.14)",
        },
        confirmed: {
          DEFAULT: "#2FA37D",
          bg: "rgba(47,163,125,0.14)",
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
