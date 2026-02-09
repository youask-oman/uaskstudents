import typography from "@tailwindcss/typography";
import type { Config } from "tailwindcss";

const config: Config = {
    darkMode: "class",
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                "primary": "#2563EB",
                "background-light": "#f6f6f8",
                "background-dark": "#101622",
                "electric-blue": "#2563EB",
                "navy": "#1E293B",
                // Ported from layout.tsx script
                "off-white": "#FAFAFA",
                "light-gray": "#F8FAFC",
                "math-blue": "#1E293B",
                "accent": "#0ea5e9",
                "surface-dark": "#1a1d23",
                "card-dark": "#121212",
                "border-dark": "#2d333b",
                "latex-cyan": "#a5f3fc",
                "admin-primary": "#0ea5e9",
                "admin-bg-dark": "#0F172A",
                "panel-dark": "#1E293B",
                "accent-cyan": "#22d3ee",
                "accent-emerald": "#10b981",
                "accent-purple": "#a855f7",
                "accent-amber": "#f59e0b",
                "primary-hover": "#2563eb",
                "neon-green": "#22c55e",
                "neon-amber": "#f59e0b",
                "chalkboard": "#2c2f33",
                "chalk": "#ffffff",
                "chalk-cyan": "#a5f3fc"
            },
            fontFamily: {
                "display": ["var(--font-space-grotesk)", "sans-serif"],
                "math": ["Times New Roman", "serif"],
                "admin": ["var(--font-lexend)", "sans-serif"],
                "architects": ["'Architects Daughter'", "cursive"],
                "hand": ["'Patrick Hand'", "cursive"],
                "sketch": ["'Caveat'", "cursive"],
                "gochi": ["'Gochi Hand'", "cursive"]
            },
        },
    },
    plugins: [typography],
};

export default config;
