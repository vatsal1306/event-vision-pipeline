import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

interface UseEventPhotosOptions {
  eventId: string;
  folderId?: string;
  limit?: number;
}

export function useEventPhotos({ eventId, folderId, limit = 50 }: UseEventPhotosOptions) {
  return useInfiniteQuery({
    queryKey: ['event-photos', eventId, folderId],
    queryFn: async ({ pageParam = 0 }) => {
      return api.getEventPhotos(eventId, pageParam, limit, folderId);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.offset + lastPage.limit;
      if (nextOffset < lastPage.total) {
        return nextOffset;
      }
      return undefined;
    },
  });
}

export function useMovePhotos(eventId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { photoIds: string[]; targetFolderId: string | null }) => 
      api.movePhotos(eventId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event-photos', eventId] });
    },
  });
}

export function useDeletePhotos(eventId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (photoIds: string[]) => {
      // API currently only supports single delete, so we do it in parallel
      await Promise.all(photoIds.map(id => api.deletePhoto(eventId, id)));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event-photos', eventId] });
      queryClient.invalidateQueries({ queryKey: ['events'] }); // update total photos
    },
  });
}
