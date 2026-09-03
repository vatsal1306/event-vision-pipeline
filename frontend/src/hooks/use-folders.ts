import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { FolderNode, Folder } from '@/types/event';

export function useFolders(eventId: string) {
  return useQuery({
    queryKey: ['folders', eventId],
    queryFn: async () => {
      const res = await api.getFolders(eventId);
      return res as unknown as FolderNode[];
    },
    enabled: !!eventId,
  });
}

export function useCreateFolder(eventId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { name: string; parentId: string | null }) => api.createFolder(eventId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', eventId] });
    },
  });
}

export function useRenameFolder(eventId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ folderId, name }: { folderId: string; name: string }) => 
      api.updateFolder(eventId, folderId, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', eventId] });
    },
  });
}

export function useDeleteFolder(eventId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (folderId: string) => api.deleteFolder(eventId, folderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', eventId] });
      queryClient.invalidateQueries({ queryKey: ['photos', eventId] });
    },
  });
}
