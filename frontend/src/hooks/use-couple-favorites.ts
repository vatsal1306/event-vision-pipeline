import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { Photo } from '@/types/event';

export function useFavorites(slug: string, token: string | null) {
  return useQuery({
    queryKey: ['favorites', slug, token],
    queryFn: () => api.getFavorites(slug, token!),
    enabled: !!token,
  });
}

export function useToggleFavorite(slug: string, token: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (photoId: string) => api.toggleFavorite(slug, { photoId }, token!),
    onMutate: async (photoId: string) => {
      if (!token) return;

      // Cancel any outgoing refetches (so they don't overwrite our optimistic update)
      await queryClient.cancelQueries({ queryKey: ['favorites', slug, token] });

      // Snapshot the previous value
      const previousFavorites = queryClient.getQueryData<Photo[]>(['favorites', slug, token]);

      // Optimistically update to the new value
      queryClient.setQueryData<Photo[]>(['favorites', slug, token], (old) => {
        if (!old) return old;
        
        // If it's already a favorite, we're removing it
        if (old.some(p => p.id === photoId)) {
          return old.filter(p => p.id !== photoId);
        }
        
        // If it's not a favorite, we add it (optimistically adding a stub photo, 
        // though normally we'd have the full photo object. Since this hook is typically 
        // used when we already have the photo from the master list, the master list 
        // will still render it. However, the favorites view needs the full object.
        // For our use case, we might need to fetch the full object or rely on refetch.)
        // A simple stub for the ID is enough for the `Set` matching logic in the UI.
        return [...old, { id: photoId } as Photo];
      });

      // Return a context with the previous and new todo
      return { previousFavorites };
    },
    // If the mutation fails, use the context we returned above
    onError: (err, newFavorite, context) => {
      if (context?.previousFavorites && token) {
        queryClient.setQueryData(['favorites', slug, token], context.previousFavorites);
      }
    },
    // Always refetch after error or success to ensure true state
    onSettled: () => {
      if (token) {
        queryClient.invalidateQueries({ queryKey: ['favorites', slug, token] });
      }
    },
  });
}
