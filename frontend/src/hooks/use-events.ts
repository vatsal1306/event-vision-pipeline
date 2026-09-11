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
    refetchInterval: (query) => {
      return query.state.data?.some(e => e.status === 'processing' || e.status === 'uploading') ? 5000 : false;
    }
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

export function useUpdateEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Event> }) => {
      const updated = await api.updateEvent(id, {
        name: data.name,
        date_start: data.dateStart || null,
        date_end: data.dateEnd || null,
        event_type: data.eventType,
        description: data.description || null,
      });
      return mapEventFromApi(updated);
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['event', id] });
    },
  });
}

export function useArchiveEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.archiveEvent(id);
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['event', id] });
      const previousEvent = queryClient.getQueryData(['event', id]);
      queryClient.setQueryData(['event', id], (old: any) => ({ ...old, status: 'archived' }));
      return { previousEvent };
    },
    onError: (err, id, context) => {
      if (context?.previousEvent) {
        queryClient.setQueryData(['event', id], context.previousEvent);
      }
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
      toast.success('Event archived successfully');
    },
  });
}

export function useRestoreEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.restoreEvent(id);
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['event', id] });
      const previousEvent = queryClient.getQueryData(['event', id]);
      queryClient.setQueryData(['event', id], (old: any) => ({ ...old, status: 'ready' }));
      return { previousEvent };
    },
    onError: (err, id, context) => {
      if (context?.previousEvent) {
        queryClient.setQueryData(['event', id], context.previousEvent);
      }
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
      toast.success('Event unarchived successfully');
    },
  });
}

export function useDeleteEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.deleteEvent(id);
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
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'processing' || status === 'uploading' ? 5000 : false;
    }
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