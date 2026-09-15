import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { mapPhotoFromApi } from '@/lib/map-api';
import { Photo } from '@/types/event';

export function useSharedPhotos(slug: string, token: string | null) {
  return useQuery({
    queryKey: ['sharedPhotos', slug, token],
    queryFn: async () => {
      const res = await api.getSharedPhotos(slug, token!);
      return (res.items || []).map((item) =>
        mapPhotoFromApi(item as unknown as Record<string, unknown>)
      );
    },
    enabled: !!token,
  });
}

export function useToggleShare(slug: string, token: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (photoId: string) => api.toggleShare(slug, { photo_id: photoId }, token!),
    onMutate: async (photoId: string) => {
      if (!token) return;

      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['sharedPhotos', slug, token] });

      // Snapshot the previous value
      const previousShared = queryClient.getQueryData<Photo[]>(['sharedPhotos', slug, token]);

      // Optimistically update to the new value
      queryClient.setQueryData<Photo[]>(['sharedPhotos', slug, token], (old) => {
        if (!old) return old;
        
        // If it's already shared, we're removing it
        if (old.some(p => p.id === photoId)) {
          return old.filter(p => p.id !== photoId);
        }
        
        return [...old, { id: photoId } as Photo];
      });

      return { previousShared };
    },
    onError: (err, newShared, context) => {
      if (context?.previousShared && token) {
        queryClient.setQueryData(['sharedPhotos', slug, token], context.previousShared);
      }
    },
    onSettled: () => {
      if (token) {
        queryClient.invalidateQueries({ queryKey: ['sharedPhotos', slug, token] });
      }
    },
  });
}
