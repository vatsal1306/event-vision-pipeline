import { describe, it, expect } from 'vitest';
import { guestSelfieFailureCopy, isSelfieMatchSuccess } from '@/lib/guest-selfie';

describe('guestSelfieFailureCopy', () => {
  it('should explain liveness failures instead of saying no photos', () => {
    expect(guestSelfieFailureCopy('liveness_failed')).toMatch(/live selfie/i);
  });

  it('should fall back for unknown statuses', () => {
    expect(guestSelfieFailureCopy('mystery')).toMatch(/couldn.t match/i);
  });
});

describe('isSelfieMatchSuccess', () => {
  it('should require a matched status and at least one photo', () => {
    expect(isSelfieMatchSuccess('matched', 4)).toBe(true);
    expect(isSelfieMatchSuccess('matched', 0)).toBe(false);
    expect(isSelfieMatchSuccess('no_match', 0)).toBe(false);
    expect(isSelfieMatchSuccess('liveness_failed', 0)).toBe(false);
  });
});
