/** Tailwind config for the standalone CLI build.
 *  Source: web/src/input.css  →  Output: web/static/app.css
 *  Build:  npm run build:css   (or the tailwindcss standalone binary directly)
 *
 *  The dashboard's component styling is authored as plain CSS inside input.css,
 *  so utilities are optional. The per-metric palette is mirrored in
 *  web/static/js/palette.js (single source of truth for runtime coloring).
 */
module.exports = {
  content: ["./web/index.html", "./web/static/js/**/*.js"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0a0c0f",
        panel: "#11141a",
        coding: "#56c878",
        dsa: "#d0a83e",
        gym: "#9277cf",
        sleep: "#4391d6",
        deepwork: "#3bb3b3",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "SF Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
