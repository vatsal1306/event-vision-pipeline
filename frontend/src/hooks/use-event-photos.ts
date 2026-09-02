import { useInfiniteQuery } from '@tanstack/react-query';
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
