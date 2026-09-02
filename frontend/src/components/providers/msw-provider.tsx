'use client';

import { useEffect, useState, ReactNode } from 'react';

export function MSWProvider({ children }: { children: ReactNode }) {
  const [mswReady, setMswReady] = useState(false);

  useEffect(() => {
    const initMsw = async () => {
      if (process.env.NEXT_PUBLIC_MOCK_API === 'true') {
        const { worker } = await import('@/mocks/browser');
        await worker.start({ onUnhandledRequest: 'warn' });
      }
      setMswReady(true);
    };

    initMsw();
  }, []);

  // While MSW is starting, wait before rendering to avoid real network requests
  if (!mswReady && process.env.NEXT_PUBLIC_MOCK_API === 'true') {
    return null; 
  }

  return <>{children}</>;
}
