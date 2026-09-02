import type { Metadata } from "next";
import { Sofia_Sans } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/query-provider";

const sofiaSans = Sofia_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sofia-sans",
});

export const metadata: Metadata = {
  title: "SpotMe",
  description: "Find yourself in every shot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${sofiaSans.variable} font-sans antialiased min-h-screen bg-canvas text-ink`}>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
