/* eslint-disable @next/next/no-page-custom-font */
import "katex/dist/katex.min.css";
import type { Metadata } from "next";
import { Space_Grotesk, Lexend } from "next/font/google"; // For Student & Admin
import Script from "next/script";
import "./globals.css";
import { MathJaxContext } from "better-react-mathjax";
import { ThemeProvider } from "@/hooks/useTheme";

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: '--font-space-grotesk' });
const lexend = Lexend({ subsets: ["latin"], variable: '--font-lexend' });

const mathJaxConfig = {
  loader: { load: ["input/tex", "output/chtml", "[tex]/ams"] },
  tex: {
    packages: { "[+]": ["ams"] },
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  chtml: {
    scale: 1.5,
    matchFontHeight: true,
  },
};

export const metadata: Metadata = {
  title: "uask.ai | Master Math & Physics with AI",
  description: "Snap a photo, get step-by-step guidance, and master complex concepts in seconds.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
      <html lang="en" data-theme="light" className={`${spaceGrotesk.variable} ${lexend.variable} light`}>
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
        <Script id="tailwind-config" strategy="beforeInteractive">
          {`
            window.tailwind = window.tailwind || {};
            window.tailwind.config = {
              darkMode: "class",
              theme: {
                  extend: {
                      colors: {
                          "primary": "#2563EB",
                          "electric-blue": "#2563EB",
                          "navy": "#1E293B",
                          "off-white": "#FAFAFA",
                          "light-gray": "#F8FAFC",
                          "math-blue": "#1E293B",
                          "accent": "#0ea5e9",
                          "background-light": "#f6f6f8",
                          "background-dark": "#0f1115",
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
                          "neon-amber": "#f59e0b"
                      },
                      fontFamily: {
                          "display": ["var(--font-space-grotesk)", "sans-serif"],
                          "admin": ["var(--font-lexend)", "sans-serif"]
                      },
                      borderRadius: {
                          "DEFAULT": "0.25rem",
                          "lg": "0.5rem",
                          "xl": "0.75rem",
                          "full": "9999px"
                      },
                  },
              },
            }
          `}
        </Script>
        <Script src="https://cdn.tailwindcss.com?plugins=forms,container-queries" strategy="beforeInteractive" />
        <style>{`
          .material-symbols-outlined {
              font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
          }
        `}</style>
      </head>
      <body className="bg-background-light dark:bg-background-dark text-[#111318] dark:text-white transition-colors duration-200">
        <ThemeProvider>
          <MathJaxContext config={mathJaxConfig}>
            {children}
          </MathJaxContext>
        </ThemeProvider>
      </body>
    </html>
  );
}
