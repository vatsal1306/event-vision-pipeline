import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export function useEventInfo(slug: string) {
  return useQuery({
    queryKey: ['event-info', slug],
    queryFn: () => api.getEventInfo(slug),
  });
}

export function useMasterAuth() {
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: { name: string; phone: string } }) =>
      api.masterAuth(slug, data),
  });
}

export function useMasterVerify() {
  return useMutation({
    mutationFn: ({ slug, otp }: { slug: string; otp: string }) =>
      api.verifyMasterAuth(slug, { otp }),
  });
}

export function useMasterFolders(slug: string, token: string | null) {
  return useQuery({
    queryKey: ['master-folders', slug, token],
    queryFn: () => api.getMasterFolders(slug, token!),
    enabled: !!token,
  });
}

export function useMasterPhotos(slug: string, token: string | null) {
  return useQuery({
    queryKey: ['master-photos', slug, token],
    queryFn: () => api.getMasterPhotos(slug, token!),
    enabled: !!token,
  });
}
