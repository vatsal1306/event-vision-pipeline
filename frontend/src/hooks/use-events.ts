import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api-client';
import { mapEventFromApi } from '@/lib/map-api';
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
      return (res.events || []).map((item) => mapEventFromApi(item));
    },
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateEventData) => {
      const created = await api.createEvent({
        name: data.name,
        date_start: data.dateStart || null,
        date_end: data.dateEnd || null,
        event_type: data.eventType,
        description: data.description || null,
      });
      return mapEventFromApi(created);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });
}

export function useEvent(id: string) {
  return useQuery({
    queryKey: ['event', id],
    queryFn: async () => mapEventFromApi(await api.getEventDetails(id)),
    enabled: !!id,
  });
}

export function useToggleLink(eventId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (type: 'guest' | 'master') =>
      mapEventFromApi(await api.toggleLink(eventId, type)),
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
    mutationFn: async (data: Partial<Event>) =>
      mapEventFromApi(
        await api.updateEventSettings(eventId, {
          download_enabled: data.downloadEnabled,
          master_link_active: data.masterLinkActive,
          guest_link_active: data.guestLinkActive,
        })
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['event', eventId] });
    },
    onError: () => {
      toast.error('Failed to update settings');
    }
  });
}