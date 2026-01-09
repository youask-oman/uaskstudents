import type { Metadata } from "next";
import { Space_Grotesk, Lexend } from "next/font/google"; // For Student & Admin
import "./globals.css";

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: '--font-space-grotesk' });
const lexend = Lexend({ subsets: ["latin"], variable: '--font-lexend' });

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
    <html lang="en" className={`${spaceGrotesk.variable} ${lexend.variable} light`}>
      <head>
        {/* Material Symbols */}
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />

        {/* KaTeX for Math Rendering */}
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossOrigin="anonymous" />
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossOrigin="anonymous"></script>
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js" integrity="sha384-+VBxd3r6XgURycqtZ117nYw44OOcIax56Z4dCRWbxyPt0Koah1uHoK0o4+/RRE05" crossOrigin="anonymous"></script>

        {/* Tailwind CDN - Must load first */}
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>

        {/* Tailwind Config - Loads after CDN to configure it */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              tailwind.config = {
                darkMode: "class",
                theme: {
                    extend: {
                        colors: {
                            "primary": "#135bec", // Student Primary
                            "background-light": "#f6f6f8",
                            "background-dark": "#0a0c10", // Updated for Workspace deep dark
                            
                            // Workspace specialized dark colors
                            "surface-dark": "#161b22",
                            "border-dark": "#282e39",

                            // Admin Colors
                            "admin-primary": "#0ea5e9",
                            "admin-bg-dark": "#0F172A",
                            "panel-dark": "#1E293B",
                            "accent-cyan": "#22d3ee",
                            "accent-emerald": "#10b981",
                            "accent-purple": "#a855f7",
                            "accent-amber": "#f59e0b",
                            
                            // Admin Content Management Specifics
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
            `
          }}
        />

        <style>{`
          .material-symbols-outlined {
              font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
          }
        `}</style>
      </head>
      <body className="bg-background-light dark:bg-background-dark text-[#111318] dark:text-white transition-colors duration-200">
        {children}
      </body>
    </html>
  );
}
