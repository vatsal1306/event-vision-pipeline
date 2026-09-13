/** Photographer-facing copy for guest selfie match outcomes. */

const FAILURE_COPY: Record<string, string> = {
  no_match:
    "We couldn't match that selfie to photos from this event. Try again in good light, facing the camera.",
  no_face_detected: "We couldn't see a face. Hold the phone a bit further back and try again.",
  liveness_failed: 'That photo did not look like a live selfie. Please retake it facing the camera.',
  low_quality: 'That selfie was a bit blurry or turned away. Please retake it looking at the camera.',
  no_clusters: 'Photos are still being grouped. Please try again in a minute.',
  crop_failed: 'We could not read that selfie. Please retake it.',
  invalid_image: 'That file did not look like a photo. Please retake your selfie.',
  error: 'Something went wrong matching your selfie. Please try again.',
};

/**
 * Return a guest-facing explanation when selfie matching did not find photos.
 */
export function guestSelfieFailureCopy(status: string | undefined): string {
  if (!status) {
    return FAILURE_COPY.no_match;
  }
  return FAILURE_COPY[status] ?? FAILURE_COPY.no_match;
}

/** Whether the guest should proceed to their personalized gallery. */
export function isSelfieMatchSuccess(status: string | undefined, matchedPhotoCount: number): boolean {
  return status === 'matched' && matchedPhotoCount > 0;
}
