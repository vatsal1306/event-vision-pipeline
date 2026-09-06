import { EventStatus } from '@/types/event';

export const OTP_LENGTH = 6;
export const MAX_CONCURRENT_UPLOADS = 6;
export const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB

export const EVENT_STATUS_LABELS: Record<EventStatus, string> = {
  draft: 'Draft',
  uploading: 'Uploading',
  processing: 'Processing',
  ready: 'Ready',
  archived: 'Archived',
};
