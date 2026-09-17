import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { GALLERY_PAGE_SIZE } from '@/lib/constants';
import { mapPhotoFromApi } from '@/lib/map-api';
import { getOffsetNextPageParam } from '@/lib/pagination';
import { PaginatedResponse } from '@/types/api';
import { Photo } from '@/types/event';

/** Map a guest photo list payload into frontend Photo models. */
function mapGuestPhotoPage(page: PaginatedResponse<Photo> | PaginatedResponse<unknown>) {
  const items = page.items.map((item) => mapPhotoFromApi(item as unknown as Record<string, unknown>));
  return { ...page, items };
}

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
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, data, token }: { slug: string; data: FormData; token: string }) =>
      api.submitSelfie(slug, data, token),
    onSuccess: (result, { slug, token }) => {
      const rawPhotos = result.photos ?? [];
      if (rawPhotos.length === 0) {
        return;
      }
      // Pre-populate the first page of guest photos from selfie result
      queryClient.setQueryData(['guestPhotos', slug, token], {
        pages: [mapGuestPhotoPage({
          items: rawPhotos,
          total: result.matched_photo_count,
          offset: 0,
          limit: rawPhotos.length,
        })],
        pageParams: [0],
      });
    },
  });
}

export function useGuestPhotos(slug: string, token: string | null) {
  return useInfiniteQuery({
    queryKey: ['guestPhotos', slug, token],
    queryFn: async ({ pageParam = 0 }) => {
      const page = await api.getGuestPhotos(slug, token!, pageParam, GALLERY_PAGE_SIZE);
      return mapGuestPhotoPage(page) as PaginatedResponse<Photo>;
    },
    initialPageParam: 0,
    getNextPageParam: getOffsetNextPageParam,
    enabled: !!token,
    staleTime: 0,
  });
}

export function useGuestHighlights(slug: string, token: string | null) {
  return useInfiniteQuery({
    queryKey: ['guestHighlights', slug, token],
    queryFn: async ({ pageParam = 0 }) => {
      const page = await api.getGuestHighlights(slug, token!, pageParam, GALLERY_PAGE_SIZE);
      return mapGuestPhotoPage(page) as PaginatedResponse<Photo>;
    },
    initialPageParam: 0,
    getNextPageParam: getOffsetNextPageParam,
    enabled: !!token,
    staleTime: 0,
  });
}

