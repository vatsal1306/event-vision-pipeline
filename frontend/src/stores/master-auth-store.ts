import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface MasterAuthDetails {
  eventId: string;
  token: string;
  name: string;
  phone: string;
}

interface MasterAuthStore {
  // Store authentication per event to support multiple events
  authSessions: Record<string, MasterAuthDetails>;
  
  // Actions
  login: (eventId: string, details: Omit<MasterAuthDetails, 'eventId'>) => void;
  logout: (eventId: string) => void;
  getToken: (eventId: string) => string | null;
  isAuthenticated: (eventId: string) => boolean;
}

export const useMasterAuthStore = create<MasterAuthStore>()(
  persist(
    (set, get) => ({
      authSessions: {},
      
      login: (eventId, details) => set((state) => ({
        authSessions: {
          ...state.authSessions,
          [eventId]: { eventId, ...details }
        }
      })),
      
      logout: (eventId) => set((state) => {
        const newSessions = { ...state.authSessions };
        delete newSessions[eventId];
        return { authSessions: newSessions };
      }),
      
      getToken: (eventId) => get().authSessions[eventId]?.token || null,
      
      isAuthenticated: (eventId) => !!get().authSessions[eventId]?.token,
    }),
    {
      name: 'master-auth-storage',
    }
  )
);
