import { Photographer } from '@/types/user';

export const mockProfile: Photographer = {
  id: 'photog-1234',
  email: 'vatsal@example.com',
  studio_name: 'Vatsal Studio',
  phone: '+919876543210',
  phone_verified: true,
  logo_url: 'https://picsum.photos/seed/logo/200/200',
  watermark_url: 'https://picsum.photos/seed/watermark/400/200',
  storage_used_bytes: 25000000000,
  storage_limit_bytes: 100000000000,
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};
