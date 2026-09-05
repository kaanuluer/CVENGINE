/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#3B82F6",
        secondary: "#8B5CF6",
        success: "#16A34A",
        warning: "#D97706",
        danger: "#DC2626",
        surface: "#FFFFFF",
        ink: "#111827",
        muted: "#6B7280",
        canvas: "#F5F5F7",
        line: "#E5E7EB",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "SF Pro Text", "Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "JetBrains Mono", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(17,24,39,0.06), 0 8px 24px rgba(17,24,39,0.04)",
      },
      borderRadius: {
        card: "12px",
      },
    },
  },
  plugins: [],
};
