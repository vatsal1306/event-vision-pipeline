import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api-client';
import { EVENT_STATUS_POLL_INTERVAL_MS } from '@/lib/constants';
import { Event } from '@/types/event';

function faceProcessingDisabledMessage(): string {
  return (
    'Face matching is not enabled on this server. On your laptop, set ' +
    'ML_FACE_PROCESSING_ENABLED=true in backend/.env and run a Celery worker on the ' +
    'face_processing queue.'
  );
}

function startFaceProcessingErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'FACE_PROCESSING_DISABLED') {
      return faceProcessingDisabledMessage();
    }
    if (error.status === 422) {
      return 'Upload photos first, then click Find faces.';
    }
    return error.message;
  }
  return 'Could not start face matching. Please try again.';
}

/**
 * Enqueue face extraction + clustering for an event the photographer owns.
 */
export function useStartFaceProcessing(eventId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.startFaceProcessing(eventId),
    onSuccess: (result) => {
      queryClient.setQueryData<Event | undefined>(['event', eventId], (current) => {
        if (!current) {
          return current;
        }
        return { ...current, status: result.status };
      });
      void queryClient.invalidateQueries({ queryKey: ['event', eventId] });
      void queryClient.invalidateQueries({ queryKey: ['events'] });
      void queryClient.invalidateQueries({ queryKey: ['face-processing-progress', eventId] });

      if (result.already_running) {
        toast.info('Face matching is already running for this event.');
        return;
      }
      toast.success('Finding faces. Large events can take a few minutes.');
    },
    onError: (error: unknown) => {
      toast.error(startFaceProcessingErrorMessage(error));
    },
  });
}

/**
 * Poll Redis-backed bulk progress while the event is Processing.
 */
export function useFaceProcessingProgress(eventId: string, isProcessing: boolean) {
  return useQuery({
    queryKey: ['face-processing-progress', eventId],
    queryFn: () => api.getFaceProcessingProgress(eventId),
    enabled: Boolean(eventId) && isProcessing,
    refetchInterval: isProcessing ? EVENT_STATUS_POLL_INTERVAL_MS : false,
  });
}
