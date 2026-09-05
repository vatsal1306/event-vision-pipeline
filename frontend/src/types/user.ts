export interface Photographer {
  id: string;
  email: string;
  studio_name: string;
  phone: string;
  phone_verified: boolean;
  logo_url: string | null;
  watermark_url: string | null;
  storage_used_bytes: number;
  storage_limit_bytes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type GuestSessionStatus = 'pending' | 'verified' | 'matched';

export interface GuestSession {
  id: string;
  eventId: string;
  name: string;
  phone: string;
  phoneVerified: boolean;
  selfieUrl: string | null;
  matchedClusterIds: string[];
  matchedPhotoCount: number;
  status: GuestSessionStatus;
  createdAt: string;
}

export interface CoupleSession {
  id: string;
  eventId: string;
  name: string;
  phone: string;
  phoneVerified: boolean;
  createdAt: string;
}
