import { describe, it, expect } from 'vitest';
import { getEventStatusPresentation } from '@/lib/event-status';

const base = {
  totalPhotos: 12,
  processedPhotos: 12,
  pendingFacePhotos: 12,
};

describe('getEventStatusPresentation', () => {
  it('should show Ready in the success tone', () => {
    expect(getEventStatusPresentation({ ...base, status: 'ready', pendingFacePhotos: 0 })).toEqual({
      status: 'ready',
      label: 'Ready',
      tone: 'success',
    });
  });

  it('should not say Uploading after photos are in and faces are pending', () => {
    expect(getEventStatusPresentation({ ...base, status: 'uploading' }).label).toBe('Awaiting faces');
  });

  it('should say Preparing photos while proxies are still finishing', () => {
    expect(
      getEventStatusPresentation({
        status: 'uploading',
        totalPhotos: 10,
        processedPhotos: 4,
        pendingFacePhotos: 10,
      }).label
    ).toBe('Preparing photos');
  });

  it('should describe processing as Finding faces', () => {
    expect(getEventStatusPresentation({ ...base, status: 'processing' }).label).toBe('Finding faces');
  });
});
