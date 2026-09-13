import { Event, EventStatus } from '@/types/event';

/** Pipeline statuses returned by GET face-processing-progress. */
export type FacePipelineStatus = 'idle' | 'processing' | 'clustering' | 'complete' | 'error' | string;

/**
 * Whether the photographer should see the Find faces action.
 *
 * Shown when photos still need face extraction and the event is waiting
 * (Uploading) or already Ready after new uploads.
 */
export function shouldShowFindFacesButton(event: Pick<Event, 'status' | 'pendingFacePhotos'>): boolean {
  const pending = event.pendingFacePhotos ?? 0;
  if (pending <= 0) {
    return false;
  }
  return event.status === 'uploading' || event.status === 'ready';
}

/** Guest and couple galleries are only usable once the event is Ready. */
export function isGalleryReady(status: EventStatus): boolean {
  return status === 'ready';
}

/**
 * Map bulk-progress counters to a 0–100 percent for the dashboard bar.
 *
 * Clustering is treated as almost done so the bar does not sit at 100%
 * before the event actually flips to Ready.
 */
export function faceProcessingPercent(
  processedPhotos: number,
  totalPhotos: number,
  pipelineStatus: FacePipelineStatus
): number {
  if (pipelineStatus === 'complete') {
    return 100;
  }
  if (pipelineStatus === 'clustering') {
    if (totalPhotos <= 0) {
      return 95;
    }
    return Math.min(99, Math.max(95, Math.round((processedPhotos / totalPhotos) * 100)));
  }
  if (totalPhotos <= 0) {
    return 0;
  }
  return Math.min(99, Math.round((processedPhotos / totalPhotos) * 100));
}

/** Short photographer-facing copy for the current pipeline stage. */
export function faceProcessingStatusCopy(pipelineStatus: FacePipelineStatus): string {
  switch (pipelineStatus) {
    case 'clustering':
      return 'Grouping people so guests can find themselves…';
    case 'complete':
      return 'Face matching is complete.';
    case 'error':
      return 'Face matching ran into a problem. You can try again in a moment.';
    case 'idle':
      return 'Getting ready to find faces…';
    default:
      return 'Finding faces in your photos…';
  }
}
