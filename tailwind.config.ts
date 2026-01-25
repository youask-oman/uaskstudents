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
                "primary": "#135bec",
                "background-light": "#f6f6f8",
                "background-dark": "#101622",
                "electric-blue": "#135bec",
                "navy": "#111318",
            },
            fontFamily: {
                "display": ["Lexend", "sans-serif"],
                "math": ["Times New Roman", "serif"],
            },
        },
    },
    plugins: [typography],
};

export default config;
