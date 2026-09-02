import { useAuthStore } from '../stores/auth-store';
import { useGuestAuthStore } from '../stores/guest-auth-store';

export const useAuth = () => {
  const { photographer, accessToken, isAuthenticated, setPhotographer, logout, refreshToken } = useAuthStore();
  
  return {
    photographer,
    accessToken,
    isAuthenticated,
    setPhotographer,
    logout,
    refreshToken
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
