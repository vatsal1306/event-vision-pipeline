import { describe, it, expect } from 'vitest';
import { guestSelfieFailureCopy, canProceedToGallery } from '@/lib/guest-selfie';

describe('guestSelfieFailureCopy', () => {
  it('should explain liveness failures instead of saying no photos', () => {
    expect(guestSelfieFailureCopy('liveness_failed')).toMatch(/live selfie/i);
  });

  it('should fall back for unknown statuses', () => {
    expect(guestSelfieFailureCopy('mystery')).toMatch(/couldn.t match/i);
  });
});

describe('canProceedToGallery', () => {
  it('should allow matched and no_match statuses', () => {
    expect(canProceedToGallery('matched')).toBe(true);
    expect(canProceedToGallery('no_match')).toBe(true);
    expect(canProceedToGallery('liveness_failed')).toBe(false);
  });
});
