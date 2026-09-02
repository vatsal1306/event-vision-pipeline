import { Photographer } from '@/types/user';

export const mockProfile: Photographer = {
  id: 'photog-1234',
  email: 'vatsal@example.com',
  studioName: 'Vatsal Studio',
  phone: '+919876543210',
  phoneVerified: true,
  logoUrl: 'https://picsum.photos/seed/logo/200/200',
  watermarkUrl: 'https://picsum.photos/seed/watermark/400/200',
  storageUsedBytes: 25000000000, // 25GB
  storageLimitBytes: 100000000000, // 100GB
  isActive: true,
  createdAt: '2025-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};
