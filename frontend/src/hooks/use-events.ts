import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';
import { Event, EventType } from '@/types/event';

export interface CreateEventData {
  name: string;
  dateStart: string;
  dateEnd?: string;
  eventType: EventType;
  description?: string;
}

export function useEvents() {
  return useQuery({
    queryKey: ['events'],
    queryFn: async () => {
      const res = await api.getEvents();
      // Safely handle generic 'items' or specific 'events' key based on backend contract
      return ((res as any).events || res.items || []) as Event[];
    },
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateEventData) => api.createEvent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });
}

export function useEvent(id: string) {
  return useQuery({
    queryKey: ['event', id],
    queryFn: () => api.getEventDetails(id),
    enabled: !!id,
  });
}

export function useToggleLink(eventId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (type: 'guest' | 'master') => api.toggleLink(eventId, type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', eventId] });
    },
    onError: () => {
      toast.error('Failed to toggle link');
    }
  });
}

export function useUpdateEventSettings(eventId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Event>) => api.updateEventSettings(eventId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', eventId] });
    },
    onError: () => {
      toast.error('Failed to update settings');
    }
  });
}