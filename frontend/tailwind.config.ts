import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "Oxygen",
          "Ubuntu",
          "Cantarell",
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          '"JetBrains Mono"',
          '"Geist Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        canvas: "#0B0F19",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
          subtle: "#141C2E",
          hover: "#1A253D",
        },
        border: {
          DEFAULT: "var(--border)",
          subtle: "#1E293B",
          highlight: "#334155",
        },
        primary: {
          DEFAULT: "#2563EB", // Electric Royal Blue
          hover: "#1D4ED8",
          foreground: "#FFFFFF",
          subtle: "rgba(37, 99, 235, 0.12)",
        },
        accent: {
          DEFAULT: "#10B981", // Emerald Cashflow
          foreground: "#FFFFFF",
          subtle: "rgba(16, 185, 129, 0.12)",
        },
        expense: {
          DEFAULT: "#F43F5E", // Rose / Outflow
          foreground: "#FFFFFF",
          subtle: "rgba(244, 63, 94, 0.12)",
        },
        warning: {
          DEFAULT: "#F59E0B",
          subtle: "rgba(245, 158, 11, 0.12)",
        },
        info: {
          DEFAULT: "#0284C7",
          subtle: "rgba(2, 132, 199, 0.12)",
        },
        muted: {
          DEFAULT: "#64748B",
          foreground: "#94A3B8",
          subtle: "#1E293B",
        },
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(0, 0, 0, 0.25)",
        card: "0 4px 20px -2px rgba(0, 0, 0, 0.35)",
        glow: "0 0 20px -5px rgba(37, 99, 235, 0.25)",
      },
    },
  },
  plugins: [],
};

export default config;
