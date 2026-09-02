export interface Photographer {
  id: string; // UUID
  email: string;
  studioName: string;
  phone: string;
  phoneVerified: boolean;
  logoUrl: string | null;
  watermarkUrl: string | null;
  storageUsedBytes: number;
  storageLimitBytes: number;
  isActive: boolean;
  createdAt: string; // ISO Datetime string
  updatedAt: string; // ISO Datetime string
}

export type GuestSessionStatus = 'pending' | 'verified' | 'matched';

export interface GuestSession {
  id: string; // UUID
  eventId: string; // UUID
  name: string;
  phone: string;
  phoneVerified: boolean;
  selfieUrl: string | null; // using selfieUrl to match webProxyUrl preference
  matchedClusterIds: string[]; // UUID[]
  matchedPhotoCount: number;
  status: GuestSessionStatus;
  createdAt: string; // ISO Datetime string
}

export interface CoupleSession {
  id: string; // UUID
  eventId: string; // UUID
  name: string;
  phone: string;
  phoneVerified: boolean;
  createdAt: string; // ISO Datetime string
}
