import Link from 'next/link';
import { Logo } from '@/components/shared/logo';

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-muted/30">
      <header className="absolute top-0 w-full p-6">
        <Link href="/" aria-label="SpotMe Home" className="inline-block transition-transform hover:scale-105">
          <Logo size="md" />
        </Link>
      </header>
      <main className="flex-1 flex flex-col items-center justify-center p-6 mt-16 md:mt-0">
        <div className="w-full max-w-[440px] bg-card text-card-foreground shadow-sm border border-border/50 rounded-2xl p-8 md:p-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {children}
        </div>
      </main>
      <footer className="py-6 text-center text-sm text-muted-foreground">
        ©️ {new Date().getFullYear()} HPK AI Labs. All rights reserved
      </footer>
    </div>
  );
}
