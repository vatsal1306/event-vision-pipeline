import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export function useAnalyticsSummary(eventId: string) {
  return useQuery({
    queryKey: ['events', eventId, 'analytics', 'summary'],
    queryFn: () => api.getAnalyticsSummary(eventId),
    enabled: !!eventId,
  });
}

export function useTopPhotos(eventId: string) {
  return useQuery({
    queryKey: ['events', eventId, 'analytics', 'top-photos'],
    queryFn: () => api.getAnalyticsTopPhotos(eventId),
    enabled: !!eventId,
  });
}

export function useGuests(
  eventId: string,
  page: number,
  limit: number,
  sortBy: string,
  sortOrder: 'asc' | 'desc'
) {
  return useQuery({
    queryKey: ['events', eventId, 'analytics', 'guests', page, limit, sortBy, sortOrder],
    queryFn: () => api.getAnalyticsGuests(eventId, page, limit, sortBy, sortOrder),
    enabled: !!eventId,
    placeholderData: (prev) => prev,
  });
}
