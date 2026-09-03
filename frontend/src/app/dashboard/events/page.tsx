'use client';

import { useAuthStore } from '@/stores/auth-store';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useEffect } from 'react';

export default function EventsPlaceholderPage() {
  const { clearTokens, accessToken } = useAuthStore();
  const router = useRouter();

  // Basic client-side protection just for this placeholder
  useEffect(() => {
    if (!accessToken) {
      router.push('/login');
    }
  }, [accessToken, router]);

  if (!accessToken) return null;

  return (
    <div className="flex flex-col items-center justify-center min-h-screen space-y-4">
      <h1 className="text-3xl font-bold">Dashboard Placeholder</h1>
      <p className="text-muted-foreground">You are successfully logged in!</p>
      <Button onClick={() => {
        clearTokens();
        router.push('/login');
      }}>
        Log out
      </Button>
    </div>
  );
}
