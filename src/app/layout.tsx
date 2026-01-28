/* eslint-disable @next/next/no-page-custom-font */
import "katex/dist/katex.min.css";
import type { Metadata } from "next";
import { Space_Grotesk, Lexend } from "next/font/google"; // For Student & Admin

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
    scale: 1.1,
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
    <html lang="en" suppressHydrationWarning className={`${spaceGrotesk.variable} ${lexend.variable}`}>
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
        <style>{`
          .material-symbols-outlined {
              font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
          }
        `}</style>
      </head>
      <body className="min-h-screen bg-background-light dark:bg-background-dark text-[#111318] dark:text-white transition-colors duration-200">
        <ThemeProvider>
          <MathJaxContext config={mathJaxConfig}>
            {children}
          </MathJaxContext>
        </ThemeProvider>
      </body>
    </html>
  );
}
