import { Event, EventType, EventStatus, Folder, FolderNode, Photo } from '@/types/event';
import { Photographer } from '@/types/user';
import { AnalyticsSummary, AnalyticsTopPhoto, PaginatedGuests } from '@/types/analytics';
import { PaginatedResponse, RegisterResponse, LoginOtpPendingResponse, TokenResponse } from '@/types/api';

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

  private async handle401(): Promise<void> {
    if (typeof window !== 'undefined') {
      try {
        await useAuthStore.getState().refreshToken();
        return; // Token refreshed, can retry
      } catch (e) {
        useAuthStore.getState().clearTokens();
      }
    }
    throw new ApiError(401, 'Unauthorized', 'UNAUTHORIZED');
  }

  private parseDetail(detail: unknown): string {
    if (Array.isArray(detail)) {
      return detail.map((err) => err.msg || JSON.stringify(err)).join(', ');
    }
    return typeof detail === 'string' ? detail : 'An error occurred';
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
        if (!path.includes('/auth/login') && !path.includes('/auth/refresh')) {
          await this.handle401();
          // Retry the request once with the new token
          const newToken = this.getToken();
          if (newToken) {
            const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` };
            const retryResponse = await fetch(`${this.baseUrl}${path}`, { ...fetchOptions, headers: retryHeaders });
            
            if (!retryResponse.ok) {
              const errorData = await retryResponse.json().catch(() => ({}));
              throw new ApiError(retryResponse.status, this.parseDetail(errorData.detail), errorData.code || 'UNKNOWN_ERROR', errorData.errors);
            }
            if (retryResponse.status === 204) return {} as T;
            return await retryResponse.json();
          }
        }
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
          response.status,
          this.parseDetail(errorData.detail),
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
  register: (data: unknown) => apiClient.post<RegisterResponse>('/api/v1/auth/register', data),
  login: (data: unknown) => apiClient.post<LoginOtpPendingResponse>('/api/v1/auth/login', data),
  logout: (refreshToken: string) =>
    apiClient.post<void>('/api/v1/auth/logout', { refresh_token: refreshToken }),
  refresh: (refreshToken: string) =>
    apiClient.post<TokenResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken }),
  forgotPassword: (data: unknown) =>
    apiClient.post<{ message: string }>('/api/v1/auth/forgot-password', data),
  resetPassword: (data: unknown) =>
    apiClient.post<{ message: string }>('/api/v1/auth/reset-password', data),
  sendOtp: (data: unknown) =>
    apiClient.post<{ message: string; expires_in: number }>('/api/v1/auth/send-otp', data),
  verifyOtp: (data: unknown) => apiClient.post<TokenResponse>('/api/v1/auth/verify-otp', data),

  // Events
  getEvents: () =>
    apiClient.get<{ events: Record<string, unknown>[]; total: number; offset: number; limit: number }>(
      '/api/v1/events'
    ),
  createEvent: (data: unknown) => apiClient.post<Record<string, unknown>>('/api/v1/events', data),
  getEventDetails: (id: string) => apiClient.get<Record<string, unknown>>(`/api/v1/events/${id}`),
  updateEvent: (id: string, data: unknown) =>
    apiClient.put<Record<string, unknown>>(`/api/v1/events/${id}`, data),
  deleteEvent: (id: string) => apiClient.delete<void>(`/api/v1/events/${id}`),
  archiveEvent: (id: string) => apiClient.post<void>(`/api/v1/events/${id}/archive`, {}),

  // Folders
  getFolders: (eventId: string) =>
    apiClient.get<{ folders: Record<string, unknown>[] }>(`/api/v1/events/${eventId}/folders`),
  createFolder: (eventId: string, data: unknown) =>
    apiClient.post<Folder>(`/api/v1/events/${eventId}/folders`, data),
  updateFolder: (eventId: string, folderId: string, data: unknown) =>
    apiClient.put<Folder>(`/api/v1/events/${eventId}/folders/${folderId}`, data),
  deleteFolder: (eventId: string, folderId: string, options?: { deletePhotos?: boolean }) => {
    const url = `/api/v1/events/${eventId}/folders/${folderId}${options?.deletePhotos ? '?delete_photos=true' : ''}`;
    return apiClient.delete<void>(url);
  },

  // Photos
  getEventPhotos: (eventId: string, offset = 0, limit = 50, folderId?: string) => {
    const params = new URLSearchParams({ offset: offset.toString(), limit: limit.toString() });
    if (folderId) params.append('folder_id', folderId);
    return apiClient.get<PaginatedResponse<Photo>>(`/api/v1/events/${eventId}/photos?${params.toString()}`);
  },
  deletePhoto: (eventId: string, photoId: string) =>
    apiClient.delete<void>(`/api/v1/events/${eventId}/photos/${photoId}`),
  movePhotos: (eventId: string, data: unknown) =>
    apiClient.post<void>(`/api/v1/events/${eventId}/photos/move`, data),
  downloadPhoto: (eventId: string, photoId: string, context: 'photographer' | 'master' | 'guest' = 'photographer', slug?: string) => {
    let url = `/api/v1/events/${eventId}/photos/${photoId}/download`;
    if (context === 'master' && slug) {
      url = `/api/v1/event/${slug}/master/photos/${photoId}/download`;
    } else if (context === 'guest' && slug) {
      url = `/api/v1/event/${slug}/photos/${photoId}/download`;
    }
    return apiClient.get<{ download_url: string }>(url);
  },

  // Upload
  createUpload: (data: unknown) => apiClient.post<{ uploadUrl: string }>('/api/v1/upload/create', data),
  uploadChunk: (uploadId: string, data: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiClient.patch<void>(`/api/v1/upload/${uploadId}`, data, options),
  getUploadOffset: (uploadId: string) => apiClient.head<{ offset: number }>(`/api/v1/upload/${uploadId}`),

  // Sharing
  getLinks: (eventId: string) => apiClient.get<unknown>(`/api/v1/events/${eventId}/links`),
  toggleLink: (eventId: string, type: 'guest' | 'master') =>
    apiClient.put<Record<string, unknown>>(`/api/v1/events/${eventId}/links/${type}/toggle`),
  updateEventSettings: (eventId: string, data: unknown) =>
    apiClient.put<Record<string, unknown>>(`/api/v1/events/${eventId}/settings`, data),

  // Guest / Couple
  getEventInfoPublic: (slug: string) => apiClient.get<unknown>(`/api/v1/event/${slug}/info`),
  getEventInfo: (slug: string) =>
    apiClient.get<{ event: Event; photographer: Photographer }>(`/api/v1/event/${slug}/info`),
  masterAuth: (slug: string, data: { name: string; phone: string }) =>
    apiClient.post<{ success: boolean }>(`/api/v1/event/${slug}/master/auth`, data),
  verifyMasterAuth: (slug: string, data: { name: string; phone: string; otp: string }) =>
    apiClient.post<{ token: string }>(`/api/v1/event/${slug}/master/verify`, data),
  sendGuestOtp: (slug: string, data: unknown) => apiClient.post<void>(`/api/v1/event/${slug}/auth`, data),
  verifyGuestOtp: (slug: string, data: { name: string; phone: string; otp: string }) =>
    apiClient.post<GuestTokenResponse>(`/api/v1/event/${slug}/auth/verify`, data),
  submitSelfie: (slug: string, data: unknown, token?: string) =>
    apiClient.post<{ matched_photo_ids: string[]; matched_photo_count: number; status: string }>(
      `/api/v1/event/${slug}/selfie`,
      data,
      token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
    ),
  getGuestPhotos: (slug: string, token?: string) =>
    apiClient.get<PaginatedResponse<Photo>>(
      `/api/v1/event/${slug}/guest/photos`,
      token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
    ),
  getMasterPhotos: (slug: string, token?: string) =>
    apiClient.get<PaginatedResponse<Photo>>(
      `/api/v1/event/${slug}/master/photos`,
      token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
    ),
  getMasterFolders: (slug: string, token?: string) =>
    apiClient.get<{ folders: FolderNode[] }>(
      `/api/v1/event/${slug}/master/folders`,
      token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
    ),
  toggleFavorite: (slug: string, data: { photo_id: string }, token?: string) =>
    apiClient.post<{ success: boolean }>(
      `/api/v1/event/${slug}/master/favorite`,
      data,
      token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
    ),
  getFavorites: (slug: string, token?: string) =>
    apiClient.get<PaginatedResponse<Photo>>(
      `/api/v1/event/${slug}/master/favorites`,
      token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
    ),
  downloadGuestPhoto: (slug: string, photoId: string) =>
    apiClient.get<{ url: string }>(`/api/v1/event/${slug}/photos/${photoId}/download`),

  // Analytics
  getAnalyticsSummary: (eventId: string) =>
    apiClient.get<AnalyticsSummary>(`/api/v1/events/${eventId}/analytics/summary`),
  getAnalyticsTopPhotos: (eventId: string) =>
    apiClient.get<{ photos: AnalyticsTopPhoto[] }>(`/api/v1/events/${eventId}/analytics/top-photos`),
  getAnalyticsGuests: (eventId: string, page = 1, limit = 10, sortBy = 'guest_name', sortOrder = 'asc') => {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
      sortBy,
      sortOrder
    });
    return apiClient.get<PaginatedGuests>(`/api/v1/events/${eventId}/analytics/guests?${params.toString()}`);
  },
  exportAnalyticsGuests: (eventId: string) =>
    apiClient.get<Blob>(`/api/v1/events/${eventId}/analytics/guests/export`),

  // Profile
  getProfile: () => apiClient.get<Photographer>('/api/v1/profile'),
  updateProfile: (data: unknown) => apiClient.put<Photographer>('/api/v1/profile', data),
  uploadLogo: (data: unknown) => apiClient.post<{ url: string }>('/api/v1/profile/logo', data),
  uploadWatermark: (data: unknown) => apiClient.post<{ url: string }>('/api/v1/profile/watermark', data),
  getStorageUsage: () => apiClient.get<{ used: number; limit: number }>('/api/v1/profile/storage'),
};
