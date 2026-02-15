import "katex/dist/katex.min.css";
import type { Metadata } from "next";

import "./globals.css";
import { ThemeProvider } from "@/hooks/useTheme";
import { AuthProvider } from "@/contexts/AuthContext";
import { ToastProvider } from "@/components/ui/ToastProvider";
import AnalyticsCookieBanner from "@/components/AnalyticsCookieBanner";
import TermsAcceptanceGate from "@/components/TermsAcceptanceGate";

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
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning className="min-h-screen bg-background-light dark:bg-background-dark text-[#111318] dark:text-white transition-colors duration-200">
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              {children}
              <TermsAcceptanceGate />
              <AnalyticsCookieBanner />
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>

        {/* SVG Filters for hand-drawn effects */}
        <svg style={{ position: 'absolute', width: 0, height: 0 }} aria-hidden="true" focusable="false">
          <filter id="roughpaper" x="0%" y="0%" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="5" result="noise" />
            <feDiffuseLighting in="noise" lightingColor="#ffffff" surfaceScale="2" result="diffuse">
              <feDistantLight azimuth="45" elevation="60" />
            </feDiffuseLighting>
            <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.15 0" in="diffuse" result="textureAlpha" />
            <feComposite operator="in" in="diffuse" in2="textureAlpha" result="subtleTexture" />
            <feBlend mode="multiply" in="subtleTexture" in2="SourceGraphic" />
          </filter>
          <filter id="handWobble">
            <feTurbulence type="fractalNoise" baseFrequency="0.005" numOctaves="2" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="3" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </svg>
      </body>
    </html>
  );
}
