import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { GuestSession } from '@/types/user';

interface GuestAuthState {
  guestSession: GuestSession | null;
  sessionToken: string | null;
  needsSelfie: boolean;
  isVerified: boolean;
  setGuestSession: (session: GuestSession, token: string, needsSelfie: boolean) => void;
  clearGuestSession: () => void;
}

export const useGuestAuthStore = create<GuestAuthState>()(
  persist(
    (set) => ({
      guestSession: null,
      sessionToken: null,
      needsSelfie: true,
      isVerified: false,

      setGuestSession: (session: GuestSession, token: string, needsSelfie: boolean) => {
        set({ guestSession: session, sessionToken: token, needsSelfie, isVerified: true });
      },

      clearGuestSession: () => {
        set({ guestSession: null, sessionToken: null, needsSelfie: true, isVerified: false });
      },
    }),
    {
      name: 'guest-auth-storage', // keep session for return visits
    }
  )
);
