import { Event, EventStatus } from '@/types/event';

export type EventStatusTone = 'neutral' | 'info' | 'warning' | 'success' | 'muted';

export interface EventStatusPresentation {
  /** Backend status value. */
  status: EventStatus;
  /** Short photographer-facing label. */
  label: string;
  tone: EventStatusTone;
}

/**
 * Map API event status to what photographers should actually see.
 *
 * Backend still uses `uploading` after files are in, until Find faces runs.
 * That word is misleading once uploads have finished.
 */
export function getEventStatusPresentation(
  event: Pick<Event, 'status' | 'totalPhotos' | 'processedPhotos' | 'pendingFacePhotos'>
): EventStatusPresentation {
  const { status } = event;

  if (status === 'draft') {
    return { status, label: 'Draft', tone: 'neutral' };
  }
  if (status === 'archived') {
    return { status, label: 'Archived', tone: 'muted' };
  }
  if (status === 'processing') {
    return { status, label: 'Finding faces', tone: 'warning' };
  }
  if (status === 'ready') {
    return { status, label: 'Ready', tone: 'success' };
  }

  const total = event.totalPhotos;
  const processed = event.processedPhotos;
  const pendingFaces = event.pendingFacePhotos ?? 0;

  if (total > 0 && processed < total) {
    return { status, label: 'Preparing photos', tone: 'info' };
  }
  if (pendingFaces > 0) {
    return { status, label: 'Awaiting faces', tone: 'info' };
  }
  if (total === 0) {
    return { status, label: 'Uploading', tone: 'info' };
  }
  return { status, label: 'Uploaded', tone: 'info' };
}
