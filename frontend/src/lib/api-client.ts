import { Event, EventType, EventStatus, Folder, FolderNode, Photo } from '@/types/event';
import { Photographer } from '@/types/user';
import { AnalyticsSummary, AnalyticsTopPhoto, PaginatedGuests } from '@/types/analytics';
import { PaginatedResponse, TokenResponse } from '@/types/api';

export class ApiError extends Error {
  constructor(
    public status: number,
    public message: string,
    public code: string,
    public errors?: { field?: string; message: string }[]
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

import { useAuthStore } from '../stores/auth-store';

class ApiClient {
  private baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

  private getToken(): string | null {
    if (typeof window !== 'undefined') {
      // Direct getState call to avoid React hooks rules issue outside of components
      return useAuthStore.getState().accessToken || localStorage.getItem('access_token');
    }
    return null;
  }

  private async handle401() {
    // Placeholder for token refresh logic to be implemented later
    if (typeof window !== 'undefined') {
      // e.g. trigger Zustand store logout if refresh fails
      // window.location.href = '/login';
    }
    throw new ApiError(401, 'Unauthorized', 'UNAUTHORIZED');
  }

  private async request<T>(method: string, path: string, options?: RequestOptions): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(token && { Authorization: `Bearer ${token}` }),
    };

    const isFormData = options?.body instanceof FormData;
    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }

    // Safely cast or merge options headers
    if (options?.headers) {
      Object.assign(headers, options.headers);
    }

    const fetchOptions: RequestInit = {
      method,
      headers,
      signal: options?.signal,
    };

    if (options?.body) {
      fetchOptions.body = isFormData ? (options.body as FormData) : JSON.stringify(options.body);
    }

    try {
      const response = await fetch(`${this.baseUrl}${path}`, fetchOptions);

      if (response.status === 401) {
        await this.handle401();
        // optionally retry request here later
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
          response.status,
          errorData.detail || 'An error occurred',
          errorData.code || 'UNKNOWN_ERROR',
          errorData.errors
        );
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return {} as T;
      }

      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(500, error instanceof Error ? error.message : 'Network Error', 'NETWORK_ERROR');
    }
  }

  public get<T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) {
    return this.request<T>('GET', path, options);
  }

  public post<T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) {
    return this.request<T>('POST', path, { ...options, body });
  }

  public put<T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) {
    return this.request<T>('PUT', path, { ...options, body });
  }

  public patch<T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) {
    return this.request<T>('PATCH', path, { ...options, body });
  }

  public delete<T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) {
    return this.request<T>('DELETE', path, options);
  }

  public head<T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) {
    return this.request<T>('HEAD', path, options);
  }
}

export const apiClient = new ApiClient();

