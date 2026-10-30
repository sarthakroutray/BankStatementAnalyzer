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
          "sans-serif",
        ],
        mono: [
          "var(--font-mono)",
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },
      colors: {
        // Hyper-Saturated Fluid Tokens
        "cyber-yellow": "#FDE047", // The single shout color (flat, never gradient)
        onyx: "#0A0A0A",          // Main page background / "void"
        charcoal: "#171717",      // Secondary dark panels
        "deep-gray": "#262626",   // UI elements inside the void
        white: "#FFFFFF",
        // Semantic data colors (sparingly for credit/debit and trend chips)
        success: "#4ADE80",
        danger: "#F87171",
        // Compatibility variables
        background: "var(--background)",
        foreground: "var(--foreground)",
        border: "var(--border)",
      },
      borderRadius: {
        "panel": "32px",
        "liquid-hero": "120px",
        "liquid-subtle": "40px",
      },
      boxShadow: {
        "glass": "0 20px 50px -10px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.12)",
        "glass-yellow": "0 20px 50px -10px rgba(253, 224, 71, 0.25), 0 0 0 1px rgba(253, 224, 71, 0.3)",
        "yellow-glow": "0 0 35px -5px rgba(253, 224, 71, 0.4)",
        "subtle": "0 2px 8px 0 rgba(0, 0, 0, 0.3)",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-8px)" },
        },
        "float-slow": {
          "0%, 100%": { transform: "translateY(0px) rotate(0deg)" },
          "50%": { transform: "translateY(-12px) rotate(1deg)" },
        },
        ticker: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "0.6", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.05)" },
        },
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        "float-slow": "float-slow 8s ease-in-out infinite",
        ticker: "ticker 25s linear infinite",
        "pulse-glow": "pulse-glow 3s ease-in-out infinite",
      },
      transitionTimingFunction: {
        "fluid": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
