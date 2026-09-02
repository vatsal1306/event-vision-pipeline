import Link from 'next/link';
import { Logo } from '@/components/shared/logo';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 text-center">
      <div className="mb-8">
        <Logo size="lg" />
      </div>
      <h1 className="text-4xl font-bold tracking-tight mb-4">404</h1>
      <p className="text-lg text-ink/60 max-w-md mx-auto mb-8">
        This page doesn&apos;t exist, or it has been moved.
      </p>
      <Link
        href="/"
        className="bg-ink text-canvas rounded-button px-6 py-3 font-medium hover:bg-ink/90 transition-colors"
      >
        Return Home
      </Link>
    </div>
  );
}
