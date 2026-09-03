'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { Sidebar } from '@/components/dashboard/sidebar';
import { Header } from '@/components/dashboard/header';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import { useUiStore } from '@/stores/ui-store';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { accessToken } = useAuthStore();
  const { isSidebarCollapsed } = useUiStore();
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(useAuthStore.persist.hasHydrated());
    const unsub = useAuthStore.persist.onFinishHydration(() => setIsHydrated(true));
    return () => {
      if (unsub) unsub();
    };
  }, []);

  useEffect(() => {
    if (isHydrated && !accessToken) {
      router.push('/login');
    }
  }, [isHydrated, accessToken, router]);

  if (!isHydrated || !accessToken) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={cn(
          'transition-all duration-300',
          isSidebarCollapsed ? 'md:pl-16' : 'md:pl-64'
        )}
      >
        <Header />
        <main className="p-4 md:p-6 lg:p-8" id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}