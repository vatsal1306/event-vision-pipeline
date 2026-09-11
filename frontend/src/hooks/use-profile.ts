import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';
import { Photographer } from '@/types/user';

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: () => api.getProfile(),
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Photographer> & { studioName?: string }) =>
      api.updateProfile({
        studio_name: data.studio_name ?? data.studioName,
        phone: data.phone,
        watermark_url: data.watermark_url,
        logo_url: data.logo_url,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      toast.success('Profile updated successfully');
    },
    onError: () => {
      toast.error('Failed to update profile');
    },
  });
}

export function useUploadLogo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.uploadLogo(formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      toast.success('Logo uploaded successfully');
    },
    onError: () => {
      toast.error('Failed to upload logo');
    },
  });
}

export function useUploadWatermark() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, scale, x, y, opacity }: { file: File, scale: number, x: number, y: number, opacity: number }) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('scale', scale.toString());
      formData.append('x', x.toString());
      formData.append('y', y.toString());
      formData.append('opacity', opacity.toString());
      return api.uploadWatermark(formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      toast.success('Watermark uploaded successfully');
    },
    onError: () => {
      toast.error('Failed to upload watermark');
    },
  });
}
