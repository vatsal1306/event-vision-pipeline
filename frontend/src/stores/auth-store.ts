import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Photographer } from '@/types/user';
import { api } from '@/lib/api-client';

interface AuthState {
  photographer: Photographer | null;
  accessToken: string | null;
  refreshTokenString: string | null;
  isAuthenticated: boolean;
  setSession: (photographer: Photographer, accessToken: string, refreshToken: string) => void;
  setTokens: (accessToken: string, refreshToken?: string) => void;
  clearTokens: () => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      photographer: null,
      accessToken: null,
      refreshTokenString: null,
      isAuthenticated: false,

      setSession: (photographer: Photographer, accessToken: string, refreshToken: string) => {
        set({
          photographer,
          accessToken,
          refreshTokenString: refreshToken,
          isAuthenticated: true,
        });
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', accessToken);
          localStorage.setItem('refresh_token', refreshToken);
        }
      },

      setTokens: (accessToken: string, refreshToken?: string) => {
        set({
          accessToken,
          refreshTokenString: refreshToken || null,
          isAuthenticated: true,
        });
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', accessToken);
          if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken);
          }
        }
      },

      clearTokens: () => {
        set({
          accessToken: null,
          refreshTokenString: null,
          isAuthenticated: false,
          photographer: null,
        });
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
      },

      logout: async () => {
        const refreshToken = get().refreshTokenString;
        const accessToken = get().accessToken;
        if (refreshToken && accessToken) {
          try {
            await api.logout(refreshToken);
          } catch {
            // Clear local session even if the API call fails.
          }
        }
        get().clearTokens();
      },

      refreshToken: async () => {
        const refreshToken = get().refreshTokenString;
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }
        const response = await api.refresh(refreshToken);
        set({
          accessToken: response.access_token,
          refreshTokenString: response.refresh_token,
          photographer: response.photographer,
          isAuthenticated: true,
        });
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', response.access_token);
          localStorage.setItem('refresh_token', response.refresh_token);
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        photographer: state.photographer,
        accessToken: state.accessToken,
        refreshTokenString: state.refreshTokenString,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
