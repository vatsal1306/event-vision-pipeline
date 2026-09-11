import Link from 'next/link';
import { Logo } from '@/components/shared/logo';

export default function MarketingLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation */}
      <header className="w-full border-b border-ink/10 sticky top-0 z-50 bg-canvas/80 backdrop-blur-md">
        <nav className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <Link href="/" aria-label="SpotMe home">
            <Logo size="md" />
          </Link>

          <div className="flex items-center gap-3">
            <Link
              href="/register"
              className="text-sm font-medium bg-ink text-canvas rounded-button px-5 py-2 hover:bg-ink/90 transition-colors"
            >
              Create Account
            </Link>
            <Link
              href="/login"
              className="text-sm font-medium text-ink/70 hover:text-ink transition-colors px-4 py-2"
            >
              Log In
            </Link>
          </div>
        </nav>
      </header>

      {/* Page Content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-ink/10">
        <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <Logo size="sm" />
            <span className="text-sm text-ink/40">
              ©️ {new Date().getFullYear()} HPK AI Labs. All rights reserved
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
