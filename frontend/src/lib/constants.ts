import { EventStatus } from '@/types/event';

export const OTP_LENGTH = 6;
export const MAX_CONCURRENT_UPLOADS = 6;
/** Default page size for gallery photo list endpoints. */
export const GALLERY_PAGE_SIZE = 50;
/** Load the next page when the user is this close to the document bottom. */
export const INFINITE_SCROLL_THRESHOLD_PX = 600;
/**
 * How many pages gallery hooks silently warm ahead of what's visible (see
 * `usePrefetchNextPage`). Deliberately 1, not more — prefetching further
 * ahead would waste bandwidth on photos the user may never scroll to.
 */
export const PREFETCH_PAGES_AHEAD = 1;
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
