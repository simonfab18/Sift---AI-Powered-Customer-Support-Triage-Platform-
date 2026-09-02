import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "Space Grotesk", "ui-sans-serif", "system-ui"],
        sans: ["var(--font-sans)", "Inter", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-mono)", "JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        brand: {
          50: "#f4f5ff",
          100: "#e6e8ff",
          600: "#4f46e5",
          700: "#4338ca",
          900: "#17134f",
        },
        urgency: {
          critical: "#8f8aa8",
          high: "#aaa4be",
          medium: "#b8b3c7",
          low: "#d9d5df",
        },
      },
    },
  },
  plugins: [],
};

export default config;


