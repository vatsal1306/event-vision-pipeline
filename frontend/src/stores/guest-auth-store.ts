import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { GuestSession } from '@/types/user';

interface GuestAuthState {
  guestSession: GuestSession | null;
  isVerified: boolean;
  setGuestSession: (session: GuestSession) => void;
  clearGuestSession: () => void;
}

export const useGuestAuthStore = create<GuestAuthState>()(
  persist(
    (set) => ({
      guestSession: null,
      isVerified: false,

      setGuestSession: (session: GuestSession) => {
        set({ guestSession: session, isVerified: true });
      },

      clearGuestSession: () => {
        set({ guestSession: null, isVerified: false });
      },
    }),
    {
      name: 'guest-auth-storage', // keep session for return visits
    }
  )
);
