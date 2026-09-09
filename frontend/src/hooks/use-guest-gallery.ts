import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export function useGuestAuth() {
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: { name: string; phone: string } }) =>
      api.sendGuestOtp(slug, data),
  });
}

export function useGuestVerify() {
  return useMutation({
    mutationFn: ({ slug, name, phone, otp }: { slug: string; name: string; phone: string; otp: string }) =>
      api.verifyGuestOtp(slug, { name, phone, otp }),
  });
}

export function useSubmitSelfie() {
  return useMutation({
    // We send FormData for selfie upload. Data is a FormData object.
    mutationFn: ({ slug, data, token }: { slug: string; data: FormData; token: string }) =>
      api.submitSelfie(slug, data, token),
  });
}

export function useGuestPhotos(slug: string, token: string | null) {
  return useQuery({
    queryKey: ['guestPhotos', slug, token],
    // The apiClient doesn't have token in getGuestPhotos by default, but we'll modify it or just pass if needed.
    // Assuming api.getGuestPhotos takes slug. The backend might rely on cookie or we pass the token in headers.
    // Wait, the API client: getGuestPhotos: (slug: string) => apiClient.get<PaginatedResponse<Photo>>(`/api/event/${slug}/guest/photos`)
    // I need to update api-client.ts to accept token for getGuestPhotos and submitSelfie.
    queryFn: () => api.getGuestPhotos(slug, token!),
    enabled: !!token,
  });
}
