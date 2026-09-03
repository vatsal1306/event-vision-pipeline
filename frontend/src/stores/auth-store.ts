import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Photographer } from '@/types/user';

interface AuthState {
  photographer: Photographer | null;
  accessToken: string | null;
  refreshTokenString: string | null;
  isAuthenticated: boolean;
  setPhotographer: (photographer: Photographer, token: string) => void;
  setTokens: (accessToken: string, refreshToken?: string) => void;
  clearTokens: () => void;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      photographer: null,
      accessToken: null,
      refreshTokenString: null,
      isAuthenticated: false,

      setPhotographer: (photographer: Photographer, token: string) => {
        set({ photographer, accessToken: token, isAuthenticated: true });
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', token);
        }
      },

      setTokens: (accessToken: string, refreshToken?: string) => {
        set({ accessToken, refreshTokenString: refreshToken || null, isAuthenticated: true });
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', accessToken);
          if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken);
          }
        }
      },

      clearTokens: () => {
        set({ accessToken: null, refreshTokenString: null, isAuthenticated: false, photographer: null });
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
      },

      logout: () => {
        set({ photographer: null, accessToken: null, refreshTokenString: null, isAuthenticated: false });
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
      },

      refreshToken: async () => {
        throw new Error('Not implemented'); // TODO FE-008
      },
    }),
    {
      name: 'auth-storage', // key in local storage
      // omit refreshToken and actions from persistence
      partialize: (state) => ({ 
        photographer: state.photographer, 
        accessToken: state.accessToken,
        refreshTokenString: state.refreshTokenString,
        isAuthenticated: state.isAuthenticated 
      }),
    }
  )
);
