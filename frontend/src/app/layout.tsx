import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "@fontsource/nunito/300.css";
import "@fontsource/nunito/400.css";
import "@fontsource/nunito/600.css";
import "@fontsource/jetbrains-mono/400.css";
import Script from "next/script";
import "./globals.css";
import Providers from "@/components/providers";
import ThemeToggle from "@/components/theme-toggle";
import WatchTowerLogo from "@/components/watchtower-logo";
import { typeMdSemibold } from "@/lib/style-maps";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "WatchTower AI",
  description:
    "Flight radar for AI services — detect Claude / GPT / Gemini outages before the official status page does.",
  icons: {
    icon: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      data-scroll-behavior="smooth"
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col font-sans">
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var d=document.documentElement;var t=localStorage.getItem('theme');var dark;if(t==='dark')dark=true;else if(t==='light')dark=false;else dark=false;d.classList.toggle('dark',dark);d.style.colorScheme=dark?'dark':'light';}catch(e){}})();`,
          }}
        />
        <Providers>
          <nav className="fixed top-0 left-0 right-0 z-50 border-b border-zinc-200 dark:border-zinc-800 bg-[var(--background)]">
            <div className="max-w-[1180px] mx-auto px-4 md:px-8 py-4 flex items-center justify-between">
              <a
                href="/"
                className="flex items-center gap-2.5 text-zinc-700 dark:text-zinc-300 hover:text-[var(--accent)] transition-colors"
              >
                <WatchTowerLogo size={28} />
                <span style={typeMdSemibold} className="tracking-tight">
                  WatchTower AI
                </span>
              </a>
              <ThemeToggle />
            </div>
          </nav>
          <main className="flex-1 pt-16">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
