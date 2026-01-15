/** @type {import('tailwindcss').Config} */
module.exports = {
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
                // Keeping legacy matches just in case, but mapped to new palette
                "electric-blue": "#135bec",
                "navy": "#111318",
            },
            fontFamily: {
                "display": ["Lexend", "sans-serif"],
                "math": ["Times New Roman", "serif"]
            },
        },
    },
    plugins: [
        require('@tailwindcss/typography'),
    ],
};
