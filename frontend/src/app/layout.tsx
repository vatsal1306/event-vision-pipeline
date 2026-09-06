import type { Metadata, Viewport } from "next";
import { Sofia_Sans } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/query-provider";
import { MSWProvider } from "@/components/providers/msw-provider";
import { Toaster } from "@/components/ui/sonner";

const sofiaSans = Sofia_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sofia-sans",
});

export const metadata: Metadata = {
  title: "SpotMe",
  description: "Find yourself in every shot",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${sofiaSans.variable} font-sans antialiased min-h-screen bg-canvas text-ink`}>
        <MSWProvider>
          <QueryProvider>
            {children}
          </QueryProvider>
        </MSWProvider>
        <Toaster />
      </body>
    </html>
  );
}