// §10.2 Typed API Methods
export const api = {
  // Auth
  register: (data: unknown) => apiClient.post<TokenResponse>('/api/auth/register', data),
  login: (data: unknown) => apiClient.post<TokenResponse>('/api/auth/login', data),
  logout: () => apiClient.post<void>('/api/auth/logout'),
  refresh: () => apiClient.post<TokenResponse>('/api/auth/refresh'),
  forgotPassword: (data: unknown) => apiClient.post<void>('/api/auth/forgot-password', data),
  resetPassword: (data: unknown) => apiClient.post<void>('/api/auth/reset-password', data),
  sendOtp: (data: unknown) => apiClient.post<void>('/api/auth/send-otp', data),
  verifyOtp: (data: unknown) => apiClient.post<TokenResponse>('/api/auth/verify-otp', data),

  // Events
  getEvents: () => apiClient.get<PaginatedResponse<Event>>('/api/events'),
  createEvent: (data: unknown) => apiClient.post<Event>('/api/events', data),
  getEventDetails: (id: string) => apiClient.get<Event>(`/api/events/${id}`),
  updateEvent: (id: string, data: unknown) => apiClient.put<Event>(`/api/events/${id}`, data),
  deleteEvent: (id: string) => apiClient.delete<void>(`/api/events/${id}`),

  // Folders
  getFolders: (eventId: string) => apiClient.get<FolderNode[]>(`/api/events/${eventId}/folders`),
  createFolder: (eventId: string, data: unknown) => apiClient.post<Folder>(`/api/events/${eventId}/folders`, data),
  updateFolder: (eventId: string, folderId: string, data: unknown) => apiClient.put<Folder>(`/api/events/${eventId}/folders/${folderId}`, data),
  deleteFolder: (eventId: string, folderId: string) => apiClient.delete<void>(`/api/events/${eventId}/folders/${folderId}`),

  // Photos
  getEventPhotos: (eventId: string, offset = 0, limit = 50, folderId?: string) => {
    const params = new URLSearchParams({ offset: offset.toString(), limit: limit.toString() });
    if (folderId) params.append('folderId', folderId);
    return apiClient.get<PaginatedResponse<Photo>>(`/api/events/${eventId}/photos?${params.toString()}`);
  },
  deletePhoto: (eventId: string, photoId: string) => apiClient.delete<void>(`/api/events/${eventId}/photos/${photoId}`),
  movePhotos: (eventId: string, data: unknown) => apiClient.post<void>(`/api/events/${eventId}/photos/move`, data),
  downloadPhoto: (eventId: string, photoId: string) => apiClient.get<{ url: string }>(`/api/events/${eventId}/photos/${photoId}/download`),

  // Upload
  createUpload: (data: unknown) => apiClient.post<{ uploadUrl: string }>('/api/upload/create', data),
  uploadChunk: (uploadId: string, data: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) => apiClient.patch<void>(`/api/upload/${uploadId}`, data, options),
  getUploadOffset: (uploadId: string) => apiClient.head<{ offset: number }>(`/api/upload/${uploadId}`),

  // Sharing
  getLinks: (eventId: string) => apiClient.get<unknown>(`/api/events/${eventId}/links`),
  toggleLink: (eventId: string, type: 'guest' | 'master') => apiClient.put<void>(`/api/events/${eventId}/links/${type}/toggle`),
  updateEventSettings: (eventId: string, data: unknown) => apiClient.put<Event>(`/api/events/${eventId}/settings`, data),

  // Guest / Couple
  getEventInfoPublic: (slug: string) => apiClient.get<unknown>(`/api/event/${slug}/info`),
  getEventInfo: (slug: string) => apiClient.get<{ event: Event; photographer: Photographer }>(`/api/event/${slug}/info`),
  masterAuth: (slug: string, data: { name: string; phone: string }) => apiClient.post<{ success: boolean }>(`/api/event/${slug}/master/auth`, data),
  verifyMasterAuth: (slug: string, data: { otp: string }) => apiClient.post<{ token: string }>(`/api/event/${slug}/master/verify`, data),
  sendGuestOtp: (slug: string, data: unknown) => apiClient.post<void>(`/api/event/${slug}/auth`, data),
  verifyGuestOtp: (slug: string, data: unknown) => apiClient.post<TokenResponse>(`/api/event/${slug}/auth/verify`, data),
  submitSelfie: (slug: string, data: unknown) => apiClient.post<{ matchedPhotoIds: string[]; matchCount: number }>(`/api/event/${slug}/selfie`, data),
  getGuestPhotos: (slug: string) => apiClient.get<PaginatedResponse<Photo>>(`/api/event/${slug}/guest/photos`),
  getMasterPhotos: (slug: string, token?: string) => apiClient.get<Photo[]>(`/api/event/${slug}/master/photos`, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined),
  getMasterFolders: (slug: string, token?: string) => apiClient.get<FolderNode[]>(`/api/event/${slug}/master/folders`, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined),
  toggleFavorite: (slug: string, data: { photoId: string }, token?: string) => apiClient.post<{ success: boolean }>(`/api/event/${slug}/master/favorite`, data, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined),
  getFavorites: (slug: string, token?: string) => apiClient.get<Photo[]>(`/api/event/${slug}/master/favorites`, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined),
  downloadGuestPhoto: (slug: string, photoId: string) => apiClient.get<{ url: string }>(`/api/event/${slug}/photos/${photoId}/download`),

  // Analytics
  getAnalyticsSummary: (eventId: string) => apiClient.get<AnalyticsSummary>(`/api/events/${eventId}/analytics/summary`),
  getAnalyticsTopPhotos: (eventId: string) => apiClient.get<{ photos: AnalyticsTopPhoto[] }>(`/api/events/${eventId}/analytics/top-photos`),
  getAnalyticsGuests: (eventId: string, page = 1, limit = 10, sortBy = 'guest_name', sortOrder = 'asc') => {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
      sortBy,
      sortOrder
    });
    return apiClient.get<PaginatedGuests>(`/api/events/${eventId}/analytics/guests?${params.toString()}`);
  },
  exportAnalyticsGuests: (eventId: string) => apiClient.get<Blob>(`/api/events/${eventId}/analytics/guests/export`),

  // Profile
  getProfile: () => apiClient.get<Photographer>('/api/profile'),
  updateProfile: (data: unknown) => apiClient.put<Photographer>('/api/profile', data),
  uploadLogo: (data: unknown) => apiClient.post<{ url: string }>('/api/profile/logo', data),
  uploadWatermark: (data: unknown) => apiClient.post<{ url: string }>('/api/profile/watermark', data),
  getStorageUsage: () => apiClient.get<{ used: number; limit: number }>('/api/profile/storage'),
};
