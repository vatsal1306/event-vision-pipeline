import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { mapEventFromApi, mapPhotoFromApi, mapFolderNodeFromApi } from '@/lib/map-api';

export function useEventInfo(slug: string) {
  return useQuery({
    queryKey: ['event-info', slug],
    queryFn: async () => {
      const data = await api.getEventInfo(slug);
      return {
        ...data,
        event: mapEventFromApi(data.event as unknown as Record<string, unknown>),
      };
    },
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
    mutationFn: ({ slug, name, phone, otp }: { slug: string; name: string; phone: string; otp: string }) =>
      api.verifyMasterAuth(slug, { name, phone, otp }),
  });
}

export function useMasterFolders(slug: string, token: string | null) {
  return useQuery({
    queryKey: ['master-folders', slug, token],
    queryFn: async () => {
      const res = await api.getMasterFolders(slug, token!);
      return (res.folders || []).map((folder) =>
        mapFolderNodeFromApi(folder as unknown as Record<string, unknown>)
      );
    },
    enabled: !!token,
  });
}

export function useMasterPhotos(slug: string, token: string | null) {
  return useQuery({
    queryKey: ['master-photos', slug, token],
    queryFn: async () => {
      const res = await api.getMasterPhotos(slug, token!);
      return (res.items || []).map((item) =>
        mapPhotoFromApi(item as unknown as Record<string, unknown>)
      );
    },
    enabled: !!token,
  });
}
