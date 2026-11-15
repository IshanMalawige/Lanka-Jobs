export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"], display: ["'Space Grotesk'", "system-ui", "sans-serif"] },
      colors: {
        ink: "#14213d", paper: "#eef1f4", line: "#d5dbe3", teal: { DEFAULT: "#0e8a7d", dark: "#0a6c62" },
        amber: { DEFAULT: "#c98a0a" }, rose: { DEFAULT: "#b4414f" },
      },
    },
  },
  plugins: [],
};
