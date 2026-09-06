import { useAuthStore } from '../stores/auth-store';
import { useGuestAuthStore } from '../stores/guest-auth-store';

export const useAuth = () => {
  const { photographer, accessToken, isAuthenticated, setSession, logout, refreshToken } =
    useAuthStore();

  return {
    photographer,
    accessToken,
    isAuthenticated,
    setSession,
    logout,
    refreshToken,
  };
};

export const useGuestAuth = () => {
  const { guestSession, isVerified, setGuestSession, clearGuestSession } = useGuestAuthStore();
  
  return {
    guestSession,
    isVerified,
    setGuestSession,
    clearGuestSession
  };
};
