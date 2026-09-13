import { describe, it, expect } from 'vitest';
import {
  faceProcessingPercent,
  faceProcessingStatusCopy,
  isGalleryReady,
  shouldShowFindFacesButton,
} from '@/lib/face-processing';

describe('shouldShowFindFacesButton', () => {
  it('should show when uploading with pending face photos', () => {
    expect(shouldShowFindFacesButton({ status: 'uploading', pendingFacePhotos: 12 })).toBe(true);
  });

  it('should show when ready after more photos were added', () => {
    expect(shouldShowFindFacesButton({ status: 'ready', pendingFacePhotos: 3 })).toBe(true);
  });

  it('should hide when there is nothing to process', () => {
    expect(shouldShowFindFacesButton({ status: 'uploading', pendingFacePhotos: 0 })).toBe(false);
    expect(shouldShowFindFacesButton({ status: 'ready', pendingFacePhotos: 0 })).toBe(false);
  });

  it('should hide while processing, draft, or archived', () => {
    expect(shouldShowFindFacesButton({ status: 'processing', pendingFacePhotos: 10 })).toBe(false);
    expect(shouldShowFindFacesButton({ status: 'draft', pendingFacePhotos: 1 })).toBe(false);
    expect(shouldShowFindFacesButton({ status: 'archived', pendingFacePhotos: 4 })).toBe(false);
  });
});

describe('isGalleryReady', () => {
  it('should allow guest and couple galleries only when Ready', () => {
    expect(isGalleryReady('ready')).toBe(true);
    expect(isGalleryReady('uploading')).toBe(false);
    expect(isGalleryReady('processing')).toBe(false);
    expect(isGalleryReady('draft')).toBe(false);
    expect(isGalleryReady('archived')).toBe(false);
  });
});

describe('faceProcessingPercent', () => {
  it('should map processed photos to a percent under 100 while detecting', () => {
    expect(faceProcessingPercent(40, 200, 'processing')).toBe(20);
  });

  it('should treat clustering as almost complete', () => {
    expect(faceProcessingPercent(200, 200, 'clustering')).toBe(99);
  });

  it('should return 100 only when the pipeline reports complete', () => {
    expect(faceProcessingPercent(200, 200, 'complete')).toBe(100);
  });

  it('should return 0 when totals are unknown', () => {
    expect(faceProcessingPercent(0, 0, 'processing')).toBe(0);
  });
});

describe('faceProcessingStatusCopy', () => {
  it('should describe clustering in photographer language', () => {
    expect(faceProcessingStatusCopy('clustering')).toContain('Grouping people');
  });

  it('should tell the photographer they can retry after a pipeline error', () => {
    expect(faceProcessingStatusCopy('error')).toContain('try again');
  });
});
