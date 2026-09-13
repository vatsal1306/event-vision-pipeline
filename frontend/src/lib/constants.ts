import { EventStatus } from '@/types/event';

export const OTP_LENGTH = 6;
export const MAX_CONCURRENT_UPLOADS = 6;
export const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB
/** Event status and face-processing progress while Uploading or Processing. */
export const EVENT_STATUS_POLL_INTERVAL_MS = 60_000;

/** Filter labels keyed by backend status (photographer-facing copy). */
export const EVENT_STATUS_LABELS: Record<EventStatus, string> = {
  draft: 'Draft',
  uploading: 'Needs faces',
  processing: 'Finding faces',
  ready: 'Ready',
  archived: 'Archived',
};
